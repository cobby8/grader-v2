# 노치 규칙(엔진) — 조각 찾기·앞뒤 판정·노치 자리·삽입. stiz_notch_add.py(명령줄)와 그레이더(서버)가 같이 쓴다
#   (2026-10-20 사장님: «그레이딩 시스템 안에 넣어야지» — 일러스트 없이 파이썬만으로 돈다)
#   규칙: jersey(긴팔 슈팅저지 래글런) · pants(농구 하의 말아박기·슬림 — 한 장짜리 옆선은 CAD 세로선/옆선 판/비율)
#   방식: 외곽선에 박힌 일자 홈(안쪽 5mm) · 앞 1개 · 뒤 2개(간격 20mm) · 꿰매는 두 변의 «짧은 쪽 절반»을 같은 끝에서
#   아래 «조각 찾기·판정» 부분의 실측 이력은 stiz_notch_add.py 머리말 참고
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import illustrator as ai
from shapely.geometry import Polygon, LineString
import notching as nt


def corners(P, thr=25):
    Q = nt._closed(P); n = len(Q); ang = lambda a, b: math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])); out = []
    for i in range(n):
        a, b, c = Q[i - 1], Q[i], Q[(i + 1) % n]
        if math.dist(a, b) < 1e-6 or math.dist(b, c) < 1e-6: continue
        if abs((ang(b, c) - ang(a, b) + 180) % 360 - 180) > thr: out.append(b)
    return out


def bbox(P):
    xs = [p[0] for p in P]; ys = [p[1] for p in P]; return min(xs), min(ys), max(xs), max(ys)


def per(P): return sum(math.dist(P[k], P[k + 1]) for k in range(len(P) - 1))


def cad_side_x(doc, P):
    """조각 P 안을 위아래로 거의 다 지나는 꺼진 레이어의 세로선 하나 → 그 x (없거나 여럿이면 None)
    조건: 수직(폭 0.05mm 안) · 조각 높이의 60% 이상과 겹침 · 선 길이의 90% 이상이 조각 안"""
    if "_hidden" not in doc:
        doc["_hidden"] = ai.hidden_drawings(doc["source"]) if doc.get("source") else []
    poly = Polygon(nt._closed(P)); x0, y0, x1, y1 = bbox(P); xs = set()
    for g, Q in doc["_hidden"]:
        qx = [q[0] for q in Q]; qy = [q[1] for q in Q]
        if len(Q) < 2 or max(qx) - min(qx) > 0.05 or not (x0 < qx[0] < x1): continue
        lo, hi = max(min(qy), y0), min(max(qy), y1)
        if hi - lo < 0.6 * (y1 - y0): continue
        seg = LineString([(qx[0], min(qy)), (qx[0], max(qy))])
        if seg.intersection(poly).length < 0.9 * seg.length: continue
        xs.add(round(qx[0], 1))
    xs = sorted(xs)
    return xs[0] if xs and xs[-1] - xs[0] < 0.5 else None


def along_x(P, a, b, x):
    """꼭짓점 a → b 경로를 따라가다 세로선 x 와 만나는 곳까지의 길이"""
    idx = nt.edge(P, a, b); Q = nt._closed(P); s = 0.0
    for k in range(len(idx) - 1):
        u, v = Q[idx[k]], Q[idx[k + 1]]; L = math.dist(u, v)
        if (u[0] - x) * (v[0] - x) <= 0 and abs(v[0] - u[0]) > 1e-9:
            return s + L * abs(x - u[0]) / abs(v[0] - u[0])
        s += L
    raise ValueError(f"세로선 x={x:.1f} 이 경로와 안 만난다")


