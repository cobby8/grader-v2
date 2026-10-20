# 조각별 «디자이너 방식» 맞춤 시험(2026-10-20) — 몸판: 높이 비율 + 위·가운데 / 띠: 늘이기 / 그 밖·예전 프리셋: 예전 그대로
#   실행: python -m unittest tests.test_fit_modes -v   (저장소 루트)
#   배경: 실주문 5건을 디자이너 사이즈별 결과와 견주니, 디자이너는 몸판을 높이 비율로 키우고 목선(위·가운데)에 맞췄다.
#        그레이더는 좁은 쪽 비율 + 왼아래라 작은 사이즈일수록 그림이 내려갔다(최대 29mm).
import os, sys, json, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class FitMatrix(unittest.TestCase):
    def _apply(self, m, x, y):
        a, b, c, d, e, f = m
        return a * x + c * y + e, b * x + d * y + f

    def test_top_height(self):
        """높이 비율 등방 + 영역 위·가운데 → 조각 위·가운데"""
        from engine.pdfutil import fit_matrix
        m = fit_matrix((0, 0, 100, 200), (1000, 500, 1090, 680), "top_height")
        self.assertAlmostEqual(m[0], 0.9); self.assertAlmostEqual(m[3], 0.9)     # 180/200
        tx, ty = self._apply(m, 50, 200)                                          # 영역 위·가운데
        self.assertAlmostEqual(tx, 1045); self.assertAlmostEqual(ty, 680)
        bx, by = self._apply(m, 50, 0)                                            # 아래 끝은 조각 아래 끝
        self.assertAlmostEqual(by, 500)

    def test_stretch(self):
        """띠: 가로·세로를 따로 맞춘다(왼아래 → 왼아래, 오른위 → 오른위)"""
        from engine.pdfutil import fit_matrix
        m = fit_matrix((0, 0, 600, 60), (10, 20, 550, 82), "stretch")
        self.assertEqual(self._apply(m, 0, 0), (10, 20))
        x, y = self._apply(m, 600, 60)
        self.assertAlmostEqual(x, 550); self.assertAlmostEqual(y, 82)

    def test_unknown_fit_rejected(self):
        from engine.pdfutil import fit_matrix
        with self.assertRaises(ValueError):
            fit_matrix((0, 0, 1, 1), (0, 0, 1, 1), "cover")


