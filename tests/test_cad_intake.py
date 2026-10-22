# -*- coding: utf-8 -*-
"""패턴 의뢰 → 패턴 자동 제작 + S~3XL 그레이딩 시험 — webapp/cad.py POST /api/cad/intake/{id}/build (2026-10-22)

  ① 직원이 누르면 만들기만 한다 — 창고에 아무것도 안 쓰고, 의뢰 data.build 에 확인표를 붙인다 · 처음엔 기준 사이즈만
  ② 관리자 — 기준 사이즈만 «검토 대기» v1 · 사이즈를 골라 다시 누르면 v2(기준 + 고른 사이즈, ※ 가정 증분)
  ⑤ 실물이 L 인 의뢰는 L 이 기준(의뢰 값 그대로)
  ③ 거절은 한국어 — 번호 형식 400 · 없는 의뢰 404 · 작성 중·휴지통 409 · 만드는 중 409 · 다른 옷(엔진 거절)은 작업 실패 + 의뢰에 오류 기록
  의뢰 표(Supabase REST)는 가짜(_intake_rest)로 — RLS 흉내: 직원은 자기 의뢰만 고친다
실행(저장소 루트): GRADER_CLEANUP_DISABLED=1 PYTHONIOENCODING=utf-8 python -m unittest tests.test_cad_intake -v
"""
import copy
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_cad_rebuild import _Base, SKIP, ADMIN, STAFF  # noqa: E402
from test_cad_import import _Jobs  # noqa: E402

FIX = os.path.join(ROOT, "vendor", "pattern_engine", "tests", "fixtures", "intake", "PI-261022-001.json")
SID = "rugby-jersey-pi-261022-001"


class _Resp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body

    def json(self):
        return self._body


