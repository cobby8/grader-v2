# -*- coding: utf-8 -*-
"""number_glyphs — 디자이너 '번호 글리프셋'(0~9 블록체)을 .ai 에서 추출해 번호를 렌더한다.

────────────────────────────────────────────────────────────────────────────
큰 그림 (비유)
  · 지금까지 번호는 폰트(HY헤드라인M)를 아웃라인으로 펴서 그렸다.
  · 그런데 디자이너가 만든 유니폼 번호는 폰트가 아니라 '직접 그린 athletic 블록체'다.
    (획 끝이 각지고, 두꺼우며, 폰트 숫자와 모양이 분명히 다르다.)
  · 그래서 디자이너가 .ai 안 ArtBox 에 1~0 까지 10개 숫자를 그려둔 '견본판(글리프셋)'을
    그대로 떼어내(추출), JSON 으로 저장해 두고, 번호를 그릴 때 폰트 대신 이 견본을 조립한다.
    → "23" = 떼어둔 '2' 도형 + '3' 도형을 나란히 놓아 만든다(폰트 불필요, 디자이너 모양 그대로).
────────────────────────────────────────────────────────────────────────────

핵심 사실(소스 조사로 확정):
  · 소스 .ai ArtBox[585,4673,3923,5211] 안에 단색 fill 경로 정확히 10개(=숫자 견본)가 있다.
  · x 오름차순으로 정렬하면 순서가 order="1234567890" 이다(왼쪽부터 1,2,…,9,0).
  · 각 글리프 cap_height ≈ 538.6pt, "1"만 폭 156(좁음)·나머지 ~298~334.
  · 구멍(0/4/6/8/9 안쪽)은 여러 subpath + non-zero winding fill('f')로 자동 처리된다.
  · 색은 device CMYK k fill 로만 칠한다(렌더 시 preset 색으로 재지정) → verify PASS 유지.
  · 좌표는 베이스라인(글리프 잉크 하단) 원점으로 정규화해 저장 → 렌더 시 자유 배치.

공개 함수:
  extract_number_glyphs(src, artbox, order)  → glyphset dict (추출)
  save_glyphset_json(glyphset, path)          → JSON 저장
  load_glyphset_json(path)                     → JSON 로드
  render_glyph_number_ops(glyphset, text, cap_h_pt, center_x, center_y, color)
                                               → (ops_str, warnings)  잉크중심 정렬 렌더
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import pikepdf
from pikepdf import parse_content_stream

from .pdfutil import fmt


# ── 행렬(CTM) 유틸 — flatten.py / job.py 의 검증된 식과 동일(좌표 일관성 보장) ──
def _mat_mul(m1, m2):
    """PDF 행렬 곱: cm 은 현재 CTM 왼쪽에 곱해진다(new = m1 × m2)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _apply(m, x, y):
    """점 (x,y) 에 행렬 m 을 적용해 변환된 (x',y') 반환."""
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _to_nums(operands):
    """피연산자들을 float 리스트로. 숫자가 아니면 None(색공간 이름 등)."""
    out = []
    for o in operands:
        try:
            out.append(float(o))
        except Exception:
            return None
    return out


def _normalize_cmyk(color_cmyk) -> Tuple[float, float, float, float]:
    """CMYK 값을 0~1 범위로 정규화한다(text.py 와 동일 규칙 — 0~100 입력도 허용)."""
    vals = list(color_cmyk) + [0, 0, 0, 0]
    c, m, y, k = (float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]))
    if max(c, m, y, k) > 1.0:               # 0~100 스케일로 들어온 경우
        c, m, y, k = c / 100.0, m / 100.0, y / 100.0, k / 100.0
    clamp = lambda v: max(0.0, min(1.0, v))
    return clamp(c), clamp(m), clamp(y), clamp(k)


# ════════════════════════════════════════════════════════════════════════════
# 1) 추출 — .ai ArtBox 안 단색 fill 경로 10개를 글리프셋으로 떼어낸다.
# ════════════════════════════════════════════════════════════════════════════


