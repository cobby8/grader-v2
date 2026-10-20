# -*- coding: utf-8 -*-
"""재단 패턴 엔진 복사본 맞추기 — stizshop tools/pattern-engine → vendor/pattern_engine (F10 2단계)

왜 이 파일이 있나(비유):
  엔진의 «원본 장부» 는 stizshop 저장소 하나뿐이다(시험·골든이 거기 있다). 그레이더는 그 장부의 «도장 찍힌 사본» 만 쓴다.
  이 스크립트가 옆 폴더 stizshop 에서 필요한 파일만 베껴 오고, 어느 판(커밋)에서 베꼈는지와 파일마다 지문(sha256)을
  ENGINE_VERSION.json 에 적는다. tests/test_engine_vendor.py 가 지문을 대조하므로 사본을 손으로 고치면 시험이 실패한다.
  → 엔진을 고칠 때는 언제나 stizshop 에서 고치고, 커밋한 뒤 이 스크립트를 다시 돌린다.

무엇을 베끼나:
  service.py(창구)에서 출발해 «서로 import 하는 엔진 파일» 을 끝까지 따라간 묶음 + 창구가 돌리는 스크립트 2개
  + requirements.txt + 원본 .ai 4개(fixtures/gas-warmup-2026). 🚫 창구가 안 쓰는 파일은 안 가져온다.
  F10 6단계부터 창구가 들여오기를 부르므로(service.import_all → import style_import) style_import.py 도 «import 따라가기» 로 들어온다.
  F10 4단계부터 창구가 마커를 부르므로(service.marker_all → import marker) marker.py 도 «import 따라가기» 로 저절로 들어온다
  — 목록을 손으로 적지 않는다(창구가 쓰는 것 = 복사하는 것).
  글자 파일(.py·.json·.txt)은 줄바꿈을 LF 로 맞춰 베끼고 그 바이트로 지문을 낸다(git 이 저장하는 모양과 같다).

실행(저장소 루트):
  python scripts/sync_pattern_engine.py                 # 베끼기 + ENGINE_VERSION.json
  python scripts/sync_pattern_engine.py --check         # 베끼지 않고 «사본이 stizshop 지금 파일과 같은가» 만 (다르면 종료 코드 1)
  옵션: --src <stizshop/tools/pattern-engine>  (기본: 옆 폴더 ../stizshop/tools/pattern-engine, 또는 환경변수 STIZSHOP_ENGINE_DIR)
"""
from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "vendor", "pattern_engine")
DEFAULT_SRC = os.environ.get("STIZSHOP_ENGINE_DIR") or os.path.join(os.path.dirname(ROOT), "stizshop", "tools", "pattern-engine")
ROOTS = ["service.py", "gas_warmup_build.py", "gas_warmup_grade.py",   # 창구 + 창구가 runpy 로 돌리는 스크립트(import 로는 안 잡힌다)
         "preset_export.py"]    # 노치 일꾼(webapp/notch_child.py)이 쓰는 입구 — notch_rules·illustrator·notching 이 import 로 따라온다(2026-10-20)
EXTRA = ["requirements.txt"]
FIXTURES = ["fixtures/gas-warmup-2026/gas_top_2xl.ai", "fixtures/gas-warmup-2026/gas_bottom_2xl.ai",
            "fixtures/gas-warmup-2026/std_warmup_top.ai", "fixtures/gas-warmup-2026/std_warmup_pants.ai"]
TEXT_EXT = (".py", ".json", ".txt", ".md")
KEEP = {"ENGINE_VERSION.json", ".gitattributes"}                     # 사본 폴더에서 지우지 않는 «이 저장소 것»
GITATTR = "# 엔진 사본은 바이트 그대로 둔다 — 줄바꿈 변환이 끼면 지문 시험이 헛 실패한다\n* -text\n"


def file_bytes(path: str) -> bytes:
    """지문을 낼 바이트 — 글자 파일은 CRLF → LF(워크트리마다 줄바꿈이 달라도 같은 지문)"""
    with open(path, "rb") as f:
        b = f.read()
    return b.replace(b"\r\n", b"\n") if path.lower().endswith(TEXT_EXT) else b


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def local_imports(path: str, src: str) -> set:
    """이 파일이 import 하는 «같은 폴더의 엔진 파일» 이름들(함수 안 import 까지)"""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return {n + ".py" for n in names if os.path.isfile(os.path.join(src, n + ".py"))}


