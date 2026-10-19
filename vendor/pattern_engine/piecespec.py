# 조각 «명세» 모델 (차용 명세서 F1 — Seamly2D 의 «재봉선 + 점마다 속성» 방식)
#
#   옛 형식(legacy)  {cut, sew, draw, notch, fold}            — 재봉선에 노치가 5mm 뾰족점으로 박혀 있고 재단선은 «들고 다닌다»
#   명세(spec)       {seam: [점 + 속성], sa_builtin, cut_builtin, internal, notch_lines, fold, meta}
#
#   seam[k] = {"x", "y",
#              "node":  "겨드랑이" | None,                  # 기준점 이름 — 그레이딩 규칙의 열쇠(cardinal.py 와 같은 이름)
#              "notch": {"type": "slit", "depth": 5.0, "dir": [ux, uy]} | None,   # dir = 몸판 안쪽 방향 단위벡터
#              "sa":    9.0,                                # 이 점 → 다음 점 변의 시접(mm). 원본에서 잰 값
#              "corner": "hem_mirror" }                     # (선택) 이 점 모서리의 재단선 방식 — miter(기본)·hem_mirror·square (F2)
#   sa_builtin=True  → 재단선은 cut_builtin(원본 OptiCad) 그대로.  False → compute_cut() 으로 계산(F2)
#
#   to_legacy(from_legacy(p)) 는 원래 조각과 «점 하나까지» 같다(시험으로 지킨다).
import math, copy, re
from shapely.geometry import Polygon, LineString, Point

SPEC_VERSION = 1


def _tips(P):
    n = len(P)
    return {i for i in range(n) if 3 < math.dist(P[i - 1], P[i]) < 7 and 3 < math.dist(P[i], P[(i + 1) % n]) < 7
            and math.dist(P[i - 1], P[(i + 1) % n]) < 0.5}


def _unit(v):
    m = math.hypot(*v); return (v[0] / m, v[1] / m) if m else (0.0, 0.0)


def _clean_ring(P):
    """노치 뾰족점·되돌아온 점·0 길이 점을 뺀 닫힌 고리(재기용)"""
    T = _tips(P); out = []
    for i, v in enumerate(P):
        if i in T: continue
        if out and math.dist(out[-1], v) < 1e-6: continue
        out.append(tuple(v))
    if len(out) > 2 and math.dist(out[0], out[-1]) < 1e-6: out.pop()
    return out


# ── 옛 형식 → 명세 ──
def from_legacy(p, names=None, meta=None):
    """names: {"겨드랑이": (x, y), …} — 가장 가까운 재봉선 점에 기준점 이름을 붙인다"""
    S = [tuple(v) for v in p["sew"]]; T = _tips(S); n = len(S)
    R = {(i + 1) % n for i in T}                             # 뾰족점 바로 뒤 «되돌아온 점»(바닥점과 같은 자리)
    seam, at = [], {}
    for i in range(n):
        if i in T or i in R: continue
        at[i] = len(seam)
        seam.append({"x": S[i][0], "y": S[i][1], "node": None, "notch": None, "sa": None})
    for i in T:                                              # 뾰족점 = 바로 앞 점(바닥)의 노치 — 첫 점·끝 점에 걸쳐도 된다
        b, t = S[(i - 1) % n], S[i]
        k = at.get((i - 1) % n)
        if k is None: continue                               # 바닥이 다른 뾰족점의 되돌아온 점인 이상한 경우 — 버리지 않고 건너뜀
        seam[k]["notch"] = {"type": "slit", "depth": math.dist(b, t), "dir": list(_unit((t[0] - b[0], t[1] - b[1])))}
    # ⚠️ 뾰족점이 0번(또는 되돌아온 점이 0번)이면 to_legacy 는 같은 고리를 «다른 시작점»으로 내놓는다(모양은 같다).
    #    지금 자료(가스 135조각)에는 이런 경우가 없다 — 시험이 «점 하나까지 같음»을 지킨다
    # 변마다 시접 = 변 가운데에서 원본 재단선(홈 뺀 것)까지 거리
    cut_ring = _clean_ring(p["cut"]); cr = Polygon(cut_ring).exterior if len(cut_ring) > 2 else None
    for k in range(len(seam)):
        a, b = seam[k], seam[(k + 1) % len(seam)]
        if cr is None or math.dist((a["x"], a["y"]), (b["x"], b["y"])) < 1e-9:
            a["sa"] = None; continue
        m = ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2)
        a["sa"] = round(cr.distance(Point(m)) * 2) / 2          # 0.5mm 단위(곡선 변 가운데는 ±0.2 흔들린다)
    if names:
        for nm, q in names.items():
            k = min(range(len(seam)), key=lambda j: math.dist((seam[j]["x"], seam[j]["y"]), q))
            seam[k]["node"] = nm
    return {"version": SPEC_VERSION, "name": p.get("name"), "meta": dict(meta or {}),
            "seam": seam, "sa_builtin": True, "cut_builtin": [list(v) for v in p["cut"]],
            "internal": copy.deepcopy(p.get("draw") or []), "notch_lines": copy.deepcopy(p.get("notch") or []),
            "fold": copy.deepcopy(p.get("fold"))}


