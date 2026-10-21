# 양면 두 면·상의+하의 함께 찍기 시험(2026-10-20)
#   실행: python -m unittest tests.test_sides_companion -v   (저장소 루트)
#   배경: 양면 디자인은 한 면씩 두 번 돌려야 했고, 같은 대지의 하의는 상의 프리셋에 없어 따로 돌려야 했다.
import os, sys, json, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.test_region_match import _svg, _design, _shift   # noqa: E402

BODY = [(0, 0), (500, 0), (500, 700), (0, 700)]
BACK = [(0, 0), (480, 0), (480, 650), (240, 690), (0, 650)]
LEG = [(0, 0), (420, 0), (440, 380), (220, 420), (0, 380)]


def _clips(pdf):
    import fitz
    seen = set()   # 조각 하나가 클립을 두 단(본체색 채움·디자인)으로 쓰므로 같은 자리는 한 번만 센다
    for x in fitz.open(pdf)[0].get_drawings(extended=True):
        if x.get("type") == "clip" and (x.get("level") or 0) <= 1 and x["scissor"].width > 300:
            r = x["scissor"]
            seen.add((round(r.x0), round(r.y0), round(r.x1), round(r.y1)))
    return len(seen)


def _preset(d, name, polys, extra=None):
    pdir = os.path.join(d, "patterns", name); os.makedirs(pdir)
    for sz in ("M", "L"):
        _svg(os.path.join(pdir, f"{sz}.svg"), polys)
    pr = {"preset_name": name, "version": 1, "design": {"base_size": "L", "page_size_pt": [2000, 1600], "auto_regions": True},
          "sizes": [{"name": "M", "pattern_file": "M.svg"}, {"name": "L", "pattern_file": "L.svg"}],
          "pieces": [{"id": f"p{i}", "svg_index": i, "design_region_pt": [0, 0, 2000, 1600]} for i in range(len(polys))],
          "design_mapping": {"mode": "anchor"}, "shrink": {"x": 1.0, "y": 1.0}, "output": {"format": "pdf"},
          "cutline": {"draw_from": "svg_polygon", "color_cmyk": [0, 0.96, 0.95, 0], "stroke_width": 2.0}}
    pr.update(extra or {})
    with open(os.path.join(pdir, "preset.json"), "w", encoding="utf-8") as f:
        json.dump(pr, f)
    return os.path.join(pdir, "preset.json")


