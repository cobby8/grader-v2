# AAMA/ASTM 식 DXF + 규칙표(RUL) 내보내기 — 차용 명세서 F8 (2026-10-19) · F3 노치 6종 · F4 자르는 선·구멍 · F5 식서·라벨 · F6 뒤집기·접기
#
#   왜: 지금 내보내기(patlib.export)는 «사이즈마다 DXF 한 장» 이고 레이어만 AAMA 를 흉내 낸다.
#       공장 CAD(Gerber·Optitex·Lectra 등)는 «기준 사이즈 DXF 한 장 + 규칙표(RUL)» 를 받으면
#       우리 그레이딩을 그대로 불러와 사이즈를 다시 펼치고, 거기서 직접 고칠 수 있다.
#
#   만드는 것 (그룹 = 상의 / 하의 마다)
#     GAS_WARMUP_<TOP|BOTTOM>_<기준>.dxf       기준 사이즈만 — 조각 = BLOCK(+INSERT), 그레이드 점마다 «# 규칙번호»
#     GAS_WARMUP_<TOP|BOTTOM>.rul              규칙표 — 규칙마다 사이즈별 Δx,Δy (기준 사이즈 대비, mm)
#     GAS_WARMUP_<TOP|BOTTOM>_ALLSIZES.dxf     전 사이즈 겹친 묶음(graded nest) — RUL 을 못 읽는 CAD 용
#     GAS_WARMUP_<TOP|BOTTOM>_<기준>_1대1.pdf  기준 사이즈 1:1 — 노치 모양·자르는 선(빨강)·구멍 기호·식서 화살표·라벨 (tile_pdf.py 로 A4 분할)
#     aama_검산.json                            규칙을 기준에 적용해 다시 만든 점 ↔ 엔진 결과 어긋남(꺾인 점·곡선 점 따로)
#     (--check) 확인_F3-F6_1대1.pdf            노치 6종·자르는 선·구멍 4종·립 식서·접어 재단·라벨을 한 장에 (사람 확인용)
#
#   레이어 (ASTM D6673 / AAMA-292 — 공개 Gerber AccuMark 내보내기 5개·astm-parser 레이어 표와 맞춤)
#     1 경계(재단선 — 노치 뾰족점 없음)  2 꺾인 점  3 곡선 점  4 노치(V·일자)  6 접는 선(대칭축)  7 식서(조각에 그려진 식서선, 없을 때만 세로 기본)  8 안쪽선(그리기만)
#     11 안쪽 자르는 선(Internal cutouts)  13 구멍(점)  14 재봉선  15 글자(라벨·메모)  80 T 노치  81 성곽 노치  83 U 노치
#     규칙 번호 = 점과 같은 자리·같은 레이어의 TEXT "# n"     조각 속성 = 블록 안 레이어 1 TEXT (Piece Name · SIZE · Quantity · CATEGORY · ANNOTATION)
#
#   노치 표기 (notch_style) — 기본 "point"
#     point  재단선 «꼭짓점» 위 POINT + 각도(그룹 50 = 몸판 안쪽 방향, 도). 종류는 레이어(4 일자·V·다이아 / 80 T / 81 성곽 / 83 U)
#            근거: 공개 Gerber AccuMark AAMA 샘플 5개의 노치 75개가 «전부» 레이어 4 POINT 였고, 75개 모두 재단선 꼭짓점과 같은 자리였다.
#                  짧은 선(LINE) 노치는 0개. 노치 점이 재단선 꼭짓점이라 RUL 그레이딩을 그대로 따라간다(짧은 선은 규칙이 안 붙는다)
#     line   재단선에서 안쪽으로 짧은 선(notchshapes 모양 그대로 — 일자 5mm 1개는 예전 결과와 같다). CAD 가 아닌 뷰어로 볼 때
#     cut_in=True → V·U·성곽은 재단선 자체를 파낸다(레이어 1). 그 노치는 레이어 4/80~83 에 다시 넣지 않는다(이중 금지)
#
#   규칙 값은 «엔진이 실제로 움직인 양» 에서만 뽑는다(재계산·추측 없음):
#     같은 점 번호끼리 (사이즈 점 − 기준 점) 을 재고, 그 사이 점이 «길이 비율 배분» 으로 0.05mm 안에 다시 나오도록
#     그레이드 점을 고른다(꺾인 점은 항상 그레이드 점). 같은 이동량 묶음은 규칙 번호 하나를 같이 쓴다.
#
#   실행(저장소 루트): python tools/pattern-engine/aama.py [--graded <graded.json>] [--out <폴더>] [--sample 2XL]
#                      [--notch-style point|line] [--cut-in] [--fold 상의:뒤판 …] [--label 팀=… --label 주문번호=…] [--check]
#     graded.json = gas_warmup_grade.py 결과(기본 tmp/pattern-engine/gas-warmup/graded/graded.json)
#     🚫 라벨 값은 인자로만 받는다 — 운영 DB 를 읽지 않는다
import sys, os, json, math, argparse, datetime, copy, re
sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ezdxf
from shapely.geometry import Polygon, LineString, Point, box as sbox
from shapely.ops import polylabel
from patlib import expand                                  # 좌우 거울 펼치기(읽기만 — 기존 파일 안 고침)
from cardinal import tips
from gas_warmup_meta import SPEC_T, SPEC_B
from piecespec import from_legacy, clean_ring, spec_drills, fill_label, flip_rule, DEFAULT_LABEL
import notchshapes as NS

TOL_KNOT = 0.05          # 그레이드 점 사이를 «길이 비율 배분» 했을 때 허용 어긋남(mm)
TURN_DEG = 25.0          # 이 각도보다 꺾이면 꺾인 점(turn point) — cardinal.corners 와 같은 기준
TEXT_H = 5.0             # 조각 속성 글자 높이(mm)
RULE_H = 2.0             # 규칙 번호 글자 높이(mm)
SNAP_MM = 0.5            # 노치 점을 재단선 꼭짓점에 붙이는 거리 — OptiCad 원본 노치 바닥점이 0.02~0.17mm 안에 있다(2026-10-19 실측)

NOTCH_STYLES = ("point", "line")
NOTCH_STYLE = "point"    # 기본 — 위 머리말 «노치 표기» 근거
POINT_LAYER = {"slit": "4", "V": "4", "diamond": "4", "T": "80", "castle": "81", "U": "83"}   # ASTM D6673 노치 종류 레이어
# ⚠️ 다이아몬드는 ASTM 에 종류 레이어가 없다 → 점 표기에서는 레이어 4(일자·V)로 나간다. 모양까지 지키려면 line 표기 또는 cut_in
INTERNAL_CUT_LAYER = "11"   # ASTM «Internal cutouts». 레이어 1 에 넣으면 공장 CAD 가 경계 조각과 «이어 붙여» 한 고리로 읽는다
                            # (astm-parser: «boundary (fragments chained)») — 그래서 기본은 11, --cut-layer 1 로 바꿀 수 있다

# 조각 이름(영문 — R12 는 한글이 깨진다) · 분류(Category)
EN = {"뒤판": "BACK", "앞판": "FRONT", "소매": "SLEEVE", "소매중심덧방": "SLEEVE CENTER OVERLAY", "카우스": "CUFF RIB",
      "밑단립": "HEM RIB", "에리(립)": "COLLAR RIB", "앞주머니구찌": "POCKET ZIP FACING", "앞주머니감": "POCKET BAG",
      "앞옆배색": "FRONT SIDE PANEL SNAP", "뒤옆배색": "BACK SIDE PANEL SNAP MATE", "앞구찌": "POCKET ZIP FACING"}
CATEGORY = {"카우스": "RIB", "밑단립": "RIB", "에리(립)": "RIB", "앞주머니감": "POCKETING"}
GROUPS = {"top": ("TOP", SPEC_T), "bottom": ("BOTTOM", SPEC_B)}
GROUP_KO = {"top": "상의", "bottom": "하의"}
SIDE_EN = {"R": "RIGHT", "L": "LEFT"}
DRILL_EN = {"스냅": "SNAP", "짝": "SNAP MATE", "아일렛": "EYELET", "단추": "BUTTON"}
NOTCH_KO = {"slit": "일자", "T": "T", "V": "V", "U": "U", "diamond": "다이아몬드", "castle": "성곽"}


def _ascii(s):
    """DXF R12 용 — 영문·숫자·기본 기호만 남긴다(한글은 깨진다). «·» 는 «/»"""
    s = str(s or "").replace("·", "/")
    s = "".join(c if (c.isascii() and (c.isalnum() or c in " -_()/#.,+x")) else " " for c in s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"(?:\s*/\s*)+", " / ", s).strip(" /")


def _en(base):
    return EN.get(base) or _ascii(base).upper() or "PIECE"


# ════════ 기하 도우미 ════════
def _unit(v):
    m = math.hypot(*v); return (v[0] / m, v[1] / m) if m > 1e-12 else (0.0, 0.0)


def _cum(P, closed):
    """점마다 처음부터의 길이(닫힌 고리는 마지막 → 처음 변까지 더한 전체 길이도 돌려준다)"""
    s = [0.0]
    for i in range(1, len(P)): s.append(s[-1] + math.dist(P[i - 1], P[i]))
    total = s[-1] + (math.dist(P[-1], P[0]) if closed else 0.0)
    return s, total


