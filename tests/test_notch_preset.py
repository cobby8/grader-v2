# 노치 프리셋 시험(2026-10-20) — 주문 PDF 재단선에 노치 · 노치 없는 프리셋은 그대로 · 공장용 재단 패턴 DXF
#   실행: python -m unittest tests.test_notch_preset -v   (저장소 루트)
#   ⚠️ 업로드·패턴 폴더는 state.UPLOADS_DIR·PATTERNS_DIR 을 임시로 바꾼다(get_*_dir 만 바꾸면 실제 data/ 에 쓴다)
import os, sys, json, math, io, shutil, tempfile, unittest, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
MM = 25.4 / 72


def _square_svg(path, spikes):
    """한 변 300×400pt 사각형 조각 하나(왼쪽 변 1개 · 오른쪽 변 2개 노치를 spikes 면 넣는다)"""
    P = [(50, 50), (350, 50), (350, 450)]
    if spikes:
        d = 5 / MM
        P += [(350, 300), (350 - d, 300), (350, 300), (350, 330), (350 - d, 330), (350, 330)]
    P += [(50, 450)]
    if spikes:
        d = 5 / MM
        P += [(50, 250), (50 + d, 250), (50, 250)]
    P += [P[0]]
    with open(path, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="500" viewBox="0 0 400 500">\n'
                '  <polyline class="st0" points="' + " ".join(f"{x:.3f} {y:.3f}" for x, y in P) + '"/>\n</svg>\n')


def _preset(d, notches):
    pr = {"preset_name": "시험", "version": 1,
          "design": {"base_size": "M", "design_file": "design.pdf", "page_size_pt": [400, 500]},
          "sizes": [{"name": "M", "pattern_file": "M.svg", "scale": 1.0}],
          "pieces": [{"id": "front", "name": "앞판", "svg_index": 0, "design_region_pt": [0, 0, 400, 500]}],
          "design_mapping": {"mode": "anchor", "anchor": "bottom-left", "fit": "contain", "preserve_aspect": True},
          "shrink": {"x": 1.0, "y": 1.0}, "output": {"format": "pdf"},
          "cutline": {"draw_from": "svg_polygon", "color_cmyk": [0, 0.96, 0.95, 0], "stroke_width": 2.0}}
    if notches:
        pr["notches"] = {"rule": "pants", "notched_suffix": ".notched.svg", "depth_mm": 5.0,
                         "sizes": {"M": {"pieces": [[{"p": [50, 250], "w": [1, 0], "depth_mm": 5.0},
                                                     {"p": [350, 300], "w": [-1, 0], "depth_mm": 5.0},
                                                     {"p": [350, 330], "w": [-1, 0], "depth_mm": 5.0}]],
                                         "kinds": ["one_piece"], "mirror": [False]}}}
    with open(os.path.join(d, "preset.json"), "w", encoding="utf-8") as f:
        json.dump(pr, f, ensure_ascii=False)
    _square_svg(os.path.join(d, "M.svg"), False)
    _square_svg(os.path.join(d, "M.notched.svg"), True)
    import fitz
    doc = fitz.open(); pg = doc.new_page(width=400, height=500)
    pg.draw_rect(pg.rect, color=None, fill=(0.1, 0.05, 0, 0)); pg.clean_contents()
    doc.save(os.path.join(d, "design.pdf"), garbage=3)


def _red_tips(pdf):
    import fitz
    pg = fitz.open(pdf)[0]; n = 0
    for dr in pg.get_drawings():
        c = dr.get("color")
        red = c and ((len(c) == 4 and c[1] > 0.9 and c[2] > 0.9) or (len(c) == 3 and c[0] > 0.8 and c[1] < 0.3 and c[2] < 0.3))
        if not red: continue                                   # 재단선 빨강(CMYK 0·96·95·0 — 뷰어에 따라 RGB 로 나온다)
        P = []
        for it in dr["items"]:
            if it[0] != "l": continue
            for q in (it[1], it[2]):
                if not P or abs(P[-1].x - q.x) + abs(P[-1].y - q.y) > 1e-6: P.append(q)
        n += sum(1 for i in range(1, len(P) - 1) if abs(P[i - 1].x - P[i + 1].x) + abs(P[i - 1].y - P[i + 1].y) < 1e-3
                 and 3 < math.hypot(P[i].x - P[i - 1].x, P[i].y - P[i - 1].y) * MM < 7)
    return n


