# 정확도 점검 3바퀴 수정 시험(2026-10-21)
#   실행: python -m unittest tests.test_round3_fixes -v   (저장소 루트)
#   ① 완성본 번호 찾기 — 앞·뒤 «같은 숫자» 짝 · 두 벌이면 위 벌 + 아래 벌 색  ② 테두리 번호
#   ③ 평탄화 — 반투명 요소마다 바로 밑 색과 섞기 · 얇은 테는 배경 아님  ④ 아동 호수  ⑤ 조각 이름은 모양으로
import os, sys, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _glyph(x, y, w, h, col):
    return {"bbox": (x, y, x + w, y + h), "color": col}


def _num(x, y, h, col, gap=0.1):
    """«23» 처럼 폭 0.7h 글자 두 개."""
    w = 0.7 * h
    return [_glyph(x, y, w, h, col), _glyph(x + w + gap * h, y, w, h, col)]


class NumberPair(unittest.TestCase):
    def test_two_kits_pick_top_and_side_color(self):
        from engine.reference import _find_number_pair
        red, white = (0.0, 0.8, 0.4, 0.4), (0.0, 0.0, 0.0, 0.0)
        fills = (_num(1100, 4100, 280, red) + _num(2800, 4300, 550, red)        # 위 벌(흰 옷) 앞·뒤
                 + _num(1100, 1650, 280, white) + _num(2800, 1850, 550, white)  # 아래 벌(자주 옷)
                 + [_glyph(900, 3700, 300, 360, red), _glyph(1250, 3750, 200, 270, red),   # 무늬·워드마크 덩어리
                    _glyph(3300, 3000, 500, 700, red), _glyph(2500, 2600, 120, 400, white)])
        got = _find_number_pair(fills, 2239.0)
        self.assertIsNotNone(got)
        self.assertEqual(got["front"]["bbox"][1], 4100)
        self.assertEqual(got["back"]["bbox"][1], 4300)
        self.assertAlmostEqual(got["back"]["bbox"][3] - got["back"]["bbox"][1], 550, places=1)
        self.assertEqual(len(got["sides"]), 1)
        self.assertEqual(got["sides"][0]["back_color"], list(white))
        self.assertAlmostEqual(got["sides"][0]["dy"], -2450, places=0)

    def test_noise_only_gives_none(self):
        from engine.reference import _find_number_pair
        red = (0.0, 0.8, 0.4, 0.4)
        fills = [_glyph(900, 3700, 300, 360, red), _glyph(3300, 3000, 500, 700, red)]
        self.assertIsNone(_find_number_pair(fills, 2239.0))

    def test_outlined_number(self):
        from engine.reference import _find_number_pair
        dark, red = (0.0, 0.38, 0.0, 1.0), (0.0, 0.8, 0.4, 0.4)
        fills = []
        for x0, y0, h in ((1100, 4100, 280), (2800, 4300, 550)):
            ow = h * 0.01
            for g in _num(x0, y0, h, dark):
                b = g["bbox"]
                fills.append(g)
                fills.append(_glyph(b[0] + ow, b[1] + ow, (b[2] - b[0]) - 2 * ow, (b[3] - b[1]) - 2 * ow, red))
        got = _find_number_pair(fills, 2239.0)
        self.assertEqual(tuple(got["back"]["color"]), red)
        self.assertEqual(got["back"]["outline"]["color_cmyk"], list(dark))
        self.assertAlmostEqual(got["back"]["outline"]["width_pt"], 5.5, places=0)

    def test_place_number_outline_ops(self):
        from engine.text import place_number
        font = os.path.join(ROOT, "data", "fonts", "HY헤드라인M.ttf")
        plain, _ = place_number("23", font, 300, 500, 500, (0, 0.8, 0.4, 0.4))
        lined, _ = place_number("23", font, 300, 500, 500, (0, 0.8, 0.4, 0.4),
                                outline={"color_cmyk": [0, 0, 0, 1], "width_pt": 4})
        self.assertNotIn(" K ", plain)
        self.assertIn(" K 8 w 1 j", lined)
        self.assertIn("\nS\n", lined)


def _pdf(path, content, xobjects=None, gstates=None):
    import pikepdf
    pdf = pikepdf.new()
    res = pikepdf.Dictionary()
    if xobjects:
        xd = pikepdf.Dictionary()
        for nm, (bbox, ops) in xobjects.items():
            xo = pikepdf.Stream(pdf, ops.encode())
            xo.Type = pikepdf.Name("/XObject"); xo.Subtype = pikepdf.Name("/Form")
            xo.BBox = pikepdf.Array(bbox)
            xd[pikepdf.Name("/" + nm)] = xo
        res.XObject = xd
    if gstates:
        gd = pikepdf.Dictionary()
        for nm, a in gstates.items():
            gd[pikepdf.Name("/" + nm)] = pikepdf.Dictionary(Type=pikepdf.Name("/ExtGState"), ca=a, CA=a)
        res.ExtGState = gd
    page = pikepdf.Dictionary(Type=pikepdf.Name("/Page"), MediaBox=pikepdf.Array([0, 0, 1000, 1000]),
                              Resources=res, Contents=pikepdf.Stream(pdf, content.encode()))
    pdf.pages.append(pikepdf.Page(page))
    pdf.save(path)