def turn_points(P, closed):
    """꺾인 점 번호 — 앞뒤 변 방향이 TURN_DEG 넘게 바뀌는 점(0 길이 변은 건너 이웃을 본다). 열린 선은 양 끝 포함"""
    n = len(P); out = set()
    if not closed: out |= {0, n - 1}
    for i in range(n):
        if not closed and i in (0, n - 1): continue
        j = (i - 1) % n
        while math.dist(P[j], P[i]) < 1e-6 and j != i: j = (j - 1) % n
        k = (i + 1) % n
        while math.dist(P[k], P[i]) < 1e-6 and k != i: k = (k + 1) % n
        a = math.atan2(P[i][1] - P[j][1], P[i][0] - P[j][0]); b = math.atan2(P[k][1] - P[i][1], P[k][0] - P[i][0])
        if abs((math.degrees(b - a) + 180) % 360 - 180) > TURN_DEG: out.add(i)
    return out


def distribute(P, closed, knots, kdisp):
    """그레이드 점(knots)의 이동량만으로 나머지 점 이동량을 «길이 비율»로 나눈다 — 공장 CAD 의 비례 배분과 같은 생각"""
    n = len(P); s, total = _cum(P, closed); K = sorted(knots); out = [None] * n
    for k in K: out[k] = kdisp[k]
    pairs = list(zip(K, K[1:])) + ([(K[-1], K[0])] if closed else [])
    for a, b in pairs:
        L = (s[b] - s[a]) if b > a else (total - s[a] + s[b])          # 고리를 한 바퀴 넘는 구간
        i = (a + 1) % n
        while i != b:
            d = (s[i] - s[a]) if i > a else (total - s[a] + s[i])
            t = d / L if L > 1e-9 else 0.0
            out[i] = (kdisp[a][0] + (kdisp[b][0] - kdisp[a][0]) * t, kdisp[a][1] + (kdisp[b][1] - kdisp[a][1]) * t)
            i = (i + 1) % n
    return out


def pick_knots(P, closed, disp, must):
    """disp: {사이즈: [점마다 (dx,dy)]} — must(꺾인 점)에서 시작해, 비례 배분이 TOL_KNOT 를 넘는 가장 나쁜 점을 하나씩 더한다"""
    n = len(P); K = set(must) or {0}
    while True:
        worst, wi = 0.0, None
        for sz, D in disp.items():
            R = distribute(P, closed, K, {k: D[k] for k in K})
            for i in range(n):
                e = math.dist(R[i], D[i])
                if e > worst: worst, wi = e, i
        if worst <= TOL_KNOT or wi is None or wi in K: return sorted(K)
        K.add(wi)


def cyclic_match(A, B):
    """꼭짓점 목록 A(기준) ↔ B(사이즈) 를 같은 개수일 때 «시작점만 돌려» 맞춘다 — 거리 합이 가장 작은 돌림(돌린 번호 목록)"""
    n = len(A); best = min(range(n), key=lambda r: sum(math.dist(A[i], B[(i + r) % n]) for i in range(n)))
    return [(i + best) % n for i in range(n)]


def _at_fraction(P, closed, a, b, t):
    """선 P 의 a 번 점 → b 번 점 구간(앞으로, 고리면 한 바퀴 넘어도)에서 길이 비율 t 자리의 점"""
    n = len(P); idx = [a]
    while idx[-1] != b: idx.append((idx[-1] + 1) % n)
    seg = [math.dist(P[idx[k]], P[idx[k + 1]]) for k in range(len(idx) - 1)]
    goal = t * sum(seg); s = 0.0
    for k, L in enumerate(seg):
        if s + L >= goal - 1e-12 and L > 0:
            u = (goal - s) / L; p, q = P[idx[k]], P[idx[k + 1]]
            return (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
        s += L
    return P[b]


# ── 닫힌 고리(재단선) 위 길이 좌표 ──
def _ring_project(R, q):
    """고리 R 위에서 q 에 가장 가까운 점 → (길이 좌표 s, 변 번호 i, 그 점)"""
    best = None; s0 = 0.0; n = len(R)
    for i in range(n):
        a, b = R[i], R[(i + 1) % n]; L = math.dist(a, b)
        t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / (L * L)))
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t); d = math.dist(p, q)
        if best is None or d < best[0]: best = (d, s0 + t * L, i, p)
        s0 += L
    return best[1], best[2], best[3]


def _ring_at(R, s):
    """고리 R 의 길이 좌표 s(한 바퀴 넘으면 돌린다) 자리의 점"""
    _, tot = _cum(R, True); s %= tot; acc = 0.0; n = len(R)
    for i in range(n):
        a, b = R[i], R[(i + 1) % n]; L = math.dist(a, b)
        if acc + L >= s and L > 0:
            u = (s - acc) / L; return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        acc += L
    return R[0]


def _ring_insert(R, q, snap=SNAP_MM):
    """q 를 고리 R 의 꼭짓점으로 — snap 안에 꼭짓점이 있으면 그 점, 없으면 가장 가까운 변 위에 새 점을 끼운다 → (새 고리, 그 점)"""
    v = min(R, key=lambda p: math.dist(p, q))
    if math.dist(v, q) <= snap: return R, v
    _, i, p = _ring_project(R, q)
    if math.dist(p, R[i]) < 1e-6: return R, R[i]
    if math.dist(p, R[(i + 1) % len(R)]) < 1e-6: return R, R[(i + 1) % len(R)]
    return R[: i + 1] + [p] + R[i + 1:], p


def _carve(R, path):
    """재단선 R 을 노치 꺾은선 path(양끝 = 재단선 위, 가운데 = 안쪽)로 파낸다 — V·U·성곽. 원래 첫 점 순서를 지킨다"""
    _, tot = _cum(R, True); cum, _ = _cum(R, True)
    s0, _, p0 = _ring_project(R, path[0]); s1, _, p1 = _ring_project(R, path[-1])
    if (s1 - s0) % tot > tot / 2:                            # 고리 방향으로 path[0] → path[-1] 이 짧은 쪽이 되게
        path = path[::-1]; s0, s1, p0, p1 = s1, s0, p1, p0
    span = (s0 - s1) % tot                                    # s1 → (남는 쪽) → s0
    kept = [(((cum[i] - s1) % tot), i) for i in range(len(R)) if 1e-9 < (cum[i] - s1) % tot < span - 1e-9]
    kept.sort(); seq = [i for _, i in kept]
    out = [R[i] for i in seq] + [p0] + [tuple(v) for v in path[1:-1]] + [p1]
    if seq:                                                   # 원래 번호가 가장 작은 남은 점부터 — 사이즈마다 같은 순서
        r = out.index(R[min(seq)]); out = out[r:] + out[:r]
    return out


# ── 접어 재단(F6) — 대칭축 한쪽만 ──
def _sym_axis(P):
    """세로 대칭축 x — 좌우 끝의 가운데. 거울로 뒤집어 1mm 넘게 어긋나면 대칭이 아니다(오류)"""
    xs = [q[0] for q in P]; ax = (min(xs) + max(xs)) / 2
    a = Polygon(P).exterior; b = Polygon([(2 * ax - x, y) for x, y in P]).exterior
    h = a.hausdorff_distance(b)
    if h > 1.0: raise ValueError(f"좌우 대칭이 아니라 접어 재단할 수 없다(거울 어긋남 {h:.2f}mm)")
    return ax


def _half_ring(R, ax, keep):
    """고리 R 에서 keep·(x−ax) ≥ 0 쪽만 — 축과 만나는 점을 넣고, 축 위 가장 위 점에서 시작(사이즈마다 같은 순서)"""
    f = lambda q: keep * (q[0] - ax); out = []; n = len(R)
    for i in range(n):
        a, b = R[i], R[(i + 1) % n]; fa, fb = f(a), f(b)
        if fa >= -1e-9: out.append((ax, a[1]) if abs(fa) <= 1e-9 else a)
        if (fa > 1e-9 and fb < -1e-9) or (fa < -1e-9 and fb > 1e-9):
            t = fa / (fa - fb); out.append((ax, a[1] + (b[1] - a[1]) * t))
    ded = []
    for q in out:
        if not ded or math.dist(ded[-1], q) > 1e-6: ded.append(q)
    if len(ded) > 2 and math.dist(ded[0], ded[-1]) < 1e-6: ded.pop()
    on = [i for i, q in enumerate(ded) if abs(q[0] - ax) < 1e-6]
    if len(on) < 2: raise ValueError("접는 선이 재단선과 두 번 만나지 않는다")
    r = max(on, key=lambda i: ded[i][1]); ded = ded[r:] + ded[:r]
    return ded, [(ax, min(ded[i][1] for i in range(len(ded)) if abs(ded[i][0] - ax) < 1e-6)), (ax, ded[0][1])]


def _half_line(P, closed, ax, keep):
    """안쪽선을 남길 쪽으로 자른다 — 조각 목록(닫힌 것은 닫힌 채로, 걸치면 잘린 고리)"""
    half = sbox(ax, -1e6, ax + 1e6, 1e6) if keep > 0 else sbox(ax - 1e6, -1e6, ax, 1e6)
    if all(keep * (q[0] - ax) >= -1e-6 for q in P): return [(list(P), closed)]
    if all(keep * (q[0] - ax) <= 1e-6 for q in P): return []
    g = (Polygon(P).buffer(0) if closed and len(P) > 2 else LineString(P)).intersection(half)
    parts = list(getattr(g, "geoms", [g]))
    if closed: return [(list(x.exterior.coords)[:-1], True) for x in parts if x.geom_type == "Polygon" and x.area > 1e-6]
    return [(list(x.coords), False) for x in parts if x.geom_type == "LineString" and x.length > 1e-6]


