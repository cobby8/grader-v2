# 재단선 기본 시험(2026-10-20) — 새 등록 패턴은 조각 윤곽 빨간 재단선을 그린다(노치 없이도)
#   실행: python -m unittest tests.test_cutline_default -v   (저장소 루트)
#   배경: 화면으로 등록한 패턴엔 cutline 설정이 없어, 디자인에 «패턴선» 레이어가 없으면 재단선이 안 그려졌다.
import os, sys, json, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _red_paths(pdf):
    import fitz
    n = 0
    for d in fitz.open(pdf)[0].get_drawings():
        c = d.get("color")
        if c and ((len(c) == 4 and c[1] > 0.9 and c[2] > 0.9) or (len(c) == 3 and c[0] > 0.8 and c[1] < 0.3 and c[2] < 0.3)):
            n += 1
    return n


class CutlineDefault(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cutline_")
        from webapp import state
        self.old = (state.PATTERNS_DIR, state.UPLOADS_DIR)
        state.PATTERNS_DIR = os.path.join(self.tmp, "patterns")
        state.UPLOADS_DIR = os.path.join(self.tmp, "uploads")

    def tearDown(self):
        from webapp import state
        state.PATTERNS_DIR, state.UPLOADS_DIR = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_register_then_job_draws_cutline(self):
        import fitz
        from fastapi.testclient import TestClient
        from webapp.main import app
        from engine.job import run_job
        src = os.path.join(self.tmp, "src"); os.makedirs(src)
        files = []
        for sz, s in (("M", 0.96), ("L", 1.0)):
            p = os.path.join(src, f"{sz}.svg")
            with open(p, "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 1600">'
                        f'<polyline points="100 100 {100 + 700 * s} 100 {100 + 700 * s} {100 + 1000 * s} 100 {100 + 1000 * s} 100 100"/>'
                        f'<polyline points="900 100 {900 + 680 * s} 100 {900 + 680 * s} {100 + 980 * s} 900 {100 + 980 * s} 900 100"/></svg>')
            files.append((sz, p))
        fh = [("files", (f"{sz}.svg", open(p, "rb"))) for sz, p in files]
        try:
            r = TestClient(app).post("/api/patterns", data={"name": "재단선시험", "base_size": "L"}, files=fh)
        finally:
            for _, (_, f) in fh:
                f.close()
        self.assertEqual(r.status_code, 200, r.text[:400])
        pdir = os.path.join(self.tmp, "patterns", "재단선시험")
        with open(os.path.join(pdir, "preset.json"), encoding="utf-8") as f:
            pr = json.load(f)
        self.assertEqual((pr.get("cutline") or {}).get("draw_from"), "svg_polygon")
        self.assertEqual(pr["cutline"].get("hide_design_cutline_layer"), "if_present")
        self.assertNotIn("notches", pr)
        d = fitz.open(); pg = d.new_page(width=pr["design"]["page_size_pt"][0], height=pr["design"]["page_size_pt"][1])
        pg.draw_rect(pg.rect, color=None, fill=(0.2, 0.1, 0, 0)); pg.clean_contents()
        design = os.path.join(self.tmp, "design.pdf"); d.save(design)
        res = run_job(os.path.join(pdir, "preset.json"), design, [{"size": "M", "name": "", "number": "", "qty": 1}],
                      os.path.join(self.tmp, "job"), make_preview=False, out_format="pdf")
        self.assertTrue(res["summary"]["precise_placement"])
        o = res["outputs"][0]
        out = o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(self.tmp, "job", o["pdf"])
        self.assertEqual(_red_paths(out), 2, "조각 2개 = 빨간 재단선 2줄")


if __name__ == "__main__":
    unittest.main()
