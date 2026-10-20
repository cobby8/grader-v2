# -*- coding: utf-8 -*-
"""PDF 콘텐츠 스트림 저수준 헬퍼.

PoC(poc_cmyk_compose.py)에서 검증된 표기/연산자 생성 로직을 모았다.
PDF 좌표계는 y가 위로 증가(좌하단 원점)한다는 점에 주의.
"""
from __future__ import annotations

from typing import Iterable, Sequence, Tuple

Point = Tuple[float, float]
Matrix = Tuple[float, float, float, float, float, float]  # a b c d e f (cm 연산자)


def fmt(v: float) -> str:
    """PDF 숫자 표기 — 불필요한 0/소수점 제거. PoC와 동일."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def clip_path_ops(polygon: Sequence[Point]) -> str:
    """다각형 윤곽을 클리핑 경로로 변환 (`W n`).

    polygon은 PDF 좌표(점 목록). 임의 다각형(곡선 평탄화 포함) 클리핑이 가능하다는 점이
    과거 '사각형만 클리핑' 한계를 푼 핵심(PoC 검증 항목 1).
    """
    parts = []
    for i, (x, y) in enumerate(polygon):
        parts.append(f"{fmt(x)} {fmt(y)} {'m' if i == 0 else 'l'}")
    parts.append("h W n")  # h=경로 닫기, W=클립 영역 설정, n=경로 그리지 않고 종료
    return "\n".join(parts)


def cm_matrix(a: float, b: float, c: float, d: float, e: float, f: float) -> str:
    """CTM 변환 연산자(`cm`). 디자인 좌표를 시트 좌표로 매핑."""
    return f"{fmt(a)} {fmt(b)} {fmt(c)} {fmt(d)} {fmt(e)} {fmt(f)} cm"


def scale_translate(scale: float, ox: float, oy: float) -> Matrix:
    """등방 스케일 + 평행이동 행렬. PoC의 `s 0 0 s ox oy cm`와 동일."""
    return (scale, 0.0, 0.0, scale, ox, oy)


# 조각별 «디자이너 방식» 맞춤(2026-10-20) — preset.pieces[].fit 이 있을 때만 쓴다(없으면 예전 방식 그대로).
#   실주문 5건(고려대·홍해·신탄진·페가수스·구미혜당)을 디자이너 사이즈별 결과와 견준 결과:
#     몸판  : 높이 비율로 등방 + 위·가운데(목선) 정렬이 디자이너와 같았다(다른 픽셀 3.6~9.8% → 0.3~2.1%)
#     띠    : 조각 길이·높이에 맞춰 늘이기(목 밴드 22% → 0~3.6%)
FIT_MODES = ("top_height", "stretch")


def fit_matrix(design_region, piece_bbox, fit: str, shrink: float = 1.0) -> Matrix:
    """design_region(디자인 좌표) → 조각 bbox(시트 좌표, y 위로) 행렬.

    top_height : s = 조각높이/영역높이 (등방). 영역 위·가운데 → 조각 위·가운데.
                 폭이 남으면 본체색이 채우고, 넘치면 조각 윤곽이 잘라 낸다.
    stretch    : 가로 = 조각폭/영역폭, 세로 = 조각높이/영역높이 (비등방). 왼아래 → 왼아래.
    """
    dx0, dy0, dx1, dy1 = design_region
    px0, py0, px1, py1 = piece_bbox
    dw, dh = (dx1 - dx0), (dy1 - dy0)
    pw, ph = (px1 - px0), (py1 - py0)
    if fit == "stretch":
        sx = pw / dw * shrink
        sy = ph / dh * shrink
        return (sx, 0.0, 0.0, sy, px0 - sx * dx0, py0 - sy * dy0)
    if fit == "top_height":
        s = ph / dh * shrink
        return scale_translate(s, (px0 + px1) / 2.0 - s * (dx0 + dx1) / 2.0, py1 - s * dy1)
    raise ValueError(f"알 수 없는 fit '{fit}' (가능: {FIT_MODES})")


def _fill_polygon_ops(polygon: Sequence[Point], cmyk: Sequence[float]) -> str:
    """폴리곤을 device CMYK 본체색으로 채우는 ops(m/l…h f)를 만든다.

    ⚠️ place_block 에서 클립용 `W n` 은 경로를 '소비'한다(경로가 비워짐). 그래서 같은
       폴리곤을 fill 하려면 경로를 **다시** 그려야 한다(clip_path_ops 재사용 불가).
       device CMYK 4채널 `k`(소문자=fill 색) + `f`(채움) → CMYK 무손실·불투명·벡터 유지.

    cmyk : 본체색 4채널(예: [0.8, 0.5, 0, 0.1]).
    """
    parts = []
    for i, (x, y) in enumerate(polygon):
        parts.append(f"{fmt(x)} {fmt(y)} {'m' if i == 0 else 'l'}")
    k0, k1, k2, k3 = [float(v) for v in cmyk]
    # k = device CMYK fill 색 지정, h = 경로 닫기, f = 채움(불투명·벡터).
    return (
        f"{fmt(k0)} {fmt(k1)} {fmt(k2)} {fmt(k3)} k\n"
        + "\n".join(parts) + "\n"
        "h f"
    )


def place_block(polygon: Sequence[Point], matrix: Matrix, xobject_name: str,
                bg_cmyk: Sequence[float] | None = None) -> str:
    """조각 1개 배치 블록: 그래픽 상태 저장 → 클립 → (본체색 채움) → 변환 → 디자인 참조 → 복원.

        q
          <clip path> W n
          [bg_cmyk 있으면: k → 폴리곤 재경로 h f]   ← 클립 안에만 칠해짐
          a b c d e f cm
          /Xn Do                                   ← 디자인이 본체색 위를 덮음
        Q

    bg_cmyk : None(기본) 이면 기존과 완전 동일(하위호환). 4채널 CMYK 가 오면 클립 영역(조각
              윤곽) '안'만 본체색으로 먼저 칠한다. 그 위로 디자인 Do 가 덮으므로 디자인이 있는
              곳은 디자인색, 디자인이 비어 있는(투명) 곳만 본체색이 보인다 → 패턴선 안쪽 흰틈
              제거. 클립 안에만 칠하므로 번호/이름(extra_ops, Do 뒤·클립 밖)에는 영향이 없다.
    """
    a, b, c, d, e, f = matrix
    # 본체색 채움 블록(있을 때만). W n 직후·cm/Do 앞에 끼운다.
    fill = ""
    if bg_cmyk is not None:
        fill = f"{_fill_polygon_ops(polygon, bg_cmyk)}\n"
    return (
        "q\n"
        f"{clip_path_ops(polygon)}\n"
        f"{fill}"
        f"{cm_matrix(a, b, c, d, e, f)}\n"
        f"{xobject_name} Do\n"
        "Q"
    )


def bbox(points: Iterable[Point]) -> Tuple[float, float, float, float]:
    """점 목록의 경계 상자 (minx, miny, maxx, maxy)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)