def pieces(doc, min_len):
    """선·채움 상관없이 닫힌 큰 윤곽 → 같은 모양끼리 묶음 [(대표 점들, [(그림, 토막)…])]"""
    groups = []
    for gi, g in enumerate(doc["drawings"]):
        for si, P in enumerate(g["subpaths"]):
            if len(P) < 4 or per(P) < min_len or math.dist(P[0], P[-1]) > 1.0: continue
            b = bbox(P); W, H = doc["page"][0] * ai.MM, doc["page"][1] * ai.MM
            if (b[2] - b[0]) > W * 0.9 and (b[3] - b[1]) > H * 0.9 and b[0] > -1 and b[1] > -1 and b[2] < W + 1 and b[3] < H + 1:
                continue                                                                  # 대지를 덮는 바탕 사각형은 뺀다
                # (대지보다 큰 «조각»은 남긴다 — 슬림 하의는 A4 대지에 730mm 판이 걸쳐 있다)
            if min(abs(b[0]), abs(b[1]), abs(b[2] - W), abs(b[3] - H)) < 0.5:              # 대지 경계에서 «딱» 끊김 = PDF 에 잘려 저장된 조각
                                                                                          # (대지 밖으로 나가 있기만 한 조각은 온전하다 — 그대로 쓴다)
                doc.setdefault("clipped", []).append([round(v) for v in b]); continue
            for G in groups:
                gb = bbox(G[0])
                if max(abs(u - v) for u, v in zip(b, gb)) < 0.5 and abs(per(P) - per(G[0])) < 0.5:
                    G[1].append((gi, si)); break
            else:
                groups.append((P, [(gi, si)]))
    return groups


def _label(doc, grp, name):
    """조각(겹친 사본 포함)에 이름표 — 그레이더가 어느 조각을 쓸지 고를 때 쓴다(front·back·sleeve·split_front …)"""
    for key in grp[1]: doc.setdefault("labels", {})[key] = name


class Plan:
    def __init__(self): self.marks = {}
    def put(self, grp, a, b, dist):
        P = grp[0]; ms, L = nt.marks_from(P, a, b, dist)
        for key in grp[1]: self.marks.setdefault(key, []).append((a, b, dist))
        return L


def apply_plan(doc, plan):
    n = 0
    for (gi, si), items in plan.marks.items():
        P = doc["drawings"][gi]["subpaths"][si]; marks = []
        for a, b, dist in items: marks += nt.marks_from(P, a, b, dist)[0]
        doc["drawings"][gi]["subpaths"][si] = nt.insert_slits(P, marks); n += len(marks)
    return n


