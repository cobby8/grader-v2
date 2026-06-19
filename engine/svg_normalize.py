# -*- coding: utf-8 -*-
"""svg_normalize — path SVG(직선 d 명령) → polyline SVG 전처리 변환기.

왜 이 모듈이 필요한가 (큰 그림):
  엔진의 parse_svg 는 패턴 조각을 <polyline points="x y x y ..."> 로 적힌 SVG 에서만
  읽는다(Adobe Illustrator "SVG Export Plug-In" 출력 형식 = U넥 패턴). 그런데 V넥 패턴
  13개는 inkscape/PyMuPDF 류가 <path d="M..H..L..V.."> + path 별 matrix(...) 로 내보낸
  형식이라 parse_svg 가 0조각으로 읽는다(태그가 polyline 이 아니라서).

  ⇒ parse_svg 를 고치지 않고(불변 제약), path SVG 를 읽어 U넥 과 '똑같은' polyline SVG 로
     다시 써 주는 '앞단 도구'가 이 모듈이다. 비유하면 '번역기' — 같은 도형을 엔진이
     알아듣는 언어(polyline)로 옮긴다. 엔진 코어는 일절 건드리지 않는다(ElementTree 만 씀).

실측으로 확인한 V넥 SVG 의 특성(2026-06-19, 13개 전수 분석):
  · 곡선 명령(C/Q/S/A) 전무 — 전부 직선(M/H/L/V). → 직선 전개로 정확 변환 가능.
  · Z(닫기) 명령 없음 — 면적 조각도 '시작점=끝점'으로만 닫혀 있다(gap≈0).
    → 닫힘 판정은 Z 유무가 아니라 '시작점≈끝점 근접'으로 한다.
  · XL 만 가로 viewBox(4478×3401)·큰 조각 2개. 나머지 12개는 세로 viewBox(4478×5669)에
    앞·뒤판이 '위·아래 2벌씩' 중복돼 큰 조각이 4개. → 중복 제거로 앞·뒤 2개만 남긴다.
  · 보조선(접는선=세로선, 밑단표식=수평선)은 폭/높이 한쪽이 0이거나 점이 적다. → 필터.

불변 제약(절대 준수):
  parse_svg/Polyline 등 engine 공개 API 무수정. pattern.py 에 함수 추가하지 않는다(계층 분리).
  이 모듈은 표준 라이브러리(re, xml, math, os)만 쓰고 engine 코어를 import 하지 않는다.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from typing import List, Tuple

Point = Tuple[float, float]

# 숫자 토큰(부호·소수·지수 허용). parse_svg 의 _NUM 과 동형으로 맞춘다.
_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
# d 속성 토큰화: 명령 글자(직선 + 곡선) 또는 숫자.
_DTOK = re.compile(r"[MmLlHhVvZzCcQqSsAa]|" + _NUM)
_NUM_RE = re.compile(_NUM)
_SVG_NS = "http://www.w3.org/2000/svg"


# ─────────────────────────────────────────────────────────────────────────────
# 1) d 속성 파서 (직선 명령 전개)
# ─────────────────────────────────────────────────────────────────────────────
def _parse_path_d(d: str, *, flatten_curves: bool = False, samples: int = 16):
    """SVG path 의 d 문자열을 직선 점열로 전개한다.

    지원 명령(현재 V넥 데이터에 존재하는 것):
      M/m 이동(시작), L/l 선, H/h 수평선, V/v 수직선, Z/z 닫기(시작점 복귀).
      절대(대문자)는 그대로, 상대(소문자)는 현재 좌표에 더한다.

    곡선(C/Q/S/A): 현재 V넥 데이터엔 0개라 미사용. flatten_curves=True 면 끝점만
      이어 직선 근사(거친 폴백)하고 has_curves=True 로 표시. False 면 끝점만 잇되
      경고용으로 has_curves 만 올린다(1차는 직선 데이터만 정확 처리하는 게 목표).

    반환: (points, closed, has_curves)
      points     : [(x, y), ...] viewBox 좌표(flip 하지 않음 — 핵심).
      closed     : Z 가 있었거나 시작점≈끝점이면 True.
      has_curves : 곡선 명령을 만났으면 True(경고용).
    """
    toks = _DTOK.findall(d)
    pts: List[Point] = []
    cx = cy = 0.0     # 현재 좌표
    sx = sy = 0.0     # 현재 서브패스 시작점(Z 복귀용)
    cmd = None
    i = 0
    n = len(toks)
    had_z = False
    has_curves = False

    def _read(k: int) -> List[float]:
        """다음 k개 숫자 토큰을 읽어 float 로 반환(인덱스 i 전진)."""
        nonlocal i
        vals = [float(toks[i + j]) for j in range(k)]
        i += k
        return vals

    while i < n:
        t = toks[i]
        if re.match(r"[A-Za-z]", t):
            cmd = t
            i += 1
            if cmd in "Zz":
                # 닫기: 시작점으로 복귀(점을 또 찍지는 않음 — 시작점과 동일).
                had_z = True
                cx, cy = sx, sy
            continue

        # 명령 없이 숫자가 이어지면 직전 명령의 반복(SVG 규약).
        if cmd in "Mm":
            x, y = _read(2)
            if cmd == "m":
                x += cx; y += cy
            cx, cy = x, y
            sx, sy = x, y
            pts.append((cx, cy))
            # M 다음 이어지는 좌표쌍은 암묵적으로 L/l 로 처리(SVG 규약).
            cmd = "L" if cmd == "M" else "l"
        elif cmd in "Ll":
            x, y = _read(2)
            if cmd == "l":
                x += cx; y += cy
            cx, cy = x, y
            pts.append((cx, cy))
        elif cmd in "Hh":
            (x,) = _read(1)
            if cmd == "h":
                x += cx
            cx = x
            pts.append((cx, cy))
        elif cmd in "Vv":
            (y,) = _read(1)
            if cmd == "v":
                y += cy
            cy = y
            pts.append((cx, cy))
        elif cmd in "CcQqSsAa":
            # 곡선 — 현재 데이터엔 없음. 파라미터 개수만큼 소비하고 끝점만 직선으로 잇는다.
            has_curves = True
            params = {"C": 6, "c": 6, "S": 4, "s": 4, "Q": 4, "q": 4,
                      "A": 7, "a": 7}[cmd]
            vals = _read(params)
            # 끝점(마지막 좌표쌍)만 사용 — 1차 폴백(정밀 평탄화는 후속 과제).
            ex, ey = vals[-2], vals[-1]
            if cmd.islower():
                ex += cx; ey += cy
            cx, cy = ex, ey
            pts.append((cx, cy))
        else:
            i += 1  # 알 수 없는 토큰은 건너뜀(방어)

    # 닫힘 판정: Z 가 있었거나, 점이 충분하고 시작점≈끝점이면 닫힌 면적 조각.
    closed = had_z
    if not closed and len(pts) >= 3:
        dx = pts[0][0] - pts[-1][0]
        dy = pts[0][1] - pts[-1][1]
        if math.hypot(dx, dy) <= 1.0:  # 1pt 이내면 닫힌 것으로 본다(실측 gap≈0).
            closed = True

    return pts, closed, has_curves


# ─────────────────────────────────────────────────────────────────────────────
# 2) transform="matrix(a,b,c,d,e,f)" 파싱·적용
# ─────────────────────────────────────────────────────────────────────────────
def _parse_matrix(transform: str) -> Tuple[float, float, float, float, float, float]:
    """transform 문자열에서 matrix(a,b,c,d,e,f) 6요소를 뽑는다. 없으면 항등행렬.

    V넥은 전부 matrix(1,0,0,-1,tx,ty)(y반전+평행이동)지만, 일반 6요소를 그대로 지원한다.
    """
    if not transform:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    m = re.search(r"matrix\(([^)]*)\)", transform)
    if not m:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    nums = [float(x) for x in _NUM_RE.findall(m.group(1))[:6]]
    if len(nums) < 6:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return tuple(nums)  # type: ignore[return-value]


def _apply_matrix(pts: List[Point], mat) -> List[Point]:
    """각 점에 affine matrix 를 적용한다: x' = a*x + c*y + e, y' = b*x + d*y + f."""
    a, b, c, d, e, f = mat
    return [(a * x + c * y + e, b * x + d * y + f) for (x, y) in pts]


def _bbox(pts: List[Point]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ─────────────────────────────────────────────────────────────────────────────
# 3) viewBox 추출
# ─────────────────────────────────────────────────────────────────────────────
def _strip_ns(tag: str) -> str:
    """'{ns}path' → 'path'. 네임스페이스 접두 제거."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _get_viewbox(root: ET.Element) -> Tuple[str, float, float]:
    """root 의 viewBox 문자열과 (W, H) 를 돌려준다. 없으면 width/height 폴백."""
    vb = root.get("viewBox")
    if vb:
        nums = _NUM_RE.findall(vb)
        if len(nums) >= 4:
            return vb.strip(), float(nums[2]), float(nums[3])
    w = root.get("width", "0")
    h = root.get("height", "0")
    wv = float(_NUM_RE.findall(w)[0]) if _NUM_RE.findall(w) else 0.0
    hv = float(_NUM_RE.findall(h)[0]) if _NUM_RE.findall(h) else 0.0
    return f"0 0 {wv} {hv}", wv, hv


