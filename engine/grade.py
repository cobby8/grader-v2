# -*- coding: utf-8 -*-
"""그레이딩 일반화 — preset.json 1장으로 전 사이즈를 자동 합성한다.

이 모듈은 grading_compare/compare_mapping.py 의 "방식 A(앵커 정합)" 로직을
preset.json 기반으로 일반화한 것이다. 시험 렌더에서 검증된 그 방식을, 이제는
하드코딩한 측정값이 아니라 패턴 폴더의 preset.json 에서 읽어 동작하게 한다.

────────────────────────────────────────────────────────────────────────────
큰 그림 (비유)
  · preset.json = "레시피 카드". 디자인의 어느 영역을 어느 패턴 조각에 얹을지 적혀 있다.
  · 디자인 PDF  = "재료(통짜 그림 1장)".
  · 이 모듈     = "요리사". 레시피대로 디자인을 조각마다 잘라 얹는 좌표(transform)를 계산한다.
  · engine.compose = "오븐". 실제로 무손실 CMYK PDF 를 굽는다(여기선 import 만, 절대 수정 안 함).
────────────────────────────────────────────────────────────────────────────

방식 A(앵커 정합)의 핵심:
  조각마다 "디자인의 해당 영역(design_region_pt)"을, 그 조각의 윤곽 bbox 좌하단에
  맞추고(anchor=bottom-left), 비율을 깨지 않도록 등방 contain 배율로 키워 얹는다.
  → 디자인의 각 부위가 패턴 조각 크기에 "맞춰" 들어간다.

공개 함수:
  load_preset(preset_path)                 preset.json 로드 + 기본 검증
  build_layouts(preset, design_pdf_path)   전 사이즈의 SizeLayout 목록 생성
  grade(preset_path, design_pdf_path, out)  위 둘을 묶어 compose 까지 실행 → 배치 수 반환
"""
from __future__ import annotations

import json
import os
from typing import List

# ── engine 공개 API 는 import 만 한다. 수정 금지. ──
from .compose import Piece, SizeLayout, compose
from .pattern import parse_svg
from .pdfutil import scale_translate

# preset.json 에 반드시 있어야 하는 최상위 키 (없으면 설계도 결함이므로 즉시 알린다).
_REQUIRED_TOP_KEYS = ("preset_name", "sizes", "pieces", "design_mapping")


def load_preset(preset_path: str) -> dict:
    """preset.json 을 읽어 dict 로 돌려준다. 필수 키가 없으면 친절한 에러를 낸다.

    검증을 하는 이유: preset.json 은 사람이 손으로 채우는 설계도라 오타/누락이 잦다.
    여기서 미리 걸러야 나중에 합성 도중 알 수 없는 에러로 죽는 일을 막는다.
    """
    if not os.path.exists(preset_path):
        raise FileNotFoundError(f"preset.json 없음: {preset_path}")

    with open(preset_path, "r", encoding="utf-8") as f:
        preset = json.load(f)

    # ── 최상위 필수 키 검증 ──
    missing = [k for k in _REQUIRED_TOP_KEYS if k not in preset]
    if missing:
        raise ValueError(f"preset.json 필수 키 누락: {missing} (파일: {preset_path})")

    # ── sizes / pieces 는 비어 있으면 안 된다 ──
    if not preset["sizes"]:
        raise ValueError("preset.json 의 sizes 가 비어 있습니다. 사이즈를 최소 1개 등록하세요.")
    if not preset["pieces"]:
        raise ValueError("preset.json 의 pieces 가 비어 있습니다. 조각을 최소 1개 정의하세요.")

    # ── 각 조각에 svg_index 와 design_region_pt 가 있는지 확인 ──
    for p in preset["pieces"]:
        for key in ("svg_index", "design_region_pt"):
            if key not in p:
                raise ValueError(f"조각 '{p.get('id', '?')}' 에 '{key}' 가 없습니다.")
        if len(p["design_region_pt"]) != 4:
            raise ValueError(
                f"조각 '{p.get('id', '?')}' 의 design_region_pt 는 [x0,y0,x1,y1] 4개여야 합니다.")

    # 폴더 위치를 기억해 둔다(상대경로 pattern_file 을 절대경로로 풀 때 사용).
    preset["_dir"] = os.path.dirname(os.path.abspath(preset_path))
    return preset


