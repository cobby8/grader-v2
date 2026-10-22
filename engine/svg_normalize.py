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
_DTOK = re.compile(r"[MmLlHhVvZzCcQqSsTtAa]|" + _NUM)
_NUM_RE = re.compile(_NUM)
_SVG_NS = "http://www.w3.org/2000/svg"


# ─────────────────────────────────────────────────────────────────────────────
# 1) d 속성 파서 (직선 명령 전개)
# ─────────────────────────────────────────────────────────────────────────────
def _parse_path_d(d: str, *, flatten_curves: bool = True, samples: int = 16):
    """SVG path 의 d 문자열을 직선 점열로 전개한다.

    지원 명령(현재 V넥 데이터에 존재하는 것):
      M/m 이동(시작), L/l 선, H/h 수평선, V/v 수직선, Z/z 닫기(시작점 복귀).
      절대(대문자)는 그대로, 상대(소문자)는 현재 좌표에 더한다.

    곡선(C/S/Q/T): 베지어를 samples 등분한 직선으로 평탄화한다(2026-10-20).
      예전엔 끝점만 이어 축구 소매 산에서 재단선이 최대 1.3mm 어긋났다(곡선 마스터 실측).
      flatten_curves=False 면 그 옛 동작(끝점만)을 그대로 한다 — 비교·회귀 확인용.
      호(A)는 드물어 끝점만 잇고 has_curves 로 알린다.

    반환: (points, closed, has_curves)
      points     : [(x, y), ...] viewBox 좌표(flip 하지 않음 — 핵심).
      closed     : Z 가 있었거나 시작점≈끝점이면 True.
      has_curves : 끝점만 이은 곡선(호, 또는 flatten_curves=False 의 베지어)이 있으면 True(경고용).
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
    last_c = None     # 직전 C/S 의 두 번째 조절점(S 의 반사용)
    last_q = None     # 직전 Q/T 의 조절점(T 의 반사용)

    def _bezier(p0, p1, p2, p3=None):
        """베지어(3차 또는 p3=None 이면 2차)를 samples 등분한 점들(시작점 제외)."""
        out = []
        for k in range(1, samples + 1):
            t = k / samples
            u = 1.0 - t
            if p3 is None:
                x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
                y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            else:
                x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
                y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
            out.append((x, y))
        return out

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
                last_c = last_q = None
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
        elif cmd in "CcSsQqTt" and flatten_curves:
            # 베지어 평탄화 — 상대 명령(소문자)은 모든 좌표에 현재점을 더한다.
            params = {"C": 6, "S": 4, "Q": 4, "T": 2}[cmd.upper()]
            vals = _read(params)
            if cmd.islower():
                vals = [v + (cx if j % 2 == 0 else cy) for j, v in enumerate(vals)]
            p0 = (cx, cy)
            up = cmd.upper()
            if up == "C":
                p1, p2, p3 = (vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5])
                pts.extend(_bezier(p0, p1, p2, p3))
                last_c, last_q = p2, None
            elif up == "S":
                p1 = (2 * cx - last_c[0], 2 * cy - last_c[1]) if last_c else p0
                p2, p3 = (vals[0], vals[1]), (vals[2], vals[3])
                pts.extend(_bezier(p0, p1, p2, p3))
                last_c, last_q = p2, None
            elif up == "Q":
                q1, p3 = (vals[0], vals[1]), (vals[2], vals[3])
                pts.extend(_bezier(p0, q1, p3))
                last_q, last_c = q1, None
            else:  # T
                q1 = (2 * cx - last_q[0], 2 * cy - last_q[1]) if last_q else p0
                p3 = (vals[0], vals[1])
                pts.extend(_bezier(p0, q1, p3))
                last_q, last_c = q1, None
            cx, cy = p3
            continue
        elif cmd in "CcQqSsTtAa":
            # 끝점만 잇는 폴백 — 호(A), 또는 flatten_curves=False(옛 동작 확인용) 의 베지어.
            has_curves = True
            params = {"C": 6, "c": 6, "S": 4, "s": 4, "Q": 4, "q": 4, "T": 2, "t": 2,
                      "A": 7, "a": 7}[cmd]
            vals = _read(params)
            ex, ey = vals[-2], vals[-1]
            if cmd.islower():
                ex += cx; ey += cy
            cx, cy = ex, ey
            pts.append((cx, cy))
        else:
            i += 1  # 알 수 없는 토큰은 건너뜀(방어)
        last_c = last_c if cmd in "CcSs" else None   # S/T 반사는 바로 앞 명령이 같은 계열일 때만
        last_q = last_q if cmd in "QqTt" else None

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


def _perimeter(pts: List[Point]) -> float:
    """닫힌 둘레 길이(마지막 점 → 첫 점 포함). 중복 조각 판정용."""
    n = len(pts)
    return sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n))


def _polygon_area(pts: List[Point]) -> float:
    """신발끈 공식 넓이(절댓값). 중복 조각 판정용."""
    n = len(pts)
    s = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
            for i in range(n))
    return abs(s) / 2.0


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
def _shoelace_abs(pts) -> float:
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def _chain_open_paths(cands: list, tol: float = 1.5) -> Tuple[list, int]:
    """(2026-10-21) 끝점이 맞닿는 열린 선들을 이어 닫힌 조각으로 만든다.

    왜: 슈팅셔츠 마스터는 조각 윤곽을 «반쪽 열린 선 두 개» 로 그렸다(3XL 소매·XL 앞판 — 시작·끝이 bbox 대각선
    양 끝). 열린 선은 조각이 아니라고 버려서 «소매 없음·앞판 없음» 으로 보였다(디자이너: 조각은 다 들어 있다).
    같은 선을 겹쳐 그린 사본끼리 이으면 넓이 0 고리가 되니, 이은 결과가 bbox 의 5% 이상 넓이일 때만 인정한다.
    cands: [(pts, bbox, closed)] → (새 목록, 이어 만든 조각 수). 못 이은 열린 선은 그대로 남긴다.
    """
    opens = [i for i, c in enumerate(cands) if not c[2] and len(c[0]) >= 2]
    used = set()
    made = []
    for i in opens:
        if i in used:
            continue
        chain = list(cands[i][0])
        members = [i]
        grew = True
        while grew and math.dist(chain[0], chain[-1]) > tol:
            grew = False
            for j in opens:
                if j in used or j in members:
                    continue
                q = cands[j][0]
                if sorted(q) == sorted(chain):        # 같은 선의 사본
                    continue
                if math.dist(chain[-1], q[0]) <= tol:
                    chain += list(q[1:])
                elif math.dist(chain[-1], q[-1]) <= tol:
                    chain += list(reversed(q[:-1]))
                else:
                    continue
                members.append(j)
                grew = True
                break
        if len(members) < 2 or math.dist(chain[0], chain[-1]) > tol:
            continue
        if not any(len(cands[m][0]) >= 5 for m in members):
            continue                                  # 짧은 직선 넷으로 된 상자(라벨 칸)는 조각이 아니다
        bb = _bbox(chain)
        if _shoelace_abs(chain[:-1]) < 0.05 * (bb[2] - bb[0]) * (bb[3] - bb[1]):
            continue
        used.update(members)
        made.append((chain[:-1], bb, True))
    # 다른 조각 안에 쏙 들어가는 고리 = 그 조각의 봉제선·보조선(소매 안쪽 선 등) → 버린다
    #   (점 4개 이하 사각형 = 대지 테·라벨 칸은 «바깥 조각» 으로 치지 않는다)
    boxes = [c[1] for c in cands if c[2] and len(c[0]) > 5] + [m[1] for m in made]

    def _inside(bb):
        return any(o is not bb and o[0] - 2 <= bb[0] and o[1] - 2 <= bb[1] and bb[2] <= o[2] + 2 and bb[3] <= o[3] + 2
                   and (bb[2] - bb[0]) * (bb[3] - bb[1]) < (o[2] - o[0]) * (o[3] - o[1]) for o in boxes)
    made = [m for m in made if not _inside(m[1])]
    if not made:
        return cands, 0
    return [c for k, c in enumerate(cands) if k not in used] + made, len(made)


def normalize_svg(in_path: str, out_path: str, *,
                  min_points: int = 3,
                  drop_open: bool = True,
                  min_dim_ratio: float = 0.05,
                  min_area_ratio: float = 0.002,
                  dedup_tol_ratio: float = 0.01,
                  flatten_curves: bool = True,
                  samples: int = 16,
                  rel_area_ratio: float = 0.02,
                  edge_cut_pt: float = 100.0,
                  margin_pt: float = 50.0) -> dict:
    """path SVG 를 읽어 U넥형 polyline SVG 로 다시 쓴다(원자적 저장).

    매개변수
      in_path        : 입력 path SVG 경로.
      out_path       : 출력 polyline SVG 경로(임시파일→os.replace 로 원자적 저장).
      min_points     : 폴리라인 최소 점 수(이보다 적으면 보조선으로 보고 버림).
      drop_open      : True 면 '열린' 조각(시작≠끝)을 버린다. V넥 면적 조각은 모두 닫힘.
      min_dim_ratio  : 페이지 대비 폭·높이 최소 비율. (이슈3 정정) "한 축이라도 작으면 버림"은
                       목 '밴드' 조각(폭은 충분, 높이만 얇음 176pt)까지 버리는 부작용이 있었다.
                       → 이제 폭·높이 '둘 다' 이 비율보다 작을 때만 버린다(진짜 보조선=양축 작음).
                       밴드처럼 한 축만 얇고 다른 축이 충분한 띠 조각은 보존된다. 0.05 = 5%.
      min_area_ratio : 페이지넓이(page_dim²) 대비 최소 면적 비율. bbox 면적이 이보다 작으면
                       (접는선·짧은 표식 등 면적이 거의 0인 보조선) 버린다. 한 축만 얇아도
                       면적이 충분하면(밴드) 보존. 0.002 = 0.2%(예: 4337²×0.002≈3.8만pt²).
                       실측 밴드 최소 면적 ≈ 24만pt² 이므로 안전히 보존, 0면적 보조선만 제거.
      dedup_tol_ratio: 중복 조각 판정 허용오차(페이지 대비 비율). bbox 폭·높이·중심이 모두
                       이 안에서 같고 둘레·넓이까지 같으면 같은 조각으로 보고 1개만 남긴다
                       (위·아래 중복 제거). 크기만 비슷한 다른 조각(목·암홀 밴드)은 남는다.
      flatten_curves : 베지어를 samples 등분 직선으로 평탄화(기본 True). False 는 옛 «끝점만» 동작.
      samples        : 곡선 하나를 나눌 직선 수.
      rel_area_ratio : 면적 임계를 «가장 큰 조각 bbox 넓이 × 이 비율» 과 페이지 기준 중 작은 쪽으로(2026-10-20).
                       대지가 크면(축구 5080mm) 페이지 기준만으로는 목 밴드(54mm 띠)가 보조선으로 버려졌다.
      edge_cut_pt    : 대지 테두리 위에 곧게 누운 변의 합이 이 길이(pt, 100≈35mm) 이상인 조각은
                       «대지에 잘린 조각»으로 보고 뺀다(하키티 소매·하의 XL 트임판 — 온전한 사본이 따로 있거나 자산 결함).
      margin_pt      : 조각이 대지 밖으로 나가 있으면 전체를 이만큼 여백을 두고 대지 안으로 옮긴다
                       (그레이더 출력 페이지는 좌하단 원점이라 음수 좌표 조각이 잘렸다 — 슈팅셔츠 M).

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

    vb_nums = [float(v) for v in _NUM_RE.findall(vb_str)[:4]]
    vb_x, vb_y = (vb_nums[0], vb_nums[1]) if len(vb_nums) >= 2 else (0.0, 0.0)

    # ── 자르개(클립)·정의 안의 path 는 «그림»이 아니다 — 건너뛴다(2026-10-20). ──
    #    PyMuPDF 는 페이지 테두리를 <clipPath> 안 사각형으로 내보낸다. 이걸 조각으로 읽어
    #    테두리가 사이즈마다 같은 좌표라 «복붙 결함» 오판 → 하키티·슈팅셔츠·축구·하의 사이즈가 꺼졌다.
    _NON_DRAWING = ("clipPath", "mask", "defs", "pattern", "symbol", "marker")
    parent = {c: p for p in root.iter() for c in p}

    def _inside_non_drawing(e) -> bool:
        while e in parent:
            e = parent[e]
            if _strip_ns(e.tag) in _NON_DRAWING:
                return True
        return False

    # ── 모든 <path> 를 순회하며 점열로 전개 + matrix 적용 ──
    candidates = []  # (pts(viewBox 좌표), bbox, closed)
    stroked = {}     # id(pts) → 윤곽선(stroke)이 있는 요소인가 — 채움만 있는 «잘린 사본» 판정용
    any_curves = False
    dropped_clip = 0
    for el in root.iter():
        if _strip_ns(el.tag) != "path":
            continue
        if _inside_non_drawing(el):
            dropped_clip += 1
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
        stroke = (el.get("stroke") or "").strip().lower()
        style = (el.get("style") or "").replace(" ", "").lower()
        if "stroke:" in style:
            stroke = style.split("stroke:", 1)[1].split(";", 1)[0]
        stroked[id(pts)] = bool(stroke) and stroke != "none"
        candidates.append((pts, _bbox(pts), closed))

    if any_curves:
        warnings.append(
            "🟡 곡선(호)을 끝점만 이어 직선으로 근사했습니다. 형태가 어긋날 수 있어 확인이 필요합니다.")
    candidates, n_chained = _chain_open_paths(candidates)
    for pts, bb, closed in candidates[len(candidates) - n_chained:]:
        stroked[id(pts)] = True             # 이어 만든 조각은 윤곽선에서 왔다(잘린 채움 사본 아님)

    # ── 보조선·작은 표식 필터 (이슈3에서 정정) ──
    #   [수정 이유] 종전 "한 축이라도 5%보다 작으면 버림"은 목 '밴드' 조각(폭 1380~1992,
    #   높이 176pt)까지 버려 V넥에 밴드 조각이 누락됐다. 밴드는 한 축(높이)만 얇을 뿐
    #   '면적'은 충분한(≈24만~35만pt²) 띠 조각이다. 진짜 보조선(접는선/짧은표식)은
    #   '양 축이 둘 다 작거나' '면적이 거의 0'이다.
    #   → 판정 기준을 (A)양 축이 둘 다 작을 때만 버림  AND  (B)면적이 최소치 미만이면 버림
    #     으로 바꿔, 밴드는 보존하고 진짜 보조선만 제거한다.
    dim_thr = page_dim * min_dim_ratio          # 길이 임계(폭/높이)
    area_thr = (page_dim ** 2) * min_area_ratio  # 면적 임계(page_dim² 대비 비율)
    # (2026-10-20) 대지가 아주 크면 페이지 기준 임계가 진짜 조각(목 밴드)을 버린다 →
    #   «가장 큰 닫힌 조각» 기준과 견줘 작은 쪽을 쓴다. 보통 대지(V넥 4478pt)에선 면적 임계는 그대로고
    #   길이 임계만 283→약 200pt 로 낮아지는데, 면적 임계가 남아 있어 결과는 같다(농구 마스터 4종 실측 0.0pt).
    big = [(bb[2] - bb[0], bb[3] - bb[1]) for pts, bb, closed in candidates
           if closed and len(pts) >= min_points]
    if big:
        bw, bh = max(big, key=lambda wh: wh[0] * wh[1])
        dim_thr = min(dim_thr, max(bw, bh) * 0.1)
        area_thr = min(area_thr, bw * bh * rel_area_ratio)
    dropped_open = 0
    dropped_small = 0
    kept = []  # (pts, bbox)
    for pts, bb, closed in candidates:
        x0, y0, x1, y1 = bb
        w = x1 - x0
        h = y1 - y0
        area = w * h
        # 점이 너무 적으면 선분(보조선) → 버림.
        if len(pts) < min_points:
            dropped_small += 1
            continue
        # (A) 폭·높이가 '둘 다' 너무 작으면(점 같은 작은 표식) → 버림.
        #     한 축만 작은 띠(밴드)는 이 조건을 통과한다.
        if w < dim_thr and h < dim_thr:
            dropped_small += 1
            continue
        # (B) bbox 면적이 최소치 미만이면(접는선처럼 한 축이 0에 수렴하는 보조선) → 버림.
        #     밴드는 면적이 충분(≈24만+)하므로 통과, 0면적 보조선만 제거된다.
        if area < area_thr:
            dropped_small += 1
            continue
        # 닫히지 않은(열린) 조각은 면적 조각이 아님 → drop_open 이면 버림.
        if drop_open and not closed:
            dropped_open += 1
            continue
        kept.append((pts, bb))

    # ── 중복 조각 제거(위·아래 2벌 같은 조각 → 1개). bbox 폭·높이·중심 근사 동일 + 모양 동일 기준. ──
    #    (2026-10-19) bbox 만 보면 «크기가 비슷한 다른 조각»까지 버린다. 실측: V넥 슬림(암홀O)
    #    2XL~5XL 에서 목 밴드(661mm)와 암홀 밴드(644mm)가 tol(≈20mm) 안이라 암홀 밴드가 사라졌다.
    #    그래서 둘레·넓이까지 같아야 복제로 본다. 드라이브 218개 실측: 진짜 복제는 둘레차 ≤1.1pt·
    #    넓이차 ≤0.04%, 잘못 버려지던 조각은 둘레차 ≥12pt·넓이차 ≥1.8%.
    tol = page_dim * dedup_tol_ratio
    deduped = []  # (pts, bbox, 둘레, 넓이)
    dropped_dup = 0
    for pts, bb in kept:
        x0, y0, x1, y1 = bb
        w = x1 - x0
        h = y1 - y0
        cx = (x0 + x1) / 2.0
        per = _perimeter(pts)
        area = _polygon_area(pts)
        is_dup = False
        for e_pts, ebb, eper, earea in deduped:
            ex0, ey0, ex1, ey1 = ebb
            ew = ex1 - ex0
            eh = ey1 - ey0
            ecx = (ex0 + ex1) / 2.0
            # 폭·높이·가로중심이 모두 tol 안에서 같고(세로위치만 다른 복제),
            # 둘레·넓이도 같아야(모양이 같은 복제) 같은 조각.
            if (abs(w - ew) <= tol and abs(h - eh) <= tol
                    and abs(cx - ecx) <= tol
                    and abs(per - eper) <= max(2.0, 0.002 * eper)
                    and abs(area - earea) <= 0.005 * max(earea, 1e-9)):
                is_dup = True
                stroked[id(e_pts)] = stroked.get(id(e_pts), False) or stroked.get(id(pts), False)   # 채움+선 쌍이면 «선 있음»
                break
        if is_dup:
            dropped_dup += 1
            continue
        deduped.append((pts, bb, per, area))

    # ── 대지에 잘린 조각 빼기(2026-10-20) ──
    #    대지 테두리 위에 곧게 누운 변이 길면 «대지에서 잘린» 모양이다. 하키티 소매는 온전한 윤곽과
    #    대지에 잘린 흰 채움이 함께 들어 있어 두 번 잡혔고, 하의 XL 트임판은 잘린 모양만 있다(자산 결함).
    def _edge_run(pts) -> float:
        lines = ((0, vb_x), (0, vb_x + vb_w), (1, vb_y), (1, vb_y + vb_h))   # (축, 값)
        run = 0.0
        n = len(pts)
        for k in range(n):
            a, b = pts[k], pts[(k + 1) % n]
            for ax, v in lines:
                if abs(a[ax] - v) <= 0.5 and abs(b[ax] - v) <= 0.5:
                    run += math.dist(a, b)
                    break
        return run

    #    단, 대지를 그림에 딱 맞춘 파일은 «멀쩡한» 조각의 곧은 변도 경계 위에 놓인다 → 아래 둘 중 하나일 때만 뺀다.
    #      ① 같은 자리에 더 큰 «온전한 사본»이 있다(하키티 소매)  ② 윤곽선 없이 채움만 있는 요소다(잘린 색 면 — 하의 XL 트임판)
    #    둘 다 아니면 남기고 경고만 한다.
    def _contains(big, small, tol=2.0):
        return (big[0] - tol <= small[0] and big[1] - tol <= small[1]
                and big[2] + tol >= small[2] and big[3] + tol >= small[3])

    edge_cut = []
    edge_kept = []
    if edge_cut_pt and vb_w > 0 and vb_h > 0:
        kept2 = []
        for item in deduped:
            if _edge_run(item[0]) < edge_cut_pt:
                kept2.append(item)
                continue
            bx0, by0, bx1, by1 = item[1]
            size_mm = [round((bx1 - bx0) * 25.4 / 72), round((by1 - by0) * 25.4 / 72)]
            has_full = any(o is not item and _contains(o[1], item[1]) and o[3] > item[3] * 1.02 for o in deduped)
            if has_full or not stroked.get(id(item[0]), False):
                edge_cut.append(size_mm)
            else:
                edge_kept.append(size_mm)
                kept2.append(item)
        if edge_cut:
            warnings.append(
                f"🟡 대지 경계에 잘린 조각 {len(edge_cut)}개를 뺐습니다(폭×높이 mm {edge_cut}). "
                "온전한 모양이 따로 없다면 원본 .ai 에서 대지를 넓혀 다시 저장해 주세요.")
        if edge_kept:
            warnings.append(
                f"🟡 대지 경계에 붙은 조각 {len(edge_kept)}개(폭×높이 mm {edge_kept})는 윤곽선이 있어 남겼습니다 — "
                "대지에서 잘린 것이면 원본 대지를 넓혀 다시 저장해 주세요.")
        deduped = kept2

    # ── 대지 밖 조각은 전체를 대지 안으로 옮긴다(2026-10-20) ──
    #    그레이더 출력 페이지는 좌하단 원점 + «가장 먼 조각까지» 라, 음수 좌표 조각은 잘린다
    #    (슈팅셔츠 M 뒤판 590mm 중 188mm 만 인쇄). 조각끼리의 상대 위치는 그대로 둔다.
    shifted = None
    if deduped:
        ux0 = min(bb[0] for _, bb, _, _ in deduped)
        uy0 = min(bb[1] for _, bb, _, _ in deduped)
        ux1 = max(bb[2] for _, bb, _, _ in deduped)
        uy1 = max(bb[3] for _, bb, _, _ in deduped)
        # parse_svg 는 viewBox 원점을 무시하고 y 를 «높이 − y» 로 뒤집는다 → 그 기준(x≥0 · 0≤y≤높이)으로 본다
        dx = (margin_pt - ux0) if ux0 < 0 else 0.0
        dy = (margin_pt - uy0) if uy0 < 0 else 0.0
        new_w = max(vb_w, ux1 + dx + (margin_pt if ux1 + dx > vb_w else 0.0))
        new_h = max(vb_h, uy1 + dy + (margin_pt if uy1 + dy > vb_h else 0.0))
        if dx or dy or new_w != vb_w or new_h != vb_h:
            deduped = [([(x + dx, y + dy) for x, y in pts], (bb[0] + dx, bb[1] + dy, bb[2] + dx, bb[3] + dy), per, ar)
                       for pts, bb, per, ar in deduped]
            vb_w, vb_h = new_w, new_h
            vb_str = f"0 0 {vb_w:g} {vb_h:g}"
            shifted = [round(dx, 2), round(dy, 2)]
            how = (f"전체를 {round(dx * 25.4 / 72)}·{round(dy * 25.4 / 72)}mm 옮기고 " if (dx or dy) else "")
            warnings.append(
                f"🟡 대지 밖에 놓인 조각이 있어 {how}대지를 {round(vb_w * 25.4 / 72)}×{round(vb_h * 25.4 / 72)}mm 로 넓혔습니다"
                "(조각끼리의 위치는 그대로).")

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
    for pts, bb, _, _ in deduped:
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
        "dropped_clip": dropped_clip,
        "dropped_edge_cut": edge_cut,
        "shifted": shifted,
        "has_curves": any_curves,
        "bboxes": bboxes,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5) 사이즈 단조성 가드 (이슈3 — 자산 결함 자동 탐지)
