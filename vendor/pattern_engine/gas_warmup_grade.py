# 한국가스공사 웜업 — «점별 규칙» 그레이딩 S~5XL (2026-10-19 사장님: 표준 CAD 점별 규칙 방식으로)
#
#   의류 CAD(Optitex 등)의 그레이딩 원리 그대로:
#     ① 조각의 기준점(꼭짓점·주요 노치)마다 «사이즈 한 칸에 x·y 로 얼마나 움직이는지» 규칙을 둔다
#     ② 기준점 사이의 선 위 점들은 두 기준점의 이동량을 «선 길이 비율»로 나눠 받는다
#     ③ 맞물리는 변의 길이가 어긋나면 한쪽 기준점 규칙을 고쳐 맞춘다(트루잉)
#   규칙은 «표준 웜업 CAD(OptiCad 13사이즈)»에서 같은 이름의 기준점이 실제로 움직인 양을 읽어 온다.
#     상의: 그대로 쓴다(가슴 +2 · 총기장 +2 …).  하의: x 이동량만 «가스 2XL ÷ 표준 2XL» 거리 비율을 곱한다(2XL 바지 비율 유지).
#   시접 9mm 는 늘리지 않는다 — 재단선 점은 가장 가까운 재봉선 점의 이동량을 따라간다.
#   실행: python tools/pattern-engine/gas_warmup_grade.py [--pieces <pieces_after.json>] [--std-top <.ai>] [--std-pants <.ai>]
#                                                        [--out <폴더>] [--sizes S M …] [--no-export]
#         기본: tmp/pattern-engine/gas-warmup/2xl/pieces_after.json · fixtures 표준 CAD → tmp/pattern-engine/gas-warmup/graded/
import sys, os, json, math, copy, re
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--pieces", default=os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup", "2xl", "pieces_after.json"))
_ap.add_argument("--std-top", default=os.path.join(HERE, "fixtures", "gas-warmup-2026", "std_warmup_top.ai"))
_ap.add_argument("--std-pants", default=os.path.join(HERE, "fixtures", "gas-warmup-2026", "std_warmup_pants.ai"))
_ap.add_argument("--out", default=os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup", "graded"))
_ap.add_argument("--sizes", nargs="*")
_ap.add_argument("--no-export", action="store_true")
# 식서(결 방향선)를 알아보려고 OptiCad 원본도 읽는다 — pieces_after.json 에는 «대문자 L» 표시가 남지 않는다
_ap.add_argument("--src-top", default=os.path.join(HERE, "fixtures", "gas-warmup-2026", "gas_top_2xl.ai"))
_ap.add_argument("--src-bottom", default=os.path.join(HERE, "fixtures", "gas-warmup-2026", "gas_bottom_2xl.ai"))
ARGS = _ap.parse_args()
sys.path.insert(0, HERE)
from patlib import bb, circle, outline, expand, export, SA
from cardinal import tips, clean, back_pts, front_pts_gas, front_pts_std, sleeve_pts, pants_pts
from shapely.geometry import Polygon, LineString, Point, box
from opticad import load_sized as load                                              # 표준 CAD 읽기

SIZES = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
A = json.load(open(ARGS.pieces, encoding="utf-8"))
T0, B0 = A["top"], A["bottom"]
STD_T, STD_P = load(ARGS.std_top), load(ARGS.std_pants)


# ════════ 규칙표 — 표준 CAD 기준점 이동량 (조각 기준 좌표) ════════
def deltas(f):
    base = f("2XL"); return {s: {k: (f(s)[k][0] - base[k][0], f(s)[k][1] - base[k][1]) for k in base} for s in SIZES}


R_BACK = deltas(lambda s: back_pts(STD_T[s]["뒤판"]["sew"])[0])
R_FRONT = deltas(lambda s: front_pts_std(STD_T[s]["앞판"]["sew"], STD_T[s]["앞판사이바"]["sew"]))
R_SLEEVE = deltas(lambda s: sleeve_pts(STD_T[s]["소매"]["sew"], True)[0])
R_PF = deltas(lambda s: pants_pts(STD_P[s]["앞판"]["sew"], False)[0])
R_PB = deltas(lambda s: pants_pts(STD_P[s]["뒤판"]["sew"], True)[0])
for s in SIZES:                       # 표준 앞판사이바 밑단이 4XL·5XL 에서 3~8mm 휘는 것은 립을 다는 가스 밑단에 맞지 않아 0 으로 둔다
    R_FRONT[s]["옆밑단"] = (R_FRONT[s]["옆밑단"][0], 0.0)
STD_PF2 = pants_pts(STD_P["2XL"]["앞판"]["sew"], False)[0]; STD_PB2 = pants_pts(STD_P["2XL"]["뒤판"]["sew"], True)[0]


# ════════ 점별 그레이딩 엔진 ════════
def path_len(P, idx):
    pts = [P[i] for i in idx if i not in TIPS_CACHE.get(id(P), set())]
    return sum(math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1))


TIPS_CACHE = {}


def walk(n, i, j, fwd):
    return [(i + k) % n for k in range(((j - i) % n) + 1)] if fwd else [(i - k) % n for k in range(((i - j) % n) + 1)]


def seg_len(P, T, idx):
    pts = [P[i] for i in idx if i not in T]
    return sum(math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1))


def nearest_idx(P, T, q):
    return min((i for i in range(len(P)) if i not in T), key=lambda i: math.dist(P[i], q))