# ════════ 엔진 조각(옛 형식) + 명세 → AAMA 조각 ════════
GRAIN_TILT = 3.0             # 세로에서 기운 각도 한도(도)
GRAIN_INSET = 5.0            # 식서 두 끝이 재봉선 안쪽으로 이만큼 이상(mm) — 덧방 위치선·구찌 선·바지 보조선은 재봉선에 «닿는다»(0mm)
GRAIN_MIN = 20.0             # 이보다 짧으면 식서가 아니다(스냅 자리 표시 10mm 선 등)


def find_grain(p, internal=None):
    """식서선 찾기 → 안쪽선 번호 또는 None.
       OptiCad 원본 식서선은 DRAW 레이어의 «대문자 L 로 끝나는 세로선»(다른 안쪽선은 소문자 l)인데 opticad.parse 가 L/l 을 합쳐
       표시가 옛 형식까지 오지 않는다. 엔진이 새로 그린 조각(립·상의 주머니감·에리)은 «# 식서» 로 세로선을 직접 그린다.
       둘 다 같은 모양 규칙으로 찾는다 — 사이즈에 영향받지 않게 «길이 비율» 은 쓰지 않는다:
         열린 두 점 선 · 세로(3° 안) · 길이 20mm 이상 · 두 끝이 재봉선 안쪽 5mm 이상(재봉선에 닿는 보조선 제외).
       여럿이면 가장 긴 것. (실측 2026-10-19 가스 9벌 × 31조각: 조각마다 정확히 하나 — 식서 안쪽 거리 15~174mm, 보조선 0mm)"""
    sew = Polygon(clean_ring(p["sew"])).buffer(0); ext = sew.exterior
    best = None
    for j, d in enumerate(internal if internal is not None else p["draw"]):
        P = d.get("pts") or []
        if d.get("snap") or d.get("closed") or d.get("cut") or len(P) != 2: continue
        L = math.dist(P[0], P[1])
        if L < GRAIN_MIN: continue
        tilt = math.degrees(math.atan2(abs(P[1][0] - P[0][0]), abs(P[1][1] - P[0][1])))
        if tilt >= GRAIN_TILT: continue
        if not all(sew.contains(Point(q)) and ext.distance(Point(q)) >= GRAIN_INSET for q in P): continue
        if best is None or L > best[0]: best = (L, j)
    return None if best is None else best[1]


def _grain_off_fold(grain, sew_half, ax, keep):
    """접어 재단 — 식서가 접는 선 바로 위에 있으면(공장이 못 본다) 반쪽 안쪽으로 평행이동. 두 끝이 재봉선 안쪽 5mm 이상인 자리"""
    if not grain or max(abs(q[0] - ax) for q in grain) > 1.0: return grain
    poly = Polygon(sew_half).buffer(0); ext = poly.exterior; xs = [q[0] for q in sew_half]
    far = max(xs) if keep > 0 else min(xs)
    for f in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2):
        x = ax + (far - ax) * f; g = [(x, q[1]) for q in grain]
        if all(poly.contains(Point(q)) and ext.distance(Point(q)) >= GRAIN_INSET for q in g): return g
    return grain


def _sew_keep(sew):
    """재봉선에서 노치 뾰족점과 «되돌아온 점»을 뺀 점 번호 — 노치는 따로 레이어 4 로 낸다"""
    T = tips(sew); n = len(sew); R = {(i + 1) % n for i in T}
    return [i for i in range(n) if i not in T and i not in R], sorted(T)


def notch_sites(p, spec, ring):
    """노치마다 {"p": 재단선 위 점, "w": 몸판 안쪽 단위벡터, type·depth·count·width·gap·angle}
       재봉선 노치(명세 seam[k].notch) — 바닥점에서 바깥으로 쏜 선이 «뾰족점 뺀» 재단선과 만나는 점
         (예전에는 뾰족점이 남은 재단선과 만나 10곳이 재단선 5mm 안쪽에서 시작했다 — 2026-10-19 고침)
       따로 그린 노치 선(옛 형식 notch — 립·덧방) — 그 선 그대로 일자"""
    sites = []; poly = Polygon(p["sew"]).buffer(0); ext = Polygon(ring).exterior
    for s in spec["seam"]:
        nt = s.get("notch")
        if not nt: continue
        b = (s["x"], s["y"]); u = tuple(nt["dir"])
        if poly.contains(Point(b[0] + u[0] * 0.5, b[1] + u[1] * 0.5)): u = (-u[0], -u[1])   # u = 바깥(재단선) 쪽
        hit = LineString([b, (b[0] + u[0] * 40, b[1] + u[1] * 40)]).intersection(ext)
        pts = [hit] if hit.geom_type == "Point" else [g for g in getattr(hit, "geoms", []) if g.geom_type == "Point"]
        if pts:
            c = min(pts, key=lambda q: q.distance(Point(b))); c = (c.x, c.y)
        else:                                                # 바깥 방향 선이 재단선과 안 만나면 가장 가까운 재단선 위 점
            q = ext.interpolate(ext.project(Point(b))); c = (q.x, q.y)
        sites.append({"p": c, "w": (-u[0], -u[1]), "type": nt.get("type", "slit"), "depth": float(nt["depth"]),
                      "count": nt.get("count", 1), "width": nt.get("width", NS.WIDTH), "gap": nt.get("gap", NS.GAP), "angle": nt.get("angle")})
    for a, b in spec.get("notch_lines") or []:
        a, b = tuple(a), tuple(b); d = math.dist(a, b)
        sites.append({"p": a, "w": _unit((b[0] - a[0], b[1] - a[1])), "type": "slit", "depth": d, "count": 1,
                      "width": NS.WIDTH, "gap": NS.GAP, "angle": None, "end": b})
    return sites


def _site_paths(st):
    """노치 하나의 모양(꺾은선 목록) — 일자 1개는 예전과 똑같은 선(재단선 점 → 안쪽 depth)"""
    if st["type"] == "slit" and st["count"] == 1 and not st.get("angle"):
        return [[st["p"], st.get("end") or (st["p"][0] + st["w"][0] * st["depth"], st["p"][1] + st["w"][1] * st["depth"])]]
    w = st["w"]
    return NS.notch_paths(st["p"], w, (w[1], -w[0]), st["type"], st["depth"], st["width"], st["count"], st["gap"], angle=st.get("angle"))


def to_aama(p, spec=None, notch_style=NOTCH_STYLE, cut_in=False, internal_cut_layer=INTERNAL_CUT_LAYER):
    """옛 형식 조각(+ 명세 속성) → {"lines": [(레이어, 점들, 닫힘?)], "drills", "drill_kinds", "notches"(짧은 선/꺾은선),
       "notch_points"[(레이어, 점, 각도)], "shapes"(PDF 용 노치 모양), "carved", "mirror"(접는 선), "flip", "on_fold"} (엔진 좌표 그대로)"""
    if notch_style not in NOTCH_STYLES: raise ValueError(f"노치 표기 {notch_style!r} — {NOTCH_STYLES}")
    spec = spec if spec is not None else from_legacy(p)
    ring = [tuple(v) for v in clean_ring(p["cut"])]                         # ① 재단선에서 노치 뾰족점 빼기 — 노치는 따로
    keep, _T = _sew_keep(p["sew"]); sew = [tuple(p["sew"][i]) for i in keep]
    sites = notch_sites(p, spec, ring)
    internal = [(d, j) for j, d in enumerate(spec.get("internal") or p["draw"])]
    gj = find_grain(p, [d for d, _ in internal])                            # 식서선(원본·엔진이 그린 것) — 레이어 8 → 7
    grain = [tuple(v) for v in internal[gj][0]["pts"]] if gj is not None else None
    if gj is not None: internal = [(d, j) for d, j in internal if j != gj]
    drills = spec_drills(spec)
    rib_fold = [tuple(v) for v in p["fold"]] if p.get("fold") else None
    mirror = None; fold = spec.get("cut_on_fold")
    if fold:                                                                # F6 접어 재단 — 반쪽만, 대칭축 = 접는 선(레이어 6)
        keep_s = -1 if isinstance(fold, dict) and fold.get("keep") == "-" else 1
        ax = _sym_axis(sew)
        ring, mirror = _half_ring(ring, ax, keep_s); sew, _ = _half_ring(sew, ax, keep_s)
        sites = [st for st in sites if keep_s * (st["p"][0] - ax) >= -1e-6]
        drills = [d for d in drills if keep_s * (d["pt"][0] - ax) >= -1e-6]
        internal = [(dict(d, pts=P2, closed=c2), j) for d, j in internal if not d.get("snap")
                    for P2, c2 in _half_line(d["pts"], bool(d["closed"]), ax, keep_s)]
        if rib_fold:
            parts = _half_line(rib_fold, False, ax, keep_s); rib_fold = parts[0][0] if parts else None
        if grain:
            parts = _half_line(grain, False, ax, keep_s); grain = [tuple(v) for v in parts[0][0]] if parts else None
            grain = _grain_off_fold(grain, sew, ax, keep_s)                # 접는 선 위 식서 → 반쪽 안쪽으로
    shapes, notches, npts, carved = [], [], [], []
    for st in sites:                                                        # ② 노치 — 파낼 것 먼저(재단선이 바뀐다)
        paths = _site_paths(st)
        if cut_in and st["type"] in NS.OPEN_TYPES:
            for path in paths: ring = _carve(ring, path)
            carved.append(st["type"]); continue
        shapes.append({"type": st["type"], "paths": paths, "p": st["p"], "w": st["w"]})
        if notch_style == "line": notches += paths
    if notch_style == "point":                                              # ③ 점 표기 — 노치 자리를 재단선 꼭짓점으로
        for sh in shapes:
            st = next(s for s in sites if s["p"] is sh["p"])
            s0, _, _ = _ring_project(ring, st["p"]); ang = round(math.degrees(math.atan2(st["w"][1], st["w"][0])), 4)
            for k in range(st["count"]):
                off = (k - (st["count"] - 1) / 2) * st["gap"]
                ring, q = _ring_insert(ring, _ring_at(ring, s0 + off) if off else st["p"])
                npts.append((POINT_LAYER[st["type"]], q, ang))
    lines = [("1", ring, True), ("14", sew, True)]
    for d, j in internal:
        if d.get("snap"): continue                                          # 스냅 동그라미 = 구멍 점 하나(레이어 13)
        lines.append((internal_cut_layer if d.get("cut") else "8", [tuple(v) for v in d["pts"]], bool(d["closed"])))
    if rib_fold: lines.append(("8", rib_fold, False))                       # 접는 선(2겹 립) — 안쪽선
    return {"lines": lines, "drills": [tuple(d["pt"]) for d in drills], "drill_kinds": [d["kind"] for d in drills],
            "notches": notches, "notch_points": npts, "shapes": shapes, "carved": carved, "mirror": mirror,
            "on_fold": bool(fold), "notch_style": notch_style, "grain": grain}