class FlattenBackdrop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="flat_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_each_element_mixes_with_its_own_backdrop(self):
        import pikepdf
        from pikepdf import parse_content_stream
        from engine.flatten import flatten_transparency
        src = os.path.join(self.tmp, "d.pdf")
        # 아래 반 = 갈색 면, 위 반 = 종이. 그 위에 각각 반투명(30%) 검정 무늬 하나씩.
        content = ("0 0.5 0.5 0.8 k 0 0 1000 500 re f\n"
                   "q /G0 gs /Top Do Q\nq /G0 gs /Bot Do Q\n")
        _pdf(src, content,
             xobjects={"Top": ([100, 600, 900, 900], "0 0 0 1 k 100 600 800 300 re f"),
                       "Bot": ([100, 100, 900, 400], "0 0 0 1 k 100 100 800 300 re f")},
             gstates={"G0": 0.3})
        out = os.path.join(self.tmp, "o.pdf")
        info = flatten_transparency(src, out)
        with pikepdf.open(out) as p:
            xo = p.pages[0].Resources.XObject
            col = {}
            for nm in ("Top", "Bot"):
                for ops, op in parse_content_stream(xo["/" + nm]):
                    if str(op) == "k":
                        col[nm] = tuple(round(float(v), 3) for v in ops)
        self.assertEqual(col["Top"], (0.0, 0.0, 0.0, 0.3))                  # 종이(흰색)와 섞임
        self.assertEqual(col["Bot"], (0.0, 0.35, 0.35, 0.86))               # 갈색과 섞임
        self.assertTrue(any("바로 밑 색" in w for w in info["warnings"]))

    def test_thin_ring_is_not_background(self):
        import pikepdf
        from engine.flatten import detect_background_cmyk
        src = os.path.join(self.tmp, "r.pdf")
        # 큰 회색 «테»(바깥 990 − 안 980, 짝홀 채움) + 그 안의 흰 본판 800×800
        content = ("0 0 0 0.5 k 5 5 990 990 re 10 10 980 980 re f*\n"
                   "0 0 0 0 k 100 100 800 800 re f\n")
        _pdf(src, content)
        with pikepdf.open(src) as p:
            self.assertEqual(detect_background_cmyk(p, 0), (0.0, 0.0, 0.0, 0.0))