def grade_outline(P, cards):
    """cards: [(재봉선 위 점(원래 좌표), (dx, dy))] → 재봉선 모든 점의 이동량"""
    n = len(P); T = tips(P)
    ci = sorted({nearest_idx(P, T, q): d for q, d in cards}.items())
    D = [None] * n
    for k in range(len(ci)):
        (a, da), (b, db) = ci[k], ci[(k + 1) % len(ci)]
        idx = walk(n, a, b, True)
        tot = seg_len(P, T, idx) or 1.0
        s = 0.0; prev = None
        for i in idx:
            if i in T: continue
            if prev is not None: s += math.dist(P[prev], P[i])
            t = s / tot
            D[i] = (da[0] + (db[0] - da[0]) * t, da[1] + (db[1] - da[1]) * t); prev = i
    for i in range(n):
        if i in T: D[i] = D[i - 1]
    return D


def ring_disp(P, D, q):
    best = None
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        ab = (b[0] - a[0], b[1] - a[1]); L2 = ab[0] ** 2 + ab[1] ** 2
        t = 0 if L2 == 0 else max(0, min(1, ((q[0] - a[0]) * ab[0] + (q[1] - a[1]) * ab[1]) / L2))
        c = (a[0] + ab[0] * t, a[1] + ab[1] * t); d = math.dist(c, q)
        if best is None or d < best[0]:
            Da, Db = D[i], D[(i + 1) % len(P)]
            best = (d, (Da[0] + (Db[0] - Da[0]) * t, Da[1] + (Db[1] - Da[1]) * t))
    return best


def field(P, D, q):
    d, v = ring_disp(P, D, q)
    if d < 1.5: return v
    ws = sorted(((math.dist(P[i], q), D[i]) for i in range(len(P))), key=lambda x: x[0])[:40]
    W = [1 / max(w, 1e-6) ** 2 for w, _ in ws]
    return (sum(w * v[0] for w, (_, v) in zip(W, ws)) / sum(W), sum(w * v[1] for w, (_, v) in zip(W, ws)) / sum(W))


def grade_piece(p, cards):
    P = p["sew"]; D = grade_outline(P, cards)
    mv = lambda q, d: (q[0] + d[0], q[1] + d[1])
    q = dict(p)
    q["sew"] = [mv(P[i], D[i]) for i in range(len(P))]
    q["cut"] = [mv(v, ring_disp(P, D, v)[1]) for v in p["cut"]]
    q["draw"] = [dict(d, pts=[mv(v, field(P, D, v)) for v in d["pts"]], **({"snap": mv(d["snap"], field(P, D, d["snap"]))} if d.get("snap") else {}))
                 for d in p["draw"]]
    q["notch"] = [[mv(v, ring_disp(P, D, v)[1]) for v in l] for l in p.get("notch") or []]
    q["fold"] = None
    place_grain(p, q)                    # 식서만은 «필드 이동» 대신 세로·길이 고정으로 다시 놓는다
    return q, D


# ════════ 식서(결 방향선) — 기울이지 않고 · 길이 고정 · 조각 안 상대 위치만 따라간다 (2026-10-19) ════════
#   안쪽선은 field() 로 옮기는데 식서까지 그렇게 옮기면 사이즈마다 기울고(소매 S 0.2° · 바지 앞판 S 1.1°) 길이가 변했다
#   (소매 417.6~469.0mm). 표준 CAD(std_warmup_top.ai 13사이즈)는 식서를 «세로 · 길이 고정 · 조각 가운데»에 둔다.
#   그래서 2XL 식서를 «평행이동»만 한다 — 중점이 2XL 조각의 재봉선 외곽 상자에서 차지하던 가로·세로 비율을
#   그레이딩된 조각의 외곽 상자에서 그대로 차지하게.
def raw_grains(path):
    """OptiCad 원본 DRAW 레이어의 식서 → [(시작점, 끝점)] mm.
       식서는 «대문자 L»(꺾인 점 직선)로 끝나는 두 점 선이다 — 덧방 위치선·립 접는 선 같은 보조선은 소문자 l.
       opticad.parse 는 L/l 을 합쳐 버려서 여기서 원본 글줄을 직접 훑는다(층 쌓기는 parse 와 같은 방식)."""
    stack, out, prev = [], [], None
    MMF = 25.4 / 72
    for ln in open(path, "rb").read().decode("cp949", errors="replace").splitlines():
        s = ln.strip(); p = s.split()
        if s.startswith("%AI5_BeginLayer"): stack.append(None); continue
        if s.startswith("%AI5_EndLayer"): stack.pop(); continue
        m = re.match(r"^\((.*)\) Ln$", s)
        if m: stack[-1] = m.group(1); continue
        if not p: continue
        # 바로 앞 줄이 «x y m»(선 시작) 이고 이 줄이 «x y L» 이면 식서 한 줄
        if stack and stack[-1] == "DRAW" and len(p) == 3 and p[2] == "L" and prev and len(prev) == 3 and prev[2] == "m":
            out.append(((float(prev[0]) * MMF, float(prev[1]) * MMF), (float(p[0]) * MMF, float(p[1]) * MMF)))
        prev = p
    return out


GRAIN_REF = raw_grains(ARGS.src_top) + raw_grains(ARGS.src_bottom)


