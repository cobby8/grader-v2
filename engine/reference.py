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
