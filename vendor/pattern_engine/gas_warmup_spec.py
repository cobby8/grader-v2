# 가스공사 웜업 → 조각 «명세»(piecespec) 로 바꿔 저장 + 시접·재단선 보고
#   실행: python tools/pattern-engine/gas_warmup_spec.py [--pieces <2xl/pieces_after.json>] [--graded <graded/graded.json>] [--out <폴더>]
#   결과: <out>/spec_2XL수정.json · spec_<사이즈>.json · spec_보고.md
#   재단선은 아직 원본 그대로(sa_builtin) — 계산 재단선(compute_cut)과의 차이는 보고만 한다
#   F2(2026-10-19): 하의 밑단(시접 25) 양끝 모서리 방식을 원본 재단선에서 읽어 붙인다(read_corners) —
#     바지 앞판 양끝·뒤판 안솔기 쪽 = 밑단 대칭(hem_mirror), 뒤판 옆선 쪽 = 연장 교차(miter, OptiCad 원본이 그렇게 그렸다)
#   F4~F6(2026-10-19): decorate() — 상의 앞판 주머니 입구 = 자르는 선 · 옆배색 스냅/짝 · 립 식서 · 라벨 틀 · 좌우 조각 뒤집기 금지
#     aama.py 가 import 해서 같은 규칙으로 내보낸다(그래서 실행 부분은 main() 안에 있다)
import sys, os, json, math, argparse
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from piecespec import from_legacy, to_legacy, sa_summary, compare_cut, validate, read_corners, DEFAULT_LABEL
HEM_SA = 25.0                                                # 가스 바지 밑단 시접(mm) — 이 변 양끝이 «밑단 모서리»
from cardinal import back_pts, front_pts_gas, sleeve_pts, pants_pts
from gas_warmup_meta import SPEC_T, SPEC_B

EN = {"뒤판": "BACK", "앞판": "FRONT", "소매": "SLEEVE", "소매중심덧방": "SLEEVE CENTER OVERLAY", "카우스": "CUFF RIB", "밑단립": "HEM RIB",
      "에리(립)": "COLLAR RIB", "앞주머니구찌": "POCKET ZIP FACING", "앞주머니감": "POCKET BAG", "앞옆배색": "FRONT SIDE PANEL SNAP",
      "뒤옆배색": "BACK SIDE PANEL SNAP MATE", "앞구찌": "POCKET ZIP FACING"}


def names_for(garment, name, sew):
    """기준점 이름 → 원본 좌표 (cardinal.py 와 같은 이름 · 같은 찾는 법)"""
    try:
        if garment == "top" and name == "뒤판":
            g, (cx, hy) = back_pts(sew)
            out = {"뒤중심밑단": (cx, hy), "뒤목중심": (cx, hy + g["뒤목중심"][1])}
            for side, tag in ((1, "R"), (-1, "L")):
                for k in ("옆밑단", "겨드랑이", "목옆"):
                    out[f"{k}{tag}"] = (cx + side * g[k][0], hy + g[k][1])
            return out
        if garment == "top" and name == "앞판":
            g, (cfx, hy) = front_pts_gas(sew)
            return {"앞중심밑단": (cfx, hy), **{k: (cfx - v[0], hy + v[1]) for k, v in g.items()}}
        if garment == "top" and name == "소매":
            g, (hx, hy, sg) = sleeve_pts(sew, False)
            return {"밑단가운데": (hx, hy), **{k: (hx + sg * v[0], hy + v[1]) for k, v in g.items()}}
        if garment == "bottom" and name in ("앞판", "뒤판"):
            g, (sx, hy, sg) = pants_pts(sew, name == "뒤판")
            return {k: (sx + sg * v[0], hy + v[1]) for k, v in g.items()}
    except Exception:
        return None
    return None


RIBS = ("카우스", "밑단립", "에리(립)")                         # 립(시보리) — 골 세로 · 늘어나는 방향 가로
SNAP_KIND = {"앞옆배색": "스냅", "뒤옆배색": "짝"}            # 하의 옆배색 똑딱이 — 앞 = 수(스냅) · 뒤 = 암(짝)


def is_pocket_box(d, length=150.0, width=15.0, tol=1.0):
    """주머니 입구 박스(gas_warmup_build 의 «입구 150 × 15 맞춤 박스») — 닫힌 4점 직사각형, 변 길이 15·150"""
    P = d.get("pts") or []
    if not d.get("closed") or d.get("snap") or len(P) != 4: return False
    sides = sorted(math.dist(P[i], P[(i + 1) % 4]) for i in range(4))
    return all(abs(a - width) < tol for a in sides[:2]) and all(abs(a - length) < tol for a in sides[2:])