def grain_index(p):
    """2XL 조각 draw 목록에서 원본 식서가 몇 번째 선인가(없으면 None) — 원본 좌표 0.01mm 안으로 같은 두 점 선.
       grade_piece·band_grade 는 draw 순서를 지키므로 같은 번호가 그레이딩된 조각의 식서다(소매 덧방 위치선과 같은 방식)."""
    for i, d in enumerate(p.get("draw") or []):
        P = d.get("pts") or []
        if len(P) == 2 and any(math.dist(a, P[0]) < 0.01 and math.dist(b, P[1]) < 0.01 for a, b in GRAIN_REF):
            return i
    return None


def grain_inside(sew, pts, where):
    """식서 두 끝이 재봉선 안에 있는가 — 밖이면 오류로 멈춘다(조각 밖 식서는 재단에서 쓸 수 없다)"""
    poly = Polygon(clean(sew)).buffer(0)
    for v in pts:
        if not poly.contains(Point(v)):
            raise ValueError(f"식서가 조각 밖으로 나갔다: {where} 끝점 ({v[0]:.1f}, {v[1]:.1f})")


def place_grain(p0, q):
    """p0: 2XL 조각 · q: 그레이딩된 조각(draw 순서 같음) — q 의 식서를 2XL 식서의 평행이동으로 바꾼다(각도·길이 그대로)"""
    gi = grain_index(p0)
    if gi is None: return
    a, b = p0["draw"][gi]["pts"]
    x0, y0, x1, y1 = bb(clean(p0["sew"])); X0, Y0, X1, Y1 = bb(clean(q["sew"]))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    rx, ry = (mx - x0) / (x1 - x0), (my - y0) / (y1 - y0)                     # 2XL 에서 중점의 상대 위치
    dx, dy = X0 + rx * (X1 - X0) - mx, Y0 + ry * (Y1 - Y0) - my              # 같은 상대 위치로 옮기는 이동량
    pts = [(a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)]
    grain_inside(q["sew"], pts, q.get("name") or p0.get("name"))
    q["draw"] = list(q["draw"]); q["draw"][gi] = dict(q["draw"][gi], pts=pts)


def rib_piece(name, L, Hsew, notch_xs):
    r = box(0, 0, L, Hsew)
    p = {"name": name, "cut": outline(r.buffer(SA, join_style=2)), "sew": outline(r), "draw": [], "notch": [], "fold": [(-SA, Hsew / 2), (L + SA, Hsew / 2)]}
    for x in notch_xs:
        p["notch"].append([(x, -SA), (x, -SA + 5)]); p["notch"].append([(x, Hsew + SA), (x, Hsew + SA - 5)])
    p["draw"].append({"pts": [(30, 15), (30, Hsew - 15)], "closed": False, "new": True, "nodes": 2})
    return p


# ════════ 상의 ════════
BK, FR, SL, DB = T0["뒤판"], T0["앞판"], T0["소매"], T0["소매중심덧방"]
GB, (CBX, BHEM) = back_pts(BK["sew"])
GF, (CFX, FHEM) = front_pts_gas(FR["sew"])
GS, (SHX, SHEM, SSG) = sleeve_pts(SL["sew"], False)
absB = lambda k, side=1: (CBX + side * GB[k][0], BHEM + GB[k][1])
absF = lambda k: (CFX - GF[k][0], FHEM + GF[k][1])
absS = lambda k: (SHX + SSG * GS[k][0], SHEM + GS[k][1])
BAND_X = (414.0, 479.0)                                # 소매 덧방 위치선 x (소매 가운데선에서 앞쪽 44.4 · 뒤쪽 20.6)


def _is_band_line(d):
    """2XL 원본 소매의 덧방 위치선인가 — 두 점짜리 세로선이고 x 가 위치선 자리(3mm 안)"""
    x0, _, x1, _ = bb(d["pts"])
    return d["nodes"] == 2 and abs(x0 - x1) < 0.5 and min(abs(x0 - x) for x in BAND_X) < 3


SL_BAND_IDX = {i for i, d in enumerate(SL["draw"]) if _is_band_line(d)}   # 원본 기준 번호 — 사이즈가 바뀌어도 같다
assert len(SL_BAND_IDX) == 2, f"2XL 소매 덧방 위치선은 2줄이어야 한다: {len(SL_BAND_IDX)}"
# 식서가 꼭 있어야 하는 조각 — 원본에서 못 찾으면(파일이 바뀌었다는 뜻) 조용히 넘어가지 말고 멈춘다
for _g, _n in (("top", "뒤판"), ("top", "앞판"), ("top", "소매"), ("bottom", "앞판"), ("bottom", "뒤판"), ("bottom", "앞옆배색"), ("bottom", "뒤옆배색")):
    assert grain_index(A[_g][_n]) is not None, f"2XL {_g} {_n} 에서 원본 식서(대문자 L 세로선)를 못 찾았다"
# 소매중심덧방은 사이즈마다 소매에서 다시 오려 만들지만 식서는 다른 조각과 같은 규칙 — 원본 2XL 덧방 조각(DB)의 식서를
#   길이 그대로(445.55mm) · 원본 상대 위치 그대로(세로 약 0.4905) 옮긴다. 그래서 그레이딩 2XL 덧방 식서 = 2XL 수정본(2026-10-19 결정)
assert grain_index(DB) is not None, "2XL 소매중심덧방에서 원본 식서(대문자 L 세로선)를 못 찾았다"