# ─────────────────────────────────────────────────────────────────────────────
#
# 왜 이 가드가 필요한가 (큰 그림):
#   이슈3에서 3XL.svg 가 5XL.svg 와 '조각 좌표 100% 동일'한 자산 결함이 있었다.
#   그런데 이 결함은 기존 6개 검증 신호(조각수3·viewBox통일·OOB없음·높이내림차순·
#   verify PASS·selftest PASS)를 전부 통과한다. 즉 "초록불인데 치수만 틀린" 함정이라,
#   사람 눈으로도 잡기 어렵고 결국 3XL 주문 선수에게 5XL 크기가 출고될 뻔했다.
#
#   ⇒ 이를 자동으로 잡는 유일한 방법은 '여러 사이즈를 함께 놓고 비교'하는 것이다.
#     비유하면 옷 사이즈표 검표기 — "3XL인데 5XL과 치수가 똑같다"는 모순을 잡아낸다.
#     (a) 인접/임의 두 사이즈의 조각 좌표가 100% 동일하면 → 같은 자산 복붙 의심(실패).
#     (b) 사이즈가 커질수록 조각 높이가 단조 증가해야 정상인데, 작아지거나 그대로면 경고.
#
# 불변 제약: 기존 함수는 일절 건드리지 않고 '추가'만 한다. parse_svg(pattern.py)를
#   읽기 전용으로 호출해 "엔진이 실제로 보는 조각"을 기준으로 비교한다(가장 신뢰도 높음).
def _piece_coord_hash(points: List[Point], *, ndigits: int = 2) -> str:
    """조각 윤곽 점열을 안정적인 해시 문자열로 만든다(좌표 비교용).

    왜 반올림: 부동소수 미세오차로 '사실상 동일'이 '다름'으로 오판되지 않게
    소수 ndigits 자리에서 반올림한 뒤 해시한다. 점 순서는 그대로 둔다
    (정규화된 SVG 는 같은 자산이면 점 순서까지 동일하므로 정렬 불필요).
    """
    import hashlib

    norm = ";".join(f"{round(x, ndigits)},{round(y, ndigits)}" for (x, y) in points)
    return hashlib.md5(norm.encode("utf-8")).hexdigest()[:8]


