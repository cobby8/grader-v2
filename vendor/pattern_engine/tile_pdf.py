# A4 분할 PDF — 1:1 패턴 PDF 한 장을 사무실 프린터로 뽑아 붙일 수 있게 A4 여러 장으로 쪼갠다 (차용 명세서 F8)
#
#   왜: 1:1 패턴은 폭 1.8m 가 넘어 플로터가 없으면 못 뽑는다. 샘플 한 벌은 A4 로 뽑아 이어 붙이면 된다.
#   규칙
#     · 용지 방향(가로/세로)은 쪽 수가 적은 쪽으로 자동
#     · 이웃 장끼리 «겹침 10mm» — 같은 그림이 두 장에 다 찍힌다. 겹침 가운데 점선 + 십자 맞춤 표시
#     · 쪽 번호 «행-열»(위에서부터 행, 왼쪽에서부터 열) + 이웃 장 번호를 가장자리에
#     · 첫 장 = 안내 장: 100mm 확인 자(가로·세로) · 붙이는 순서 지도 · «100% 로 인쇄»
#   그리는 위치는 원본 좌표에서 정한다 — 그래서 겹치는 두 장에 같은 표시가 «같은 자리»에 찍힌다
#   실행: python tools/pattern-engine/tile_pdf.py <1대1.pdf> <결과.pdf> [--overlap 10] [--margin 10] [--title 글자]
#   결과 옆에 <결과>.json — 행·열·겹침·장마다 원본 범위(시험·사람 확인용)
import sys, os, json, math, argparse
sys.stdout.reconfigure(encoding="utf-8")
import fitz

PT = 72 / 25.4                      # mm → pt
A4 = (210.0, 297.0)
FONT = "C:/Windows/Fonts/malgun.ttf"


def _layout(W, H, paper, margin, overlap):
    """용지 방향 하나에 대해 (열 수, 행 수, 그림 칸 폭·높이, 한 칸씩 나아가는 거리)"""
    cw, ch = paper[0] - 2 * margin, paper[1] - 2 * margin
    sx, sy = cw - overlap, ch - overlap
    cols = max(1, math.ceil((W - overlap) / sx)); rows = max(1, math.ceil((H - overlap) / sy))
    return {"paper": paper, "cw": cw, "ch": ch, "sx": sx, "sy": sy, "cols": cols, "rows": rows}


def _ink_boxes(page):
    """원본 쪽에서 무언가 그려진 상자들(mm) — 빈 장 판정용"""
    out = [fitz.Rect(d["rect"]) for d in page.get_drawings()]
    out += [fitz.Rect(b[:4]) for b in page.get_text("blocks")]
    return [fitz.Rect(r.x0 / PT, r.y0 / PT, r.x1 / PT, r.y1 / PT) for r in out]