def engine_files(src: str) -> list:
    """창구에서 출발해 import 를 따라간 엔진 파일 전부(정렬) + 덧붙일 파일"""
    todo, seen = list(ROOTS), set()
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        if not os.path.isfile(os.path.join(src, f)):
            raise SystemExit(f"엔진 파일이 없다: {os.path.join(src, f)}")
        seen.add(f)
        todo.extend(local_imports(os.path.join(src, f), src) - seen)
    return sorted(seen) + EXTRA + FIXTURES


def git(src: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=src, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return r.stdout.rstrip() if r.returncode == 0 else ""     # 앞 공백은 남긴다 — status 첫 줄 « M 파일» 의 자리가 밀리지 않게
    except Exception:
        return ""


def dirty_files(src: str, files: list) -> list:
    """stizshop 에서 커밋 안 된(바뀐·새) 엔진 파일 — 이것이 있으면 «그 커밋 판» 이라고 믿으면 안 된다"""
    out = git(src, "status", "--porcelain", "--", *files)
    res = []
    for line in out.splitlines():
        p = line[3:].strip().strip('"')
        res.append(p.replace("\\", "/"))
    return sorted(res)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="엔진 사본 맞추기(stizshop → vendor/pattern_engine)")
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--check", action="store_true", help="베끼지 않고 비교만")
    a = ap.parse_args(argv)
    src = os.path.abspath(a.src)
    if not os.path.isfile(os.path.join(src, "service.py")):
        print(f"stizshop 엔진 폴더를 못 찾았다: {src} (--src 로 알려 주세요)"); return 2
    files = engine_files(src)
    if a.check:
        with open(os.path.join(DEST, "ENGINE_VERSION.json"), encoding="utf-8") as f:
            ev = json.load(f)
        diff = [p for p in files if ev["files"].get(p) != sha256(file_bytes(os.path.join(src, p)))]
        gone = sorted(set(ev["files"]) - set(files))
        print(f"사본 판 {ev.get('commit_short')} · stizshop 지금 {git(src, 'rev-parse', '--short=8', 'HEAD')}")
        print("같다 — 다시 맞출 것 없음" if not (diff or gone) else f"다르다: {diff + gone}")
        return 1 if (diff or gone) else 0
    os.makedirs(DEST, exist_ok=True)
    fp = {}
    for p in files:
        b = file_bytes(os.path.join(src, p))
        dst = os.path.join(DEST, *p.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(b)
        fp[p] = sha256(b)
    # 목록에 없는 옛 파일 지우기 — 사본 폴더 안에서만
    for d, dirs, names in os.walk(DEST, topdown=False):
        for nm in names:
            rel = os.path.relpath(os.path.join(d, nm), DEST).replace("\\", "/")
            if rel not in fp and rel not in KEEP:
                os.remove(os.path.join(d, nm))
        for dn in dirs:
            full = os.path.join(d, dn)
            if dn == "__pycache__":
                shutil.rmtree(full, ignore_errors=True)
            elif os.path.isdir(full) and not os.listdir(full):
                os.rmdir(full)
    with open(os.path.join(DEST, ".gitattributes"), "w", encoding="utf-8", newline="\n") as f:
        f.write(GITATTR)
    head = git(src, "rev-parse", "HEAD")
    dirty = dirty_files(src, [p for p in files])
    ev = {"engine": "stizshop tools/pattern-engine", "commit": head or None, "commit_short": head[:8] if head else None,
          "dirty_files": dirty, "synced_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
          "note": "🚫 이 폴더를 손으로 고치지 마라 — stizshop 에서 고치고 scripts/sync_pattern_engine.py 를 다시 돌린다",
          "files": fp}
    with open(os.path.join(DEST, "ENGINE_VERSION.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"엔진 사본 {len(fp)}개 → {DEST}")
    print(f"stizshop 판 {ev['commit_short']}" + (f" · ⚠️ 커밋 안 된 파일 {len(dirty)}개: {', '.join(dirty)}" if dirty else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
