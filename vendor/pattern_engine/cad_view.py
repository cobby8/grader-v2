# 재단 패턴 «보기 전용» 묶음 만들기 — F10 1단계 (2026-10-19)
#
#   왜: 그레이더(grader-v2)의 «재단 패턴» 화면은 1단계에서 서버에 엔진을 두지 않는다(메모리·빌드 위험 0).
#       대신 여기(stizshop)에서 이미 만든 결과를 «화면용 그림 자료(view.json)» 와 «산출물 묶음(exports.zip)» 으로
#       묶어 올리면, 그레이더는 그림만 그리고 파일만 내려준다.
#
#   읽는 것 (만들지 않는다 — 이미 만든 결과만)
#     tmp/pattern-engine/gas-warmup/spec/spec_<사이즈>.json   조각 명세(F1) 9벌 — 재봉선·재단선·안쪽선·노치·구멍·기준점
#     tmp/pattern-engine/gas-warmup/graded/검산.json           맞물림 검산값(그레이딩이 낸 것) — 화면 검산표의 «정답»
#     tmp/pattern-engine/gas-warmup/graded/<사이즈>/          사이즈별 DXF · 1:1 PDF · .ai
#     tmp/pattern-engine/gas-warmup/2xl/                       2XL 수정본 DXF · 1:1 PDF · .ai
#     tmp/pattern-engine/aama/                                 (있으면) AAMA DXF · RUL · 전 사이즈 DXF · A4 분할 PDF
#
#   만드는 것 → tmp/pattern-engine/cad/<style_id>/  (상의·하의 따로)
#     view.json     화면용 — 점은 0.05mm 오차 안에서 줄이고(기준점·노치 점은 남김) 0.01mm 정수로 저장(압축). y 는 아래로(+) = SVG 좌표
#     exports.zip   산출물 — 안의 이름은 영문·숫자만(한글 이름은 manifest 의 orig 에). manifest.json 에 파일마다 sha256
#
#   ⚠️ gas_warmup_grade.py · gas_warmup_spec.py 는 import 하는 순간 명령줄 인자를 읽는다 → 여기서는 결과 JSON 만 읽는다.
#   실행(저장소 루트): python tools/pattern-engine/cad_view.py [--src <gas-warmup 폴더>] [--aama <aama 폴더>] [--out <폴더>]
import sys, os, json, math, hashlib, zipfile, argparse, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
from shapely.geometry import Polygon, LineString
from shapely.ops import polylabel

SIMPLIFY = 0.05                             # 점 줄이기 허용 오차(mm) — 선에서 0.05mm 안쪽으로만 벗어나는 점은 뺀다
Q = 0.01                                    # 좌표 저장 단위(mm) — 정수 × 0.01 = mm (0.05 격자로 반올림하면 곡선 길이가 0.1mm 쯤 부푼다 — 실측)
FORMAT = "stiz-cad-view"; FORMAT_VERSION = 1
TOL_CHECK = 0.1                             # 화면에서 다시 잰 길이 ↔ 검산.json 허용 차(mm)
GRADED = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
EDIT = "2XL-edit"                           # 2XL 수정본(그레이딩의 출발점) — 열쇠는 영문만
SIZE_LABEL = {EDIT: "2XL 수정본"}
ZIP_TIME = (2026, 1, 1, 0, 0, 0)            # ZIP 안 날짜 고정 → 같은 입력이면 같은 ZIP(지문이 같다)
SHEET_W = 2400; GAP = 60                    # 화면 배치(조각을 겹치지 않게 늘어놓는 폭·간격, mm)

GROUPS = {
    "top": {"key": "top", "ko": "상의", "en": "TOP", "style_id": "gas-warmup-2026-top"},
    "bottom": {"key": "bottom", "ko": "하의", "en": "BOTTOM", "style_id": "gas-warmup-2026-bottom"},
}
STYLE_NAME = "한국가스공사 페가수스 웜업 2026-27"


# ════════ 작은 도구 ════════
def q(v):
    """mm → 0.01mm 정수(압축)"""
    return int(round(v / Q))