def idx_path(P, a, b, expect):
    T = tips(P); n = len(P); i, j = nearest_idx(P, T, a), nearest_idx(P, T, b)
    f, g = walk(n, i, j, True), walk(n, i, j, False)
    return min((f, g), key=lambda w: abs(seg_len(P, T, w) - expect))


IDX = {   # 맞물림·목둘레 경로(원본 재봉선 번호) — 사이즈가 바뀌어도 점 번호는 같다
    "뒤 래글런": (BK["sew"], idx_path(BK["sew"], absB("겨드랑이"), absB("목옆"), 386)),
    "뒤 목": (BK["sew"], idx_path(BK["sew"], absB("목옆", -1), absB("목옆"), 145)),
    "뒤 밑단": (BK["sew"], idx_path(BK["sew"], absB("옆밑단", -1), absB("옆밑단"), 600)),
    "뒤 옆선": (BK["sew"], idx_path(BK["sew"], absB("겨드랑이"), absB("옆밑단"), 430)),
    "앞 래글런": (FR["sew"], idx_path(FR["sew"], absF("겨드랑이"), absF("목옆"), 336.6)),
    "앞 목": (FR["sew"], idx_path(FR["sew"], absF("목옆"), absF("앞중심목"), 89)),
    "앞 밑단": (FR["sew"], idx_path(FR["sew"], absF("옆밑단"), (CFX, FHEM), 294)),
    "앞 옆선": (FR["sew"], idx_path(FR["sew"], absF("겨드랑이"), absF("옆밑단"), 430)),
    "소매 앞 래글런": (SL["sew"], idx_path(SL["sew"], absS("겨드랑이앞"), absS("목앞"), 336.5)),
    "소매 뒤 래글런": (SL["sew"], idx_path(SL["sew"], absS("겨드랑이뒤"), absS("목뒤"), 385.9)),
    "소매 목": (SL["sew"], idx_path(SL["sew"], absS("목앞"), absS("목뒤"), 114.8)),
    "소매 목 뒤쪽": (SL["sew"], idx_path(SL["sew"], absS("목뒤"), absS("어깨"), 39.9)),
    "소매 밑단": (SL["sew"], idx_path(SL["sew"], absS("밑단앞"), absS("밑단뒤"), 320)),
    "소매 앞 밑선": (SL["sew"], idx_path(SL["sew"], absS("겨드랑이앞"), absS("밑단앞"), 468.5)),
    "소매 뒤 밑선": (SL["sew"], idx_path(SL["sew"], absS("겨드랑이뒤"), absS("밑단뒤"), 468.5)),
}
for k, (P, idx) in IDX.items():
    L0 = seg_len(P, tips(P), idx); assert L0 > 20, k


def L(graded_sew, key):
    P, idx = IDX[key]; return seg_len(graded_sew, tips(P), idx)


def notch_pos(graded_sew, key):
    P, idx = IDX[key]; T = tips(P); out = []; s = 0.0; prev = None
    for i in idx:
        if i in T: out.append(round(s, 2)); continue
        if prev is not None: s += math.dist(graded_sew[prev], graded_sew[i])
        prev = i
    return out


def top_cards(s, adj=None):
    adj = adj or {}
    rb, rf, rs = R_BACK[s], R_FRONT[s], R_SLEEVE[s]
    cb = [((CBX, BHEM), (0, 0)), (absB("뒤목중심"), rb["뒤목중심"])]
    for side in (1, -1):
        for k in ("옆밑단", "겨드랑이", "목옆"):
            cb.append((absB(k, side), (side * rb[k][0], rb[k][1])))
    cf = [((CFX, FHEM), (0, 0))] + [(absF(k), (-rf[k][0], rf[k][1])) for k in ("앞중심목", "목옆", "겨드랑이", "옆밑단")]
    cs = [((SHX, SHEM), (0, 0))]
    for k in ("밑단앞", "밑단뒤", "겨드랑이앞", "겨드랑이뒤", "목앞", "목뒤", "어깨"):
        d = rs[k]; a = adj.get(k, (0, 0))
        cs.append((absS(k), (SSG * d[0] + a[0], d[1] + a[1])))
    return cb, cf, cs