# ── 명세 → 옛 형식(지금 내보내기·그레이딩이 쓰는 모양) ──
def to_legacy(spec, sew_notch_spikes=True):
    sew = []
    for s in spec["seam"]:
        sew.append((s["x"], s["y"]))
        nt = s.get("notch")
        if nt and sew_notch_spikes:                         # OptiCad 원본처럼 재봉선 안쪽으로 뾰족점 (공장 CAD 관례)
            d = nt["depth"]; u = nt["dir"]
            sew.append((s["x"] + u[0] * d, s["y"] + u[1] * d)); sew.append((s["x"], s["y"]))
    cut = [tuple(v) for v in spec["cut_builtin"]] if spec.get("sa_builtin") else compute_cut(spec)
    out = {"name": spec.get("name"), "sew": sew, "cut": cut, "draw": copy.deepcopy(spec["internal"]),
           "notch": copy.deepcopy(spec["notch_lines"]), "fold": copy.deepcopy(spec.get("fold"))}
    return out


# ── 재단선 계산 (F2) — 변마다 시접만큼 바깥으로, 모서리는 점마다 고른 방식으로 잇는다 ──
#   seam[k]["corner"] (없으면 "miter")
#     "miter"       연장 교차 — 이웃 두 시접선을 늘려 만나는 점 (지금까지의 방식)
#     "hem_mirror"  밑단 대칭 — 시접이 큰 쪽 변이 «밑단»(접는 선 = 재봉선). 옆선 시접선을 접는 선까지 늘린 뒤
#                   접는 선 기준 거울로 꺾어 밑단 재단선까지 — 밑단을 접어 올리면 옆선 시접과 정확히 겹친다(공장 CAD 관례)
#     "square"      직각 — 옆선 시접선을 접는 선까지 늘린 뒤, 거기서 밑단 변에 «수직»으로 내려 밑단 재단선까지 (밑단 끝이 네모)
#   두 변의 시접이 같으면 hem_mirror·square 는 «어느 쪽이 밑단인지» 알 수 없어 miter 로 처리한다.
#   접는 선 변(sa=0)은 시접선 = 재봉선이라 그대로 남는다.
CORNER_TYPES = ("miter", "hem_mirror", "square")


def _seam_ring_full(spec):
    """명세 재봉선 → 닫힌 고리(0 길이·닫는 중복점 빼고) + 변마다 시접 + 점마다 모서리 방식 + 원래 seam 번호"""
    pts, sas, cor, idx = [], [], [], []
    for k, s in enumerate(spec["seam"]):
        q = (s["x"], s["y"])
        if pts and math.dist(pts[-1], q) < 1e-6:
            if s.get("corner") and not cor[-1]: cor[-1] = s["corner"]   # 같은 자리 겹친 점 — 모서리 지정은 살린다
            continue
        pts.append(q); sas.append(s.get("sa") if s.get("sa") is not None else 0.0)
        cor.append(s.get("corner")); idx.append(k)
    if len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop(); sas.pop(); c = cor.pop(); idx.pop()
        if c and not cor[0]: cor[0] = c
    return pts, sas, cor, idx


