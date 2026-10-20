# 디자인 영역 자동 짝짓기 시험(2026-10-20) — 모양으로 · 왼·오른 소매(거울)를 가려서 · 디자인에 한 장뿐이면 뒤집어서
#   실행: python -m unittest tests.test_region_match -v   (저장소 루트)
#   배경: 영역을 안 맞춘 등록은 «균등분할» 어림값이라 그림이 잘렸고, 크기가 같은 왼·오른 소매는 뒤바뀌었다.
import os, sys, json, shutil, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 좌우가 다른(쏠린) 소매 윤곽 — 오른쪽이 더 깊게 파였다
SLEEVE = [(0, 0), (400, 0), (380, 120), (300, 220), (60, 200)]


def _mirror(P):
    return [(400 - x, y) for x, y in P]


def _shift(P, dx, dy):
    return [(x + dx, y + dy) for x, y in P]


def _svg(path, polys, H=1600):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 {H}">'
                + "".join('<polyline points="' + " ".join(f"{x} {H - y}" for x, y in P + [P[0]]) + '"/>' for P in polys)
                + "</svg>")


def _design(path, polys, fills=None):
    """PDF(y 위로) 좌표의 윤곽들을 회색 선 + 채움으로 그린 디자인(2000×1600)."""
    import fitz, pikepdf
    d = fitz.open()
    pg = d.new_page(width=2000, height=1600)
    for i, P in enumerate(polys):
        pts = [fitz.Point(x, 1600 - y) for x, y in P] + [fitz.Point(P[0][0], 1600 - P[0][1])]
        pg.draw_polyline(pts, color=(0.6, 0.6, 0.6), fill=(fills or [(1, 1, 1)] * len(polys))[i], width=1)
    tmp = path + ".tmp.pdf"
    d.save(tmp)
    with pikepdf.open(tmp) as pdf:
        pdf.pages[0].contents_coalesce()
        pdf.save(path)
    os.remove(tmp)


class RegionMatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="region_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_left_right_sleeves_not_swapped(self):
        """패턴 왼소매(원본)·오른소매(거울) ↔ 디자인에선 자리를 바꿔 그려도 모양으로 제 짝을 찾는다"""
        from engine.region_match import match_regions
        from engine.pattern import parse_svg
        left, right = _shift(SLEEVE, 100, 100), _shift(_mirror(SLEEVE), 700, 100)
        _svg(os.path.join(self.tmp, "p.svg"), [left, right])
        # 디자인엔 오른소매를 왼쪽 자리에, 왼소매를 오른쪽 자리에
        d_right, d_left = _shift(_mirror(SLEEVE), 1100, 900), _shift(SLEEVE, 1600, 900)
        _design(os.path.join(self.tmp, "d.pdf"), [d_right, d_left])
        polys = parse_svg(os.path.join(self.tmp, "p.svg"))
        m = match_regions(os.path.join(self.tmp, "d.pdf"), polys)
        idx_left = min(range(2), key=lambda i: polys[i].bbox[0])      # 패턴 왼소매
        self.assertAlmostEqual(m[idx_left]["region_pt"][0], 1600, delta=2, msg=m)   # 디자인 «왼소매 모양»(오른쪽 자리)
        self.assertFalse(m[idx_left]["mirrored"])
        self.assertAlmostEqual(m[1 - idx_left]["region_pt"][0], 1100, delta=2, msg=m)

    def test_single_sleeve_in_design_is_mirrored(self):
        """디자인엔 소매가 한 장뿐 → 나머지 소매는 같은 그림을 뒤집어 쓴다"""
        from engine.region_match import match_regions
        from engine.pattern import parse_svg
        _svg(os.path.join(self.tmp, "p.svg"), [_shift(SLEEVE, 100, 100), _shift(_mirror(SLEEVE), 700, 100)])
        _design(os.path.join(self.tmp, "d.pdf"), [_shift(SLEEVE, 1200, 900)])
        polys = parse_svg(os.path.join(self.tmp, "p.svg"))
        m = match_regions(os.path.join(self.tmp, "d.pdf"), polys)
        self.assertEqual(len(m), 2, m)
        self.assertEqual(sorted(v["mirrored"] for v in m.values()), [False, True])

    def test_with_mirror_matrix(self):
        """뒤집기 행렬: 영역 왼끝 → 오른끝, 오른끝 → 왼끝 (그다음 m 적용)"""
        from engine.pdfutil import with_mirror
        m = with_mirror((100, 0, 300, 50), (2, 0, 0, 2, 10, 20))
        ap = lambda M, x, y: (M[0] * x + M[2] * y + M[4], M[1] * x + M[3] * y + M[5])
        self.assertEqual(ap(m, 100, 0), ap((2, 0, 0, 2, 10, 20), 300, 0))
        self.assertEqual(ap(m, 300, 50), ap((2, 0, 0, 2, 10, 20), 100, 50))

    def test_run_job_auto_regions(self):
        """run_job: design.auto_regions 면 디자인 윤곽으로 영역을 맞추고 알린다(검증 통과)"""
        from engine.job import run_job
        d = os.path.join(self.tmp, "j"); os.makedirs(d)
        body = [(0, 0), (500, 0), (500, 700), (0, 700)]
        polys = [_shift(body, 100, 100), _shift(SLEEVE, 700, 100), _shift(_mirror(SLEEVE), 700, 500)]
        for sz in ("M", "L"):
            _svg(os.path.join(d, f"{sz}.svg"), polys)
        design = os.path.join(d, "design.pdf")
        _design(design, [_shift(body, 1300, 800), _shift(_mirror(SLEEVE), 200, 1100), _shift(SLEEVE, 200, 800)],
                fills=[(0.9, 0.2, 0.2), (0.2, 0.2, 0.9), (0.2, 0.9, 0.2)])
        pr = {"preset_name": "t", "version": 1, "design": {"base_size": "L", "page_size_pt": [2000, 1600], "auto_regions": True},
              "sizes": [{"name": "M", "pattern_file": "M.svg"}, {"name": "L", "pattern_file": "L.svg"}],
              "pieces": [{"id": "front", "svg_index": 0, "design_region_pt": [0, 0, 2000, 800]},
                         {"id": "s1", "svg_index": 1, "design_region_pt": [0, 800, 1000, 1600]},
                         {"id": "s2", "svg_index": 2, "design_region_pt": [1000, 800, 2000, 1600]}],
              "design_mapping": {"mode": "anchor"}, "shrink": {"x": 1.0, "y": 1.0}, "output": {"format": "pdf"}}
        with open(os.path.join(d, "preset.json"), "w", encoding="utf-8") as f:
            json.dump(pr, f)
        res = run_job(os.path.join(d, "preset.json"), design, [{"size": "M", "name": "", "number": "", "qty": 1}],
                      os.path.join(d, "job"), make_preview=False, out_format="pdf")
        self.assertEqual(res["summary"]["verify_pass"], 1, res["summary"])
        self.assertTrue(any(w.startswith("[영역]") for w in res["summary"]["warnings"]), res["summary"]["warnings"])


if __name__ == "__main__":
    unittest.main()