# ── 긴팔 슈팅저지(래글런) ──
def jersey(doc):
    G = sorted(pieces(doc, 1500), key=lambda g: -per(g[0]))
    def is_sleeve(P):
        x0, y0, x1, y1 = bbox(P); low = [c for c in corners(P) if c[1] > y1 - 40]
        return bool(low) and (max(c[0] for c in low) - min(c[0] for c in low)) < (x1 - x0) * 0.4   # 소매부리가 폭보다 훨씬 좁다
    sleeves = [g for g in G if is_sleeve(g[0])]
    bodies = [g for g in G if not is_sleeve(g[0]) and (bbox(g[0])[3] - bbox(g[0])[1]) > 600][:2]
    assert len(bodies) == 2 and 1 <= len(sleeves) <= 2, f"조각 판정 실패: 몸판 {len(bodies)} · 소매 {len(sleeves)}"

    def body_pts(P):
        C = corners(P); x0, y0, x1, y1 = bbox(P); cx = (x0 + x1) / 2
        hem = [c for c in C if c[1] > y1 - 5]
        neckL = min([c for c in C if c[0] < cx], key=lambda c: c[1]); neckR = min([c for c in C if c[0] > cx], key=lambda c: c[1])
        rest = [c for c in C if c not in hem and c not in (neckL, neckR)]
        Q = nt._closed(P)
        def ua(side_x, pick):                       # 곧은 옆선(밑단 모서리와 같은 x)의 가장 위 점 = 겨드랑이 — 둥글게 이어져 꺾임이 안 잡혀도 된다
            on = [q for q in Q if abs(q[0] - side_x) < 0.5 and q[1] < y1 - 50]
            return min(on, key=lambda q: q[1]) if on else pick(rest, key=lambda c: c[0])
        return {"hemL": min(hem, key=lambda c: c[0]), "hemR": max(hem, key=lambda c: c[0]),
                "uaL": ua(x0, min), "uaR": ua(x1, max), "neckL": neckL, "neckR": neckR}
    L = lambda P, a, b: nt.length(P, nt.edge(P, a, b))
    (fg, fp), (bg, bp) = sorted([(g, body_pts(g[0])) for g in bodies], key=lambda t: -L(t[0][0], t[1]["neckL"], t[1]["neckR"]))   # 앞 = 목선이 길다
    Lf, Lb = L(fg[0], fp["uaL"], fp["neckL"]), L(bg[0], bp["uaL"], bp["neckL"])
    sl_info = []
    for sg in sleeves:
        P = sg[0]; C = corners(P); x0, y0, x1, y1 = bbox(P)
        uaL = min(C, key=lambda c: c[0]); uaR = max(C, key=lambda c: c[0])
        tops = sorted([c for c in C if c[1] < y0 + 60], key=lambda c: c[0]); nL, nR = tops[0], tops[-1]
        Ls = {"L": L(P, uaL, nL), "R": L(P, uaR, nR)}
        front = "L" if abs(Ls["L"] - Lf) + abs(Ls["R"] - Lb) < abs(Ls["R"] - Lf) + abs(Ls["L"] - Lb) else "R"
        sl_info.append({"g": sg, "front": front, "F": (uaL, nL) if front == "L" else (uaR, nR), "B": (uaR, nR) if front == "L" else (uaL, nL),
                        "LF": Ls[front], "LB": Ls["R" if front == "L" else "L"]})
    df = round(min([Lf] + [s["LF"] for s in sl_info]) / 2); db = round(min([Lb] + [s["LB"] for s in sl_info]) / 2)
    plan = Plan()
    for side in ("L", "R"):
        plan.put(fg, fp["ua" + side], fp["neck" + side], nt.single(df))
        plan.put(bg, bp["ua" + side], bp["neck" + side], nt.double(db))
    for s in sl_info:
        plan.put(s["g"], *s["F"], nt.single(df)); plan.put(s["g"], *s["B"], nt.double(db))
    for g, p in ((fg, fp), (bg, bp)):                                    # 앞·뒤 목 가운데
        plan.put(g, p["neckL"], p["neckR"], [L(g[0], p["neckL"], p["neckR"]) / 2])
    report = {"래글런 앞(몸판·소매)": [round(Lf, 1)] + [round(s["LF"], 1) for s in sl_info],
              "래글런 뒤(몸판·소매)": [round(Lb, 1)] + [round(s["LB"], 1) for s in sl_info],
              "앞 노치(겨드랑이에서)": df, "뒤 더블 노치 가운데(겨드랑이에서)": db,
              "옆선 앞·뒤": [round(L(fg[0], fp["uaL"], fp["hemL"]), 1), round(L(bg[0], bp["uaL"], bp["hemL"]), 1)],
              "목선 앞·뒤": [round(L(fg[0], fp["neckL"], fp["neckR"]), 1), round(L(bg[0], bp["neckL"], bp["neckR"]), 1)],
              "소매 장수": len(sleeves), "소매 앞쪽": ["왼쪽" if s["front"] == "L" else "오른쪽" for s in sl_info],
              "겹친 사본(같은 모양 함께 고침)": sum(len(g[1]) - 1 for g in [fg, bg] + sleeves)}
    _label(doc, fg, "front"); _label(doc, bg, "back")
    for x in sl_info: _label(doc, x["g"], "sleeve")
    return plan, report


