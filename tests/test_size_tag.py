# 사이즈 택 바꾸기 시험(2026-10-20) — 기준 택 찾기 · 출력 사이즈 택 덮어 찍기 · 검증 통과 · 기준 사이즈는 그대로
#   실행: python -m unittest tests.test_size_tag -v   (저장소 루트)
#   배경: 최근 주문 5건 모두 L 출력에 «XL» 택이 찍혔다(그레이더는 기준 디자인을 키우고 줄이기만 했다).
import os, sys, json, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _design_with_tag(path, tag_pdf, at=(300, 400), k=1.0, bg=(0.0, 0.0, 0.0, 0.0)):
    """흰(또는 bg) 바탕 1000×1400pt 디자인에 라이브러리 택을 at(왼아래, PDF 좌표)·k배로 넣는다."""
    import fitz
    d = fitz.open()
    pg = d.new_page(width=1000, height=1400)
    pg.draw_rect(pg.rect, color=None, fill=bg)
    t = fitz.open(tag_pdf)
    w, h = t[0].rect.width * k, t[0].rect.height * k
    x0, y0 = at
    pg.show_pdf_page(fitz.Rect(x0, 1400 - y0 - h, x0 + w, 1400 - y0), t, 0)
    tmp = path + ".tmp.pdf"
    d.save(tmp)
    import pikepdf
    with pikepdf.open(tmp) as pdf:            # 실제 .ai 처럼 콘텐츠를 한 스트림으로(verify 가 한 스트림을 읽는다)
        pdf.pages[0].contents_coalesce()
        pdf.save(path)
    os.remove(tmp)
    return [x0, y0, x0 + w, y0 + h]


