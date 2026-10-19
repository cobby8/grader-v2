# -*- coding: utf-8 -*-
"""엔진 사본 지문 시험 — vendor/pattern_engine 이 ENGINE_VERSION.json 과 같은가 (F10 2단계)

왜(비유): 사본에 찍힌 도장(지문)과 사본 내용이 다르면 «누가 사본을 몰래 고쳤다» 는 뜻이다.
  엔진 정본은 stizshop tools/pattern-engine 하나 — 고칠 때는 거기서 고치고 scripts/sync_pattern_engine.py 로 다시 베낀다.
  ① 목록의 파일이 전부 있고 지문이 같다  ② 목록에 없는 파일이 사본 폴더에 끼어 있지 않다
  ③ 엔진이 쓰는 라이브러리 판(requirements)이 그레이더 requirements.txt 와 같다(Render 가 같은 판을 깐다)
실행(저장소 루트): python -m unittest tests.test_engine_vendor -v
"""
import hashlib
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "vendor", "pattern_engine")
TEXT_EXT = (".py", ".json", ".txt", ".md")
KEEP = {"ENGINE_VERSION.json", ".gitattributes"}


def file_sha(path):
    """scripts/sync_pattern_engine.py 와 같은 규칙 — 글자 파일은 CRLF → LF 로 본다"""
    with open(path, "rb") as f:
        b = f.read()
    if path.lower().endswith(TEXT_EXT):
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def pins(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*([A-Za-z0-9_.-]+)==([^\s#]+)", line)
            if m:
                out[m.group(1).lower()] = m.group(2)
    return out


class EngineVendor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(VENDOR, "ENGINE_VERSION.json"), encoding="utf-8") as f:
            cls.ev = json.load(f)

    def test_has_version_stamp(self):
        self.assertEqual(self.ev.get("engine"), "stizshop tools/pattern-engine")
        self.assertRegex(self.ev.get("commit") or "", r"^[0-9a-f]{40}$")
        self.assertIn("service.py", self.ev["files"])
        self.assertIn("fixtures/gas-warmup-2026/gas_top_2xl.ai", self.ev["files"])
        self.assertIn("marker.py", self.ev["files"])             # F10 4단계 — 창구(service.marker_all)가 import 해서 따라 들어온다
        self.assertIn("style_import.py", self.ev["files"])       # F10 6단계 — 창구(service.import_all)가 import 해서 따라 들어온다
        self.assertNotIn("stiz_notch_add.py", self.ev["files"])  # 창구가 안 쓰는 파일은 안 가져온다(다른 작업자 영역)

    def test_fingerprints_match(self):
        bad = []
        for rel, want in self.ev["files"].items():
            p = os.path.join(VENDOR, *rel.split("/"))
            if not os.path.isfile(p):
                bad.append(f"없음: {rel}")
            elif file_sha(p) != want:
                bad.append(f"지문 다름: {rel}")
        self.assertEqual(bad, [], "엔진 사본이 손으로 바뀌었다 — stizshop 에서 고치고 scripts/sync_pattern_engine.py 를 다시 돌리세요")

    def test_no_stray_files(self):
        extra = []
        for d, dirs, names in os.walk(VENDOR):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for nm in names:
                rel = os.path.relpath(os.path.join(d, nm), VENDOR).replace("\\", "/")
                if rel not in self.ev["files"] and rel not in KEEP:
                    extra.append(rel)
        self.assertEqual(extra, [], "사본 폴더에 목록에 없는 파일이 있다")

    def test_requirements_pinned_same(self):
        eng, app = pins(os.path.join(VENDOR, "requirements.txt")), pins(os.path.join(ROOT, "requirements.txt"))
        for name, ver in eng.items():
            self.assertEqual(app.get(name), ver, f"그레이더 requirements.txt 에 {name}=={ver} 가 있어야 한다")

    def test_synced_from_clean_commit(self):
        """복사할 때 stizshop 엔진 파일이 전부 커밋돼 있었다 — 판 표시(커밋 번호)를 믿을 수 있다"""
        self.assertEqual(self.ev.get("dirty_files"), [], "stizshop 을 커밋한 뒤 scripts/sync_pattern_engine.py 를 다시 돌리세요")

    def test_numpy_pinned(self):
        self.assertRegex(pins(os.path.join(ROOT, "requirements.txt")).get("numpy", ""), r"^\d+\.\d+\.\d+$")

    def test_docker_build_runs_this_test(self):
        """배포 이미지 빌드가 이 시험을 돌린다(지문이 다르면 빌드 실패) — 코드 복사 «뒤» 에 있어야 의미가 있다"""
        with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
            lines = [l.strip() for l in f]
        run = [i for i, l in enumerate(lines) if l == "RUN python -m unittest tests.test_engine_vendor"]
        copy = [i for i, l in enumerate(lines) if l.startswith("COPY . .")]
        self.assertTrue(run and copy and run[0] > copy[0])

    def test_dockerignore_keeps_vendor_and_drops_keys(self):
        with open(os.path.join(ROOT, ".dockerignore"), encoding="utf-8") as f:
            pats = [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
        self.assertIn("stiz-*.json", pats)                                   # 서비스 계정 열쇠 파일은 이미지에 안 넣는다
        for p in pats:                                                       # 지문 시험에 필요한 것은 빠지면 안 된다
            self.assertFalse(p.rstrip("/") in ("vendor", "vendor/pattern_engine", "tests", "*.ai", "*.json"), p)

    def test_tamper_is_detected(self):
        """거짓 통과 점검 — 한 바이트만 바꿔도 지문이 달라진다"""
        p = os.path.join(VENDOR, "service.py")
        with open(p, "rb") as f:
            b = f.read()
        self.assertNotEqual(hashlib.sha256(b + b" ").hexdigest(), self.ev["files"]["service.py"])


if __name__ == "__main__":
    unittest.main()
