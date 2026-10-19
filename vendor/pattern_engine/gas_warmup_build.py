# 한국가스공사 페가수스 웜업 2XL 패턴 수정 (2026-10-19 사장님 결정)
#   원본: 카톡 «한국가스공사상의(26-09-21).ai» · «한국가스공사 하의(26-09-22).ai» (OptiCad Adobe Export, 2XL 한 사이즈)
#   원본 조각의 선은 한 점도 옮기지 않는다 — 더하고(주머니·스냅·립 에리) 빼고(뒷주머니) 이름·장수만 바꾼다.
#   결과: <out>/상의_2XL_수정.{ai,dxf} · _1대1.pdf · _미리보기.png, 하의 같은 꼴, check.json(검산 수치)
#   실행: python tools/pattern-engine/gas_warmup_build.py [<원본 상의.ai> <원본 하의.ai> <out 폴더>]
#         인자가 없으면 fixtures/gas-warmup-2026 → tmp/pattern-engine/gas-warmup/2xl
import sys, os, json, math
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opticad import parse
import ezdxf, fitz
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import polylabel

MM = 25.4 / 72
SA = 9.0            # 원본 시접 실측: 재단선-재봉선 9mm (밑단립 946-928, 구찌 48-30)
R_SNAP = 7.0        # 원본 스냅 동그라미 지름 14mm


# ── 원본 읽기: 베지어를 잘게 펴서 mm, y 위쪽(+) 그대로 ──
def flat(seg):
    P = []
    for s in seg:
        if s[0] in "ML":
            P.append((s[1] * MM, s[2] * MM))
        else:
            x0, y0 = P[-1]; x1, y1, x2, y2, x3, y3 = [v * MM for v in s[1:]]
            for k in range(1, 17):
                t = k / 16; a = (1 - t) ** 3; b = 3 * (1 - t) ** 2 * t; c = 3 * (1 - t) * t * t; d = t ** 3
                P.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
    return P


def load(path):
    _, items = parse(path)
    pcs = {}
    for i in items:
        if i["t"] != "path": continue
        lay = i["layers"][-1]; n = i.get("note")
        p = pcs.setdefault(n, {"name": n, "cut": None, "sew": None, "draw": [], "notch": [], "fold": None})
        pts = flat(i["seg"])
        if lay == "CUT" and p["cut"] is None: p["cut"] = pts
        elif lay == "SEW" and p["sew"] is None: p["sew"] = pts
        elif lay == "DRAW": p["draw"].append({"pts": pts, "closed": i.get("closed", False), "new": False, "nodes": len(i["seg"])})
    return pcs


