# -*- coding: utf-8 -*-
"""패턴 파일 파싱 — SVG → 조각별 윤곽 점 목록 (PDF 좌표).

실제 운영 패턴(Adobe Illustrator SVG 내보내기)은 조각을 <polyline points="x y x y ...">
로 표현한다. viewBox 좌표계는 y가 아래로 증가(좌상단 원점)하므로, PDF 좌표(y 위로 증가,
좌하단 원점)로 뒤집어 준다.

이식한 지식(DESIGN.md 9번):
  · 조각 분류는 x위치보다 '크기(높이)' 기준이 안정적 (lessons 2026-04-21).
DXF 입력(ezdxf)은 Phase 4에서 같은 Polyline 표현으로 정규화해 합류시킨다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Tuple

Point = Tuple[float, float]
_SVG_NS = "{http://www.w3.org/2000/svg}"
_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class Polyline:
    """패턴 조각 1개의 윤곽 (PDF 좌표, y는 위로 증가)."""
    points: List[Point]

    @property
    def height(self) -> float:
        ys = [p[1] for p in self.points]
        return max(ys) - min(ys)

    @property
    def width(self) -> float:
        xs = [p[0] for p in self.points]
        return max(xs) - min(xs)

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)


def _parse_points_attr(raw: str) -> List[Point]:
    """'x1 y1 x2 y2 ...' 또는 'x1,y1 x2,y2' 모두 허용 → [(x,y), ...]."""
    nums = [float(n) for n in _NUM.findall(raw)]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _viewbox(root: ET.Element) -> Tuple[float, float, float, float]:
    vb = root.get("viewBox")
    if vb:
        x, y, w, h = (float(n) for n in _NUM.findall(vb)[:4])
        return x, y, w, h
    # viewBox 없으면 width/height 폴백
    w = float(_NUM.findall(root.get("width", "0"))[0]) if root.get("width") else 0.0
    h = float(_NUM.findall(root.get("height", "0"))[0]) if root.get("height") else 0.0
    return 0.0, 0.0, w, h


def parse_svg(path: str, flip_y: bool = True) -> List[Polyline]:
    """SVG에서 모든 <polyline>/<polygon> 조각을 읽어 PDF 좌표 Polyline 목록으로 반환.

    flip_y=True : viewBox 높이를 기준으로 y를 뒤집어 PDF 좌표(y 위로)로 맞춘다.
    조각은 높이 내림차순으로 정렬(큰 조각=앞/뒤판 먼저) — 분류·디버깅 편의.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    _, _, _, vb_h = _viewbox(root)

    polylines: List[Polyline] = []
    for tag in ("polyline", "polygon"):
        for el in root.iter(f"{_SVG_NS}{tag}"):
            pts = _parse_points_attr(el.get("points", ""))
            if len(pts) < 3:
                continue
            if flip_y and vb_h:
                pts = [(x, vb_h - y) for (x, y) in pts]
            polylines.append(Polyline(points=pts))

    polylines.sort(key=lambda pl: pl.height, reverse=True)
    return polylines


def classify_by_height(polylines: List[Polyline]) -> dict:
    """조각을 높이 기준으로 큰/작은 그룹으로 단순 분류 (DESIGN.md 지식 이식).

    반환: {'large': [...], 'small': [...]} — 중앙값 높이 기준.
    실제 조각 정의는 preset.json에 명시하는 것이 원칙이나, 자동 분류의 1차 근거로 사용.
    """
    if not polylines:
        return {"large": [], "small": []}
    heights = sorted(pl.height for pl in polylines)
    mid = heights[len(heights) // 2]
    large = [pl for pl in polylines if pl.height >= mid]
    small = [pl for pl in polylines if pl.height < mid]
    return {"large": large, "small": small}
