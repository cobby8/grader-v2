# -*- coding: utf-8 -*-
"""재단 패턴(F10 1단계) API 시험 — webapp/cad.py

  ① 올리기 → 새 버전(v1, v2 …) · 덮어쓰기 없음 · 목록/정보/화면 자료
  ② 내려받은 파일이 올린 것과 지문(sha256) 동일 — ZIP 통째 · 사이즈별 DXF 등
  ③ 잘못 올린 것(짝 안 맞는 ZIP · 한글 스타일 번호 · ZIP 안 한글 이름) → 400
  ④ 권한: 인증 켜짐에서 토큰 없음 401 · 일반 직원 올리기 403 · 보기는 통과
  ⑤ 창고 백업(가짜 창고): 열쇠가 영문·숫자·-·/ 만 · 되읽기 확인 · 디스크가 비면 로그인 요청 때 복원
  (선택) stizshop 가 만든 실제 가스 웜업 묶음이 옆 폴더에 있으면 그것도 올려 9벌·지문을 본다

실행(저장소 루트): python -m unittest discover -s tests -v
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402

STIZ_CAD = os.environ.get("STIZ_CAD_DIR", os.path.join(os.path.dirname(ROOT), "stizshop", "tmp", "pattern-engine", "cad"))
sha = lambda b: hashlib.sha256(b).hexdigest()


def make_bundle(style_id="test-style-top", sizes=("S", "M")):
    """작은 가짜 묶음 — cad_view.py 와 같은 모양(view.json + exports.zip)"""
    files, members = [], {}
    for s in sizes:
        data = f"0\nSECTION\n{s}\n".encode() * 50
        p = f"sizes/{s}/TOP_{s}.dxf"; members[p] = data
        files.append({"kind": "dxf", "size": s, "path": p, "orig": f"상의_{s}.dxf", "bytes": len(data), "sha256": sha(data)})
    rul = b"RUL\n"; members["aama/GAS_WARMUP_TOP.rul"] = rul
    files.append({"kind": "rul", "size": None, "path": "aama/GAS_WARMUP_TOP.rul", "orig": "GAS_WARMUP_TOP.rul", "bytes": 4, "sha256": sha(rul)})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p, b in members.items():
            z.writestr(zipfile.ZipInfo(p, (2026, 1, 1, 0, 0, 0)), b)
        z.writestr("manifest.json", json.dumps({"files": files}))
    zb = buf.getvalue()
    piece = {"name": "뒤판", "seam": [0, 0, 1000, 0, 1000, 1000, 0, 1000], "cut": [-90, -90, 1090, -90, 1090, 1090, -90, 1090],
             "internal": [], "notches": [], "holes": [], "fold": None, "nodes": {"a": 0, "b": 2}, "qty": 1}
    view = {"format": "stiz-cad-view", "version": 1, "unit": "mm", "q": 0.01,
            "style": {"id": style_id, "name": "시험 스타일", "garment": "상의", "group": "top", "base_size": sizes[0],
                      "sizes": list(sizes), "size_labels": {}, "pieces": ["뒤판"]},
            "sizes": {s: {"label": s, "pieces": [piece], "checks": []} for s in sizes},
            "files": files, "exports_zip": {"sha256": sha(zb), "bytes": len(zb)}, "source": {"commit": "test"}}
    return json.dumps(view, ensure_ascii=False).encode("utf-8"), zb, members


class CadBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cad-test-")
        self.env = mock.patch.dict(os.environ, {"GRADER_CAD_DIR": self.tmp, "GRADER_REQUIRE_AUTH": "0",
                                                "GRADER_CLEANUP_DISABLED": "1", "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": ""})
        self.env.start()
        from webapp import cad
        self.cad = cad
        cad._last_restore["at"] = 0.0
        from webapp.main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def upload(self, view, zb, note="", headers=None):
        return self.client.post("/api/cad/styles", files={"view": ("view.json", view, "application/json"),
                                                         "exports": ("exports.zip", zb, "application/zip")},
                                data={"note": note}, headers=headers or {})


class CadApi(CadBase):
    def test_upload_versions_and_fingerprints(self):
        view, zb, members = make_bundle()
        r = self.upload(view, zb, "첫 판"); self.assertEqual(r.status_code, 201, r.text)
        j = r.json(); self.assertEqual((j["style_id"], j["version"]), ("test-style-top", 1))
        self.assertTrue(j["backup"]["skipped"])                                   # 로컬 — 창고 없음
        r2 = self.upload(view, zb, "둘째 판"); self.assertEqual(r2.json()["version"], 2)   # 덮어쓰지 않고 늘린다
        lst = self.client.get("/api/cad/styles").json()["styles"]
        self.assertEqual([s["id"] for s in lst], ["test-style-top"]); self.assertEqual(lst[0]["versions"], [1, 2])
        info = self.client.get("/api/cad/styles/test-style-top").json()
        self.assertEqual([h["note"] for h in info["history"]], ["첫 판", "둘째 판"])
        self.assertEqual(sha(self.client.get("/api/cad/styles/test-style-top/v/1/view").content), sha(view))
        self.assertEqual(self.client.get("/api/cad/styles/test-style-top/v/latest/view").headers["x-cad-version"], "2")
        z = self.client.get("/api/cad/styles/test-style-top/v/2/files/zip"); self.assertEqual(sha(z.content), sha(zb))
        d = self.client.get("/api/cad/styles/test-style-top/v/1/files/dxf?size=M")
        self.assertEqual(d.status_code, 200); self.assertEqual(sha(d.content), sha(members["sizes/M/TOP_M.dxf"]))
        self.assertIn("filename*=UTF-8''", d.headers["content-disposition"])     # 원래 한글 이름도 같이
        self.assertEqual(self.client.get("/api/cad/styles/test-style-top/v/1/files/dxf").status_code, 400)  # 사이즈 고르기
        self.assertEqual(sha(self.client.get("/api/cad/styles/test-style-top/v/1/files/rul").content), sha(b"RUL\n"))
        self.assertEqual(self.client.get("/api/cad/styles/test-style-top/v/1/files/a4").status_code, 404)
        self.assertEqual(self.client.get("/api/cad/styles/test-style-top/v/9/view").status_code, 404)
        self.assertEqual(self.client.get("/api/cad/styles/Bad_ID/v/1/view").status_code, 400)
        self.assertTrue(self.client.get("/api/cad/me").json()["can_upload"])      # 로컬 무인증 = 올리기 가능

    def test_rejects_bad_uploads(self):
        view, zb, _ = make_bundle()
        _, other, _ = make_bundle(sizes=("S", "L"))
        self.assertEqual(self.upload(view, other).status_code, 400)                 # 짝이 아닌 ZIP
        v2 = json.loads(view); v2["style"]["id"] = "가스-상의"
        self.assertEqual(self.upload(json.dumps(v2).encode(), zb).status_code, 400)  # 한글 스타일 번호
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z: z.writestr("상의.dxf", b"x")
        v3 = json.loads(view); v3["exports_zip"] = {}
        self.assertEqual(self.upload(json.dumps(v3).encode(), buf.getvalue()).status_code, 400)  # ZIP 안 한글 이름
        self.assertEqual(self.upload(b"{not json", zb).status_code, 400)
        self.assertFalse(os.listdir(self.tmp))                                      # 아무것도 안 남았다

    def test_object_keys_ascii_only(self):
        self.assertEqual(self.cad.object_key("gas-warmup-2026-top", 3, "view"), "gas-warmup-2026-top/v3/view")
        with self.assertRaises(ValueError):
            self.cad.object_key("gas-warmup-2026-top", 1, "view.json")                 # 점도 안 쓴다(영문·숫자·-·/ 만)
        with self.assertRaises(ValueError):
            self.cad.object_key("상의", 1, "view")


class CadAuth(CadBase):
    def setUp(self):
        super().setUp()
        os.environ["GRADER_REQUIRE_AUTH"] = "1"
        os.environ["SUPABASE_URL"] = "https://example.invalid"; os.environ["SUPABASE_PUBLISHABLE_KEY"] = "pub-test"
        from webapp import auth
        self.roles = {"tok-admin": "admin", "tok-staff": None}
        self.p = mock.patch.object(auth, "_introspect", side_effect=lambda t: {"user_id": t, "email": t + "@stiz.kr", "role": self.roles[t]}
                                   if t in self.roles else (_ for _ in ()).throw(auth.HTTPException(status_code=401, detail="x")))
        self.p.start(); auth._TOKEN_CACHE.clear()
        # 가짜 창고 — 실제 네트워크 대신 딕셔너리
        self.store = {}
        def up(key, data, ctype, jwt):
            if self.roles.get(jwt) != "admin": return False, "status 403"
            if key in self.store: return False, "status 409"                       # 덮어쓰기 금지
            self.store[key] = data; return True, "ok"
        def down(key, jwt): return self.store.get(key) if jwt in self.roles else None
        def lst(prefix, jwt):
            if jwt not in self.roles: return None
            names = set()
            for k in self.store:
                if k.startswith(prefix): names.add(k[len(prefix):].split("/")[0] + ("" if "/" not in k[len(prefix):] else "/"))
            return [{"name": n.rstrip("/"), "id": None if n.endswith("/") else "f"} for n in sorted(names)]
        self.sp = [mock.patch.object(self.cad, "_sb_upload", side_effect=up), mock.patch.object(self.cad, "_sb_download", side_effect=down),
                   mock.patch.object(self.cad, "_sb_list", side_effect=lst)]
        for p in self.sp: p.start()

    def tearDown(self):
        for p in self.sp: p.stop()
        self.p.stop()
        super().tearDown()

    def test_gates(self):
        view, zb, _ = make_bundle()
        self.assertEqual(self.client.get("/api/cad/styles").status_code, 401)
        self.assertEqual(self.upload(view, zb, headers={"Authorization": "Bearer tok-staff"}).status_code, 403)
        self.assertFalse(self.client.get("/api/cad/me", headers={"Authorization": "Bearer tok-staff"}).json()["can_upload"])
        r = self.upload(view, zb, headers={"Authorization": "Bearer tok-admin"}); self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(self.client.get("/api/cad/styles/test-style-top/v/1/files/zip", headers={"Authorization": "Bearer tok-staff"}).status_code, 200)

    def test_backup_readback_and_restore(self):
        view, zb, _ = make_bundle()
        r = self.upload(view, zb, headers={"Authorization": "Bearer tok-admin"}).json()
        self.assertTrue(r["backup"]["ok"], r["backup"])
        self.assertEqual(sorted(self.store), ["test-style-top/v1/exports", "test-style-top/v1/meta", "test-style-top/v1/view"])
        self.assertTrue(all(o["verified"] for o in r["backup"]["objects"].values()))
        # 재배포 흉내 — 디스크를 비운다 → 로그인 직원이 목록을 열면 창고에서 복원
        shutil.rmtree(os.path.join(self.tmp, "test-style-top")); self.cad._last_restore["at"] = 0.0
        lst = self.client.get("/api/cad/styles", headers={"Authorization": "Bearer tok-staff"}).json()
        self.assertEqual(lst["restore"]["restored"], 1); self.assertEqual(lst["styles"][0]["versions"], [1])
        self.assertEqual(sha(self.client.get("/api/cad/styles/test-style-top/v/1/files/zip", headers={"Authorization": "Bearer tok-staff"}).content), sha(zb))
        # 다시 올리면 v2 — 창고의 v1 을 덮지 않는다
        r2 = self.upload(view, zb, headers={"Authorization": "Bearer tok-admin"}).json()
        self.assertEqual(r2["version"], 2); self.assertTrue(r2["backup"]["ok"]); self.assertEqual(len(self.store), 6)
        # 창고 사본이 망가졌으면(지문 불일치) 복원하지 않는다
        shutil.rmtree(os.path.join(self.tmp, "test-style-top", "v2")); self.store["test-style-top/v2/view"] = b"{}"
        self.cad._last_restore["at"] = 0.0
        lst = self.client.get("/api/cad/styles", headers={"Authorization": "Bearer tok-staff"}).json()
        self.assertEqual(lst["styles"][0]["versions"], [1])


def tweak(view_bytes, fn):
    """view.json 을 고쳐 다시 bytes 로(검사 시험용)"""
    v = json.loads(view_bytes); fn(v); return json.dumps(v, ensure_ascii=False).encode("utf-8")


class CadHardening(CadBase):
    """검증 리뷰(2026-10-19) 지적 1·2·4·5·6 — 항목마다 시험 하나씩"""

    def test_1_numbers_only_where_screen_expects_numbers(self):
        view, zb, _ = make_bundle()
        for k, bad in (("tol_check", "<img src=x onerror=alert(1)>"), ("tol_check", True), ("q", "0.01"), ("q", 0), ("simplify", [1])):
            r = self.upload(tweak(view, lambda v: v.__setitem__(k, bad)), zb)
            self.assertEqual(r.status_code, 400, (k, bad, r.text))
        self.assertEqual(self.upload(tweak(view, lambda v: v.__setitem__("tol_check", 0.1)), zb).status_code, 201)

    def test_2_zip_bomb(self):
        view, _, _ = make_bundle()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("big/BOMB.dxf", b"\0" * (self.cad.MAX_UNZIPPED_FILE + 1))   # 60MB 넘는 0 — 압축하면 수십 KB
        zb = buf.getvalue(); self.assertLess(len(zb), 1_000_000)
        r = self.upload(tweak(view, lambda v: (v.__setitem__("files", []), v.__setitem__("exports_zip", {}))), zb)
        self.assertEqual(r.status_code, 400); self.assertIn("너무 큰", r.json()["detail"])
        # 합계 상한 — 파일 하나는 작아도 합치면 넘는 경우
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for i in range(3): z.writestr(f"p/F{i}.dxf", b"\0" * 400_000)
        with mock.patch.object(self.cad, "MAX_UNZIPPED_TOTAL", 1_000_000):
            r = self.upload(tweak(view, lambda v: (v.__setitem__("files", []), v.__setitem__("exports_zip", {}))), buf.getvalue())
        self.assertEqual(r.status_code, 400); self.assertIn("풀면 너무", r.json()["detail"])

    def test_4_fullmatch_rejects_trailing_newline(self):
        for rx, ok in ((self.cad.STYLE_ID_RE, "abc"), (self.cad.KEY_RE, "abc/v1/view"), (self.cad.ZIP_MEMBER_RE, "a/B.dxf")):
            self.assertTrue(rx.fullmatch(ok)); self.assertIsNone(rx.fullmatch(ok + "\n"))
        with self.assertRaises(ValueError):
            self.cad.object_key("abc", 1, "view\n")
        view, zb, _ = make_bundle()
        self.assertEqual(self.upload(tweak(view, lambda v: v["style"].__setitem__("id", "test-style\n")), zb).status_code, 400)
        self.assertEqual(self.client.get("/api/cad/styles/abc%0A").status_code, 400)

    def test_5_odd_shapes_are_400_not_500(self):
        view, zb, _ = make_bundle()
        odd = [lambda v: v.__setitem__("style", "가스"), lambda v: v.__setitem__("files", ["a", "b"]),
               lambda v: v["files"][0].__setitem__("path", ["x"]), lambda v: v.__setitem__("exports_zip", "abc"),
               lambda v: v["style"].__setitem__("sizes", "SM"), lambda v: v["sizes"].__setitem__("S", "x"),
               lambda v: v["sizes"]["S"].__setitem__("pieces", "x"), lambda v: v["style"].__setitem__("name", {"a": 1}),
               lambda v: v["files"][0].__setitem__("size", 3), lambda v: v.__setitem__("sizes", [])]
        for i, fn in enumerate(odd):
            r = self.upload(tweak(view, fn), zb)
            self.assertEqual(r.status_code, 400, (i, r.text))
        self.assertEqual(self.upload(b"[1,2]", zb).status_code, 400)
        self.assertFalse(os.listdir(self.tmp))

    def test_6_broken_meta_is_404(self):
        view, zb, _ = make_bundle()
        self.assertEqual(self.upload(view, zb).status_code, 201)
        with open(os.path.join(self.tmp, "test-style-top", "v1", "meta.json"), "w") as f: f.write("{깨짐")
        self.assertEqual(self.client.get("/api/cad/styles/test-style-top").status_code, 404)
        self.assertEqual(self.client.get("/api/cad/styles").json()["styles"], [])


class CadStorageFailures(CadBase):
    """지적 3·7 — 창고 실패 때의 상태"""

    def setUp(self):
        super().setUp()
        os.environ["SUPABASE_URL"] = "https://example.invalid"; os.environ["SUPABASE_PUBLISHABLE_KEY"] = "pub-test"
        self.store, self.fail_keys, self.list_ok = {}, set(), True
        def up(key, data, ctype, jwt):
            if any(key.endswith(k) for k in self.fail_keys): return False, "status 500"
            if key in self.store: return False, "status 409"
            self.store[key] = data; return True, "ok"
        def lst(prefix, jwt):
            if not self.list_ok: return None
            names = set()
            for k in self.store:
                if k.startswith(prefix):
                    rest = k[len(prefix):]; names.add(rest.split("/")[0] + ("/" if "/" in rest else ""))
            return [{"name": n.rstrip("/"), "id": None if n.endswith("/") else "f"} for n in sorted(names)]
        self.sp = [mock.patch.object(self.cad, "_sb_upload", side_effect=up),
                   mock.patch.object(self.cad, "_sb_download", side_effect=lambda k, j: self.store.get(k)),
                   mock.patch.object(self.cad, "_sb_list", side_effect=lst)]
        for p in self.sp: p.start()
        self.H = {"Authorization": "Bearer tok"}                    # 인증 꺼짐(로컬 시험) — 토큰만 창고로 넘어간다

    def tearDown(self):
        for p in self.sp: p.stop()
        super().tearDown()

    def test_3_backup_failure_removes_version(self):
        view, zb, _ = make_bundle()
        self.fail_keys = {"/exports"}
        r = self.upload(view, zb, headers=self.H)
        self.assertEqual(r.status_code, 502, r.text); self.assertIn("취소", r.json()["detail"])
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "test-style-top", "v1")))     # «있는 것처럼» 남지 않는다
        self.assertEqual(self.client.get("/api/cad/styles").json()["styles"], [])
        self.fail_keys = set()                                       # 창고가 돌아오면 다시 올리기 → 다음 번호(v1 반쪽 조각은 그대로)
        r2 = self.upload(view, zb, headers=self.H); self.assertEqual(r2.status_code, 201, r2.text)
        self.assertEqual(r2.json()["version"], 2); self.assertTrue(r2.json()["backup"]["ok"])
        shutil.rmtree(os.path.join(self.tmp, "test-style-top")); self.cad._last_restore["at"] = 0.0
        lst = self.client.get("/api/cad/styles", headers=self.H).json()                  # 반쪽 v1 은 되살아나지 않는다
        self.assertEqual(lst["styles"][0]["versions"], [2])

    def test_7_restore_time_recorded_only_on_success(self):
        self.list_ok = False
        self.client.get("/api/cad/styles", headers=self.H)
        self.assertEqual(self.cad._last_restore["at"], 0.0); self.assertFalse(self.cad._last_restore["busy"])
        self.list_ok = True
        self.client.get("/api/cad/styles", headers=self.H)
        self.assertGreater(self.cad._last_restore["at"], 0.0); self.assertFalse(self.cad._last_restore["busy"])
        r = self.client.get("/api/cad/styles", headers=self.H).json()["restore"]
        self.assertTrue(r.get("cached"))                             # 성공 뒤 10분 안은 다시 안 묻는다


class CadScreen(unittest.TestCase):
    """지적 1·9·10 — 화면 파일(cad.html) 정적 검사"""
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "webapp", "static", "screens", "cad.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_1_every_interpolation_is_escaped_or_numeric(self):
        """템플릿 ${…} 는 esc·fmt·Number·encodeURIComponent 를 거치거나, 화면이 만든 값(목록)만 — 업로드 글자가 그대로 HTML 에 들어가지 않게"""
        import re
        script = self.html[self.html.index("<script>"):]
        safe_prefix = ("esc(", "fmt(", "Number(", "encodeURIComponent(", "sizeColor(", "KIND_LABEL[")
        own = {"k", "sw", "rows", "meas", "detail", "bb", "badge", "icon", "kind", "id", "ver", "dx", "dy", "dx.toFixed(3)", "dy.toFixed(3)",
               "best.idx", "tol", "j.version", "j.style_id", "S.view.style.pieces.length", "(s.versions || []).length", "(s.sizes || []).length",
               "S.view.style.sizes.indexOf(sid) + 1", "S.view.style.sizes.map(sizeLabel).map(esc).join(\" · \")",
               "v == null ? \"\" : v.toFixed(3)", "sid === S.size ? \"is-active\" : \"\"", "S.overlay.has(sid) ? \"checked\" : \"\"",
               "String(v) === String(ver) ? \"selected\" : \"\""}
        bad = []
        for m in re.finditer(r"\$\{", script):
            depth, i = 1, m.end()
            while depth and i < len(script):
                depth += {"{": 1, "}": -1}.get(script[i], 0); i += 1
            expr = script[m.end():i - 1].strip()
            if expr.startswith(safe_prefix) or expr in own: continue
            if re.match(r"^[\w.() ]+\s*\?\s*[`\"]", expr) and "esc(" in expr: continue     # 조건부 + 안에서 esc
            if expr.startswith(("m.short != null", "L.uploaded_at ?", "L.note ?", "L.uploaded_by ?", "Number(p.mult) > 1")): continue
            bad.append(expr[:80])
        self.assertEqual(bad, [])
        self.assertIn("const tol = Number(S.view.tol_check) || 0.1", self.html)
        self.assertIn('"×" + Number(p.mult)', self.html)

    def test_9_sidebar_background_to_bottom(self):
        self.assertIn("linear-gradient(to right, var(--surface-card) calc(var(--sidebar-w) - 1px)", self.html)

    def test_10_tiny_piece_labels_hidden_until_hover(self):
        for s in ("getComputedTextLength", "is-tiny", ".pname.is-tiny.is-hover", 'el("title"'):
            self.assertIn(s, self.html)


@unittest.skipUnless(os.path.isfile(os.path.join(STIZ_CAD, "gas-warmup-2026-top", "view.json")), "stizshop 가스 웜업 묶음 없음")
class CadRealGasWarmup(CadBase):
    def test_gas_warmup_top_bottom(self):
        for sid in ("gas-warmup-2026-top", "gas-warmup-2026-bottom"):
            d = os.path.join(STIZ_CAD, sid)
            with open(os.path.join(d, "view.json"), "rb") as f: view = f.read()
            with open(os.path.join(d, "exports.zip"), "rb") as f: zb = f.read()
            r = self.upload(view, zb); self.assertEqual(r.status_code, 201, r.text)
            v = json.loads(self.client.get(f"/api/cad/styles/{sid}/v/1/view").content)
            self.assertEqual(len(v["style"]["sizes"]), 9)
            self.assertEqual(sha(self.client.get(f"/api/cad/styles/{sid}/v/1/files/zip").content), sha(zb))
            for f in v["files"]:
                q = f"?size={f['size']}" if f["kind"] in ("dxf", "pdf", "ai") else ""
                got = self.client.get(f"/api/cad/styles/{sid}/v/1/files/{f['kind']}{q}")
                self.assertEqual(got.status_code, 200, (sid, f["path"]))
                self.assertEqual(sha(got.content), f["sha256"], (sid, f["path"]))
                self.assertEqual(got.headers["x-content-sha256"], f["sha256"])


if __name__ == "__main__":
    unittest.main()