# ── 농구 하의 말아박기(2번 패턴: 옆선 있는 앞·뒤 + 한 장 + 밑단 트임 한 장 — 사이즈마다 일부만 있을 수 있음) ──
def pants(doc):
    G = pieces(doc, 1000)
    wide = sorted([g for g in G if bbox(g[0])[2] - bbox(g[0])[0] > 600], key=lambda g: bbox(g[0])[1])
    narrow = [g for g in G if bbox(g[0])[2] - bbox(g[0])[0] <= 600]
    L = lambda P, a, b: nt.length(P, nt.edge(P, a, b))
    plan = Plan(); report = {}
    sp = []
    for g in narrow:
        P = g[0]; x0, y0, x1, y1 = bbox(P); C = corners(P)
        right_straight = sum(1 for c in C if abs(c[0] - x1) < 1) >= 2              # 오른쪽 끝에 꼭짓점 둘 = 곧은 옆선
        sgn = -1 if right_straight else 1                                           # 옆선 반대편이 가랑이
        hem = [c for c in C if c[1] > y1 - 5]
        cr = max(C, key=lambda c: sgn * c[0])
        side_x = x1 if right_straight else x0; cx = (x0 + x1) / 2
        side_top = min([c for c in C if abs(c[0] - side_x) < 1], key=lambda c: c[1])
        hull = [tuple(q) for q in Polygon(nt._closed(P)).convex_hull.exterior.coords]
        top_h = [c for c in C if c[1] < cr[1] - 100 and any(math.dist(c, h) < 0.05 for h in hull)]
        waist_c = max(top_h, key=lambda c: sgn * c[0])                               # 볼록 껍질 위 위쪽 꼭짓점 중 가랑이 쪽 끝 = 허리 앞(뒤) 중심
        d = {"g": g, "cr": cr, "side_top": side_top, "waist_c": waist_c,
             "side_hem": max(hem, key=lambda c: -sgn * c[0]), "ins_hem": max(hem, key=lambda c: sgn * c[0])}
        d["rise"] = L(P, d["waist_c"], cr); sp.append(d)
    Ld = lambda d, a, b: L(d["g"][0], d[a], d[b])
    fr = bk = None
    if len(sp) == 2:
        fr, bk = sorted(sp, key=lambda d: d["rise"])                                 # 앞 = 밑위가 짧다
        _label(doc, fr["g"], "split_front"); _label(doc, bk["g"], "split_back")
        side_d = round(min(Ld(fr, "side_hem", "side_top"), Ld(bk, "side_hem", "side_top")) / 2)
        plan.put(fr["g"], fr["side_hem"], fr["side_top"], nt.single(side_d)); plan.put(bk["g"], bk["side_hem"], bk["side_top"], nt.double(side_d))
        report.update({"옆선 앞·뒤": [round(Ld(fr, "side_hem", "side_top"), 1), round(Ld(bk, "side_hem", "side_top"), 1)], "옆선 노치(밑단에서)": side_d,
                       "밑위 앞·뒤": [round(fr["rise"], 1), round(bk["rise"], 1)]})
    elif sp:
        raise AssertionError(f"옆선 있는 판이 {len(sp)}장 — 앞·뒤 짝을 못 정함")
    # 한 장짜리 꼭짓점
    one = []
    for g in wide:
        P = g[0]; C = corners(P); x0, y0, x1, y1 = bbox(P)
        fcr = min(C, key=lambda c: c[0]); bcr = max(C, key=lambda c: c[0])
        cx = (x0 + x1) / 2
        # 밑단 양 끝 = 왼·오른쪽 절반에서 가장 아래 꼭짓점 (슬림은 밑단이 20mm 기울어 «맨 아래 5mm» 로는 한쪽만 잡힌다)
        #   그중에서도 바깥쪽(트임 판의 트임 아래 꼭짓점에 속지 않게)
        lh = [c for c in C if c[0] < cx]; rh = [c for c in C if c[0] > cx]
        ly = max(c[1] for c in lh); ry = max(c[1] for c in rh)
        hem = [min([c for c in lh if c[1] > ly - 5], key=lambda c: c[0]), max([c for c in rh if c[1] > ry - 5], key=lambda c: c[0])]
        # 허리 양 끝 = 볼록 껍질 위의 위쪽 꼭짓점 중 왼·오 끝 — 밑위 곡선의 꺾임(오목)·허리선 가운데 꺾임에 속지 않는다
        hull = [tuple(q) for q in Polygon(nt._closed(P)).convex_hull.exterior.coords]
        top = [c for c in C if c[1] < min(fcr[1], bcr[1]) - 100 and any(math.dist(c, h) < 0.05 for h in hull)]
        fw = min(top, key=lambda c: c[0]); bw = max(top, key=lambda c: c[0])
        slit = [c for c in C if c[1] > y1 - 60 and x0 + 100 < c[0] < x1 - 100]
        one.append({"g": g, "fcr": fcr, "bcr": bcr, "fhem": hem[0], "bhem": hem[-1], "fw": fw, "bw": bw, "slit": slit})
    # 안솔기: 옆선 판이 있으면 그 판 기준, 없으면 한 장짜리 자체 앞·뒤 안솔기
    if fr:
        ins = [Ld(fr, "ins_hem", "cr"), Ld(bk, "ins_hem", "cr")]
    else:
        ins = [L(one[0]["g"][0], one[0]["fhem"], one[0]["fcr"]), L(one[0]["g"][0], one[0]["bhem"], one[0]["bcr"])]
    ins_d = round(min(ins) / 2)
    if fr:
        plan.put(fr["g"], fr["ins_hem"], fr["cr"], nt.single(ins_d)); plan.put(bk["g"], bk["ins_hem"], bk["cr"], nt.double(ins_d))
    report.update({"안솔기 앞·뒤": [round(v, 1) for v in ins], "안솔기 노치(밑단에서)": ins_d})
    # 한 장짜리 옆선 자리: 옆선 판이 있으면 «앞판 허리·밑단 폭 − 옆선 시접», 없으면 트임 V 자리(밑단) · 같은 비율(허리)
    res_one = []
    slit_one = next((o for o in one if len(o["slit"]) >= 2), None)
    for o in one:
        P = o["g"][0]
        plan.put(o["g"], o["fhem"], o["fcr"], nt.single(ins_d)); plan.put(o["g"], o["bhem"], o["bcr"], nt.double(ins_d))
        _label(doc, o["g"], "one_piece_slit" if len(o["slit"]) >= 2 else "one_piece")
        waist = L(P, o["fw"], o["bw"]); hem_len = L(P, o["fhem"], o["bhem"])
        cad = cad_side_x(doc, P)
        if doc.get("side_override"):
            # 손으로 준 값(--side 허리,밑단) — 슬림 XL 은 CAD 세로선이 파일에 없어 L·2XL 의 가운데 값을 준다
            sa = None; how = "지정값(--side)"; dw, dh = doc["side_override"]
        elif cad is not None:
            # 꺼진 레이어의 공장 CAD 도면에 «앞·뒤를 붙인 옆선»이 세로선으로 남아 있으면 그 자리를 쓴다(슬림 하의)
            #   검증 2026-10-19: 일반 하의 5XS 의 CAD 세로선 = 허리 0.5135 · 밑단 0.4254 ↔ 우리가 옆선 판으로 구한 0.5070 · 0.4326
            #   슬림은 사이즈마다 정확히 10mm 씩 옮겨 간다(옆선 그레이딩) — 비율 짐작보다 낫다
            sa = None; how = "CAD 옆선(꺼진 레이어 세로선)"
            dw = along_x(P, o["fw"], o["bw"], cad); dh = along_x(P, o["fhem"], o["bhem"], cad)
        elif fr:
            sa = ((Ld(fr, "waist_c", "side_top") + Ld(bk, "waist_c", "side_top")) - waist) / 2
            dw = Ld(fr, "waist_c", "side_top") - sa; dh = Ld(fr, "ins_hem", "side_hem") - sa; how = "옆선 판 폭 − 시접"
        else:
            # 옆선 판이 없는 파일: 밑단 = 트임 V 꼭짓점 자리 · 허리 = 옆선 판 있는 사이즈의 실측 비율(허리 50.97%)
            sa = None
            if slit_one:
                v = min(slit_one["slit"], key=lambda c: c[1])                         # V 꼭짓점(가장 위)
                SP = slit_one["g"][0]; dh_abs = v[0] - slit_one["fhem"][0]
                dh = dh_abs * hem_len / (slit_one["bhem"][0] - slit_one["fhem"][0])
            else:
                dh = hem_len * 0.4326
            dw = waist * 0.5097; how = "비율(옆선 판 없는 파일)"
        plan.put(o["g"], o["fw"], o["bw"], [dw])
        if len(o["slit"]) < 2: plan.put(o["g"], o["fhem"], o["bhem"], [dh])
        res_one.append({"허리": round(waist, 1), "옆선 시접(추정)": None if sa is None else round(sa, 1), "밑단 트임": len(o["slit"]) >= 2,
                        "옆선 자리 허리(앞 허리끝에서)": round(dw, 1), "옆선 자리 밑단": None if len(o["slit"]) >= 2 else round(dh, 1), "정한 법": how})
    report["한 장짜리"] = res_one
    report["옆선 판"] = len(sp)
    return plan, report


