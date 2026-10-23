# 솔기 대조 검사 — 꿰매지는 짝끼리 길이·노치·시접이 맞는지 잰다 (2026-10-22)
#
#   재봉사가 봉제 전에 줄자로 «앞 어깨 = 뒤 어깨» 를 맞춰 보는 일을 숫자로 한다.
#   재는 것은 내보낸 조각의 재봉선(spec seam) 그대로 — 설계도 공식이 아니라 «실제로 나간 조각» 을 본다.
#
#   스타일 JSON 의 "sewing" 칸이 짝을 정한다:
#     "seams": [{"key", "ko", "kind": equal|ease|ratio, "a": [변…], "b": [변…], "min", "max", "notches": [[a쪽 노치, b쪽 노치]…]}]
#     변 = [조각, 시작점, 끝점] 또는 [조각, 시작점, 끝점, "rev"](재봉선을 거꾸로 따라감)
#     점 = 재봉선 기준점 이름(HPS·SP_L …) 또는 "@이름"(설계도 점 — 재봉선에서 가장 가까운 꼭짓점. 이름 끝 _L 은 좌우 거울)
#   kind: equal = 길이가 같아야(허용 tol_mm · 주의 warn_mm) · ease = b 가 a 보다 min~max mm 길어야(소매산 여유)
#         ratio = b/a 가 min~max(립을 늘려 다는 솔기)
#   한쪽(오른쪽)만 잰다 — 왼쪽은 설계도에서 거울로 펼쳐 같은 길이다(mirror_x).
import math

STATUS_KO = {"ok": "맞음", "warn": "주의", "bad": "어긋남"}


class SeamCheckError(ValueError):
    pass


def _xy(s):
    return (s["x"], s["y"])


def _find(seam, name, model):
    """점 이름 → 재봉선 꼭짓점 번호"""
    if name.startswith("@"):
        nm = name[1:]; flip = nm.endswith("_L")
        if model is None:
            raise SeamCheckError(f"설계도 점 {name} 을 찾으려면 모델이 필요합니다")
        p = model.get(nm[:-2] if flip else nm)
        q = (-p[0], p[1]) if flip else (p[0], p[1])
        i = min(range(len(seam)), key=lambda k: math.dist(_xy(seam[k]), q))
        if math.dist(_xy(seam[i]), q) > 0.5:
            raise SeamCheckError(f"설계도 점 {name} 이 재봉선 꼭짓점과 {math.dist(_xy(seam[i]), q):.1f}mm 떨어져 있습니다")
        return i
    for i, s in enumerate(seam):
        if s.get("node") == name:
            return i
    raise SeamCheckError(f"재봉선에 기준점 {name} 이 없습니다")


def edge_points(seam, a, b, rev=False, model=None):
    """재봉선 a → b 꼭짓점 목록(앞으로, rev 면 뒤로)"""
    n = len(seam); i, j = _find(seam, a, model), _find(seam, b, model)
    step = -1 if rev else 1
    idx = [i]
    while idx[-1] != j:
        idx.append((idx[-1] + step) % n)
        if len(idx) > n:
            raise SeamCheckError(f"{a} → {b} 를 따라가지 못했습니다")
    return [seam[k] for k in idx]


def _length(pts):
    return sum(math.dist(_xy(pts[k]), _xy(pts[k + 1])) for k in range(len(pts) - 1))


def chain(specs, edges, model=None):
    """변 목록 → {"pts": 이어 붙인 꼭짓점, "length", "sa": 쓰인 시접 집합, "parts": [(조각, 길이)]}"""
    pts, parts, sas = [], [], set()
    for e in edges:
        piece, a, b = e[0], e[1], e[2]
        rev = len(e) > 3 and e[3] == "rev"
        if piece not in specs:
            raise SeamCheckError(f"조각 «{piece}» 이 없습니다")
        seam = specs[piece]["seam"]
        ep = edge_points(seam, a, b, rev, model)
        # 이 변들의 시접 — 점의 sa 는 «이 점 → 다음 점» 변의 시접. 뒤로 가면 다음 점 것이 그 변의 시접
        for k in range(len(ep) - 1):
            s = ep[k + 1] if rev else ep[k]
            if s.get("sa") is not None: sas.add(round(float(s["sa"]), 1))
        parts.append((piece, round(_length(ep), 1)))
        pts += ep if not pts else ep[1:]
    return {"pts": pts, "length": round(sum(p[1] for p in parts), 1), "sa": sorted(sas), "parts": parts}


def _notch_from_end(pts, ref):
    """노치 ref 가 이 솔기의 «끝» 에서 재봉선을 따라 몇 mm 인지 — 없으면 None"""
    for k, s in enumerate(pts):
        if (s.get("notch") or {}).get("ref") == ref:
            return round(_length(pts[k:]), 1)
    return None