def _piece_transform(design_region, poly, shrink_x, shrink_y):
    """조각 1개의 transform(디자인 좌표 → 시트 좌표)을 방식 A 로 계산한다.

    design_region : (dx0, dy0, dx1, dy1)  디자인에서 이 부위가 차지하는 영역.
    poly          : 이 조각의 패턴 윤곽(Polyline). poly.bbox 가 시트 위 위치.
    shrink_x/y    : 수축 보정 계수(보통 1.0).

    원리(compare_mapping.build_layout_A 와 동일):
      · 등방 contain 배율 s = min(조각폭/영역폭, 조각높이/영역높이)
        - 등방(가로=세로 같은 배율)인 이유: engine 의 scale_translate 가 등방만 지원하고,
          디자인 부위 비율을 깨지 않으려면 한 배율을 써야 하기 때문.
        - contain(둘 중 작은 값)인 이유: 영역이 조각 밖으로 삐져나오지 않게 하려고.
      · 디자인 영역 좌하단(dx0,dy0) → 조각 윤곽 좌하단(px0,py0) 으로 평행이동.
            시트X = px0 + (디자인X - dx0)*s = s*디자인X + (px0 - s*dx0)
            → scale_translate(s, ox=px0 - s*dx0, oy=py0 - s*dy0)
    """
    dx0, dy0, dx1, dy1 = design_region
    px0, py0, px1, py1 = poly.bbox  # 조각 윤곽 bbox (시트 좌표)

    dw, dh = (dx1 - dx0), (dy1 - dy0)   # 디자인 영역 크기
    pw, ph = (px1 - px0), (py1 - py0)   # 조각 크기

    # 등방 contain 배율(둘 중 작은 쪽). shrink 보정도 함께 곱한다(수축 미리 반영).
    #   shrink_x/y 가 1.0 이면 보정 없음. 가로/세로가 다르면 더 작은 쪽을 곱해 비율 유지.
    s = min(pw / dw, ph / dh) * min(shrink_x, shrink_y)

    # 디자인 영역 좌하단 → 조각 좌하단으로 옮기는 오프셋.
    ox = px0 - s * dx0
    oy = py0 - s * dy0
    return scale_translate(s, ox, oy)


def build_layouts(preset: dict, design_pdf_path: str) -> List[SizeLayout]:
    """preset 의 모든 사이즈에 대해 방식 A 로 SizeLayout 목록을 만든다.

    design_pdf_path : (현재 미사용) 인터페이스 일관성을 위해 받는다. 방식 A 는 디자인
                      영역 좌표를 preset 에서 직접 읽으므로 PDF 페이지 크기는 불필요.
                      A-3 이후 디자인별 보정이 생기면 이 인자를 활용한다.
    """
    if not os.path.exists(design_pdf_path):
        raise FileNotFoundError(f"디자인 파일 없음: {design_pdf_path}")

    pieces_def = preset["pieces"]
    shrink = preset.get("shrink", {"x": 1.0, "y": 1.0})
    shrink_x = float(shrink.get("x", 1.0))
    shrink_y = float(shrink.get("y", 1.0))

    layouts: List[SizeLayout] = []
    for size in preset["sizes"]:
        # ── 이 사이즈의 패턴 SVG 를 파싱(높이 내림차순 정렬된 조각 목록) ──
        svg_path = os.path.join(preset["_dir"], size["pattern_file"])
        polys = parse_svg(svg_path)  # 높이 내림차순 정렬

        layout_pieces: List[Piece] = []
        for pdef in pieces_def:
            idx = pdef["svg_index"]
            if idx < 0 or idx >= len(polys):
                raise ValueError(
                    f"조각 '{pdef.get('id','?')}' svg_index={idx} 가 SVG 조각 수({len(polys)})를 벗어남"
                    f" (사이즈 {size['name']}, 파일 {size['pattern_file']})")
            poly = polys[idx]

            # 방식 A: 디자인 영역을 이 조각 bbox 에 앵커정렬+contain 스케일.
            transform = _piece_transform(pdef["design_region_pt"], poly, shrink_x, shrink_y)
            # 클립 윤곽은 조각 윤곽 그대로(시트 좌표). 디자인이 이 모양으로 잘린다.
            layout_pieces.append(
                Piece(outline=poly.points, transform=transform, name=pdef.get("name", pdef.get("id", ""))))

        # ── 페이지 크기 = 모든 조각 윤곽을 감싸는 전체 bbox + 여백 50pt ──
        all_x = [x for poly in (polys[p["svg_index"]] for p in pieces_def) for (x, _) in poly.points]
        all_y = [y for poly in (polys[p["svg_index"]] for p in pieces_def) for (_, y) in poly.points]
        page = (max(all_x) + 50.0, max(all_y) + 50.0)  # 좌하단은 원점 유지(조각이 양수 좌표라 충분)

        layouts.append(SizeLayout(name=size["name"], page_size=page, pieces=layout_pieces))

    return layouts


def grade(preset_path: str, design_pdf_path: str, out_path: str) -> int:
    """preset + 디자인 → 전 사이즈 합성 PDF 저장. 총 배치(조각) 수를 돌려준다.

    절차: load_preset → build_layouts → engine.compose(절대 수정 안 함, 그대로 호출).
    """
    preset = load_preset(preset_path)
    layouts = build_layouts(preset, design_pdf_path)
    # compose 는 디자인을 Form XObject 1개로 임베드 후 조각마다 참조+클립(무손실 CMYK).
    placements = compose(design_pdf_path, layouts, out_path, design_page=0)
    return placements


# ── 단독 실행 진입부 (CLI 없이도 빠르게 돌려볼 수 있게) ──────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("사용법: python -m engine.grade <preset.json> <design.(ai|pdf)> <out.pdf>")
        sys.exit(2)
    n = grade(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"합성 완료: 배치 {n}개 → {sys.argv[3]}")
