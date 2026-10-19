# -*- coding: utf-8 -*-
"""재단 패턴 4단계(마커·요척) 시험 — POST /api/cad/styles/{id}/v/{ver}/marker · /api/cad/order/counts · /api/cad/jobs/{job}/files/{kind}

  [가짜로 빠르게]
  ① 입력 검사(400·한국어): 원단 폭 50~300 · 간격 0~20 · 그 버전에 없는 사이즈 · 벌수 합 1~200 · 정수 아님 · 없는 조각/전부 빼기
     · nap 이 참/거짓 아님 · JSON 아님 · 마커 못 만드는 스타일 · 없는 버전 404 · 로그인 없으면 401 · 직원(관리자 아님)도 된다
  ② 주문서: 양식①(이니셜·배번·사이즈·하의) · 양식③(순번·부제 상의/하의·비고 «2장») → 피스 규칙 벌수 · 깨진 엑셀·엑셀 아님 400
     · 하의 열 없는 주문서로 하의 마커 400 · multipart(options + order) 로 시작하면 주문서 벌수가 요청에 들어간다
  ③ 작업: 단계 → 끝 · 결과(요약·검산·메모리) · 파일 4종 내려받기(지문 같음) · 중간 결과는 지운다 · 검산 틀리면 error
     · 일꾼 환경: 주소 공간 상한 = 운영자 값(GRADER_ENGINE_LIMIT_AS_MB·GRADER_MARKER_LIMIT_AS_MB) 먼저, 없으면 마커 기본 1152MB
       · check_view = 그 버전 view.json · 규칙표 없는 버전은 rules=None
  [진짜 엔진 — 약 2분, GRADER_SKIP_ENGINE_TESTS=1 이면 건너뜀]
  ④ 완료 기준: 가스 상의 S~5XL 1벌씩 — 겹침 0 · 식서 0°/180° · 서버 길 결과 = stizshop marker.py 명령줄(같은 graded.json·같은 인자)
     길이·효율·조각 자리 전부 같음 · 일꾼 최고 메모리 < 512MB(결과에 기록) · 원단이 좁으면 한국어 사유로 error
     (GRADER_MARKER_FULL_TEST=1 이면 «빠르게» 대신 서버 기본 탐색(일꾼 1·기억 100MB·120초)으로도 견준다 — 약 4분 더)
실행(저장소 루트): python -m unittest tests.test_cad_marker -v
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_cad import make_bundle  # noqa: E402
from test_cad_rebuild import _Base, STIZ_ENGINE, SKIP, SID, ADMIN, STAFF  # noqa: E402
import xlsx_bombs  # noqa: E402

sha = lambda b: hashlib.sha256(b).hexdigest()
SIZES = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
BID = "gas-warmup-2026-bottom"
FULL = os.environ.get("GRADER_MARKER_FULL_TEST") == "1"


def xlsx(rows, sheet="작성하기"):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = sheet
    for r in rows:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


# 양식①: 이니셜 | 배번 | 사이즈(상의) | 하의 | 수량 — 상의만·하의만·위아래 다른 사람이 섞였다
FORM1 = xlsx([["이니셜", "배번", "사이즈", "하의", "수량"], ["김가", "1", "L", "XL", None], ["이나", "2", "2XL", None, None],
              ["박다", "3", None, "M", None], ["최라", "4", "2XL", "2XL", None]])
# 양식③(STIZ 신폼): 순번 | 이니셜 | 배번 | 사이즈 + 부제(상의 | 하의) | 비고(«2장» = 그 줄 2벌)
#   실제 신폼처럼 명단 머리글이 18번째 줄쯤 있다(위는 팀명·연락처 칸) — 그래야 parse_order 가 양식③으로 읽는다
FORM3 = xlsx([["STIZ CUSTOM 주문서"]] + [[f"안내 {i}"] for i in range(16)] + [["순\xa0\xa0 번", "\xa0이니셜", "\xa0배\xa0\xa0 번", "\xa0사이즈", None, "비  고"],
              [None, None, None, "상의", "하의", None], [1, "가", 1, "M", "L", "2장"], [2, "나", 2, "S", None, "1장"],
              [3, None, None, None, None, None]])
# 하의 열이 없는 주문서
TOPONLY = xlsx([["이니셜", "배번", "사이즈"], ["김가", "1", "L"], ["이나", "2", "M"]])


def bomb_rows(rows=300000, cols="AN"):
    """4.8KB «xlsx 폭탄» — 시트 크기를 A1:AN300000 으로 적고 맨 끝 칸 하나만 둔다(read_only 가 빈 줄을 전부 만들던 것)"""
    import re, zipfile
    src = zipfile.ZipFile(io.BytesIO(xlsx([["이니셜", "배번", "사이즈"], ["김가", "1", "L"]], sheet="Sheet")))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for it in src.infolist():
            data = src.read(it.filename)
            if it.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(rb'<dimension ref="[^"]*"/>', f'<dimension ref="A1:{cols}{rows}"/>'.encode(), data)
                data = data.replace(b"</sheetData>", f'<row r="{rows}"><c r="{cols}{rows}" t="inlineStr"><is><t>x</t></is></c></row></sheetData>'.encode())
            z.writestr(it, data)
    return out.getvalue()


def bomb_zip(mb=60):
    """풀면 60MB 인 xlsx — 시트 XML 안에 긴 주석(압축하면 수십 KB)"""
    import zipfile
    src = zipfile.ZipFile(io.BytesIO(TOPONLY)); out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for it in src.infolist():
            data = src.read(it.filename)
            if it.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b"<sheetData>", b"<!--" + b"a" * (mb * 2**20) + b"--><sheetData>")
            z.writestr(it, data)
    return out.getvalue()


class FakeSvc:
    """진짜 창구(vendor service)를 그대로 쓰되 marker 만 가짜 — 서버 쪽 처리(작업·파일·정리)만 빠르게 본다"""

    def __init__(self, real, mode="ok"):
        self._real, self.mode, self.calls = real, mode, []

    def __getattr__(self, k):
        return getattr(self._real, k)

    def marker(self, work, group, counts, on_step=None, env=None, **kw):
        self.calls.append({"work": work, "group": group, "counts": counts, "env": env, **kw})
        if self.mode == "slow":                                          # 취소를 기다린다(최대 20초)
            ev = kw.get("cancel")
            if ev is not None and ev.wait(20):
                raise self._real.ServiceError("취소했습니다.")
        for i, n in enumerate(self._real.MARKER_STEPS, 1):
            on_step and on_step(i, len(self._real.MARKER_STEPS), n)
        out = os.path.join(work, "marker"); os.makedirs(out, exist_ok=True)
        os.makedirs(os.path.join(work, "gas-warmup", "graded"), exist_ok=True)              # 중간 결과(지워져야 한다)
        files = {}
        for k, nm in self._real.MARKER_FILES.items():
            data = (f"{k}-가짜-" * 50).encode("utf-8")
            p = os.path.join(out, nm); open(p, "wb").write(data)
            files[k] = {"path": p, "bytes": len(data), "sha256": sha(data)}
        if self.mode == "outside":                                       # 작업 폴더 밖 파일을 가리키면 내려주지 않는다
            files["pdf"]["path"] = os.path.abspath(__file__)
        ok = self.mode != "bad"
        return {"ok": True, "summary": {"length_m": 1.234, "yield_m_per_bundle": 0.617, "efficiency_pct": 80.0, "piece_count": 34,
                                        "bundles": 2, "counts": counts},
                "verify": {"ok": ok, "overlaps": 0 if ok else 2, "outside": 0, "min_gap_mm": 3.0, "gap_ok": True,
                           "rotations": [0, 180], "grain_ok": True, "flipped": 0},
                "files": files, "font": {"source": "builtin"}, "engine": {"commit": "fake"}, "peak_rss_mb": 300.0,
                "peak_rss_mb_max": 300.0, "wall_s": 0.1, "timings_s": {"marker": 0.1},
                "graded_run": {"peak_rss_mb": 120.0, "view_match": {"max_mm": 0.0, "pieces": 72, "diffs": []}, "rules_used": False,
                               "graded_sha256": "0" * 64}}


class _Jobs:
    def wait_job(self, job_id, tok=STAFF, limit=900):
        t0 = time.time()
        while time.time() - t0 < limit:
            j = self.client.get(f"/api/cad/jobs/{job_id}", headers={"Authorization": tok}).json()
            if j.get("status") in ("done", "error"):
                return j
            time.sleep(0.2)
        self.fail("작업이 끝나지 않음")


class CadMarkerFast(_Base, _Jobs):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        cls.uploads = os.path.join(cls.tmp, "uploads")
        up = mock.patch.object(cls.state, "UPLOADS_DIR", cls.uploads); up.start(); cls.patches.append(up)   # data/uploads 에 안 남긴다
        cls.roles["tok-staff2"] = None                                    # 다른 직원(취소 권한 시험)
        for sid in (SID, BID):
            view, zb, _ = make_bundle(style_id=sid, sizes=("S", "M", "L"))
            r = cls.upload(view, zb, headers={"Authorization": ADMIN})
            assert r.status_code == 201, r.text
        cls.real = cls.cad.load_service()

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def post(self, body, sid=SID, tok=STAFF, ver="1"):
        return self.client.post(f"/api/cad/styles/{sid}/v/{ver}/marker", json=body, headers={"Authorization": tok})

    def test_1_input_validation(self):
        ok = {"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}}
        bad = [({"width_cm": 49}, "원단 폭"), ({"width_cm": 301}, "원단 폭"), ({"width_cm": "150"}, "원단 폭"),
               ({"gap_mm": 21}, "간격"), ({"gap_mm": -1}, "간격"),
               ({"counts": {"XL": 1}}, "없는 사이즈"),                                         # 버전에 없는 사이즈(S·M·L 만)
               ({"counts": {"2XL-edit": 1}}, "없는 사이즈"),
               ({"counts": {}}, "하나 이상"), ({"counts": {"S": 0}}, "합이 0"), ({"counts": {"S": 150, "M": 51}}, "200벌까지"),
               ({"counts": {"S": 1.5}}, "정수"), ({"counts": {"S": -1}}, "정수"), ({"counts": [1]}, "하나 이상"),
               ({"exclude": ["모자"]}, "없는 조각"), ({"exclude": ["뒤판"]}, "전부 뺄 수는"),
               ({"nap": "yes"}, "참/거짓"), ({"quick": 1}, "참/거짓")]
        for patch, want in bad:
            r = self.post({**ok, **patch})
            self.assertEqual(r.status_code, 400, (patch, r.text))
            self.assertIn(want, r.json()["detail"], patch)
        r = self.client.post(f"/api/cad/styles/{SID}/v/1/marker", content=b"not json", headers={"Authorization": STAFF,
                                                                                            "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.post([1, 2]).status_code, 400)
        self.assertEqual(self.post(ok, ver="9").status_code, 404)
        self.assertEqual(self.client.post(f"/api/cad/styles/{SID}/v/1/marker", json=ok).status_code, 401)   # 로그인 없음
        view, zb, _ = make_bundle(style_id="other-style", sizes=("S",))
        self.upload(view, zb, headers={"Authorization": ADMIN})
        r = self.post(ok, sid="other-style")
        self.assertEqual(r.status_code, 400); self.assertIn("마커를 만들 수 없습니다", r.json()["detail"])

    def test_2_order_counts(self):
        def counts(data, name="o.xlsx"):
            return self.client.post("/api/cad/order/counts", files={"order": (name, data, "application/octet-stream")},
                                    headers={"Authorization": STAFF})
        j = counts(FORM1).json()
        self.assertEqual((j["top"], j["bottom"], j["bottom_found"]), ({"L": 1, "2XL": 2}, {"M": 1, "XL": 1, "2XL": 1}, True))
        j = counts(FORM3).json()                                                         # 비고 «2장» = 그 줄 두 벌
        self.assertEqual((j["top"], j["bottom"], j["people"]), ({"S": 1, "M": 2}, {"L": 2}, 2))     # 2줄(«2장» 줄은 2벌)
        j = counts(TOPONLY).json()
        self.assertEqual((j["top"], j["bottom"], j["bottom_found"]), ({"M": 1, "L": 1}, {}, False))
        self.assertTrue(any("하의" in w for w in j["warnings"]))
        r = counts(b"PK\x03\x04 broken zip bytes")                                        # 깨진 엑셀
        self.assertEqual(r.status_code, 400); self.assertIn("찾지 못했습니다", r.json()["detail"])
        r = counts(b"a,b", name="o.csv")
        self.assertEqual(r.status_code, 400); self.assertIn(".xlsx", r.json()["detail"])
        self.assertEqual(counts(b"", name="o.xlsx").status_code, 400)
        r = self.client.post("/api/cad/order/counts", files={"order": ("o.xlsx", FORM1, "application/octet-stream")})
        self.assertEqual(r.status_code, 401)

    def test_3_order_multipart_start(self):
        seen = []
        with mock.patch.object(self.cad, "_start_engine_job", side_effect=lambda req, kind, total, fields, target, args, need_token=True, lane="cad":
                               (seen.append((kind, args, need_token, lane)) or ("a" * 12, 0))):
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/marker", headers={"Authorization": STAFF},
                                 data={"options": json.dumps({"width_cm": 160, "gap_mm": 2, "counts": {"S": 99}})},
                                 files={"order": ("o.xlsx", FORM3, "application/octet-stream")})
            self.assertEqual(r.status_code, 202, r.text)
            self.assertEqual(r.json()["request"]["counts"], {"S": 1, "M": 2})              # 주문서가 손 입력을 이긴다(상의)
            self.assertEqual(r.json()["order"]["bottom"], {"L": 2})
            kind, args, need, lane = seen[-1]
            self.assertEqual((kind, need, lane, args[2], args[3]["width_cm"], args[3]["gap_mm"]), ("cad-marker", False, "marker", "top", 160.0, 2.0))
            self.assertEqual((args[3]["jobs"], args[3]["cache_mb"], args[3]["quick"]), (1, 0.0, True))   # 서버 기본값 — 직원이 못 바꾼다
            self.assertLessEqual(args[3]["budget"], 120.0)
            r = self.client.post(f"/api/cad/styles/{BID}/v/1/marker", headers={"Authorization": STAFF},
                                 data={"options": "{}"}, files={"order": ("o.xlsx", FORM3, "application/octet-stream")})
            self.assertEqual(r.status_code, 202, r.text)
            self.assertEqual(r.json()["request"]["counts"], {"L": 2})                      # 하의 스타일은 하의 열
            r = self.client.post(f"/api/cad/styles/{BID}/v/1/marker", headers={"Authorization": STAFF},
                                 data={"options": "{}"}, files={"order": ("o.xlsx", TOPONLY, "application/octet-stream")})
            self.assertEqual(r.status_code, 400); self.assertIn("하의 사이즈 열", r.json()["detail"])
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/marker", headers={"Authorization": STAFF},
                                 data={"options": "{"}, files={"order": ("o.xlsx", FORM3, "application/octet-stream")})
            self.assertEqual(r.status_code, 400)
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/marker", headers={"Authorization": STAFF},
                                 data={"options": "{}"}, files={"order": ("o.xlsx", b"garbage", "application/octet-stream")})
            self.assertEqual(r.status_code, 400)

    def test_4_job_files_and_cleanup(self):
        fake = FakeSvc(self.real)
        with mock.patch.object(self.cad, "load_service", return_value=fake):
            r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1, "M": 1}, "quick": True})
            self.assertEqual(r.status_code, 202, r.text)
            j = self.wait_job(r.json()["job_id"])
        self.assertEqual(j["status"], "done", j.get("error"))
        self.assertEqual(j["kind"], "cad-marker")
        res = j["result"]
        self.assertEqual((res["summary"]["length_m"], res["verify"]["ok"], res["memory"]["worker_max_mb"]), (1.234, True, 300.0))
        self.assertIsNotNone(res["memory"]["server_peak_mb"])
        call = fake.calls[-1]
        self.assertEqual(call["env"]["GRADER_ENGINE_LIMIT_AS_MB"], str(self.cad.MARKER_AS_LIMIT_MB_DEFAULT))   # 운영자 값이 없으면 마커 기본값
        self.assertLessEqual(call["timeout"], self.cad.MARKER_TIMEOUT_S_DEFAULT)          # 전체 시간 상한
        self.assertTrue(call["check_view"].endswith(os.path.join(SID, "v1", "view.json")))  # 그 버전 모양과 견준다
        self.assertIsNone(call["rules"])                                                   # 규칙표 없는 버전 = 표준 규칙
        self.assertEqual((call["jobs"], call["cache_mb"], call["quick"]), (1, 0.0, True))
        self.assertLessEqual(call["budget"], 120.0)
        for k, f in res["files"].items():
            d = self.client.get(f["url"], headers={"Authorization": STAFF})
            self.assertEqual(d.status_code, 200, k)
            self.assertEqual(sha(d.content), f["sha256"], k)
            self.assertIn("marker", d.headers["content-disposition"])
        self.assertEqual(self.client.get(res["files"]["pdf"]["url"]).status_code, 401)      # 로그인 없음
        self.assertEqual(self.client.get(f"/api/cad/jobs/{'0' * 12}/files/pdf", headers={"Authorization": STAFF}).status_code, 404)
        self.assertEqual(self.client.get(res["files"]["pdf"]["url"].replace("/pdf", "/exe"), headers={"Authorization": STAFF}).status_code, 400)
        left = sorted(os.listdir(call["work"]))
        self.assertNotIn("gas-warmup", left)                                               # 중간 결과는 지웠다
        self.assertIn("marker", left)

    def test_5_bad_verify_is_error(self):
        with mock.patch.object(self.cad, "load_service", return_value=FakeSvc(self.real, "bad")):
            r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}})
            j = self.wait_job(r.json()["job_id"])
        self.assertEqual(j["status"], "error")
        self.assertIn("검산이 맞지 않아", j["error"])
        r = self.client.get(f"/api/cad/jobs/{r.json()['job_id']}/files/pdf", headers={"Authorization": STAFF})
        self.assertEqual(r.status_code, 404)

    def test_7_cancel_and_lanes(self):
        """취소: 맡긴 본인·관리자만(다른 직원 403) · 돌던 일꾼을 멈춤 · 마커 칸은 하나 — 관리자 줄은 막지 않는다"""
        fake = FakeSvc(self.real, "slow")
        with mock.patch.object(self.cad, "load_service", return_value=fake):
            r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}})
            self.assertEqual(r.status_code, 202, r.text)
            jid = r.json()["job_id"]
            t0 = time.time()
            while not fake.calls and time.time() - t0 < 10:
                time.sleep(0.05)
            r2 = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}}, tok=ADMIN)    # 마커 칸이 찼다
            self.assertEqual(r2.status_code, 429); self.assertIn("한 번에 하나", r2.json()["detail"])
            self.assertEqual((self.cad._queue["marker"], self.cad._queue["waiting"]), (1, 0))   # 관리자 줄은 비어 있다
            self.assertEqual(self.client.delete(f"/api/cad/jobs/{jid}", headers={"Authorization": "Bearer tok-staff2"}).status_code, 403)
            d = self.client.delete(f"/api/cad/jobs/{jid}", headers={"Authorization": STAFF})
            self.assertEqual((d.status_code, d.json()["status"]), (200, "cancelling"))
            j = self.wait_job(jid)
        self.assertEqual((j["status"], j["error"], j["cancelled"]), ("error", "취소했습니다.", True))
        self.assertEqual(self.cad._queue["marker"], 0)
        self.assertEqual(self.client.delete(f"/api/cad/jobs/{'0' * 12}", headers={"Authorization": STAFF}).status_code, 404)

    def test_8_admin_may_search_staff_quick(self):
        fake = FakeSvc(self.real)
        with mock.patch.object(self.cad, "load_service", return_value=fake):
            for tok, want in ((STAFF, True), (ADMIN, False)):
                r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}, "quick": False}, tok=tok)
                self.wait_job(r.json()["job_id"], tok=tok)
                self.assertEqual(fake.calls[-1]["quick"], want, tok)        # 직원은 언제나 빠르게 · 관리자만 여러 번 깔기

    def test_9_paths_env_and_unknown_sizes(self):
        with mock.patch.object(self.cad, "load_service", return_value=FakeSvc(self.real, "outside")):
            r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}})
            j = self.wait_job(r.json()["job_id"])
        self.assertNotIn("pdf", j["result"]["files"])                       # 작업 폴더 밖 주소는 버린다
        with mock.patch.dict(os.environ, {"GRADER_ENGINE_LIMIT_AS_MB": "777"}):
            self.assertEqual(self.cad._marker_env()["GRADER_ENGINE_LIMIT_AS_MB"], "777")     # 운영자 값을 따른다
        with mock.patch.dict(os.environ, {"GRADER_ENGINE_LIMIT_AS_MB": "0"}):
            self.assertEqual(self.cad._marker_env()["GRADER_ENGINE_LIMIT_AS_MB"], "0")       # 끔도 그대로
        with mock.patch.dict(os.environ, {"GRADER_MARKER_LIMIT_AS_MB": "900", "GRADER_ENGINE_LIMIT_AS_MB": "777"}):
            self.assertEqual(self.cad._marker_env()["GRADER_ENGINE_LIMIT_AS_MB"], "900")     # 마커 전용 값이 먼저
        withxs = xlsx([["이니셜", "배번", "사이즈", "하의"], ["김", "1", "XS", "M"], ["이", "2", "L", "L"]])
        with mock.patch.object(self.cad, "_start_engine_job", return_value=("b" * 12, 0)):
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/marker", headers={"Authorization": STAFF},
                                 data={"options": "{}"}, files={"order": ("o.xlsx", withxs, "application/octet-stream")})
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual((r.json()["request"]["counts"], r.json()["order"]["dropped"]), ({"L": 1}, {"XS": 1}))   # 없는 사이즈는 빼고 경고
        self.assertTrue(any("XS 1벌" in w for w in r.json()["order"]["warnings"]))

    def test_10_bottom_only_rows_and_bombs(self):
        """하의만 산 줄을 버리지 않는다 · xlsx 폭탄은 빨리·작게 끝난다 · 깨진 파일 문구에 서버 경로가 없다"""
        pad = [[f"안내 {i}"] for i in range(16)]
        f3 = xlsx(pad + [["순번", "이니셜", "배번", "사이즈", None, "비고"], [None, None, None, "상의", "하의", None],
                         [1, "가", 1, "M", "L", "2장"], [2, None, None, None, "L", "2장"], [3, "나", 2, "S", None, "상의1장 하의0장"]])
        f1 = xlsx([["이니셜", "배번", "사이즈", "하의"], ["김", "1", "L", "XL"], ["박", None, None, "M"], ["최", "3", "XXL", "2XL"]])
        post = lambda data: self.client.post("/api/cad/order/counts", files={"order": ("o.xlsx", data, "application/octet-stream")},
                                             headers={"Authorization": STAFF})
        self.assertEqual((post(f3).json()["top"], post(f3).json()["bottom"]), ({"S": 1, "M": 2}, {"L": 4}))
        self.assertEqual((post(f1).json()["top"], post(f1).json()["bottom"]), ({"L": 1, "2XL": 1}, {"M": 1, "XL": 1, "2XL": 1}))
        t0 = time.time(); r = post(bomb_rows())                          # 4.8KB → (예전) 30만 행
        self.assertLess(time.time() - t0, 3.0)
        self.assertEqual((r.status_code, r.json()["top"]), (200, {"L": 1}))
        r = post(bomb_zip())                                             # 시트 XML 하나가 60MB
        self.assertEqual(r.status_code, 400); self.assertIn("너무 큽니다", r.json()["detail"])
        r = post(b"PK\x03\x04 broken")
        self.assertEqual(r.status_code, 400)
        for bad in (self.uploads, "uploads", ":\\", "/tmp", self.tmp):
            self.assertNotIn(bad, r.json()["detail"])
        t0 = time.time()                                                 # 합성 쪽 /api/order/parse 도 같은 상한
        r = self.client.post("/api/order/parse", files={"file": ("o.xlsx", bomb_rows(), "application/octet-stream")},
                             headers={"Authorization": STAFF})
        self.assertLess(time.time() - t0, 3.0)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any("2000행" in w for w in r.json()["warnings"]))
        self.assertTrue(os.listdir(self.uploads))                          # 올린 파일은 임시 폴더로 갔다(data/uploads 아님)

    def test_11_xlsx_bombs_refused_before_reading(self):
        """엑셀 폭탄 4종(재리뷰 실측: 1,082MB · 1,491MB · 291MB · CPU 530초) — 합성(/api/order/parse)·마커(/api/cad/order/counts) 둘 다
        «열기 전에» 항목별 상한으로 막는다: 빨리(3초 안) · 작게(파이썬 메모리 30MB 안) · 사유는 한국어 · 서버 경로 없음"""
        import tracemalloc
        for name, make in xlsx_bombs.BOMBS.items():
            data = make()
            for url, field in (("/api/cad/order/counts", "order"), ("/api/order/parse", "file")):
                tracemalloc.start(); t0 = time.time()
                r = self.client.post(url, files={field: ("o.xlsx", data, "application/octet-stream")}, headers={"Authorization": STAFF})
                took = time.time() - t0; peak = tracemalloc.get_traced_memory()[1] / 2 ** 20; tracemalloc.stop()
                self.assertLess(took, 3.0, (name, url))
                self.assertLess(peak, 30 + len(data) * 3 / 2 ** 20, (name, url, peak))       # 올린 파일 몇 벌 + 여유 — 풀어 읽지 않았다
                text = r.json().get("detail") or " ".join(r.json().get("warnings") or [])
                self.assertTrue(("너무 많습니다" in text) or ("너무 큽니다" in text), (name, url, text))
                self.assertNotIn(self.uploads, text)
                if url.endswith("counts"):
                    self.assertEqual(r.status_code, 400, name)
                else:
                    self.assertEqual((r.status_code, r.json()["rows"]), (200, []), name)  # 합성 쪽은 원래처럼 «빈 결과 + 경고»
        # 진짜 주문서(그림 없는 작은 것)는 그대로 읽힌다
        self.assertEqual(self.client.post("/api/cad/order/counts", files={"order": ("o.xlsx", FORM1, "application/octet-stream")},
                                          headers={"Authorization": STAFF}).status_code, 200)

    def test_12_cancel_while_waiting_for_synthesis(self):
        """합성이 도는 동안(HeavyGate 대기 — 최대 600초) 취소하면 바로 끝난다(엔진은 안 띄운다)"""
        release = threading.Event(); entered = threading.Event()

        def synth():
            with self.state.HEAVY.shared_use():
                entered.set(); release.wait(30)
        th = threading.Thread(target=synth, daemon=True); th.start(); entered.wait(5)
        fake = FakeSvc(self.real)
        try:
            with mock.patch.object(self.cad, "load_service", return_value=fake), \
                    mock.patch.dict(os.environ, {"GRADER_CAD_HEAVY_WAIT_S": "60"}):
                r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}})
                jid = r.json()["job_id"]
                t0 = time.time()
                while self.client.get(f"/api/cad/jobs/{jid}", headers={"Authorization": STAFF}).json().get("stage") != "wait_heavy":
                    self.assertLess(time.time() - t0, 10); time.sleep(0.05)
                self.client.delete(f"/api/cad/jobs/{jid}", headers={"Authorization": STAFF})
                j = self.wait_job(jid, limit=10)
        finally:
            release.set(); th.join(5)
        self.assertEqual((j["status"], j["cancelled"]), ("error", True))
        self.assertLess(time.time() - t0, 5.0)
        self.assertEqual(fake.calls, [])                                   # 엔진을 띄우지 않았다
        self.assertEqual(self.state.HEAVY.snapshot(), {"shared": 0, "exclusive": False, "waiting_excl": 0})

    def test_13_cancel_after_done_leaves_nothing(self):
        """끝난 작업을 취소하면 그대로(표시를 안 덮고 · 취소 신호가 남지 않는다) · 서버 몫 = 지금 서버 RSS + 30MB"""
        with mock.patch.object(self.cad, "load_service", return_value=FakeSvc(self.real)):
            r = self.post({"width_cm": 150, "gap_mm": 3, "counts": {"S": 1}})
            j = self.wait_job(r.json()["job_id"])
        d = self.client.delete(f"/api/cad/jobs/{r.json()['job_id']}", headers={"Authorization": STAFF}).json()
        self.assertEqual((d["status"], j["stage"]), ("done", "done"))
        self.assertEqual(self.client.get(f"/api/cad/jobs/{r.json()['job_id']}", headers={"Authorization": STAFF}).json()["stage"], "done")
        self.assertNotIn(r.json()["job_id"], self.cad._CANCEL)
        with mock.patch.object(self.real, "current_rss_mb", return_value=200.0):
            self.assertEqual(self.cad._server_mb(self.real), 230.0)
        with mock.patch.object(self.real, "current_rss_mb", return_value=None):
            self.assertEqual(self.cad._server_mb(self.real), self.real.MARKER_SERVER_MB)

    def test_14_note_numbers_are_not_quantities(self):
        """«비고» 의 숫자는 «장·벌·개·세트» 가 바로 붙을 때만 수량 — 1벌이 아닌 수를 읽은 줄은 경고에 남긴다(독립 시험 지적)"""
        rows = [["이니셜", "배번", "사이즈", "하의", "비고"],
                ["가", "1", "M", "M", "11번으로 변경"],          # 등번호 바꾼 메모 — 1벌
                ["나", "2", "M", "M", "2024 우승기념"],          # 해 — 1벌
                ["다", "3", "M", "M", "010-1234-5678"],          # 전화번호 — 1벌
                ["라", "4", "M", "M", "5XL 요청"],               # 사이즈 메모 — 1벌
                ["마", "5", "L", "L", "상의2장 하의1장"],         # 따로
                ["바", "6", "XL", "XL", "2장"],                  # 둘 다 2
                ["사", "7", "S", "S", "상의2장"],                # 한쪽만 — 하의는 사이즈 칸이 찼으니 1
                ["아", "8", "2XL", "2XL", "하의 3장"]]           # 한쪽만 — 상의 1
        j = self.client.post("/api/cad/order/counts", files={"order": ("o.xlsx", xlsx(rows), "application/octet-stream")},
                             headers={"Authorization": STAFF}).json()
        self.assertEqual(j["top"], {"S": 2, "M": 4, "L": 2, "XL": 2, "2XL": 1})
        self.assertEqual(j["bottom"], {"S": 1, "M": 4, "L": 1, "XL": 2, "2XL": 3})
        w = " ".join(j["warnings"])
        self.assertIn("1벌이 아닌 수를 읽은 줄 4개", w)
        for frag in ("상의2장 하의1장", "«2장»", "«상의2장»", "«하의 3장»"):
            self.assertIn(frag, w)
        for frag in ("11번", "2024", "010-", "5XL 요청"):
            self.assertNotIn(frag, w)
        # 머리글이 «수량» 이면 맨 숫자도 수량
        j = self.client.post("/api/cad/order/counts", files={"order": ("o.xlsx", xlsx([["이니셜", "배번", "사이즈", "수량"], ["가", "1", "M", 3]]),
                                                                       "application/octet-stream")}, headers={"Authorization": STAFF}).json()
        self.assertEqual(j["top"], {"M": 3})

    def test_15_uploads_never_touch_real_folder(self):
        """시험이 올린 주문서는 임시 폴더로만 — state.UPLOADS_DIR 을 바꿔야 막힌다(get_uploads_dir 만 바꾸면 실제 data/uploads 에 쓴다)"""
        real = os.path.join(ROOT, "data", "uploads")
        before = set(os.listdir(real)) if os.path.isdir(real) else set()
        self.assertNotEqual(os.path.realpath(self.state.UPLOADS_DIR), os.path.realpath(real))
        for make in xlsx_bombs.BOMBS.values():
            self.client.post("/api/cad/order/counts", files={"order": ("o.xlsx", make(), "application/octet-stream")},
                             headers={"Authorization": STAFF})
            self.client.post("/api/order/parse", files={"file": ("o.xlsx", make(), "application/octet-stream")},
                             headers={"Authorization": STAFF})
        after = set(os.listdir(real)) if os.path.isdir(real) else set()
        self.assertEqual(after - before, set())

    def test_6_me_lists_markerable(self):
        j = self.client.get("/api/cad/me", headers={"Authorization": STAFF}).json()
        self.assertEqual(sorted(j["markerable"]), sorted([SID, BID]))


@unittest.skipIf(SKIP, "GRADER_SKIP_ENGINE_TESTS=1")
class CadMarkerEngine(_Base, _Jobs):
    @classmethod
    def setUpClass(cls):
        cls.start_env(require_auth=True)
        up = mock.patch.object(cls.state, "UPLOADS_DIR", os.path.join(cls.tmp, "uploads")); up.start(); cls.patches.append(up)
        vend = os.path.join(ROOT, "vendor", "pattern_engine")
        sys.path.insert(0, vend)
        import importlib
        cls.svc = importlib.import_module("service")
        # v1 = 서버 엔진(사본)으로 만든 가스 상의 — AAMA 없이(시간 절약)
        res = cls.svc.rebuild(os.path.join(cls.tmp, "v1"), groups=["top"], aama=False)
        s = res["styles"][SID]
        with open(s["view"], "rb") as fv, open(s["zip"], "rb") as fz:
            r = cls.upload(fv.read(), fz.read(), headers={"Authorization": ADMIN})
        assert r.status_code == 201, r.text
        cls.graded_v1 = os.path.join(cls.tmp, "v1", "gas-warmup", "graded", "graded.json")   # v1 을 만든 그레이딩(명령줄 견주기용)
        cls.runs = {}

    @classmethod
    def tearDownClass(cls):
        cls.stop_env()

    def run_marker(self, key, body, tok=STAFF):
        if key not in self.runs:
            t0 = time.time()
            r = self.client.post(f"/api/cad/styles/{SID}/v/1/marker", json=body, headers={"Authorization": tok})
            self.assertEqual(r.status_code, 202, r.text)
            jid = r.json()["job_id"]
            self.runs[key] = (jid, self.wait_job(jid, tok=tok), round(time.time() - t0, 1))
        return self.runs[key]

    def cli(self, res, tag):
        """stizshop 정본 marker.py 명령줄 — 같은 graded.json · 같은 인자(service.marker_argv)"""
        out = os.path.join(self.tmp, "cli-" + tag)
        argv = self.svc.marker_argv(self.graded_v1, out, res["request"], name="cli")
        eng = STIZ_ENGINE if os.path.isfile(os.path.join(STIZ_ENGINE, "marker.py")) else os.path.join(ROOT, "vendor", "pattern_engine")
        r = subprocess.run([sys.executable, os.path.join(eng, "marker.py"), *argv], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        with open(os.path.join(out, "cli.json"), encoding="utf-8") as f:
            return json.load(f)

    def check_same(self, key, body):
        jid, j, secs = self.run_marker(key, body)
        self.assertEqual(j["status"], "done", j.get("error"))
        res = j["result"]
        srv = self.client.get(res["files"]["json"]["url"], headers={"Authorization": STAFF}).json()
        with open(self.graded_v1, "rb") as f:
            self.assertEqual(sha(f.read()), res["graded_sha256"])                          # 서버가 다시 만든 그레이딩 = v1 을 만든 그레이딩
        cli = self.cli(res, key)
        key_of = lambda S: [(q["id"], q["rot"], q["flip"], q["dx"], q["dy"]) for q in S["placements"]]
        s, m, v = res["summary"], res["memory"], res["verify"]
        print(f"\n[마커 · {key}] {s['length_m']} m · 벌당 {s['yield_m_per_bundle']} m · 효율 {s['efficiency_pct']}% · 조각 {s['piece_count']}"
              f" · 탐색 한도 걸림 {s.get('search', {}).get('time_budget_hit')} · 명령줄 {cli['length_m']} m"
              f" · 일꾼 최고 {m['worker_max_mb']} MB(그레이딩 {m['graded_worker_mb']}) · 서버 {m['server_peak_mb']} MB · {secs}초")
        self.assertEqual((s["length_m"], s["efficiency_pct"], s["piece_count"]), (cli["length_m"], cli["efficiency_pct"], cli["piece_count"]))
        self.assertEqual(key_of(srv), key_of(cli))                                         # 조각 자리(회전·이동)까지 전부 같다
        self.assertTrue(v["ok"], v)
        self.assertEqual((v["overlaps"], v["outside"], v["flipped"]), (0, 0, 0))
        self.assertTrue(set(v["rotations"]) <= {0, 180})
        self.assertGreaterEqual(v["min_gap_mm"], 3.0 - 0.01)
        self.assertEqual(res["view_match"]["diffs"], [])
        self.assertLessEqual(res["view_match"]["max_mm"], 0.05)
        self.assertLess(m["worker_max_mb"], 512)
        return res

    def test_1_quick_same_as_cli(self):
        res = self.check_same("quick", {"width_cm": 150, "gap_mm": 3, "counts": {s: 1 for s in SIZES}, "quick": True})
        self.assertEqual(res["summary"]["piece_count"], 17 * 8)
        for k in ("pdf", "dxf", "png"):
            d = self.client.get(res["files"][k]["url"], headers={"Authorization": STAFF})
            self.assertEqual((d.status_code, sha(d.content)), (200, res["files"][k]["sha256"]), k)
        self.assertTrue(self.client.get(res["files"]["png"]["url"], headers={"Authorization": STAFF}).content.startswith(b"\x89PNG"))

    @unittest.skipUnless(FULL, "GRADER_MARKER_FULL_TEST=1 일 때만(관리자 여러 번 깔기 — 약 3분)")
    def test_2_admin_search_within_wall_clock(self):
        """관리자 «여러 번 깔기» — 벽시계 한도(전체 180초) 안에서 끝나고, 빠르게보다 길지 않고, 규칙(겹침·식서)을 지킨다.
        ⚠️ 한도에 걸린 탐색은 «어디서 멈췄나» 가 기계 속도에 달려 명령줄과 같음을 보장하지 않는다 — 같음은 빠르게(test_1)로 본다"""
        jid, j, secs = self.run_marker("search", {"width_cm": 150, "gap_mm": 3, "counts": {s: 1 for s in SIZES}, "quick": False}, tok=ADMIN)
        self.assertEqual(j["status"], "done", j.get("error"))
        res = j["result"]; s, v = res["summary"], res["verify"]
        quick = self.run_marker("quick", {"width_cm": 150, "gap_mm": 3, "counts": {s: 1 for s in SIZES}, "quick": True})[1]["result"]["summary"]
        print(f"\n[여러 번 깔기] {s['length_m']} m(빠르게 {quick['length_m']} m) · 효율 {s['efficiency_pct']}% · 깔기 {s['search']['tries']}번"
              f" · 한도 걸림 {s['search']['time_budget_hit']} · {secs}초 · 일꾼 최고 {res['memory']['worker_max_mb']} MB")
        self.assertFalse(res["request"]["quick"])
        self.assertLess(secs, self.cad.MARKER_TIMEOUT_S_DEFAULT)
        self.assertLessEqual(s["length_m"], quick["length_m"])
        self.assertTrue(v["ok"], v)

    def test_3_narrow_fabric_korean_error(self):
        jid, j, _ = self.run_marker("narrow", {"width_cm": 50, "gap_mm": 3, "counts": {"M": 1}, "quick": True})
        self.assertEqual(j["status"], "error")
        self.assertIn("원단에 깔지 못했습니다", j["error"])
        self.assertNotIn("Traceback", j["error"])


if __name__ == "__main__":
    unittest.main()