def _match_lines(base, size):
    """기준 조각의 선마다 사이즈 조각의 같은 선(점 개수 같음)을 찾는다 — 순서가 같으면 그대로, 아니면 가장 가까운 것"""
    out = []; used = set()
    same = [(L, len(P), c) for L, P, c in base["lines"]] == [(L, len(P), c) for L, P, c in size["lines"]]
    for k, (L, P, c) in enumerate(base["lines"]):
        if same: out.append(size["lines"][k][1]); continue
        cand = [j for j, (L2, P2, c2) in enumerate(size["lines"]) if L2 == L and len(P2) == len(P) and c2 == c and j not in used]
        if not cand: out.append(None); continue
        j = min(cand, key=lambda j: sum(math.dist(a, b) for a, b in zip(P, size["lines"][j][1])))
        used.add(j); out.append(size["lines"][j][1])
    return out


def grade_points(base, sizes, sample):
    """조각 하나의 그레이드 점과 사이즈별 이동량.
       돌려주는 값: 선마다 {"knots": [번호], "turn": set, "disp": {번호: {사이즈: (dx,dy)}}, "mode": "index"|"corner"}
                   + 구멍마다 {사이즈: (dx,dy)}"""
    res = []
    matched = {s: _match_lines(base, g) for s, g in sizes.items()}
    for k, (L, P, closed) in enumerate(base["lines"]):
        turn = turn_points(P, closed)
        if all(matched[s][k] is not None for s in sizes):      # 점 번호가 사이즈마다 같다 → 점마다 실제 이동량
            D = {s: [(q[0] - p[0], q[1] - p[1]) for p, q in zip(P, matched[s][k])] for s in sizes}
            knots = pick_knots(P, closed, D, turn)
            res.append({"knots": knots, "turn": turn, "mode": "index", "disp": {i: {s: D[s][i] for s in sizes} for i in knots}})
            continue
        # 점 개수가 사이즈마다 다르다(교차로 다시 만든 조각 — 소매중심덧방) → 꺾인 점끼리 맞추고,
        # 그 사이 점은 «꺾인 점 사이 길이 비율이 같은 자리»의 사이즈 선 위 점으로 대응시켜 이동량을 잰다(엔진 선 위의 점만 쓴다)
        cand = {s: [(L2, P2, c2) for L2, P2, c2 in sizes[s]["lines"] if L2 == L and c2 == closed] for s in sizes}
        TK = sorted(turn); BK = [P[i] for i in TK]; D = {}; MT = {}
        if len(TK) < 2: raise ValueError(f"꺾인 점이 둘 미만이라 맞출 수 없다 (레이어 {L})")
        for s in sizes:
            best = None
            for L2, P2, c2 in cand[s]:
                tp = sorted(turn_points(P2, c2))
                if len(tp) != len(BK): continue
                rot = cyclic_match(BK, [P2[i] for i in tp]) if closed else list(range(len(tp)))
                M = [tp[j] for j in rot]
                err = sum(math.dist(BK[k], P2[M[k]]) for k in range(len(BK)))
                if best is None or err < best[0]: best = (err, P2, M)
            if best is None: raise ValueError(f"꺾인 점 개수가 사이즈 {s} 에서 달라 맞출 수 없다 (레이어 {L})")
            _, P2, M = best; s_cum, s_tot = _cum(P, closed); Dsz = [None] * len(P)
            MT[s] = (P2, {TK[k]: P2[M[k]] for k in range(len(TK))})       # 검산용 — 꺾인 점이 맞은 엔진 꼭짓점
            pairs = list(zip(range(len(TK)), range(1, len(TK)))) + ([(len(TK) - 1, 0)] if closed else [])
            for ka, kb in pairs:
                a, b = TK[ka], TK[kb]; La = (s_cum[b] - s_cum[a]) if b > a else (s_tot - s_cum[a] + s_cum[b])
                i = a
                while True:
                    d = (s_cum[i] - s_cum[a]) if i >= a else (s_tot - s_cum[a] + s_cum[i])
                    q = _at_fraction(P2, closed, M[ka], M[kb], d / La if La > 1e-9 else 0.0)
                    Dsz[i] = (q[0] - P[i][0], q[1] - P[i][1])
                    if i == b: break
                    i = (i + 1) % len(P)
            D[s] = Dsz
        knots = pick_knots(P, closed, D, turn)
        res.append({"knots": knots, "turn": turn, "mode": "corner", "disp": {i: {s: D[s][i] for s in sizes} for i in knots}, "matched": MT})
    drills = []
    for j, d in enumerate(base["drills"]):
        drills.append({s: (sizes[s]["drills"][j][0] - d[0], sizes[s]["drills"][j][1] - d[1]) for s in sizes})
    return res, drills


# ════════ 규칙표 ════════
class Rules:
    """같은 이동량 묶음(사이즈 순서대로 0.01mm 반올림)은 같은 규칙 번호 — 0번 = 움직이지 않는 점"""
    def __init__(self, sizes):
        self.sizes = sizes; self.table = {}; self.order = []
        self.add({s: (0.0, 0.0) for s in sizes})

    def key(self, d):
        return tuple((round(d[s][0], 2) + 0.0, round(d[s][1], 2) + 0.0) for s in self.sizes)

    def add(self, d):
        key = self.key(d)
        if key not in self.table:
            self.table[key] = len(self.order); self.order.append(key)
        return self.table[key]

    def write(self, path, name, sample, when):
        L = ["ASTM/D13Proposal 1 Version: D 6673-04", "AUTHOR: STIZ", "PRODUCT: STIZ PATTERN ENGINE", "VERSION: 2026-10-19",
             f"CREATION DATE: {when:%d-%m-%Y}", f"CREATION TIME: {when:%H:%M}", "UNITS: METRIC", f"GRADE RULE TABLE: {name}",
             f"NUMBER OF SIZES: {len(self.sizes)}", "SIZE LIST: " + " ".join(self.sizes), f"SAMPLE SIZE: {sample}"]
        for n, key in enumerate(self.order):
            L.append(f"RULE: DELTA {n}")
            pairs = [f"{dx:10.2f},{dy:9.2f}" for dx, dy in key]
            for i in range(0, len(pairs), 4): L.append("".join(pairs[i:i + 4]))      # 한 줄에 네 사이즈(Gerber 내보내기와 같은 꼴)
        L.append("END")
        with open(path, "w", encoding="ascii", newline="\r\n") as f: f.write("\n".join(L) + "\n")


# ════════ 식서·라벨 ════════
def _block_name(n, base, size):
    suf = n.split(" ")[-1] if " " in n else ""
    return (_en(base) + ("_" + suf if suf else "")).replace(" ", "_") + "_" + size


def _grain(sew_local, anchor):
    """식서 기본 — «세로»(패턴 그린 방향 = 원단 길이 방향). 이름표 자리 세로선의 가운데 60%"""
    poly = Polygon(sew_local).buffer(0)
    seg = LineString([(anchor[0], -1e5), (anchor[0], 1e5)]).intersection(poly)
    segs = [seg] if seg.geom_type == "LineString" else list(getattr(seg, "geoms", []))
    segs = [g for g in segs if g.geom_type == "LineString" and g.length > 1]
    if not segs: return None
    g = max(segs, key=lambda g: g.length); (x, y0), (_, y1) = g.coords[0], g.coords[-1]
    lo, hi = min(y0, y1), max(y0, y1); m = (hi - lo) * 0.2
    return [(x, lo + m), (x, hi - m)]


def grain_of(spec, sew_local, anchor, loc, orig=None):
    """F5 식서 — ① 명세 grain{from,to} ② 조각에 그려진 식서선(orig — OptiCad 원본 또는 엔진 «# 식서», 엔진 좌표) ③ 없을 때만 세로 기본.
       → (선, 화살표, 립?, 출처)"""
    g = spec.get("grain") or {}
    if g.get("from"): line, src = loc([tuple(g["from"]), tuple(g["to"])]), "명세"
    elif orig: line, src = loc(orig), "식서선"
    else: line, src = _grain(sew_local, anchor), "세로(기본)"
    return line, g.get("arrow", "both"), bool(g.get("rib")), src