def seam_ring(spec):
    """명세 재봉선을 닫힌 고리로(0 길이·닫는 중복점 빼고) + 변마다 시접"""
    pts, sas, _, _ = _seam_ring_full(spec)
    return pts, sas


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _meet(p, d, q, e):
    """직선 p+t·d 와 q+s·e 의 만나는 점 — 나란하면 None"""
    den = _cross(d, e)
    if abs(den) < 1e-9: return None
    t = _cross((q[0] - p[0], q[1] - p[1]), e) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def _reflect(v, d):
    """벡터 v 를 단위 방향 d 의 직선에 대해 거울 반사"""
    k = v[0] * d[0] + v[1] * d[1]
    return (2 * k * d[0] - v[0], 2 * k * d[1] - v[1])


def _corner_pts(V, A, B, kind):
    """모서리 V — A = 들어오는 변(앞 변), B = 나가는 변. 각 변 = (시접선 위 한 점, 단위방향, 바깥 법선, 시접)
       돌려주는 값: 재단선에 넣을 점 목록(고리 순서대로) 또는 None(→ 마이터로)"""
    (pa, da, na, oa), (pb, db, nb, ob) = A, B
    if kind not in ("hem_mirror", "square") or abs(oa - ob) < 1e-9: return None
    hem_is_b = ob > oa                                        # 시접이 큰 쪽이 밑단
    # 접는 선 = 밑단 변의 재봉선(V 를 지나 밑단 방향). 옆 시접선이 접는 선과 만나는 점 F 에서 꺾는다
    (ps, ds), (ph, dh, nh, oh) = ((pa, da), (pb, db, nb, ob)) if hem_is_b else ((pb, db), (pa, da, na, oa))
    F = _meet(ps, ds, V, dh)
    if F is None or math.dist(F, V) > 10 * max(oa, ob): return None   # 거의 나란한 이상한 모양 — 마이터로
    if kind == "hem_mirror":                                  # 옆 시접선을 접는 선에 거울로 비춘 선 → 밑단 시접선과 만나는 G
        G = _meet(F, _reflect(ds, dh), ph, dh)
        if G is None or math.dist(G, V) > 10 * max(oa, ob): return None
    else:                                                     # square — F 에서 밑단에 수직으로 시접만큼 (밑단 시접선 위에 떨어진다)
        G = (F[0] + nh[0] * oh, F[1] + nh[1] * oh)
    return [F, G] if hem_is_b else [G, F]


def compute_cut(spec, miter_limit=4.0, default_sa=None):
    P, SA, COR, _ = _seam_ring_full(spec)
    if default_sa is not None: SA = [default_sa] * len(P)
    n = len(P)
    area2 = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
    sg = 1 if area2 > 0 else -1                              # 반시계면 바깥 법선 = (dy, -dx)
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]; d = _unit((b[0] - a[0], b[1] - a[1]))
        nrm = (sg * d[1], -sg * d[0]); o = SA[i]
        lines.append(((a[0] + nrm[0] * o, a[1] + nrm[1] * o), (b[0] + nrm[0] * o, b[1] + nrm[1] * o), d, o, nrm))
    out = []
    for i in range(n):
        (p1, p2, d1, o1, n1), (q1, q2, d2, o2, n2) = lines[i - 1], lines[i]
        special = _corner_pts(P[i], (p1, d1, n1, o1), (q1, d2, n2, o2), COR[i] or "miter")
        if special:                                          # 밑단 대칭·직각 — 두 점으로 꺾는다
            out.extend(special); continue
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:                                  # 거의 나란함 — 그대로 잇는다
            out.append(q1); continue
        t = ((q1[0] - p1[0]) * d2[1] - (q1[1] - p1[1]) * d2[0]) / den
        x = (p1[0] + d1[0] * t, p1[1] + d1[1] * t)
        if math.dist(x, P[i]) > miter_limit * max(o1, o2, 1e-6):   # 너무 뾰족하면 잘라 두 점(베벨)
            out.append(p2); out.append(q1)
        else:
            out.append(x)
    return out


def mark_hem_corners(spec, hem_sa, kind="hem_mirror"):
    """시접이 hem_sa 인 변(밑단)의 양끝 모서리에 모서리 방식을 붙인다 — 이웃 변 시접이 다른 곳만. 붙인 seam 번호 목록을 돌려준다"""
    P, SA, _, IDX = _seam_ring_full(spec); n = len(P); done = []
    for i in range(n):
        a, b = SA[i - 1], SA[i]                              # 들어오는 변 · 나가는 변 시접
        if (a == hem_sa) != (b == hem_sa):
            spec["seam"][IDX[i]]["corner"] = kind; done.append(IDX[i])
    return done