class KidsSizesAndNames(unittest.TestCase):
    def test_hosu_sizes(self):
        from webapp.api import _parse_size_from_filename, _SIZE_ORDER, _SIZE_TOKENS
        self.assertEqual(_parse_size_from_filename("유소년 V넥 14호.ai"), "14호")
        self.assertLess(_SIZE_ORDER.index("14호"), _SIZE_ORDER.index("5XS"))
        self.assertLess(_SIZE_TOKENS.index("12호"), _SIZE_TOKENS.index("14호"))

    def test_piece_names_follow_shape(self):
        from webapp.api import _set_piece_fit
        tmp = tempfile.mkdtemp(prefix="names_")
        try:
            svg = os.path.join(tmp, "L.svg")
            # 소매가 먼저 나오는 마스터: 소매(500×400) · 몸판(700×1000) · 몸판 · 띠(60×700)
            polys = [(0, 0, 500, 400), (600, 0, 700, 1000), (1400, 0, 700, 1000), (2200, 0, 60, 700)]
            with open(svg, "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3000 1200">' + "".join(
                    f'<polyline points="{x} {y} {x + w} {y} {x + w} {y + h} {x} {y + h} {x} {y}"/>' for x, y, w, h in polys)
                    + "</svg>")
            pieces = [{"id": i, "name": n, "svg_index": k} for k, (i, n) in
                      enumerate((("front", "앞판"), ("back", "뒤판"), ("band", "넥밴드"), ("piece_3", "조각3")))]
            _set_piece_fit(pieces, svg, [], use_kind=False)
            from engine.pattern import parse_svg
            ps = parse_svg(svg)                        # 읽는 순서가 파일 순서와 다를 수 있다 → 모양으로 찾는다
            kind = {}
            for k, p in enumerate(ps):
                w, h = p.width, p.height
                kind[k] = "band" if max(w, h) / min(w, h) >= 4 else ("body" if w * h > 500000 else "sleeve")
            names = {p["svg_index"]: p["name"] for p in pieces}
            self.assertEqual(sorted(names[k] for k in kind if kind[k] == "body"), ["뒤판", "앞판"])
            self.assertEqual([names[k] for k in kind if kind[k] == "band"], ["넥밴드"])
            self.assertEqual([names[k] for k in kind if kind[k] == "sleeve"], ["소매1"])
            self.assertEqual([p["id"] for p in pieces], ["front", "back", "band", "piece_3"])   # id 는 그대로
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class MasterChainAndKidsSleeve(unittest.TestCase):
    """(2026-10-21 김현서 답 16·20번) 반쪽 열린 선으로 그린 마스터 조각 · 한 장뿐인 유소년 소매."""

    def test_chain_open_halves(self):
        from engine.svg_normalize import _chain_open_paths, _bbox
        import math
        # 둥근 윗변 조각을 «왼쪽 반 + 오른쪽 반» 열린 선 둘로
        top = [(500 + 300 * math.cos(math.pi * k / 20), 1000 + 200 * math.sin(math.pi * k / 20)) for k in range(21)]
        left = [(800, 0), (800, 1000)] + top[:11]                  # (800,0)→오른쪽 위→꼭대기
        right = top[10:] + [(200, 1000), (200, 0), (800, 0)]       # 꼭대기→왼쪽→아래→처음
        box = [[(0, 0), (300, 0)], [(300, 0), (300, 300)], [(300, 300), (0, 300)], [(0, 300), (0, 0)]]   # 라벨 칸
        cands = [(left, _bbox(left), False), (right, _bbox(right), False)] + [(b, _bbox(b), False) for b in box]
        got, n = _chain_open_paths(cands)
        self.assertEqual(n, 1)
        closed = [c for c in got if c[2]]
        self.assertEqual(len(closed), 1)
        self.assertEqual([round(v) for v in closed[0][1]], [200, 0, 800, 1200])

    def test_inner_seam_loop_dropped(self):
        from engine.svg_normalize import _chain_open_paths, _bbox
        outer = [(0, 0), (200, 0), (400, 0), (400, 400), (400, 800), (200, 820), (0, 800), (0, 400)]   # 조각 바깥선(점 여럿)
        a = [(20, 20), (380, 20), (380, 400), (370, 500), (360, 600), (350, 780)]
        b = [(350, 780), (20, 780), (20, 20)]
        cands = [(outer, _bbox(outer), True), (a, _bbox(a), False), (b, _bbox(b), False)]
        got, n = _chain_open_paths(cands)
        self.assertEqual(n, 0)                                     # 바깥선 안의 봉제선 고리는 조각이 아니다

    def test_single_sleeve_duplicated_mirrored(self):
        import json
        from engine.job import _build_precise_layout
        tmp = tempfile.mkdtemp(prefix="kids_")
        try:
            body = [(100, 100), (700, 100), (700, 900), (100, 900)]
            sleeve = [(900, 100), (1300, 100), (1250, 500), (900, 600)]   # 비대칭(거울이면 모양이 다르다)
            with open(os.path.join(tmp, "14호.svg"), "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1500 1000">' + "".join(
                    '<polyline points="' + " ".join(f"{x} {1000 - y}" for x, y in pts + pts[:1]) + '"/>' for pts in (body, sleeve))
                    + "</svg>")
            preset = {"_dir": tmp, "design": {"page_size_pt": [3000, 1500]},
                      "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [0, 0, 600, 800], "fit": "top_height"},
                                 {"id": "piece_1", "svg_index": 1, "design_region_pt": [1000, 0, 1400, 500]},
                                 {"id": "piece_1_2", "svg_index": 1, "design_region_pt": [1500, 0, 1900, 500],
                                  "dup_of": "piece_1", "outline_mirror": True}]}
            lay = _build_precise_layout(preset, {"name": "14호", "pattern_file": "14호.svg"}, warnings=[])
            self.assertEqual(len(lay.pieces), 3)
            s1, s2 = lay.pieces[1].outline, lay.pieces[2].outline
            self.assertGreater(min(x for x, _ in s2), max(x for x, _ in s1))      # 시트 오른쪽 옆에 따로
            w1 = max(x for x, _ in s1) - min(x for x, _ in s1)
            w2 = max(x for x, _ in s2) - min(x for x, _ in s2)
            self.assertAlmostEqual(w1, w2, places=3)
            # 뒤집힌 모양: 원래 조각의 «가장 높은 점» 이 왼쪽이면 복제본은 오른쪽
            lo1 = max(s1, key=lambda p: p[1])[0] - min(x for x, _ in s1)
            lo2 = max(s2, key=lambda p: p[1])[0] - min(x for x, _ in s2)
            self.assertAlmostEqual(lo1 + lo2, w1, places=3)
            self.assertGreaterEqual(lay.page_size[0], max(x for x, _ in s2))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