def check_size(specs, sewing, model=None):
    """한 사이즈 — 짝마다 결과 목록"""
    tol = float(sewing.get("tol_mm", 1.0)); warn = float(sewing.get("warn_mm", 3.0))
    out = []
    for sd in sewing["seams"]:
        A, B = chain(specs, sd["a"], model), chain(specs, sd["b"], model)
        la, lb = A["length"], B["length"]
        kind = sd.get("kind", "equal")
        r = {"key": sd["key"], "ko": sd["ko"], "kind": kind, "a": la, "b": lb, "diff": round(lb - la, 1),
             "a_parts": A["parts"], "b_parts": B["parts"]}
        if kind == "equal":
            d = abs(lb - la)
            r["status"] = "ok" if d <= tol else "warn" if d <= warn else "bad"
            r["say"] = "같음" if d <= tol else f"{d:.1f}mm 차이"
        elif kind == "ease":
            e = lb - la; lo, hi = float(sd.get("min", 0)), float(sd.get("max", 20))
            r["ease"] = round(e, 1)
            r["status"] = "ok" if lo <= e <= hi else "warn" if lo - warn <= e <= hi + warn else "bad"
            r["say"] = f"여유 {e:+.1f}mm (기준 {lo:g}~{hi:g})"
        elif kind == "ratio":
            q = lb / la if la else 0; lo, hi = float(sd.get("min", 0)), float(sd.get("max", 1))
            r["ratio"] = round(q, 3)
            r["status"] = "ok" if lo <= q <= hi else "bad"
            r["say"] = f"{q * 100:.0f}% 길이 — {1 / q:.2f}배 늘려 단다 (기준 {lo * 100:g}~{hi * 100:g}%)" if q else "길이 0"
        else:
            raise SeamCheckError(f"솔기 종류를 모르겠습니다: {kind}")
        if sd.get("same_sa", True) and A["sa"] and B["sa"] and A["sa"] != B["sa"]:
            r["status"] = "bad" if r["status"] != "bad" else r["status"]
            r["say"] += f" · 시접이 다름({'/'.join(map(str, A['sa']))} vs {'/'.join(map(str, B['sa']))}mm)"
        r["sa"] = A["sa"] or B["sa"]
        notes = []
        for na, nb in sd.get("notches") or []:
            pa, pb = _notch_from_end(A["pts"], na), _notch_from_end(B["pts"], nb)
            if pa is None or pb is None:
                notes.append({"a": na, "b": nb, "missing": True}); r["status"] = "bad"
                r["say"] += f" · 노치 {na if pa is None else nb} 없음"
                continue
            notes.append({"a": na, "b": nb, "a_mm": pa, "b_mm": pb, "diff": round(pb - pa, 1)})
        if notes:
            r["notches"] = notes
        if kind == "ease" and notes and not any(n.get("missing") for n in notes):
            # 노치끼리 맞춰 꿰매면 여유가 노치 아래(끝~노치)·위(노치~시작)로 나뉜다 — 어느 쪽이 모자라면(음수) 소매가 당긴다
            below = max(n["diff"] for n in notes); above = round(r["ease"] - below, 1)
            r["ease_below"], r["ease_above"] = round(below, 1), above
            if min(below, above) < -tol:
                if r["status"] == "ok": r["status"] = "warn"
                short = "위" if above < below else "아래"
                r["say"] += f" · 노치로 나누면 아래 {below:+.1f} / 위 {above:+.1f}mm — 노치 {short}쪽 소매가 모자람"
        out.append(r)
    return out


def check(specs_by_size, sewing, models=None):
    """사이즈마다 검사 → {"sizes": {사이즈: [결과…]}, "ok": bool, "bad": [(사이즈, 짝 이름, 설명)…], "warn": […]}"""
    res = {"sizes": {}, "bad": [], "warn": []}
    for s, specs in specs_by_size.items():
        rows = check_size(specs, sewing, (models or {}).get(s))
        res["sizes"][s] = rows
        for r in rows:
            if r["status"] in ("bad", "warn"):
                res[r["status"]].append((s, r["ko"], r["say"]))
    res["ok"] = not res["bad"]
    res["seams"] = len(sewing["seams"])
    return res


def md_section(res, sizes):
    """확인표용 표 — 짝마다 한 줄, 사이즈마다 칸(맞음/주의/어긋남 + 핵심 수치)"""
    def cell(r):
        k = r["kind"]
        v = f"{r['diff']:+.1f}" if k == "equal" else f"+{r['ease']:.1f}" if k == "ease" else f"{r['ratio'] * 100:.0f}%"
        mark = {"ok": "", "warn": "⚠ ", "bad": "✖ "}[r["status"]]
        return f"{mark}{v}"
    first = res["sizes"][sizes[0]]
    lines = ["| 솔기 | 짝 | " + " | ".join(sizes) + " |", "|---|---|" + "---|" * len(sizes)]
    for i, r in enumerate(first):
        pair = " + ".join(dict.fromkeys(p for p, _ in r["a_parts"])) + " ↔ " + " + ".join(dict.fromkeys(p for p, _ in r["b_parts"]))
        lines.append(f"| {r['ko']} | {pair} | " + " | ".join(cell(res["sizes"][s][i]) for s in sizes) + " |")
    return "\n".join(lines)


def md_issues(res, sizes):
    """확인할 것 — 솔기마다 한 줄(사이즈마다 같은 문제가 되풀이되면 가장 작은·큰 사이즈 값만)"""
    out = []
    for i, r0 in enumerate(res["sizes"][sizes[0]]):
        hit = [(s, res["sizes"][s][i]) for s in sizes if res["sizes"][s][i]["status"] in ("bad", "warn")]
        if not hit:
            continue
        mark = "✖" if any(r["status"] == "bad" for _, r in hit) else "⚠"
        ss = "·".join(s for s, _ in hit) if len(hit) < len(sizes) else "모든 사이즈"
        say = hit[0][1]["say"] if len(hit) == 1 else f"{hit[0][0]} {hit[0][1]['say']} … {hit[-1][0]} {hit[-1][1]['say']}"
        out.append(f"{mark} 솔기 «{r0['ko']}» ({ss}): {say}")
    return out