class BuildLayouts(unittest.TestCase):
    """build_layouts: fit 이 있는 조각만 새 방식, 없는 조각은 예전 방식(좁은 쪽 비율 + 왼아래) 그대로"""

    def test_fit_only_where_set(self):
        import fitz
        from engine.grade import load_preset, build_layouts, _piece_transform
        from engine.pattern import parse_svg
        tmp = tempfile.mkdtemp(prefix="fit_")
        try:
            with open(os.path.join(tmp, "M.svg"), "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 1200">'
                        '<polyline points="100 100 700 100 700 1000 100 1000 100 100"/>'
                        '<polyline points="900 100 1500 100 1500 160 900 160 900 100"/></svg>')
            pr = {"preset_name": "t", "version": 1, "design": {"base_size": "M", "page_size_pt": [2000, 1200]},
                  "sizes": [{"name": "M", "pattern_file": "M.svg", "scale": 1.0}],
                  "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [0, 0, 640, 1000], "fit": "top_height"},
                             {"id": "band", "svg_index": 1, "design_region_pt": [0, 0, 640, 60]}],
                  "design_mapping": {"mode": "anchor"}, "shrink": {"x": 1.0, "y": 1.0}}
            with open(os.path.join(tmp, "preset.json"), "w", encoding="utf-8") as f:
                json.dump(pr, f)
            doc = fitz.open(); doc.new_page(width=2000, height=1200); doc.save(os.path.join(tmp, "d.pdf"))
            p = load_preset(os.path.join(tmp, "preset.json"))
            lay = build_layouts(p, os.path.join(tmp, "d.pdf"))[0]
            polys = parse_svg(os.path.join(tmp, "M.svg"))
            s = lay.pieces[0].transform[0]
            self.assertAlmostEqual(s, 900 / 1000)                                  # 높이 비율(폭 비율 600/640 이 아님)
            self.assertEqual(lay.pieces[1].transform, _piece_transform([0, 0, 640, 60], polys[1], 1.0, 1.0),
                             "fit 없는 조각은 예전 방식 그대로")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RegisterFit(unittest.TestCase):
    """등록: 몸판 top_height · 띠 stretch · 소매(가로로 길고 작은 조각)는 적지 않음"""

    def test_roles(self):
        from webapp.api import _set_piece_fit
        tmp = tempfile.mkdtemp(prefix="fitreg_")
        try:
            p = os.path.join(tmp, "XL.svg")
            with open(p, "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3000 3000">'
                        '<polyline points="0 0 600 0 600 850 0 850"/>'           # 몸판(세로가 김)
                        '<polyline points="700 0 1300 0 1300 820 700 820"/>'     # 몸판
                        '<polyline points="0 1000 640 1000 640 1310 0 1310"/>'   # 소매(가로가 길고 작음)
                        '<polyline points="0 1500 600 1500 600 1560 0 1560"/>'   # 띠(10:1)
                        '</svg>')
            from engine.pattern import parse_svg
            order = parse_svg(p)                                                  # svg_index = 높이순
            pieces = [{"id": f"p{i}", "svg_index": i} for i in range(len(order))]
            w = []
            _set_piece_fit(pieces, p, w)
            got = {(round(order[pc["svg_index"]].width), round(order[pc["svg_index"]].height)): pc.get("fit") for pc in pieces}
            self.assertEqual(got[(600, 850)], "top_height")
            self.assertEqual(got[(600, 820)], "top_height")
            self.assertIsNone(got[(640, 310)], "소매는 예전 방식")
            self.assertEqual(got[(600, 60)], "stretch")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RegisterFitMore(unittest.TestCase):
    def _svg(self, tmp, polys):
        p = os.path.join(tmp, "XL.svg")
        with open(p, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4000 4000">'
                    + "".join('<polyline points="' + " ".join(f"{x} {y}" for x, y in P) + '"/>' for P in polys) + "</svg>")
        return p

    def test_long_sleeve_keeps_old_way(self):
        """긴팔 소매(세로가 길어도 몸판 넓이의 75%)는 예전 방식 — 몸판으로 판정하지 않는다(리뷰 지적)"""
        from webapp.api import _set_piece_fit
        from engine.pattern import parse_svg
        tmp = tempfile.mkdtemp(prefix="fitreg2_")
        try:
            p = self._svg(tmp, [[(0, 0), (640, 0), (640, 805), (0, 805)], [(700, 0), (1166, 0), (1166, 826), (700, 826)]])
            order = parse_svg(p)
            pieces = [{"id": f"p{i}", "svg_index": i} for i in range(len(order))]
            _set_piece_fit(pieces, p, [])
            by = {round(order[pc["svg_index"]].width): pc.get("fit") for pc in pieces}
            self.assertEqual(by[640], "top_height")
            self.assertIsNone(by[466])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_notch_kinds_first(self):
        """노치 등록: 조각 이름(종류)을 먼저 본다 — 소매는 커도 예전 방식, 목 띠는 늘이기"""
        from webapp.api import _set_piece_fit
        tmp = tempfile.mkdtemp(prefix="fitreg3_")
        try:
            p = self._svg(tmp, [[(0, 0), (640, 0), (640, 805), (0, 805)], [(700, 0), (1300, 0), (1300, 800), (700, 800)],
                                [(0, 900), (500, 900), (500, 960), (0, 960)]])
            pieces = [{"id": "sleeve", "svg_index": 0}, {"id": "back", "svg_index": 1}, {"id": "neck", "svg_index": 2}]
            _set_piece_fit(pieces, p, [], use_kind=True)
            self.assertEqual([pc.get("fit") for pc in pieces], [None, "top_height", "stretch"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_wide_logo_band_not_stretched(self):
        """긴 조각이라도 높이가 150mm 넘으면(옆판·허리판 등) 늘이지 않는다 — 로고가 찌그러진다"""
        from webapp.api import _set_piece_fit
        tmp = tempfile.mkdtemp(prefix="fitreg4_")
        try:
            h = 200 / (25.4 / 72)
            p = self._svg(tmp, [[(0, 0), (3000, 0), (3000, 2400), (0, 2400)], [(0, 2500), (3400, 2500), (3400, 2500 + h), (0, 2500 + h)]])
            pieces = [{"id": "a", "svg_index": 0}, {"id": "b", "svg_index": 1}]
            _set_piece_fit(pieces, p, [])
            self.assertNotEqual(pieces[1].get("fit"), "stretch")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Guards(unittest.TestCase):
    def test_bad_fit_rejected_at_load(self):
        from engine.grade import load_preset
        tmp = tempfile.mkdtemp(prefix="fitbad_")
        try:
            pr = {"preset_name": "t", "sizes": [{"name": "M", "pattern_file": "M.svg"}], "design_mapping": {},
                  "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [0, 0, 1, 1], "fit": "contain"}]}
            with open(os.path.join(tmp, "preset.json"), "w", encoding="utf-8") as f:
                json.dump(pr, f)
            with self.assertRaises(ValueError):
                load_preset(os.path.join(tmp, "preset.json"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ops_bbox(self):
        from engine.job import _ops_bbox
        ops = " ".join(["q", "0 0 0 1 k", "10 20 m", "30 20 l", "30 40 35 45 40 50 c", "h f", "Q"])
        self.assertEqual(_ops_bbox(ops, (2, 0, 0, 2, 100, 0)), (120, 40, 180, 100))


if __name__ == "__main__":
    unittest.main()
