# -*- coding: utf-8 -*-
"""좌표정합 시험 렌더 — 방식A(앵커 정합) vs 방식B(전체 정렬 후 클리핑) 비교.

이 스크립트는 "디자인 1장을 패턴 조각에 어떻게 얹을 것인가"를 두 가지 전략으로
실제 합성해 보고, 눈으로 비교하기 위한 일회성 도구다. engine은 import만 하고
절대 수정하지 않는다.

────────────────────────────────────────────────────────────────────────────
실행법 (Windows PowerShell / cmd):
    cd "C:/0. Programing/grader-v2"
    python grading_compare/compare_mapping.py

생성물:
    grading_compare/outA.pdf      방식A 결과 PDF
    grading_compare/outB.pdf      방식B 결과 PDF
    grading_compare/previewA/     방식A 미리보기 PNG
    grading_compare/previewB/     방식B 미리보기 PNG
────────────────────────────────────────────────────────────────────────────

두 방식의 핵심 차이:
  · 방식A(앵커 정합): 조각마다 "디자인의 해당 영역"을 따로 떼어,
      디자인 영역의 좌하단 → 패턴 조각 윤곽의 좌하단에 맞추고,
      (조각크기 / 디자인영역크기) 비율로 스케일한다. 조각별 transform이 모두 다르다.
      → 디자인의 각 부위가 패턴 조각 크기에 "맞춰" 들어간다.

  · 방식B(전체 정렬 후 클리핑): 디자인 페이지 전체(4478×5669)를
      패턴 시트 전체 bbox 에 1회만 정렬하는 공통 transform 1개를 만들고,
      모든 조각이 그 동일 transform 을 공유한다. 조각마다 다른 것은 "클리핑 윤곽"뿐.
      → 디자인 한 장을 통째로 깔고, 패턴 모양대로 오려낸다.
"""
from __future__ import annotations

import os
import sys

# ── 콘솔 인코딩 안전장치 (한글 Windows cp949 콘솔에서 비-cp949 문자 print 시 크래시 방지) ──
def _force_utf8_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # 미지원 환경이면 조용히 무시
        except Exception:
            pass


_force_utf8_console()

# ── 이 스크립트는 grading_compare/ 하위에 있으므로, 저장소 루트를 import 경로에 추가한다.
#    (그래야 루트의 engine 패키지를 찾는다.) ──
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── engine은 import 만. 수정 금지. ──
from engine.compose import Piece, SizeLayout, compose
from engine.pattern import parse_svg
from engine.pdfutil import scale_translate, bbox
from engine.preview import render_previews
from engine.verify import verify_output, format_report

# ── 경로 상수 ────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = r"C:/0. Programing/grader/illustrator-scripts/test/design_XL.ai"
PATTERN = r"C:/0. Programing/grader/illustrator-scripts/test/pattern_XS.svg"

OUT_A = os.path.join(HERE, "outA.pdf")
OUT_B = os.path.join(HERE, "outB.pdf")
PREVIEW_A = os.path.join(HERE, "previewA")
PREVIEW_B = os.path.join(HERE, "previewB")

# ── 확정 측정값 (PM 제공, 재측정 불필요) ──────────────────────────────────────
# 디자인 design_XL.ai 의 각 부위가 차지하는 영역 (PDF pt, 좌하단 원점).
#   (xmin, ymin, xmax, ymax)
DESIGN_AREAS = {
    "앞판": (468.0, 2877.0, 2098.0, 5287.0),
    "뒤판": (2310.0, 2877.0, 3997.0, 5287.0),
    "소매": (468.0, 5301.0, 2225.0, 5562.0),
}

# 디자인 페이지(MediaBox) 크기.
DESIGN_PAGE = (4478.74, 5669.29)