# ── 그레이더용: .ai 한 장 → 조각 외곽선(노치 뺀 깨끗한 선) + 노치 자리 + 조각 이름 ─────────────────────
#   (2026-10-20 메인 세션 권고) 프리셋 SVG 에는 깨끗한 외곽선만 두고, 노치는 «자리 자료»로 따로 둔다
#     → 주문 PDF 재단선은 그릴 때 끼우고(insert_sites), 공장 DXF 는 aama 관례(레이어 4 POINT)로 낸다
#     → 노치 없는 기존 프리셋은 자료가 없으니 아무것도 바뀌지 않는다

RULES = {"jersey": jersey, "pants": pants}


def notch_tips(P):
    """외곽선 P 에 박힌 일자 홈(바닥→끝 3~7mm→바닥)의 끝 점 번호"""
    return [i for i in range(1, len(P) - 1) if math.dist(P[i - 1], P[i + 1]) < 1e-3 and 3 < math.dist(P[i - 1], P[i]) < 7]


def split_slits(P):
    """홈이 박힌 외곽선 → (깨끗한 외곽선, [{"p": 바닥, "w": 안쪽 단위벡터, "depth": 깊이}])  — 닫힘 표시(끝=처음)는 뺀다"""
    Q = list(P)
    if len(Q) > 2 and math.dist(Q[0], Q[-1]) < 1e-6: Q = Q[:-1]
    n = len(Q); T = [i for i in range(n) if math.dist(Q[(i - 1) % n], Q[(i + 1) % n]) < 1e-3 and 3 < math.dist(Q[(i - 1) % n], Q[i]) < 7]
    drop = set(T) | {(i + 1) % n for i in T}
    sites = []
    for i in T:
        b, t = Q[(i - 1) % n], Q[i]; d = math.dist(b, t)
        sites.append({"p": (b[0], b[1]), "w": ((t[0] - b[0]) / d, (t[1] - b[1]) / d), "depth": d})
    bases = {(i - 1) % n for i in T}
    out = [(k, tuple(q)) for k, q in enumerate(Q) if k not in drop]
    keep = []
    for j, (k, q) in enumerate(out):                    # 곧은 토막 위에 끼워졌던 바닥점은 뺀다(꺾인 점 위 바닥점은 원래 점이라 남긴다)
        if k in bases and len(out) > 3:
            a, c = out[j - 1][1], out[(j + 1) % len(out)][1]
            L = math.dist(a, c)
            if L > 1e-9 and abs((c[0] - a[0]) * (q[1] - a[1]) - (c[1] - a[1]) * (q[0] - a[0])) / L < 1e-6: continue
        keep.append(q)
    return keep, sites


