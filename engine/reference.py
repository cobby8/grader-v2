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