def bb(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def circle(cx, cy, r=R_SNAP, n=32):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def outline(poly):
    return list(poly.exterior.coords)[:-1]


HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
FIX = os.path.join(HERE, "fixtures", "gas-warmup-2026")
SRC_TOP, SRC_BOT, OUT = (sys.argv[1:4] if len(sys.argv) >= 4 else
                         (os.path.join(FIX, "gas_top_2xl.ai"), os.path.join(FIX, "gas_bottom_2xl.ai"),
                          os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup", "2xl")))
T, B = load(SRC_TOP), load(SRC_BOT)
CHECK = {}

# ════════════════ 상의 ════════════════
# ① 앞주머니 — 하의 앞주머니와 같은 방식(입구 150 × 15 박스 + 구찌 30×150 + 주머니감)
#    위치(시안 실측): 입구 가운데선이 옆선 재봉선에서 몸 안쪽 55mm, 입구 아래끝이 밑단 재봉선(=밑단립 다는 선) 위 45mm, 옆선과 나란히
F = T["앞판"]
Fs = Polygon(F["sew"])
hem_y = bb(F["sew"])[1]                                   # 밑단 재봉선 높이


def side_x(y):                                            # 그 높이에서 옆선(왼쪽 끝) 재봉선 x
    seg = LineString([(-1e5, y), (1e5, y)]).intersection(Fs)
    return seg.bounds[0]


PK_LOW, PK_LEN, PK_IN, PK_W = 45.0, 150.0, 55.0, 15.0
y1, y2 = hem_y + PK_LOW, hem_y + PK_LOW + PK_LEN
x1, x2 = side_x(y1) + PK_IN, side_x(y2) + PK_IN
pk = [(x1 - PK_W / 2, y1), (x1 + PK_W / 2, y1), (x2 + PK_W / 2, y2), (x2 - PK_W / 2, y2)]
F["draw"].append({"pts": pk, "closed": True, "new": True, "nodes": 5})
CHECK["상의 주머니 입구"] = {"길이": round(math.dist((x1, y1), (x2, y2)), 1), "옆선에서": PK_IN, "밑단선 위": PK_LOW,
                        "앞중심(지퍼)선까지": round(bb(F["sew"])[2] - (x1 + x2) / 2, 1)}

# 구찌 — 하의 «앞구찌» 를 그대로 복사 (재봉 30×150 · 재단 48×168 · 안쪽 선 2줄)
g = B["앞구찌"]
T["앞주머니구찌"] = {"name": "앞주머니구찌", "cut": list(g["cut"]), "sew": list(g["sew"]),
                 "draw": [dict(d) for d in g["draw"]], "notch": [], "fold": None}

# 주머니감 — 입구 둘레로 옆선 쪽 20 · 위아래 20 · 앞중심 쪽 150, 모서리 R30. 재봉 170 × 190
bag = box(-20, -20, 150, 170)
bag = bag.buffer(-30).buffer(30)
P_ = {"name": "앞주머니감", "cut": outline(bag.buffer(SA)), "sew": outline(bag), "draw": [], "notch": [], "fold": None}
P_["draw"].append({"pts": rect(-PK_W / 2, 0, PK_W / 2, PK_LEN), "closed": True, "new": True, "nodes": 5})   # 입구 맞춤 박스
P_["draw"].append({"pts": [(75, 10), (75, 140)], "closed": False, "new": True, "nodes": 2})                # 식서
T["앞주머니감"] = P_
CHECK["상의 주머니감"] = {"재봉 가로": 170, "재봉 세로": 190, "옆선까지 여유": round(PK_IN - 20, 1),
                      "앞중심선까지 여유": round(bb(F["sew"])[2] - (x1 + x2) / 2 - 150, 1), "밑단선까지 여유": PK_LOW - 20}

# ② 에리 → 립(시보리) 접어 2겹. 길이 = 원본 에리 목선 길이(=몸판 목둘레), 완성 높이 55 그대로
E = T["에리"]
E_bb = bb(E["sew"])
# 원본 에리 목선(곡선 쪽) 길이 = 변 실측 (112.4 + 163.8) × 2 — 몸판 목둘레 145 + 114.8×2 + 89×2 = 552.6 과 0.2mm 차
L_NECK = round(2 * (112.4 + 163.8), 1)
H_FIN = 55.0
rib = box(0, 0, L_NECK, 2 * H_FIN)
R = {"name": "에리(립)", "cut": outline(rib.buffer(SA, join_style=2)), "sew": outline(rib), "draw": [], "notch": [], "fold": None}
R["fold"] = [(-SA, H_FIN), (L_NECK + SA, H_FIN)]
cb = L_NECK / 2
for x in (cb - 112.4, cb, cb + 112.4):                    # 원본 에리 노치: 뒤중심 · 뒤중심±112.4(=소매 윗점)
    R["notch"].append([(x, -SA), (x, -SA + 5)])
    R["notch"].append([(x, 2 * H_FIN + SA), (x, 2 * H_FIN + SA - 5)])
R["draw"].append({"pts": [(40, 15), (40, 95)], "closed": False, "new": True, "nodes": 2})                  # 식서 = 립 골 방향(세로)
del T["에리"]
T["에리(립)"] = R
CHECK["에리 립"] = {"목둘레(몸판 합)": round(145.0 + 2 * 114.8 + 2 * 89.0, 1), "립 길이": L_NECK, "완성 높이": H_FIN, "재봉 높이(펼침)": 2 * H_FIN}

QTY_T = {"뒤판": (1, ""), "앞판": (2, "좌우 대칭"), "소매": (2, "좌우 대칭"), "소매중심덧방": (2, "좌우 대칭"),
         "카우스": (2, "립"), "밑단립": (1, "립 · 접어 2겹"), "에리(립)": (1, "립 · 접어 2겹"),
         "앞주머니구찌": (2, ""), "앞주머니감": (4, "주머니 하나에 2장 · 안감")}

# ════════════════ 하의 ════════════════
REN = {"@Piece2": "앞판", "Piece2": "뒤판", "사리드배색": "앞옆배색", "@사리드배색": "뒤옆배색", "DKVWNAJSL": "앞주머니감", "앞구찌": "앞구찌"}
# ③ 뒷주머니 삭제 — 뒤구찌 · 뒤주머니무가데 조각, 뒤판의 주머니 박스(5점 · 290mm · 허리 아래)
del B["뒤구찌"], B["뒤주머니무가데"]
before = len(B["Piece2"]["draw"])
B["Piece2"]["draw"] = [d for d in B["Piece2"]["draw"]
                       if not (d["nodes"] == 5 and bb(d["pts"])[1] > 950 * 1 and 1240 < bb(d["pts"])[0] < 1260)]
CHECK["뒷주머니 박스 삭제"] = before - len(B["Piece2"]["draw"])

# ④ 스냅 — 원본 7개(밑단~가랑이, 맨 아래가 밑단 스티치 위) → 9개(밑단 스티치 위 21mm ~ 허리 고무줄 스티치 아래 50mm)
FB, BB_ = B["사리드배색"], B["@사리드배색"]
old = [d for d in FB["draw"] if d["nodes"] == 17]
sx = sum((bb(d["pts"])[0] + bb(d["pts"])[2]) / 2 for d in old) / len(old)
FB["draw"] = [d for d in FB["draw"] if d["nodes"] != 17]
fb = bb(FB["sew"])
hemline = fb[1] + 25.0                                    # 밑단 스티치(원본 선 47/52 중 위쪽 = 재봉 밑선 +25)
casing = min(bb(d["pts"])[1] for d in FB["draw"] if d["nodes"] == 2 and bb(d["pts"])[1] > fb[3] - 100)   # 허리 고무줄 맨 아래 스티치
Y0, Y1, N = hemline + 28.0, casing - 57.0, 9
YS = [Y0 + (Y1 - Y0) * k / (N - 1) for k in range(N)]
for y in YS:
    FB["draw"].append({"pts": circle(sx, y), "closed": True, "new": True, "nodes": 17, "snap": (sx, y)})
# 뒤옆배색 스냅 짝: 앞옆배색이 뒤옆배색의 바깥(트인 쪽) 60mm 를 완전히 덮는다고 보고, 같은 거리에 짝을 찍는다
#   앞옆배색: 앞판과 꿰매는 쪽 = 원본 배치에서 앞판(@Piece2)에 붙어 있던 왼쪽 변(x 최소) → 스냅은 그 변에서 (sx - fb[0])
#   뒤옆배색: 뒤판과 꿰매는 쪽 = 뒤판(Piece2) 쪽 오른쪽 변(x 최대) → 트인 쪽 = 왼쪽 변(x 최소)
bbk = bb(BB_["sew"])
d_seam = sx - fb[0]
kx = bbk[0] + d_seam
for y in YS:
    BB_["draw"].append({"pts": circle(kx, y), "closed": True, "new": True, "nodes": 17, "snap": (kx, y)})
    BB_["draw"].append({"pts": [(kx - 5, y), (kx + 5, y)], "closed": False, "new": True, "nodes": 2})
    BB_["draw"].append({"pts": [(kx, y - 5), (kx, y + 5)], "closed": False, "new": True, "nodes": 2})
CHECK["스냅"] = {"개수(한쪽)": N, "간격": round((Y1 - Y0) / (N - 1), 1), "맨아래 중심-밑단스티치": round(Y0 - hemline, 1),
               "맨위 중심-허리스티치": round(casing - Y1, 1), "앞옆배색 꿰매는변에서": round(d_seam, 1),
               "뒤옆배색 트인변에서": round(kx - bbk[0], 1), "원본 개수": len(old)}

# 앞판 주머니 입구와 옆선 거리(참고)
QTY_B = {"앞판": (2, "좌우 대칭"), "뒤판": (2, "좌우 대칭"), "앞옆배색": (2, "좌우 대칭 · 스냅(수)"), "뒤옆배색": (2, "좌우 대칭 · 스냅 짝(암)"),
         "앞구찌": (2, ""), "앞주머니감": (4, "주머니 하나에 2장 · 공장 확인")}
B = {REN[k]: dict(v, name=REN[k]) for k, v in B.items()}


# ════════════════ 자를 장수대로 펼치기 (2026-10-19 사장님: «두 개 필요한 건 모두 두 개로») ════════════════
#   모든 조각은 겉면에서 본 모습. 원본이 어느 쪽인지 (원본 그림 그대로 = y 위쪽 +):
#     상의 앞판   앞중심이 오른쪽 · 옆선이 왼쪽            → 몸의 오른쪽 앞판 (R)
#     상의 소매   뒤(더블 노치·386)가 오른쪽 · 앞(336)이 왼쪽 → 왼팔 (L)  ※ 웜업 CAD 규칙: 겉면에서 뒤가 왼쪽 = 오른팔
#     소매중심덧방 짧은 변 739 = 소매 표시선 x414(739) · 긴 변 757 = x479(757) → 원본 소매와 같은 방향 = 왼팔 (L)
#     상의 주머니감 입구가 옆선 쪽(왼쪽)에 · 몸통이 앞중심 쪽(오른쪽)으로 → 오른쪽 앞판용 (R)
#     하의 앞판   가랑이가 왼쪽 · 옆선이 오른쪽               → 왼다리 (L)
#     하의 뒤판   옆선이 왼쪽 · 가랑이가 오른쪽               → 왼다리 (L)
#     옆배색·주머니감 원본 배치에서 왼다리 앞·뒤판에 맞물리던 방향 → 왼다리 (L)
#   반대쪽은 좌우 거울(x → −x)로 만든다. 거울은 선 순서까지 뒤집어 겉면 방향을 지킨다.
def mirror(p):
    f = lambda pts: [(-a, b) for a, b in pts]
    return dict(p, cut=f(p["cut"])[::-1], sew=f(p["sew"])[::-1],
                draw=[dict(d, pts=f(d["pts"])[::-1], **({"snap": (-d["snap"][0], d["snap"][1])} if "snap" in d else {})) for d in p["draw"]],
                notch=[f(l) for l in p["notch"]], fold=f(p["fold"])[::-1] if p["fold"] else None)


def expand(pcs, spec):
    """spec: 원본이름 → [(조각이름, 거울?, 좌우글자, 메모)] — 결과: 조각이름 → (조각, 원본이름, 좌우, 메모)"""
    out = {}
    for base, lst in spec.items():
        for nm, mir, side, note in lst:
            out[nm] = (mirror(pcs[base]) if mir else pcs[base], base, side, note)
    return out


TI = expand(T, {
    "뒤판": [("뒤판", False, "", "")],
    "앞판": [("앞판 R", False, "R", "오른쪽"), ("앞판 L", True, "L", "왼쪽")],
    "소매": [("소매 R", True, "R", "오른팔"), ("소매 L", False, "L", "왼팔")],
    "소매중심덧방": [("소매중심덧방 R", True, "R", "오른팔"), ("소매중심덧방 L", False, "L", "왼팔")],
    "카우스": [("카우스 1", False, "", "립"), ("카우스 2", False, "", "립")],
    "밑단립": [("밑단립", False, "", "립 · 접어 2겹")],
    "에리(립)": [("에리(립)", False, "", "립 · 접어 2겹")],
    "앞주머니구찌": [("앞주머니구찌 1", False, "", ""), ("앞주머니구찌 2", False, "", "")],
    "앞주머니감": [("앞주머니감 R-1", False, "R", "오른쪽 주머니"), ("앞주머니감 R-2", False, "R", "오른쪽 주머니"),
               ("앞주머니감 L-1", True, "L", "왼쪽 주머니"), ("앞주머니감 L-2", True, "L", "왼쪽 주머니")],
})
BI = expand(B, {
    "앞판": [("앞판 R", True, "R", "오른다리"), ("앞판 L", False, "L", "왼다리")],
    "뒤판": [("뒤판 R", True, "R", "오른다리"), ("뒤판 L", False, "L", "왼다리")],
    "앞옆배색": [("앞옆배색 R", True, "R", "오른다리 · 스냅(수)"), ("앞옆배색 L", False, "L", "왼다리 · 스냅(수)")],
    "뒤옆배색": [("뒤옆배색 R", True, "R", "오른다리 · 스냅 짝(암)"), ("뒤옆배색 L", False, "L", "왼다리 · 스냅 짝(암)")],
    "앞구찌": [("앞구찌 1", False, "", ""), ("앞구찌 2", False, "", "")],
    "앞주머니감": [("앞주머니감 R-1", True, "R", "오른쪽 주머니 · 공장 확인"), ("앞주머니감 R-2", True, "R", "오른쪽 주머니 · 공장 확인"),
               ("앞주머니감 L-1", False, "L", "왼쪽 주머니 · 공장 확인"), ("앞주머니감 L-2", False, "L", "왼쪽 주머니 · 공장 확인")],
})


# ════════════════ 내보내기 ════════════════
def export(inst, name, title, legend):
    pcs = {n: v[0] for n, v in inst.items()}
    order = sorted(pcs, key=lambda n: (-(bb(pcs[n]["cut"])[3] - bb(pcs[n]["cut"])[1]), n))
    # 조각 좌표: y 아래로(+) 바꾸고 각 조각을 원점으로
    P = {}
    for n in order:
        p = pcs[n]; x0, y0, x1, y1 = bb(p["cut"])
        f = lambda pts: [(a - x0, y1 - b) for a, b in pts]
        P[n] = {"cut": f(p["cut"]), "sew": f(p["sew"]),
                "draw": [dict(d, pts=f(d["pts"]), snap=(f([d["snap"]])[0] if "snap" in d else None)) for d in p["draw"]],
                "notch": [f(l) for l in p["notch"]], "fold": f(p["fold"]) if p["fold"] else None,
                "w": x1 - x0, "h": y1 - y0}
    GAP, SHEET_W = 40, 1800
    place, x, y, rowh = {}, GAP, GAP + 80, 0
    for n in order:
        w, h = P[n]["w"], P[n]["h"]
        if x + w > SHEET_W - GAP: x, y, rowh = GAP, y + rowh + GAP, 0
        place[n] = (x, y); x += w + GAP; rowh = max(rowh, h)
    W, H = SHEET_W, y + rowh + GAP
    tr = lambda n, pts: [(a + place[n][0], b + place[n][1]) for a, b in pts]
    # 겹침 검사
    polys = {n: Polygon(tr(n, P[n]["cut"])).buffer(0) for n in order}
    overlap = [(a, b) for i, a in enumerate(order) for b in order[i + 1:] if polys[a].intersects(polys[b])]
    # 이름표 자리
    anchor = {}
    for n in order:
        S = Polygon(P[n]["sew"]).buffer(0); S = max(getattr(S, "geoms", [S]), key=lambda g: g.area); a = polylabel(S, tolerance=0.5); anchor[n] = (a.x, a.y)

    def labels(n):
        note = inst[n][3]
        return [n, "2XL · 1장 · 겉면" + (f" · {note}" if note else "")]

    PT = 72 / 25.4; FONT = "C:/Windows/Fonts/malgun.ttf"
    LAYERS = ["재단선", "재봉선", "안쪽선(원본)", "수정·추가", "노치", "접는선", "글자"]

    def build_pdf(path):
        pdf = fitz.open(); page = pdf.new_page(width=W * PT, height=H * PT)
        oc = {L: pdf.add_ocg(L, on=True) for L in LAYERS}
        Q = lambda pts: [fitz.Point(a * PT, b * PT) for a, b in pts]
        for L, key, color, width, dashes in (("재단선", "cut", (0, 0, 0), 0.9, None), ("재봉선", "sew", (0.12, 0.37, 0.75), 0.5, "[6 4] 0")):
            sh = page.new_shape()
            for n in order:
                sh.draw_polyline(Q(tr(n, P[n][key]))); sh.finish(color=color, width=width, dashes=dashes, closePath=True, oc=oc[L])
            sh.commit()
        for L, new, color in (("안쪽선(원본)", False, (0.1, 0.5, 0.2)), ("수정·추가", True, (0.9, 0.35, 0))):
            sh = page.new_shape()
            for n in order:
                for d in P[n]["draw"]:
                    if d["new"] != new: continue
                    sh.draw_polyline(Q(tr(n, d["pts"]))); sh.finish(color=color, width=0.7 if new else 0.5, closePath=d["closed"], oc=oc[L])
            sh.commit()
        sh = page.new_shape()
        for n in order:
            for l in P[n]["notch"]:
                p = Q(tr(n, l)); sh.draw_line(p[0], p[1])
        sh.finish(color=(0, 0, 0), width=0.9, oc=oc["노치"]); sh.commit()
        sh = page.new_shape()
        for n in order:
            if P[n]["fold"]:
                p = Q(tr(n, P[n]["fold"])); sh.draw_line(p[0], p[1])
        sh.finish(color=(0.12, 0.52, 0.29), width=0.6, dashes="[8 3 2 3] 0", oc=oc["접는선"]); sh.commit()
        font = fitz.Font(fontfile=FONT)
        for n in order:
            if P[n]["fold"]:
                (fx, fy), _ = tr(n, P[n]["fold"])
                page.insert_text(fitz.Point((fx + 60) * PT, (fy - 1.5) * PT), "접는 선 — 2겹", fontsize=8, fontname="malgun", fontfile=FONT, color=(0.12, 0.52, 0.29), oc=oc["접는선"])
            (cx, cy), = tr(n, [anchor[n]])
            for i, t in enumerate(labels(n)):
                fs = 12 if i == 0 else 9
                tw = font.text_length(t, fontsize=fs) / PT
                page.insert_text(fitz.Point((cx - tw / 2) * PT, (cy - 4 + i * 14) * PT), t, fontsize=fs, fontname="malgun", fontfile=FONT, oc=oc["글자"])
            side = inst[n][2]
            if side:                                                   # 큰 좌우 글자 — 재단 때 뒤집어 자르지 않게
                fs = 90 if min(P[n]["w"], P[n]["h"]) > 150 else 40
                tw = font.text_length(side, fontsize=fs) / PT
                page.insert_text(fitz.Point((cx - tw / 2) * PT, (cy - 22) * PT), side, fontsize=fs, fontname="malgun", fontfile=FONT, color=(0.83, 0.33, 0), oc=oc["글자"])
        page.insert_text(fitz.Point(GAP * PT, 36 * PT), title, fontsize=14, fontname="malgun", fontfile=FONT, oc=oc["글자"])
        for i, t in enumerate(legend):
            page.insert_text(fitz.Point(GAP * PT, (52 + i * 11) * PT), t, fontsize=9, fontname="malgun", fontfile=FONT, oc=oc["글자"])
        sh = page.new_shape()
        sh.draw_line(fitz.Point((W - 170) * PT, 30 * PT), fitz.Point((W - 70) * PT, 30 * PT)); sh.finish(color=(0, 0, 0), width=0.8, oc=oc["글자"]); sh.commit()
        page.insert_text(fitz.Point((W - 135) * PT, 44 * PT), "100 mm", fontsize=9, fontname="malgun", fontfile=FONT, oc=oc["글자"])
        pdf.set_metadata({"title": name, "creator": "STIZ pattern 2026-10-19", "subject": "한국가스공사 웜업 2XL 수정 패턴 1:1 mm"})
        pdf.subset_fonts(); pdf.save(path, garbage=3, deflate=True)

    build_pdf(os.path.join(OUT, f"{name}_1대1.pdf"))
    build_pdf(os.path.join(OUT, f"{name}.ai"))
    z = 2000 / max(W * PT, H * PT)
    fitz.open(os.path.join(OUT, f"{name}_1대1.pdf"))[0].get_pixmap(matrix=fitz.Matrix(z, z)).save(os.path.join(OUT, f"{name}_미리보기.png"))

    # DXF (AAMA 관례: 1 재단 · 14 재봉 · 8 안쪽선 · 4 노치 · 13 스냅 구멍 점) — 조각 이름은 영문(R12 한글 깨짐)
    EN = {"뒤판": "BACK", "앞판": "FRONT", "소매": "SLEEVE", "소매중심덧방": "SLEEVE CENTER OVERLAY", "카우스": "CUFF RIB", "밑단립": "HEM RIB",
          "에리(립)": "COLLAR RIB", "앞주머니구찌": "POCKET ZIP FACING", "앞주머니감": "POCKET BAG", "앞옆배색": "FRONT SIDE PANEL SNAP",
          "뒤옆배색": "BACK SIDE PANEL SNAP MATE", "앞구찌": "POCKET ZIP FACING"}
    doc = ezdxf.new("R12"); msp = doc.modelspace()
    for L, c in (("1", 7), ("14", 5), ("8", 3), ("4", 7), ("13", 1)):
        doc.layers.add(L, color=c, linetype="Continuous")
    flip = lambda pts: [(a, -b) for a, b in pts]
    for k, n in enumerate(order):
        blk = doc.blocks.new(name=f"PIECE_{k + 1}")
        blk.add_polyline2d(flip(P[n]["cut"]), close=True, dxfattribs={"layer": "1"})
        blk.add_polyline2d(flip(P[n]["sew"]), close=True, dxfattribs={"layer": "14"})
        for d in P[n]["draw"]:
            blk.add_polyline2d(flip(d["pts"]), close=d["closed"], dxfattribs={"layer": "8"})
            if d.get("snap"):
                blk.add_point(flip([d["snap"]])[0], dxfattribs={"layer": "13"})
        for l in P[n]["notch"]:
            blk.add_line(*flip(l), dxfattribs={"layer": "4"})
        if P[n]["fold"]:
            blk.add_line(*flip(P[n]["fold"]), dxfattribs={"layer": "8"})
        base, side = inst[n][1], inst[n][2]
        suf = n.split(" ")[-1] if " " in n else ""
        ax, ay = anchor[n]
        for i, t in enumerate([f"Piece Name: {EN[base]}" + (f" {suf}" if suf else ""), "Size: 2XL", "Quantity: 1", "Units: mm", "Face: UP (outside)"]):
            blk.add_text(t, dxfattribs={"layer": "1", "height": 5, "halign": 1, "valign": 0}).set_placement(
                (ax, -(ay + i * 8)), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
        msp.add_blockref(blk.name, (place[n][0], -place[n][1]))
    allp = [p for n in order for p in flip(tr(n, P[n]["cut"]))]
    x0, y0, x1, y1 = bb(allp)
    msp.reset_extents((x0, y0, 0), (x1, y1, 0))
    doc.saveas(os.path.join(OUT, f"{name}.dxf"))
    return {"sheet_mm": [round(W), round(H)], "pieces": order, "overlap": overlap, "total_qty": len(order)}


LEG_T = ["검정 재단선 · 파랑 점선 재봉선 · 초록 원본 안쪽선 · 주황 이번에 넣은 선 · 초록 일점쇄선 접는 선 · 짧은 선 노치",
         "수정: ① 앞주머니 추가(입구 150 · 구찌 · 주머니감) ② 에리 → 립 접어 2겹 ③ 파이핑 없음 ④ 자를 장수대로 펼침(좌우 거울 · 큰 R/L 글자) — 모두 17장"]
LEG_B = ["검정 재단선 · 파랑 점선 재봉선 · 초록 원본 안쪽선 · 주황 이번에 넣은 선(스냅 ○ · 스냅 짝 ⊕)",
         "수정: ① 스냅 7 → 9개(밑단~허리 아래) · 맨 아래 스냅을 밑단 스티치에서 띄움 ② 뒤옆배색에 스냅 짝 위치 ③ 뒷주머니 삭제 ④ 이름 정리 ⑤ 자를 장수대로 펼침(좌우 거울 · 큰 R/L 글자) — 모두 14장"]
os.makedirs(OUT, exist_ok=True)
# 비교 그림(compare.py)용 — 원본 좌표 그대로(mm, y 위쪽 +) 수정 후 조각
json.dump({"top": T, "bottom": B}, open(os.path.join(OUT, "pieces_after.json"), "w", encoding="utf-8"), ensure_ascii=False)   # 그레이딩 입력
CHECK["상의 시트"] = export(TI, "상의_2XL_수정", "한국가스공사 페가수스 웜업 상의 · 2XL · 수정 패턴 1:1 mm (2026-10-19)", LEG_T)
CHECK["하의 시트"] = export(BI, "하의_2XL_수정", "한국가스공사 페가수스 웜업 하의 · 2XL · 수정 패턴 1:1 mm (2026-10-19)", LEG_B)
json.dump(CHECK, open(os.path.join(OUT, "check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(CHECK, ensure_ascii=False, indent=1))