def decorate(garment, name, sp, side=""):
    """명세에 F4~F6 «값» 을 붙인다 — 모양(점)은 하나도 안 바꾼다. 조각 이름만 보고 붙여서 모든 사이즈·좌우에 똑같이 붙는다
       (사이즈마다 다르게 붙으면 그레이딩 규칙이 어긋난다).
         상의 앞판 주머니 입구 박스 = 자르는 선(cut) · 하의 옆배색 스냅 = 앞 스냅 / 뒤 짝 · 립 = 식서 «골 세로·늘어나는 방향 가로»
         라벨 틀 = 기본 틀 · 좌우 조각 = 뒤집기 금지(나머지는 규칙 기본값 — marker.py 와 같다)"""
    for d in sp.get("internal") or []:
        if garment == "top" and name == "앞판" and is_pocket_box(d): d["cut"] = True
        if garment == "bottom" and name in SNAP_KIND and d.get("snap"): d["kind"] = SNAP_KIND[name]
    if garment == "top" and name in RIBS: sp["grain"] = {"arrow": "both", "rib": True}
    sp["label"] = {"template": DEFAULT_LABEL}
    if side: sp["flip"] = "금지"
    return sp


def to_spec(pcs, size):
    out = {}
    for garment, spec_tbl in (("top", SPEC_T), ("bottom", SPEC_B)):
        out[garment] = {}
        for name, p in pcs[garment].items():
            meta = {"style": "gas-warmup-2026", "garment": "상의" if garment == "top" else "하의", "size": size, "en": EN.get(name, name),
                    "instances": [{"name": a, "mirror": m, "side": sd, "note": nt} for a, m, sd, nt in spec_tbl.get(name, [])]}
            sp = from_legacy(p, names_for(garment, name, p["sew"]), meta)
            if garment == "bottom":                          # 밑단 모서리 방식 — 원본 재단선에 가장 가까운 것(비기면 miter 기본)
                read_corners(sp, hem_sa=HEM_SA)
            decorate(garment, name, sp, "R" if any(sd for _, _, sd, _ in spec_tbl.get(name, [])) else "")   # F4~F6 값(원본 그린 쪽 기준)
            out[garment][name] = sp
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    base = os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup")
    ap.add_argument("--pieces", default=os.path.join(base, "2xl", "pieces_after.json"))
    ap.add_argument("--graded", default=os.path.join(base, "graded", "graded.json"))
    ap.add_argument("--out", default=os.path.join(base, "spec"))
    A = ap.parse_args(argv)
    os.makedirs(A.out, exist_ok=True)
    P2 = json.load(open(A.pieces, encoding="utf-8"))
    G = json.load(open(A.graded, encoding="utf-8")) if os.path.exists(A.graded) else {}
    sets = [("2XL수정", "2XL", P2)] + [(s, s, G[s]) for s in G]
    report = ["# 명세(F1·F2) 보고 — 시접·재단선", "", "| 사이즈 | 옷 | 조각 | 시접(mm: 재봉선 길이) | 계산 재단선−원본 최대(mm) · 자리 | 모서리 방식(miter 아닌 것) | 기준점 | 검사 |", "|---|---|---|---|---|---|---|---|"]
    for tag, size, pcs in sets:
        sp = to_spec(pcs, size)
        json.dump({"style": "gas-warmup-2026", "size": size, "garments": sp}, open(os.path.join(A.out, f"spec_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        if tag in ("2XL수정", "S", "5XL"):
            for g in sp:
                for n, s in sp[g].items():
                    h, at = compare_cut(s)
                    nodes = [x["node"] for x in s["seam"] if x["node"]]
                    cor = [x["corner"] for x in s["seam"] if x.get("corner") not in (None, "miter")]
                    report.append(f"| {tag} | {s['meta']['garment']} | {n} | {sa_summary(s)} | {h} · {at} | {', '.join(cor) or '-'} | {len(nodes)} | {validate(s) or '정상'} |")
    report += ["", "- 시접은 원본 재단선에서 0.5mm 단위로 읽었다. 바지는 허리 3 · 밑단 25 · 나머지 9 — 원본 그대로",
               "- 모서리(F2): 바지 밑단 양끝은 원본에서 읽은 방식 — 앞판 양끝·뒤판 안솔기 쪽 «밑단 대칭»(접는 선에서 다리선 기울기를 거울로 뒤집어 밑단을 접어 올리면 시접이 겹친다), 뒤판 옆선 쪽은 원본이 «연장 교차». 연장 교차만 쓰던 때 어긋남 앞판 2.99 · 뒤판 5.28mm",
               "- 그레이딩 사이즈의 «원본» 재단선은 OptiCad 가 아니라 그레이딩이 재봉선 이동량을 따라 옮긴 것이라, 가랑이 끝처럼 뾰족한 곳에서 계산 재단선과 1mm 안팎 다를 수 있다(계산 쪽이 정확한 평행선)"]
    open(os.path.join(A.out, "spec_보고.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")
    print("명세 저장:", A.out, len(sets), "벌")


if __name__ == "__main__":                                  # import 해도(aama.py 가 decorate 를 쓴다) 아무것도 돌지 않게
    main()