def grade_top(s):
    cb, cf, cs = top_cards(s)
    bk, _ = grade_piece(BK, cb); fr, _ = grade_piece(FR, cf)
    tF, tB = L(fr["sew"], "앞 래글런"), L(bk["sew"], "뒤 래글런")
    # 트루잉: 소매 목앞·목뒤 규칙을 래글런 방향으로 고쳐 몸판 래글런과 길이를 0 으로
    adj = {"목앞": (0.0, 0.0), "목뒤": (0.0, 0.0)}
    uF = (absS("목앞")[0] - absS("겨드랑이앞")[0], absS("목앞")[1] - absS("겨드랑이앞")[1]); m = math.hypot(*uF); uF = (uF[0] / m, uF[1] / m)
    uB = (absS("목뒤")[0] - absS("겨드랑이뒤")[0], absS("목뒤")[1] - absS("겨드랑이뒤")[1]); m = math.hypot(*uB); uB = (uB[0] / m, uB[1] / m)
    for _ in range(12):
        sl, _ = grade_piece(SL, top_cards(s, adj)[2])
        eF, eB = tF - L(sl["sew"], "소매 앞 래글런"), tB - L(sl["sew"], "소매 뒤 래글런")
        if abs(eF) < 0.02 and abs(eB) < 0.02: break
        adj["목앞"] = (adj["목앞"][0] + uF[0] * eF, adj["목앞"][1] + uF[1] * eF)
        adj["목뒤"] = (adj["목뒤"][0] + uB[0] * eB, adj["목뒤"][1] + uB[1] * eB)
    out = {"뒤판": bk}
    # 앞주머니 — 크기 고정, 옆선에서 55 · 밑단선 위 45
    fr["draw"] = [d for d in fr["draw"] if not d.get("new")]
    Fs = Polygon(fr["sew"]).buffer(0); hem = bb(fr["sew"])[1]
    sx = lambda y: LineString([(-1e5, y), (1e5, y)]).intersection(Fs).bounds[0]
    y1, y2 = hem + 45.0, hem + 195.0; x1, x2 = sx(y1) + 55.0, sx(y2) + 55.0
    fr["draw"].append({"pts": [(x1 - 7.5, y1), (x1 + 7.5, y1), (x2 + 7.5, y2), (x2 - 7.5, y2)], "closed": True, "new": True, "nodes": 5})
    out["앞판"] = fr
    # 소매중심덧방 — 소매 가운데선(밑단 가운데~어깨 노치, 규칙상 x 이동 0)에서 앞쪽 44.4 · 뒤쪽 20.6, 폭 65 고정
    bx0, bx1 = BAND_X                                     # 원본 덧방 위치선(소매 가운데선 x 에서 앞쪽 44.4 · 뒤쪽 20.6)
    sl_poly = Polygon(clean(sl["sew"])).buffer(0)
    band = sl_poly.intersection(box(bx0, -1e4, bx1, 1e4))
    band = max(getattr(band, "geoms", [band]), key=lambda g: g.area)
    bsew = outline(band)
    db = {"name": "소매중심덧방", "sew": bsew, "cut": outline(band.buffer(SA, join_style=2)), "draw": [], "notch": [], "fold": None}
    by0, by1 = band.bounds[1], band.bounds[3]
    #   식서 — 원본 덧방 식서를 자리만 잡아 넣고(draw 0번) place_grain 이 새 덧방 외곽 상자의 같은 비율 자리로 옮긴다
    #   (전에는 «가운데 세로 · 위아래 150 씩 뺀 길이»라 사이즈마다 길이가 변했고 2XL 도 원본과 11mm 달랐다)
    db["draw"].append(dict(DB["draw"][grain_index(DB)]))
    place_grain(DB, db)
    db["notch"].append([(SHX, by0 - SA), (SHX, by0 - SA + 5)])          # 소매 밑단 가운데 노치
    top_at = LineString([(SHX, -1e4), (SHX, 1e4)]).intersection(band.exterior)
    ty = max(p.y for p in getattr(top_at, "geoms", [top_at]))
    db["notch"].append([(SHX, ty + SA), (SHX, ty + SA - 5)])
    out["소매중심덧방"] = db
    # 소매 안 덧방 위치선 두 줄 다시
    #   옛 위치선은 «그레이딩 뒤» 모양으로 찾으면 안 된다 — field() 가 선을 기울이고(폭 0.5mm 초과) 3mm 넘게 옮겨
    #   S·M·5XL 은 두 줄, L~4XL 은 한 줄이 안 지워져 잔선으로 남았다(2026-10-19). grade_piece 는 draw 순서를 지키므로
    #   «2XL 원본 소매(SL)에서 몇 번째 선인가»로 찾아 같은 번호를 지운다.
    sl["draw"] = [d for i, d in enumerate(sl["draw"]) if i not in SL_BAND_IDX]
    for x in (bx0, bx1):
        seg = LineString([(x, -1e4), (x, 1e4)]).intersection(sl_poly)
        sl["draw"].append({"pts": list(seg.coords), "closed": False, "new": False, "nodes": 2})
    out["소매"] = sl
    LL = {k: L({"뒤": bk, "앞": fr}.get(k[0], sl)["sew"] if not k.startswith("소매") else sl["sew"], k) for k in IDX}
    fh, bh = LL["앞 밑단"], LL["뒤 밑단"]; R_HEM, R_CUFF = 928.0 / 1188.0, 220.0 / 320.0
    hem_len = R_HEM * (bh + 2 * fh)
    out["밑단립"] = rib_piece("밑단립", hem_len, 120.0, [R_HEM * fh, R_HEM * (fh + bh / 2), R_HEM * (fh + bh)])
    cuff = R_CUFF * LL["소매 밑단"]
    out["카우스"] = rib_piece("카우스", cuff, 130.0, [cuff / 2])
    neck = LL["뒤 목"] + 2 * LL["앞 목"] + 2 * LL["소매 목"]; cbn = neck / 2; off = LL["뒤 목"] / 2 + LL["소매 목 뒤쪽"]
    out["에리(립)"] = rib_piece("에리(립)", neck, 110.0, [cbn - off, cbn, cbn + off])
    for k in ("앞주머니구찌", "앞주머니감"): out[k] = copy.deepcopy(T0[k])
    nF_b, nF_s = notch_pos(fr["sew"], "앞 래글런"), notch_pos(sl["sew"], "소매 앞 래글런")
    nB_b, nB_s = notch_pos(bk["sew"], "뒤 래글런"), notch_pos(sl["sew"], "소매 뒤 래글런")
    chk = {"앞 래글런 몸판−소매": round(LL["앞 래글런"] - LL["소매 앞 래글런"], 2), "뒤 래글런 몸판−소매": round(LL["뒤 래글런"] - LL["소매 뒤 래글런"], 2),
           "앞 래글런 노치 차": [round(a - b, 2) for a, b in zip(nF_b, nF_s)], "뒤 래글런 노치 차": [round(a - b, 2) for a, b in zip(nB_b, nB_s)],
           "옆선 앞−뒤": round(LL["앞 옆선"] - LL["뒤 옆선"], 2), "소매 밑선 앞−뒤": round(LL["소매 앞 밑선"] - LL["소매 뒤 밑선"], 2),
           "에리=목둘레": round(neck, 1), "밑단립": round(hem_len, 1), "카우스": round(cuff, 1),
           "트루잉(소매 목앞·목뒤 추가 이동 mm)": [round(math.hypot(*adj["목앞"]), 2), round(math.hypot(*adj["목뒤"]), 2)]}
    bw = Polygon(bk["sew"]).buffer(0); fw = Polygon(fr["sew"]).buffer(0)
    yb = BHEM + GB["겨드랑이"][1] + R_BACK[s]["겨드랑이"][1] - 1; yf = FHEM + GF["겨드랑이"][1] + R_FRONT[s]["겨드랑이"][1] - 1
    chest = (LineString([(-1e5, yb), (1e5, yb)]).intersection(bw).length + 2 * LineString([(-1e5, yf), (1e5, yf)]).intersection(fw).length) / 2
    meas = {"총기장(뒤중심+밑단립)": round(GB["뒤목중심"][1] + R_BACK[s]["뒤목중심"][1] + 60, 1), "가슴폭(겨드랑이 단면)": round(chest, 1),
            "팔기장(어깨 노치~밑단+카우스)": round(GS["어깨"][1] + R_SLEEVE[s]["어깨"][1] + 65, 1)}
    rules = {"뒤판": {k: [round(v, 1) for v in R_BACK[s][k]] for k in R_BACK[s]}, "앞판": {k: [round(v, 1) for v in R_FRONT[s][k]] for k in R_FRONT[s]},
             "소매": {k: [round(R_SLEEVE[s][k][0] + SSG * adj.get(k, (0, 0))[0], 1), round(R_SLEEVE[s][k][1] + adj.get(k, (0, 0))[1], 1)]
                    for k in R_SLEEVE[s]}}
    return out, chk, meas, rules