def label_values(base, size, qty, side, values=None, en=False):
    """라벨 자리표시자 값 — 조각·사이즈·장수·좌우는 조각에서, 원단·색·팀·주문번호는 부르는 쪽(인자)에서"""
    v = {"조각": _en(base) if en else base, "사이즈": size, "장수": qty, "좌우": side}
    v.update({k: x for k, x in (values or {}).items() if k not in v or x})
    return v


def _texts(blk, at, rows, layer="1", h=TEXT_H):
    for i, t in enumerate(rows):
        blk.add_text(t, dxfattribs={"layer": layer, "height": h}).set_placement(
            (at[0], at[1] - i * h * 1.6), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)


def _write_shape(blk, path, layer):
    """노치 꺾은선 — 두 점이면 LINE(예전과 같음), 그보다 많으면 열린 POLYLINE"""
    if len(path) == 2: blk.add_line(*path, dxfattribs={"layer": layer})
    else: blk.add_polyline2d(path, close=False, dxfattribs={"layer": layer})


def _write_piece(blk, Gl, notch_layer="4"):
    """선(레이어 1·14·8·11)·노치·구멍·접는 선 — 기준 블록과 전 사이즈 블록이 같이 쓴다(규칙 번호·점 종류는 기준 블록만)"""
    for path in Gl["notches"]: _write_shape(blk, path, notch_layer)
    for lay, q, ang in Gl["notch_points"]:
        blk.add_point(q, dxfattribs={"layer": lay, "angle": ang})
    if Gl.get("mirror"): blk.add_line(*Gl["mirror"], dxfattribs={"layer": "6"})


def _localize(G, loc):
    """조각 좌표로 옮긴 사본(선·노치·구멍·접는 선·노치 모양)"""
    out = dict(G)
    out["lines"] = [(L, loc(P), c) for L, P, c in G["lines"]]
    out["drills"] = loc(G["drills"]) if G["drills"] else []
    out["notches"] = [loc(p) for p in G["notches"]]
    out["notch_points"] = [(L, loc([q])[0], a) for L, q, a in G["notch_points"]]
    out["shapes"] = [dict(s, paths=[loc(p) for p in s["paths"]], p=loc([s["p"]])[0]) for s in G["shapes"]]
    out["mirror"] = loc(G["mirror"]) if G.get("mirror") else None
    return out


def _check_err(P, closed, gi, sizes, s, kd, Q_index, cands):
    """규칙만으로 다시 만든 선 ↔ 엔진 선 — 꺾인 점·곡선 점·모든 점·모양을 «따로» 잰다(정직한 검산)
       index 모드: 같은 번호 엔진 점과 거리.  corner 모드(사이즈마다 점 수가 다른 선): 엔진에는 «같은 번호 점» 이 없다 —
         꺾인 점은 맞춘 엔진 꼭짓점과의 거리, 곡선 점은 엔진 선까지의 거리(선 위에 있나), 모양은 하우스도르프"""
    R = distribute(P, closed, gi["knots"], kd); rec = [(P[i][0] + R[i][0], P[i][1] + R[i][1]) for i in range(len(P))]
    out = {"turn": 0.0, "curve": 0.0, "all": None, "shape": None}
    if gi["mode"] == "index":
        for i in gi["knots"]:
            k = "turn" if i in gi["turn"] else "curve"; out[k] = max(out[k], math.dist(rec[i], Q_index[i]))
        out["all"] = max(math.dist(rec[i], Q_index[i]) for i in range(len(P)))
        return out
    P2, tmap = gi["matched"][s]
    mk = (lambda q: Polygon(q).exterior) if closed else LineString
    eng = mk(P2)
    for i in gi["knots"]:
        if i in gi["turn"]: out["turn"] = max(out["turn"], math.dist(rec[i], tmap[i]))
        else: out["curve"] = max(out["curve"], eng.distance(Point(rec[i])))
    out["shape"] = min(mk(rec).hausdorff_distance(mk(Q)) for Q in cands)
    return out


GROUP_ALIAS = {"상의": "top", "top": "top", "하의": "bottom", "bottom": "bottom"}


def fold_targets(fold, grp, pieces, style=""):
    """--fold 값 → 이 그룹에서 접어 재단할 원본 이름 집합.
       «상의:뒤판» 처럼 옷을 적으면 그 옷만 — 대칭이 아니면 오류(분명히 시킨 것이라 조용히 넘기지 않는다).
       이름만(«뒤판») 주면 상의·하의 어디든 «좌우 대칭인 조각» 에만 — 대칭이 아니면 경고만 하고 건너뛴다
       (가스: 상의 뒤판 = 대칭 → 접음 · 하의 뒤판 = 다리 한 짝이라 비대칭 → 건너뜀)"""
    out = set()
    for item in fold or ():
        g, _, name = item.rpartition(":")
        if g and GROUP_ALIAS.get(g.strip()) is None: raise ValueError(f"--fold 옷 구분 {g!r} — 상의·하의(top·bottom)")
        if g and GROUP_ALIAS[g.strip()] != grp: continue
        name = name.strip()
        if name not in pieces:
            if g: raise ValueError(f"--fold {item!r}: {style} 에 «{name}» 조각이 없다")
            continue
        try:
            _sym_axis([tuple(v) for v in clean_ring(pieces[name]["sew"])]); out.add(name)
        except ValueError as e:
            if g: raise ValueError(f"--fold {item!r}: {e}")
            print(f"⚠️ --fold {name}: {style} 의 «{name}» 은 {e} — 건너뜀", file=sys.stderr)
    return out