class NotchPreset(unittest.TestCase):
    def test_vendor_has_notch_engine(self):
        """엔진 사본에 노치 파일이 있어야 등록·DXF 가 된다(scripts/sync_pattern_engine.py ROOTS 에 preset_export.py)"""
        v = os.path.join(ROOT, "vendor", "pattern_engine")
        for f in ("notch_rules.py", "preset_export.py", "illustrator.py", "notching.py"):
            self.assertTrue(os.path.isfile(os.path.join(v, f)), f"vendor 에 {f} 없음")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="notch_preset_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, notches):
        from engine.job import run_job
        d = os.path.join(self.tmp, "p_on" if notches else "p_off"); os.makedirs(d)
        _preset(d, notches)
        res = run_job(os.path.join(d, "preset.json"), os.path.join(d, "design.pdf"),
                      [{"size": "M", "name": "A", "number": "1", "qty": 1}], os.path.join(d, "job"), make_preview=False, out_format="pdf")
        o = res["outputs"][0]
        return _red_tips(o["pdf"] if os.path.isabs(o["pdf"]) else os.path.join(d, "job", o["pdf"]))

    def test_order_pdf_cutline_has_notches(self):
        self.assertEqual(self._run(True), 3, "노치 프리셋 — 빨간 재단선에 홈 3개")

    def test_preset_without_notches_unchanged(self):
        self.assertEqual(self._run(False), 0, "노치 설정이 없으면 노치 든 SVG 가 있어도 안 쓴다")

    def test_cut_dxf_endpoint(self):
        import ezdxf
        from webapp import state
        old = (state.PATTERNS_DIR, state.UPLOADS_DIR)
        state.PATTERNS_DIR = os.path.join(self.tmp, "patterns"); state.UPLOADS_DIR = os.path.join(self.tmp, "uploads")
        try:
            d = os.path.join(state.PATTERNS_DIR, "시험_노치"); os.makedirs(d); _preset(d, True)
            from fastapi.testclient import TestClient
            from webapp.main import app
            r = TestClient(app).get("/api/patterns/시험_노치/cut-dxf")
            self.assertEqual(r.status_code, 200, r.text[:300])
            z = zipfile.ZipFile(io.BytesIO(r.content)); names = z.namelist()
            self.assertEqual(len(names), 1)
            doc = ezdxf.read(io.StringIO(z.read(names[0]).decode("ascii")))
            blocks = [b for b in doc.blocks if not b.name.startswith("*")]
            self.assertEqual(sum(1 for b in blocks for e in b if e.dxftype() == "POINT" and e.dxf.layer == "4"), 3, "레이어 4 노치 점 3개")
            self.assertEqual(sum(1 for b in blocks for e in b if e.dxftype() == "POLYLINE" and e.dxf.layer == "1"), 1)
        finally:
            state.PATTERNS_DIR, state.UPLOADS_DIR = old

    def test_notch_options(self):
        from webapp.api import _notch_options
        from fastapi import HTTPException
        w = []
        self.assertIsNone(_notch_options("", None, None, w), "노치 안 고르면 None(기존 동작)")
        from fastapi import Form
        self.assertIsNone(_notch_options(Form(None), Form(None), Form(None), w), "드라이브 등록처럼 함수로 부를 때의 Form 객체 = 없음")
        o = _notch_options("pants", "split_front, split_back", '{"xl":[283.5,307.8]}', w)
        self.assertEqual(o, {"rule": "pants", "select": ["split_front", "split_back"], "side": {"XL": [283.5, 307.8]}})
        with self.assertRaises(HTTPException): _notch_options("hat", None, None, w)
        with self.assertRaises(HTTPException): _notch_options("pants", None, "[1,2]", w)


if __name__ == "__main__":
    unittest.main(verbosity=2)
