# -*- coding: utf-8 -*-
"""재단 패턴 F10 6단계 «새 스타일 들여오기» 시험 — webapp/cad.py (+ vendor service.import_style·restyle·marker)

  [입력 검사 — 엔진 없이 빠르게]
  ① 직원 403 · 머리(PDF·엉뚱한 파일) 400 · 사이즈 레이어 없음·하나 400 · 기준 사이즈 없음 400 · 스타일 번호 글자 400 · 50MB 넘음 400
     · 어림 메모리가 상자를 넘는 원본 400 · 이름 글자 400 — 전부 한국어 · 실패해도 작업 폴더·디스크에 남는 것이 없다
  [진짜 엔진 — 약 1분 반, GRADER_SKIP_ENGINE_TESTS=1 이면 건너뜀] 완료 기준(설계 §6 6단계):
  ② 표준 웜업 상의 13사이즈 .ai → v1 (창고 백업·되읽기 · 원본은 {style}/source/ 디스크 + 창고) · 화면 자료 13사이즈·기준점 이름 같음
  ③ 확인 목록 9건 → 이름 고쳐 v2 — 모양은 v1 과 «0.01mm 정수까지» 같다(이 파일이 직접 견준다) · v1 그대로 · 확인 필요 7
  ④ 규칙표(들여온 판) 읽기 → 미리보기(재생성 검산 초록) → 저장 v3 · 미리보기 없이 저장 400
  ⑤ 마커(빠르게) 1회 — 명세 묶음으로 · 겹침 0 · 장수 = 벌수 × 한 벌 장수 · 파일 내려받기
  ⑥ 같은 번호 409(디스크 · 들여오는 중) · 잠근 판 이름·규칙 409 · 재배포(디스크 비움) 뒤 복원해도 들여온 판·확인 목록 그대로
  ⑦ 시험이 실제 data/uploads·data/cad 에 쓰지 않는다(state.UPLOADS_DIR·GRADER_CAD_DIR 를 임시로)
실행(저장소 루트): GRADER_CLEANUP_DISABLED=1 PYTHONIOENCODING=utf-8 python -m unittest tests.test_cad_import -v
"""
import hashlib
import json
import os
import shutil
import sys
import time
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_cad_rebuild import _Base, SKIP, ADMIN, STAFF  # noqa: E402

