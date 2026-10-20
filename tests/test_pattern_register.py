# 패턴 등록 오인식 시험(2026-10-20) — 대지 테두리·대지 밖 조각·잘린 조각·큰 대지 밴드·곡선·사이즈별 조각 번호
#   실행: python -m unittest tests.test_pattern_register -v   (저장소 루트)
#   배경: 하키티·슈팅셔츠·축구·하의 마스터를 그대로 올리면 대지 테두리(clipPath)를 조각으로 읽어 «복붙» 오판으로
#        사이즈가 꺼지고(기준 XL 포함), 대지 밖 조각은 출력에서 잘리고, 사이즈마다 같은 번호가 다른 조각을 가리켰다.
import os, sys, math, shutil, tempfile, unittest
import xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
MM = 25.4 / 72


def _path_svg(path, w, h, shapes, clip_border=True):
    """PyMuPDF get_svg_image 꼴 path SVG — shapes = [(점 목록 또는 d 문자열)], 대지 테두리는 clipPath 안."""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    if clip_border:
        out.append(f'<defs><clipPath id="c0"><path d="M0 {h}H{w}V0H0Z"/></clipPath></defs>')
    out.append('<g clip-path="url(#c0)">')
    for s in shapes:
        fill_only = isinstance(s, tuple) and s[0] == "fill"
        if fill_only:
            s = s[1]
        d = s if isinstance(s, str) else "M" + " L".join(f"{x:g} {y:g}" for x, y in s) + " Z"
        paint = 'fill="#d8242a"' if fill_only else 'fill="none" stroke="#231916"'
        out.append(f'<path d="{d}" {paint}/>')
    out.append("</g></svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _poly_svg(path, w, h, polys):
    """이미 polyline 인 SVG(사이즈 파일 .svg 업로드용)."""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    for P in polys:
        out.append('<polyline class="st0" points="' + " ".join(f"{x:g} {y:g}" for x, y in P + [P[0]]) + '"/>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def _sleeve(x, y, s, mirror=False):
    """좌우가 다른(쏠린) 소매 모양 — 거울이면 x 를 뒤집는다."""
    P = [(0, 0), (300, 0), (260, 160), (60, 200)]
    P = [((300 - px) if mirror else px, py) for px, py in P]
    return [(x + px * s, y + py * s) for px, py in P]


class Normalize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pat_reg_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _norm(self, shapes, w=3000, h=2000, **kw):
        from engine.svg_normalize import normalize_svg
        from engine.pattern import parse_svg
        src, dst = os.path.join(self.tmp, "in.svg"), os.path.join(self.tmp, "out.svg")
        _path_svg(src, w, h, shapes, **kw)
        r = normalize_svg(src, dst)
        return r, parse_svg(dst), dst

    def test_clip_border_is_not_a_piece(self):
        """대지 테두리(clipPath 안 사각형)는 조각이 아니다"""
        r, ps, _ = self._norm([_rect(100, 100, 800, 1200), _rect(1000, 100, 800, 1150)])
        self.assertEqual(r["pieces_written"], 2)
        self.assertGreaterEqual(r["dropped_clip"], 1)
        self.assertTrue(all(p.width < 1000 for p in ps), "3000pt 테두리가 조각으로 들어오면 안 된다")

    def test_band_kept_on_huge_board(self):
        """대지가 아주 커도(14400pt) 54mm 띠(목 밴드)는 남는다 — 예전엔 페이지 넓이 기준이라 버려졌다"""
        band_h = 54 / MM
        r, ps, _ = self._norm([_rect(500, 500, 1500, 2200), _rect(2500, 500, 1500, 2100), _rect(500, 3500, 1200, band_h)],
                              w=14400, h=14400)
        self.assertEqual(r["pieces_written"], 3, f"밴드가 빠졌다: {[(round(p.width), round(p.height)) for p in ps]}")

    def test_board_cut_copy_dropped_full_kept(self):
        """대지 아래 경계에서 잘린 사본은 빼고, 대지 밖까지 온전한 조각은 남긴다(하키티 소매)"""
        full = _rect(1000, 1700, 600, 500)          # 대지(2000) 밖으로 200 나감
        cut = _rect(1000, 1700, 600, 300)           # 같은 자리, 대지 경계(y=2000)에서 잘림
        r, ps, _ = self._norm([_rect(100, 100, 800, 1200), full, cut])
        self.assertEqual(r["pieces_written"], 2)
        self.assertEqual(len(r["dropped_edge_cut"]), 1)
        self.assertTrue(any(abs(p.height - 500) < 1 for p in ps), "온전한 소매(높이 500)가 남아야 한다")

    def test_edge_touching_outlined_piece_kept(self):
        """대지를 그림에 맞춘 파일: 윤곽선 있는 조각이 경계에 붙어 있어도 남긴다(경고만)"""
        r, ps, _ = self._norm([_rect(100, 100, 800, 1200), _rect(1000, 1800, 900, 200)])   # 아래 변이 y=2000 경계
        self.assertEqual(r["pieces_written"], 2)
        self.assertEqual(r["dropped_edge_cut"], [])
        self.assertTrue(any("윤곽선이 있어 남겼습니다" in w for w in r["warnings"]), r["warnings"])

    def test_edge_cut_fill_only_dropped(self):
        """윤곽선 없이 채움만 있는 잘린 색 면(하의 XL 트임판)은 뺀다"""
        r, ps, _ = self._norm([_rect(100, 100, 800, 1200), ("fill", _rect(1000, 1800, 900, 200))])
        self.assertEqual(r["pieces_written"], 1)
        self.assertEqual(len(r["dropped_edge_cut"]), 1)

    def test_off_board_pieces_moved_inside(self):
        """대지 왼쪽 밖(음수 x)에 놓인 조각 → 전체를 대지 안으로 옮긴다(조각끼리 간격은 그대로)"""
        r, ps, dst = self._norm([_rect(-400, 100, 800, 1200), _rect(600, 100, 800, 1150)])
        self.assertIsNotNone(r["shifted"])
        xs = sorted(p.bbox[0] for p in ps)
        self.assertGreaterEqual(xs[0], 0.0, "조각이 페이지 안(양수 좌표)이어야 출력에서 안 잘린다")
        self.assertAlmostEqual(xs[1] - xs[0], 1000.0, places=3)
        vb = ET.parse(dst).getroot().get("viewBox").split()
        self.assertGreaterEqual(float(vb[2]), max(p.bbox[2] for p in ps))

    def test_on_board_unchanged(self):
        """대지 안 조각만 있으면 옮기지 않는다(기존 패턴 회귀 0)"""
        r, ps, _ = self._norm([_rect(100, 100, 800, 1200), _rect(1000, 100, 800, 1150)])
        self.assertIsNone(r["shifted"])
        self.assertEqual(sorted(round(p.bbox[0]) for p in ps), [100, 1000])

    def test_curve_flattened(self):
        """베지어 곡선은 평탄화 — 반지름 500 원의 4등분 베지어가 원에서 0.5pt 안"""
        k = 0.5523 * 500
        cx, cy = 1500, 1000
        d = (f"M{cx + 500} {cy} C{cx + 500} {cy + k} {cx + k} {cy + 500} {cx} {cy + 500} "
             f"C{cx - k} {cy + 500} {cx - 500} {cy + k} {cx - 500} {cy} "
             f"C{cx - 500} {cy - k} {cx - k} {cy - 500} {cx} {cy - 500} "
             f"C{cx + k} {cy - 500} {cx + 500} {cy - k} {cx + 500} {cy} Z")
        r, ps, _ = self._norm([d])
        self.assertEqual(r["pieces_written"], 1)
        self.assertFalse(r["has_curves"])
        P = ps[0].points
        self.assertGreater(len(P), 40)
        err = max(abs(math.hypot(x - cx, (2000 - y) - cy) - 500) for x, y in P)
        self.assertLess(err, 0.5, f"원에서 최대 {err:.2f}pt 벗어남")

    def test_curve_old_mode_still_available(self):
        """flatten_curves=False 는 옛 «끝점만» — 비교용으로 남아 있다"""
        from engine.svg_normalize import _parse_path_d
        pts, closed, has = _parse_path_d("M0 0 C0 100 100 100 100 0 Z", flatten_curves=False)
        self.assertEqual(len(pts), 2)
        self.assertTrue(has)
        pts2, _, has2 = _parse_path_d("M0 0 C0 100 100 100 100 0 Z")
        self.assertEqual(len(pts2), 17)
        self.assertFalse(has2)


class ParseOrder(unittest.TestCase):
    def test_data_order_honored_else_height(self):
        from engine.pattern import parse_svg
        tmp = tempfile.mkdtemp(prefix="pat_ord_")
        try:
            p = os.path.join(tmp, "a.svg")
            with open(p, "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                        '<polyline data-order="1" points="0 0 10 0 10 90 0 90"/>'
                        '<polyline data-order="0" points="20 0 30 0 30 20 20 20"/></svg>')
            self.assertEqual([round(x.height) for x in parse_svg(p)], [20, 90], "data-order 를 따른다")
            with open(p, "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                        '<polyline points="20 0 30 0 30 20 20 20"/><polyline points="0 0 10 0 10 90 0 90"/></svg>')
            self.assertEqual([round(x.height) for x in parse_svg(p)], [90, 20], "data-order 없으면 예전대로 높이순")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class DuplicateGuard(unittest.TestCase):
    def test_all_pieces_compared(self):
        """0번 조각만 같고 나머지가 다르면 복붙이 아니다 — 전부 같아야 복붙"""
        from engine.svg_normalize import check_size_monotonicity
        tmp = tempfile.mkdtemp(prefix="pat_dup_")
        try:
            a, b, c = (os.path.join(tmp, f"{n}.svg") for n in ("M", "L", "XL"))
            _poly_svg(a, 3000, 2000, [_rect(0, 0, 900, 1500), _rect(1000, 0, 800, 1200)])
            _poly_svg(b, 3000, 2000, [_rect(0, 0, 900, 1500), _rect(1000, 0, 840, 1260)])
            _poly_svg(c, 3000, 2000, [_rect(0, 0, 900, 1500), _rect(1000, 0, 840, 1260)])
            g = check_size_monotonicity({"M": a, "L": b}, piece_index=None)
            self.assertEqual(g["duplicates"], [], "다른 조각이 다르면 복붙 아님")
            g0 = check_size_monotonicity({"M": a, "L": b}, piece_index=0)
            self.assertEqual(len(g0["duplicates"]), 1, "옛 방식(0번만)은 오판 — 바뀐 이유")
            g2 = check_size_monotonicity({"L": b, "XL": c}, piece_index=None)
            self.assertEqual(len(g2["duplicates"]), 1, "전부 같으면 진짜 복붙")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RegisterAlign(unittest.TestCase):
    """등록 API — 사이즈마다 조각 순서가 달라도 같은 조각에 같은 번호, 남는 조각은 빼고, 빠진 사이즈는 끈다"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pat_align_")
        from webapp import state
        self.old = (state.PATTERNS_DIR, state.UPLOADS_DIR)
        state.PATTERNS_DIR = os.path.join(self.tmp, "patterns")
        state.UPLOADS_DIR = os.path.join(self.tmp, "uploads")

    def tearDown(self):
        from webapp import state
        state.PATTERNS_DIR, state.UPLOADS_DIR = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _register(self, files, base="L"):
        from fastapi.testclient import TestClient
        from webapp.main import app
        fh = [("files", (f"{s}.svg", open(p, "rb"))) for s, p in files]
        try:
            r = TestClient(app).post("/api/patterns", data={"name": "정렬시험", "base_size": base}, files=fh)
        finally:
            for _, (_, f) in fh:
                f.close()
        return r

    def test_align_reorder_drop_disable(self):
        from engine.pattern import parse_svg
        src = os.path.join(self.tmp, "src"); os.makedirs(src)
        files = []
        # 몸판(높이 1500·1450) + 왼·오른 소매(거울). 사이즈 S 는 몸판 두 장 높이가 뒤바뀐다(옛 높이순이면 번호가 엇갈림)
        for sz, s, body_h, extra, drop_sleeve in (("S", 0.92, (1380, 1395), True, False), ("M", 0.96, (1440, 1392), False, False),
                                                 ("L", 1.0, (1500, 1450), False, False), ("XL", 1.04, (1560, 1508), False, True)):
            polys = [_rect(100, 100, 900 * s, body_h[0]), _rect(1100, 100, 860 * s, body_h[1]),
                     _sleeve(100, 1800, s), _sleeve(700, 1800, s, mirror=True)]
            if extra:
                polys.append(_rect(1500, 1800, 700, 40))          # S 에만 있는 띠 → 빼야 한다
            if drop_sleeve:
                polys.pop(3)                                       # XL 에 오른 소매가 없다 → 사이즈를 끈다
            p = os.path.join(src, f"{sz}.svg"); _poly_svg(p, 3000, 2400, polys); files.append((sz, p))
        r = self._register(files)
        self.assertEqual(r.status_code, 200, r.text[:500])
        j = r.json()
        self.assertEqual(j["pieces"], 4)
        self.assertEqual([d["name"] for d in j["disabled_sizes"]], ["XL"], j["warnings"])
        self.assertTrue(any("기준 사이즈에 없는 조각" in w and "S" in w for w in j["warnings"]), j["warnings"])
        pdir = os.path.join(self.tmp, "patterns", "정렬시험")
        ref = parse_svg(os.path.join(pdir, "L.svg"))
        for sz in ("S", "M"):
            ps = parse_svg(os.path.join(pdir, f"{sz}.svg"))
            self.assertEqual(len(ps), 4, sz)
            for i, (a, b) in enumerate(zip(ref, ps)):
                ratio_w = b.width / a.width
                self.assertTrue(0.85 < ratio_w < 1.0, f"{sz}#{i}: 같은 번호가 다른 조각(폭비 {ratio_w:.2f})")
            # 거울 소매: 2·3번의 좌우 순서가 기준과 같아야 한다
            self.assertLess(ps[2].bbox[0], ps[3].bbox[0], f"{sz}: 왼·오른 소매가 뒤바뀜")

    def test_base_with_no_pieces_does_not_wipe_others(self):
        """기준 사이즈 파일만 조각이 0개여도 다른 사이즈는 멀쩡해야 한다(리뷰 지적 — 예전 수정안은 전부 0조각으로 다시 썼다)"""
        from engine.pattern import parse_svg
        src = os.path.join(self.tmp, "src"); os.makedirs(src)
        files = []
        for sz, s, n in (("M", 0.96, 2), ("L", 1.0, 0), ("XL", 1.04, 2)):
            p = os.path.join(src, f"{sz}.svg")
            _poly_svg(p, 3000, 2400, [_rect(100, 100, 900 * s, 1500 * s), _rect(1100, 100, 860 * s, 1450 * s)][:n])
            files.append((sz, p))
        r = self._register(files, base="L")
        self.assertEqual(r.status_code, 200, r.text[:500])
        pdir = os.path.join(self.tmp, "patterns", "정렬시험")
        for sz in ("M", "XL"):
            self.assertEqual(len(parse_svg(os.path.join(pdir, f"{sz}.svg"))), 2, sz)

    def test_base_disabled_falls_back(self):
        """기준 사이즈가 꺼지면 살아 있는 사이즈로 기준을 바꾼다(예전엔 작업이 바로 멈췄다)"""
        src = os.path.join(self.tmp, "src"); os.makedirs(src)
        files = []
        for sz, s, n in (("M", 0.96, 2), ("L", 1.0, 2), ("XL", 1.04, 1)):
            polys = [_rect(100, 100, 900 * s, 1500 * s), _rect(1100, 100, 860 * s, 1450 * s)][:n]
            p = os.path.join(src, f"{sz}.svg"); _poly_svg(p, 3000, 2400, polys); files.append((sz, p))
        r = self._register(files, base="XL")
        self.assertEqual(r.status_code, 200, r.text[:500])
        import json
        with open(os.path.join(self.tmp, "patterns", "정렬시험", "preset.json"), encoding="utf-8") as f:
            pr = json.load(f)
        self.assertIn(pr["design"]["base_size"], [s["name"] for s in pr["sizes"]])


if __name__ == "__main__":
    unittest.main()
