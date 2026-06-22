# -*- coding: utf-8 -*-
"""reference — 완성본(샘플 번호·이름이 박힌 디자인)에서 '어디에·어떤 크기·색으로'
배번/이름이 들어가는지를 자동 추출한다.

쓰임(계획서 §3 "차이가 곧 위치"):
  디자이너가 완성본 + 빈 템플릿을 주면, 완성본에서 추출한 이 좌표/크기/색을 그대로
  빈 템플릿에 선수별 글자로 주입한다. 사람이 좌표를 손으로 넣지 않아도 된다.

추출 대상(모두 design(page) 좌표 = pt):
  · 이름(보통 뒤판 상단): 살아있는 텍스트(BT…ET) → Tm 위치 + 글자 높이 추정.
  · 번호(앞/뒤): 그림에 구워진 흰색(또는 단색) 윤곽선 채움(숫자 글리프) → 묶어서 bbox·색.

원리:
  콘텐츠 스트림을 CTM(좌표변환) 추적하며 훑어, 채움(fill)마다 page 좌표 bbox·색을 모은다.
  '큰 단색 채움이 가로로 인접해 모인 덩어리' = 번호(여러 자리 숫자). 이를 앞/뒤로 나눠
  number_region 으로 보고한다. 살아있는 텍스트는 name_block 으로 보고한다.
  ⚠️ 1차 휴리스틱: 디자인마다 검증 필요. 빈 템플릿과 diff 하면 더 정확(향후 옵션).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import pikepdf
from pikepdf import parse_content_stream

Box = Tuple[float, float, float, float]  # (x0,y0,x1,y1) page 좌표


def _mm(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2, c1 * a2 + d1 * c2,
            c1 * b2 + d1 * d2, e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


def _ap(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _nums(operands):
    out = []
    for o in operands:
        try:
            out.append(float(o))
        except Exception:
            return None
    return out


def _collect_fills(page) -> Tuple[list, list]:
    """페이지의 (채움 목록, 텍스트블록 목록)을 page 좌표로 수집.

    채움: [{"color": (c,m,y,k)|None, "bbox": (x0,y0,x1,y1)}]
    텍스트: [{"tm": (a,b,c,d,e,f), "size": 추정높이, "pos": (x,y)}]
    """
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    stack: List[tuple] = []
    color: Optional[tuple] = None
    pts: List[Tuple[float, float]] = []
    fills: list = []
    texts: list = []

    in_text = False
    text_tm = None

    for operands, op in parse_content_stream(page):
        o = str(op)
        n = _nums(operands)
        if o == "q":
            stack.append(ctm)
        elif o == "Q":
            ctm = stack.pop() if stack else ctm
        elif o == "cm" and n and len(n) >= 6:
            ctm = _mm(tuple(n[:6]), ctm)
        elif o in ("scn", "k") and n and len(n) == 4:
            color = tuple(round(v, 4) for v in n)
        elif o == "BT":
            in_text = True
            text_tm = None
        elif o == "ET":
            if text_tm is not None:
                a, b, c, d, e, f = text_tm
                pos = _ap(ctm, e, f)
                # 글자 높이 ≈ d(세로 스케일). 행렬에 폰트크기가 녹아있는 경우가 많다.
                size = abs(d) if d else abs(a)
                texts.append({"tm": text_tm, "size": round(size, 2),
                              "pos": (round(pos[0], 2), round(pos[1], 2))})
            in_text = False
        elif o == "Tm" and n and len(n) >= 6:
            text_tm = tuple(n[:6])
        elif o == "m" and n and len(n) >= 2:
            pts.append(_ap(ctm, n[0], n[1]))
        elif o == "l" and n and len(n) >= 2:
            pts.append(_ap(ctm, n[0], n[1]))
        elif o == "c" and n and len(n) >= 6:
            pts.append(_ap(ctm, n[4], n[5]))
        elif o in ("v", "y") and n and len(n) >= 4:
            pts.append(_ap(ctm, n[2], n[3]))
        elif o == "re" and n and len(n) >= 4:
            x, y, w, h = n[:4]
            pts += [_ap(ctm, x, y), _ap(ctm, x + w, y + h)]
        elif o in ("f", "F", "f*", "b", "b*", "B", "B*"):
            if pts:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                fills.append({"color": color,
                              "bbox": (min(xs), min(ys), max(xs), max(ys))})
            pts = []
        elif o in ("n", "S", "s", "W", "W*"):
            pts = []
    return fills, texts


def _cluster_number(fills: list, x_lo: float, x_hi: float,
                    y_lo: float, y_hi: float,
                    min_w: float = 100.0, min_h: float = 250.0,
                    max_w: float = 700.0, max_h: float = 900.0) -> Optional[dict]:
    """주어진 영역 안의 '숫자 글리프 후보 채움'을 묶어 번호 영역 1개로 만든다.

    크기 창(min/max)으로 패널 배경(너무 큼)·작은 글자(YONSEI 등, 너무 작음)·줄무늬(가늘고 긺)를
    배제하고 '번호 자릿수 글리프'만 남긴다. 향후 빈 템플릿과 diff 하면 이 휴리스틱 없이도 정확.

    반환: {"bbox": 합친 bbox, "color": 대표색, "glyph_boxes": [개별 글자 bbox...]} | None
    """
    cand = []
    for fl in fills:
        b = fl["bbox"]
        cx = (b[0] + b[2]) / 2; cy = (b[1] + b[3]) / 2
        w = b[2] - b[0]; h = b[3] - b[1]
        if (x_lo <= cx <= x_hi and y_lo <= cy <= y_hi
                and min_w <= w <= max_w and min_h <= h <= max_h):
            cand.append(fl)
    if not cand:
        return None
    xs0 = [c["bbox"][0] for c in cand]; ys0 = [c["bbox"][1] for c in cand]
    xs1 = [c["bbox"][2] for c in cand]; ys1 = [c["bbox"][3] for c in cand]
    # 대표색 = 가장 흔한 색
    from collections import Counter
    col = Counter(c["color"] for c in cand).most_common(1)[0][0]
    return {
        "bbox": (round(min(xs0), 1), round(min(ys0), 1), round(max(xs1), 1), round(max(ys1), 1)),
        "color": col,
        "glyph_boxes": [tuple(round(v, 1) for v in c["bbox"]) for c in cand],
        "count": len(cand),
    }


def extract_reference(design_path: str, page_index: int = 0,
                      page_width: Optional[float] = None) -> dict:
    """완성본에서 앞번호/뒤번호/뒤이름의 위치·크기·색을 추출한다.

    page_width 를 주면 그 값으로 앞(왼쪽)/뒤(오른쪽)를 나눈다. 없으면 MediaBox 폭의 절반.
    반환(dict): {
      "page_size": (w,h),
      "name_blocks": [{pos,size,tm}...],          # 살아있는 텍스트(이름)
      "front_number": {bbox,color,count}|None,
      "back_number":  {bbox,color,count}|None,
    }
    """
    pdf = pikepdf.open(design_path)
    page = pdf.pages[page_index]
    mb = [float(v) for v in page.MediaBox]
    pw = page_width or (mb[2] - mb[0])
    ph = mb[3] - mb[1]
    mid = mb[0] + pw / 2.0

    fills, texts = _collect_fills(page)

    # 흰색 또는 단색(4채널) 채움만 번호 후보로 본다. 색 무관하게 큰 글자 덩어리를 찾되,
    # 흰색(0,0,0,0) 우선. (디자인 대부분 번호=흰색)
    # 번호는 보통 패널 중앙 하단(세로 중앙±) — y 범위를 넓게 잡고 큰 채움만 추린다.
    y_lo, y_hi = ph * 0.45, ph * 0.95   # 상단~중앙(좌표는 아래가 0)
    front = _cluster_number(fills, mb[0], mid, y_lo, y_hi)
    back = _cluster_number(fills, mid, mb[2], y_lo, y_hi)

    # 이름: 텍스트블록 중 뒤판(오른쪽)·상단의 것(번호보다 위)
    name_blocks = []
    for t in texts:
        x, y = t["pos"]
        name_blocks.append(t)

    pdf.close()
    return {
        "page_size": (round(pw, 2), round(ph, 2)),
        "split_x": round(mid, 2),
        "name_blocks": name_blocks,
        "front_number": front,
        "back_number": back,
    }


# ════════════════════════════════════════════════════════════════════════════
# Phase B — 이름 fitz rawdict 정밀 추출 + preset area JSON 초안 묶기
#
#   pikepdf(extract_reference)는 번호(구워진 흰색 채움)에 강하지만, '살아있는 텍스트'인
#   이름은 fitz rawdict 가 size·font·bbox·문자별 origin(중심·baseline·음절피치)을 훨씬
#   정밀하게 준다. 두 추출을 합쳐 preset 이 바로 먹는 area JSON 초안으로 묶는다.
# ════════════════════════════════════════════════════════════════════════════


def _name_from_rawdict(design_path: str, page_index: int, x_lo: float, x_hi: float):
    """fitz rawdict 로 '뒤판 이름'을 정밀 추출한다(완성본 단독, 템플릿 불필요).

    fitz 좌표는 좌상단 원점·y아래로 증가 → 우리(좌하단 원점·y위로)와 다르므로
    y 를 page_h - y 로 뒤집어 design pt 로 통일한다.

    반환: {
      "text": "김경원", "size": 136.4, "font": "H2hdrM",
      "center_x": 3219.8, "baseline": 4765.7, "pitch": 195.4,
      "bbox": (x0,y0,x1,y1)   # 좌하단 원점 design pt
    } | None
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    doc = fitz.open(design_path)
    page = doc[page_index]
    page_h = page.rect.height
    raw = page.get_text("rawdict")           # span/char 단위 상세 구조

    # ── 후보 span 수집: 뒤판(x_lo..x_hi) 영역의 한글 텍스트 라인. ──
    #    가장 큰 글자(size 최대)를 이름으로 본다(YONSEI 등 작은 워드마크 배제).
    best = None
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars", [])
                if not chars:
                    continue
                # span 가로중심(fitz 좌표 그대로 x) 으로 앞/뒤 판정.
                sb = span.get("bbox", (0, 0, 0, 0))
                scx = (sb[0] + sb[2]) / 2.0
                if not (x_lo <= scx <= x_hi):
                    continue
                size = float(span.get("size", 0.0))
                if best is None or size > best["size"]:
                    best = {"size": size, "font": span.get("font", ""),
                            "bbox": sb, "chars": chars}

    if best is None:
        doc.close()
        return None

    chars = best["chars"]
    # ── 문자별 origin(=baseline 시작점, fitz 좌표) 로 중심·피치 산출 ──
    #    각 char 의 origin x 와 advance(다음 char origin - 현재 origin)로 음절 중심·피치.
    text = "".join(c.get("c", "") for c in chars)
    origins = [c.get("origin", (0.0, 0.0)) for c in chars]

    # baseline(design pt) = page_h - origin_y. 모든 char 거의 동일 → 평균.
    baseline = page_h - sum(o[1] for o in origins) / len(origins)

    # 가로 중심 = span bbox 중심(fitz x 그대로, 좌우 반전 없음).
    sb = best["bbox"]
    center_x = (sb[0] + sb[2]) / 2.0

    # ── 음절 피치 = '비공백 음절'끼리의 origin x 간격 중앙값 ──
    #    완성본은 자간을 "음절+공백+Tc"로 주므로, 공백 char origin 이 음절 사이에 끼어
    #    작은 간격을 만든다. 진짜 음절 피치는 글자(비공백)끼리의 중심 거리이므로,
    #    공백 char 를 빼고 비공백 음절만 모아 인접 간격을 잰다.
    real_xs = sorted(o[0] for c, o in zip(chars, origins)
                     if c.get("c", "").strip() != "")
    gaps = [real_xs[i + 1] - real_xs[i] for i in range(len(real_xs) - 1)
            if real_xs[i + 1] - real_xs[i] > 1.0]
    if gaps:
        gaps.sort()
        pitch = gaps[len(gaps) // 2]          # 중앙값(이상치에 강함)
    else:
        pitch = 0.0

    # bbox 를 design pt(좌하단 원점)로 변환.
    bx0, by0, bx1, by1 = sb
    bbox_design = (round(bx0, 1), round(page_h - by1, 1),
                   round(bx1, 1), round(page_h - by0, 1))

    doc.close()
    return {
        "text": text,
        "size": round(best["size"], 2),
        "font": best["font"],
        "center_x": round(center_x, 1),
        "baseline": round(baseline, 1),
        "pitch": round(pitch, 1),
        "bbox": bbox_design,
    }


def _number_area_from_cluster(cluster: Optional[dict]) -> Optional[dict]:
    """_cluster_number 결과(번호 채움 덩어리)를 preset number_area 초안으로 변환.

    preset 스키마: {"center":[cx,cy], "cap_height":h, "color_cmyk":[c,m,y,k]}
      · center = 합친 bbox 의 (가로중심, 세로중심).
      · cap_height = 합친 bbox 의 세로 높이(자릿수 잉크 높이 근사).
      · color_cmyk = 대표색(없으면 흰색 [0,0,0,0]).
    """
    if not cluster:
        return None
    x0, y0, x1, y1 = cluster["bbox"]
    cx = round((x0 + x1) / 2.0, 1)
    cy = round((y0 + y1) / 2.0, 1)
    cap_h = round(y1 - y0, 1)
    col = cluster.get("color")
    color_cmyk = list(col) if col else [0, 0, 0, 0]
    return {"center": [cx, cy], "cap_height": cap_h, "color_cmyk": color_cmyk}


def build_area_preset(design_path: str, page_index: int = 0,
                      page_width: Optional[float] = None,
                      font: str = "data/fonts/HY헤드라인M.ttf") -> dict:
    """완성본에서 preset area JSON 초안(front/back number + back name)을 만든다.

    완성본 단독으로 동작(템플릿 생략 허용). 추출 실패 부분은 None 으로 남기고 경고에 담아
    크래시 없이 사람이 보충하도록 한다(친절한 한글 메시지).

    반환: {
      "page_size": [w,h], "split_x": x,
      "areas": {                                   # ← preset.json 에 붙일 초안
         "front_number_area": {center, cap_height, color_cmyk, font} | None,
         "back_number_area":  {center, cap_height, color_cmyk, font} | None,
         "back_name_area":    {center_x, baseline, em_pt, pitch, color_cmyk, font} | None,
      },
      "name_detail": {...} | None,                 # 추출 원본(검수용)
      "warnings": [...],
    }
    """
    warnings: List[str] = []

    # ── 1) 번호: 기존 pikepdf 추출(extract_reference) 재사용(무수정). ──
    ref = extract_reference(design_path, page_index=page_index, page_width=page_width)
    pw, ph = ref["page_size"]
    split_x = ref["split_x"]

    front_area = _number_area_from_cluster(ref["front_number"])
    back_area = _number_area_from_cluster(ref["back_number"])
    if front_area is None:
        warnings.append("🟡 앞 번호(왼쪽 절반)를 자동 추출하지 못했습니다 — preset 에 직접 넣어주세요.")
    if back_area is None:
        warnings.append("🟡 뒤 번호(오른쪽 절반)를 자동 추출하지 못했습니다 — preset 에 직접 넣어주세요.")

    # 번호 area 에 폰트 경로 부착(preset 스키마 일치).
    if front_area is not None:
        front_area["font"] = font
    if back_area is not None:
        back_area["font"] = font

    # ── 2) 이름: fitz rawdict 정밀 추출(뒤판=오른쪽 절반). ──
    #    fitz 좌표는 좌상단 원점이라 x 는 그대로지만, 페이지 폭 절반 기준 오른쪽을 뒤판으로 본다.
    name_detail = _name_from_rawdict(design_path, page_index, split_x, pw)
    name_area = None
    if name_detail is not None and name_detail["text"].strip():
        col = ref["back_number"]["color"] if ref.get("back_number") else None
        color_cmyk = list(col) if col else [0, 0, 0, 0]
        name_area = {
            "center_x": name_detail["center_x"],
            "baseline": name_detail["baseline"],
            "em_pt": name_detail["size"],
            "pitch": name_detail["pitch"],
            "color_cmyk": color_cmyk,
            "font": font,
        }
    else:
        warnings.append("🟡 뒤 이름(살아있는 텍스트)을 자동 추출하지 못했습니다 — preset 에 직접 넣어주세요.")

    return {
        "page_size": [pw, ph],
        "split_x": split_x,
        "areas": {
            "front_number_area": front_area,
            "back_number_area": back_area,
            "back_name_area": name_area,
        },
        "name_detail": name_detail,
        "warnings": warnings,
    }


# ════════════════════════════════════════════════════════════════════════════
# Phase C — 합성 작업1: 조각 자동 매핑(디자인 재단선 ↔ 패턴 SVG 조각)
#
#   목적: preset.json 의 pieces(어느 디자인 영역이 어느 SVG 조각에 얹히는가)를
#         사람이 손으로 좌표를 넣지 않고 자동 산출한다.
#
#   원리(계획서 "차이가 곧 위치"):
#     ① 디자인 .ai 안의 "패턴선/재단선" 레이어(OCG)에 그려진 닫힌 윤곽 = 각 조각의
#        실제 재단 경계. 이 윤곽의 bbox 가 곧 'design_region_pt'(앞/뒤/밴드 영역).
#     ② 패턴 SVG 조각들의 bbox·넥깊이를 측정한다.
#     ③ 둘을 규칙(높이 최소=밴드, 좌/우 + 넥 형태)으로 짝지어 svg_index 를 정한다.
#
#   왜 OCG(레이어)로 거르나:
#     본체(파란 색면)·요소까지 다 모으면 영역이 뭉개진다. 재단선 레이어만 추리면
#     '조각 1개 = 닫힌 윤곽 1개'로 깨끗하게 떨어진다(앞/뒤/밴드 = 3개).
# ════════════════════════════════════════════════════════════════════════════

# 재단 경계로 인정할 OCG 레이어명(디자이너 명명 차이를 흡수).
_CUTLINE_LAYER_NAMES = ("패턴선", "재단선")


def _ocg_property_names(page) -> dict:
    """페이지의 마킹 프로퍼티명(/MCx) → 레이어 사람이름(한글) 매핑을 만든다.

    Adobe Illustrator 는 레이어를 OCG(Optional Content Group)로 내보내며,
    콘텐츠 스트림의 `/OC /MCx BDC … EMC` 가 그 레이어 구간을 표시한다.
    레이어 이름은 Resources.Properties[/MCx].Name 또는 OCProperties.OCGs[].Name 에
    UTF-16(BOM 포함) 바이트로 들어있다 → 디코딩해 한글로 되돌린다.
    """
    names: dict = {}

    def _decode(name_obj) -> Optional[str]:
        # pikepdf.String → UTF-16(BOM) 바이트. BOM 없으면 latin-1 폴백.
        try:
            b = bytes(name_obj)
        except Exception:
            return None
        if b[:2] in (b"\xfe\xff", b"\xff\xfe"):
            try:
                return b.decode("utf-16")
            except Exception:
                return None
        try:
            return b.decode("latin-1")
        except Exception:
            return None

    # ── 1순위: 페이지 Resources.Properties(/MCx → OCG dict) ──
    try:
        props = page.Resources.get("/Properties")
    except Exception:
        props = None
    if props is not None:
        for mc_key, ocg in props.items():
            try:
                nm = ocg.get("/Name")
            except Exception:
                nm = None
            if nm is not None:
                dec = _decode(nm)
                if dec is not None:
                    names[str(mc_key)] = dec
    return names


def _mc_matches_cutline(operands, mcmap: dict) -> bool:
    """BDC 오퍼랜드(`/OC /MCx`)가 재단선 레이어를 가리키면 True.

    operands 는 보통 [Name('/OC'), Name('/MCx')] 형태. 두 번째가 레이어 프로퍼티명.
    """
    if len(operands) < 2:
        return False
    mc = str(operands[1])
    layer = mcmap.get(mc)
    return layer in _CUTLINE_LAYER_NAMES


def _collect_cutline_subpaths(stream, mcmap: dict, base_ctm: tuple,
                              in_target: bool, out: list,
                              page_resources) -> None:
    """콘텐츠 스트림을 훑어 '재단선 레이어 구간'의 닫힌 서브패스 bbox 를 page 좌표로 모은다.

    핵심 동작:
      · q/Q 로 CTM(좌표변환) 스택을 추적하고, cm 으로 누적한다.
      · BDC/EMC 의 '마킹 깊이'를 스택으로 추적해, 재단선 레이어 안쪽인지(in_target) 안다.
        (중첩 마킹도 안전 — 들어올 때 현재 상태를 push, 나갈 때 pop)
      · m/l/c/v/y/re 로 현재 서브패스 점을 CTM 적용해 모으고, 칠/획/끝(f/S/n…) 시점에
        target 안이고 점이 3개 이상이면 그 bbox 를 수집한다.
      · Do(Form XObject, 예: Fm0) 를 만나면 그 Form 안으로 재귀(Matrix·in_target 전파).
        → 재단선이 Form 안에 들어있는 경우도 놓치지 않는다.
    """
    ctm = base_ctm
    stack: List[tuple] = []
    cur: List[Tuple[float, float]] = []   # 현재 서브패스 점들(page 좌표)
    start: Optional[Tuple[float, float]] = None
    mc_stack: List[bool] = []             # BDC/EMC 마킹 깊이별 in_target 보관

    # Form 안에서는 그 Form 의 Resources 가 우선(없으면 페이지 것).
    res = getattr(stream, "Resources", None) or page_resources

    for operands, op in parse_content_stream(stream):
        o = str(op)
        n = _nums(operands)
        if o == "q":
            stack.append(ctm)
        elif o == "Q":
            ctm = stack.pop() if stack else ctm
        elif o == "cm" and n and len(n) >= 6:
            ctm = _mm(tuple(n[:6]), ctm)
        elif o == "BDC":
            # 마킹 진입: 현재 in_target 을 보관하고, 재단선 레이어면 켠다.
            mc_stack.append(in_target)
            if _mc_matches_cutline(operands, mcmap):
                in_target = True
        elif o == "BMC":
            # 이름만 있는 마킹(레이어 아님) — 깊이만 추적.
            mc_stack.append(in_target)
        elif o == "EMC":
            in_target = mc_stack.pop() if mc_stack else in_target
        elif o == "m" and n and len(n) >= 2:
            cur = [_ap(ctm, n[0], n[1])]
            start = cur[0]
        elif o == "l" and n and len(n) >= 2:
            cur.append(_ap(ctm, n[0], n[1]))
        elif o == "c" and n and len(n) >= 6:
            cur.append(_ap(ctm, n[4], n[5]))
        elif o in ("v", "y") and n and len(n) >= 4:
            cur.append(_ap(ctm, n[2], n[3]))
        elif o == "re" and n and len(n) >= 4:
            x, y, w, h = n[:4]
            cur = [_ap(ctm, x, y), _ap(ctm, x + w, y),
                   _ap(ctm, x + w, y + h), _ap(ctm, x, y + h)]
            start = cur[0]
        elif o == "h":
            if start is not None:
                cur.append(start)
        elif o in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"):
            # 경로 페인팅/종료: 재단선 레이어 안이고 닫힌 모양이면 bbox 수집.
            if in_target and len(cur) >= 3:
                xs = [p[0] for p in cur]; ys = [p[1] for p in cur]
                out.append((min(xs), min(ys), max(xs), max(ys)))
            cur = []
            start = None
        elif o == "Do":
            # Form XObject 재귀(/MC2 요소 안의 Fm0 등도 추적).
            if operands:
                xname = str(operands[0])
                try:
                    xo = res.get("/XObject", {}).get(xname)
                except Exception:
                    xo = None
                if xo is not None and str(xo.get("/Subtype")) == "/Form":
                    fm_ctm = ctm
                    if "/Matrix" in xo:
                        try:
                            fm_ctm = _mm(tuple(float(v) for v in xo.Matrix), ctm)
                        except Exception:
                            fm_ctm = ctm
                    _collect_cutline_subpaths(xo, mcmap, fm_ctm, in_target,
                                              out, page_resources)


def _body_fallback_bboxes(page) -> list:
    """재단선 레이어가 없을 때의 폴백: 페이지 안 큰 채움(몸판) bbox 들을 면적순으로.

    완벽하진 않지만(본체 색면 기준) 자동매핑이 아예 비는 것보다 낫다 → 경고와 함께 반환.
    """
    fills, _texts = _collect_fills(page)
    boxes = []
    for fl in fills:
        b = fl["bbox"]
        w = b[2] - b[0]; h = b[3] - b[1]
        if w > 100 and h > 100:        # 너무 작은 잡채움 제외
            boxes.append(b)
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return boxes


def extract_design_pieces(design_pdf: str, n_pieces: Optional[int] = None,
                          page_index: int = 0) -> List[dict]:
    """디자인 .ai/.pdf 의 재단선 레이어에서 조각 영역(bbox)을 자동 추출한다.

    반환: [{"design_region_pt": (x0,y0,x1,y1), "area": 면적, "source": "cutline"|"body"}]
          면적 내림차순. n_pieces 를 주면 상위 N 개만.

    동작:
      ① OCG 프로퍼티명(/MCx)→레이어명 매핑(UTF-16 디코딩).
      ② "패턴선/재단선" 레이어 구간의 닫힌 서브패스 bbox 를 CTM 적용해 수집(Form 내부 포함).
      ③ 면적 상위 N. 없으면 몸판 채움 폴백(+경고는 호출부에서 처리).
    """
    pdf = pikepdf.open(design_pdf)
    try:
        page = pdf.pages[page_index]
        mcmap = _ocg_property_names(page)

        raw: list = []
        _collect_cutline_subpaths(page, mcmap, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                                  False, raw, page.Resources)

        source = "cutline"
        if not raw:
            # ── 폴백: 재단선 레이어를 못 찾음 → 몸판 채움으로 근사(경고 대상). ──
            raw = _body_fallback_bboxes(page)
            source = "body"

        pieces = []
        for b in raw:
            x0, y0, x1, y1 = b
            pieces.append({
                "design_region_pt": (round(x0, 1), round(y0, 1),
                                     round(x1, 1), round(y1, 1)),
                "area": round((x1 - x0) * (y1 - y0), 1),
                "source": source,
            })
        # 면적 내림차순(큰 조각=몸판 먼저). 동일 bbox 중복 제거.
        seen = set()
        uniq = []
        for p in sorted(pieces, key=lambda d: d["area"], reverse=True):
            key = tuple(round(v) for v in p["design_region_pt"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(p)
        if n_pieces is not None:
            uniq = uniq[:n_pieces]
        return uniq
    finally:
        pdf.close()


def measure_svg_pieces(polylines) -> List[dict]:
    """패턴 SVG 조각(Polyline 목록)의 bbox·넥깊이를 측정한다.

    넥깊이: 조각 '상단 35%' 높이 안에서 '가로 중앙 ±15%' 컬럼의 최저 y 를 찾아,
            윗변(y1)에서 얼마나 파여 들어왔는지(=목둘레 파임). V넥은 크고 라운드는 작다.

    반환(입력 순서 보존 — 인덱스가 곧 svg_index):
      [{"index": i, "bbox": (x0,y0,x1,y1), "width": w, "height": h,
        "cx": 가로중심, "neck_depth": 넥깊이}]
    """
    out = []
    for i, pl in enumerate(polylines):
        x0, y0, x1, y1 = pl.bbox
        w = x1 - x0; h = y1 - y0
        cx = (x0 + x1) / 2.0
        # 상단 35% 영역(y 위로 증가하므로 윗변에서 0.35*h 만큼 내려온 선 위쪽).
        top_thresh = y1 - 0.35 * h
        x_lo = cx - 0.15 * w; x_hi = cx + 0.15 * w
        col_ys = [py for (px, py) in pl.points
                  if x_lo <= px <= x_hi and py >= top_thresh]
        neck_depth = (y1 - min(col_ys)) if col_ys else 0.0
        out.append({
            "index": i,
            "bbox": (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)),
            "width": round(w, 1),
            "height": round(h, 1),
            "cx": round(cx, 1),
            "neck_depth": round(neck_depth, 1),
        })
    return out


def match_pieces(design_bboxes: List[dict], svg_measures: List[dict]) -> List[dict]:
    """디자인 재단영역(design_bboxes)과 SVG 조각(svg_measures)을 짝지어 svg_index 를 정한다.

    규칙(계획서):
      · 밴드(band): 양쪽 모두에서 '높이가 가장 작은' 것끼리 매칭.
      · 앞/뒤: 남은 둘을 좌/우 위치 + 넥깊이로 가른다.
          - 좌측(작은 cx) ↔ 넥깊이 큰(=V넥) = 앞판(front)
          - 우측(큰 cx)   ↔ 넥깊이 작은(=라운드) = 뒤판(back)
      · 불일치(예: 좌측인데 넥이 더 얕음) 시 경고를 담는다.

    반환: [{"id","name","design_region_pt","svg_index"} ...] + 마지막 항목에
          별도로 경고를 붙이지 않고, 함수는 (pieces, warnings) 가 아닌 pieces 만 반환.
          (경고는 build_pieces_preset 가 따로 모은다 — 여기선 _warn 키로 첨부)
    """
    # 디자인 bbox 도 면적순(이미 그렇지만 안전하게) → 큰 둘 = 몸판, 작은 = 밴드.
    dz = sorted(design_bboxes, key=lambda d: d["area"], reverse=True)
    sv = sorted(svg_measures, key=lambda d: d["height"], reverse=True)

    warns: List[str] = []
    result: List[dict] = []

    if len(dz) < 3 or len(sv) < 3:
        # 3조각(앞/뒤/밴드)이 아니면 가능한 만큼만 면적·높이순으로 1:1 매칭(경고).
        warns.append("🟡 조각 수가 3개(앞/뒤/밴드)가 아닙니다 — 면적·높이순 단순 매칭으로 진행합니다.")
        for i, (d, s) in enumerate(zip(dz, sv)):
            result.append({"id": f"piece{i}", "name": f"조각{i}",
                           "design_region_pt": d["design_region_pt"],
                           "svg_index": s["index"]})
        return {"pieces": result, "warnings": warns}

    # ── 밴드: 양쪽에서 가장 작은(면적/높이 최소) 것. ──
    band_design = min(dz, key=lambda d: d["area"])
    band_svg = min(sv, key=lambda d: d["height"])

    # ── 남은 둘(앞/뒤 후보) ──
    body_design = [d for d in dz if d is not band_design]
    body_svg = [s for s in sv if s is not band_svg]

    # 디자인: x0 작은 쪽=좌측(앞), 큰 쪽=우측(뒤).
    body_design.sort(key=lambda d: d["design_region_pt"][0])
    d_front, d_back = body_design[0], body_design[1]

    # SVG: 넥깊이 큰 쪽=앞(V넥), 작은 쪽=뒤(라운드).
    body_svg.sort(key=lambda s: s["neck_depth"], reverse=True)
    s_front, s_back = body_svg[0], body_svg[1]

    # ── 교차 검증: 좌/우 위치와 넥깊이 정렬이 서로 모순되지 않는지. ──
    #    앞(좌측 디자인)에 매칭된 SVG 의 cx 가 뒤 SVG 의 cx 보다 커야 자연스럽지 않다 —
    #    SVG 좌표는 별개 viewBox 라 위치보다 넥깊이를 우선하되, 둘이 어긋나면 경고만.
    if s_front["neck_depth"] <= s_back["neck_depth"]:
        warns.append("🟡 앞/뒤 넥깊이 구분이 모호합니다(앞 넥깊이 ≤ 뒤). 결과를 육안 확인하세요.")
    if s_front["cx"] > s_back["cx"]:
        # SVG 상에서도 앞(좌)·뒤(우)가 위치로 자연스러운지 참고(절대조건 아님).
        warns.append("🟡 SVG 좌우 위치가 넥깊이 기반 앞/뒤 판정과 다릅니다 — 넥깊이 우선 적용했습니다.")

    result = [
        {"id": "front", "name": "앞판",
         "design_region_pt": d_front["design_region_pt"],
         "svg_index": s_front["index"]},
        {"id": "back", "name": "뒤판",
         "design_region_pt": d_back["design_region_pt"],
         "svg_index": s_back["index"]},
        {"id": "band", "name": "넥밴드",
         "design_region_pt": band_design["design_region_pt"],
         "svg_index": band_svg["index"]},
    ]
    return {"pieces": result, "warnings": warns}


def build_pieces_preset(design_pdf: str, svgdir: str, base: str = "XL") -> dict:
    """디자인 .ai + 패턴 SVG 폴더로 preset 의 pieces(svg_index·design_region_pt)를 자동 산출.

    동작:
      ① extract_design_pieces 로 재단선 영역(앞/뒤/밴드) 추출.
      ② base 사이즈 SVG(예: XL.svg)를 parse_svg → measure_svg_pieces.
      ③ match_pieces 로 둘을 짝지어 svg_index 결정.

    반환: {"pieces": [...], "warnings": [...], "base_svg": 경로, "source": "cutline"|"body"}
    """
    import os

    from .pattern import parse_svg

    warnings: List[str] = []

    # ── 1) 디자인 재단영역 추출(상위 3개 = 앞/뒤/밴드). ──
    design_pieces = extract_design_pieces(design_pdf, n_pieces=3)
    if not design_pieces:
        warnings.append("🔴 디자인에서 조각 영역을 하나도 찾지 못했습니다 — preset 을 직접 점검하세요.")
        return {"pieces": [], "warnings": warnings, "base_svg": None, "source": None}
    source = design_pieces[0]["source"]
    if source == "body":
        warnings.append("🟡 재단선 레이어(패턴선/재단선)를 못 찾아 '몸판 채움'으로 근사했습니다 — "
                        "영역이 부정확할 수 있으니 육안 확인하세요.")

    # ── 2) base 사이즈 SVG 측정. ──
    base_svg = os.path.join(svgdir, f"{base}.svg")
    if not os.path.exists(base_svg):
        warnings.append(f"🔴 base SVG 가 없습니다: {base_svg}")
        return {"pieces": [], "warnings": warnings, "base_svg": base_svg, "source": source}
    polys = parse_svg(base_svg)
    svg_measures = measure_svg_pieces(polys)

    # ── 3) 매칭 → svg_index 결정. ──
    matched = match_pieces(design_pieces, svg_measures)
    warnings.extend(matched["warnings"])

    return {
        "pieces": matched["pieces"],
        "warnings": warnings,
        "base_svg": base_svg,
        "source": source,
    }
