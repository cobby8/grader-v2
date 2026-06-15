# -*- coding: utf-8 -*-
"""selftest용 합성 픽스처 — 외부 파일 없이 PoC를 재현한다.

PoC(poc_cmyk_compose.py)의 기지 색값 샘플 디자인과 조각/사이즈 기하를 그대로 옮겨,
`python -m engine selftest`가 어떤 환경에서도 자기완결적으로 돌아가게 한다.
(DESIGN.md Phase 0 완료 기준: engine 단독 실행으로 PoC 재현.)
"""
from __future__ import annotations

from typing import List

import pikepdf

from .pdfutil import fmt

DESIGN_W, DESIGN_H = 400.0, 300.0  # pt

# 기지 색값 (C,M,Y,K) — 출력에서 한 톨도 변하면 안 됨 (PoC와 동일)
KNOWN_FILLS = [
    (1.0, 0.0, 0.0, 0.0),    # C100
    (0.0, 1.0, 0.0, 0.0),    # M100
    (0.0, 0.0, 1.0, 0.0),    # Y100
    (0.0, 0.0, 0.0, 1.0),    # K100
    (0.5, 0.2, 0.0, 0.1),    # 혼합 1
    (0.2, 0.8, 0.9, 0.05),   # 혼합 2
]
KNOWN_STROKE = (0.1, 0.9, 0.3, 0.0)

# PoC 조각 기하 (디자인 좌표계) + 사이즈 배율
BASE_PIECES = [
    [(0, 0), (180, 0), (180, 140), (0, 140)],                      # 사각형 A
    [(200, 0), (400, 0), (400, 140), (200, 140)],                  # 사각형 B
    [(0, 160), (180, 160), (180, 300), (0, 300)],                  # 사각형 C
    [(200, 160), (300, 300), (400, 240), (380, 170), (290, 160)],  # 오각형
]
SIZE_SCALES = [("XS", 0.5), ("S", 0.7), ("M", 0.85), ("L", 1.0), ("XL", 1.15), ("2XL", 1.3)]


def make_known_cmyk_design(path: str) -> str:
    """device CMYK(k/K)만으로 그린 기지 색값 디자인 PDF 생성 — ICC/RGB·투명도 없음."""
    ops = []
    for i, (c, m, y, k) in enumerate(KNOWN_FILLS):
        col, row = i % 3, i // 3
        x, yy = 20 + col * 125, 170 - row * 130
        ops.append(f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k")
        ops.append(f"{x} {yy} 105 100 re f")
    c, m, y, k = KNOWN_STROKE
    ops.append(f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} K")
    ops.append("3 w 30 30 m 130 90 270 -30 370 30 c S")
    content = "\n".join(ops).encode("ascii")

    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(DESIGN_W, DESIGN_H))
    page.obj["/Contents"] = pdf.make_stream(content)
    pdf.save(path)
    return path
