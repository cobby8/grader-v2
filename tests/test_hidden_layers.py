# 숨김 레이어 시험(2026-10-20) — 디자이너가 꺼 둔 레이어는 출력에 안 찍힌다 · 켜진 레이어는 그대로 · 끄는 설정
#   실행: python -m unittest tests.test_hidden_layers -v   (저장소 루트)
#   배경: compose 가 디자인을 Form 으로 옮기며 레이어 켜짐/꺼짐을 버려, 꺼 둔 «레이어 2»(택 아래 초록 상자)가 찍혔다.
import os, sys, json, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _design(path):
    """흰 바탕에 켜진 레이어(파랑 상자 왼쪽) + 꺼진 레이어(초록 상자 오른쪽)."""
    import fitz, pikepdf
    d = fitz.open()
    on = d.add_ocg("보임", on=True)
    off = d.add_ocg("레이어 2", on=False)
    pg = d.new_page(width=1000, height=1400)
    pg.draw_rect(pg.rect, color=None, fill=(1, 1, 1))
    pg.draw_rect(fitz.Rect(100, 100, 400, 400), color=None, fill=(0, 0, 1), oc=on)
    pg.draw_rect(fitz.Rect(600, 100, 900, 400), color=None, fill=(0, 1, 0), oc=off)
    tmp = path + ".tmp.pdf"
    d.save(tmp)
    with pikepdf.open(tmp) as pdf:
        pdf.pages[0].contents_coalesce()
        pdf.save(path)
    os.remove(tmp)


def _pixel(pdf, x, y_design_top):
    """디자인(위 원점, 높이 1400) 좌표의 점 → 출력 페이지 픽셀. 출력 페이지는 «조각 끝 + 50pt» 라 높이가 다르다."""
    import fitz
    pg = fitz.open(pdf)[0]
    y = pg.rect.height - (1400 - y_design_top)
    pix = pg.get_pixmap(dpi=18, alpha=False)
    s = 18 / 72
    return pix.pixel(int(x * s), int(y * s))


class HiddenLayers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hidden_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hide_off_layers(self):
        from engine.job import hide_off_layers
        src = os.path.join(self.tmp, "d.pdf"); _design(src)
        out = os.path.join(self.tmp, "o.pdf")
        info = hide_off_layers(src, src, out)
        self.assertTrue(info["found"])
        self.assertEqual(info["removed_layers"], ["레이어 2"])

    def _job(self, remove=True):
        import pikepdf
        from engine.job import run_job
        d = os.path.join(self.tmp, f"p{int(remove)}"); os.makedirs(d)
        design = os.path.join(d, "design.pdf"); _design(design)
        with open(os.path.join(d, "M.svg"), "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1400"><polyline points="0 0 1000 0 1000 1400 0 1400 0 0"/></svg>')
        pr = {"preset_name": "t", "version": 1, "design": {"base_size": "M", "page_size_pt": [1000, 1400]},
              "sizes": [{"name": "M", "pattern_file": "M.svg"}],
              "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [0, 0, 1000, 1400]}],
              "design_mapping": {"mode": "anchor"}, "shrink": {"x": 1.0, "y": 1.0}, "output": {"format": "pdf"}}
        if not remove:
            pr["hidden_layers"] = {"remove": False}
        with open(os.path.join(d, "preset.json"), "w", encoding="utf-8") as f:
            json.dump(pr, f)
        res = run_job(os.path.join(d, "preset.json"), design, [{"size": "M", "name": "", "number": "", "qty": 1}],
                      os.path.join(d, "job"), make_preview=False, out_format="pdf")
        self.assertEqual(res["summary"]["verify_pass"], 1, res["summary"])
        o = res["outputs"][0]
        return o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(d, "job", o["pdf"])

    def test_output_hides_off_layer_keeps_on_layer(self):
        """출력: 꺼 둔 초록 상자는 없고, 켜진 파랑 상자는 그대로"""
        p = self._job(True)
        blue = _pixel(p, 250, 250)
        green = _pixel(p, 750, 250)
        self.assertLess(blue[0], 80, f"켜진 레이어(파랑)가 사라짐 {blue}")
        self.assertGreater(green[0], 200, f"꺼 둔 레이어(초록)가 찍힘 {green}")

    def test_can_turn_off(self):
        """preset.hidden_layers.remove=false 면 예전처럼 둔다"""
        p = self._job(False)
        green = _pixel(p, 750, 250)
        self.assertLess(green[0], 120, f"설정을 껐는데 초록이 빠짐 {green}")


if __name__ == "__main__":
    unittest.main()