sha = lambda b: hashlib.sha256(b).hexdigest()
FIX = os.path.join(ROOT, "vendor", "pattern_engine", "fixtures", "gas-warmup-2026")
TOP = os.path.join(FIX, "std_warmup_top.ai")
SIZES = ["5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
SID = "std-warmup-top"
REAL_UPLOADS = os.path.join(ROOT, "data", "uploads")


def _count(d):
    try:
        return len(os.listdir(d))
    except OSError:
        return -1


class _Jobs:
    def wait_job(self, job_id, tok=ADMIN, limit=900):
        t0 = time.time()
        while time.time() - t0 < limit:
            j = self.client.get(f"/api/cad/jobs/{job_id}", headers={"Authorization": tok}).json()
            if j.get("status") in ("done", "error"):
                return j
            time.sleep(0.3)
        self.fail("작업이 끝나지 않음")


def _fake_ai(sizes=("S", "M"), head=b"%!PS-Adobe-3.0\r\n%%Creator: OptiCad Adobe Export\r\n"):
    """사이즈 레이어 이름 줄만 든 가짜 .ai (엔진까지 가지 않는 입력 검사용)"""
    body = b"".join(b"%AI5_BeginLayer\r\n(" + s.encode() + b") Ln\r\n%AI5_EndLayer\r\n" for s in sizes)
    return head + body + b"%%EOF\r\n"


class CadImportChecks(_Base, _Jobs):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        cls.uploads = os.path.join(cls.tmp, "uploads")
        up = mock.patch.object(cls.state, "UPLOADS_DIR", cls.uploads); up.start(); cls.patches.append(up)
        cls.real_uploads_before = _count(REAL_UPLOADS)

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def post(self, data, fields=None, tok=ADMIN, name="std_warmup_top.ai"):
        return self.client.post("/api/cad/styles/import", files={"source": (name, data, "application/postscript")},
                                data=fields or {"base_size": "M"}, headers={"Authorization": tok})

    def test_1_refusals_korean(self):
        with open(TOP, "rb") as f:
            top = f.read()
        r = self.post(top, tok=STAFF)
        self.assertEqual(r.status_code, 403)
        cases = [(b"%PDF-1.7\n" + b"0" * 50, {"base_size": "M"}, "PDF 형식"), (b"PK\x03\x04zip", {"base_size": "M"}, "PostScript"),
                 (b"", {"base_size": "M"}, "비어"), (_fake_ai(()), {"base_size": "M"}, "사이즈 레이어를 찾지 못"),
                 (_fake_ai(("M",)), {"base_size": "M"}, "둘 이상"), (_fake_ai(), {"base_size": "XL"}, "기준 사이즈 XL"),
                 (_fake_ai(), {"base_size": "M", "style_id": "한글번호"}, "영문 소문자"),
                 (_fake_ai(), {"base_size": "M", "style_id": "ab"}, "3~64자"),
                 (_fake_ai(), {"base_size": "M", "name": "<script>"}, "80자"),
                 (_fake_ai()[:-8], {"base_size": "M"}, "%%EOF"),                                  # 중간에 끊긴 파일 — 원인이 보이게
                 (_fake_ai() + b"%" * (3 * 2 ** 20), {"base_size": "M"}, "까지")]          # 3MB — 어림 메모리가 512MB 상자를 넘는다
        for data, fields, word in cases:
            r = self.post(data, fields)
            self.assertEqual(r.status_code, 400, (word, r.text))
            self.assertIn(word, r.json()["detail"], word)
        r = self.post(b"%!PS-Adobe-3.0\n" + b"0" * (50 * 2 ** 20 + 10))
        self.assertEqual(r.status_code, 400); self.assertIn("50MB", r.json()["detail"])
        self.assertEqual(os.listdir(self.jobs), [])                                      # 거절된 것은 작업 폴더도 안 만든다
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "cad", "std-warmup-top")))

    def test_2_in_progress_is_409(self):
        with self.cad._IMPORT_LOCK:
            self.cad._IMPORTING.add("busy-style")
        try:
            r = self.post(_fake_ai(), {"base_size": "M", "style_id": "busy-style"})
            self.assertEqual(r.status_code, 409); self.assertIn("들여오는 중", r.json()["detail"])
        finally:
            self.cad._IMPORTING.discard("busy-style")

    def test_3_me_says_importable(self):
        self.assertTrue(self.client.get("/api/cad/me", headers={"Authorization": ADMIN}).json()["importable"])
        self.assertFalse(self.client.get("/api/cad/me", headers={"Authorization": STAFF}).json()["importable"])

    def test_9_never_touch_real_uploads(self):
        self.assertNotEqual(os.path.realpath(self.state.UPLOADS_DIR), os.path.realpath(REAL_UPLOADS))
        self.assertEqual(_count(REAL_UPLOADS), self.real_uploads_before)


