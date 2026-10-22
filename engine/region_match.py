# -*- coding: utf-8 -*-
"""디자인 속 조각 윤곽 ↔ 패턴 조각 짝짓기(2026-10-20) — 모양으로, 좌우 거울까지 가려서.

왜:
  · 등록 화면에서 영역을 맞추지 않으면 design_region_pt 가 «페이지 균등분할» 어림값이라 그림이 엉뚱하게 잘렸다.
  · 왼·오른 소매처럼 크기가 같은 거울 짝은 크기만 보면 뒤바뀐다 → 한쪽에만 로고가 있으면 반대편에 찍힌다.
어떻게:
  디자인(기준 사이즈 라인작업)에 그려진 닫힌 윤곽(재단 윤곽)을 모두 읽어, 패턴 기준 사이즈 SVG 조각과
  «그대로 겹친 차이»와 «좌우 뒤집어 겹친 차이»를 함께 잰다. 그대로 맞는 것 = 같은 조각, 뒤집어야 맞는 것 = 거울 짝.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

MM = 25.4 / 72


def _flatten(items, n=12):
    pts = []
    for it in items:
        if it[0] == "l":
            a, b = it[1], it[2]
            if not pts:
                pts.append((a.x, a.y))
            pts.append((b.x, b.y))
        elif it[0] == "c":
            p0, p1, p2, p3 = it[1:5]
            if not pts:
                pts.append((p0.x, p0.y))
            for k in range(1, n + 1):
                t = k / n; u = 1 - t
                pts.append((u ** 3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t ** 3 * p3.x,
                            u ** 3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t ** 3 * p3.y))
        elif it[0] == "re":
            r = it[1]
            pts += [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
        elif it[0] == "qu":
            q = it[1]
            pts += [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
    return pts


def design_outlines(design_pdf: str, min_mm: float = 40.0) -> List[dict]:
    """디자인 첫 페이지의 «선이 있는» 닫힌 큰 경로 = 재단 윤곽 후보. 좌표는 PDF(y 위로)."""
    import fitz
    doc = fitz.open(design_pdf)
    pg = doc[0]
    H = pg.rect.height
    out = []
    for d in pg.get_drawings():
        r = d["rect"]
        if not d.get("color") or r.width * MM < min_mm or r.height * MM < min_mm * 0.3:
            continue
        P = _flatten(d["items"])
        if len(P) < 4:
            continue
        P = [(x, H - y) for x, y in P]
        xs = [p[0] for p in P]; ys = [p[1] for p in P]
        box = (min(xs), min(ys), max(xs), max(ys))
        if any(all(abs(a - b) < 1.0 for a, b in zip(box, q["bbox"])) for q in out):
            continue                       # 채움+선 따로 그린 같은 윤곽
        out.append({"points": P, "bbox": box})
    doc.close()
    return out


def _resample(P, n=160):
    L = sum(math.dist(P[i], P[(i + 1) % len(P)]) for i in range(len(P)))
    if L <= 0:
        return list(P)
    step = L / n
    out = [P[0]]; acc = 0.0; cur = P[0]; i = 0
    pts = list(P) + [P[0]]
    while len(out) < n and i < len(pts) - 1:
        nxt = pts[i + 1]
        seg = math.dist(cur, nxt)
        if seg > 0 and acc + seg >= step:
            t = (step - acc) / seg
            cur = (cur[0] + (nxt[0] - cur[0]) * t, cur[1] + (nxt[1] - cur[1]) * t)
            out.append(cur); acc = 0.0
        else:
            acc += seg; cur = nxt; i += 1
    return out


def _shape_cost(A, B, mirror=False) -> float:
    """두 윤곽을 bbox 가운데로 맞춰 겹친 평균 차이(mm). mirror 면 B 를 좌우로 뒤집는다."""
    import numpy as np
    a = np.array(_resample(A)); b = np.array(_resample(B))
    if mirror:
        b[:, 0] = -b[:, 0]
    a -= (a.min(0) + a.max(0)) / 2
    b -= (b.min(0) + b.max(0)) / 2
    d = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1))
    return float((d.min(1).mean() + d.min(0).mean()) / 2 * MM)


def match_regions(design_pdf: str, svg_polys, max_cost_mm: float = 6.0,
                  prefer: str = "top") -> Dict[int, dict]:
    """패턴 조각(svg_polys, parse_svg 결과) 마다 디자인 속 같은 모양 윤곽을 찾는다.

    반환: {svg_index: {"region_pt": (x0,y0,x1,y1), "cost_mm", "mirrored": 뒤집어야 맞았나, "alts": 같은 모양 개수}}
      · 같은 모양이 여러 벌(양면 두 면 등)이면 prefer="top" 이면 위쪽 벌을 쓴다(나머지는 alts 로 알린다).
      · 크기가 아주 다르거나(5% 넘게) 차이가 max_cost_mm 를 넘으면 짝이 없다.
    """
    outs = design_outlines(design_pdf)
    cand = []
    for si, sp in enumerate(svg_polys):
        sw, sh = sp.width, sp.height
        for oi, o in enumerate(outs):
            ow = o["bbox"][2] - o["bbox"][0]; oh = o["bbox"][3] - o["bbox"][1]
            if abs(ow - sw) > 0.05 * sw or abs(oh - sh) > 0.05 * sh:
                continue
            c0 = _shape_cost(o["points"], sp.points)
            c1 = _shape_cost(o["points"], sp.points, mirror=True)
            # 거울 짝을 가르는 핵심: 그대로 겹친 것이 뚜렷이 나아야 «같은 조각»
            if c0 <= max_cost_mm:
                cand.append((c0, si, oi, False, c1))
            elif c1 <= max_cost_mm:
                cand.append((c1 + 0.5, si, oi, True, c0))   # 뒤집어야 맞는 것은 마지막 수단
    # 같은 조각에 같은 모양이 여러 벌이면 위쪽(또는 아래쪽) 벌 먼저 · 모양이 좌우대칭이라 둘 다 맞으면
    #   «패턴에서 왼쪽 조각 ↔ 디자인에서 왼쪽 윤곽» (상대 가로 위치가 가까운 것)
    def _rel(xs):
        lo, hi = min(xs), max(xs)
        return [(x - lo) / (hi - lo) if hi > lo else 0.5 for x in xs]
    srx = _rel([(sp.bbox[0] + sp.bbox[2]) / 2 for sp in svg_polys]) if svg_polys else []
    orx = _rel([(o["bbox"][0] + o["bbox"][2]) / 2 for o in outs]) if outs else []

    def key(c):
        o = outs[c[2]]
        top = -o["bbox"][3] if prefer == "top" else o["bbox"][1]
        return (round(c[0], 1), round(top, -1), abs(srx[c[1]] - orx[c[2]]))
    cand.sort(key=key)
    got: Dict[int, dict] = {}
    used = set()
    for cost, si, oi, mir, other in cand:
        if si in got or oi in used:
            continue
        same = [c for c in cand if c[1] == si and not c[3] and abs(c[0] - cost) < 1.0]
        got[si] = {"region_pt": tuple(round(v, 2) for v in outs[oi]["bbox"]), "cost_mm": round(cost, 2),
                   "mirrored": mir, "alts": len(same)}
        used.add(oi)
    # 양면(두 번째 면 이후): 첫 면에 쓰지 않은 윤곽만으로 «모든 조각»이 다시 한 벌씩 짝지어지면 한 면 더.
    #   (리뷰 지적: 조각마다 같은 모양 목록을 따로 만들면 옆 조각 윤곽까지 들어가 면이 섞이고 면 수가 부풀었다)
    sides = []
    first = {si: v for si, v in got.items() if not v["mirrored"]}
    if first and len(first) == len(got):
        while True:
            rnd: Dict[int, tuple] = {}
            taken = set()
            for cost, si, oi, mir, other in sorted(cand, key=key):
                if mir or si in rnd or oi in used or oi in taken or si not in first:
                    continue
                rnd[si] = tuple(round(v, 2) for v in outs[oi]["bbox"])
                taken.add(oi)
            if len(rnd) != len(first):
                break
            sides.append(rnd)
            used |= taken
    # 디자인엔 한 장뿐인 거울 짝(왼·오른 소매): 남은 조각은 이미 쓴 윤곽이라도 «뒤집어 맞으면» 그 그림을 뒤집어 쓴다
    for cost, si, oi, mir, other in sorted(cand, key=key):
        if si in got:
            continue
        if not mir and other <= max_cost_mm and oi in used:
            got[si] = {"region_pt": tuple(round(v, 2) for v in outs[oi]["bbox"]), "cost_mm": round(other, 2),
                       "mirrored": True, "alts": 1}
        elif mir and oi in used:
            got[si] = {"region_pt": tuple(round(v, 2) for v in outs[oi]["bbox"]), "cost_mm": round(cost - 0.5, 2),
                       "mirrored": True, "alts": 1}
    if sides:
        got["_sides"] = sides      # [ {svg_index: region} ] — 두 번째 면부터
    else:
        # (2026-10-21) 패턴엔 한 장뿐인데(유소년 소매) 디자인엔 같은 모양이 하나 더 있으면(왼·오른 소매) 그것도 찍는다.
        #   김현서: «유소년은 소매가 패턴마다 하나씩 들어 있는 것이 있다. 반전해서 사용해도 무방».
        #   패턴에 비슷한 크기 조각이 둘 이상이면(이미 왼·오른이 있음) 하지 않는다.
        def _single(si):
            sw, sh = svg_polys[si].width, svg_polys[si].height
            return sum(1 for q in svg_polys if abs(q.width - sw) <= 0.05 * sw and abs(q.height - sh) <= 0.05 * sh) == 1
        extra = []
        for cost, si, oi, mir, other in sorted(cand, key=key):
            if oi in used or si not in got or not _single(si) or any(e["svg_index"] == si for e in extra):
                continue
            c_norm, c_mir = (cost, other) if not mir else (other, cost - 0.5)
            extra.append({"svg_index": si, "region_pt": tuple(round(v, 2) for v in outs[oi]["bbox"]),
                          "mirrored": c_mir < c_norm})     # 디자인 윤곽에 더 잘 맞는 쪽(왼·오른 소매는 거울)
            used.add(oi)
        if extra:
            got["_extra"] = extra   # [{svg_index, region_pt, mirrored: 패턴 모양을 뒤집어 재단}]
    return got