def export_group(graded, grp, sample, out, when, notch_style=NOTCH_STYLE, cut_in=False, internal_cut_layer=INTERNAL_CUT_LAYER,
                 fold=(), decorate=None, label=None, label_en=None, spec_table=None, style=None, pdf=True):
    """그룹(상의/하의) 하나 → 기준 DXF · RUL · 전 사이즈 DXF · 1:1 PDF · 검산 수치
       decorate(grp, 원본이름, 명세, 좌우) — 명세에 F4~F6 값을 붙이는 함수(가스 = gas_warmup_spec.decorate)
       fold — 접어 재단할 조각(«뒤판» 또는 «상의:뒤판», fold_targets) · label / label_en — 라벨 값(PDF 한글 / DXF 영문, 없으면 한글 값에서 영문만 남긴다)"""
    tag, spec_t = GROUPS[grp] if spec_table is None else (grp.upper(), spec_table)
    style = style or f"GAS_WARMUP_{tag}"; sizes = list(graded)
    inst = {s: expand(graded[s][grp], spec_t) for s in sizes}
    names = sorted(inst[sample], key=lambda n: (-(max(v[1] for v in inst[sample][n][0]["cut"]) - min(v[1] for v in inst[sample][n][0]["cut"])), n))
    qty = {}
    for n in names:
        _, b, sd, _ = inst[sample][n]; qty[(b, sd)] = qty.get((b, sd), 0) + 1   # 라벨 «장수» — 같은 원본·같은 좌우 장 수

    fold_bases = fold_targets(fold, grp, {inst[sample][n][1]: inst[sample][n][0] for n in names}, style)

    def spec_of(s, n):
        p, base, side, _ = inst[s][n]; sp = from_legacy(p)
        if decorate: decorate(grp, base, sp, side)
        if base in fold_bases: sp["cut_on_fold"] = True
        return sp
    SP = {s: {n: spec_of(s, n) for n in names} for s in sizes}
    rules = Rules(sizes)
    A = {s: {n: to_aama(inst[s][n][0], SP[s][n], notch_style, cut_in, internal_cut_layer) for n in names} for s in sizes}
    # 조각 좌표 = 엔진 좌표 − 기준 사이즈 재단선 왼쪽 아래(모든 사이즈 같은 원점 → 규칙 Δ 가 그대로 맞는다)
    origin = {n: (min(v[0] for v in A[sample][n]["lines"][0][1]), min(v[1] for v in A[sample][n]["lines"][0][1])) for n in names}
    locf = lambda n: (lambda pts: [(x - origin[n][0], y - origin[n][1]) for x, y in pts])
    # 배치 — 모든 사이즈를 겹쳐도 이웃 조각과 안 겹치게 사이즈 합친 상자로 줄 세운다
    boxes = {}
    for n in names:
        allp = [q for s in sizes for q in locf(n)(A[s][n]["lines"][0][1])]
        boxes[n] = (min(q[0] for q in allp), min(q[1] for q in allp), max(q[0] for q in allp), max(q[1] for q in allp))
    GAP, SHEET_W = 40, 1800; place, x, y, rowh = {}, GAP, -GAP, 0
    for n in names:
        x0, y0, x1, y1 = boxes[n]; w, h = x1 - x0, y1 - y0
        if x + w > SHEET_W - GAP and x > GAP: x, y, rowh = GAP, y - rowh - GAP, 0
        place[n] = (x - x0, y - y1); x += w + GAP; rowh = max(rowh, h)

    report = {"style": style, "sample": sample, "sizes": sizes, "notch_style": notch_style, "cut_in": cut_in,
              "internal_cut_layer": internal_cut_layer, "pieces": {}}

    def new_doc():
        doc = ezdxf.new("R12")
        for L, c in (("1", 7), ("2", 2), ("3", 3), ("4", 1), ("6", 6), ("7", 4), ("8", 3), ("11", 1), ("13", 1), ("14", 5),
                     ("15", 7), ("80", 1), ("81", 1), ("83", 1)):
            doc.layers.add(L, color=c, linetype="Continuous")
        msp = doc.modelspace()
        # 머리 글자 — 공개 Gerber AccuMark 내보내기와 같은 열쇠·순서(+ ASTM 의 Grade Rule Table). TOLERANCE = 그레이드 점 허용(mm)
        head = [f"Style Name: {style}", f"Creation Date: {when:%d-%m-%Y}", f"Creation Time: {when:%H:%M}", "Author: STIZ",
                "PRODUCT: STIZ PATTERN ENGINE", "VERSION: 2026-10-19", f"Sample Size: {sample}", f"Grade Rule Table: {style}",
                "Units: METRIC", f"TOLERANCE: {TOL_KNOT:.3f}".replace("0.", ".", 1)]
        for i, t in enumerate(head):
            msp.add_text(t, dxfattribs={"layer": "1", "height": TEXT_H}).set_placement((GAP, 60 - i * TEXT_H * 1.6))
        return doc, msp

    doc, msp = new_doc(); nest, nmsp = new_doc(); recs = []
    for n in names:
        p, base_name, side, _note = inst[sample][n]; spec = SP[sample][n]
        G = A[sample][n]; loc = locf(n); Gl = _localize(G, loc)
        info, drill_d = grade_points(G, {s: A[s][n] for s in sizes}, sample)
        sew_l = Gl["lines"][1][1]; S = Polygon(sew_l).buffer(0); S = max(getattr(S, "geoms", [S]), key=lambda g: g.area)
        a = polylabel(S, tolerance=0.5); anchor = (a.x, a.y)
        grain, arrow, rib, gsrc = grain_of(spec, sew_l, anchor, loc, G["grain"])
        flip = flip_rule(spec, side)
        ann = [SIDE_EN[side]] if side else []
        if flip == "금지": ann.append("NO FLIP")
        if G["on_fold"]: ann.append("CUT ON FOLD")
        suffix = (f" {n.split(' ')[-1]}" if ' ' in n else "")
        rows = lambda size: [f"Piece Name: {_en(base_name)}{suffix}", f"SIZE: {size}", "Quantity: 1",
                             f"CATEGORY: {CATEGORY.get(base_name, 'SHELL')}"] + ([f"ANNOTATION: {', '.join(ann)}"] if ann else [])
        tmpl = (spec.get("label") or {}).get("template") or DEFAULT_LABEL
        lab_ko = fill_label(tmpl, label_values(base_name, sample, qty[(base_name, side)], side, label))
        lab_en = _ascii(fill_label(tmpl, label_values(base_name, sample, qty[(base_name, side)], side,
                                                      {k: _ascii(v) for k, v in (label_en or label or {}).items()}, en=True)))
        notes = [lab_en] if lab_en else []
        kinds = {}
        for k in G["drill_kinds"]: kinds[k] = kinds.get(k, 0) + 1
        notes += [f"DRILL {DRILL_EN.get(k, _ascii(k))} x{c}" for k, c in kinds.items()]
        if rib: notes.append("RIB - WALE VERTICAL - STRETCH HORIZONTAL")
        # ── 기준 사이즈 블록: 선 + 점 종류(2/3) + 규칙 번호 ──
        blk = doc.blocks.new(name=_block_name(n, base_name, sample))
        prep = {"lines": [], "drills": []}
        for (L, P, closed), gi in zip(Gl["lines"], info):
            blk.add_polyline2d(P, close=closed, dxfattribs={"layer": L})
            rmap = {i: rules.add(gi["disp"][i]) for i in gi["knots"]}
            for i, q in enumerate(P):
                lay = "2" if i in gi["turn"] else "3"
                blk.add_point(q, dxfattribs={"layer": lay})
                if i in rmap:
                    blk.add_text(f"# {rmap[i]}", dxfattribs={"layer": lay, "height": RULE_H, "insert": q})
            prep["lines"].append({"layer": L, "n": len(P), "grade_points": len(gi["knots"]),
                                  "turn_knots": sum(1 for i in gi["knots"] if i in gi["turn"]), "mode": gi["mode"]})
        for d, dd in zip(Gl["drills"], drill_d):
            r = rules.add(dd)
            blk.add_point(d, dxfattribs={"layer": "13"})
            blk.add_text(f"# {r}", dxfattribs={"layer": "13", "height": RULE_H, "insert": d})
        _write_piece(blk, Gl)
        if grain:
            blk.add_line(*grain, dxfattribs={"layer": "7"})
            for q in grain: blk.add_point(q, dxfattribs={"layer": "2"})
        _texts(blk, anchor, rows(sample))
        _texts(blk, (anchor[0], anchor[1] - len(rows(sample)) * TEXT_H * 1.6 - TEXT_H), notes, layer="15", h=TEXT_H * 0.7)
        msp.add_blockref(blk.name, place[n], dxfattribs={"layer": "1"})
        # ── 전 사이즈 묶음: 사이즈마다 블록(선·노치·구멍·글자), 모두 같은 자리에 겹쳐 꽂는다 ──
        for s in sizes:
            Gs = _localize(A[s][n], loc); b2 = nest.blocks.new(name=_block_name(n, base_name, s))
            for L, P, closed in Gs["lines"]: b2.add_polyline2d(P, close=closed, dxfattribs={"layer": L})
            for d in Gs["drills"]: b2.add_point(d, dxfattribs={"layer": "13"})
            _write_piece(b2, Gs)
            gs = grain if (gsrc != "식서선" or not A[s][n]["grain"]) else loc(A[s][n]["grain"])   # 사이즈마다 자기 식서선
            if gs: b2.add_line(*gs, dxfattribs={"layer": "7"})
            _texts(b2, anchor, rows(s) if s == sample else rows(s)[:2])
            nmsp.add_blockref(b2.name, place[n], dxfattribs={"layer": "1"})
        # ── 검산: 규칙만으로 다시 만든 점 ↔ 엔진 점 — 꺾인 점·곡선 점 따로, 점 수 다른 선은 «모든 점» 을 비워 둔다 ──
        e = {"turn": 0.0, "curve": 0.0, "all": 0.0, "shape": None, "round": 0.0}; any_corner = False
        mt = {s: _match_lines(G, A[s][n]) for s in sizes}
        for k, ((L, P, closed), gi) in enumerate(zip(G["lines"], info)):
            any_corner |= gi["mode"] == "corner"
            for s in sizes:
                kd = {i: rules.order[rules.table[rules.key(gi["disp"][i])]][sizes.index(s)] for i in gi["knots"]}
                for i in gi["knots"]:                          # 규칙 반올림(0.01mm) 오차 — 예전 «grade_point_err» 가 잰 것은 이것뿐이었다
                    e["round"] = max(e["round"], math.dist(kd[i], gi["disp"][i][s]))
                cands = [P2 for L2, P2, c2 in A[s][n]["lines"] if L2 == L and c2 == closed]
                r = _check_err(P, closed, gi, sizes, s, kd, mt[s][k], cands)
                e["turn"] = max(e["turn"], r["turn"]); e["curve"] = max(e["curve"], r["curve"])
                if r["all"] is not None: e["all"] = max(e["all"], r["all"])
                if r["shape"] is not None: e["shape"] = max(e["shape"] or 0.0, r["shape"])
        dk = {}
        for k in G["drill_kinds"]: dk[k] = dk.get(k, 0) + 1
        prep.update({"block": blk.name, "drills": len(G["drills"]), "drills_by_kind": dk,
                     "notches": len(G["notches"]) if notch_style == "line" else len(G["notch_points"]),
                     "notch_sites": len(G["shapes"]) + len(G["carved"]), "notch_types": sorted({s["type"] for s in G["shapes"]} | set(G["carved"])),
                     "carved_notches": len(G["carved"]), "internal_cut_lines": sum(1 for L, _, _ in G["lines"] if L == internal_cut_layer and L != "1")
                     + (sum(1 for L, _, _ in G["lines"][1:] if L == "1") if internal_cut_layer == "1" else 0),
                     "flip": flip, "on_fold": G["on_fold"], "label": lab_ko, "label_dxf": lab_en,
                     "grain": gsrc, "rib_grain": rib,
                     "rule_rounding_err_mm": round(e["round"], 3),
                     "turn_point_err_mm": round(e["turn"], 3), "curve_point_err_mm": round(e["curve"], 3),
                     "all_points_err_mm(index)": None if any_corner else round(e["all"], 3),
                     "shape_hausdorff_mm(corner)": None if e["shape"] is None else round(e["shape"], 3),
                     "check_note": "점 수가 사이즈마다 다른 선 — 곡선 점은 «같은 번호 엔진 점» 이 없어 엔진 선까지 거리, 모양은 하우스도르프로 잰다"
                     if any_corner else None})
        report["pieces"][n] = prep
        recs.append({"name": n, "base": base_name, "side": side, "G": Gl, "place": place[n], "anchor": anchor, "grain": grain,
                     "arrow": arrow, "rib": rib, "label": lab_ko, "flip": flip,
                     "rows": [f"{n} · {sample}", f"{GROUP_KO.get(grp, grp)} · 뒤집기 {flip}" + (" · 접어 재단" if G["on_fold"] else "")]})
    allp = [(q[0] + place[n][0], q[1] + place[n][1]) for n in names for q in locf(n)(A[sample][n]["lines"][0][1])]
    for d in (doc, nest):
        d.modelspace().reset_extents((min(q[0] for q in allp), min(q[1] for q in allp), 0), (max(q[0] for q in allp), max(q[1] for q in allp), 0))
    files = {"dxf": os.path.join(out, f"{style}_{sample}.dxf"), "rul": os.path.join(out, f"{style}.rul"),
             "nest": os.path.join(out, f"{style}_ALLSIZES.dxf")}
    doc.saveas(files["dxf"]); nest.saveas(files["nest"]); rules.write(files["rul"], style, sample, when)
    if pdf:
        files["pdf"] = os.path.join(out, f"{style}_{sample}_1대1.pdf")
        write_pdf(files["pdf"], recs, f"{style} · {sample} · 1:1 — 100% 로 인쇄", internal_cut_layer)
    report["rules"] = len(rules.order); report["files"] = {k: os.path.basename(v) for k, v in files.items()}
    return report