def check_size_monotonicity(svg_paths, *,
                            size_order=None,
                            piece_index=0,
                            fail_on_duplicate: bool = True):
    """여러 사이즈 SVG 의 조각 좌표를 비교해 '사이즈 단조성'을 점검한다.

    이슈3 자산 결함(3XL=5XL 동일 도형) 같은 "초록불인데 치수만 틀린" 함정을 잡는
    전용 가드. parse_svg(읽기 전용)로 각 SVG 의 조각을 읽어 다음 두 가지를 본다:

      (A) 좌표 동일 검출 : 서로 다른 두 사이즈의 piece_index 조각 좌표 해시가 같으면
          → 같은 자산을 복붙한 결함으로 본다(기본: 실패 신호).
      (B) 높이 단조 검출 : size_order 순으로 piece_index 조각의 높이가 단조 증가해야
          정상. 인접 사이즈에서 높이가 '동일'하거나 '감소'하면 경고(자산 의심).

    매개변수
      svg_paths        : {사이즈명: svg경로} dict  또는  [svg경로,...] 리스트.
                         리스트면 파일명(확장자 제외)을 사이즈명으로 쓴다.
      size_order       : 작은→큰 사이즈 이름 순서 리스트(예: ["5XS",...,"5XL"]).
                         None 이면 단조(높이) 검사는 건너뛰고 좌표 동일 검사만 한다.
      piece_index      : 비교 기준 조각 인덱스(parse_svg 순서). 0=가장 큰 조각(앞판).
                         None 이면 «모든 조각»을 함께 비교(등록 화면은 이것을 쓴다).
      fail_on_duplicate: True 면 좌표 동일 발견 시 passed=False(출고 차단용).

    반환(dict): {
      "passed"        : bool — (A)좌표동일 없음 + (fail_on_duplicate 일 때) 통과 여부,
      "checked"       : 검사한 사이즈 수,
      "duplicates"    : [(sizeA, sizeB), ...] 좌표 100% 동일한 사이즈 쌍,
      "non_monotonic" : [{"size","prev","height","prev_height","kind"}...] 단조 위반,
      "hashes"        : {사이즈명: 조각해시} (디버그/리포트용),
      "heights"       : {사이즈명: 조각높이},
      "warnings"      : [사람이 읽을 한글 경고/안내],
      "missing"       : [읽기 실패한 사이즈명],
    }

    parse_svg 는 pattern.py 의 것을 '여기서' 지연 import 한다(읽기 전용 호출 — 불변
    제약 위반 아님). engine 코어 코드를 수정하지 않는다.
    """
    # 지연 import (모듈 최상단 import 를 피해 svg_normalize 의 '표준라이브러리만' 원칙 유지).
    from .pattern import parse_svg

    # ── 입력 정규화: dict / list 둘 다 받아 {사이즈명: 경로} 로 통일 ──
    if isinstance(svg_paths, dict):
        path_map = dict(svg_paths)
    else:
        path_map = {}
        for p in svg_paths:
            base = os.path.basename(p)
            name = base[:-4] if base.lower().endswith(".svg") else base
            path_map[name] = p

    warnings: List[str] = []
    missing: List[str] = []
    hashes: dict = {}
    heights: dict = {}

    # ── 각 사이즈 SVG 를 parse_svg 로 읽어 piece_index 조각의 해시·높이를 모은다 ──
    for size_name, path in path_map.items():
        try:
            polys = parse_svg(path)  # 높이 내림차순 정렬된 Polyline 리스트
        except Exception as e:
            missing.append(size_name)
            warnings.append(f"🟡 [{size_name}] parse_svg 실패(가드 건너뜀): {e}")
            continue
        if not polys or (piece_index is not None and piece_index >= len(polys)):
            missing.append(size_name)
            warnings.append(
                f"🟡 [{size_name}] 조각 {piece_index} 없음(조각수 {len(polys)}) — 가드 건너뜀.")
            continue
        if piece_index is None:
            # (2026-10-20) 모든 조각을 함께 본다 — 한 조각(예전엔 0번 = 대지 테두리)만 같아도
            #   «복붙»으로 오판해 멀쩡한 사이즈를 껐다. 조각 전부가 같아야 진짜 복붙이다.
            hashes[size_name] = "|".join(_piece_coord_hash(p.points) for p in polys)
            heights[size_name] = round(polys[0].height, 2)
            continue
        poly = polys[piece_index]
        hashes[size_name] = _piece_coord_hash(poly.points)
        heights[size_name] = round(poly.height, 2)

    lab = "조각 전부" if piece_index is None else f"조각{piece_index}"
    # ── (A) 좌표 동일(=같은 자산 복붙) 검출: 서로 다른 사이즈인데 해시가 같으면 결함 ──
    duplicates: List[Tuple[str, str]] = []
    items = list(hashes.items())
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            na, ha = items[a]
            nb, hb = items[b]
            if ha == hb:
                duplicates.append((na, nb))
                warnings.append(
                    f"🔴 [{na}] 와(과) [{nb}] 의 {lab} 좌표가 100% 동일합니다 "
                    f"(해시 {ha}). 같은 자산을 복붙한 결함 의심 — 사이즈가 다른데 도형이 "
                    f"같으면 한쪽 사이즈로 오출고됩니다. 원본 .ai 재확보 후 재변환 필요.")

    # ── (B) 높이 단조 증가 검출: size_order 가 주어졌을 때만 ──
    non_monotonic: list = []
    if size_order:
        prev_name = None
        prev_h = None
        for sz in size_order:
            if sz not in heights:
                continue  # 비활성/누락 사이즈는 단조 검사에서 자연스럽게 건너뜀
            h = heights[sz]
            if prev_h is not None:
                if h < prev_h - 1e-6:
                    non_monotonic.append({
                        "size": sz, "prev": prev_name,
                        "height": h, "prev_height": prev_h, "kind": "감소"})
                    warnings.append(
                        f"🟡 [{sz}] {lab} 높이({h})가 더 작은 사이즈 "
                        f"[{prev_name}]({prev_h})보다 작습니다(단조 감소). 자산 순서 확인 필요.")
                elif abs(h - prev_h) <= 1e-6:
                    non_monotonic.append({
                        "size": sz, "prev": prev_name,
                        "height": h, "prev_height": prev_h, "kind": "동일"})
                    warnings.append(
                        f"🟡 [{sz}] {lab} 높이({h})가 인접 사이즈 "
                        f"[{prev_name}]와 동일합니다 — 사이즈 구분이 없습니다(자산 의심).")
            prev_name = sz
            prev_h = h

    passed = True
    if fail_on_duplicate and duplicates:
        passed = False

    return {
        "passed": passed,
        "checked": len(hashes),
        "duplicates": duplicates,
        "non_monotonic": non_monotonic,
        "hashes": hashes,
        "heights": heights,
        "warnings": warnings,
        "missing": missing,
    }