# ════════ 하의 ════════
PF, PB = B0["앞판"], B0["뒤판"]
GPF, (PFX, PFY, PFS) = pants_pts(PF["sew"], False)
GPB, (PBX, PBY, PBS) = pants_pts(PB["sew"], True)
ZBOT, ZTOP = 40.0, 100.0                 # 밑단 스티치 구역 · 허리 고무줄 구역(길이 고정 — 기준점을 하나씩 더 둔다)


def pants_rule(R, G, STD, s, k):
    dx, dy = R[s][k]
    ratio = (G[k][0] / STD[k][0]) if abs(STD[k][0]) > 1 else 1.0     # 2XL 비율 유지: x 이동량 × (가스 거리 ÷ 표준 거리)
    return (dx * ratio, dy)


def pants_cards(p, G, R, STD, X0, Y0, sg, s):
    absP = lambda q: (X0 + sg * q[0], Y0 + q[1])
    rr = {k: pants_rule(R, G, STD, s, k) for k in G}
    D = lambda d: (sg * d[0], d[1])
    S = p["sew"]; Ymax = max(v[1] for v in S)
    cards = [(absP(G[k]), D(rr[k])) for k in G]
    # 옆선·안솔기 밑단 구역 위끝, 옆선·밑위 허리 구역 아래끝 — 각각 밑단·허리 규칙을 그대로 따른다
    def on_edge_near(a, b, y):
        seg = LineString([a, b]); line = LineString([(-1e5, y), (1e5, y)])
        cand = LineString(S + [S[0]]).intersection(line)
        pts = [cand] if cand.geom_type == "Point" else list(getattr(cand, "geoms", []))
        return min(pts, key=lambda q: seg.distance(q))
    sh, sw = absP(G["옆밑단"]), absP(G["허리옆"]); ih, cr = absP(G["안솔기밑단"]), absP(G["가랑이"]); wc = absP(G["허리중심"])
    q = on_edge_near(sh, sw, Y0 + ZBOT); cards.append(((q.x, q.y), D(rr["옆밑단"])))
    q = on_edge_near(sh, sw, sw[1] - ZTOP); cards.append(((q.x, q.y), D(rr["허리옆"])))
    q = on_edge_near(ih, cr, Y0 + ZBOT); cards.append(((q.x, q.y), D(rr["안솔기밑단"])))
    q = on_edge_near(cr, wc, wc[1] - ZTOP); cards.append(((q.x, q.y), D(rr["허리중심"])))
    return cards, rr


def band_grade(p, waist_dy):
    S = p["sew"]; y0 = min(v[1] for v in S); y1 = max(v[1] for v in S)
    fy = lambda y: y if y <= y0 + ZBOT else (y + waist_dy if y >= y1 - ZTOP else y + waist_dy * (y - y0 - ZBOT) / (y1 - ZTOP - y0 - ZBOT))
    m = lambda v: (v[0], fy(v[1]))
    q = dict(p); q["sew"] = [m(v) for v in S]; q["cut"] = [m(v) for v in p["cut"]]
    q["draw"] = [dict(d, pts=[m(v) for v in d["pts"]], **({"snap": m(d["snap"])} if d.get("snap") else {})) for d in p["draw"]]
    place_grain(p, q)                    # 옆배색 식서도 세로 늘림을 받지 않게 — 길이 고정·상대 위치만
    return q