def _local_gap(spec, V, R, orig):
    """모서리 V 둘레(반지름 R) 안에서 계산 재단선 ↔ 원본 재단선 최대 어긋남(mm) — 양쪽 점을 서로에게 잰다"""
    cc = compute_cut(spec); ca = Polygon(cc).exterior
    g = [orig.distance(Point(q)) for q in cc if math.dist(q, V) < R]
    g += [ca.distance(Point(q)) for q in orig.coords if math.dist(q, V) < R]
    return max(g) if g else 0.0


def corner_gap(spec, k, radius=None):
    """seam[k] 모서리 둘레에서 계산 재단선 ↔ 원본 재단선 최대 어긋남(mm) — 지금 붙어 있는 모서리 방식 그대로 잰다"""
    orig = Polygon(_clean_ring(spec["cut_builtin"])).exterior
    s = spec["seam"][k]; P, SA, _, IDX = _seam_ring_full(spec); i = IDX.index(k)
    return _local_gap(spec, (s["x"], s["y"]), radius or 3 * max(SA[i - 1], SA[i], 1.0), orig)


def read_corners(spec, hem_sa=None, kinds=("hem_mirror", "square"), radius=None):
    """원본 재단선(cut_builtin)에서 모서리 방식을 «읽는다» — 시접(from_legacy)을 원본에서 읽는 것과 같은 생각.
       이웃 두 변 시접이 다른 모서리마다(hem_sa 를 주면 그 시접 변의 양끝만) miter + kinds 를 다 계산해 원본에 가장 가까운 것을 붙인다.
       0.05mm 안으로 비기면 miter(기본)를 남긴다. 돌려주는 값: {seam 번호: (방식, 그 방식의 어긋남, miter 의 어긋남)}"""
    if not spec.get("cut_builtin"): return {}
    orig = Polygon(_clean_ring(spec["cut_builtin"])).exterior
    P, SA, _, IDX = _seam_ring_full(spec); out = {}
    for i in range(len(P)):
        a, b = SA[i - 1], SA[i]
        if a == b or (hem_sa is not None and hem_sa not in (a, b)): continue
        s = spec["seam"][IDX[i]]; R = radius or 3 * max(a, b, 1.0)
        tried = {}
        for kind in ("miter",) + tuple(kinds):
            s["corner"] = kind; tried[kind] = _local_gap(spec, P[i], R, orig)
        best = min(tried, key=lambda k: (tried[k] + (0.05 if k != "miter" else 0)))   # 비기면 기본
        s["corner"] = best
        out[IDX[i]] = (best, round(tried[best], 2), round(tried["miter"], 2))
    return out


def compare_cut(spec):
    """계산한 재단선 vs 원본 재단선(홈 뺀 것) — 최대 어긋남(mm)과 그 자리"""
    a = Polygon(compute_cut(spec)).exterior; b = Polygon(_clean_ring(spec["cut_builtin"])).exterior
    h = a.hausdorff_distance(b)
    # 어긋남이 큰 자리 — 계산 재단선 점 중 원본에서 가장 먼 점
    far = max(compute_cut(spec), key=lambda q: b.distance(Point(q)))
    return round(h, 2), [round(far[0], 1), round(far[1], 1)]