def insert_sites(P, sites, depth=None):
    """깨끗한 외곽선 P(닫힌 고리, 끝=처음 아님) 에 노치 자리마다 «바닥 → 안쪽 끝 → 바닥» 을 끼운다(단위는 P 와 같게)
    depth 를 주면 그 깊이, 아니면 자리마다 depth. 바닥은 가장 가까운 토막 위로 붙인다"""
    n = len(P); ins = {}
    for st in sites:
        p = st["p"]; best = None
        for k in range(n):
            a, b = P[k], P[(k + 1) % n]; L2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L2))
            q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t); d = math.dist(p, q)
            if best is None or d < best[0]: best = (d, k, t, q)
        _, k, t, q = best; dd = depth if depth is not None else st.get("depth", nt.DEPTH)
        tip = (q[0] + st["w"][0] * dd, q[1] + st["w"][1] * dd)
        ins.setdefault(k, []).append((t, [q, tip, q]))
    out = []
    for k in range(n):
        out.append(tuple(P[k]))
        for _, trio in sorted(ins.get(k, [])): out.extend(trio)
    return out


def notch_ai(path, rule, side_override=None, min_len=300):
    """.ai(PDF 호환) 한 장 → 조각마다 {"outline": 깨끗한 외곽선(mm), "sites": 노치 자리, "label": 이름|None}
    · 원본에 노치가 이미 박혀 있으면(공장 CAD 원본) 새로 넣지 않고 그 노치를 자리 자료로 옮긴다 — 겹치면 안 된다
    · 곡선은 illustrator.read 가 16토막으로 편다(그레이더 normalize_svg 는 곡선 끝점만 이어 모양이 어긋난다)
    반환: {"pieces": [...], "page_mm": (w, h), "notched": 새로 넣은 수, "existing": 원래 있던 수, "report", "clipped"}"""
    return _notch_doc(ai.read(path), rule, side_override, min_len)


def _notch_doc(doc, rule, side_override=None, min_len=300):
    """notch_ai 의 본체 — 이미 읽은 문서(.ai 또는 SVG)에서"""
    if side_override: doc["side_override"] = list(side_override)
    G = pieces(doc, min_len)
    existing = sum(len(notch_tips(doc["drawings"][mem[0][0]]["subpaths"][mem[0][1]])) for _, mem in G)
    report, n = {}, 0
    if rule and not existing:
        if rule not in RULES: raise ValueError(f"모르는 노치 규칙: {rule} (가능: {', '.join(RULES)})")
        plan, report = RULES[rule](doc)
        n = apply_plan(doc, plan)
        G = pieces(doc, min_len)                       # 노치 든 외곽선으로 다시 모은다(겹친 사본은 하나만)
    labels = doc.get("labels", {}); out = []
    for _, mem in G:
        gi, si = mem[0]
        outline, sites = split_slits(doc["drawings"][gi]["subpaths"][si])
        lab = next((labels[k] for k in mem if k in labels), None)
        out.append({"outline": outline, "sites": sites, "label": lab})
    W, H = doc["page"]
    return {"pieces": out, "page_mm": (W * ai.MM, H * ai.MM), "notched": n, "existing": existing,
            "report": report, "clipped": doc.get("clipped", [])}


