# -*- coding: utf-8 -*-
"""재단 패턴 3단계(기준점 끌어서 다시 그레이딩)·5단계(고른 것만 내려받기 · 공장 보낸 판 잠금) + 2단계 남은 작은 것 시험

  [진짜 엔진 — 약 2분, GRADER_SKIP_ENGINE_TESTS=1 이면 건너뜀]
  ① v1(서버 엔진으로 만든 가스 웜업 상의)의 규칙표를 읽는다(view 에서 — 출처 "view")
  ② 완료 기준: 소매 겨드랑이 규칙만 바꾸면 미리보기 래글런 «빨강» · 저장은 거절 / 몸판 겨드랑이도 같이 바꾸면 «초록»
  ③ 저장하면 v2 — v1 은 지문 그대로 · v2 는 rules.json(넘긴 표 그대로) · 창고에 rules 물건 · 다시 읽으면 출처 "stored"
  ④ 5단계: 고른 것만 ZIP — v1 사이즈 S DXF 를 엔진 없이(stizshop tests/dxfcheck.py) 재면 골든과 같다(독립 검산)
           v2 는 소매·몸판만 바뀌고 나머지 조각은 v1 과 같다 · 잠근 v2 는 미리보기·저장 409
  [가짜로 빠르게]
  ⑤ 잠금: 직원 403 · 두 번 409 · 창고 lock 물건 · 재배포(디스크 비움) 뒤 복원해도 잠금 유지 · 목록에 «공장 보냄»
  ⑥ 내려받기 고르기: 형식·사이즈 · 잘못된 형식 400 · 없는 것 404
  ⑦ HeavyGate 상한: 합성이 안 끝나면 엔진 작업 error(한국어) · 대기 표시 풀림 · 뒤에 선 합성이 다시 돈다
     합성이 엔진을 기다리는 동안 작업 stage_ko «재단 패턴 작업이 끝나기를 기다림»
  ⑧ 일꾼 환경: PYTHONSTARTUP·PYTHONPATH·LC_ 아무거나 는 안 넘어가고 PYTHONIOENCODING 은 넘어간다
  ⑨ 서버 콘솔이 cp949 여도 «−» 로그 한 줄에 죽지 않는다 · 결과에 view/zip 이 없으면 한국어 오류
실행(저장소 루트): python -m unittest tests.test_cad_regrade -v
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_cad import make_bundle  # noqa: E402
from test_cad_rebuild import _Base, FakeEngine, STIZ_ENGINE, SKIP, SID, ADMIN, STAFF  # noqa: E402

sha = lambda b: hashlib.sha256(b).hexdigest()
SIZES = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


def step_change(base, piece, point, dy, dx=0.0):
    """«사이즈 한 칸 이동량» 을 바꾼 칸들(화면 «한 칸 비례» 와 같은 규칙) — 2XL 에서 n 칸이면 n 배"""
    out = {}
    for s in SIZES:
        if s == "2XL":
            continue
        n = SIZES.index(s) - SIZES.index("2XL")
        b = base[piece][point][s]
        out[s] = [b[0] + dx * n, b[1] + dy * n]
    return {piece: {point: out}}


def merge(*chs):
    out = {}
    for c in chs:
        for pc, pts in c.items():
            for k, bys in pts.items():
                out.setdefault(pc, {}).setdefault(k, {}).update(bys)
    return out


class _Jobs:
    def wait_job(self, job_id, limit=600):
        t0 = time.time()
        while time.time() - t0 < limit:
            j = self.client.get(f"/api/cad/jobs/{job_id}", headers={"Authorization": ADMIN}).json()
            if j.get("status") in ("done", "error"):
                return j
            time.sleep(0.3)
        self.fail("작업이 끝나지 않음")


@unittest.skipIf(SKIP, "GRADER_SKIP_ENGINE_TESTS=1")
class CadRegradeEngine(_Base, _Jobs):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        vend = os.path.join(ROOT, "vendor", "pattern_engine")
        sys.path.insert(0, vend)
        import importlib
        cls.svc = importlib.import_module("service")
        # v1 = 서버 엔진(사본)으로 만든 상의 — 그레이딩 시트(사이즈별 DXF)는 있고 AAMA 는 없이(시간 절약)
        res = cls.svc.rebuild(os.path.join(cls.tmp, "v1"), groups=["top"], aama=False)
        s = res["styles"][SID]
        cls.v1_view, cls.v1_zip = open(s["view"], "rb").read(), open(s["zip"], "rb").read()
        r = cls.upload(cls.v1_view, cls.v1_zip, headers={"Authorization": ADMIN})
        assert r.status_code == 201, r.text
        cls.rules_v1 = cls.client.get(f"/api/cad/styles/{SID}/v/1/rules", headers={"Authorization": ADMIN}).json()
        cls.done, cls.ids = {}, {}

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def post(self, url, body, tok=ADMIN):
        return self.client.post(url, json=body, headers={"Authorization": tok})

    def job(self, key, url, body):
        if key not in self.done:
            r = self.post(url, body)
            self.assertEqual(r.status_code, 202, r.text)
            self.ids[key] = r.json()["job_id"]
            self.done[key] = self.wait_job(self.ids[key])
        return self.done[key]

    @property
    def sleeve(self):
        b = self.rules_v1["rules"]
        return merge(step_change(b, "소매", "겨드랑이앞", 1.0), step_change(b, "소매", "겨드랑이뒤", 1.0))

    @property
    def both(self):
        b = self.rules_v1["rules"]       # 몸판 래글런은 소매보다 눕혀져 있어 세로로 1.17배 움직여야 길이가 같이 변한다
        return merge(self.sleeve, step_change(b, "앞판", "겨드랑이", 1.17), step_change(b, "뒤판", "겨드랑이", 1.17))

    def test_1_rules_read_from_view(self):
        r = self.rules_v1
        self.assertEqual((r["source"], r["group"], r["editable"], r["locked"]), ("view", "top", True, None))
        self.assertEqual(set(r["rules"]), {"뒤판", "앞판", "소매"})
        self.assertEqual(r["rules"]["소매"]["겨드랑이앞"]["2XL"], [0.0, 0.0])
        self.assertIn(["앞판", "앞중심목"], r["lock_x"])
        self.assertEqual(r["frame"]["뒤판"]["겨드랑이"], [["겨드랑이R", 1], ["겨드랑이L", -1]])
        staff = self.client.get(f"/api/cad/styles/{SID}/v/1/rules", headers={"Authorization": STAFF}).json()
        self.assertFalse(staff["editable"])                                        # 직원은 보기만

    def test_2_sleeve_only_red_and_not_saved(self):
        j = self.job("sleeve", f"/api/cad/styles/{SID}/regrade", {"base_version": 1, "rules": self.sleeve})
        self.assertEqual(j["status"], "done", j.get("error"))
        res = j["result"]; mesh = res["mesh"]
        print("\n[미리보기 · 소매만] S:", [(x["key"], x["value"], x["ok"]) for x in mesh["sizes"]["S"]], f"· {res.get('wall_s')}초")
        self.assertFalse(mesh["ok"])
        self.assertEqual(sorted(x["key"] for x in mesh["sizes"]["S"] if x["ok"] is False), ["raglan_back", "raglan_front"])
        self.assertEqual(len(res["changes"]), 14)                                   # 2점 × 7사이즈
        self.assertLessEqual(res["rules_echo_max_mm"], 0.01)
        v = self.client.get(res["view_url"], headers={"Authorization": ADMIN})
        self.assertEqual(v.status_code, 200)
        self.assertEqual(v.json()["style"]["id"], SID)                              # 미리보기 그림을 화면이 가져갈 수 있다
        self.assertEqual(self.client.get(f"/api/cad/styles/{SID}", headers={"Authorization": ADMIN}).json()["versions"], [1])
        # 저장은 바로 거절(엔진을 돌리지 않는다) — 같은 규칙의 미리보기가 빨강 / 미리보기 없이 / 다른 규칙의 미리보기로
        t0 = time.time()
        r = self.post(f"/api/cad/styles/{SID}/versions", {"base_version": 1, "rules": self.sleeve, "preview_job": self.ids["sleeve"]})
        self.assertEqual(r.status_code, 400); self.assertIn("전부 초록이 아니어서", r.json()["detail"])
        self.assertLess(time.time() - t0, 5)
        r = self.post(f"/api/cad/styles/{SID}/versions", {"base_version": 1, "rules": self.sleeve})
        self.assertEqual(r.status_code, 400); self.assertIn("미리보기가 없습니다", r.json()["detail"])
        r = self.post(f"/api/cad/styles/{SID}/versions", {"base_version": 1, "rules": self.both, "preview_job": self.ids["sleeve"]})
        self.assertEqual(r.status_code, 400); self.assertIn("미리보기가 없습니다", r.json()["detail"])
        self.assertEqual(self.client.get(f"/api/cad/styles/{SID}", headers={"Authorization": ADMIN}).json()["versions"], [1])

    def test_3_body_too_green_and_saved_as_v2(self):
        j = self.job("both", f"/api/cad/styles/{SID}/regrade", {"base_version": 1, "rules": self.both})
        self.assertEqual(j["status"], "done", j.get("error"))
        print("\n[미리보기 · 몸판도] S:", [(x["key"], x["value"], x["ok"]) for x in j["result"]["mesh"]["sizes"]["S"]])
        self.assertTrue(j["result"]["mesh"]["ok"])
        js = self.job("both_save", f"/api/cad/styles/{SID}/versions",
                      {"base_version": 1, "rules": self.both, "note": "겨드랑이 1mm/칸", "preview_job": self.ids["both"]})
        self.assertEqual(js["status"], "done", js.get("error"))
        self.assertEqual(js["result"]["version"], 2)
        print(f"[저장] v2 · 일꾼 최고 {js['result'].get('peak_rss_mb')} MB · {js['result'].get('wall_s')}초")
        st = self.client.get(f"/api/cad/styles/{SID}", headers={"Authorization": ADMIN}).json()
        self.assertEqual(st["versions"], [1, 2])
        self.assertEqual(sha(self.client.get(f"/api/cad/styles/{SID}/v/1/view", headers={"Authorization": ADMIN}).content), sha(self.v1_view))
        h2 = st["history"][1]
        self.assertEqual((h2["regraded_from"], h2["has_rules"], h2["rule_changes_count"], h2["note"]), (1, True, 28, "겨드랑이 1mm/칸"))
        self.assertTrue(h2["mesh"]["ok"])
        self.assertEqual(h2["backup"]["ok"], True)
        self.assertIn(f"{SID}/v2/rules", self.store)                               # 규칙표도 창고에(되읽기 확인)
        r2 = self.client.get(f"/api/cad/styles/{SID}/v/2/rules", headers={"Authorization": ADMIN}).json()
        self.assertEqual(r2["source"], "stored")
        want = self.svc.merge_rules(self.rules_v1["rules"], self.both)
        self.assertEqual(self.svc.max_rule_gap(want, r2["rules"]), 0.0)            # 넘긴 표 그대로 보관
        self.assertLessEqual(self.svc.max_rule_gap(want, self.svc.rules_from_view(
            self.client.get(f"/api/cad/styles/{SID}/v/2/view", headers={"Authorization": ADMIN}).json())), 0.01)

    def test_4_export_and_independent_check(self):
        if not os.path.isfile(os.path.join(STIZ_ENGINE, "tests", "dxfcheck.py")):
            self.skipTest("옆 폴더 stizshop 의 dxfcheck 가 없다")
        self.test_3_body_too_green_and_saved_as_v2()
        sys.path.insert(0, os.path.join(STIZ_ENGINE, "tests"))
        from dxfcheck import metrics
        with open(os.path.join(STIZ_ENGINE, "tests", "golden_gas_warmup.json"), encoding="utf-8") as f:
            golden = json.load(f)["graded"]

        def got(ver, size):
            r = self.post(f"/api/cad/styles/{SID}/v/{ver}/export", {"kinds": ["dxf"], "sizes": [size]})
            self.assertEqual(r.status_code, 200, r.text)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            self.assertEqual(sorted(z.namelist()), sorted([f"sizes/{size}/TOP_{size}.dxf", "manifest.json"]))
            p = os.path.join(self.tmp, f"v{ver}_{size}.dxf")
            open(p, "wb").write(z.read(f"sizes/{size}/TOP_{size}.dxf"))
            return metrics(p)
        for size in ("S", "5XL"):
            m1, m2, want = got(1, size), got(2, size), golden[size]["상의"]
            for n in want:                                                         # v1 = 골든(엔진 없이 잰 값)
                self.assertAlmostEqual(m1[n][1], want[n][1], delta=0.05, msg=f"v1 {size} {n} 재봉선 둘레")
                self.assertEqual(m1[n][3:6], want[n][3:6], f"v1 {size} {n}")
            changed = sorted(n for n in want if abs(m2[n][1] - m1[n][1]) > 0.05)
            print(f"\n[독립 검산] {size}: v2 에서 재봉선 둘레가 바뀐 조각 {changed}")
            body = {"BACK", "FRONT L", "FRONT R", "SLEEVE L", "SLEEVE R", "SLEEVE CENTER OVERLAY L", "SLEEVE CENTER OVERLAY R"}
            self.assertLessEqual(set(changed), body)                               # DXF 조각 이름(영문) — 몸판·소매(+소매에서 오리는 덧방)만 바뀐다
            self.assertIn("SLEEVE L", changed); self.assertIn("BACK", changed)
            self.assertEqual(sorted(m2), sorted(m1))
        # 잠그면 고칠 수 없다
        lk = self.post(f"/api/cad/styles/{SID}/v/2/lock", {"note": "공장 1차"})
        self.assertEqual(lk.status_code, 200, lk.text)
        self.assertIn(f"{SID}/v2/lock", self.store)
        for url in (f"/api/cad/styles/{SID}/regrade", f"/api/cad/styles/{SID}/versions"):
            r = self.post(url, {"base_version": 2, "rules": self.both})
            self.assertEqual(r.status_code, 409, r.text)
        rr = self.client.get(f"/api/cad/styles/{SID}/v/2/rules", headers={"Authorization": ADMIN}).json()
        self.assertFalse(rr["editable"]); self.assertEqual(rr["locked"]["note"], "공장 1차")


class CadLockExportFast(_Base, _Jobs):
    """가짜 묶음으로 — 잠금·고른 것만 내려받기·작업 줄의 작은 것들"""

    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        v, zb, cls.members = make_bundle(style_id=SID, sizes=("S", "M"))
        assert cls.upload(v, zb, headers={"Authorization": ADMIN}).status_code == 201

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def post(self, url, body=None, tok=ADMIN):
        return self.client.post(url, json=body or {}, headers={"Authorization": tok} if tok else {})

    def test_export_pick(self):
        r = self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["dxf"], "sizes": ["M"]})
        self.assertEqual(r.status_code, 200, r.text)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        self.assertEqual(sorted(z.namelist()), ["manifest.json", "sizes/M/TOP_M.dxf"])
        self.assertEqual(z.read("sizes/M/TOP_M.dxf"), self.members["sizes/M/TOP_M.dxf"])   # 저장된 그대로
        man = json.loads(z.read("manifest.json"))
        self.assertEqual(man["files"][0]["sha256"], sha(self.members["sizes/M/TOP_M.dxf"]))
        r = self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["dxf", "rul"]})
        self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(r.content)).namelist()),
                         ["aama/GAS_WARMUP_TOP.rul", "manifest.json", "sizes/M/TOP_M.dxf", "sizes/S/TOP_S.dxf"])
        r2 = self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["dxf", "rul"]})
        self.assertEqual(sha(r.content), sha(r2.content))                          # 같은 선택 = 같은 묶음
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["zip"]}).status_code, 400)
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["../x"]}).status_code, 400)
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["a4"]}).status_code, 404)
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["dxf"]}, tok=STAFF).status_code, 200)   # 🔒 직원도
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/v/1/export", {"kinds": ["dxf"]}, tok=None).status_code, 401)

    def test_lock_and_restore(self):
        v, zb, _ = make_bundle(style_id="lock-test-top", sizes=("S",))
        self.assertEqual(self.upload(v, zb, headers={"Authorization": ADMIN}).status_code, 201)
        url = "/api/cad/styles/lock-test-top/v/1/lock"
        self.assertEqual(self.post(url, {}, tok=STAFF).status_code, 403)
        r = self.post(url, {"note": "공장 보냄 1차"})
        self.assertEqual(r.status_code, 200, r.text)
        rec = r.json()["locked"]
        self.assertEqual((rec["locked_by"], rec["note"], rec["version"]), ("tok-admin@stiz.kr", "공장 보냄 1차", 1))
        self.assertEqual(self.post(url, {}).status_code, 409)                      # 두 번 잠그지 않는다
        self.assertIn("lock-test-top/v1/lock", self.store)
        s = self.client.get("/api/cad/styles/lock-test-top", headers={"Authorization": ADMIN}).json()
        self.assertEqual(s["history"][0]["locked"]["locked_at"], rec["locked_at"])
        lst = self.client.get("/api/cad/styles", headers={"Authorization": ADMIN}).json()["styles"]
        self.assertEqual([x["locked_versions"] for x in lst if x["id"] == "lock-test-top"], [[1]])
        # 재배포 흉내 — 디스크를 비우고 로그인 사용자 토큰으로 복원 → 잠금이 살아 있다
        shutil.rmtree(os.path.join(self.cad.cad_dir(), "lock-test-top"))
        self.cad.restore_missing_with_token("tok-admin", force=True)
        s = self.client.get("/api/cad/styles/lock-test-top", headers={"Authorization": ADMIN}).json()
        self.assertEqual(s["history"][0]["locked"]["locked_by"], "tok-admin@stiz.kr")
        self.assertEqual(self.post(url, {}).status_code, 409)

    def test_lock_store_failure_does_not_lock(self):
        v, zb, _ = make_bundle(style_id="lock-fail-top", sizes=("S",))
        self.upload(v, zb, headers={"Authorization": ADMIN})
        with mock.patch.object(self.cad, "_sb_upload", return_value=(False, "status 500")):
            r = self.post("/api/cad/styles/lock-fail-top/v/1/lock", {})
        self.assertEqual(r.status_code, 502)
        self.assertIsNone(self.cad._lock_info("lock-fail-top", 1))                 # 창고에 못 남기면 잠그지 않는다

    def test_regrade_refusals(self):
        fake = FakeEngine()
        with mock.patch.object(self.cad, "load_service", return_value=fake):
            r = self.post(f"/api/cad/styles/{SID}/regrade", {"base_version": 1, "rules": {}}, tok=STAFF)
        self.assertEqual(r.status_code, 403)
        r = self.post("/api/cad/styles/test-style-top/regrade", {"rules": {}})       # 서버에 원본이 없는(다시 만들 수 없는) 스타일
        self.assertIn(r.status_code, (400, 404))
        r = self.post(f"/api/cad/styles/{SID}/regrade", {"base_version": 9, "rules": {}})
        self.assertEqual(r.status_code, 404)
        r = self.post(f"/api/cad/styles/{SID}/regrade", {"base_version": 1, "rules": {}})
        self.assertEqual(r.status_code, 400)                                       # 가짜 묶음은 기준점이 없어 규칙을 못 읽는다
        self.assertIn("규칙을 읽지 못했습니다", r.json()["detail"])
        self.assertEqual(self.client.get("/api/cad/jobs/abcdefabcdef/view", headers={"Authorization": ADMIN}).status_code, 404)


class FakeRegrade:
    """_regrade_thread 를 엔진 없이 — 저장 도중 기준 판이 잠기는 경쟁을 흉내 낸다"""
    STEPS = FakeEngine.STEPS; STEP_KO = FakeEngine.STEP_KO; BASE_SIZE = "2XL"; GRADE_SIZES = SIZES

    def __init__(self, on_run=None):
        self.on_run = on_run

    def regrade(self, work, group, table, full=False, on_step=None, timeout=None, env=None):
        os.makedirs(work, exist_ok=True)
        if self.on_run: self.on_run()
        view, zb, _ = make_bundle(style_id=SID, sizes=("S", "M"))
        vp, zp = os.path.join(work, "view.json"), os.path.join(work, "exports.zip")
        with open(vp, "wb") as f: f.write(view)
        with open(zp, "wb") as f: f.write(zb)
        mesh = {"ok": True, "sizes": {"S": [{"key": "k", "label": "l", "value": 0.0, "target": 0.0, "tol": 0.5, "ok": True}]}}
        return {"styles": {SID: {"view": vp, "zip": zp, "checks_bad": [], "mesh": mesh, "rules_echo_max_mm": 0.0}},
                "font": {"source": "builtin"}, "engine": {"commit": "fake"}, "peak_rss_mb": 1.0}


class VerifyFixes(_Base, _Jobs):
    """검증 지적 고친 것 — 복원(목록 못 읽음·규칙표/잠금 빠짐) · 저장 중 잠금 경쟁 · 판정 못 한 칸 · meta 안 고침 · 묶음에 없는 파일"""

    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def up(self, sid):
        v, zb, _ = make_bundle(style_id=sid, sizes=("S",))
        self.assertEqual(self.upload(v, zb, headers={"Authorization": ADMIN}).status_code, 201)

    def test_restore_keeps_lock_when_list_fails(self):
        self.up("rs-fix-top")
        self.assertEqual(self.client.post("/api/cad/styles/rs-fix-top/v/1/lock", json={}, headers={"Authorization": ADMIN}).status_code, 200)
        with open(os.path.join(self.cad._vdir("rs-fix-top", 1), "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.assertNotIn("locked", meta)                                           # 8 — 디스크 meta 는 그대로
        shutil.rmtree(os.path.join(self.cad.cad_dir(), "rs-fix-top"))
        real = self.cad._sb_list
        with mock.patch.object(self.cad, "_sb_list", side_effect=lambda p, j: None if p == "rs-fix-top/v1/" else real(p, j)):
            self.cad.restore_missing_with_token("tok-admin", force=True)
        self.assertEqual(self.cad._versions_on_disk("rs-fix-top"), [])            # 2 — 목록을 못 읽으면 «잠금 없이» 복원하지 않는다
        self.cad.restore_missing_with_token("tok-admin", force=True)              # 다음 시도에는 정상 복원 + 잠금 유지
        self.assertIsNotNone(self.cad._lock_info("rs-fix-top", 1))

    def test_restore_needs_rules_when_meta_says_so(self):
        self.up("rs-rules-top")
        key = "rs-rules-top/v1/meta"
        meta = json.loads(self.store[key]); meta["rules_sha256"] = "0" * 64        # 창고 meta 가 «규칙표 있음» 이라 말하는데 rules 물건이 없다
        self.store[key] = json.dumps(meta).encode("utf-8")
        shutil.rmtree(os.path.join(self.cad.cad_dir(), "rs-rules-top"))
        self.cad.restore_missing_with_token("tok-admin", force=True)
        self.assertEqual(self.cad._versions_on_disk("rs-rules-top"), [])

    def test_restore_ignores_rules_without_meta_hash(self):
        self.up("rs-norule-top")
        self.store["rs-norule-top/v1/rules"] = b'{"rules": {}}'                    # 7 — meta 가 보증하지 않는 규칙표
        shutil.rmtree(os.path.join(self.cad.cad_dir(), "rs-norule-top"))
        self.cad.restore_missing_with_token("tok-admin", force=True)
        self.assertEqual(self.cad._versions_on_disk("rs-norule-top"), [1])
        self.assertFalse(os.path.exists(os.path.join(self.cad._vdir("rs-norule-top", 1), "rules.json")))

    def test_lock_during_save_is_refused(self):
        if not self.cad._versions_on_disk(SID):
            self.up(SID)
        base = max(self.cad._versions_on_disk(SID))
        before = self.cad._versions_on_disk(SID)

        def lock_now():                                                           # 3 — 엔진이 도는 사이 다른 관리자가 잠갔다
            with open(os.path.join(self.cad._vdir(SID, base), "lock.json"), "w", encoding="utf-8") as f:
                json.dump({"style_id": SID, "version": base}, f)
        from webapp import state
        jid = state.create_job(total=5)
        with mock.patch.object(self.cad, "load_service", return_value=FakeRegrade(lock_now)):
            with self.cad._QUEUE_LOCK:
                self.cad._queue["waiting"] += 1
            self.cad._regrade_thread(jid, SID, base, "top", {}, [{"piece": "소매"}], "tok-admin", "a@stiz.kr", "", False)
        j = state.get_job(jid)
        self.assertEqual(j["status"], "error"); self.assertIn("잠겨", j["error"])
        self.assertEqual(self.cad._versions_on_disk(SID), before)
        os.remove(os.path.join(self.cad._vdir(SID, base), "lock.json"))

    def test_mesh_none_is_not_green(self):
        g = self.cad._mesh_all_green
        row = lambda ok: {"ok": ok}
        self.assertTrue(g({"sizes": {"S": [row(True), row(True)]}}))
        self.assertFalse(g({"sizes": {"S": [row(True), row(None)]}}))               # 6 — 판정 못 한 칸은 저장 안 됨
        self.assertFalse(g({"sizes": {"S": [row(False)]}}))
        self.assertFalse(g({"sizes": {}})); self.assertFalse(g({}))

    def test_export_missing_member_is_404(self):
        self.up("ex-miss-top")
        mp = os.path.join(self.cad._vdir("ex-miss-top", 1), "meta.json")
        with open(mp, encoding="utf-8") as f:
            meta = json.load(f)
        meta["files"].append({"kind": "a4", "size": "2XL", "path": "aama/NOPE.pdf", "sha256": "0" * 64})
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        r = self.client.post("/api/cad/styles/ex-miss-top/v/1/export", json={"kinds": ["a4"]}, headers={"Authorization": ADMIN})
        self.assertEqual(r.status_code, 404); self.assertIn("그 파일이 없습니다", r.json()["detail"])   # 9
        r = self.client.post("/api/cad/styles/ex-miss-top/v/1/export", json={"kinds": ["dxf"]}, headers={"Authorization": ADMIN})
        self.assertEqual(r.status_code, 200)                                       # 4 — 임시 파일로 흘려보내도 내용은 같다
        self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(r.content)).namelist()), ["manifest.json", "sizes/S/TOP_S.dxf"])

    def test_screen_grade_tab_admin_only(self):
        with open(os.path.join(ROOT, "webapp", "static", "screens", "cad.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('$("#gradeTab").classList.toggle("hidden", !(G.rules0 && S.canUpload))', html)   # 1 — 직원에게는 탭 자체를 숨김
        self.assertIn("preview_job: G.preview.job", html)


class SmallItems(unittest.TestCase):
    """2단계 리뷰의 남은 작은 것"""

    def test_heavy_gate_timeout_releases_waiters(self):
        from webapp.state import HeavyGate
        g, log = HeavyGate(), []
        hold, inside = threading.Event(), threading.Event()

        def synth(name, h=None):
            with g.shared_use():
                log.append(name); inside.set(); h and h.wait(5)
        ta = threading.Thread(target=synth, args=("A", hold)); ta.start(); inside.wait(5)
        err = []

        def engine():
            try:
                with g.exclusive_use(timeout=0.3):
                    log.append("E")
            except TimeoutError as e:
                err.append(e)
        te = threading.Thread(target=engine); te.start()
        for _ in range(100):
            if g.snapshot()["waiting_excl"]: break
            time.sleep(0.01)
        tb = threading.Thread(target=synth, args=("B",)); tb.start()               # 엔진 뒤에 선 합성
        te.join(5)
        self.assertTrue(err)                                                       # 엔진은 포기했다
        tb.join(5)
        self.assertEqual(log, ["A", "B"])                                          # 엔진이 포기하자 B 가 깨어나 돌았다(A 가 아직인데도)
        self.assertEqual(g.snapshot()["waiting_excl"], 0)
        hold.set(); ta.join(5)

    def test_engine_job_errors_when_synthesis_never_ends(self):
        from webapp import cad, state
        jid = state.create_job(total=5)
        hold, inside = threading.Event(), threading.Event()

        def synth():
            with state.HEAVY.shared_use():
                inside.set(); hold.wait(10)
        t = threading.Thread(target=synth); t.start(); inside.wait(5)
        tmp = tempfile.mkdtemp(prefix="cad-heavy-")
        try:
            with mock.patch.dict(os.environ, {"GRADER_CAD_HEAVY_WAIT_S": "0.3"}), \
                    mock.patch.object(cad, "load_service", return_value=FakeEngine()), \
                    mock.patch.object(state, "get_jobs_dir", return_value=tmp):
                with cad._QUEUE_LOCK: cad._queue["waiting"] += 1
                cad._rebuild_thread(jid, SID, 1, "top", None, None, "")
            j = state.get_job(jid)
            self.assertEqual(j["status"], "error")
            self.assertIn("합성 작업이", j["error"]); self.assertIn("넘게 끝나지 않아", j["error"])
            self.assertEqual(state.HEAVY.snapshot()["waiting_excl"], 0)
        finally:
            hold.set(); t.join(5); shutil.rmtree(tmp, ignore_errors=True)

    def test_synthesis_job_shows_waiting_for_engine(self):
        from webapp import api, state
        jid = state.create_job(total=1)
        seen = []
        with mock.patch.object(api, "run_job", side_effect=lambda **k: {"summary": {"produced": 1}}):
            with state.HEAVY.exclusive_use():
                t = threading.Thread(target=api._run_job_thread, args=(jid, "p", "d", [], tempfile.gettempdir(), "pdf")); t.start()
                for _ in range(100):
                    seen.append(state.get_job(jid).get("stage_ko"))
                    if seen[-1]: break
                    time.sleep(0.01)
            t.join(5)
        self.assertIn("재단 패턴 작업이 끝나기를 기다림", seen)
        self.assertEqual(state.get_job(jid)["status"], "done")

    def test_env_exact_names(self):
        from webapp import cad
        with mock.patch.dict(os.environ, {"PYTHONSTARTUP": "/evil.py", "PYTHONINSPECT": "1", "PYTHONPATH": "/evil",
                                          "LC_EVIL": "x", "PYTHONIOENCODING": "utf-8", "LC_ALL": "C.UTF-8", "PATTERN_ENGINE_FONT": "f"}):
            env = cad._engine_env()
        for k in ("PYTHONSTARTUP", "PYTHONINSPECT", "LC_EVIL"):
            self.assertNotIn(k, env)
        self.assertEqual(env["PYTHONPATH"], cad.CHILD_GUARD_DIR)                   # 서버의 PYTHONPATH 는 안 넘긴다
        for k in ("PYTHONIOENCODING", "LC_ALL", "PATTERN_ENGINE_FONT"):
            self.assertIn(k, env)

    def test_log_survives_cp949_console(self):
        from webapp import cad
        buf = io.TextIOWrapper(io.BytesIO(), encoding="cp949")
        with mock.patch.object(sys, "stdout", buf):
            cad._log("[cad] 앞 래글런 몸판−소매 → 0.4")                              # «−»·«→» 는 cp949 에 없다
        buf.flush()
        self.assertIn("앞 래글런".encode("cp949"), buf.buffer.getvalue())

    def test_result_without_view_is_korean(self):
        from webapp import cad
        with self.assertRaises(ValueError) as cm:
            cad._result_style({"styles": {SID: {"zip": "/no/such.zip"}}}, SID)
        self.assertIn("화면 자료(view.json)", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