def sa_summary(spec):
    """변 시접 값 → 그 값을 가진 재봉선 길이 합(mm)"""
    P, SA = seam_ring(spec); out = {}
    for i in range(len(P)):
        L = math.dist(P[i], P[(i + 1) % len(P)]); k = SA[i]
        out[k] = out.get(k, 0.0) + L
    return {k: round(v, 1) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


NOTCH_TYPES = ("slit", "T", "V", "U", "diamond", "castle")   # Seamly2D 의 6종(일자·T·V·U·다이아몬드·성곽)


# ════════ F4 내부선·구멍 · F5 식서·라벨 · F6 뒤집기·접기 (2026-10-19) ════════
#   명세에 «값만» 붙이는 속성 — from_legacy·to_legacy 는 손대지 않는다(왕복 «점 하나까지 같음» 유지)
#     internal[j]["cut"] = True          이 안쪽선은 «자르는 선»(주머니 입구 박스 같은 트임) — 없으면 그리기만 하는 선
#     internal[j]["kind"]                스냅 동그라미(snap)의 구멍 종류 — 없으면 «스냅»
#     drills = [{"pt": [x, y], "kind": "스냅|짝|아일렛|단추"}]   (선택) 있으면 이것이 구멍 목록 전부(안쪽선 snap 대신)
#     grain = {"from": [x, y], "to": [x, y], "arrow": "both|one", "rib": bool}   (선택) 없으면 세로(원단 길이 방향)
#             rib=True → «골 세로 · 늘어나는 방향 가로» 표기(립·시보리)
#     label = {"template": "{조각} {사이즈} …"}   자리표시자는 LABEL_KEYS 만
#     flip  = "금지" | "허용"            없으면 좌우(R/L) 조각은 금지·나머지 허용(marker.py 와 같은 규칙)
#     cut_on_fold = True | {"keep": "+"|"-"}   접어 재단 — 반쪽만 그리고 접는 선(대칭축) 표시. «+» = 오른쪽(x 큰 쪽)을 남긴다
clean_ring = _clean_ring                                     # 공개 이름 — aama.py 가 재단선의 노치 뾰족점을 뺄 때 쓴다

DRILL_KINDS = ("스냅", "짝", "아일렛", "단추")
FLIP_TYPES = ("금지", "허용")
LABEL_KEYS = ("조각", "사이즈", "장수", "좌우", "원단", "색", "팀", "주문번호")
DEFAULT_LABEL = "{조각} {사이즈} {좌우} {장수}장 · {원단} {색} · {팀} {주문번호}"
_PH = re.compile(r"\{([^{}]*)\}")


def label_keys(template):
    """라벨 틀의 자리표시자 목록(나온 순서)"""
    return _PH.findall(template or "")


def fill_label(template, values):
    """라벨 틀 채우기 — values 는 부르는 쪽이 준다(🚫 여기서 운영 DB 를 읽지 않는다).
       없는 값은 빈칸으로 두고, 빈칸 때문에 생긴 겹 공백·떠도는 «·» 를 정리한다. 모르는 자리표시자는 오류(오타를 잡으려고)"""
    def rep(m):
        k = m.group(1)
        if k not in LABEL_KEYS: raise ValueError(f"라벨 자리표시자 {{{k}}} — {', '.join(LABEL_KEYS)} 중 하나")
        v = (values or {}).get(k)
        return "" if v is None else str(v)
    s = _PH.sub(rep, template or "")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?:\s*·\s*)+", " · ", s)                   # 값이 빠져 «· ·» 가 된 자리를 하나로
    return s.strip(" ·")


def spec_drills(spec):
    """구멍 목록 [{"pt": [x, y], "kind": 종류}] — 명세 drills 가 있으면 그것, 없으면 안쪽선의 스냅 동그라미(snap)에서"""
    if spec.get("drills") is not None:
        return [{"pt": [float(d["pt"][0]), float(d["pt"][1])], "kind": d.get("kind") or "스냅"} for d in spec["drills"]]
    return [{"pt": [float(d["snap"][0]), float(d["snap"][1])], "kind": d.get("kind") or "스냅"}
            for d in spec.get("internal") or [] if d.get("snap")]


def flip_rule(spec, side=""):
    """뒤집기 규칙 — 명세 flip 이 있으면 그것, 없으면 좌우 조각은 금지(뒤집으면 R 이 L 로 바뀐다)·나머지 허용"""
    return spec.get("flip") or ("금지" if side else "허용")