@unittest.skipIf(SKIP, "GRADER_SKIP_ENGINE_TESTS=1")
class CadImportEngine(_Base, _Jobs):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        up = mock.patch.object(cls.state, "UPLOADS_DIR", os.path.join(cls.tmp, "uploads")); up.start(); cls.patches.append(up)
        # 입장 판정의 «서버 몫» 은 이 시험 프로세스의 RAM(다른 시험이 불린 값)이 아니라 운영 서버 실측(151MB) 근처로 둔다
        sm = mock.patch.object(cls.cad, "_server_mb", return_value=160.0); sm.start(); cls.patches.append(sm)
        cls.real_uploads_before = _count(REAL_UPLOADS)
        with open(TOP, "rb") as f:
            cls.top = f.read()
        t0 = time.time()
        r = cls.client.post("/api/cad/styles/import", files={"source": ("표준 웜업 상의(26-09-18).ai", cls.top, "application/postscript")},
                            data={"base_size": "M", "style_id": SID, "note": "시험 들여오기"}, headers={"Authorization": ADMIN})
        assert r.status_code == 202, r.text
        cls.start = r.json(); cls.stages = []
        while time.time() - t0 < 900:
            j = cls.client.get(f"/api/cad/jobs/{cls.start['job_id']}", headers={"Authorization": ADMIN}).json()
            if not cls.stages or cls.stages[-1] != j.get("stage"): cls.stages.append(j.get("stage"))
            if j.get("status") in ("done", "error"): cls.final = j; break
            time.sleep(0.3)
        cls.import_s = round(time.time() - t0, 1)
        cls.view1 = cls.client.get(f"/api/cad/styles/{SID}/v/1/view", headers={"Authorization": STAFF}).json()

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def get(self, url, tok=STAFF):
        return self.client.get(url, headers={"Authorization": tok})

    def post(self, url, body, tok=ADMIN):
        return self.client.post(url, json=body, headers={"Authorization": tok})

    # ② 들여오기 v1
    def test_1_import_v1(self):
        j = self.final
        self.assertEqual(j["status"], "done", j.get("error"))
        R = j["result"]
        print(f"\n[들여오기] {self.import_s}초 · 단계 {self.stages} · 일꾼 최고 {R.get('peak_rss_mb')} MB "
              f"(어림 {R['estimate']['rss_mb']}) · VmPeak {R.get('vm_peak_mb')} · 확인 필요 {R['confirm_open']}")
        self.assertEqual(R["version"], 1); self.assertEqual(R["confirm_open"], 9); self.assertEqual(R["pieces"], 9)
        self.assertTrue(R["backup"]["ok"], R["backup"]); self.assertTrue(R["source_backup"]["ok"], R["source_backup"])
        self.assertLess(R["peak_rss_mb"], 512); self.assertGreaterEqual(R["estimate"]["rss_mb"], R["peak_rss_mb"])
        for st in ("pieces", "verify", "bundle"):                                        # «read» 는 0.0초라 0.3초 묻기로는 못 볼 수 있다
            self.assertIn(st, self.stages)
        for k in ("view", "exports", "meta"):
            self.assertIn(f"{SID}/v1/{k}", self.store)
        self.assertEqual(self.store[f"{SID}/source/original"], self.top)                     # 원본은 창고 «source» 에도
        with open(os.path.join(self.tmp, "cad", SID, "source", "original.ai"), "rb") as f:
            self.assertEqual(f.read(), self.top)
        meta = self.get(f"/api/cad/styles/{SID}").json()["history"][0]
        self.assertEqual(meta["imported"]["source_name"], "표준 웜업 상의(26-09-18).ai")
        self.assertEqual(meta["imported"]["source_sha256"], sha(self.top))
        self.assertEqual(os.listdir(self.jobs), [])                                         # 작업 폴더는 지웠다
        self.assertEqual(_count(REAL_UPLOADS), self.real_uploads_before)

    def test_2_view_sizes_overlay_measure(self):
        """화면 자료 — 13사이즈 전환 · 사이즈마다 같은 기준점 이름(겹쳐 보기 맞춤) · 기준점 사이 재봉선 길이가 사이즈 따라 변한다"""
        v = self.view1; q = v["q"]
        self.assertEqual(v["style"]["sizes"], SIZES); self.assertTrue(v["style"]["imported"]); self.assertEqual(v["style"]["base_size"], "M")
        names = None
        for s in SIZES:
            sz = v["sizes"][s]; self.assertTrue(sz["import_check"]["ok"], s)
            nn = {p["name"]: set(p["nodes"]) for p in sz["pieces"]}
            names = names or nn
            self.assertEqual(nn, names, s)
        def seam_len(s, piece, a, b):                                                       # 화면 «길이 재기» 와 같은 셈(재봉선 따라 짧은 쪽)
            p = next(x for x in v["sizes"][s]["pieces"] if x["name"] == piece); f = p["seam"]
            P = [(f[k] * q, f[k + 1] * q) for k in range(0, len(f), 2)]; cum = [0.0]
            for i in range(len(P)): cum.append(cum[-1] + ((P[(i + 1) % len(P)][0] - P[i][0]) ** 2 + (P[(i + 1) % len(P)][1] - P[i][1]) ** 2) ** 0.5)
            fwd = (cum[p["nodes"][b]] - cum[p["nodes"][a]]) % cum[-1]
            return min(fwd, cum[-1] - fwd)
        L = [seam_len(s, "뒤판", "뒤판_P1", "뒤판_P5") for s in SIZES]
        self.assertNotEqual(round(L[0], 1), round(L[-1], 1))                                  # 사이즈가 바뀌면 길이도 바뀐다
        r = self.get(f"/api/cad/styles/{SID}/v/1/files/source")
        self.assertEqual(r.status_code, 200); self.assertEqual(r.content, self.top)
        self.assertIn("filename*=UTF-8''", r.headers["content-disposition"])
        r = self.get(f"/api/cad/styles/{SID}/v/1/files/spec?size=5XS")
        self.assertEqual(r.status_code, 200); self.assertEqual(json.loads(r.content)["size"], "5XS")

    # ③ 이름 확인 → v2
    def test_3_confirm_and_rename_v2(self):
        c = self.get(f"/api/cad/styles/{SID}/v/1/confirm").json()
        self.assertEqual((c["open"], c["total"], c["editable"]), (9, 9, False))              # 직원 = 보기만
        c = self.get(f"/api/cad/styles/{SID}/v/1/confirm", tok=ADMIN).json()
        self.assertTrue(c["editable"])
        so = next(p for p in c["pieces"] if p["piece"] == "소매")
        p1, p2 = so["points"][0]["name"], so["points"][1]["name"]
        body = {"base_version": 1, "note": "이름 확인 시험", "pieces": {
            "소매": {"name": "소매판", "en_name": "sleeve", "qty": 2, "points": {p1: "겨드랑이앞", p2: "밑단앞"}, "confirmed": True},
            "에리": {"confirmed": True}}}
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/names", body, tok=STAFF).status_code, 403)
        for bad, word in (({"소매": {"name": "뒤판"}}, "겹칩"), ({"없는조각": {"confirmed": True}}, "없는 조각"),
                          ({"소매": {"qty": 99}}, "1~20"), ({"소매": {"name": "소매"}}, "바뀐 것이 없")):
            r = self.post(f"/api/cad/styles/{SID}/names", {"base_version": 1, "pieces": bad})
            self.assertEqual(r.status_code, 400, r.text); self.assertIn(word, r.json()["detail"])
        v1_view_sha = sha(self.get(f"/api/cad/styles/{SID}/v/1/view").content)
        r = self.post(f"/api/cad/styles/{SID}/names", body)
        self.assertEqual(r.status_code, 202, r.text)
        j = self.wait_job(r.json()["job_id"])
        self.assertEqual(j["status"], "done", j.get("error"))
        self.assertEqual(j["result"]["version"], 2); self.assertEqual(j["result"]["confirm_open"], 7)
        self.assertEqual(sha(self.get(f"/api/cad/styles/{SID}/v/1/view").content), v1_view_sha)   # v1 그대로
        v2 = self.get(f"/api/cad/styles/{SID}/v/2/view").json()
        pm, ptm = {"소매": "소매판"}, {p1: "겨드랑이앞", p2: "밑단앞"}
        for s in SIZES:                                                                       # 모양 같음 — 이 파일이 직접
            A = {p["name"]: p for p in self.view1["sizes"][s]["pieces"]}; B = {p["name"]: p for p in v2["sizes"][s]["pieces"]}
            for n, p in A.items():
                qp = B[pm.get(n, n)]
                for k in ("seam", "cut", "internal", "notches", "holes", "grain"):
                    self.assertEqual(p.get(k), qp.get(k), f"{s} {n} {k}")
                self.assertEqual({(ptm.get(k, k) if n == "소매" else k): x for k, x in p["nodes"].items()}, qp["nodes"])
        meta = self.get(f"/api/cad/styles/{SID}").json()["history"][1]
        self.assertEqual(meta["renamed_from"], 1); self.assertGreaterEqual(meta["name_changes_count"], 5)
        c2 = self.get(f"/api/cad/styles/{SID}/v/2/confirm").json()
        self.assertEqual(c2["open"], 7)
        sl = next(p for p in c2["pieces"] if p["piece"] == "소매판")
        self.assertEqual((sl["qty"], sl["en_name"], sl["confirmed"], sl["confirmed_by"]), (2, "SLEEVE", True, "tok-admin@stiz.kr"))
        # 누가 확인했는지는 서버 기록(meta)에서만 — 공장에 가는 묶음(confirm.json·confirm.md)에는 이메일이 없다
        for kind in ("names", "confirm"):
            self.assertNotIn(b"@", self.get(f"/api/cad/styles/{SID}/v/2/files/{kind}").content, kind)
        r = self.post(f"/api/cad/styles/{SID}/names", {"base_version": 1, "pieces": {"뒤판": {"confirmed": True}}})
        self.assertEqual(r.status_code, 409); self.assertIn("최신", r.json()["detail"])          # 옛 판 위 이름 저장 — 앞 이름 소실 방지
        lst = self.get("/api/cad/styles").json()["styles"]
        card = next(s for s in lst if s["id"] == SID)
        self.assertEqual((card["imported"], card["confirm_open"]), (True, 7))

    # ④ 다시 그레이딩(들여온 판)
    def test_4_rules_preview_save_v3(self):
        info = self.get(f"/api/cad/styles/{SID}/v/2/rules", tok=ADMIN).json()
        self.assertEqual((info["group"], info["source"], info["base_size"], info["editable"]), ("imported", "stored", "M", True))
        self.assertEqual(info["sizes"], SIZES); self.assertEqual(len(info["mesh_def"]), 5)
        self.assertEqual(sum(len(v) for v in info["rules"].values()), 153)
        b = info["rules"]["소매판"]["겨드랑이앞"]; bi = SIZES.index("M")
        ch = {"소매판": {"겨드랑이앞": {s: [b[s][0], b[s][1] + 1.0 * (SIZES.index(s) - bi)] for s in SIZES if s != "M"}}}
        r = self.post(f"/api/cad/styles/{SID}/versions", {"base_version": 2, "rules": ch})
        self.assertEqual(r.status_code, 400); self.assertIn("미리보기", r.json()["detail"])
        r = self.post(f"/api/cad/styles/{SID}/regrade", {"base_version": 2, "rules": {"소매판": {"겨드랑이앞": {"M": [1, 0]}}}})
        self.assertEqual(r.status_code, 400); self.assertIn("기준 사이즈", r.json()["detail"])
        r = self.post(f"/api/cad/styles/{SID}/regrade", {"base_version": 2, "rules": ch})
        self.assertEqual(r.status_code, 202, r.text)
        pj = r.json()["job_id"]; j = self.wait_job(pj)
        self.assertEqual(j["status"], "done", j.get("error"))
        res = j["result"]
        self.assertTrue(res["mesh"]["ok"], res["mesh"]); self.assertEqual(len(res["changes"]), 12)
        self.assertFalse(res["import_check"]["ok"])                                         # 원본과 다른 것이 정상
        pv = self.get(res["view_url"], tok=ADMIN)
        self.assertEqual(pv.status_code, 200); self.assertEqual(pv.json()["style"]["id"], SID)
        r = self.post(f"/api/cad/styles/{SID}/versions", {"base_version": 2, "rules": ch, "preview_job": pj, "note": "겨드랑이 1mm/칸"})
        self.assertEqual(r.status_code, 202, r.text)
        j = self.wait_job(r.json()["job_id"])
        self.assertEqual(j["status"], "done", j.get("error"))
        self.assertEqual(j["result"]["version"], 3)
        meta = self.get(f"/api/cad/styles/{SID}").json()["history"][2]
        self.assertEqual((meta["regraded_from"], meta["rule_changes_count"]), (2, 12))
        info3 = self.get(f"/api/cad/styles/{SID}/v/3/rules", tok=ADMIN).json()
        self.assertEqual(info3["rules"]["소매판"]["겨드랑이앞"]["5XS"], ch["소매판"]["겨드랑이앞"]["5XS"])

    # ⑤ 마커
    def test_5_marker_quick(self):
        t0 = time.time()
        r = self.post(f"/api/cad/styles/{SID}/v/2/marker", {"width_cm": 150, "gap_mm": 3, "counts": {"M": 1, "5XS": 1}}, tok=STAFF)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["request"]["per_bundle"], 10)                             # 9조각 + 소매판 2장
        j = self.wait_job(r.json()["job_id"], tok=STAFF)
        self.assertEqual(j["status"], "done", j.get("error"))
        R = j["result"]; s, v, m = R["summary"], R["verify"], R["memory"]
        print(f"\n[들여온 마커] {round(time.time() - t0, 1)}초 · {s['length_m']} m · 효율 {s['efficiency_pct']}% · 조각 {s['piece_count']}"
              f" · 일꾼 최고 {m['worker_max_mb']} MB · 서버 {m['server_peak_mb']} MB")
        self.assertTrue(v["ok"], v); self.assertEqual(s["piece_count"], 20)
        self.assertLess(m["worker_max_mb"], 512)
        for k in ("pdf", "dxf", "png", "json"):
            self.assertEqual(self.get(R["files"][k]["url"]).status_code, 200, k)
        r = self.post(f"/api/cad/styles/{SID}/v/2/marker", {"counts": {"6XL": 1}}, tok=STAFF)
        self.assertEqual(r.status_code, 400); self.assertIn("없는 사이즈", r.json()["detail"])

    # ⑥ 같은 번호 · 잠금 · 재배포 복원
    def test_6_same_id_409(self):
        r = self.client.post("/api/cad/styles/import", files={"source": ("x.ai", self.top, "application/postscript")},
                             data={"base_size": "M", "style_id": SID}, headers={"Authorization": ADMIN})
        self.assertEqual(r.status_code, 409); self.assertIn("이미 있습니다", r.json()["detail"])

    def test_7_locked_blocks_names_and_rules(self):
        self.assertEqual(self.post(f"/api/cad/styles/{SID}/v/1/lock", {"note": "공장 1차"}).status_code, 200)
        r = self.post(f"/api/cad/styles/{SID}/names", {"base_version": 1, "pieces": {"뒤판": {"confirmed": True}}})
        self.assertEqual(r.status_code, 409)
        r = self.post(f"/api/cad/styles/{SID}/regrade", {"base_version": 1, "rules": {}})
        self.assertEqual(r.status_code, 409)
        c = self.get(f"/api/cad/styles/{SID}/v/1/confirm", tok=ADMIN).json()
        self.assertFalse(c["editable"]); self.assertTrue(c["locked"])

    def test_8_restore_after_redeploy(self):
        shutil.rmtree(os.path.join(self.tmp, "cad"))
        self.cad._last_restore["at"] = 0.0
        lst = self.get("/api/cad/styles").json()
        card = next(s for s in lst["styles"] if s["id"] == SID)
        self.assertEqual(card["versions"], [1, 2, 3]); self.assertTrue(card["imported"])
        c = self.get(f"/api/cad/styles/{SID}/v/2/confirm").json()
        self.assertEqual(c["open"], 7)
        self.assertEqual(self.get(f"/api/cad/styles/{SID}/v/1/rules", tok=ADMIN).json()["group"], "imported")

    def test_9_never_touch_real_uploads(self):
        self.assertEqual(_count(REAL_UPLOADS), self.real_uploads_before)


if __name__ == "__main__":
    unittest.main()
