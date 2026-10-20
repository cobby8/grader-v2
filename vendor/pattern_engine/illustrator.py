# 일러스트 패턴(.ai = PDF 호환) 읽기·다시 쓰기 — 외곽선만 고치고 나머지는 그대로 다시 그린다
#   read(path)  → {"page": (w_pt, h_pt), "drawings": [그림…]}
#       그림 = {type 's'|'f'|'fs', color, fill, width, dashes, closePath, even_odd, layer, subpaths: [[(x_mm, y_mm)…]…]}
#       좌표는 mm, y 아래로(+) — PDF 그대로. 베지어는 16토막으로 편다(패턴 외곽선은 대부분 직선 토막이라 차이 없음)
#   write(doc, path) → 같은 크기 PDF(.ai 로 저장하면 일러스트가 연다). 레이어 이름은 OCG 로 살린다
#   🚫 원본 파일은 덮어쓰지 않는다 — 부르는 쪽이 새 경로를 준다
#   꺼진 레이어(OCG off)는 다시 그리지 않고 원본 내용을 꺼진 채 통째로 옮긴다 · hidden_drawings(path) 로 읽을 수 있다
import math, re
import fitz

MM = 25.4 / 72


def _flatten(items):
    subs, cur = [], []
    def add(q):
        if cur and math.dist(cur[-1], q) < 1e-6: return
        cur.append(q)
    for it in items:
        kind = it[0]
        if kind == "l":
            seg = [(it[1].x * MM, it[1].y * MM), (it[2].x * MM, it[2].y * MM)]
        elif kind == "c":
            a, c1, c2, b = it[1:5]; seg = [(a.x * MM, a.y * MM)]
            for k in range(1, 17):
                t = k / 16; w = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3)
                seg.append((sum(wi * q.x for wi, q in zip(w, (a, c1, c2, b))) * MM, sum(wi * q.y for wi, q in zip(w, (a, c1, c2, b))) * MM))
        elif kind == "re":
            r = it[1]; seg = [(r.x0 * MM, r.y0 * MM), (r.x1 * MM, r.y0 * MM), (r.x1 * MM, r.y1 * MM), (r.x0 * MM, r.y1 * MM), (r.x0 * MM, r.y0 * MM)]
        elif kind == "qu":
            q = it[1]; seg = [(p.x * MM, p.y * MM) for p in (q.ul, q.ur, q.lr, q.ll, q.ul)]
        else:
            continue
        if cur and math.dist(cur[-1], seg[0]) > 0.01:
            subs.append(cur); cur = []
        for q in seg: add(q)
    if cur: subs.append(cur)
    return subs


def read(path):
    d = fitz.open(path); pg = d[0]
    out = {"page": (pg.rect.width, pg.rect.height), "drawings": [], "source": path,
           "text_chars": len(pg.get_text().strip()), "images": len(pg.get_images())}
    for g in pg.get_drawings():
        out["drawings"].append({"type": g["type"], "color": g.get("color"), "fill": g.get("fill"), "width": g.get("width") or 0,
                                "dashes": g.get("dashes"), "closePath": g.get("closePath"), "even_odd": g.get("even_odd"),
                                "layer": g.get("layer"), "lineCap": g.get("lineCap"), "lineJoin": g.get("lineJoin"),
                                "subpaths": _flatten(g["items"])})
    return out


def _hidden_segments(d):
    """꺼진 레이어(OCG off)에 든 원본 내용 → {레이어 이름: [내용 바이트…]} — get_drawings 는 꺼진 레이어를 안 돌려준다
    (2026-10-19 실측: 슈팅저지 L·M·XL·S·XS · 하의 5XS 의 꺼진 «图层 1» 에 공장 CAD 원본 도면이 선 3만 토막씩 들어 있었다)"""
    pg = d[0]; c = pg.read_contents()
    ocg = d.get_ocgs(); off = {x for x in ocg if not ocg[x]["on"]}
    if not off: return {}
    kind, val = d.xref_get_key(pg.xref, "Resources/Properties")
    src = val if kind == "dict" else (d.xref_object(int(val.split()[0])) if kind == "xref" else "")
    props = {k: int(v) for k, v in re.findall(r"/(\w+)\s+(\d+) 0 R", src)}
    out = {}
    for m in re.finditer(rb"/OC\s*/(\w+)\s+BDC", c):
        x = props.get(m.group(1).decode())
        if x not in off: continue
        depth, i = 1, m.end()
        while depth:
            nb = c.find(b"BDC", i); ne = c.find(b"EMC", i)
            if ne == -1: i = len(c) + 3; break
            if nb != -1 and nb < ne: depth += 1; i = nb + 3
            else: depth -= 1; i = ne + 3
        out.setdefault(ocg[x]["name"], []).append(c[m.end():i - 3])
    return out