def validate(spec):
    """명세 검사 — 문제를 글로 돌려준다(예외로 멈추지 않는다)"""
    errs = []
    if not isinstance(spec, dict): return ["명세가 dict 가 아님"]
    if spec.get("version") != SPEC_VERSION: errs.append("version")
    seam = spec.get("seam")
    if not isinstance(seam, list) or len(seam) < 3: return errs + ["seam 3점 미만"]
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    for k, s in enumerate(seam):
        if not (num(s.get("x")) and num(s.get("y"))): errs.append(f"seam[{k}] 좌표"); continue
        nt = s.get("notch")
        if nt:
            if nt.get("type") not in NOTCH_TYPES: errs.append(f"seam[{k}] 노치 종류 {nt.get('type')}")
            if not (num(nt.get("depth")) and nt["depth"] > 0): errs.append(f"seam[{k}] 노치 깊이")
            u = nt.get("dir") or [0, 0]
            if not (len(u) == 2 and all(num(c) for c in u) and abs(math.hypot(*u) - 1) < 1e-3): errs.append(f"seam[{k}] 노치 방향")
            # (선택, F3) 개수 1~3 · 폭 · 간격 — 모양은 notchshapes.py 가 만든다
            if "count" in nt and (type(nt["count"]) is not int or nt["count"] not in (1, 2, 3)): errs.append(f"seam[{k}] 노치 개수 {nt['count']!r}")
            for key in ("width", "gap"):
                if key in nt and not (num(nt[key]) and nt[key] > 0): errs.append(f"seam[{k}] 노치 {key} {nt[key]!r}")
        sa = s.get("sa")
        if sa is not None and not (num(sa) and 0 <= sa <= 60): errs.append(f"seam[{k}] 시접 {sa!r}")
        if s.get("corner") is not None and s.get("corner") not in CORNER_TYPES: errs.append(f"seam[{k}] 모서리 방식 {s.get('corner')!r}")
    if not spec.get("sa_builtin"):                             # 계산 재단선이면 «길이가 있는» 변마다 시접이 있어야
        for k, s in enumerate(seam):
            q = seam[(k + 1) % len(seam)]
            if s.get("sa") is None and num(s.get("x")) and num(q.get("x")) and math.dist((s["x"], s["y"]), (q["x"], q["y"])) > 1e-6:
                errs.append(f"seam[{k}] 계산 재단선인데 시접 빈 변")
    errs += _validate_extras(spec, num)
    return errs


def _validate_extras(spec, num):
    """F4~F6 속성 검사 — 없으면 아무 말도 안 한다(선택 속성)"""
    errs = []
    pt = lambda v: isinstance(v, (list, tuple)) and len(v) == 2 and all(num(c) for c in v)
    for j, d in enumerate(spec.get("internal") or []):
        if "cut" in d and not isinstance(d["cut"], bool): errs.append(f"internal[{j}] cut {d['cut']!r}")
        if d.get("kind") is not None and d["kind"] not in DRILL_KINDS: errs.append(f"internal[{j}] 구멍 종류 {d['kind']!r}")
    if spec.get("drills") is not None:
        if not isinstance(spec["drills"], list): errs.append("drills 가 목록이 아님")
        else:
            for j, d in enumerate(spec["drills"]):
                if not (isinstance(d, dict) and pt(d.get("pt"))): errs.append(f"drills[{j}] 자리"); continue
                if d.get("kind", "스냅") not in DRILL_KINDS: errs.append(f"drills[{j}] 구멍 종류 {d.get('kind')!r}")
    g = spec.get("grain")
    if g is not None:
        if not isinstance(g, dict): errs.append("grain 이 dict 가 아님")
        else:
            if ("from" in g) != ("to" in g): errs.append("grain from·to 는 함께")
            if "from" in g and "to" in g and not (pt(g["from"]) and pt(g["to"]) and math.dist(g["from"], g["to"]) > 1): errs.append("grain 자리")
            if g.get("arrow", "both") not in ("both", "one"): errs.append(f"grain arrow {g.get('arrow')!r}")
    lb = spec.get("label")
    if lb is not None:
        bad = [k for k in label_keys(lb.get("template") if isinstance(lb, dict) else None) if k not in LABEL_KEYS]
        if not isinstance(lb, dict) or not isinstance(lb.get("template"), str): errs.append("label.template 글자 아님")
        elif bad: errs.append(f"label 자리표시자 {bad}")
    if spec.get("flip") is not None and spec["flip"] not in FLIP_TYPES: errs.append(f"flip {spec['flip']!r}")
    f = spec.get("cut_on_fold")
    if f not in (None, False, True) and not (isinstance(f, dict) and f.get("keep", "+") in ("+", "-")): errs.append(f"cut_on_fold {f!r}")
    return errs
