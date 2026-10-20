# 그레이더 프리셋 내보내기 — 노치 규칙(notch_rules.grader_size)이 만든 한 사이즈 조각을
#   ① 깨끗한 외곽선 SVG(<사이즈>.svg — 합성·클립이 쓰는 기존 파일과 같은 형식)
#   ② 노치 든 재단선 SVG(<사이즈>.notched.svg — 주문 PDF 의 빨간 재단선만 이걸로 그린다)
#   ③ 공장용 재단 패턴 DXF(사이즈마다 한 장 — aama.py 관례: 레이어 1 재단선(뾰족점 없음) · 레이어 4 노치 POINT · 조각 이름 글자)
#   (2026-10-20 사장님: «주문 PDF 재단선과 공장용 재단 패턴(DXF) 둘 다 넣어줘»)
#   ⚠️ 프리셋 SVG 는 깨끗한 외곽선만 — 노치는 따로(②·③). 노치 없는 기존 프리셋은 ②가 없어 아무것도 안 바뀐다
import os, math, io
import notch_rules as nr
import illustrator as ai

PIECE_EN = {"front": "FRONT", "back": "BACK", "sleeve": "SLEEVE", "neck": "NECK BAND", "part": "PART",
            "split_front": "FRONT", "split_back": "BACK", "one_piece": "ONE PIECE", "one_piece_slit": "ONE PIECE SLIT"}


def write_svgs(pieces, svg_path, notched_path, margin_mm=10.0):
    """같은 이동으로 ①·② 를 쓴다. 반환 {"pieces_written", "viewBox", "offset_mm", "sites_pt": [조각마다 노치 자리(pt)]}"""
    w = nr.write_polyline_svg([q["outline"] for q in pieces], svg_path, margin_mm)
    _rewrite_with_offset([nr.insert_sites(q["outline"], q["sites"]) for q in pieces], notched_path, w)   # 같은 이동·같은 viewBox
    return dict(w, sites_pt=[nr.to_svg_pt(q["sites"], w["offset_mm"]) for q in pieces])


def _rewrite_with_offset(outlines, path, w):
    MM = ai.MM; ox, oy = w["offset_mm"]; vb = w["viewBox"]; W, H = vb.split()[2:]
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W}" height="{H}" viewBox="{vb}">']
    for P in outlines:
        Q = list(P) + [P[0]]
        rows.append('  <polyline class="st0" points="' + " ".join(f"{(x - ox) / MM:.3f} {(y - oy) / MM:.3f}" for x, y in Q) + '"/>')
    rows.append("</svg>")
    with open(path + ".part", "w", encoding="utf-8") as f: f.write("\n".join(rows) + "\n")
    os.replace(path + ".part", path)


def dxf_bytes(pieces, size, title="STIZ"):
    """한 사이즈 조각 → DXF(R12, mm, y 위로 +) 바이트. 조각마다 BLOCK + INSERT(공장 CAD 가 조각으로 읽는다)
    재단선·노치 표기는 aama.to_aama(점 표기) 그대로 — F10 공장 DXF 와 관례가 같다. 레이어 14(재봉선)는 내지 않는다(이 외곽선이 재단선이라)"""
    import ezdxf
    import aama
    from piecespec import from_legacy
    doc = ezdxf.new("R12")                                                              # 단위 mm(R12 는 단위 칸을 안 쓴다 — aama 와 같음)
    msp = doc.modelspace()
    for k, q in enumerate(pieces):
        P = [(x, -y) for x, y in nr.insert_sites(q["outline"], q["sites"])]                  # y 뒤집기(DXF 는 위로 +)
        P = P + [P[0]]
        p = {"cut": P, "sew": P, "draw": []}
        G = aama.to_aama(p, from_legacy(p), notch_style="point")
        name = f"{size}_{k + 1:02d}"
        blk = doc.blocks.new(name=name)
        for L, pts, closed in G["lines"]:
            if L == "14": continue
            blk.add_polyline2d(pts, close=closed, dxfattribs={"layer": L})
        for lay, pt, ang in G["notch_points"]:
            blk.add_point(pt, dxfattribs={"layer": lay, "angle": ang})
        xs = [v[0] for v in P]; ys = [v[1] for v in P]
        en = PIECE_EN.get(q.get("kind") or q.get("label") or "part", "PART") + (" (MIRROR)" if q.get("mirror") else "")
        aama._texts(blk, ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2),
                    [f"Piece Name: {title} {en}", f"Size: {size}", "Quantity: 1"], layer="1")
        msp.add_blockref(name, (0, 0), dxfattribs={"layer": "1"})
    buf = io.StringIO(); doc.write(buf)
    return buf.getvalue().encode("ascii", "replace")