# 디자인 부위 → parse_svg 조각 인덱스 매칭 (PM 확정).
#   parse_svg 는 높이 내림차순 정렬이므로:
#     idx0 = 1542x2193 (뒤판), idx1 = 1542x2085 (앞판), idx2 = 1584x176 (소매)
#   parse_svg 는 flip_y 되어 디자인 PDF 좌표계와 동일 기준(좌하단 원점).
AREA_TO_PIECE_IDX = {
    "앞판": 1,
    "뒤판": 0,
    "소매": 2,
}


def load_pattern_pieces():
    """패턴 SVG 를 파싱해 부위명 → Polyline 으로 묶어 반환."""
    polys = parse_svg(PATTERN)  # 높이 내림차순 정렬된 조각 목록
    pieces = {}
    for area, idx in AREA_TO_PIECE_IDX.items():
        pieces[area] = polys[idx]
    return pieces


# ════════════════════════════════════════════════════════════════════════════
# 방식 A — 앵커 정합
# ════════════════════════════════════════════════════════════════════════════
def build_layout_A(pattern_pieces) -> SizeLayout:
    """조각마다 디자인 영역 좌하단 → 조각 윤곽 좌하단에 맞추고 개별 스케일.

    한 조각의 transform 은 "디자인 좌표 → 시트 좌표" 변환이다.
    디자인 영역 (dx0,dy0)~(dx1,dy1) 을 조각 윤곽 bbox (px0,py0)~(px1,py1) 에
    얹으려면:
        scale_x = 조각폭 / 영역폭,  scale_y = 조각높이 / 영역높이
    인데, engine 의 transform 헬퍼(scale_translate)는 등방(가로=세로) 스케일만
    지원한다. 디자인 부위 비율을 깨지 않으려면 한 배율을 써야 하므로,
    "조각 안에 디자인 영역이 다 들어오도록" 가로/세로 중 작은 배율(contain)을 쓴다.

    그 다음 디자인 영역 좌하단이 조각 좌하단으로 가도록 평행이동한다.
        시트X = px0 + (디자인X - dx0) * s
              = s*디자인X + (px0 - s*dx0)
        → scale_translate(s, ox=px0 - s*dx0, oy=py0 - s*dy0)
    """
    layout_pieces = []
    for area, (dx0, dy0, dx1, dy1) in DESIGN_AREAS.items():
        poly = pattern_pieces[area]
        px0, py0, px1, py1 = poly.bbox  # 조각 윤곽 bbox (시트 좌표)

        dw, dh = (dx1 - dx0), (dy1 - dy0)        # 디자인 영역 크기
        pw, ph = (px1 - px0), (py1 - py0)        # 조각 크기

        # 등방 스케일: 가로/세로 중 작은 쪽(contain) — 영역이 조각 밖으로 안 삐져나오게.
        s = min(pw / dw, ph / dh)

        # 디자인 영역 좌하단 → 조각 좌하단으로 옮기는 오프셋.
        ox = px0 - s * dx0
        oy = py0 - s * dy0

        transform = scale_translate(s, ox, oy)
        # 클립 윤곽은 조각 윤곽 그대로(이미 시트 좌표). 디자인이 이 모양으로 잘린다.
        layout_pieces.append(Piece(outline=poly.points, transform=transform, name=area))

    # 페이지 크기 = 모든 조각 윤곽을 감싸는 전체 bbox + 여백.
    all_pts = [pt for poly in pattern_pieces.values() for pt in poly.points]
    minx, miny, maxx, maxy = bbox(all_pts)
    page = (maxx + 50.0, maxy + 50.0)  # 좌하단 여백은 원점 유지(조각이 양수 좌표라 충분)
    return SizeLayout(name="A_anchor", page_size=page, pieces=layout_pieces)