def _font_advance_ratio(font_path: str):
    """폰트(예: HY헤드라인M)에서 '글리프 advance ÷ 대표 잉크높이' 비율을 구한다.

    왜 필요한가(자간 문제 원인):
      · 디자이너 글리프셋은 '잉크 폭(width)'만 있고, 폰트가 본래 두던 '글자 사이 여백'
        (advance, =글자칸 폭)이 없다. 그래서 width 만큼만 전진하면 글자가 다닥다닥 붙는다.
      · 폰트는 글자칸(advance)에 좌우 여백을 포함해 둔다. HY헤드라인M 은 모든 숫자의
        advance 가 597 로 균일(monospace)하고, 대표 숫자(0/8/9) 잉크높이가 903 이다.
      · 그래서 비율 = advance(597) ÷ 잉크높이(903) ≈ 0.6611 을 구해 두고,
        각 글리프의 cap_height 에 곱하면 → 그 글리프가 가져야 할 advance(pt) 가 나온다.
        (예: cap_height 538.583 × 0.6611 ≈ 356pt 균일 advance → 폰트와 같은 자간 복원.)

    반환: (ratio, rep_advance, rep_ink_h) — 못 구하면 None.
    """
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    if not font_path or not os.path.exists(font_path):
        return None
    try:
        f = TTFont(font_path)
        cmap = f.getBestCmap()
        hmtx = f["hmtx"]
        glyf = f["glyf"]
        # 대표 숫자: 잉크높이가 큰 '0' 을 기준(없으면 8→9 순으로 폴백).
        best = None
        for ch in ("0", "8", "9", "3", "6"):
            gname = cmap.get(ord(ch))
            if gname is None:
                continue
            aw = hmtx[gname][0]                  # advance width(폰트 단위)
            g = glyf[gname]
            if getattr(g, "numberOfContours", 0) <= 0:
                continue
            ys = [p[1] for p in g.getCoordinates(glyf)[0]]
            ink_h = max(ys) - min(ys)            # 글리프 잉크 높이(폰트 단위)
            if ink_h <= 0 or aw <= 0:
                continue
            best = (aw / float(ink_h), float(aw), float(ink_h))
            break
        return best
    except Exception:
        return None


def _font_glyph_lsbs(font_path: str):
    """폰트에서 '글자별 lsb(left side bearing, 폰트 단위)'를 dict 로 읽어 온다.

    왜 필요한가(배번 "1" 치우침 원인):
      · advance(글자칸 폭)는 HY헤드라인M 숫자가 모두 597 로 균일하지만, lsb(글자칸 왼쪽
        끝에서 잉크 시작까지의 여백)는 글자마다 다르다. 예: '1'=108, '0'=56(폰트단위).
      · 우리 글리프셋은 잉크 좌하단을 (0,0)으로 정규화해 lsb 정보를 잃었다. 그래서 모든
        글자가 칸 왼쪽 끝(lsb=0)에 붙어 그려진다. 특히 '1'(원래 lsb 큼)은 본래 칸 안쪽
        오른쪽에 좁게 그려져야 하는데 왼쪽에 치우쳐 보이고 다음 글자와 너무 붙는다.
      · 그래서 글자별 lsb(폰트단위)를 읽어, 렌더 시 advance 와 같은 글리프 pt 단위로
        환산해(lsb_pt = lsb_units × advance_pt / 597) 잉크를 칸 안 제 위치로 밀어 준다.

    반환: {"1": 108.0, "2": 51.0, ...} (폰트단위). 못 구하면 None.
    """
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    if not font_path or not os.path.exists(font_path):
        return None
    try:
        f = TTFont(font_path)
        cmap = f.getBestCmap()
        hmtx = f["hmtx"]
        out: Dict[str, float] = {}
        for ch in "1234567890":
            gname = cmap.get(ord(ch))
            if gname is None:
                continue
            aw, lsb = hmtx[gname]          # (advance width, left side bearing) 폰트 단위
            out[ch] = float(lsb)
        return out if out else None
    except Exception:
        return None