def tile(src, dst, overlap=10.0, margin=10.0, title=None, page_no=0):
    S = fitz.open(src); sp = S[page_no]
    W, H = sp.rect.width / PT, sp.rect.height / PT                 # 원본 크기(mm)
    cand = [_layout(W, H, A4, margin, overlap), _layout(W, H, (A4[1], A4[0]), margin, overlap)]
    L = min(cand, key=lambda c: (c["rows"] * c["cols"], c["paper"][0] > c["paper"][1]))   # 장 수 적은 쪽, 같으면 세로
    pw, ph = L["paper"]; cols, rows = L["cols"], L["rows"]
    title = title or os.path.splitext(os.path.basename(src))[0]
    ink = _ink_boxes(sp)
    out = fitz.open(); font = fitz.Font(fontfile=FONT)

    def text(page, x, y, s, fs=8, color=(0, 0, 0), center=False):
        if center: x -= font.text_length(s, fontsize=fs) / PT / 2
        page.insert_text(fitz.Point(x * PT, y * PT), s, fontsize=fs, fontname="tilefont", fontfile=FONT, color=color)   # 원본에 든 글꼴 이름(malgun)과 겹치면 글자가 깨진다

    # 겹침 가운데 선 (원본 좌표, mm) — 열 c 와 c+1 사이 = (c+1)·sx + 겹침/2
    XS = [(c + 1) * L["sx"] + overlap / 2 for c in range(cols - 1)]
    YS = [(r + 1) * L["sy"] + overlap / 2 for r in range(rows - 1)]
    # 십자 맞춤 표시 자리(원본 mm) — 겹침 선이 만나는 곳 + 겹침 선 위 칸 가운데. 원본 좌표라 이웃한 두 장에 같은 자리로 찍힌다
    MARKS = [(X, Y) for X in XS for Y in YS]
    MARKS += [(X, r * L["sy"] + L["ch"] / 2) for X in XS for r in range(rows)]
    MARKS += [(c * L["sx"] + L["cw"] / 2, Y) for Y in YS for c in range(cols)]

    # ── 첫 장: 안내 · 100mm 자 · 붙이는 지도 ──
    cover = out.new_page(width=pw * PT, height=ph * PT)
    text(cover, 15, 20, f"{title} — A4 분할 {rows}행 × {cols}열 = {rows * cols}장 (이 안내 장 빼고)", 12)
    for i, s in enumerate([f"원본 {W:.0f} × {H:.0f} mm · 용지 {'가로' if pw > ph else '세로'} A4 · 겹침 {overlap:g}mm · 여백 {margin:g}mm",
                           "인쇄: «실제 크기 / 100%» 로. «페이지에 맞춤» 을 끄세요.",
                           "확인: 아래 자가 정확히 100mm 인지 자로 재 보세요 (가로·세로 둘 다).",
                           "붙이기: 점선(겹침 가운데)에서 한쪽 장의 여백을 잘라 내고, 십자 표시를 겹쳐 붙입니다.",
                           "쪽 번호 = 행-열 (위에서부터 행, 왼쪽에서부터 열). 회색 칸은 그림이 없는 장 — 안 뽑아도 됩니다."]):
        text(cover, 15, 30 + i * 6, s, 9)
    sh = cover.new_shape()                                         # 100mm 자 — 가로
    x0, y0 = 15, 70
    sh.draw_line(fitz.Point(x0 * PT, y0 * PT), fitz.Point((x0 + 100) * PT, y0 * PT))
    for k in range(101):
        t = 6 if k % 10 == 0 else (4 if k % 5 == 0 else 2)
        sh.draw_line(fitz.Point((x0 + k) * PT, y0 * PT), fitz.Point((x0 + k) * PT, (y0 - t) * PT))
    x1, y1 = 140, 60                                               # 100mm 자 — 세로
    sh.draw_line(fitz.Point(x1 * PT, y1 * PT), fitz.Point(x1 * PT, (y1 + 100) * PT))
    for k in range(101):
        t = 6 if k % 10 == 0 else (4 if k % 5 == 0 else 2)
        sh.draw_line(fitz.Point(x1 * PT, (y1 + k) * PT), fitz.Point((x1 + t) * PT, (y1 + k) * PT))
    sh.finish(color=(0, 0, 0), width=0.5); sh.commit()
    for k in (0, 50, 100):
        text(cover, x0 + k, y0 + 4, f"{k}", 7, center=True); text(cover, x1 + 8, y1 + k + 1, f"{k}", 7)
    text(cover, x0 + 50, y0 + 9, "100 mm", 9, center=True)
    # 붙이는 지도
    gx, gy = (15, 175) if ph > pw else (160, 62)                   # 지도 — 세로 용지는 자 아래, 가로 용지는 자 오른쪽
    k = min((pw - gx - 15) / (cols * L["sx"]), (ph - gy - 15) / (rows * L["sy"]), 25.0 / L["sx"])   # 지도 칸 = 장 하나 비율
    gw, gh = L["sx"] * k, L["sy"] * k
    tiles_info = []
    for r in range(rows):
        for c in range(cols):
            clip = fitz.Rect(c * L["sx"], r * L["sy"], c * L["sx"] + L["cw"], r * L["sy"] + L["ch"])
            blank = not any(b.intersects(clip) for b in ink)
            tiles_info.append({"row": r + 1, "col": c + 1, "label": f"{r + 1}-{c + 1}", "page": 2 + r * cols + c,
                               "src_mm": [round(clip.x0, 3), round(clip.y0, 3), round(clip.x1, 3), round(clip.y1, 3)], "blank": blank})
            rr = fitz.Rect((gx + c * gw) * PT, (gy + r * gh) * PT, (gx + (c + 1) * gw) * PT, (gy + (r + 1) * gh) * PT)
            cover.draw_rect(rr, color=(0.4, 0.4, 0.4), fill=(0.85, 0.85, 0.85) if blank else None, width=0.4)
            text(cover, gx + c * gw + gw / 2, gy + r * gh + gh / 2 + 1.2, f"{r + 1}-{c + 1}", 6 if gw < 15 else 8, center=True)

    # ── 분할 장 ──
    for t in tiles_info:
        r, c = t["row"] - 1, t["col"] - 1; x0, y0, x1, y1 = t["src_mm"]
        page = out.new_page(width=pw * PT, height=ph * PT)
        # 원본을 잘라 붙인다 — 원본 밖으로 나가는 끝 장은 안쪽만 잘라 같은 비율 자리에
        cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        if cx1 > cx0 and cy1 > cy0:
            dst_r = fitz.Rect((margin + cx0 - x0) * PT, (margin + cy0 - y0) * PT, (margin + cx1 - x0) * PT, (margin + cy1 - y0) * PT)
            page.show_pdf_page(dst_r, S, page_no, clip=fitz.Rect(cx0 * PT, cy0 * PT, cx1 * PT, cy1 * PT))
        P = lambda X, Y: fitz.Point((margin + X - x0) * PT, (margin + Y - y0) * PT)   # 원본 mm → 이 장 pt
        inside = lambda X, Y: x0 - 1e-6 <= X <= x1 + 1e-6 and y0 - 1e-6 <= Y <= y1 + 1e-6
        sh = page.new_shape()
        for X in XS:                                               # 겹침 가운데 세로 점선
            if x0 <= X <= x1: sh.draw_line(P(X, y0), P(X, y1))
        for Y in YS:
            if y0 <= Y <= y1: sh.draw_line(P(x0, Y), P(x1, Y))
        sh.finish(color=(0.55, 0.55, 0.55), width=0.3, dashes="[2 2] 0"); sh.commit()
        sh = page.new_shape()                                      # 십자 맞춤 표시 — 원본 좌표에 고정된 MARKS 중 이 장 안에 든 것
        for X, Y in MARKS:
            if not inside(X, Y): continue
            sh.draw_line(P(X - 4, Y), P(X + 4, Y)); sh.draw_line(P(X, Y - 4), P(X, Y + 4)); sh.draw_circle(P(X, Y), 2 * PT)
        sh.finish(color=(0, 0, 0), width=0.4); sh.commit()
        page.draw_rect(fitz.Rect(margin * PT, margin * PT, (pw - margin) * PT, (ph - margin) * PT), color=(0.75, 0.75, 0.75), width=0.3)
        # 여백 글자 — 그림 칸 밖에만
        text(page, margin, margin - 3, f"{t['label']}", 11)
        text(page, margin + 14, margin - 3, f"{title} · 행 {r + 1}/{rows} · 열 {c + 1}/{cols} · 겹침 {overlap:g}mm · 100% 인쇄", 7)
        g = (0.35, 0.35, 0.35)
        if c > 0: text(page, 1.5, ph / 2, f"← {r + 1}-{c}", 7, g)
        if c < cols - 1: text(page, pw - margin + 0.8, ph / 2, f"{r + 1}-{c + 2} →", 7, g)
        if r > 0: text(page, pw / 2, margin - 3, f"↑ {r}-{c + 1}", 7, g, center=True)
        if r < rows - 1: text(page, pw / 2, ph - margin + 5, f"↓ {r + 2}-{c + 1}", 7, g, center=True)
        if t["blank"]: text(page, pw / 2, ph - margin + 5 if r == rows - 1 else ph - 3, "그림 없음 — 안 뽑아도 됨", 7, g, center=True)
    out.set_metadata({"title": f"{title} A4 분할", "creator": "STIZ pattern-engine tile_pdf 2026-10-19"})
    out.subset_fonts(); out.save(dst, garbage=3, deflate=True)
    info = {"src": os.path.basename(src), "src_mm": [round(W, 3), round(H, 3)], "paper_mm": [pw, ph],
            "orientation": "landscape" if pw > ph else "portrait", "margin_mm": margin, "overlap_mm": overlap,
            "rows": rows, "cols": cols, "pages": 1 + rows * cols, "step_mm": [L["sx"], L["sy"]], "cell_mm": [L["cw"], L["ch"]],
            "blank_tiles": [t["label"] for t in tiles_info if t["blank"]], "tiles": tiles_info}
    with open(os.path.splitext(dst)[0] + ".json", "w", encoding="utf-8") as f: json.dump(info, f, ensure_ascii=False, indent=1)
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--overlap", type=float, default=10.0); ap.add_argument("--margin", type=float, default=10.0)
    ap.add_argument("--title")
    a = ap.parse_args()
    i = tile(a.src, a.dst, a.overlap, a.margin, a.title)
    print(f"{a.dst}: {i['orientation']} A4 {i['rows']}행×{i['cols']}열 = {i['rows'] * i['cols']}장 + 안내 1장 · 빈 장 {len(i['blank_tiles'])}")