# ════════ 1:1 PDF — 노치 모양·자르는 선·구멍 기호·식서·라벨 ════════
PT = 72 / 25.4
FONT = "C:/Windows/Fonts/malgun.ttf"
FOLD_DASH = "[6 2 1 2] 0"   # 접는 선(골) — 범례·그림 같은 파란 일점쇄선
COLORS = {"cut": (0, 0, 0), "sew": (0.45, 0.45, 0.45), "inner": (0, 0.55, 0), "inner_cut": (0.85, 0, 0), "notch": (0, 0, 0),
          "drill": (0, 0, 0.8), "grain": (0, 0, 0), "fold": (0, 0.3, 0.9), "text": (0, 0, 0)}


def _drill_symbol(sh, P, q, kind, r=3.0):
    """구멍 기호 — 스냅 ○ · 짝 ⊕ · 아일렛 ◎ · 단추 ⊗ (반지름 3mm)"""
    c = P(q); sh.draw_circle(c, r * PT)
    if kind == "짝":
        sh.draw_line(P((q[0] - r, q[1])), P((q[0] + r, q[1]))); sh.draw_line(P((q[0], q[1] - r)), P((q[0], q[1] + r)))
    elif kind == "아일렛":
        sh.draw_circle(c, r * 0.5 * PT)
    elif kind == "단추":
        k = r * 0.7071
        sh.draw_line(P((q[0] - k, q[1] - k)), P((q[0] + k, q[1] + k))); sh.draw_line(P((q[0] - k, q[1] + k)), P((q[0] + k, q[1] - k)))


def _arrow(sh, P, a, b, both=True, head=6.0):
    """화살표 선 — 끝(b) 에 촉, both 면 시작(a) 에도"""
    sh.draw_line(P(a), P(b))
    for s, t in ((a, b), (b, a)) if both else ((a, b),):
        d = _unit((t[0] - s[0], t[1] - s[1]))
        for sg in (1, -1):
            r = math.radians(25 * sg); c, sn = math.cos(r), math.sin(r)
            v = (-(d[0] * c - d[1] * sn), -(d[0] * sn + d[1] * c))
            sh.draw_line(P(t), P((t[0] + v[0] * head, t[1] + v[1] * head)))


def write_pdf(path, recs, title, internal_cut_layer=INTERNAL_CUT_LAYER, legend=True, type_tags=False):
    """recs: 조각마다 {"G": 조각 좌표 기하, "place": 배치 이동, "anchor", "grain", "arrow", "rib", "label", "rows"} — y 위쪽(+) mm"""
    import fitz
    allp = [(q[0] + r["place"][0], q[1] + r["place"][1]) for r in recs for q in r["G"]["lines"][0][1]]
    M, TOP = 20.0, 70.0 if legend else 30.0
    x0, y0 = min(q[0] for q in allp), min(q[1] for q in allp); x1, y1 = max(q[0] for q in allp), max(q[1] for q in allp)
    W, H = max(x1 - x0 + 2 * M, 420.0), y1 - y0 + M + TOP
    doc = fitz.open(); page = doc.new_page(width=W * PT, height=H * PT)
    has_font = os.path.exists(FONT)
    if has_font: page.insert_font(fontname="mg", fontfile=FONT); font = fitz.Font(fontfile=FONT)   # 글꼴은 한 번만 읽는다
    else: font = fitz.Font("helv")

    def text(x, y, s, fs=9, color=(0, 0, 0), center=False):
        if center: x -= font.text_length(s, fontsize=fs) / PT / 2
        page.insert_text(fitz.Point(x * PT, y * PT), s, fontsize=fs, color=color, fontname="mg" if has_font else "helv")
    text(M, 14, title, 14)
    if legend:                                               # 범례 — 선 종류·구멍 기호·노치 6종
        sh = page.new_shape(); Lp = lambda q: fitz.Point(q[0] * PT, q[1] * PT)
        items = [("재단선", "cut", None), ("재봉선(점선)", "sew", "[3 2] 0"), ("안쪽선(그리기)", "inner", None),
                 ("자르는 선(주머니 입구)", "inner_cut", None), ("접는 선(골)", "fold", FOLD_DASH)]
        for i, (nm, ck, dash) in enumerate(items):
            yy = 26 + i * 8; s2 = page.new_shape(); s2.draw_line(Lp((M, yy)), Lp((M + 18, yy)))
            s2.finish(color=COLORS[ck], width=1.0 if ck == "inner_cut" else 0.6, dashes=dash); s2.commit(); text(M + 22, yy + 1.2, nm, 8)
        for i, k in enumerate(("스냅", "짝", "아일렛", "단추")):
            q = (M + 95 + i * 30, 30); s2 = page.new_shape(); _drill_symbol(s2, Lp, q, k)
            s2.finish(color=COLORS["drill"], width=0.5); s2.commit(); text(q[0] + 5, q[1] + 1.2, k, 8)
        for i, k in enumerate(NS.NOTCH_TYPES):
            q = (M + 95 + i * 30, 46); s2 = page.new_shape(); s2.draw_line(Lp((q[0] - 8, q[1])), Lp((q[0] + 8, q[1])))
            for pth in NS.notch_paths(q, (0, 1), (1, 0), k):
                for a, b in zip(pth, pth[1:]): s2.draw_line(Lp(a), Lp(b))
            s2.finish(color=(0, 0, 0), width=0.5); s2.commit(); text(q[0] - 7, q[1] + 11, NOTCH_KO[k], 7)
        text(M + 95, 64, "식서 ↕ (원단 길이 방향) · 립: 골 세로 · 늘어나는 방향 가로 · 노치 깊이 5mm 폭 3mm", 8)
        sh.commit()
    for r in recs:
        G, (dx, dy) = r["G"], r["place"]
        P = lambda q, dx=dx, dy=dy: fitz.Point((q[0] + dx - x0 + M) * PT, (y1 - (q[1] + dy) + TOP) * PT)

        def stroke(paths, ck, wd=0.6, dash=None, closed=False):
            s2 = page.new_shape()
            for pth in paths:
                pts = [P(q) for q in pth] + ([P(pth[0])] if closed else [])
                if len(pts) > 1: s2.draw_polyline(pts)
            s2.finish(color=COLORS[ck], width=wd, dashes=dash, closePath=False); s2.commit()
        def off_axis(pts):
            """접어 재단 조각 — 고리를 접는 선 위 변에서 끊어 열린 선들로(그 변은 접는 선이 대신 그린다)"""
            if not G.get("mirror"): return [list(pts) + [pts[0]]]
            ax = G["mirror"][0][0]; on = lambda q: abs(q[0] - ax) < 1e-6; out, cur = [], [pts[0]]
            for a, b in zip(pts, list(pts[1:]) + [pts[0]]):
                if on(a) and on(b):
                    if len(cur) > 1: out.append(cur)
                    cur = [b]
                else: cur.append(b)
            if len(cur) > 1: out.append(cur)
            return out
        for L, pts, c in G["lines"]:
            if L == "1" and pts is G["lines"][0][1]: stroke(off_axis(pts), "cut", 0.7)
            elif L == "14": stroke(off_axis(pts), "sew", 0.4, "[3 2] 0")
            elif L == internal_cut_layer or L == "1": stroke([pts], "inner_cut", 1.0, closed=c)
            else: stroke([pts], "inner", 0.5, closed=c)
        for shp in G["shapes"]: stroke(shp["paths"], "notch", 0.6)
        if G.get("mirror"):
            stroke([G["mirror"]], "fold", 0.9, FOLD_DASH)
            m = G["mirror"]; text(m[0][0] + dx - x0 + M + 2, y1 - ((m[0][1] + m[1][1]) / 2 + dy) + TOP, "접는 선 — 원단을 접어 재단", 9, COLORS["fold"])
        s2 = page.new_shape()
        for q, k in zip(G["drills"], G["drill_kinds"]): _drill_symbol(s2, P, q, k)
        s2.finish(color=COLORS["drill"], width=0.5); s2.commit()
        if r.get("grain"):
            s2 = page.new_shape(); a, b = r["grain"]; _arrow(s2, P, a, b, r.get("arrow", "both") == "both")
            if r.get("rib"):                                  # 립 — 늘어나는 방향(가로) 화살표를 식서 가운데에
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); L2 = min(40.0, math.dist(a, b) * 0.6)
                _arrow(s2, P, (mid[0] - L2, mid[1]), (mid[0] + L2, mid[1]), True, 4.0)
            s2.finish(color=COLORS["grain"], width=0.5); s2.commit()
            if r.get("rib"):
                text(a[0] + dx - x0 + M + 2, y1 - (max(a[1], b[1]) + dy) + TOP + 4, "골 세로 · 늘어나는 방향 가로", 7)
        ax_, ay_ = r["anchor"]; X = ax_ + dx - x0 + M; Y = y1 - (ay_ + dy) + TOP
        for i, t in enumerate(r["rows"]): text(X, Y + i * 5, t, 10 if i == 0 else 8, center=True)
        if r.get("label"): text(X, Y + len(r["rows"]) * 5 + 2, r["label"], 9, (0.2, 0.2, 0.2), center=True)
        if type_tags:                                         # 확인 장 — 노치마다 종류 이름
            for shp in G["shapes"]:
                q = (shp["p"][0] + shp["w"][0] * 14, shp["p"][1] + shp["w"][1] * 14)
                text(q[0] + dx - x0 + M - 3, y1 - (q[1] + dy) + TOP + 1, NOTCH_KO[shp["type"]], 7, (0.6, 0, 0))
            for q, k in zip(r.get("carved_at", []), r.get("carved_types", [])):
                text(q[0] + dx - x0 + M - 3, y1 - (q[1] + dy) + TOP + 1, NOTCH_KO[k] + "(파냄)", 7, (0.6, 0, 0))
    doc.set_metadata({"title": title, "creator": "STIZ pattern-engine aama 2026-10-19"})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    doc.subset_fonts(); doc.save(path, garbage=3, deflate=True); doc.close()
    return path