def _rdp(P, eps):
    """열린 선 P 를 Douglas–Peucker 로 줄인다 — 양 끝은 남긴다"""
    if len(P) < 3: return list(P)
    (ax, ay), (bx, by) = P[0], P[-1]; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy)
    def d(p):
        if L < 1e-12: return math.dist(p, P[0])
        return abs(dy * (p[0] - ax) - dx * (p[1] - ay)) / L
    k = max(range(1, len(P) - 1), key=lambda i: d(P[i]))
    if d(P[k]) <= eps: return [P[0], P[-1]]
    return _rdp(P[:k + 1], eps)[:-1] + _rdp(P[k:], eps)


def simplify_ring(P, keep, eps=SIMPLIFY):
    """닫힌 고리 P 를 줄인다 — keep(고리 번호)은 반드시 남긴다. 반환: (새 고리, 옛 번호 → 새 번호)"""
    n = len(P); keep = sorted(set(keep) | {0})
    if len(keep) < 2: keep = sorted({0, n // 2})
    out, newidx = [], {}
    for a, b in zip(keep, keep[1:] + [keep[0] + n]):
        seg = [P[k % n] for k in range(a, b + 1)]
        simp = _rdp(seg, eps)
        newidx[a % n] = len(out); out.extend(simp[:-1])
    return out, newidx


def simplify_line(P, closed=False, eps=SIMPLIFY):
    if closed and len(P) > 3:
        return simplify_ring(P, [0, len(P) // 2], eps)[0]
    return _rdp(P, eps)


def ring_of(seam):
    """명세 재봉선 → 닫힌 고리(이웃 중복·닫는 중복 점 빼고) + 명세 번호 → 고리 번호"""
    pts, at = [], {}
    for k, s in enumerate(seam):
        p = (s["x"], s["y"])
        if pts and math.dist(pts[-1], p) < 1e-6:
            at[k] = len(pts) - 1; continue
        at[k] = len(pts); pts.append(p)
    if len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop(); at = {k: (v if v < len(pts) else 0) for k, v in at.items()}
    return pts, at


def path_len(P, i, j):
    """고리 P 에서 i→j 앞으로 걷는 길이(재봉선 따라)"""
    n = len(P); s = 0.0; k = i
    while k != j:
        s += math.dist(P[k], P[(k + 1) % n]); k = (k + 1) % n
    return s


def seam_len(P, i, j):
    """두 점 사이 재봉선 길이 — 두 방향 중 짧은 쪽(화면의 «길이 재기» 와 같은 규칙)"""
    return min(path_len(P, i, j), path_len(P, j, i))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def git_head():
    """엔진 판 표시 — 커밋 번호, 엔진 폴더에 커밋 안 된 변경(새 파일 포함)이 있으면 «+dirty» 를 붙인다.
    (커밋 번호만 보고 «그 판 코드로 만들었다» 고 믿으면 안 되는 경우를 화면에서 바로 알 수 있게)"""
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10)
        head = r.stdout.strip()
        if not head:
            return None
        st = subprocess.run(["git", "status", "--porcelain", "--", os.path.relpath(HERE, REPO)], cwd=REPO,
                            capture_output=True, text=True, timeout=20)
        return head + ("+dirty" if st.returncode != 0 or st.stdout.strip() else "")
    except Exception:
        return None


# ════════ 조각 하나 → 화면용(아직 mm, y 아래로) ════════
def piece_mm(pc):
    """명세 조각 → {seam, cut, internal, notches, holes, fold, nodes} — y 를 뒤집어(아래로 +) SVG 좌표로"""
    F = lambda p: (p[0], -p[1])
    P, at = ring_of(pc["seam"])
    seam = [F(p) for p in P]
    nodes = {s["node"]: at[k] for k, s in enumerate(pc["seam"]) if s.get("node")}
    notches = []
    for k, s in enumerate(pc["seam"]):                    # 재봉선 노치 = 바닥점에서 몸판 안쪽으로 깊이만큼
        nt = s.get("notch")
        if not nt: continue
        x, y = s["x"], s["y"]; u = nt["dir"]; d = nt["depth"]
        notches.append([F((x, y)), F((x + u[0] * d, y + u[1] * d))])
    for l in pc.get("notch_lines") or []:                  # 립 조각 등 «선으로 그린» 노치
        notches.append([F(l[0]), F(l[1])])
    internal, holes = [], []
    for d in pc.get("internal") or []:
        if d.get("snap"):                                  # 스냅 동그라미 = 구멍(중심 + 반지름)
            xs = [p[0] for p in d["pts"]]; ys = [p[1] for p in d["pts"]]
            c = F(d["snap"]); r = (max(xs) - min(xs) + max(ys) - min(ys)) / 4
            holes.append((c, r)); continue
        internal.append({"pts": [F(p) for p in d["pts"]], "closed": bool(d.get("closed")), "new": bool(d.get("new"))})
    fold = [F(p) for p in pc["fold"]] if pc.get("fold") else None
    # 점 줄이기 — 기준점·노치 바닥점은 남기고 그 사이만 0.05mm 오차로 줄인다(길이 재기 결과가 거의 안 바뀐다)
    keep = set(nodes.values()) | {at[k] for k, s in enumerate(pc["seam"]) if s.get("notch")}
    seam_s, remap = simplify_ring(seam, keep)
    return {"seam": seam_s, "cut": simplify_line([F(p) for p in pc["cut_builtin"]], True),
            "internal": [dict(d, pts=simplify_line(d["pts"], d["closed"])) for d in internal], "notches": notches,
            "holes": holes, "fold": fold, "nodes": {k: remap[v] for k, v in nodes.items()},
            "raw_seam": seam, "raw_nodes": nodes}                     # 줄이기 전(검산 대조용 — view.json 에는 안 넣는다)


def grain_of(seam):
    """식서 — 엔진에 식서 정보가 없어 «세로»(원단 길이 방향)로 둔다. aama.py 와 같은 규칙: 이름표 자리 세로선 가운데 60%"""
    poly = Polygon(seam).buffer(0); poly = max(getattr(poly, "geoms", [poly]), key=lambda g: g.area)
    a = polylabel(poly, tolerance=0.5)
    seg = LineString([(a.x, -1e5), (a.x, 1e5)]).intersection(poly)
    segs = [seg] if seg.geom_type == "LineString" else list(getattr(seg, "geoms", []))
    segs = [g for g in segs if g.geom_type == "LineString" and g.length > 1]
    if not segs: return None
    g = max(segs, key=lambda g: g.length); y0, y1 = g.coords[0][1], g.coords[-1][1]
    lo, hi = min(y0, y1), max(y0, y1); m = (hi - lo) * 0.2
    return [(a.x, lo + m), (a.x, hi - m)]


def bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def shift_piece(p, dx, dy):
    S = lambda pts: [(x + dx, y + dy) for x, y in pts]
    return dict(p, seam=S(p["seam"]), cut=S(p["cut"]), internal=[dict(d, pts=S(d["pts"])) for d in p["internal"]],
                notches=[S(l) for l in p["notches"]], holes=[((c[0] + dx, c[1] + dy), r) for c, r in p["holes"]],
                fold=S(p["fold"]) if p["fold"] else None, raw_seam=S(p["raw_seam"]))


def pack(p):
    """mm 조각 → 0.01mm 정수 납작 배열(압축)"""
    flat = lambda pts: [q(v) for xy in pts for v in xy]
    out = {"seam": flat(p["seam"]), "cut": flat(p["cut"]),
           "internal": [{"p": flat(d["pts"]), "c": 1 if d["closed"] else 0, **({"n": 1} if d["new"] else {})} for d in p["internal"]],
           "notches": [flat(l) for l in p["notches"]], "holes": [[q(c[0]), q(c[1]), q(r)] for c, r in p["holes"]],
           "fold": flat(p["fold"]) if p["fold"] else None, "nodes": p["nodes"]}
    if p.get("grain"): out["grain"] = flat(p["grain"])
    return out


def unpack_ring(flat):
    return [(flat[k] * Q, flat[k + 1] * Q) for k in range(0, len(flat), 2)]


# ════════ 검산표 정의 — 화면이 같은 두 점을 다시 잰다 ════════
#   part = (조각, 시작 기준점, 끝 기준점, 곱)   기준점 대신 "#번호" 면 고리 점 번호(립 조각처럼 기준점 없는 것)
def rib_edge(view_piece):
    """립 조각(직사각형): 윗변 양 끝 모서리 번호 — 그 사이 재봉선(짧은 쪽) = 립 길이. 노치 점이 끼어 있어도 된다"""
    P = unpack_ring(view_piece["seam"]); n = len(P)
    a = min(range(n), key=lambda i: (round(P[i][0], 1), P[i][1]))     # 왼쪽 위
    b = min(range(n), key=lambda i: (-round(P[i][0], 1), P[i][1]))    # 오른쪽 위
    return f"#{a}", f"#{b}"


def check_defs(group, pieces):
    if group == "top":
        rh, rc = rib_edge(pieces["밑단립"]), rib_edge(pieces["카우스"])
        return [
            {"key": "raglan_front", "label": "앞 래글런 몸판−소매", "kind": "pair", "ref_key": ("상의 검산", "앞 래글런 몸판−소매"),
             "a": ("몸판", [("앞판", "겨드랑이", "목옆", 1)]), "b": ("소매", [("소매", "겨드랑이앞", "목앞", 1)])},
            {"key": "raglan_back", "label": "뒤 래글런 몸판−소매", "kind": "pair", "ref_key": ("상의 검산", "뒤 래글런 몸판−소매"),
             "a": ("몸판", [("뒤판", "겨드랑이R", "목옆R", 1)]), "b": ("소매", [("소매", "겨드랑이뒤", "목뒤", 1)])},
            {"key": "side", "label": "옆선 앞−뒤", "kind": "pair", "ref_key": ("상의 검산", "옆선 앞−뒤"),
             "a": ("앞판", [("앞판", "겨드랑이", "옆밑단", 1)]), "b": ("뒤판", [("뒤판", "겨드랑이R", "옆밑단R", 1)])},
            {"key": "sleeve_under", "label": "소매 밑선 앞−뒤", "kind": "pair", "ref_key": ("상의 검산", "소매 밑선 앞−뒤"),
             "a": ("앞", [("소매", "겨드랑이앞", "밑단앞", 1)]), "b": ("뒤", [("소매", "겨드랑이뒤", "밑단뒤", 1)])},
            {"key": "neck", "label": "목둘레(= 에리 길이)", "kind": "sum", "ref_key": ("상의 검산", "에리=목둘레"),
             "parts": [("뒤판", "목옆L", "목옆R", 1), ("앞판", "목옆", "앞중심목", 2), ("소매", "목앞", "목뒤", 2)]},
            {"key": "hem_rib", "label": "밑단립 길이", "kind": "sum", "ref_key": ("상의 검산", "밑단립"), "parts": [("밑단립", rh[0], rh[1], 1)]},
            {"key": "cuff_rib", "label": "카우스 길이", "kind": "sum", "ref_key": ("상의 검산", "카우스"), "parts": [("카우스", rc[0], rc[1], 1)]},
        ]
    return [
        {"key": "pants_side_front", "label": "앞판 옆선−앞배색", "kind": "band", "ref_key": ("하의 검산", "앞판 옆선−앞배색"),
         "band_key": ("하의 치수", "바지 옆선(펼친)"), "a": ("앞판 옆선", [("앞판", "허리옆", "옆밑단", 1)])},
        {"key": "pants_side_back", "label": "뒤판 옆선−뒤배색", "kind": "band", "ref_key": ("하의 검산", "뒤판 옆선−뒤배색"),
         "band_key": ("하의 치수", "바지 옆선(펼친)"), "a": ("뒤판 옆선", [("뒤판", "허리옆", "옆밑단", 1)])},
        {"key": "inseam", "label": "안솔기 앞−뒤", "kind": "pair", "ref_key": ("하의 검산", "안솔기 앞−뒤"),
         "a": ("앞판", [("앞판", "안솔기밑단", "가랑이", 1)]), "b": ("뒤판", [("뒤판", "안솔기밑단", "가랑이", 1)])},
    ]


def measure_parts(pieces, parts, use_q=True):
    """parts 를 재고 합한다 — use_q=True 면 화면과 같은 0.05mm 점으로(화면이 내는 숫자와 같다)"""
    out, total = [], 0.0
    for name, a, b, mult in parts:
        vp = pieces[name]; Pq = unpack_ring(vp["seam"])
        ia = int(a[1:]) if a.startswith("#") else vp["nodes"][a]
        ib = int(b[1:]) if b.startswith("#") else vp["nodes"][b]
        P = Pq
        if not use_q:                                        # 줄이기 전 고리로 — 같은 자리 점 번호로 옮겨 잰다
            P, nodes = vp["_raw"]
            near = lambda i: min(range(len(P)), key=lambda k: math.dist(P[k], Pq[i]))
            ia = nodes[a] if not a.startswith("#") else near(ia)
            ib = nodes[b] if not b.startswith("#") else near(ib)
        L = seam_len(P, ia, ib); total += L * mult
        out.append({"piece": name, "from": a, "to": b, "mult": mult, "len": round(L, 2)})
    return out, total


def build_checks(group, pieces, ref_size):
    """ref_size: 검산.json 의 그 사이즈 칸(없으면 None — 2XL 수정본)"""
    rows = []
    for d in check_defs(group, pieces):
        ref = None
        if ref_size is not None:
            g, k = d["ref_key"]; ref = ref_size.get(g, {}).get(k)
        row = {"key": d["key"], "label": d["label"], "kind": d["kind"], "ref": ref,
               "ref_src": f"검산.json · {d['ref_key'][0]} · {d['ref_key'][1]}" if ref is not None else None}
        if d["kind"] == "pair":
            pa, la = measure_parts(pieces, d["a"][1]); pb, lb = measure_parts(pieces, d["b"][1])
            _, ra = measure_parts(pieces, d["a"][1], False); _, rb = measure_parts(pieces, d["b"][1], False)
            row.update(a={"label": d["a"][0], "parts": pa, "len": round(la, 2)}, b={"label": d["b"][0], "parts": pb, "len": round(lb, 2)},
                       value=round(la - lb, 2), raw=round(ra - rb, 3))
        elif d["kind"] == "sum":
            pa, la = measure_parts(pieces, d["parts"]); _, ra = measure_parts(pieces, d["parts"], False)
            row.update(parts=pa, value=round(la, 2), raw=round(ra, 3))
        else:                                                # band: 조각 옆선 − 배색 길이(배색은 직사각형 — 검산.json 의 펼친 길이)
            band = ref_size.get(d["band_key"][0], {}).get(d["band_key"][1]) if ref_size is not None else None
            pa, la = measure_parts(pieces, d["a"][1]); _, ra = measure_parts(pieces, d["a"][1], False)
            row.update(a={"label": d["a"][0], "parts": pa, "len": round(la, 2)}, band=band,
                       value=round(la - band, 2) if band is not None else None, raw=round(ra - band, 3) if band is not None else None,
                       band_src=f"검산.json · {d['band_key'][0]} · {d['band_key'][1]}" if band is not None else None)
        row["ok"] = None if (ref is None or row.get("value") is None) else abs(row["value"] - ref) <= TOL_CHECK
        rows.append(row)
    return rows


# ════════ 스타일 하나(상의 또는 하의) ════════
def size_ids():
    return GRADED + [EDIT]


def spec_path(src, sid):
    return os.path.join(src, "spec", "spec_2XL수정.json" if sid == EDIT else f"spec_{sid}.json")


def build_style(src, aama_dir, group, out_dir, when):
    G = GROUPS[group]
    ref_all = json.load(open(os.path.join(src, "graded", "검산.json"), encoding="utf-8"))
    specs = {sid: json.load(open(spec_path(src, sid), encoding="utf-8"))["garments"][group] for sid in size_ids()}
    names = list(specs["2XL"].keys())
    for sid, sp in specs.items():
        assert list(sp.keys()) == names or set(sp.keys()) == set(names), f"{sid} 조각 이름이 다르다"
    # ① 조각마다 mm 화면 좌표(y 아래로)
    mm = {sid: {n: piece_mm(specs[sid][n]) for n in names} for sid in size_ids()}
    # ② 조각 배치 — 사이즈 전부를 덮는 상자 기준으로 늘어놓는다(같은 조각은 사이즈마다 같은 이동 → 겹쳐 보기가 맞는다)
    ub = {}
    for n in names:
        boxes = [bbox(mm[sid][n]["cut"]) for sid in size_ids()]
        ub[n] = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    order = sorted(names, key=lambda n: (-(ub[n][3] - ub[n][1]), n))
    place, x, y, rowh = {}, 0.0, 0.0, 0.0
    for n in order:
        w, h = ub[n][2] - ub[n][0], ub[n][3] - ub[n][1]
        if x > 0 and x + w > SHEET_W: x, y, rowh = 0.0, y + rowh + GAP, 0.0
        place[n] = (x - ub[n][0], y - ub[n][1]); x += w + GAP; rowh = max(rowh, h)
    sheet = [0, 0, q(max(place[n][0] + ub[n][2] for n in names)), q(max(place[n][1] + ub[n][3] for n in names))]
    # ③ 사이즈마다 조각 묶기 + 검산
    sizes, check_report = {}, []
    for sid in size_ids():
        pcs = {}
        for n in names:
            p = shift_piece(mm[sid][n], *place[n]); p["grain"] = grain_of(p["seam"])
            vp = pack(p); vp["_raw"] = (p["raw_seam"], p["raw_nodes"])
            meta = specs[sid][n].get("meta") or {}
            vp.update(name=n, en=meta.get("en"), qty=len(meta.get("instances") or [1]),
                      instances=[{"name": i.get("name"), "side": i.get("side"), "mirror": bool(i.get("mirror")), "note": i.get("note")}
                                 for i in (meta.get("instances") or [])],
                      seam_len=round(sum(math.dist(p["seam"][k], p["seam"][(k + 1) % len(p["seam"])]) for k in range(len(p["seam"]))), 1))
            pcs[n] = vp
        checks = build_checks(group, pcs, None if sid == EDIT else ref_all.get(sid))
        for c in checks:
            check_report.append((sid, c["label"], c.get("value"), c.get("ref"), c.get("ok")))
        for vp in pcs.values(): vp.pop("_raw")
        meas = None if sid == EDIT else ref_all.get(sid, {}).get(f"{G['ko']} 치수")
        sizes[sid] = {"label": SIZE_LABEL.get(sid, sid), "pieces": [pcs[n] for n in order], "checks": checks, "measures": meas}
    # ④ 산출물 ZIP
    files = collect_files(src, aama_dir, G)
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, "exports.zip")
    manifest = {"style_id": G["style_id"], "made_at": when, "files": files}
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in files:
            zi = zipfile.ZipInfo(f["path"], ZIP_TIME); zi.compress_type = zipfile.ZIP_DEFLATED
            with open(f["_src"], "rb") as fh: z.writestr(zi, fh.read())
        zi = zipfile.ZipInfo("manifest.json", ZIP_TIME); zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, json.dumps({**manifest, "files": [{k: v for k, v in f.items() if k != "_src"} for f in files]},
                                  ensure_ascii=False, indent=1))
    view = {
        "format": FORMAT, "version": FORMAT_VERSION, "unit": "mm", "q": Q, "simplify": SIMPLIFY, "y_down": True,
        "style": {"id": G["style_id"], "name": f"{STYLE_NAME} · {G['ko']}", "garment": G["ko"], "group": group,
                  "base_size": "2XL", "sizes": size_ids(), "size_labels": {s: SIZE_LABEL.get(s, s) for s in size_ids()},
                  "graded_from": EDIT, "pieces": order},
        "source": {"engine": "stizshop tools/pattern-engine", "commit": git_head(), "made_at": when,
                   "inputs": ["gas-warmup/spec/spec_*.json", "gas-warmup/graded/검산.json"],
                   "note": "식서는 엔진에 정보가 없어 세로(원단 길이 방향)로 표시 — aama.py 와 같은 규칙"},
        "sheet": sheet, "sizes": sizes,
        "files": [{k: v for k, v in f.items() if k != "_src"} for f in files],
        "exports_zip": {"name": "exports.zip", "sha256": sha256(zpath), "bytes": os.path.getsize(zpath)},
        "tol_check": TOL_CHECK,
    }
    vpath = os.path.join(out_dir, "view.json")
    with open(vpath, "w", encoding="utf-8") as f:
        json.dump(view, f, ensure_ascii=False, separators=(",", ":"))
    return vpath, zpath, check_report, files


def collect_files(src, aama_dir, G):
    """사이즈별 DXF·1:1 PDF·.ai + (있으면) AAMA 묶음 — ZIP 안 이름은 영문·숫자·-·_·/ 만"""
    ko, en = G["ko"], G["en"]; out = []

    def add(kind, size, path, zname):
        if os.path.isfile(path):
            out.append({"kind": kind, "size": size, "path": zname, "orig": os.path.basename(path),
                        "bytes": os.path.getsize(path), "sha256": sha256(path), "_src": path})
    for sid in size_ids():
        if sid == EDIT:
            d, stem = os.path.join(src, "2xl"), f"{ko}_2XL_수정"
        else:
            d, stem = os.path.join(src, "graded", sid), f"{ko}_{sid}"
        add("dxf", sid, os.path.join(d, stem + ".dxf"), f"sizes/{sid}/{en}_{sid}.dxf")
        add("pdf", sid, os.path.join(d, stem + "_1대1.pdf"), f"sizes/{sid}/{en}_{sid}_1to1.pdf")
        add("ai", sid, os.path.join(d, stem + ".ai"), f"sizes/{sid}/{en}_{sid}.ai")
    if aama_dir and os.path.isdir(aama_dir):
        add("aama", "2XL", os.path.join(aama_dir, f"GAS_WARMUP_{en}_2XL.dxf"), f"aama/GAS_WARMUP_{en}_2XL.dxf")
        add("rul", None, os.path.join(aama_dir, f"GAS_WARMUP_{en}.rul"), f"aama/GAS_WARMUP_{en}.rul")
        add("allsizes", None, os.path.join(aama_dir, f"GAS_WARMUP_{en}_ALLSIZES.dxf"), f"aama/GAS_WARMUP_{en}_ALLSIZES.dxf")
        add("a4", "2XL", os.path.join(aama_dir, f"{ko}_2XL_A4분할.pdf"), f"aama/{en}_2XL_A4_tiles.pdf")
    for f in out:                                            # 한글이 ZIP 안 이름에 새지 않게(07-09 한글 열쇠 사고)
        assert all(c.isascii() for c in f["path"]), f["path"]
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="재단 패턴 보기 전용 묶음(view.json + exports.zip)")
    ap.add_argument("--src", default=os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup"))
    ap.add_argument("--aama", default=os.path.join(REPO, "tmp", "pattern-engine", "aama"))
    ap.add_argument("--out", default=os.path.join(REPO, "tmp", "pattern-engine", "cad"))
    ap.add_argument("--groups", nargs="*", default=["top", "bottom"])
    a = ap.parse_args(argv)
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    bad = 0
    for g in a.groups:
        vpath, zpath, rep, files = build_style(a.src, a.aama, g, os.path.join(a.out, GROUPS[g]["style_id"]), when)
        print(f"[{GROUPS[g]['ko']}] {vpath} ({os.path.getsize(vpath):,} B) · {zpath} ({os.path.getsize(zpath):,} B · 파일 {len(files)}개)")
        for sid, label, v, ref, ok in rep:
            if ok is False: bad += 1
            mark = "—" if ok is None else ("OK" if ok else "어긋남")
            print(f"   {sid:8s} {label:18s} 화면값 {v} · 검산 {ref} · {mark}")
    if bad:
        print(f"⚠️ 검산과 {TOL_CHECK}mm 넘게 어긋난 칸 {bad}개"); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
