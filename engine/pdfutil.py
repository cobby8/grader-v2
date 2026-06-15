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


def place_block(polygon: Sequence[Point], matrix: Matrix, xobject_name: str) -> str:
    """조각 1개 배치 블록: 그래픽 상태 저장 → 클립 → 변환 → 디자인 참조 → 복원.

        q
          <clip path> W n
          a b c d e f cm
          /Xn Do
        Q
    """
    a, b, c, d, e, f = matrix
    return (
        "q\n"
        f"{clip_path_ops(polygon)}\n"
        f"{cm_matrix(a, b, c, d, e, f)}\n"
        f"{xobject_name} Do\n"
        "Q"
    )


def bbox(points: Iterable[Point]) -> Tuple[float, float, float, float]:
    """점 목록의 경계 상자 (minx, miny, maxx, maxy)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)