def pants_len(P, kind):
    S = P; Y0 = min(v[1] for v in S); Y1 = max(v[1] for v in S); T = tips(S)
    lo = [i for i in range(len(S)) if S[i][1] < Y0 + 1 and i not in T]
    n = len(S)
    def path(a, b, expect):
        f, g = walk(n, a, b, True), walk(n, a, b, False); return min((f, g), key=lambda w: abs(seg_len(S, T, w) - expect))
    if kind == "앞옆선":
        top = max((i for i in range(n) if S[i][1] > Y1 - 5 and i not in T), key=lambda i: S[i][0]); return seg_len(S, T, path(top, max(lo, key=lambda i: S[i][0]), 1130))
    if kind == "뒤옆선":
        top = min((i for i in range(n) if S[i][1] > Y1 - 25 and i not in T), key=lambda i: S[i][0]); return seg_len(S, T, path(top, min(lo, key=lambda i: S[i][0]), 1130))
    if kind == "앞안솔기":
        return seg_len(S, T, path(min(lo, key=lambda i: S[i][0]), min((i for i in range(n) if i not in T), key=lambda i: S[i][0]), 755))
    if kind == "뒤안솔기":
        return seg_len(S, T, path(max(lo, key=lambda i: S[i][0]), max((i for i in range(n) if i not in T), key=lambda i: S[i][0]), 754))


def grade_bottom(s):
    cf_, rf = pants_cards(PF, GPF, R_PF, STD_PF2, PFX, PFY, PFS, s)
    pf, Df = grade_piece(PF, cf_)
    # 트루잉: 뒤판 가랑이 규칙을 안솔기 방향으로 고쳐 «안솔기 앞−뒤 차 = 2XL 원본 1.25mm» 를 지킨다
    d0 = pants_len(PF["sew"], "앞안솔기") - pants_len(PB["sew"], "뒤안솔기")
    ih, cr = (PBX + PBS * GPB["안솔기밑단"][0], PBY), (PBX + PBS * GPB["가랑이"][0], PBY + GPB["가랑이"][1])
    u = (cr[0] - ih[0], cr[1] - ih[1]); m = math.hypot(*u); u = (u[0] / m, u[1] / m)
    adj = (0.0, 0.0)
    for _ in range(12):
        cb_, rb = pants_cards(PB, GPB, R_PB, STD_PB2, PBX, PBY, PBS, s)
        cb_ = [(q, (d[0] + adj[0], d[1] + adj[1])) if math.dist(q, cr) < 0.5 else (q, d) for q, d in cb_]
        pb, Db = grade_piece(PB, cb_)
        e = (pants_len(pf["sew"], "앞안솔기") - pants_len(pb["sew"], "뒤안솔기")) - d0
        if abs(e) < 0.02: break
        adj = (adj[0] + u[0] * e, adj[1] + u[1] * e)
    rb = dict(rb); rb["가랑이"] = (rb["가랑이"][0] + PBS * adj[0], rb["가랑이"][1] + adj[1])
    out = {"앞판": pf, "뒤판": pb}
    out["앞옆배색"] = band_grade(B0["앞옆배색"], rf["허리옆"][1]); out["뒤옆배색"] = band_grade(B0["뒤옆배색"], rb["허리옆"][1])
    # 앞판 주머니 박스 — 크기 고정, 가운데만 따라감
    o = [d for d in PF["draw"] if d["nodes"] == 5 and 10 < bb(d["pts"])[2] - bb(d["pts"])[0] < 20][0]
    ob = bb(o["pts"]); c = ((ob[0] + ob[2]) / 2, (ob[1] + ob[3]) / 2); dc = field(PF["sew"], Df, c)
    for d in out["앞판"]["draw"]:
        if d["nodes"] == 5 and 10 < bb(d["pts"])[2] - bb(d["pts"])[0] < 22 and 140 < bb(d["pts"])[3] - bb(d["pts"])[1] < 160:
            d["pts"] = [(x + dc[0], y + dc[1]) for x, y in o["pts"]]
    # 스냅 9개 다시
    BF = B0["앞옆배색"]; y0 = min(v[1] for v in BF["sew"]); y1 = max(v[1] for v in BF["sew"])
    casing = min(bb(d["pts"])[1] for d in BF["draw"] if d["nodes"] == 2 and bb(d["pts"])[1] > y1 - 100) + rf["허리옆"][1]
    Y0, Y1 = y0 + 25.0 + 28.0, casing - 57.0; YS = [Y0 + (Y1 - Y0) * k / 8 for k in range(9)]
    sxF = [d for d in BF["draw"] if d.get("snap")][0]["snap"][0]; sxB = [d for d in B0["뒤옆배색"]["draw"] if d.get("snap")][0]["snap"][0]
    out["앞옆배색"]["draw"] = [d for d in out["앞옆배색"]["draw"] if not d.get("snap")] + \
        [{"pts": circle(sxF, y), "closed": True, "new": True, "nodes": 17, "snap": (sxF, y)} for y in YS]
    keep = [d for d in out["뒤옆배색"]["draw"] if not d.get("new")]
    for y in YS:
        keep += [{"pts": circle(sxB, y), "closed": True, "new": True, "nodes": 17, "snap": (sxB, y)},
                 {"pts": [(sxB - 5, y), (sxB + 5, y)], "closed": False, "new": True, "nodes": 2},
                 {"pts": [(sxB, y - 5), (sxB, y + 5)], "closed": False, "new": True, "nodes": 2}]
    out["뒤옆배색"]["draw"] = keep
    for k in ("앞구찌", "앞주머니감"): out[k] = copy.deepcopy(B0[k])
    E_ = {"앞옆선": pants_len(pf["sew"], "앞옆선"), "뒤옆선": pants_len(pb["sew"], "뒤옆선"), "앞안솔기": pants_len(pf["sew"], "앞안솔기"),
          "뒤안솔기": pants_len(pb["sew"], "뒤안솔기")}
    bandL = max(v[1] for v in out["앞옆배색"]["sew"]) - min(v[1] for v in out["앞옆배색"]["sew"])
    def maxw(P):
        pol = Polygon(P).buffer(0); y = pol.bounds[1]; best = 0
        while y < pol.bounds[3]:
            best = max(best, LineString([(-1e5, y), (1e5, y)]).intersection(pol).length); y += 1
        return best
    chk = {"앞판 옆선−앞배색": round(E_["앞옆선"] - bandL, 2), "뒤판 옆선−뒤배색": round(E_["뒤옆선"] - bandL, 2),
           "안솔기 앞−뒤": round(E_["앞안솔기"] - E_["뒤안솔기"], 2), "스냅 간격": round((Y1 - Y0) / 8, 1),
           "트루잉(뒤 가랑이 추가 이동 mm)": round(math.hypot(*adj), 2)}
    meas = {"바지 옆선(펼친)": round(bandL, 1), "허벅지 단면(가장 넓은 곳·배색 6cm 겹침)": round((maxw(pf["sew"]) + maxw(pb["sew"]) + 120) / 2, 1)}
    rules = {"앞판": {k: [round(v, 1) for v in rf[k]] for k in rf}, "뒤판": {k: [round(v, 1) for v in rb[k]] for k in rb}}
    return out, chk, meas, rules