class SizeTag(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="size_tag_")
        from engine.size_tag import load_library
        self.lib = load_library()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_library_complete(self):
        """세 계열 모두 5XS~5XL 택이 있다(축구는 아동 호수까지)"""
        for fam in ("basketball", "pegasus", "soccer"):
            for sz in ("5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"):
                self.assertIn(sz, self.lib.get(fam, {}), f"{fam} {sz}")
                self.assertTrue(os.path.exists(self.lib[fam][sz]["path"]))
        self.assertIn("10호", self.lib["soccer"])

    def test_find_tag_on_white_and_dark(self):
        """흰 바탕·짙은 바탕(양면 자주 면) 모두에서 기준 택 자리를 1mm 안으로 찾는다"""
        from engine.size_tag import find_tags
        for bg in ((0, 0, 0, 0), (0.3, 1.0, 0.9, 0.6)):
            p = os.path.join(self.tmp, f"d{bg[0]}.pdf")
            want = _design_with_tag(p, self.lib["basketball"]["XL"]["path"], at=(310, 420), k=1.0, bg=bg)
            hits = find_tags(p, "XL", self.lib)
            self.assertTrue(hits, f"바탕 {bg} 에서 못 찾음")
            got = hits[0]["rect_pt"]
            self.assertEqual(hits[0]["family"], "basketball")
            for a, b in zip(got, want):
                self.assertLess(abs(a - b), 3.0, f"자리 {got} vs {want}")

    def test_no_tag_no_hit(self):
        """택이 없는 디자인에선 아무것도 찾지 않는다(엉뚱한 곳에 찍지 않음)"""
        import fitz
        from engine.size_tag import find_tags
        p = os.path.join(self.tmp, "blank.pdf")
        d = fitz.open(); pg = d.new_page(width=1000, height=1400)
        pg.draw_rect(fitz.Rect(100, 100, 600, 300), color=None, fill=(0, 0.9, 0.9, 0))
        pg.insert_text((120, 500), "SINCE 2009 STIZ", fontsize=40)
        d.save(p)
        self.assertEqual(find_tags(p, "XL", self.lib), [])

    def test_overlay_matrix(self):
        """찾은 자리에 다른 사이즈 택을 찍는 행렬 = 택 상자 왼아래 → 찾은 자리 왼아래, 폭 비율"""
        from engine.size_tag import overlay_for
        meta = self.lib["basketball"]["L"]
        bx0, by0, bx1, by1 = meta["box_pt"]
        hit = {"family": "basketball", "size": "XL", "rect_pt": [100, 200, 100 + (bx1 - bx0) * 1.1, 200 + (by1 - by0) * 1.1]}
        path, m = overlay_for(hit, "L", self.lib)
        self.assertTrue(path.endswith("L.pdf"))
        self.assertAlmostEqual(m[0], 1.1, places=6)
        self.assertAlmostEqual(m[0] * bx0 + m[4], 100, places=4)
        self.assertAlmostEqual(m[3] * by0 + m[5], 200, places=4)
        self.assertIsNone(overlay_for(hit, "9XL", self.lib))

    def test_run_job_swaps_tag(self):
        """run_job: L 출력엔 L 택이 덮이고(Do +1, 검증 통과), 기준 XL 출력은 예전과 같다"""
        import pikepdf
        from engine.job import run_job
        d = os.path.join(self.tmp, "p"); os.makedirs(d)
        design = os.path.join(d, "design.pdf")
        _design_with_tag(design, self.lib["basketball"]["XL"]["path"], at=(310, 420))
        for sz, s in (("L", 0.95), ("XL", 1.0)):
            w, h = 900 * s, 1300 * s
            with open(os.path.join(d, f"{sz}.svg"), "w", encoding="utf-8") as f:
                f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1400">'
                        f'<polyline points="50 50 {50 + w} 50 {50 + w} {50 + h} 50 {50 + h} 50 50"/></svg>')
        pr = {"preset_name": "t", "version": 1, "design": {"base_size": "XL", "page_size_pt": [1000, 1400]},
              "sizes": [{"name": "L", "pattern_file": "L.svg"}, {"name": "XL", "pattern_file": "XL.svg"}],
              "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [50, 50, 950, 1350], "fit": "top_height"}],
              "design_mapping": {"mode": "anchor"}, "shrink": {"x": 1.0, "y": 1.0}, "output": {"format": "pdf"}}
        with open(os.path.join(d, "preset.json"), "w", encoding="utf-8") as f:
            json.dump(pr, f)
        res = run_job(os.path.join(d, "preset.json"), design,
                      [{"size": "L", "name": "", "number": "", "qty": 1}, {"size": "XL", "name": "", "number": "", "qty": 1}],
                      os.path.join(d, "job"), make_preview=False, out_format="pdf")
        self.assertEqual(res["summary"]["verify_pass"], 2, res["summary"])
        self.assertTrue(any("[택]" in w for w in res["summary"]["warnings"]), res["summary"]["warnings"])
        dos = {}
        for o in res["outputs"]:
            p = o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(d, "job", o["pdf"])
            with pikepdf.open(p) as pdf:
                dos[o["size"]] = b"\n".join(pg.obj["/Contents"].read_bytes() for pg in pdf.pages).count(b" Do")
        self.assertEqual(dos["L"], 2, "L: 디자인 1 + L 택 1")
        self.assertEqual(dos["XL"], 1, "기준 XL: 디자인만(택은 이미 맞다)")

    def test_disabled_by_preset(self):
        """preset.size_tag.enabled=false 면 끈다"""
        import pikepdf
        from engine.job import run_job
        d = os.path.join(self.tmp, "q"); os.makedirs(d)
        design = os.path.join(d, "design.pdf")
        _design_with_tag(design, self.lib["basketball"]["XL"]["path"], at=(310, 420))
        with open(os.path.join(d, "L.svg"), "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1400"><polyline points="50 50 900 50 900 1290 50 1290 50 50"/></svg>')
        pr = {"preset_name": "t", "version": 1, "design": {"base_size": "XL", "page_size_pt": [1000, 1400]},
              "sizes": [{"name": "L", "pattern_file": "L.svg"}], "size_tag": {"enabled": False},
              "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [50, 50, 950, 1350]}],
              "design_mapping": {"mode": "anchor"}, "shrink": {"x": 1.0, "y": 1.0}, "output": {"format": "pdf"}}
        with open(os.path.join(d, "preset.json"), "w", encoding="utf-8") as f:
            json.dump(pr, f)
        res = run_job(os.path.join(d, "preset.json"), design, [{"size": "L", "name": "", "number": "", "qty": 1}],
                      os.path.join(d, "job"), make_preview=False, out_format="pdf")
        o = res["outputs"][0]
        p = o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(d, "job", o["pdf"])
        with pikepdf.open(p) as pdf:
            self.assertEqual(b"\n".join(pg.obj["/Contents"].read_bytes() for pg in pdf.pages).count(b" Do"), 1)


if __name__ == "__main__":
    unittest.main()