# ════════ 확인 장 — 노치 6종·자르는 선·구멍 4종·립 식서·접어 재단·라벨을 한 장에 ════════
def check_sheet(graded, sample, path, label=None, decorate=None):
    """사람 확인용 1:1 한 장. 공장 파일과 별개 — 여기서만 «예시» 속성(뒤판 노치 6종·주머니감 아일렛/단추)을 붙인다"""
    picks = [("top", "뒤판", "notch6"), ("top", "뒤판", "fold"), ("top", "앞판 R", None), ("top", "밑단립", None),
             ("bottom", "앞옆배색 L", None), ("bottom", "뒤옆배색 L", None), ("top", "앞주머니감 R-1", "drills")]
    recs = []; GAP = 40; x = GAP; y = 0; rowh = 0; ROW_W = 1500
    for grp, n, demo in picks:
        p, base, side, _ = expand(graded[sample][grp], GROUPS[grp][1])[n]
        sp = from_legacy(p)
        if decorate: decorate(grp, base, sp, side)
        cut_in = False; title = n
        if demo == "notch6":                                  # 노치 6개에 6종을 하나씩 — V·U·성곽은 재단선을 파낸다
            ks = [k for k, s in enumerate(sp["seam"]) if s.get("notch")]
            for k, t in zip(ks, NS.NOTCH_TYPES):
                sp["seam"][k]["notch"].update({"type": t, "count": 2 if t == "slit" else 1, "width": NS.WIDTH})
            cut_in = True; title = f"{n} — 노치 6종(예시)"
        if demo == "fold": sp["cut_on_fold"] = True; title = f"{n} — 접어 재단(예시)"
        if demo == "drills":
            c = Polygon(clean_ring(p["sew"])).buffer(0).representative_point()
            sp["drills"] = [{"pt": [c.x - 25, c.y + 45], "kind": "아일렛"}, {"pt": [c.x + 25, c.y + 45], "kind": "단추"}]
            title = f"{n} — 아일렛·단추(예시)"
        G = to_aama(p, sp, "line", cut_in)
        # 파낸 노치 자리(글자용) — 파내기 전 자리
        carved_at = [(st["p"][0] + st["w"][0] * 14, st["p"][1] + st["w"][1] * 14)
                     for st in notch_sites(p, sp, [tuple(v) for v in clean_ring(p["cut"])]) if cut_in and st["type"] in NS.OPEN_TYPES]
        o = (min(v[0] for v in G["lines"][0][1]), min(v[1] for v in G["lines"][0][1]))
        loc = lambda pts, o=o: [(a - o[0], b - o[1]) for a, b in pts]
        Gl = _localize(G, loc); w = max(v[0] for v in Gl["lines"][0][1]); h = max(v[1] for v in Gl["lines"][0][1])
        if x + w > ROW_W and x > GAP: x, y, rowh = GAP, y - rowh - GAP - 30, 0
        sew_l = Gl["lines"][1][1]; S = Polygon(sew_l).buffer(0); S = max(getattr(S, "geoms", [S]), key=lambda g: g.area)
        a = polylabel(S, tolerance=0.5); anchor = (a.x, a.y)
        grain, arrow, rib, _ = grain_of(sp, sew_l, anchor, loc, G["grain"])
        tmpl = (sp.get("label") or {}).get("template") or DEFAULT_LABEL
        kinds = sorted(set(G["drill_kinds"]))
        recs.append({"G": Gl, "place": (x, y - h), "anchor": anchor, "grain": grain, "arrow": arrow, "rib": rib,
                     "label": fill_label(tmpl, label_values(base, sample, 1, side, label)),
                     "rows": [title, f"뒤집기 {flip_rule(sp, side)}" + (f" · 구멍 {', '.join(kinds)}" if kinds else "")
                              + (" · 자르는 선 있음" if any(L == INTERNAL_CUT_LAYER for L, _, _ in G['lines']) else "")],
                     "carved_at": loc(carved_at), "carved_types": [t for t in G["carved"]]})
        x += w + GAP; rowh = max(rowh, h)
    return write_pdf(path, recs, f"확인 — F3 노치 6종 · F4 자르는 선·구멍 · F5 식서·라벨 · F6 접어 재단 · {sample} · 1:1 (100% 인쇄)",
                     INTERNAL_CUT_LAYER, legend=True, type_tags=True)


def _kv(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        if not _: raise SystemExit(f"--label 은 키=값 — {it!r}")
        out[k.strip()] = v.strip()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--graded", default=os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup", "graded", "graded.json"))
    ap.add_argument("--out", default=os.path.join(REPO, "tmp", "pattern-engine", "aama"))
    ap.add_argument("--sample", default="2XL")
    ap.add_argument("--notch-style", choices=NOTCH_STYLES, default=NOTCH_STYLE)
    ap.add_argument("--cut-in", action="store_true", help="V·U·성곽 노치를 재단선에 파낸다")
    ap.add_argument("--cut-layer", choices=("11", "1"), default=INTERNAL_CUT_LAYER, help="자르는 안쪽선 레이어(기본 11 = ASTM Internal cutouts)")
    ap.add_argument("--fold", nargs="*", default=[], help="접어 재단할 조각 — «상의:뒤판»(그 옷만, 비대칭이면 오류) 또는 «뒤판»(대칭인 조각에만, 나머지는 경고) → 반쪽 + 접는 선(레이어 6)")
    ap.add_argument("--label", action="append", help="라벨 값 키=값 (원단·색·팀·주문번호) — 🚫 운영 DB 를 읽지 않는다")
    ap.add_argument("--label-en", action="append", help="DXF 라벨용 영문 값 키=값 (없으면 한글 값에서 영문만)")
    ap.add_argument("--no-decorate", action="store_true", help="가스 명세 속성(주머니 자르는 선·스냅 종류·립 식서·뒤집기) 끄기")
    ap.add_argument("--check", action="store_true", help="확인_F3-F6_1대1.pdf 도 만든다")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.exists(a.graded):
        sys.exit(f"그레이딩 결과가 없다: {a.graded}\n먼저 python tools/pattern-engine/gas_warmup_grade.py --no-export")
    with open(a.graded, encoding="utf-8") as f: graded = json.load(f)
    os.makedirs(a.out, exist_ok=True); when = datetime.datetime.now()
    deco = None
    if not a.no_decorate:
        from gas_warmup_spec import decorate as deco     # 가스 웜업 명세 규칙 — 같은 규칙으로 spec_*.json 도 만든다
    lab, lab_en = _kv(a.label), _kv(a.label_en)
    rep = {g: export_group(graded, g, a.sample, a.out, when, a.notch_style, a.cut_in, a.cut_layer, a.fold, deco, lab, lab_en or None,
                           pdf=not a.no_pdf) for g in GROUPS}
    with open(os.path.join(a.out, "aama_검산.json"), "w", encoding="utf-8") as f: json.dump(rep, f, ensure_ascii=False, indent=1)
    for g, r in rep.items():
        P = r["pieces"].values()
        et = max(p["turn_point_err_mm"] for p in P); ec = max(p["curve_point_err_mm"] for p in P)
        ea = max((p["all_points_err_mm(index)"] for p in P if p["all_points_err_mm(index)"] is not None), default=None)
        eh = max((p["shape_hausdorff_mm(corner)"] for p in P if p["shape_hausdorff_mm(corner)"] is not None), default=None)
        print(f"{r['style']}: 조각 {len(r['pieces'])} · 규칙 {r['rules']} · 노치 {r['notch_style']} {sum(p['notches'] for p in P)}개"
              f" · 꺾인 점 최대 {et}mm · 곡선 점 최대 {ec}mm · 모든 점(번호 같은 선) {ea}mm"
              + (f" · 점 수 다른 선 모양 {eh}mm" if eh is not None else "") + f" → {', '.join(r['files'].values())}")
    if a.check:
        print("확인 장:", check_sheet(graded, a.sample, os.path.join(a.out, "확인_F3-F6_1대1.pdf"), lab, deco))
    return rep


if __name__ == "__main__":
    main()
