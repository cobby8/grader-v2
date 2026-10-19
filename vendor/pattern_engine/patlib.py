# 패턴 공용 도구 — build.py(2XL 수정본) 에서 떼어 와 사이즈를 인자로 받게 한 것. grade.py 가 쓴다.
#   (build.py 는 검산이 끝난 2XL 수정본을 만든 그대로 두고 손대지 않는다)
import sys, os, json, math
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


# ════════════════ 내보내기 ════════════════
def ascii_safe(s):
    """DXF R12 는 한글이 깨진다 — 영문·숫자·공백·- _ 만 남기고 대문자로. 남는 게 없으면 빈 글자"""
    out = "".join(c if (c.isascii() and (c.isalnum() or c in " -_")) else " " for c in str(s or ""))
    return " ".join(out.split()).upper()


def en_name_of(p, base, en_names=None, k=0):
    """DXF 조각 영문 이름 — ① 인자 이름표 en_names[원본이름] ② 조각/명세 meta 의 en_name ③ 원본이름을 영문 안전 문자로
    ④ 그래도 비면(한글뿐) PIECE <번호>. 옷마다 이름표가 달라 엔진에 박아 두지 않는다(2026-10-19 일반화)"""
    if en_names and en_names.get(base): return en_names[base]
    meta = p.get("meta") or {}
    if p.get("en_name") or meta.get("en_name"): return p.get("en_name") or meta["en_name"]
    return ascii_safe(base) or f"PIECE {k + 1}"


def spec_instances(specs, flip_y=False):
    """piecespec 명세들 → export 가 받는 inst {조각이름: (옛 형식 조각, 원본이름, 좌우 글자, 메모)}.
    meta.qty 만큼 펼친다 — 2장이면 «1»(그린 그대로)·«2»(좌우 뒤집음, 한 쌍) · en_name 은 조각에 실어 보낸다.
    flip_y: 명세가 y 아래쪽(+) 좌표(예 parametric)면 True — export 는 y 위쪽(+)을 받는다"""
    from piecespec import to_legacy                       # 읽기만 한다(명세 모델은 다른 작업자 파일)
    inst = {}
    for base, sp in specs.items():
        p = to_legacy(sp); meta = sp.get("meta") or {}
        if flip_y:                                         # y 뒤집기 — 고리 방향이 바뀌니 순서도 뒤집어 원래 방향을 지킨다
            f = lambda pts: [(a, -b) for a, b in pts]
            p = dict(p, sew=f(p["sew"])[::-1], cut=f(p["cut"])[::-1],
                     draw=[dict(d, pts=f(d["pts"])[::-1], **({"snap": (d["snap"][0], -d["snap"][1])} if d.get("snap") else {})) for d in p["draw"]],
                     notch=[f(l) for l in p["notch"]], fold=f(p["fold"]) if p.get("fold") else None)
        p["en_name"] = meta.get("en_name")
        qty = int(meta.get("qty") or 1); note = meta.get("note") or ""
        mir = meta.get("mirror", True) is not False             # meta.mirror=False — 좌우 짝이 아니라 «같은 모양 n장»(2026-10-20 이름 확인 화면)
        if qty <= 1:
            inst[base] = (p, base, "", note)
        else:
            for j in range(qty):
                q = mirror(p) if (j % 2 and mir) else p
                inst[f"{base} {j + 1}"] = (q, base, "", (note + " · " if note else "") + ("짝(뒤집음)" if (j % 2 and mir) else f"{qty}장 중 {j + 1}"))
    return inst


def export(inst, name, title, legend, OUT, size="2XL", en_names=None, subject=None):
    """inst: {조각이름: (조각, 원본이름, 좌우 글자, 메모)} → .ai · 1:1 PDF · 미리보기 PNG · DXF R12.
    en_names: {원본이름: DXF 영문 이름} (없으면 조각 meta 의 en_name → 이름을 영문 안전 문자로). subject: PDF 설명"""
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
        return [n, f"{size} · 1장 · 겉면" + (f" · {note}" if note else "")]

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
        pdf.set_metadata({"title": name, "creator": "STIZ pattern 2026-10-19", "subject": subject or f"{name} · {size} 패턴 1:1 mm"})
        pdf.subset_fonts(); pdf.save(path, garbage=3, deflate=True)

    build_pdf(os.path.join(OUT, f"{name}_1대1.pdf"))
    build_pdf(os.path.join(OUT, f"{name}.ai"))
    z = 2000 / max(W * PT, H * PT)
    fitz.open(os.path.join(OUT, f"{name}_1대1.pdf"))[0].get_pixmap(matrix=fitz.Matrix(z, z)).save(os.path.join(OUT, f"{name}_미리보기.png"))

    # DXF (AAMA 관례: 1 재단 · 14 재봉 · 8 안쪽선 · 4 노치 · 13 스냅 구멍 점) — 조각 이름은 영문(R12 한글 깨짐)
    #   이름표는 옷마다 다르다 — 부르는 쪽이 en_names 로 주거나 명세 meta.en_name 에 싣는다(en_name_of, 2026-10-19 일반화)
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
        # 꼬리(R · L-1 · 2 …) = 조각이름에서 원본이름을 뺀 나머지 — 원본이름에 띄어쓰기가 있어도(«뒤 요크») 한글 꼬리가 안 붙게
        suf = n[len(base):].strip() if n.startswith(base) else (n.split(" ")[-1] if " " in n else "")
        suf = ascii_safe(suf)
        ax, ay = anchor[n]
        en = en_name_of(pcs[n], base, en_names, k)
        for i, t in enumerate([f"Piece Name: {en}" + (f" {suf}" if suf else ""), f"Size: {size}", "Quantity: 1", "Units: mm", "Face: UP (outside)"]):
            blk.add_text(t, dxfattribs={"layer": "1", "height": 5, "halign": 1, "valign": 0}).set_placement(
                (ax, -(ay + i * 8)), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
        msp.add_blockref(blk.name, (place[n][0], -place[n][1]))
    allp = [p for n in order for p in flip(tr(n, P[n]["cut"]))]
    x0, y0, x1, y1 = bb(allp)
    msp.reset_extents((x0, y0, 0), (x1, y1, 0))
    doc.saveas(os.path.join(OUT, f"{name}.dxf"))
    return {"sheet_mm": [round(W), round(H)], "pieces": order, "overlap": overlap, "total_qty": len(order)}