def _balance(seg):
    """조각 안에서 짝이 안 맞는 Q(바깥에서 연 q 를 닫는 것)는 빼고, 덜 닫힌 q 는 끝에서 닫는다"""
    toks = re.split(rb"(\s+)", seg); depth = 0; out = []
    for t in toks:
        if t == b"Q":
            if depth == 0: continue
            depth -= 1
        elif t == b"q": depth += 1
        out.append(t)
    return b"".join(out) + b"\nQ" * depth


def _hidden_page(path, name=None):
    """원본을 메모리에서 열어 꺼진 레이어 내용만 남긴 사본(파일은 안 바꾼다) — name 을 주면 그 레이어만"""
    d = fitz.open(path); segs = _hidden_segments(d)
    body = b"\n".join(_balance(s) for n, ss in segs.items() if name in (None, n) for s in ss)
    xs = d[0].get_contents(); d.update_stream(xs[0], body)
    for x in xs[1:]: d.update_stream(x, b"")
    return d


def hidden_drawings(path):
    """꺼진 레이어의 선 → [(그림, [(x_mm, y_mm)…])] — 분석용(예: 슬림 하의 CAD 옆선)"""
    d = _hidden_page(path)
    return [(g, P) for g in d[0].get_drawings() for P in _flatten(g["items"])]


def write(doc, path, title=""):
    pdf = fitz.open(); pg = pdf.new_page(width=doc["page"][0], height=doc["page"][1])
    # 꺼진 레이어는 원본 그대로(꺼진 채) 옮긴다 — 다시 그리지 않고 원본 내용을 통째로 붙인다(맨 아래)
    src = doc.get("source")
    if src:
        sd = fitz.open(src)
        for name in _hidden_segments(sd):
            hp = _hidden_page(src, name)
            pg.show_pdf_page(pg.rect, hp, 0, oc=pdf.add_ocg(name, on=False), overlay=False, keep_proportion=False)
        for x in range(1, pdf.xref_length()):                                   # 붙인 내용이 대지 밖으로 나가도 잘리지 않게
            if pdf.xref_get_key(x, "Subtype")[1] == "/Form": pdf.xref_set_key(x, "BBox", "[-100000 -100000 100000 100000]")
    ocg = {}
    for g in doc["drawings"]:
        L = g.get("layer") or ""
        if L and L not in ocg: ocg[L] = pdf.add_ocg(L, on=True)
    for g in doc["drawings"]:
        sh = pg.new_shape()
        for P in g["subpaths"]:
            if len(P) < 2: continue
            sh.draw_polyline([fitz.Point(x / MM, y / MM) for x, y in P])
        stroke = g["color"] if "s" in g["type"] else None
        fill = g["fill"] if "f" in g["type"] else None
        lc = g.get("lineCap"); lj = g.get("lineJoin")
        sh.finish(color=stroke, fill=fill, width=g["width"] if stroke else 0, dashes=g["dashes"] if stroke else None,
                  closePath=bool(g.get("closePath")), even_odd=bool(g.get("even_odd")),
                  lineCap=max(lc) if isinstance(lc, (tuple, list)) else (lc or 0), lineJoin=int(lj or 0),
                  oc=ocg.get(g.get("layer") or "", 0))
        sh.commit()
    pdf.set_metadata({"title": title, "creator": "STIZ pattern-engine"})
    pdf.save(path, garbage=3, deflate=True)


def outlines(doc, min_len=150):
    """선으로 그린 닫힌 큰 윤곽(조각 외곽선) — (그림 번호, 토막 번호, 점들)"""
    out = []
    for gi, g in enumerate(doc["drawings"]):
        if "s" not in g["type"]: continue
        for si, P in enumerate(g["subpaths"]):
            if sum(math.dist(P[k], P[k + 1]) for k in range(len(P) - 1)) >= min_len:
                out.append((gi, si, P))
    return out