from gas_warmup_meta import SPEC_T, SPEC_B                             # 장수·좌우 규칙
# DXF 조각 영문 이름표(R12 한글 깨짐) — 2026-10-19 까지 patlib.export 안에 박혀 있던 표를 그대로 옮겼다(내보내기 일반화)
GAS_EN = {"뒤판": "BACK", "앞판": "FRONT", "소매": "SLEEVE", "소매중심덧방": "SLEEVE CENTER OVERLAY", "카우스": "CUFF RIB", "밑단립": "HEM RIB",
          "에리(립)": "COLLAR RIB", "앞주머니구찌": "POCKET ZIP FACING", "앞주머니감": "POCKET BAG", "앞옆배색": "FRONT SIDE PANEL SNAP",
          "뒤옆배색": "BACK SIDE PANEL SNAP MATE", "앞구찌": "POCKET ZIP FACING"}

if __name__ == "__main__":
    OUT = ARGS.out; os.makedirs(OUT, exist_ok=True)
    only = [] if ARGS.no_export else (ARGS.sizes or SIZES)
    report, graded = {}, {}
    for s in SIZES:
        t, ct, mt, rt = grade_top(s); b, cbk, mb, rbk = grade_bottom(s)
        graded[s] = {"top": t, "bottom": b}
        report[s] = {"상의 검산": ct, "상의 치수": mt, "상의 규칙": rt, "하의 검산": cbk, "하의 치수": mb, "하의 규칙": rbk}
        if s in only:
            d = os.path.join(OUT, s); os.makedirs(d, exist_ok=True)
            leg = ["검정 재단선 · 파랑 점선 재봉선 · 초록 안쪽선 · 주황 2XL 수정 때 넣은 선 · 초록 일점쇄선 접는 선 · 짧은 선 노치",
                   f"점별 규칙 그레이딩(표준 웜업 CAD 기준점 이동량) · 2XL 기준 · {s}"]
            report[s]["상의 시트"] = export(expand(t, SPEC_T), f"상의_{s}", f"한국가스공사 페가수스 웜업 상의 · {s} · 1:1 mm (2026-10-19 점별 규칙 그레이딩)", leg, d, s,
                                           en_names=GAS_EN, subject=f"한국가스공사 웜업 {s} 패턴 1:1 mm")
            legb = ["검정 재단선 · 파랑 점선 재봉선 · 초록 안쪽선 · 주황 스냅 ○ · 스냅 짝 ○+",
                    f"점별 규칙 그레이딩(표준 웜업 CAD · x 이동량은 2XL 비율 유지) · 옆배색 폭·스냅 9개 고정 · {s}"]
            report[s]["하의 시트"] = export(expand(b, SPEC_B), f"하의_{s}", f"한국가스공사 페가수스 웜업 하의 · {s} · 1:1 mm (2026-10-19 점별 규칙 그레이딩)", legb, d, s,
                                           en_names=GAS_EN, subject=f"한국가스공사 웜업 {s} 패턴 1:1 mm")
        print(s, json.dumps({k: v for k, v in report[s].items() if "시트" not in k and "규칙" not in k}, ensure_ascii=False))
    json.dump(graded, open(os.path.join(OUT, "graded.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(report, open(os.path.join(OUT, "검산.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