# ─────────────────────────────────────────────────────────────────────────────
# 4) 메인 변환 함수
# ─────────────────────────────────────────────────────────────────────────────
def normalize_svg(in_path: str, out_path: str, *,
                  min_points: int = 3,
                  drop_open: bool = True,
                  min_dim_ratio: float = 0.05,
                  dedup_tol_ratio: float = 0.01,
                  flatten_curves: bool = False,
                  samples: int = 16) -> dict:
    """path SVG 를 읽어 U넥형 polyline SVG 로 다시 쓴다(원자적 저장).

    매개변수
      in_path        : 입력 path SVG 경로.
      out_path       : 출력 polyline SVG 경로(임시파일→os.replace 로 원자적 저장).
      min_points     : 폴리라인 최소 점 수(이보다 적으면 보조선으로 보고 버림).
      drop_open      : True 면 '열린' 조각(시작≠끝)을 버린다. V넥 면적 조각은 모두 닫힘.
      min_dim_ratio  : 페이지 대비 폭·높이 최소 비율. 둘 중 하나라도 이보다 작으면(세로선·
                       수평선·작은 표식) 버린다. 0.05 = 5%.
      dedup_tol_ratio: 중복 조각 판정 허용오차(페이지 대비 비율). bbox 폭·높이·중심이 모두
                       이 안에서 같으면 같은 조각으로 보고 1개만 남긴다(위·아래 중복 제거).
      flatten_curves : (인터페이스만) 곡선 평탄화 모드. 현재 V넥 곡선 0이라 미사용.
      samples        : (인터페이스만) 곡선 평탄화 분할 수.

    반환(dict): {
      "in", "out", "viewBox", "pieces_written", "dropped_open", "dropped_small",
      "dropped_dup", "has_curves", "bboxes":[[x0,y0,x1,y1]...], "warnings":[...]}

    좌표 처리의 핵심(이중 flip 금지):
      matrix 적용 결과는 viewBox 좌표(y 아래로)다. polyline 에도 viewBox 좌표 '그대로' 쓴다.
      parse_svg 가 읽을 때 자체적으로 flip_y 한다(U넥 SVG 도 viewBox 좌표 저장). 여기서
      flip 하면 parse_svg 가 또 flip → 상하반전된다. 그래서 변환기는 절대 flip 하지 않는다.
    """
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"입력 SVG 없음: {in_path}")

    warnings: List[str] = []
    tree = ET.parse(in_path)
    root = tree.getroot()
    vb_str, vb_w, vb_h = _get_viewbox(root)
    page_dim = max(vb_w, vb_h) if max(vb_w, vb_h) > 0 else 1.0

    # ── 모든 <path> 를 순회하며 점열로 전개 + matrix 적용 ──
    candidates = []  # (pts(viewBox 좌표), bbox, closed)
    any_curves = False
    for el in root.iter():
        if _strip_ns(el.tag) != "path":
            continue
        d = el.get("d", "")
        if not d:
            continue
        pts, closed, has_curves = _parse_path_d(
            d, flatten_curves=flatten_curves, samples=samples)
        if has_curves:
            any_curves = True
        if not pts:
            continue
        mat = _parse_matrix(el.get("transform", ""))
        pts = _apply_matrix(pts, mat)  # viewBox 좌표(flip 안 함)
        candidates.append((pts, _bbox(pts), closed))

    if any_curves:
        warnings.append(
            "🟡 곡선 명령(C/Q/S/A)을 만나 끝점만 직선 근사했습니다. 형태가 어긋날 수 있어 "
            "확인이 필요합니다(현재 V넥 데이터엔 곡선이 없어야 정상).")

    # ── 보조선·작은 표식 필터 ──
    dropped_open = 0
    dropped_small = 0
    kept = []  # (pts, bbox)
    for pts, bb, closed in candidates:
        x0, y0, x1, y1 = bb
        w = x1 - x0
        h = y1 - y0
        # 점이 너무 적으면 선분(보조선) → 버림.
        if len(pts) < min_points:
            dropped_small += 1
            continue
        # 폭·높이 중 하나라도 페이지 대비 너무 작으면(세로선/수평선/작은 표식) → 버림.
        if w < page_dim * min_dim_ratio or h < page_dim * min_dim_ratio:
            dropped_small += 1
            continue
        # 닫히지 않은(열린) 조각은 면적 조각이 아님 → drop_open 이면 버림.
        if drop_open and not closed:
            dropped_open += 1
            continue
        kept.append((pts, bb))

    # ── 중복 조각 제거(위·아래 2벌 같은 조각 → 1개). bbox 폭·높이·중심 근사 동일 기준. ──
    tol = page_dim * dedup_tol_ratio
    deduped = []  # (pts, bbox)
    dropped_dup = 0
    for pts, bb in kept:
        x0, y0, x1, y1 = bb
        w = x1 - x0
        h = y1 - y0
        cx = (x0 + x1) / 2.0
        is_dup = False
        for _, ebb in deduped:
            ex0, ey0, ex1, ey1 = ebb
            ew = ex1 - ex0
            eh = ey1 - ey0
            ecx = (ex0 + ex1) / 2.0
            # 폭·높이·가로중심이 모두 tol 안에서 같으면 같은 조각(세로위치만 다른 복제).
            if (abs(w - ew) <= tol and abs(h - eh) <= tol
                    and abs(cx - ecx) <= tol):
                is_dup = True
                break
        if is_dup:
            dropped_dup += 1
            continue
        deduped.append((pts, bb))

    # ── 출력 SVG 작성: U넥 과 동일 골격(viewBox 그대로, polyline class="st0"). ──
    #    조각 순서는 입력 path 순서 유지(parse_svg 가 어차피 높이 내림차순 재정렬한다).
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="{_SVG_NS}" version="1.1" '
        f'width="{vb_w:g}" height="{vb_h:g}" viewBox="{vb_str}">',
        "  <defs>",
        "    <style>",
        "      .st0 {",
        "        fill: none;",
        "        stroke: #231815;",
        "        stroke-miterlimit: 10;",
        "        stroke-width: .2px;",
        "      }",
        "    </style>",
        "  </defs>",
    ]
    bboxes = []
    for pts, bb in deduped:
        pts_str = " ".join(f"{x:g} {y:g}" for (x, y) in pts)
        lines.append(f'  <polyline class="st0" points="{pts_str}"/>')
        bboxes.append([round(v, 2) for v in bb])
    lines.append("</svg>")
    svg_text = "\n".join(lines) + "\n"

    # ── 원자적 저장(임시파일 → os.replace). 중간 실패 시 부분 파일을 남기지 않는다. ──
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".svg", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(svg_text)
        os.replace(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    return {
        "in": in_path,
        "out": out_path,
        "viewBox": vb_str,
        "pieces_written": len(deduped),
        "dropped_open": dropped_open,
        "dropped_small": dropped_small,
        "dropped_dup": dropped_dup,
        "has_curves": any_curves,
        "bboxes": bboxes,
        "warnings": warnings,
    }