def write_polyline_svg(outlines_mm, out_path, margin_mm=10.0):
    """깨끗한 외곽선(mm) → 그레이더 프리셋 SVG(<polyline> 조각마다 1개 · 단위 pt · y 아래로 +, 그레이더 관례).
    대지보다 큰 조각(슬림 하의 A4 대지에 730mm 판)도 잘리지 않게 viewBox 를 조각 전체 + 여백으로 잡고 왼쪽 위를 옮긴다.
    반환 offset_mm 로 노치 자리도 같은 만큼 옮겨야 한다(to_svg_pt)"""
    MM = ai.MM
    xs = [p[0] for P in outlines_mm for p in P]; ys = [p[1] for P in outlines_mm for p in P]
    ox, oy = min(xs) - margin_mm, min(ys) - margin_mm
    W = (max(xs) - ox + margin_mm) / MM; H = (max(ys) - oy + margin_mm) / MM
    rows = ['<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W:.2f}" height="{H:.2f}" viewBox="0 0 {W:.2f} {H:.2f}">']
    for P in outlines_mm:
        Q = list(P) + [P[0]]                           # 닫힘 = 시작점으로 돌아옴(그레이더 관례)
        rows.append('  <polyline class="st0" points="' + " ".join(f"{(x - ox) / MM:.3f} {(y - oy) / MM:.3f}" for x, y in Q) + '"/>')
    rows.append("</svg>")
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: f.write("\n".join(rows) + "\n")
    os.replace(tmp, out_path)
    return {"pieces_written": len(outlines_mm), "viewBox": f"0 0 {W:.2f} {H:.2f}", "offset_mm": (ox, oy)}


def to_svg_pt(sites, offset_mm):
    """노치 자리(mm, 원본 좌표) → 프리셋 SVG 좌표(pt) — write_polyline_svg 와 같은 이동"""
    MM = ai.MM; ox, oy = offset_mm
    return [{"p": [round((s["p"][0] - ox) / MM, 3), round((s["p"][1] - oy) / MM, 3)], "w": [round(s["w"][0], 6), round(s["w"][1], 6)],
             "depth_mm": round(s.get("depth", nt.DEPTH), 3)} for s in sites]


# ── 그레이더 프리셋 한 사이즈: 장수(좌우 2장)·좌우 거울·겹치지 않게 늘어놓기 ───────────────────────────────

def read_svg_doc(path):
    """그레이더 polyline SVG(pt, y 아래로 +) → 이 모듈의 문서(mm). 준비해 둔 조각 묶음(슈팅저지 9종)을 규칙에 넣을 때"""
    import re
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    vb = [float(v) for v in (root.get("viewBox") or f"0 0 {root.get('width')} {root.get('height')}").replace(",", " ").split()]
    num = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
    draws = []
    for el in root.iter():
        if el.tag.split("}")[-1] != "polyline": continue
        v = [float(x) for x in num.findall(el.get("points", ""))]
        P = [((v[i] - vb[0]) * ai.MM, (v[i + 1] - vb[1]) * ai.MM) for i in range(0, len(v) - 1, 2)]
        if len(P) < 3: continue
        if math.dist(P[0], P[-1]) > 1e-6: P.append(P[0])
        draws.append({"type": "s", "color": (0, 0, 0), "fill": None, "width": 1, "dashes": None, "closePath": True, "even_odd": False,
                      "layer": None, "lineCap": 0, "lineJoin": 0, "subpaths": [P]})
    # 그레이더 SVG 의 viewBox 는 «조각 + 여백 10mm» 라 큰 조각 하나가 대지의 90% 를 넘어 «바탕 사각형»으로 빠졌다(2026-10-20 리뷰)
    #   → 판정용 대지를 두 배로 잡는다(좌표는 그대로 · 대지 경계에 잘린 조각 판정에도 걸리지 않는다)
    return {"page": (vb[2] * 2, vb[3] * 2), "drawings": draws, "source": None}