class SidesCompanion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sides_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, preset, design, rows):
        from engine.job import run_job
        res = run_job(preset, design, rows, os.path.join(self.tmp, "job"), make_preview=False, out_format="pdf")
        o = res["outputs"][0]
        return res, (o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(self.tmp, "job", o["pdf"]))

    def test_stack_layouts(self):
        """쌓기: 각 면을 원점 근처로 옮긴 뒤 위→아래로 — 위 레이아웃이 위쪽, 큰 대지 좌표여도 페이지가 작다"""
        from engine.compose import Piece, SizeLayout
        from engine.job import _stack_layouts
        far = 9000.0   # 축구 마스터처럼 원점에서 먼 조각
        a = SizeLayout("a", (far + 200, far + 200), [Piece(outline=[(far, far), (far + 100, far), (far + 100, far + 80)],
                                                           transform=(1, 0, 0, 1, 0, 0), extra_ops="0 0 m")])
        b = SizeLayout("b", (far + 200, far + 200), [Piece(outline=[(far, far), (far + 120, far), (far + 120, far + 60)],
                                                           transform=(1, 0, 0, 1, 0, 0))])
        st = _stack_layouts("x", [a, b], gap=40, margin=50)
        self.assertEqual(st.page_size, (220.0, (60 + 100) + 40 + (80 + 100)))
        pa, pb = st.pieces[1], st.pieces[0]                       # 아래(b)부터 쌓인다
        self.assertEqual(pb.outline[0], (50.0, 50.0))
        self.assertGreater(min(y for _, y in pa.outline), max(y for _, y in pb.outline) + 40)
        self.assertEqual(pa.transform[4], 50.0 - far)
        self.assertIn("cm", pa.extra_ops)

    def test_two_sides_one_sheet(self):
        """디자인에 같은 조각 두 벌(위·아래) → 한 장에 두 면(조각 4개), 검증 통과"""
        polys = [_shift(BODY, 100, 100), _shift(BACK, 700, 100)]
        preset = _preset(self.tmp, "top", polys)
        design = os.path.join(self.tmp, "d.pdf")
        _design(design, [_shift(BODY, 100, 850), _shift(BACK, 700, 850), _shift(BODY, 100, 50), _shift(BACK, 700, 50)],
                fills=[(1, 1, 1), (1, 1, 1), (0.4, 0, 0.1), (0.4, 0, 0.1)])
        res, pdf = self._run(preset, design, [{"size": "M", "name": "", "number": "", "qty": 1}])
        self.assertEqual(res["summary"]["verify_pass"], 1, res["summary"])
        self.assertTrue(any(w.startswith("[양면]") for w in res["summary"]["warnings"]))
        self.assertEqual(_clips(pdf), 4)

    def test_reversible_off(self):
        """preset.reversible=false 면 한 면만"""
        polys = [_shift(BODY, 100, 100), _shift(BACK, 700, 100)]
        preset = _preset(self.tmp, "top", polys, {"reversible": False})
        design = os.path.join(self.tmp, "d.pdf")
        _design(design, [_shift(BODY, 100, 850), _shift(BACK, 700, 850), _shift(BODY, 100, 50), _shift(BACK, 700, 50)])
        res, pdf = self._run(preset, design, [{"size": "M", "name": "", "number": "", "qty": 1}])
        self.assertEqual(_clips(pdf), 2)

    def test_companion_bottom(self):
        """상의 프리셋의 companion(하의) → 같은 디자인의 하의 조각을 같은 장 아래에, 하의 사이즈는 bottom_size"""
        top = _preset(self.tmp, "top", [_shift(BODY, 100, 100), _shift(BACK, 700, 100)], {"companion": {"pattern": "pants"}})
        _preset(self.tmp, "pants", [_shift(LEG, 100, 100)])
        design = os.path.join(self.tmp, "d.pdf")
        _design(design, [_shift(BODY, 100, 850), _shift(BACK, 700, 850), _shift(LEG, 1400, 100)])
        res, pdf = self._run(top, design, [{"size": "M", "name": "", "number": "", "qty": 1, "bottom_size": "L"}])
        self.assertEqual(res["summary"]["verify_pass"], 1, res["summary"])
        self.assertTrue(any(w.startswith("[함께 찍기]") for w in res["summary"]["warnings"]), res["summary"]["warnings"])
        self.assertEqual(_clips(pdf), 3)

    def test_top_only_and_pants_only(self):
        """주문서 하의 칸 «-» = 상의만(조각 2) · 상의 칸 «-» + 하의 사이즈 = 하의만(조각 1)"""
        top = _preset(self.tmp, "top", [_shift(BODY, 100, 100), _shift(BACK, 700, 100)], {"companion": {"pattern": "pants"}})
        _preset(self.tmp, "pants", [_shift(LEG, 100, 100)])
        design = os.path.join(self.tmp, "d.pdf")
        _design(design, [_shift(BODY, 100, 850), _shift(BACK, 700, 850), _shift(LEG, 1400, 100)])
        from engine.job import run_job
        res = run_job(top, design, [{"size": "M", "name": "A", "number": "1", "qty": 1, "bottom_size": "-"},
                                    {"size": "-", "name": "B", "number": "2", "qty": 1, "bottom_size": "L"}],
                      os.path.join(self.tmp, "job"), make_preview=False, out_format="pdf")
        self.assertEqual(res["summary"]["verify_pass"], 2, res["summary"])
        outs = {o["name"]: (o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(self.tmp, "job", o["pdf"])) for o in res["outputs"]}
        self.assertEqual(_clips(outs["A"]), 2, "상의만")
        self.assertEqual(_clips(outs["B"]), 1, "하의만")

    def test_unmatched_piece_dropped(self):
        """디자인에 없는 조각(반팔 주문의 긴팔 소매 등)은 어림값으로 그리지 않고 뺀다"""
        polys = [_shift(BODY, 100, 100), _shift(BACK, 700, 100), _shift(LEG, 1300, 100)]
        preset = _preset(self.tmp, "top", polys)
        design = os.path.join(self.tmp, "d.pdf")
        _design(design, [_shift(BODY, 100, 850), _shift(BACK, 700, 850)])
        res, pdf = self._run(preset, design, [{"size": "M", "name": "", "number": "", "qty": 1}])
        self.assertEqual(_clips(pdf), 2)
        self.assertTrue(any("빼고 찍습니다" in w and w.startswith("🟡") for w in res["summary"]["warnings"]))

    def test_symmetric_pieces_two_sides_not_mixed(self):
        """좌우대칭 같은 모양 조각 2개 × 위·아래 2면 → 면 수 2(4로 부풀지 않음), 면마다 제 자리(리뷰 재현)"""
        from engine.region_match import match_regions
        from engine.pattern import parse_svg
        TRAP = [(0, 0), (400, 0), (340, 300), (60, 300)]
        _svg(os.path.join(self.tmp, "p.svg"), [_shift(TRAP, 100, 100), _shift(TRAP, 600, 100)])
        design = os.path.join(self.tmp, "d.pdf")
        _design(design, [_shift(TRAP, 100, 900), _shift(TRAP, 600, 900), _shift(TRAP, 100, 300), _shift(TRAP, 600, 300)])
        polys = parse_svg(os.path.join(self.tmp, "p.svg"))
        m = match_regions(design, polys)
        sides = m.pop("_sides", [])
        self.assertEqual(len(sides), 1, sides)                      # 두 번째 면 1개(= 2면)
        first = sorted(round(v["region_pt"][1]) for v in m.values())
        second = sorted(round(r[1]) for r in sides[0].values())
        self.assertEqual(first, [900, 900], "첫 면은 위 벌")
        self.assertEqual(second, [300, 300], "둘째 면은 아래 벌")
        self.assertEqual(len({v["region_pt"] for v in m.values()}), 2, "두 조각이 같은 윤곽을 받으면 안 된다")

    def test_order_bottom_size(self):
        """주문서 부제행 «하의» 열 → bottom_size"""
        import openpyxl
        from engine.order import parse_order
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["이니셜", "배번", "사이즈", "", "참고사항"])
        ws.append(["", "", "상의", "하의", ""])
        ws.append(["KIM", "7", "L", "XL", ""])
        ws.append(["LEE", "8", "M", "", ""])
        p = os.path.join(self.tmp, "o.xlsx"); wb.save(p)
        rows = parse_order(p)
        self.assertEqual(rows[0].get("bottom_size"), "XL", rows)
        self.assertNotIn("bottom_size", rows[1])


if __name__ == "__main__":
    unittest.main()
