# -*- coding: utf-8 -*-
"""검수용 PNG 미리보기 — PyMuPDF로 합성 PDF의 각 페이지를 래스터 렌더.

주의: 미리보기는 '눈으로 확인'용일 뿐, 공장 출력 적합성 판정이 아니다.
DESIGN.md 리스크 표: 미리보기 PNG 통과 ≠ RIP 통과 → Phase 1 완료엔 공장 시험인쇄 필수.
"""
from __future__ import annotations

import os
from typing import List

import fitz  # PyMuPDF


def render_previews(pdf_path: str, out_dir: str, dpi: int = 120,
                    prefix: str = "preview") -> List[str]:
    """PDF의 각 페이지를 PNG로 저장하고 경로 목록을 돌려준다."""
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            p = os.path.join(out_dir, f"{prefix}_p{i + 1:02d}.png")
            pix.save(p)
            paths.append(p)
        return paths
    finally:
        doc.close()


def render_page(pdf_path: str, out_png: str, page: int = 0, dpi: int = 120) -> str:
    doc = fitz.open(pdf_path)
    try:
        pix = doc[page].get_pixmap(dpi=dpi)
        pix.save(out_png)
        return out_png
    finally:
        doc.close()