def piece_kind(q):
    """이름표 그대로, 없으면 모양으로: 가로로 긴 띠(폭/높이 > 4) = neck(목 띠) · 나머지 = part(작은 조각)"""
    if q.get("label"): return q["label"]
    xs = [p[0] for p in q["outline"]]; ys = [p[1] for p in q["outline"]]
    return "neck" if (max(xs) - min(xs)) > 4 * (max(ys) - min(ys)) else "part"


def quantity(rule, q):
    """한 벌에 들어가는 장수 — 슈팅저지: 앞판·뒤판·목 띠 1 · 소매·작은 조각 2(좌우) / 하의: 전부 2(좌우 다리)"""
    k = piece_kind(q)
    if rule == "jersey": return 1 if k in ("front", "back", "neck") else 2
    if rule == "pants": return 2
    return 1


def mirror_piece(q):
    """좌우 거울(외곽선 x 를 조각 가운데로 뒤집고 점 순서를 거꾸로 — 돌아가는 방향 유지) · 노치 자리도 같이"""
    xs = [p[0] for p in q["outline"]]; c = min(xs) + max(xs)
    return {"outline": [(c - x, y) for x, y in reversed(q["outline"])],
            "sites": [{"p": (c - s["p"][0], s["p"][1]), "w": (-s["w"][0], s["w"][1]), "depth": s.get("depth", nt.DEPTH)} for s in q["sites"]],
            "label": q.get("label"), "kind": piece_kind(q), "mirror": True}


def arrange(items, gap=30.0, row_width=2400.0):
    """조각을 높이 큰 것부터 줄지어 늘어놓는다(겹치지 않게) — 외곽선·노치 자리를 같은 만큼 옮긴다"""
    def bb(q): xs = [p[0] for p in q["outline"]]; ys = [p[1] for p in q["outline"]]; return min(xs), min(ys), max(xs), max(ys)
    order = sorted(range(len(items)), key=lambda i: -(bb(items[i])[3] - bb(items[i])[1]))
    x = y = row_h = 0.0; out = [None] * len(items)
    for i in order:
        q = items[i]; x0, y0, x1, y1 = bb(q); w, h = x1 - x0, y1 - y0
        if x > 0 and x + w > row_width: x, y, row_h = 0.0, y + row_h + gap, 0.0
        dx, dy = x - x0, y - y0
        out[i] = dict(q, outline=[(p[0] + dx, p[1] + dy) for p in q["outline"]],
                      sites=[dict(s, p=(s["p"][0] + dx, s["p"][1] + dy)) for s in q["sites"]])
        x += w + gap; row_h = max(row_h, h)
    return out


def grader_size(path, rule, side_override=None, select=None, pairs=True):
    """그레이더 등록용 한 사이즈 — .ai(또는 준비한 .svg) → 노치 자리 계산 → 고른 조각만 → 좌우 2장 → 늘어놓기
    select: 남길 조각 이름 목록(하의 방법 고르기: one_piece · split_front+split_back · one_piece_slit). None 이면 전부
    반환: {"pieces": [{"outline","sites","label","kind","mirror"}], "notched", "existing", "report", "clipped", "dropped"}"""
    if str(path).lower().endswith(".svg"):
        doc = read_svg_doc(path)
        r = _notch_doc(doc, rule, side_override)
    else:
        r = notch_ai(path, rule, side_override)
    keep, dropped = [], []
    for q in r["pieces"]:
        q = dict(q, kind=piece_kind(q), mirror=False)
        (keep if not select or q["kind"] in select else dropped).append(q)
    # 좌우 짝: 같은 모양(거울 포함 — 상자 폭·높이·둘레가 같다)이 이미 그려져 있으면 그만큼 덜 만든다
    #   (소매를 두 장 그린 원본·그레이더가 만든 SVG 를 다시 넣어도 두 배가 되지 않게 — 2026-10-20 리뷰)
    def sig(q):
        xs = [p[0] for p in q["outline"]]; ys = [p[1] for p in q["outline"]]
        L = sum(math.dist(q["outline"][i], q["outline"][(i + 1) % len(q["outline"])]) for i in range(len(q["outline"])))
        return (q["kind"], round(max(xs) - min(xs)), round(max(ys) - min(ys)), round(L))
    groups = {}
    for q in keep: groups.setdefault(sig(q), []).append(q)
    items = []
    for g in groups.values():
        items += g
        if pairs:
            for _ in range(max(0, quantity(rule, g[0]) - len(g))): items.append(mirror_piece(g[0]))
    return dict(r, pieces=arrange(items), dropped=[q["kind"] for q in dropped])