def extract_number_glyphs(
    src: str,
    artbox: List[float] = [585, 4673, 3923, 5211],
    order: str = "1234567890",
    page_index: int = 0,
    font: Optional[str] = None,
) -> dict:
    """소스 .ai/.pdf 의 ArtBox 안 fill 경로들을 추출해 '번호 글리프셋' dict 로 만든다.

    동작(좌표 추적 — job._extract_red_strokes 와 같은 방식):
      · q/Q/cm 으로 CTM 을 추적해 모든 점을 '디자인 절대좌표'로 환산(평탄화).
      · fill 페인트 연산자(f/F/f*/b/B 등)로 끝나는 경로 중, 경로 중심점이 artbox 안에
        드는 것만 '숫자 글리프 후보'로 캡처한다(다른 도형 배제).
      · 캡처한 경로를 x 오름차순 정렬 → order 의 문자와 1:1 매핑.
      · 각 글리프를 '베이스라인(잉크 하단) 원점'으로 평행이동해 정규화하고,
        subpath(m/l/c/re/h/v/y 모두 보존) 목록 + width + cap_height 를 저장한다.

    인자:
      src      : 소스 파일 경로(.ai/.pdf).
      artbox   : [x0,y0,x1,y1] 추출 영역(디자인 절대좌표). 그 안 fill 만 캡처.
      order    : 캡처를 x순으로 정렬했을 때 대응하는 문자열(왼→오). 기본 "1234567890".
      page_index: 페이지 인덱스(기본 0).
      font     : (선택) 폰트 경로(.ttf). 주면 글리프마다 advance(글자칸 폭) 를
                 'cap_height × (폰트 advance÷잉크높이 비율)' 로 계산해 저장한다.
                 → 렌더 시 advance 만큼 전진해 폰트와 같은 자간을 복원(자간 문제 해결).
                 못 찾거나 비율 계산 실패 시 advance 를 넣지 않음(렌더가 width 폴백).

    반환(dict):
      {
        "units": "pt",
        "source": <파일명>,
        "artbox": [...],
        "cap_height": <대표 cap_height pt>,   # 글리프 잉크 높이 중앙값
        "glyphs": {
           "1": {"width": <pt>, "cap_height": <pt>, "subpaths": [[seg,...], ...]},
           ...
        }
      }
      subpaths 의 seg 형식: 베이스라인 원점 기준(좌하단 0,0) 상대좌표.
        ("m", x, y) / ("l", x, y) / ("c", c1x,c1y,c2x,c2y,ex,ey) /
        ("v", c2x,c2y,ex,ey) / ("y", c1x,c1y,ex,ey) / ("h",)
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"글리프 소스 파일을 찾지 못했습니다: {src}")

    ax0, ay0, ax1, ay1 = (float(artbox[0]), float(artbox[1]),
                          float(artbox[2]), float(artbox[3]))

    pdf = pikepdf.open(src)
    try:
        page = pdf.pages[page_index]

        ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)   # 현재 변환행렬(디자인 절대좌표로의 누적)
        ctm_stack: List[tuple] = []
        # 현재 경로의 세그먼트들 — 점은 이미 '디자인 절대좌표'로 환산해 둔다.
        segs: List[tuple] = []     # [(op, x,y,...), ...]  (h 는 ("h",))

        captured: List[dict] = []  # [{"segs": [...], "bbox": (x0,y0,x1,y1)}]

        def _emit(op_char, *pts):
            """원본 점들을 CTM 으로 디자인 절대좌표로 환산해 세그먼트에 누적."""
            mapped = []
            for (px, py) in pts:
                mapped.append(_apply(ctm, px, py))
            # 세그먼트를 (op, x0,y0,[x1,y1,...]) 평탄 튜플로 저장.
            flat: List = [op_char]
            for (x, y) in mapped:
                flat.append(x); flat.append(y)
            segs.append(tuple(flat))

        def _bbox_of(seglist):
            """세그먼트 목록의 잉크 경계(점 기준)를 구한다(없으면 None)."""
            xs, ys = [], []
            for s in seglist:
                op = s[0]
                if op == "h":
                    continue
                # s = (op, x0,y0, x1,y1, ...) — 좌표쌍을 모두 모은다.
                coords = s[1:]
                for i in range(0, len(coords), 2):
                    xs.append(coords[i]); ys.append(coords[i + 1])
            if not xs:
                return None
            return (min(xs), min(ys), max(xs), max(ys))

        def _flush_fill():
            """현재 경로가 fill 로 끝났고 artbox 안이면 글리프 후보로 캡처."""
            if not segs:
                return
            bb = _bbox_of(segs)
            if bb is None:
                return
            cx = (bb[0] + bb[2]) / 2.0
            cy = (bb[1] + bb[3]) / 2.0
            if not (ax0 <= cx <= ax1 and ay0 <= cy <= ay1):
                return
            captured.append({"segs": list(segs), "bbox": bb})

        for operands, op in parse_content_stream(page):
            o = str(op)
            n = _to_nums(operands)
            if o == "q":
                ctm_stack.append(ctm)
            elif o == "Q":
                ctm = ctm_stack.pop() if ctm_stack else ctm
            elif o == "cm" and n and len(n) >= 6:
                ctm = _mat_mul(tuple(n[:6]), ctm)
            # ── 경로 구성 연산자: 점을 CTM 환산해 누적(m/l/c/v/y/re/h 모두 보존) ──
            elif o == "m" and n and len(n) >= 2:
                _emit("m", (n[0], n[1]))
            elif o == "l" and n and len(n) >= 2:
                _emit("l", (n[0], n[1]))
            elif o == "c" and n and len(n) >= 6:
                _emit("c", (n[0], n[1]), (n[2], n[3]), (n[4], n[5]))
            elif o == "v" and n and len(n) >= 4:
                _emit("v", (n[0], n[1]), (n[2], n[3]))
            elif o == "y" and n and len(n) >= 4:
                _emit("y", (n[0], n[1]), (n[2], n[3]))
            elif o == "re" and n and len(n) >= 4:
                x, y, w, h = n[:4]
                # re(사각형) → m/l/h 로 풀어서 누적(보존 + 닫힌 subpath 1개).
                _emit("m", (x, y))
                _emit("l", (x + w, y))
                _emit("l", (x + w, y + h))
                _emit("l", (x, y + h))
                segs.append(("h",))
            elif o == "h":
                segs.append(("h",))
            # ── 페인트 연산자: fill 이면 캡처, 어느 쪽이든 현재 경로 종료 ──
            elif o in ("f", "F", "f*", "b", "b*", "B", "B*"):
                _flush_fill()
                segs = []
            elif o in ("S", "s", "n", "W", "W*"):
                # stroke/clip/no-op 으로 끝나는 경로는 글리프 아님 → 버린다.
                segs = []
    finally:
        pdf.close()

    # ── 캡처 검증: order 글자 수와 추출 글리프 수가 맞아야 안전하게 매핑 가능. ──
    n_cap = len(captured)
    if n_cap != len(order):
        raise ValueError(
            f"ArtBox 안 fill 글리프 {n_cap}개가 order '{order}'({len(order)}자)와 개수가 다릅니다. "
            f"artbox 좌표/소스를 확인하세요(추출 bbox: "
            f"{[tuple(round(v,1) for v in c['bbox']) for c in captured]}).")

    # ── x 오름차순 정렬 → order 문자와 1:1 매핑 ──
    captured.sort(key=lambda c: c["bbox"][0])

    # ── (자간 복원) 폰트 advance 비율 구하기 — 주어졌을 때만. ──
    #    ratio = 폰트 advance ÷ 대표 잉크높이 ≈ 0.6611(HY헤드라인M).
    ratio_info = _font_advance_ratio(font) if font else None
    adv_ratio = ratio_info[0] if ratio_info else None
    rep_advance = ratio_info[1] if ratio_info else None   # 폰트 대표 advance(597)

    # ── (배번 "1" 보정) 글자별 lsb(폰트단위) — 폰트 주어졌을 때만. ──
    #    lsb_pt = lsb_units × (그 글자의 advance_pt / rep_advance)
    #           로 advance 와 같은 글리프 pt 단위로 환산한다.
    glyph_lsbs = _font_glyph_lsbs(font) if font else None

    glyphs: Dict[str, dict] = {}
    cap_heights: List[float] = []
    for ch, cap in zip(order, captured):
        bb = cap["bbox"]
        x0, y0, x1, y1 = bb
        width = x1 - x0
        cap_h = y1 - y0
        cap_heights.append(cap_h)
        # 베이스라인 원점 정규화: 잉크 좌하단(x0,y0)을 (0,0)으로 평행이동.
        #   → 렌더 시 글리프를 자유 위치에 놓을 수 있다(원점이 항상 잉크 좌하단).
        norm_subs = _normalize_segs(cap["segs"], x0, y0)
        entry = {
            "width": round(width, 4),
            "cap_height": round(cap_h, 4),
            "subpaths": norm_subs,
        }
        # advance(글자칸 폭) = 이 글리프의 cap_height × 비율.
        #   width 보다 넉넉해 좌우 여백이 생김 → 폰트와 같은 자간(붙음 해결).
        #   비율이 없으면(폰트 미지정/실패) 키를 넣지 않음 → 렌더가 width 로 폴백.
        if adv_ratio is not None and cap_h > 0:
            entry["advance"] = round(cap_h * adv_ratio, 4)
        # lsb(글자칸 왼쪽 여백) = lsb_units × (이 글자 advance_pt / rep_advance).
        #   → 렌더 시 잉크를 +lsb*s 만큼 우측으로 밀어 칸 안 제 위치에 둔다(배번 "1" 보정).
        #   비율/lsb 없으면(폰트 미지정·실패) 키를 넣지 않음 → 렌더가 0 폴백.
        if (glyph_lsbs is not None and adv_ratio is not None and rep_advance
                and cap_h > 0 and ch in glyph_lsbs):
            adv_pt = cap_h * adv_ratio
            entry["lsb"] = round(glyph_lsbs[ch] * (adv_pt / rep_advance), 4)
        glyphs[ch] = entry

    cap_heights.sort()
    rep_cap = cap_heights[len(cap_heights) // 2] if cap_heights else 0.0  # 중앙값

    result = {
        "units": "pt",
        "source": os.path.basename(src),
        "artbox": [ax0, ay0, ax1, ay1],
        "order": order,
        "cap_height": round(rep_cap, 4),
        "glyphs": glyphs,
    }
    # (자간 복원) 폰트 advance 비율을 메타로 남김 — 재현/검수용.
    if ratio_info is not None:
        result["advance_font"] = os.path.basename(font)
        result["advance_ratio"] = round(ratio_info[0], 6)
    return result


def _normalize_segs(segs, ox: float, oy: float) -> List[list]:
    """세그먼트 목록의 모든 좌표를 (ox,oy) 만큼 빼서 베이스라인 원점으로 옮긴다.

    subpath(연속된 m… 한 덩어리)별로 잘라 리스트의 리스트로 반환한다.
    seg 출력 형식(JSON 친화적인 list):
      ["m", x, y] / ["l", x, y] / ["c", c1x,c1y,c2x,c2y,ex,ey] /
      ["v", c2x,c2y,ex,ey] / ["y", c1x,c1y,ex,ey] / ["h"]
    """
    subpaths: List[list] = []
    cur: List[list] = []
    for s in segs:
        op = s[0]
        if op == "h":
            cur.append(["h"])
            continue
        if op == "m" and cur:
            # 새 subpath 시작 — 직전 subpath 를 닫아 저장.
            subpaths.append(cur)
            cur = []
        # 좌표를 원점 보정(x 는 -ox, y 는 -oy).
        coords = s[1:]
        shifted: List = [op]
        for i in range(0, len(coords), 2):
            shifted.append(round(coords[i] - ox, 4))
            shifted.append(round(coords[i + 1] - oy, 4))
        cur.append(shifted)
    if cur:
        subpaths.append(cur)
    return subpaths


# ════════════════════════════════════════════════════════════════════════════
# 2) 저장/로드 — 글리프셋을 JSON 으로 직렬화(폴더+JSON 원칙).
# ════════════════════════════════════════════════════════════════════════════


def save_glyphset_json(glyphset: dict, path: str) -> str:
    """글리프셋 dict 를 JSON 으로 저장하고 경로를 돌려준다(폴더 자동 생성)."""
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(glyphset, f, ensure_ascii=False, indent=2)
    return path


def load_glyphset_json(path: str) -> dict:
    """JSON 글리프셋을 읽어 dict 로 돌려준다(없으면 친절 에러)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"글리프셋 JSON 을 찾지 못했습니다: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════════════════════
