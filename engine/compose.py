# -*- coding: utf-8 -*-
"""합성 코어 — 디자인 PDF를 사이즈별 조각 레이아웃에 배치해 단일 임베드 CMYK PDF를 만든다.

PoC(poc_cmyk_compose.py)에서 증명된 가설을 재사용 가능한 형태로 일반화했다:
  · 디자인은 Form XObject로 '단 1회만' 임베드 → 모든 배치는 참조(Do)만 반복 (AC-2 경량).
  · device CMYK 콘텐츠가 Form 안에 그대로 들어가 색값 무손실 통과 (AC-1).
  · 조각별 임의 다각형 클리핑(W n) + CTM 스케일/배치(cm) (AC-3 합성).

데이터 모델
  Piece       조각 1개 = 시트 위 클립 윤곽(outline) + 디자인→시트 변환(transform)
  SizeLayout  사이즈 1개 = 페이지 크기 + 그 사이즈의 조각들

  → 한 사이즈가 PDF 1페이지가 된다. 전 사이즈를 한 번의 compose 호출로 다페이지 출력.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Sequence

import pikepdf

from .pdfutil import Matrix, Point, place_block, scale_translate


@dataclass
class Piece:
    """시트 위 조각 1개.

    outline   : 클립할 다각형 윤곽 (PDF 좌표, 시트 기준 절대 위치).
    transform : 디자인 좌표를 시트 좌표로 옮기는 cm 행렬 (a b c d e f).
                기본 헬퍼 scale_translate(scale, ox, oy)로 만든다.
    name      : 식별용 (예: '앞판', '뒤판').
    """
    outline: Sequence[Point]
    transform: Matrix
    name: str = ""


@dataclass
class SizeLayout:
    """사이즈 1개의 페이지 레이아웃."""
    name: str
    page_size: tuple  # (width_pt, height_pt)
    pieces: List[Piece] = field(default_factory=list)


def compose(design_pdf: str, layouts: Sequence[SizeLayout], out_path: str,
            design_page: int = 0, compress: bool = True) -> int:
    """디자인을 전 사이즈 레이아웃에 합성한 다페이지 CMYK PDF를 저장.

    Returns: 총 배치(조각) 수 — 검증/로그용.

    주의: 디자인 PDF는 device CMYK + 투명도 없음을 전제로 한다(투명도는 업로드 단계에서
    걸러야 함, DESIGN.md 7번 안전장치). 여기서는 색공간을 일절 건드리지 않는다.
    """
    if not os.path.exists(design_pdf):
        raise FileNotFoundError(f"디자인 PDF 없음: {design_pdf}")

    src = pikepdf.open(design_pdf)
    try:
        out = pikepdf.new()
        # ── 임베드는 여기 단 한 번뿐. 이후 모든 배치는 이 객체를 참조만 한다. ──
        xobj = out.copy_foreign(src.pages[design_page].as_form_xobject())

        placements = 0
        for layout in layouts:
            page = out.add_blank_page(page_size=layout.page_size)
            # 같은 Form 객체를 이 페이지 리소스에 등록(이름 부여). 객체는 공유된다.
            name = page.add_resource(xobj, pikepdf.Name("/XObject"))
            blocks = []
            for piece in layout.pieces:
                blocks.append(place_block(piece.outline, piece.transform, str(name)))
                placements += 1
            content = "\n".join(blocks).encode("ascii")
            page.obj["/Contents"] = out.make_stream(content)

        out.save(out_path, compress_streams=compress)  # 무손실 deflate만 → 무변형
        return placements
    finally:
        src.close()


# ────────────────────────────────────────────────────────────────────────────
# 간단 레이아웃 빌더 — 등방 스케일 + 격자 배치 (PoC와 동일한 단순 전략)
# 실제 그레이딩(사이즈별 패턴 윤곽 사용)은 pattern.py + 별도 그레이딩 로직으로 확장.
# ────────────────────────────────────────────────────────────────────────────
def grid_layout(name: str, base_polys: Sequence[Sequence[Point]],
                design_box: tuple, scale: float,
                cols: int = 2, margin: float = 20.0, gap: float = 10.0) -> SizeLayout:
    """기준 조각 윤곽(base_polys, 디자인 좌표계)을 scale배 + 격자로 배치한 한 사이즈 레이아웃.

    base_polys : 디자인 좌표계의 조각 윤곽들. 각 조각이 디자인의 어느 영역을 차지하는지 정의.
    design_box : (w, h) 디자인 원본 크기 pt.
    scale      : 이 사이즈의 배율 (예: XS=0.5, L=1.15).

    각 조각은 자신의 윤곽 영역만큼 디자인을 보여준다(클립). 디자인 전체를 scale배 후
    조각 위치에 배치하고, 그 조각의 윤곽으로 잘라낸다 — PoC clip_ops와 동일한 결과.
    """
    dw, dh = design_box
    pieces: List[Piece] = []
    for j, poly in enumerate(base_polys):
        col, row = j % cols, j // cols
        ox = margin + col * (dw * scale + gap)
        oy = margin + row * (dh * scale + gap)
        # 윤곽을 시트 좌표로(스케일+오프셋), 변환도 동일 스케일+오프셋 → 디자인이 정위치에 잘림
        outline = [(ox + x * scale, oy + y * scale) for (x, y) in poly]
        transform = scale_translate(scale, ox, oy)
        pieces.append(Piece(outline=outline, transform=transform, name=f"piece{j}"))

    n_rows = (len(base_polys) + cols - 1) // cols
    page_w = margin * 2 + cols * (dw * scale) + (cols - 1) * gap
    page_h = margin * 2 + n_rows * (dh * scale) + (n_rows - 1) * gap
    return SizeLayout(name=name, page_size=(page_w, page_h), pieces=pieces)
