# -*- coding: utf-8 -*-
"""재단 패턴 «서버에서 다시 만들기» 시험 — F10 2단계 (webapp/cad.py · vendor/pattern_engine/service.py)

  ① 관리자가 POST /api/cad/styles/{id}/v/{ver}/rebuild → 작업 번호(202) → GET /api/cad/jobs/{job} 로 단계가 올라오다 끝
  ② 결과는 «새 버전» (v1 그대로 · v2 생김) · 창고 백업(가짜 창고)·되읽기 통과 · meta 에 rebuilt_from·엔진 판·메모리
  ③ 서버가 만든 view.json 이 stizshop «로컬 명령줄» (옆 폴더 stizshop 의 README 순서 그대로) 결과와 점 0.01mm 안
  ④ 리눅스(Render)처럼 시스템 글꼴이 없을 때도 오류 없이 내장 한중일 글꼴로 만든다(PATTERN_ENGINE_NO_SYSTEM_FONTS=1)
  ⑤ 메모리 최고치(일꾼) < 512MB · 거절: 직원 403 · 원본 없는 스타일 400 · 없는 버전 404 · 모르는 작업 404
  ⑥ (가짜 엔진으로 빠르게) 환경변수 허용 목록 · 검산 실패 거절 · 로그인 남은 시간 · meta 허용 열쇠 · 짧은 오류 문구
     · 결과에 스타일 없음 · 합성↔엔진 순서(HeavyGate) · 일꾼 안전띠(sitecustomize: oom_score_adj·RLIMIT_AS)
  약 90초(엔진을 두 번 — 서버 길과 로컬 명령줄 길을 동시에 돌린다). 건너뛰려면 GRADER_SKIP_ENGINE_TESTS=1
실행(저장소 루트): python -m unittest tests.test_cad_rebuild -v
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from fastapi.testclient import TestClient  # noqa: E402
from test_cad import make_bundle  # noqa: E402

STIZ_ENGINE = os.environ.get("STIZSHOP_ENGINE_DIR") or os.path.join(os.path.dirname(ROOT), "stizshop", "tools", "pattern-engine")
SKIP = os.environ.get("GRADER_SKIP_ENGINE_TESTS") == "1"
SID = "gas-warmup-2026-top"
ADMIN, STAFF = "Bearer tok-admin", "Bearer tok-staff"
sha = lambda b: hashlib.sha256(b).hexdigest()


def local_cli_chain(out):
    """stizshop 로컬 명령줄 — README «쓰는 법» 순서 그대로(옆 폴더 정본 엔진으로). 반환: 상의 view.json 경로"""
    E, F = STIZ_ENGINE, os.path.join(STIZ_ENGINE, "fixtures", "gas-warmup-2026")
    gw, aa = os.path.join(out, "gw"), os.path.join(out, "aama")
    py = lambda *a: subprocess.run([sys.executable, *a], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True)
    py(os.path.join(E, "gas_warmup_build.py"), os.path.join(F, "gas_top_2xl.ai"), os.path.join(F, "gas_bottom_2xl.ai"), os.path.join(gw, "2xl"))
    py(os.path.join(E, "gas_warmup_grade.py"), "--pieces", os.path.join(gw, "2xl", "pieces_after.json"), "--out", os.path.join(gw, "graded"))
    py(os.path.join(E, "gas_warmup_spec.py"), "--pieces", os.path.join(gw, "2xl", "pieces_after.json"),
       "--graded", os.path.join(gw, "graded", "graded.json"), "--out", os.path.join(gw, "spec"))
    py(os.path.join(E, "aama.py"), "--graded", os.path.join(gw, "graded", "graded.json"), "--out", aa)
    py(os.path.join(E, "tile_pdf.py"), os.path.join(aa, "GAS_WARMUP_TOP_2XL_1대1.pdf"), os.path.join(aa, "상의_2XL_A4분할.pdf"))
    py(os.path.join(E, "cad_view.py"), "--src", gw, "--aama", aa, "--out", os.path.join(out, "cad"), "--groups", "top")
    return os.path.join(out, "cad", SID, "view.json")


class _Base(unittest.TestCase):
    @classmethod
    def start_env(cls, require_auth):
        cls.tmp = tempfile.mkdtemp(prefix="cad-rebuild-")
        cls.env = mock.patch.dict(os.environ, {
            "GRADER_CAD_DIR": os.path.join(cls.tmp, "cad"), "GRADER_REQUIRE_AUTH": "1" if require_auth else "0",
            "GRADER_CLEANUP_DISABLED": "1", "SUPABASE_URL": "https://example.invalid" if require_auth else "",
            "SUPABASE_PUBLISHABLE_KEY": "pub-test" if require_auth else "",
            "PATTERN_ENGINE_NO_SYSTEM_FONTS": "1",                                   # ④ 리눅스 흉내 — 맑은 고딕을 못 쓰게
            "PATTERN_ENGINE_CACHE": os.path.join(cls.tmp, "fontcache")})
        cls.env.start()
        from webapp import auth, cad, state
        cls.cad, cls.state = cad, state
        cad._last_restore["at"] = 0.0
        cls.jobs = os.path.join(cls.tmp, "jobs"); os.makedirs(cls.jobs)
        cls.patches = [mock.patch.object(state, "get_jobs_dir", return_value=cls.jobs)]
        if require_auth:
            roles = cls.roles = {"tok-admin": "admin", "tok-staff": None}
            cls.patches.append(mock.patch.object(auth, "_introspect", side_effect=lambda t: {"user_id": t, "email": t + "@stiz.kr", "role": roles[t]}
                                                 if t in roles else (_ for _ in ()).throw(auth.HTTPException(status_code=401, detail="x"))))
            cls.store = {}

            def up(key, data, ctype, jwt):
                if roles.get(jwt) != "admin": return False, "status 403"
                if key in cls.store: return False, "status 409"
                cls.store[key] = data; return True, "ok"

            def lst(prefix, jwt):
                names = set()
                for k in cls.store:
                    if k.startswith(prefix): names.add(k[len(prefix):].split("/")[0] + ("" if "/" not in k[len(prefix):] else "/"))
                return [{"name": n.rstrip("/"), "id": None if n.endswith("/") else "f"} for n in sorted(names)]
            cls.patches += [mock.patch.object(cad, "_sb_upload", side_effect=up),
                            mock.patch.object(cad, "_sb_download", side_effect=lambda k, j: cls.store.get(k) if j in roles else None),
                            mock.patch.object(cad, "_sb_list", side_effect=lst)]
            auth._TOKEN_CACHE.clear()
        for p in cls.patches: p.start()
        from webapp.main import app
        cls.client = TestClient(app)

    @classmethod
    def stop_env(cls):
        for p in reversed(cls.patches): p.stop()
        cls.env.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def upload(cls, view, zb, headers=None):
        return cls.client.post("/api/cad/styles", files={"view": ("view.json", view, "application/json"),
                                                        "exports": ("exports.zip", zb, "application/zip")}, headers=headers or {})


@unittest.skipIf(SKIP, "GRADER_SKIP_ENGINE_TESTS=1")
class CadRebuild(_Base):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        view1, zb1, _ = make_bundle(style_id=SID, sizes=("S", "M"))               # v1 = 작은 가짜(다시 만들기는 «어느 버전 기준» 표시만 쓴다)
        r = cls.upload(view1, zb1, headers={"Authorization": ADMIN})
        assert r.status_code == 201, r.text
        cls.v1_sha = sha(view1)
        # ③ 기준 — 옆 폴더 stizshop 로컬 명령줄을 서버 작업과 «동시에» 돌린다(시간 절약)
        cls.ref, cls.ref_err = None, None
        if os.path.isfile(os.path.join(STIZ_ENGINE, "cad_view.py")):
            def ref():
                try: cls.ref = local_cli_chain(os.path.join(cls.tmp, "local"))
                except Exception as e: cls.ref_err = f"{e}\n{getattr(e, 'stderr', '')[-2000:]}"
            cls.ref_t = threading.Thread(target=ref); cls.ref_t.start()
        else:
            cls.ref_t = None
        t0 = time.time()
        r = cls.client.post(f"/api/cad/styles/{SID}/v/1/rebuild", json={"note": "시험 다시 만들기"}, headers={"Authorization": ADMIN})
        assert r.status_code == 202, r.text
        cls.start = r.json(); cls.stages, cls.final = [], None
        while time.time() - t0 < 900:
            j = cls.client.get(f"/api/cad/jobs/{cls.start['job_id']}", headers={"Authorization": ADMIN}).json()
            if not cls.stages or cls.stages[-1] != j.get("stage"): cls.stages.append(j.get("stage"))
            if j.get("status") in ("done", "error"): cls.final = j; break
            time.sleep(0.3)
        cls.server_s = round(time.time() - t0, 1)
        if cls.ref_t: cls.ref_t.join(900)
        vend = os.path.join(ROOT, "vendor", "pattern_engine")
        sys.path.insert(0, vend)
        import importlib
        cls.svc = importlib.import_module("service")                               # 견주기 함수(compare_views)·메모리 함수만 쓴다
        with open(os.path.join(vend, "ENGINE_VERSION.json"), encoding="utf-8") as f: cls.ev = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def get(self, url):
        return self.client.get(url, headers={"Authorization": ADMIN})

    def test_1_job_done_with_progress(self):
        self.assertIsNotNone(self.final, "15분 안에 끝나지 않음")
        self.assertEqual(self.final["status"], "done", self.final.get("error"))
        self.assertEqual(self.final["result"]["version"], 2)
        for s in ("build", "grade", "view", "done"):
            self.assertIn(s, self.stages)                                          # 진행률 — 단계가 차례로 보인다
        self.assertEqual(self.final["done"], self.final["total"])
        print(f"\n[서버 다시 만들기] {self.server_s}초 · 단계 {self.stages}")

    def test_2_new_version_old_kept(self):
        s = self.get(f"/api/cad/styles/{SID}").json()
        self.assertEqual(s["versions"], [1, 2])
        self.assertEqual(sha(self.get(f"/api/cad/styles/{SID}/v/1/view").content), self.v1_sha)   # v1 은 손대지 않았다
        h2 = s["history"][1]
        self.assertEqual(h2["rebuilt_from"], 1)
        self.assertEqual(h2["engine_run"]["font"], "builtin")                      # ④ 대체 글꼴로 만들었다(오류 없이)
        self.assertTrue((h2["source"] or {}).get("commit", "").startswith(self.ev["commit_short"]))
        self.assertEqual(h2["backup"]["ok"], True)                                 # 가짜 창고에 올라가고 되읽기 통과
        self.assertIn(f"{SID}/v2/view", self.store)
        self.assertEqual(h2["note"], "시험 다시 만들기")

    def test_3_same_as_stizshop_local(self):
        if self.ref_t is None: self.skipTest("옆 폴더 stizshop 엔진이 없다")
        self.assertIsNone(self.ref_err, self.ref_err)
        with open(self.ref, encoding="utf-8") as f: ref = json.load(f)
        got = self.get(f"/api/cad/styles/{SID}/v/2/view").json()
        c = self.svc.compare_views(ref, got)
        print(f"\n[견주기] 서버 v2 ↔ stizshop 로컬 명령줄: 점 {c['points']}개 · 최대 차 {c['max_mm']}mm · 구조 차 {c['diffs']}")
        self.assertEqual(c["diffs"], [])
        self.assertLessEqual(c["max_mm"], 0.01)
        self.assertGreater(c["points"], 1000)

    def test_4_downloads_match_fingerprints(self):
        meta = self.get(f"/api/cad/styles/{SID}").json()["history"][1]
        z = self.get(f"/api/cad/styles/{SID}/v/2/files/zip")
        self.assertEqual(sha(z.content), meta["zip_sha256"])
        for kind, size in (("dxf", "S"), ("pdf", "5XL"), ("rul", None), ("a4", None)):
            r = self.get(f"/api/cad/styles/{SID}/v/2/files/{kind}" + (f"?size={size}" if size else ""))
            self.assertEqual(r.status_code, 200, (kind, r.text[:200]))
            f = [x for x in meta["files"] if x["kind"] == kind and (size is None or x["size"] == size)][0]
            self.assertEqual(sha(r.content), f["sha256"])

    def test_5_memory(self):
        run = self.final["result"]
        mb = run.get("peak_rss_mb")
        here = self.svc.peak_rss_mb()
        print(f"\n[메모리] 엔진 일꾼 최고 {mb} MB · 이 시험 프로세스(서버 역할) 최고 {here} MB · 엔진 단계별 초 {run.get('timings_s')}")
        self.assertIsNotNone(mb)
        self.assertLess(mb, 512)

    def test_6_work_folder_cleaned(self):
        self.assertEqual([n for n in os.listdir(self.jobs) if n.startswith("web_cad_")], [])


class CadRebuildRefusals(_Base):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def test_refusals(self):
        v, zb, _ = make_bundle(style_id="test-style-top")
        self.assertEqual(self.upload(v, zb, headers={"Authorization": ADMIN}).status_code, 201)
        v, zb, _ = make_bundle(style_id=SID)
        self.assertEqual(self.upload(v, zb, headers={"Authorization": ADMIN}).status_code, 201)
        post = lambda url, h: self.client.post(url, json={}, headers={"Authorization": h} if h else {})
        self.assertEqual(post(f"/api/cad/styles/{SID}/v/1/rebuild", None).status_code, 401)
        self.assertEqual(post(f"/api/cad/styles/{SID}/v/1/rebuild", STAFF).status_code, 403)         # 직원은 못 누른다
        r = post("/api/cad/styles/test-style-top/v/1/rebuild", ADMIN)
        self.assertEqual(r.status_code, 400); self.assertIn("서버에서 다시 만들 수 없습니다", r.json()["detail"])
        self.assertEqual(post(f"/api/cad/styles/{SID}/v/9/rebuild", ADMIN).status_code, 404)
        self.assertEqual(self.client.get("/api/cad/jobs/abcdefabcdef", headers={"Authorization": ADMIN}).status_code, 404)
        self.assertEqual(self.client.get("/api/cad/jobs/../x", headers={"Authorization": ADMIN}).status_code, 404)

    def test_queue_limit(self):
        """줄이 가득 차면(3건) 429 — 실제 엔진을 돌리지 않게 줄 수만 채워 본다"""
        v, zb, _ = make_bundle(style_id=SID)
        self.upload(v, zb, headers={"Authorization": ADMIN})
        with mock.patch.dict(self.cad._queue, {"waiting": self.cad.REBUILD_QUEUE_MAX}):
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/rebuild", json={}, headers={"Authorization": ADMIN})
        self.assertEqual(r.status_code, 429)

    def test_engine_missing_is_503(self):
        v, zb, _ = make_bundle(style_id=SID)
        self.upload(v, zb, headers={"Authorization": ADMIN})
        with mock.patch.dict(os.environ, {"GRADER_PATTERN_ENGINE_DIR": os.path.join(self.tmp, "없음")}):
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/rebuild", json={}, headers={"Authorization": ADMIN})
        self.assertEqual(r.status_code, 503)


def fake_jwt(exp):
    """서명 없는 JWT 모양 토큰 — 서버는 남은 시간만 읽는다(검증은 가짜 _introspect 가 한다)"""
    import base64
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'none'})}.{b({'exp': int(exp), 'sub': 'x'})}.sig"


class FakeEngine:
    """진짜 엔진 대신 — 작은 묶음(make_bundle)을 «엔진 결과» 처럼 내놓는다. 상황(mode)을 바꿔 가며 서버 쪽 처리만 본다"""
    STEPS = ["build", "grade", "spec", "aama", "view"]
    STEP_KO = {k: k for k in STEPS}
    REBUILDABLE = {SID: "top"}

    def __init__(self, mode="ok"):
        self.mode, self.envs = mode, []

    def rebuild(self, work, groups=None, on_step=None, timeout=None, env=None):
        self.envs.append(env)
        for i, n in enumerate(self.STEPS, 1):
            on_step and on_step(i, len(self.STEPS), n)
        if self.mode == "crash":
            raise RuntimeError("엔진이 실패했습니다(종료 코드 1). 마지막 출력:\nTraceback (most recent call last):\n  File \"/app/secret/path.py\"\nKeyError: 'x'")
        if self.mode == "oom":
            raise RuntimeError("엔진이 실패했습니다(종료 코드 -9). 마지막 출력:\n(없음)")
        os.makedirs(work, exist_ok=True)
        view, zb, _ = make_bundle(style_id=SID, sizes=("S", "M"))
        vp, zp = os.path.join(work, "view.json"), os.path.join(work, "exports.zip")
        open(vp, "wb").write(view); open(zp, "wb").write(zb)
        styles = {SID: {"group": "top", "view": vp, "zip": zp, "checks_bad": []}}
        if self.mode == "checks_bad":
            styles[SID]["checks_bad"] = [["S", "앞 래글런 몸판−소매", 0.4, 0.0, False]]
        if self.mode == "no_style":
            styles = {"gas-warmup-2026-bottom": styles[SID]}
        return {"styles": styles, "font": {"source": "builtin", "path": "/tmp/x.ttf"}, "engine": {"commit": "fake"},
                "peak_rss_mb": 12.0, "timings_s": {"total": 0.1}, "wall_s": 0.1}


class CadRebuildFast(_Base):
    """가짜 엔진으로 서버 쪽 처리만 — 몇 초"""

    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        v, zb, _ = make_bundle(style_id=SID)
        assert cls.upload(v, zb, headers={"Authorization": ADMIN}).status_code == 201

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def run_fake(self, mode, token=ADMIN):
        fake = FakeEngine(mode)
        with mock.patch.object(self.cad, "load_service", return_value=fake):
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/rebuild", json={}, headers={"Authorization": token})
            if r.status_code != 202:
                return r, None, fake
            for _ in range(200):
                j = self.client.get(f"/api/cad/jobs/{r.json()['job_id']}", headers={"Authorization": ADMIN}).json()
                if j["status"] in ("done", "error"):
                    return r, j, fake
                time.sleep(0.05)
        self.fail("가짜 작업이 끝나지 않음")

    def versions(self):
        return self.client.get(f"/api/cad/styles/{SID}", headers={"Authorization": ADMIN}).json()["versions"]

    # 1 — 환경변수 허용 목록
    def test_env_allowlist_hides_secrets_in_real_child(self):
        secrets = {"ANTHROPIC_API_KEY": "sk-fake", "SUPABASE_SECRET_KEY": "s-fake", "GRADER_REQUIRE_AUTH": "1",
                   "GDRIVE_SA_JSON": "{}", "AWS_SECRET_ACCESS_KEY": "a", "OPENAI_API_KEY": "o", "PATTERN_ENGINE_FONT": ""}
        with mock.patch.dict(os.environ, secrets):
            env = self.cad._engine_env()
        code = ("import os,sys,json; m=sys.modules.get('sitecustomize'); "
                "print(json.dumps({'keys': sorted(os.environ), 'guard': os.environ.get('GRADER_ENGINE_GUARD'), "
                "'site': getattr(m, '__file__', None)}))")
        out = json.loads(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout)
        for k in ("ANTHROPIC_API_KEY", "SUPABASE_SECRET_KEY", "GRADER_REQUIRE_AUTH", "GDRIVE_SA_JSON", "AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY"):
            self.assertNotIn(k, out["keys"], k)                                # 가짜 비밀이 일꾼에서 안 보인다
        self.assertIn("PATTERN_ENGINE_FONT", out["keys"])                     # 엔진 설정은 넘어간다
        self.assertTrue(any(k.upper() == "PATH" for k in out["keys"]))
        self.assertTrue(out["site"] and out["site"].replace("\\", "/").endswith("webapp/engine_child/sitecustomize.py"), out["site"])
        self.assertTrue(out["guard"])                                          # 안전띠가 일꾼 안에서 읽혔다(윈도우는 skipped 표시)

    # 2 — 검산 실패 결과 거절
    def test_checks_bad_is_rejected(self):
        before = self.versions()
        _, j, _ = self.run_fake("checks_bad")
        self.assertEqual(j["status"], "error")
        self.assertIn("검산이 맞지 않아 저장하지 않았습니다", j["error"])
        self.assertEqual(self.versions(), before)

    # 5 — 로그인 남은 시간
    def test_token_near_expiry_is_refused_before_queue(self):
        tok = fake_jwt(time.time() + 120); self.roles[tok] = "admin"
        r, _, _ = self.run_fake("ok", token="Bearer " + tok)
        self.assertEqual(r.status_code, 401)
        self.assertIn("다시 로그인", r.json()["detail"])

    def test_backup_auth_failure_says_relogin(self):
        tok = fake_jwt(time.time() + 3600); self.roles[tok] = "admin"
        before = self.versions()
        with mock.patch.object(self.cad, "_sb_upload", return_value=(False, "status 401")):
            _, j, _ = self.run_fake("ok", token="Bearer " + tok)
        self.assertEqual(j["status"], "error")
        self.assertIn("다시 로그인", j["error"])
        self.assertEqual(self.versions(), before)                              # 반쯤 넣은 버전은 남지 않는다

    # 6 — meta 허용 열쇠
    def test_meta_extra_only_allowed_keys(self):
        v, zb, _ = make_bundle(style_id=SID)
        vv = self.cad.validate_upload(v, zb)
        code, c = self.cad.store_version(vv, v, zb, jwt="tok-admin", uploaded_by="a@stiz.kr",
                                         extra={"version": 999, "view_sha256": "가짜", "rebuilt_from": 1, "evil": "x"})
        self.assertEqual(code, 201)
        meta = self.cad._read_meta(SID, c["version"])
        self.assertNotEqual(meta["version"], 999)
        self.assertEqual(meta["view_sha256"], sha(v))
        self.assertEqual(meta["rebuilt_from"], 1)
        self.assertNotIn("evil", meta)

    # 7 — 화면에는 짧은 요약만
    def test_error_message_is_short(self):
        _, j, _ = self.run_fake("crash")
        self.assertEqual(j["status"], "error")
        self.assertIn("엔진이 실패했습니다", j["error"])
        for leak in ("Traceback", "/app/secret", "KeyError", "마지막 출력"):
            self.assertNotIn(leak, j["error"])
        _, j, _ = self.run_fake("oom")
        self.assertIn("메모리 부족일 수 있음", j["error"])

    # 8 — 엔진이 그 스타일을 못 만들었을 때
    def test_missing_style_in_result_is_korean(self):
        _, j, _ = self.run_fake("no_style")
        self.assertEqual(j["status"], "error")
        self.assertIn("엔진 결과에 이 스타일이 없습니다", j["error"])
        self.assertNotIn("KeyError", j["error"])

    def test_ok_path_and_me(self):
        before = self.versions()
        _, j, fake = self.run_fake("ok")
        self.assertEqual(j["status"], "done", j.get("error"))
        self.assertEqual(self.versions(), before + [j["result"]["version"]])
        self.assertEqual(j["result"]["font_name"], "Droid Sans Fallback (서버 내장)")
        self.assertNotIn("SUPABASE_PUBLISHABLE_KEY", fake.envs[0])            # 실제로 넘긴 환경에도 열쇠 없음
        me = self.client.get("/api/cad/me", headers={"Authorization": ADMIN}).json()
        self.assertIn(SID, me["rebuildable"])


class HeavyOrder(unittest.TestCase):
    """3 — 합성(shared) ↔ 엔진(exclusive) 순서: 엔진은 돌던 합성이 끝나길 기다리고, 기다리기 시작하면 새 합성은 엔진 뒤로"""

    def test_gate_order(self):
        from webapp.state import HeavyGate
        g, log = HeavyGate(), []
        a_in, a_go, e_go = threading.Event(), threading.Event(), threading.Event()

        def synth(name, hold=None, started=None):
            with g.shared_use():
                log.append(name + "+"); started and started.set(); hold and hold.wait(5); log.append(name + "-")

        def engine():
            with g.exclusive_use():
                log.append("E+"); e_go.wait(5); log.append("E-")
        ta = threading.Thread(target=synth, args=("A", a_go, a_in)); ta.start(); a_in.wait(5)
        te = threading.Thread(target=engine); te.start()
        for _ in range(100):
            if g.snapshot()["waiting_excl"]: break
            time.sleep(0.01)
        tb = threading.Thread(target=synth, args=("B",)); tb.start(); time.sleep(0.1)
        self.assertEqual(log, ["A+"])                                          # 엔진은 A 를 기다리고, B 는 엔진 뒤에 섰다
        a_go.set(); time.sleep(0.1)
        self.assertEqual(log, ["A+", "A-", "E+"])                              # A 가 끝나자 엔진 — B 는 아직
        e_go.set(); ta.join(5); te.join(5); tb.join(5)
        self.assertEqual(log, ["A+", "A-", "E+", "E-", "B+", "B-"])

    def test_synthesis_thread_waits_for_engine(self):
        """실제 합성 작업 함수(api._run_job_thread)가 엔진이 도는 동안 run_job 을 시작하지 않는다"""
        from webapp import api, state
        called = threading.Event()
        jid = state.create_job(total=1)
        with mock.patch.object(api, "run_job", side_effect=lambda **k: (called.set(), {"summary": {"produced": 1}})[1]):
            with state.HEAVY.exclusive_use():
                t = threading.Thread(target=api._run_job_thread, args=(jid, "p", "d", [], tempfile.gettempdir(), "pdf")); t.start()
                time.sleep(0.2)
                self.assertFalse(called.is_set())
            t.join(5)
        self.assertTrue(called.is_set())
        self.assertEqual(state.get_job(jid)["status"], "done")


class ChildGuard(unittest.TestCase):
    """3 — 일꾼 안전띠(sitecustomize)의 리눅스 갈래를 흉내 내 본다(윈도우에서도): oom_score_adj 1000 · RLIMIT_AS"""

    def test_linux_branch(self):
        import builtins, runpy, types
        path = os.path.join(ROOT, "webapp", "engine_child", "sitecustomize.py")
        written, limits = {}, {}
        fake_res = types.SimpleNamespace(RLIMIT_AS=9, RLIM_INFINITY=-1, getrlimit=lambda k: (-1, -1),
                                         setrlimit=lambda k, v: limits.__setitem__(k, v))
        real_open = builtins.open

        class W:
            def __init__(self, p): self.p = p
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def write(self, s): written[self.p] = s
        fopen = lambda p, *a, **k: W(p) if p == "/proc/self/oom_score_adj" else real_open(p, *a, **k)
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(sys.modules, {"resource": fake_res}), \
                mock.patch.object(builtins, "open", fopen), \
                mock.patch.dict(os.environ, {"GRADER_ENGINE_LIMIT_AS_MB": "1024", "GRADER_ENGINE_OOM_ADJ": "1000"}):
            runpy.run_path(path)
            guard = os.environ.get("GRADER_ENGINE_GUARD")
        self.assertEqual(written, {"/proc/self/oom_score_adj": "1000"})       # 메모리가 모자라면 일꾼부터
        self.assertEqual(limits, {9: (1024 * 2 ** 20, -1)})                   # 주소 공간 상한
        self.assertIn("rlimit_as_mb=1024", guard)

    def test_default_limit_reasoned(self):
        from webapp import cad
        self.assertGreaterEqual(cad.ENGINE_AS_LIMIT_MB_DEFAULT, 775)          # 검증이 잰 예약 775MB 보다 작으면 시작부터 죽는다
        self.assertEqual(cad._engine_env()["GRADER_ENGINE_LIMIT_AS_MB"], str(cad.ENGINE_AS_LIMIT_MB_DEFAULT))


if __name__ == "__main__":
    unittest.main()