# 3) 렌더 — 글리프셋으로 번호를 그린다(이슈2 잉크중심 정렬 적용).
# ════════════════════════════════════════════════════════════════════════════


def _seg_to_ops(seg, s: float, dx: float, dy: float) -> str:
    """정규화 세그먼트 1개를 PDF 연산자 문자열로 환산한다.

    좌표 변환: 시트좌표 = 글리프좌표*s + (dx,dy).
    s  : 글리프단위(pt) → 목표 pt 배율(cap_h_pt / glyph_cap_height).
    dx,dy : 이 글리프의 베이스라인 원점이 놓일 위치(시트 절대좌표 pt).
    """
    op = seg[0]
    if op == "h":
        return "h"
    coords = seg[1:]
    pts = []
    for i in range(0, len(coords), 2):
        x = coords[i] * s + dx
        y = coords[i + 1] * s + dy
        pts.append((x, y))
    body = " ".join(f"{fmt(x)} {fmt(y)}" for (x, y) in pts)
    return f"{body} {op}"


def _glyph_ink_bounds(glyph: dict):
    """정규화 글리프의 잉크 경계(xMin,yMin,xMax,yMax)를 모든 점에서 계산한다.

    글리프는 베이스라인 원점 정규화돼 있어 보통 (0,0,width,cap_height) 근처지만,
    곡선 제어점이 약간 음수가 될 수 있으므로 실제 점들로 정확히 잰다.
    """
    xs, ys = [], []
    for sub in glyph["subpaths"]:
        for seg in sub:
            if seg[0] == "h":
                continue
            coords = seg[1:]
            for i in range(0, len(coords), 2):
                xs.append(coords[i]); ys.append(coords[i + 1])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def render_glyph_number_ops(
    glyphset: dict,
    text,
    cap_h_pt: float,
    center_x: float,
    center_y: float,
    color,
):
    """글리프셋으로 번호('7','20' 등)를 cap_h_pt 높이로 (center_x,center_y) 잉크중심 배치.

    이슈2(잉크 기준 중앙정렬)와 동일한 규약:
      · 대표 글리프(잉크 높이 최대)의 cap_height 로 scale s = cap_h_pt / cap_height.
      · 자릿들을 width×s 로 좌→우 '임시배치'한 뒤, 배치된 전체 잉크 bbox 의 한가운데를
        (center_x, center_y) 에 평행이동한다(보이는 잉크 중심 정렬).

    반환: (ops_str, warnings) — text.place_number 와 동일 규약(ascii ops, k fill, q…Q).
    """
    warnings: List[str] = []

    # ── 빈 텍스트: 그릴 것 없음(정상). ──
    if text is None or str(text).strip() == "":
        return "", warnings
    text = str(text).strip()

    if cap_h_pt <= 0:
        warnings.append(f"🟡 번호 '{text}' 의 높이값이 잘못됐습니다(cap_height {cap_h_pt}). 건너뜁니다.")
        return "", warnings

    glyphs = glyphset.get("glyphs", {})

    # ── 글리프셋에 없는 문자 검사(번호 깨짐 방지 — 통째 미출력). ──
    missing = [ch for ch in text if ch not in glyphs]
    if missing:
        warnings.append(
            f"🟡 번호 '{text}' 중 '{''.join(missing)}' 글리프가 글리프셋에 없어 전체를 그리지 않습니다(입력값 확인).")
        return "", warnings

    entries = [glyphs[ch] for ch in text]
    if not entries:
        return "", warnings

    # ── 대표 글리프 cap_height 로 scale 결정(가장 키 큰 글리프 기준 — 한 줄 동일 배율). ──
    rep_cap = max(g.get("cap_height", 0) for g in entries)
    if rep_cap <= 0:
        warnings.append(f"🟡 번호 '{text}' 의 글리프 높이를 계산하지 못해 건너뜁니다.")
        return "", warnings
    s = cap_h_pt / rep_cap

    # ── 1차 임시배치: 자릿들을 width×s 로 좌→우 이어붙인다(가로 시작점 0 기준 상대). ──
    #    seg = (글리프, 이 글자의 가로 시작점 dx0)  — 아직 center 보정 전 상대좌표.
    placed: List[Tuple[dict, float]] = []
    pen_x = 0.0
    for g in entries:
        placed.append((g, pen_x))
        # 다음 글자 위치로 전진: advance(글자칸 폭, 좌우 여백 포함)가 있으면 그걸 쓴다.
        #   → 폰트와 같은 자간(글자 안 붙음). 구버전 JSON(advance 없음)은 width 로 폴백.
        adv = g.get("advance")
        if adv is None or adv <= 0:
            adv = g.get("width", 0)
        pen_x += adv * s

    # ── 배치된 전체 글리프의 '실제 잉크 bbox'(배치 좌표계) 측정 ──
    #    글리프는 베이스라인 원점이라 y 는 baseline=0 가정으로 잰다(아래서 shift_y 로 올림).
    ink_min_x = ink_min_y = float("inf")
    ink_max_x = ink_max_y = float("-inf")
    for g, dx0 in placed:
        b = _glyph_ink_bounds(g)
        if b is None:
            continue
        # lsb(글자칸 왼쪽 여백)만큼 잉크를 우측으로 민다(배번 "1" 보정).
        #   실제 렌더(gx)와 동일한 식이라 중앙정렬 계산이 어긋나지 않는다.
        #   구버전 글리프셋(lsb 없음)은 0 폴백 → 기존 동작 그대로.
        lsb = g.get("lsb", 0.0) * s
        ink_min_x = min(ink_min_x, b[0] * s + dx0 + lsb)
        ink_max_x = max(ink_max_x, b[2] * s + dx0 + lsb)
        ink_min_y = min(ink_min_y, b[1] * s)
        ink_max_y = max(ink_max_y, b[3] * s)

    if ink_min_x == float("inf"):
        warnings.append(f"🟡 번호 '{text}' 에 그릴 잉크가 없어 건너뜁니다.")
        return "", warnings

    # ── 잉크 중심을 center_x / center_y 에 맞추는 평행이동량 계산(이슈2). ──
    shift_x = center_x - (ink_min_x + ink_max_x) / 2.0
    baseline_y = center_y - (ink_min_y + ink_max_y) / 2.0

    # ── 자릿별 경로 누적(상대 dx0 + shift_x = 최종 시트 x, baseline_y = 최종 시트 y). ──
    blocks: List[str] = []
    for g, dx0 in placed:
        # gx = 임시배치 시작점 + lsb(칸 왼쪽 여백) + 전체 중앙정렬 보정.
        #   lsb 가 잉크 bbox 측정에도 동일 반영돼 중앙정렬은 그대로 유지된다.
        gx = dx0 + g.get("lsb", 0.0) * s + shift_x
        lines: List[str] = []
        for sub in g["subpaths"]:
            for seg in sub:
                lines.append(_seg_to_ops(seg, s, gx, baseline_y))
        if lines:
            blocks.append("\n".join(lines))
    if not blocks:
        return "", warnings

    # ── 색(CMYK k fill) + q…Q 래핑(기존 규약과 동일). 'f'(non-zero) 라 구멍 자동 처리. ──
    c, m, y, k = _normalize_cmyk(color)
    color_op = f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k"
    body = "\n".join(blocks)
    ops_str = f"q\n{color_op}\n{body}\nf\nQ"
    return ops_str, warnings