@unittest.skipIf(SKIP, "GRADER_SKIP_ENGINE_TESTS=1")
class CadIntake(_Base, _Jobs):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        with open(FIX, encoding="utf-8") as f:
            base = json.load(f)
        base.update(created_by="tok-staff", updated_at="2026-10-22T09:23:42.338225+00:00", deleted_at=None)
        cls.rows = {}

        def add(rid, **kw):
            r = copy.deepcopy(base); r["id"] = rid; r.update(kw); cls.rows[rid] = r
        cls.ID = base["id"]; add(cls.ID)
        cls.DRAFT = "00000000-0000-4000-8000-000000000001"; add(cls.DRAFT, status="draft")
        cls.TRASH = "00000000-0000-4000-8000-000000000002"; add(cls.TRASH, deleted_at="2026-10-22T10:00:00+00:00")
        cls.OTHER = "00000000-0000-4000-8000-000000000003"; add(cls.OTHER, parts=["neck:round_rib", "sleeve:raglan", "length:short"])
        cls.LBASE = "00000000-0000-4000-8000-000000000004"; add(cls.LBASE, size_label="L", code="PI-261022-009")
        cls.patches.append(mock.patch.object(cls.cad, "_intake_rest", side_effect=cls.fake_rest)); cls.patches[-1].start()

    @classmethod
    def fake_rest(cls, method, query, jwt, body=None, prefer=None):
        q = dict(kv.split("=", 1) for kv in query.split("&"))
        rid = q["id"][3:]
        row = cls.rows.get(rid)
        tok = (jwt or "").replace("Bearer ", "")
        if method == "GET":
            return _Resp(200, [copy.deepcopy(row)] if row else [])
        if not row:
            return _Resp(200, [])
        if tok != "tok-admin" and (row["created_by"] != tok or row["status"] == "reviewed"):
            return _Resp(200, [])                                             # RLS — 고칠 수 없는 줄은 0줄
        from urllib.parse import unquote
        if unquote(q.get("updated_at", "eq.")[3:]) != row["updated_at"]:
            return _Resp(200, [])
        row["data"] = body["data"]; row["updated_at"] = row["updated_at"][:-6] + "1+00:00"
        return _Resp(200, [{"id": rid}])

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def build(self, rid, tok, sizes=None):
        return self.client.post(f"/api/cad/intake/{rid}/build", headers={"Authorization": tok},
                                **({"json": {"sizes": sizes}} if sizes is not None else {}))

    def test_1_staff_builds_without_storing(self):
        r = self.build(self.ID, STAFF)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertFalse(r.json()["store"])
        j = self.wait_job(r.json()["job_id"], tok=STAFF)
        self.assertEqual(j["status"], "done", j)
        res = j["result"]
        self.assertFalse(res["stored"]); self.assertIsNone(res["version"]); self.assertTrue(res["saved_to_intake"])
        self.assertEqual(res["sizes"], ["M"]); self.assertEqual(res["base_size"], "M")   # 처음엔 기준 사이즈만
        self.assertIn("3XL", res["available"])
        self.assertEqual(self.store, {})                                     # 창고에 아무것도 안 썼다
        b = self.rows[self.ID]["data"]["build"]
        self.assertEqual(b["status"], "built"); self.assertEqual(b["style_id"], SID)
        self.assertIn("의뢰 화면에서 골라 그레이딩", b["confirm_md"]); self.assertEqual(b["assumed"], [])
        self.assertIn("measures", self.rows[self.ID]["data"])                # 다른 칸은 그대로

    def test_2_admin_stores_review_versions(self):
        for want, pick, sizes in ((1, None, ["M"]), (2, ["S", "L", "XL", "2XL", "3XL"], ["S", "M", "L", "XL", "2XL", "3XL"])):
            r = self.build(self.ID, ADMIN, pick)
            self.assertEqual(r.status_code, 202, r.text)
            self.assertTrue(r.json()["store"])
            j = self.wait_job(r.json()["job_id"])
            self.assertEqual(j["status"], "done", j)
            self.assertEqual(j["result"]["version"], want); self.assertEqual(j["result"]["sizes"], sizes)
            b = self.rows[self.ID]["data"]["build"]
            self.assertEqual((b["status"], b["ver"]), ("stored", want))
        self.assertTrue(any(k.startswith(f"{SID}/v2/") for k in self.store))
        meta = self.cad._read_meta(SID, 2)
        self.assertEqual(meta["intake"]["review"], "pending"); self.assertIn("검토 대기", meta.get("note") or "")
        self.assertIn("※ 소매 길이", self.rows[self.ID]["data"]["build"]["confirm_md"])
        v = self.client.get(f"/api/cad/styles/{SID}/v/2/view", headers={"Authorization": STAFF})
        self.assertEqual(v.status_code, 200, v.text[:300])
        self.assertEqual(v.json()["style"]["sizes"], ["S", "M", "L", "XL", "2XL", "3XL"])

    def test_3_refusals_korean(self):
        for rid, code in (("not-a-uuid", 400), ("00000000-0000-4000-8000-0000000000ff", 404), (self.DRAFT, 409), (self.TRASH, 409)):
            r = self.build(rid, STAFF)
            self.assertEqual(r.status_code, code, (rid, r.text))
            self.assertRegex(r.json()["detail"], "[가-힣]")
        for bad in (["M", "<x>"], "M", ["M"] * 14):
            r = self.build(self.ID, STAFF, bad)
            self.assertEqual(r.status_code, 400, (bad, r.text)); self.assertRegex(r.json()["detail"], "[가-힣]")
        self.cad._INTAKE_BUILDING.add(self.ID)
        try:
            r = self.build(self.ID, STAFF)
            self.assertEqual(r.status_code, 409); self.assertIn("만드는 중", r.json()["detail"])
        finally:
            self.cad._INTAKE_BUILDING.discard(self.ID)

    def test_4_other_garment_fails_with_reason(self):
        r = self.build(self.OTHER, STAFF)
        self.assertEqual(r.status_code, 202, r.text)
        j = self.wait_job(r.json()["job_id"], tok=STAFF)
        self.assertEqual(j["status"], "error")
        self.assertRegex(j["error"], "[가-힣]")
        self.assertEqual(self.rows[self.OTHER]["data"]["build"]["status"], "error")
        self.assertFalse(any(n.startswith("web_cadintake_") and os.listdir(os.path.join(self.jobs, n)) not in ([], ["engine.log"])
                             for n in os.listdir(self.jobs)))                # 실패한 작업 폴더는 engine.log 만 남는다

    def test_5_sample_L_is_base(self):
        r = self.build(self.LBASE, STAFF, ["M", "XL"])
        self.assertEqual(r.status_code, 202, r.text)
        j = self.wait_job(r.json()["job_id"], tok=STAFF)
        self.assertEqual(j["status"], "done", j)
        self.assertEqual((j["result"]["base_size"], j["result"]["sizes"]), ("L", ["M", "L", "XL"]))
        self.assertIn("기준 사이즈 L", j["result"]["confirm_md"])

    def test_6_unknown_size_fails_korean(self):
        r = self.build(self.LBASE, STAFF, ["5XL"])
        self.assertEqual(r.status_code, 202, r.text)
        j = self.wait_job(r.json()["job_id"], tok=STAFF)
        self.assertEqual(j["status"], "error"); self.assertIn("증분표", j["error"])

    def test_7_staff_rebuild_keeps_stored_version(self):      # test_2 가 v2 로 저장한 뒤 — 직원이 다시 만들어도 «저장된 판» 은 남는다
        r = self.build(self.ID, STAFF, ["L"])
        j = self.wait_job(r.json()["job_id"], tok=STAFF)
        self.assertEqual(j["status"], "done", j)
        b = self.rows[self.ID]["data"]["build"]
        self.assertEqual(b["status"], "built"); self.assertEqual(b["sizes"], ["M", "L"])
        self.assertEqual(b["last_stored"]["ver"], 2)

    def test_8_merge_rules(self):
        m = self.cad._merge_build
        ok = {"status": "built", "sizes": ["M"], "style_id": "x"}
        e = m(ok, {"status": "error", "error": "실패", "at": "t"})
        self.assertEqual((e["status"], e["sizes"], e["error"]), ("built", ["M"], "실패"))   # 실패해도 보이던 패턴은 그대로
        self.assertNotIn("error", m(e, {"status": "built", "sizes": ["M", "L"]}))          # 다시 성공하면 오류 표시는 사라진다
        self.assertEqual(m(None, {"status": "error", "error": "x"})["status"], "error")


if __name__ == "__main__":
    unittest.main()