# ════════════════════════════════════════════════════════════════════════════
# 방식 B — 전체 정렬 후 클리핑
# ════════════════════════════════════════════════════════════════════════════
def build_layout_B(pattern_pieces) -> SizeLayout:
    """디자인 페이지 전체를 패턴 시트 전체 bbox 에 1회 정렬. transform 1개를 공유.

    디자인 전체 (0,0)~(DW,DH) 를 패턴 시트 전체 bbox (sx0,sy0)~(sx1,sy1) 에 얹는다.
    등방 스케일이므로 contain 배율을 쓰고, 디자인 좌하단(0,0) → 시트 bbox 좌하단으로 이동.
        s = min(시트폭/DW, 시트높이/DH)
        ox = sx0 - s*0 = sx0,  oy = sy0
    모든 조각이 이 동일 transform 을 쓰고, 클립 윤곽만 조각별로 다르다.
    """
    DW, DH = DESIGN_PAGE

    all_pts = [pt for poly in pattern_pieces.values() for pt in poly.points]
    sx0, sy0, sx1, sy1 = bbox(all_pts)  # 패턴 시트 전체 bbox
    sw, sh = (sx1 - sx0), (sy1 - sy0)

    # 공통 transform: 디자인 전체 → 시트 전체 정렬 (등방 contain).
    s = min(sw / DW, sh / DH)
    ox = sx0
    oy = sy0
    common = scale_translate(s, ox, oy)

    layout_pieces = []
    for area, poly in pattern_pieces.items():
        # transform 은 모두 동일(common), 클립 윤곽만 조각별.
        layout_pieces.append(Piece(outline=poly.points, transform=common, name=area))

    page = (sx1 + 50.0, sy1 + 50.0)
    return SizeLayout(name="B_global", page_size=page, pieces=layout_pieces)


def run_one(tag: str, layout: SizeLayout, out_pdf: str, preview_dir: str):
    """레이아웃 1개를 합성 → 미리보기 → 검증까지 수행하고 로그를 찍는다."""
    print(f"\n===== 방식 {tag} 합성 시작 =====")
    placements = compose(DESIGN, [layout], out_pdf, design_page=0)
    print(f"[{tag}] compose 완료: 배치 {placements}개 → {out_pdf}")
    print(f"[{tag}] 출력 존재: {os.path.exists(out_pdf)} / 크기 {os.path.getsize(out_pdf)} bytes")

    pngs = render_previews(out_pdf, preview_dir, dpi=120, prefix=f"preview{tag}")
    print(f"[{tag}] 미리보기 PNG {len(pngs)}개 생성:")
    for p in pngs:
        print(f"    - {p}  (존재:{os.path.exists(p)})")

    print(f"[{tag}] ----- verify_output 리포트 -----")
    checks = verify_output(out_pdf, DESIGN, expected_placements=placements)
    print(format_report(checks))
    return placements, pngs


def main():
    print("좌표정합 시험 렌더 — 방식A(앵커) vs 방식B(전체정렬+클립)")
    print(f"디자인 : {DESIGN}  (존재:{os.path.exists(DESIGN)})")
    print(f"패턴   : {PATTERN}  (존재:{os.path.exists(PATTERN)})")

    pattern_pieces = load_pattern_pieces()
    print("\n[패턴 조각 매칭 확인]")
    for area, poly in pattern_pieces.items():
        b = poly.bbox
        print(f"  {area}: w={poly.width:.0f} h={poly.height:.0f} "
              f"bbox=({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})")

    layout_A = build_layout_A(pattern_pieces)
    layout_B = build_layout_B(pattern_pieces)

    run_one("A", layout_A, OUT_A, PREVIEW_A)
    run_one("B", layout_B, OUT_B, PREVIEW_B)

    print("\n===== 비교 안내 =====")
    print("워터마크 투명도로 인해 verify_output '투명도 없음' 항목은 FAIL 이 예상됩니다.")
    print("  → 워터마크 탓이며, 운영 시 원본 평탄화가 필요합니다. 이번 좌표정합 비교의 관심사가 아닙니다.")
    print("  → 색공간 CMYK 계열 유지 / device CMYK 무손실 항목은 PASS 여야 정상(색 변환 금지).")
    print(f"방식A 미리보기 폴더: {PREVIEW_A}")
    print(f"방식B 미리보기 폴더: {PREVIEW_B}")


if __name__ == "__main__":
    main()
