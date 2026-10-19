# -*- coding: utf-8 -*-
"""재단 패턴(F10 1단계 «보기 전용») — 스타일·버전 창고 + /api/cad/* 라우터.

왜 이 파일이 있나(비유):
  stizshop 의 패턴 엔진이 미리 만든 «화면용 그림 자료(view.json)» 와 «공장용 산출물 묶음(exports.zip)» 을
  관리자가 올리면, 이 서버는 그것을 «사진첩» 처럼 보관하고 직원에게 보여 주기만 한다.
  서버에는 패턴 엔진이 없다(1단계 — 메모리·빌드 위험 0). 계산은 전부 stizshop 에서 끝나 있다.

저장 구조:
  디스크  data/cad/{style_id}/v{n}/view.json · exports.zip · meta.json   (+ backup.json = 이 서버의 백업 기록, 창고엔 안 올림)
  창고    Supabase Storage 비공개 창고 «pattern-cad»
            {style_id}/v{n}/view · exports · meta        ← 열쇠는 영문 소문자·숫자·-·/ 만 (07-09 한글 열쇠 무음 실패 사고)
  버전은 «덮어쓰지 않고 늘린다» — 같은 스타일을 다시 올리면 v2, v3 … 옛 버전은 그대로 남는다.

권한:
  🔒 보기·내려받기 = 로그인 직원 (main.py 가 /api 전역에 require_auth 를 건다)
  🛡 올리기 = 관리자 (admin_required)
  창고 쓰기·읽기는 «요청자 로그인 토큰을 그대로 넘긴다» — 비밀키를 쓰지 않는다(storage_backup.py 와 같은 원칙).
  창고 규칙: 읽기 = 로그인(authenticated) · 쓰기 = 관리자 · 덮어쓰기(UPDATE)·삭제 규칙 없음.

재배포 복원:
  창고 읽기가 «로그인 사용자만» 이라 부팅 때(토큰 없음)는 읽을 수 없다(비밀키 금지).
  그래서 «로그인한 사람이 처음 목록을 열 때» 그 사람 토큰으로 디스크에 없는 버전만 내려받아 복원한다(10분에 한 번).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import threading
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from . import state
from .auth import admin_required, auth_required

router = APIRouter(prefix="/api/cad", tags=["cad"])

# ── 상수 ────────────────────────────────────────────────────────────────
BUCKET = "pattern-cad"
VIEW_FORMAT = "stiz-cad-view"
# ⚠️ 세 정규식은 반드시 fullmatch 로 쓴다 — `$` 는 끝의 줄바꿈 하나를 봐줘서 "abc\n" 이 통과한다(검증 리뷰 지적)
STYLE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]")         # 영문 소문자·숫자·- 만(디스크 폴더·창고 열쇠에 그대로 쓴다)
KEY_RE = re.compile(r"[a-z0-9/-]+")                                  # 창고 열쇠 검사 — 한글·점·공백이 섞이면 올리지 않는다
ZIP_MEMBER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]*")           # ZIP 안 이름 — 영문·숫자만(stizshop cad_view.py 가 그렇게 만든다)
MAX_VIEW_BYTES = 20 * 1024 * 1024
MAX_ZIP_BYTES = 50 * 1024 * 1024                                     # 창고 file_size_limit 와 같다
MAX_UNZIPPED_TOTAL = 200 * 1024 * 1024                               # ZIP 을 풀었을 때 합계 상한(압축 폭탄 방어)
MAX_UNZIPPED_FILE = 60 * 1024 * 1024                                 # ZIP 안 파일 하나 상한
MAX_ZIP_MEMBERS = 2000
OBJECTS = (("view.json", "view", "application/json"), ("exports.zip", "exports", "application/zip"),
           ("meta.json", "meta", "application/json"))               # (디스크 이름, 창고 이름, 종류)
FILE_KINDS = {                                                       # 내려받기 kind → (보통 종류, 설명)
    "zip": ("application/zip", "산출물 전체 ZIP"),
    "dxf": ("application/dxf", "사이즈별 DXF"),
    "pdf": ("application/pdf", "사이즈별 1:1 PDF"),
    "ai": ("application/postscript", "사이즈별 .ai"),
    "aama": ("application/dxf", "AAMA 기준 사이즈 DXF"),
    "rul": ("text/plain; charset=utf-8", "AAMA 규칙표 RUL"),
    "allsizes": ("application/dxf", "전 사이즈 겹친 DXF"),
    "a4": ("application/pdf", "A4 분할 PDF"),
}
_HTTP_TIMEOUT = 30.0
_RESTORE_EVERY = 600.0                                               # 복원 확인 간격(초)

_LOCK = threading.Lock()                                             # 올리기·복원이 같은 폴더를 동시에 만지지 않게
_last_restore = {"at": 0.0, "result": None, "busy": False}           # 복원 시각·결과 — 읽고 쓰기는 _LOCK 안에서만


# ══════════════════════════════════════════════════════════════════════
#  디스크
# ══════════════════════════════════════════════════════════════════════
def cad_dir() -> str:
    """data/cad 폴더(환경변수 GRADER_CAD_DIR 로 바꿀 수 있다 — 시험용)."""
    d = os.environ.get("GRADER_CAD_DIR") or os.path.join(state.PROJECT_ROOT, "data", "cad")
    os.makedirs(d, exist_ok=True)
    return d


def _check_style_id(style_id: str) -> str:
    if not isinstance(style_id, str) or not STYLE_ID_RE.fullmatch(style_id):
        raise HTTPException(status_code=400, detail="스타일 번호는 영문 소문자·숫자·- 만 쓸 수 있습니다(3~64자).")
    return style_id


def _versions_on_disk(style_id: str) -> List[int]:
    d = os.path.join(cad_dir(), style_id)
    if not os.path.isdir(d):
        return []
    out = []
    for nm in os.listdir(d):
        m = re.fullmatch(r"v([1-9][0-9]{0,5})", nm)
        if m and os.path.isfile(os.path.join(d, nm, "meta.json")):
            out.append(int(m.group(1)))
    return sorted(out)


def _vdir(style_id: str, ver: int) -> str:
    return os.path.join(cad_dir(), style_id, f"v{ver}")


def _read_meta(style_id: str, ver: int) -> Optional[Dict[str, Any]]:
    try:
        with open(os.path.join(_vdir(style_id, ver), "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_backup(style_id: str, ver: int) -> Optional[Dict[str, Any]]:
    try:
        with open(os.path.join(_vdir(style_id, ver), "backup.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _resolve_ver(style_id: str, ver: str) -> int:
    vs = _versions_on_disk(style_id)
    if not vs:
        raise HTTPException(status_code=404, detail="그 스타일이 없습니다.")
    if ver == "latest":
        return vs[-1]
    if not re.fullmatch(r"[1-9][0-9]{0,5}", ver or "") or int(ver) not in vs:
        raise HTTPException(status_code=404, detail="그 버전이 없습니다.")
    return int(ver)


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_version(style_id: str, ver: int, blobs: Dict[str, bytes]) -> None:
    """임시 폴더에 다 쓴 뒤 이름만 바꿔 넣는다 — 반쯤 쓴 버전이 목록에 보이지 않게."""
    final = _vdir(style_id, ver)
    if os.path.exists(final):
        raise HTTPException(status_code=409, detail=f"v{ver} 이 이미 있습니다(덮어쓰지 않습니다).")
    tmp = final + f".tmp-{os.getpid()}-{int(time.time() * 1000)}"
    os.makedirs(tmp)
    try:
        for name, data in blobs.items():
            with open(os.path.join(tmp, name), "wb") as f:
                f.write(data)
        os.replace(tmp, final)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


# ══════════════════════════════════════════════════════════════════════
#  창고(Supabase Storage) — 요청자 토큰을 그대로 넘긴다(비밀키 없음)
# ══════════════════════════════════════════════════════════════════════
def _sb_config() -> Tuple[Optional[str], Optional[str]]:
    base = os.environ.get("SUPABASE_URL"); pub = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if not base or not pub:
        return None, None
    return base.rstrip("/"), pub


def _bearer(request: Request) -> Optional[str]:
    authz = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if authz.lower().startswith("bearer "):
        tok = authz.split(" ", 1)[1].strip()
        return tok or None
    return None


def object_key(style_id: str, ver: int, name: str) -> str:
    """창고 열쇠 — 영문 소문자·숫자·-·/ 만. 어기면 예외(조용히 실패하지 않게)."""
    key = f"{style_id}/v{ver}/{name}"
    if not KEY_RE.fullmatch(key):
        raise ValueError(f"창고 열쇠에 쓸 수 없는 글자: {key!r}")
    return key


def _sb_headers(pub: str, jwt: str, ctype: Optional[str] = None) -> Dict[str, str]:
    h = {"apikey": pub, "Authorization": f"Bearer {jwt}"}
    if ctype:
        h["Content-Type"] = ctype
    return h


def _sb_upload(key: str, data: bytes, ctype: str, jwt: str) -> Tuple[bool, str]:
    base, pub = _sb_config()
    try:
        r = httpx.post(f"{base}/storage/v1/object/{BUCKET}/{key}", content=data,
                       headers=_sb_headers(pub, jwt, ctype), timeout=_HTTP_TIMEOUT)   # x-upsert 없음 = 덮어쓰기 금지
    except Exception as e:
        return False, f"네트워크 {type(e).__name__}"
    if r.status_code in (200, 201):
        return True, "ok"
    return False, f"status {r.status_code}"


def _sb_download(key: str, jwt: str) -> Optional[bytes]:
    base, pub = _sb_config()
    try:
        r = httpx.get(f"{base}/storage/v1/object/{BUCKET}/{key}", headers=_sb_headers(pub, jwt), timeout=_HTTP_TIMEOUT)
    except Exception:
        return None
    return r.content if r.status_code == 200 else None


def _sb_list(prefix: str, jwt: str) -> Optional[List[Dict[str, Any]]]:
    base, pub = _sb_config()
    try:
        r = httpx.post(f"{base}/storage/v1/object/list/{BUCKET}", headers=_sb_headers(pub, jwt, "application/json"),
                       json={"prefix": prefix, "limit": 1000, "offset": 0}, timeout=_HTTP_TIMEOUT)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        items = r.json()
    except Exception:
        return None
    return items if isinstance(items, list) else None


def backup_version(style_id: str, ver: int, jwt: Optional[str]) -> Dict[str, Any]:
    """디스크의 한 버전을 창고에 올리고 «되읽어» 지문을 맞춰 본다. 실패해도 예외를 던지지 않는다."""
    base, pub = _sb_config()
    if not base:
        res = {"ok": False, "skipped": True, "reason": "창고 미설정(로컬)"}
    elif not jwt:
        res = {"ok": False, "skipped": True, "reason": "로그인 토큰 없음(로컬 무인증)"}
    else:
        res = {"ok": True, "objects": {}}
        for disk_name, store_name, ctype in OBJECTS:
            with open(os.path.join(_vdir(style_id, ver), disk_name), "rb") as f:
                data = f.read()
            key = object_key(style_id, ver, store_name)
            ok, why = _sb_upload(key, data, ctype, jwt)
            back = _sb_download(key, jwt) if ok else None                   # 되읽기 — 올라간 것이 정말 같은가
            verified = back is not None and _sha256(back) == _sha256(data)
            res["objects"][store_name] = {"key": key, "uploaded": ok, "verified": verified, "reason": why, "bytes": len(data)}
            if not verified:
                res["ok"] = False
        if not res["ok"]:
            res["reason"] = "일부 파일이 창고에 올라가지 않았거나 되읽은 지문이 다릅니다"
    res["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(os.path.join(_vdir(style_id, ver), "backup.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    tag = "성공" if res.get("ok") else ("건너뜀" if res.get("skipped") else "실패")
    print(f"[cad] 창고 백업 {tag}: {style_id} v{ver}")                       # 토큰·키는 남기지 않는다
    return res


def restore_missing_with_token(jwt: Optional[str], force: bool = False) -> Dict[str, Any]:
    """창고에는 있는데 디스크에 없는 버전을 내려받는다(로그인 사용자 토큰으로). 10분에 한 번만.

    기존 storage_backup.restore_missing 과 같은 원칙: 디스크 우선(있는 것은 안 건드림) · 이상한 이름은 건너뜀 ·
    meta 의 지문과 다르면 버린다 · 예외를 밖으로 던지지 않는다.
    """
    base, _ = _sb_config()
    if not base or not jwt:
        return {"restored": 0, "skipped": True}
    with _LOCK:                                                             # 시각 확인과 «복원 중» 표시를 한 번에(두 요청이 겹쳐 돌지 않게)
        if _last_restore["busy"]:
            return {"restored": 0, "busy": True}
        if not force and time.time() - _last_restore["at"] < _RESTORE_EVERY:
            return {"restored": 0, "cached": True, "last": _last_restore["result"]}
        _last_restore["busy"] = True
    restored, errors, listed = 0, 0, False
    try:
        top = _sb_list("", jwt)
        if top is None:
            return {"restored": 0, "error": "창고 목록을 읽지 못했습니다"}      # 실패 — 시각을 남기지 않아 다음 요청이 다시 시도한다
        listed = True
        for it in top:
            sid = it.get("name") if isinstance(it, dict) else None
            if not isinstance(sid, str) or not STYLE_ID_RE.fullmatch(sid) or it.get("id") is not None:
                continue                                                    # 폴더(id 없음)만 · 이름 검사
            vers = _sb_list(sid + "/", jwt) or []
            for v in vers:
                vn = v.get("name") if isinstance(v, dict) else None
                m = re.fullmatch(r"v([1-9][0-9]{0,5})", vn or "")
                if not m or v.get("id") is not None:
                    continue
                ver = int(m.group(1))
                if os.path.isdir(_vdir(sid, ver)):
                    continue                                                # 디스크 우선
                try:
                    blobs = {}
                    for disk_name, store_name, _c in OBJECTS:
                        b = _sb_download(object_key(sid, ver, store_name), jwt)
                        if b is None:
                            raise ValueError("내려받기 실패")
                        blobs[disk_name] = b
                    meta = json.loads(blobs["meta.json"].decode("utf-8"))
                    if (meta.get("view_sha256") != _sha256(blobs["view.json"]) or
                            meta.get("zip_sha256") != _sha256(blobs["exports.zip"]) or meta.get("style_id") != sid
                            or meta.get("version") != ver):
                        raise ValueError("지문 불일치")
                    with _LOCK:
                        if not os.path.isdir(_vdir(sid, ver)):
                            _write_version(sid, ver, blobs)
                            with open(os.path.join(_vdir(sid, ver), "backup.json"), "w", encoding="utf-8") as f:
                                json.dump({"ok": True, "restored": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
                            restored += 1
                            print(f"[cad] 창고에서 복원: {sid} v{ver}")
                except Exception as e:
                    errors += 1
                    print(f"[cad] 복원 건너뜀: {sid} v{ver} - {type(e).__name__}")
    except Exception as e:
        listed = False
        print(f"[cad] 복원 중 오류(무시): {type(e).__name__}")
    finally:
        with _LOCK:
            _last_restore["busy"] = False
            if listed:                                                      # 목록을 끝까지 읽었을 때만 «확인함» 으로 기록
                _last_restore["at"] = time.time()
                _last_restore["result"] = {"restored": restored, "errors": errors}
    return {"restored": restored, "errors": errors}


# ══════════════════════════════════════════════════════════════════════
#  올린 파일 검사
# ══════════════════════════════════════════════════════════════════════
def _is_num(v: Any) -> bool:
    """진짜 숫자인가(참·거짓·NaN·무한대 제외)"""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def validate_upload(view_bytes: bytes, zip_bytes: bytes) -> Dict[str, Any]:
    """view.json + exports.zip 가 서로 맞는지 본다. 틀리면 400(한국어 사유).

    모양이 이상한 자료(글자 자리에 목록 등)도 500 이 아니라 400 으로 — 마지막에 형식 오류를 통째로 잡는다.
    """
    try:
        return _validate_upload(view_bytes, zip_bytes)
    except HTTPException:
        raise
    except (TypeError, AttributeError, KeyError, ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"view.json 모양이 예상과 다릅니다({type(e).__name__}).")


def _validate_upload(view_bytes: bytes, zip_bytes: bytes) -> Dict[str, Any]:
    def bad(msg: str):
        raise HTTPException(status_code=400, detail=msg)
    if not view_bytes or len(view_bytes) > MAX_VIEW_BYTES:
        bad("view.json 이 비었거나 너무 큽니다(20MB 이하).")
    if not zip_bytes or len(zip_bytes) > MAX_ZIP_BYTES:
        bad("exports.zip 이 비었거나 너무 큽니다(50MB 이하).")
    try:
        view = json.loads(view_bytes.decode("utf-8"))
    except Exception:
        bad("view.json 을 읽지 못했습니다(JSON 형식이 아님).")
    if not isinstance(view, dict) or view.get("format") != VIEW_FORMAT:
        bad("view.json 형식이 다릅니다(stizshop tools/pattern-engine/cad_view.py 결과만 받습니다).")
    style = view.get("style")
    if not isinstance(style, dict):
        bad("view.json 의 style 은 객체여야 합니다.")
    sid = style.get("id")
    if not isinstance(sid, str) or not STYLE_ID_RE.fullmatch(sid):
        bad("view.json 의 스타일 번호(style.id)는 영문 소문자·숫자·- 만 쓸 수 있습니다.")
    for k in ("name", "garment", "base_size", "graded_from"):
        if style.get(k) is not None and not isinstance(style.get(k), str):
            bad(f"view.json 의 style.{k} 는 글자여야 합니다.")
    sizes = style.get("sizes")
    if not isinstance(sizes, list) or not sizes or not all(isinstance(x, str) and x for x in sizes):
        bad("view.json 의 style.sizes 는 사이즈 이름 목록이어야 합니다.")
    if not isinstance(view.get("sizes"), dict) or any(not isinstance(view["sizes"].get(x), dict) for x in sizes):
        bad("view.json 에 사이즈 자료가 빠져 있습니다.")
    for x in sizes:
        if not isinstance(view["sizes"][x].get("pieces"), list) or not isinstance(view["sizes"][x].get("checks", []), list):
            bad(f"view.json 사이즈 {x[:20]} 의 pieces·checks 는 목록이어야 합니다.")
    if not isinstance(style.get("pieces", []), list):
        bad("view.json 의 style.pieces 는 목록이어야 합니다.")
    # 화면이 숫자로 쓰는 값 — 숫자가 아니면 받지 않는다(글자가 화면 HTML 에 섞이지 않게)
    if not _is_num(view.get("q")) or view["q"] <= 0:
        bad("view.json 의 q(좌표 단위)는 양수여야 합니다.")
    for k in ("tol_check", "simplify"):
        if k in view and not (_is_num(view[k]) and view[k] >= 0):
            bad(f"view.json 의 {k} 는 숫자여야 합니다.")
    ez = view.get("exports_zip", {})
    if not isinstance(ez, dict):
        bad("view.json 의 exports_zip 은 객체여야 합니다.")
    if ez.get("sha256") is not None and (not isinstance(ez["sha256"], str) or ez["sha256"] != _sha256(zip_bytes)):
        bad("exports.zip 이 view.json 과 짝이 아닙니다(지문이 다름). 같은 때 만든 두 파일을 올려 주세요.")
    files = view.get("files", [])
    if not isinstance(files, list) or not all(isinstance(f, dict) for f in files):
        bad("view.json 의 files 는 객체 목록이어야 합니다.")
    for f in files:
        if not isinstance(f.get("path"), str) or not isinstance(f.get("sha256"), str) or not isinstance(f.get("kind"), str):
            bad("view.json 의 files 항목(path·sha256·kind)은 글자여야 합니다.")
        if f.get("size") is not None and not isinstance(f.get("size"), str):
            bad("view.json 의 files 항목 size 는 글자여야 합니다.")
        if f["kind"] not in FILE_KINDS:
            bad(f"모르는 파일 종류: {f['kind'][:20]}")
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        bad("exports.zip 이 ZIP 이 아닙니다.")
    with zf:
        infos = zf.infolist()
        # 압축 폭탄 방어 — 풀기 전에 «풀면 몇 바이트인가» 를 먼저 본다(작은 ZIP 이 수 GB 로 부푸는 것 차단)
        if len(infos) > MAX_ZIP_MEMBERS:
            bad(f"ZIP 안 파일이 너무 많습니다({MAX_ZIP_MEMBERS}개 이하).")
        if any(i.file_size > MAX_UNZIPPED_FILE for i in infos):
            bad(f"ZIP 안에 너무 큰 파일이 있습니다(파일 하나 {MAX_UNZIPPED_FILE // 2**20}MB 이하).")
        if sum(i.file_size for i in infos) > MAX_UNZIPPED_TOTAL:
            bad(f"ZIP 을 풀면 너무 큽니다(합계 {MAX_UNZIPPED_TOTAL // 2**20}MB 이하).")
        names = {i.filename for i in infos}
        for n in names:
            if not ZIP_MEMBER_RE.fullmatch(n) or ".." in n.split("/"):
                bad(f"ZIP 안 파일 이름에 쓸 수 없는 글자가 있습니다: {n[:80]}")
        for f in files:
            p = f["path"]
            if p not in names:
                bad(f"ZIP 에 빠진 파일: {p[:80]}")
            if _sha256(zf.read(p)) != f["sha256"]:
                bad(f"ZIP 안 파일 지문이 view.json 과 다릅니다: {p[:80]}")
    return view


# ══════════════════════════════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════════════════════════════
def _style_summary(style_id: str) -> Optional[Dict[str, Any]]:
    vs = _versions_on_disk(style_id)
    if not vs:
        return None
    metas = [m for m in (_read_meta(style_id, v) for v in vs) if m]
    if not metas:
        return None
    last = metas[-1]
    return {"id": style_id, "name": last.get("name"), "garment": last.get("garment"), "sizes": last.get("sizes"),
            "versions": vs, "latest": _public_meta(last, _read_backup(style_id, last.get("version")))}


def _public_meta(m: Dict[str, Any], backup: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = {k: m.get(k) for k in ("version", "uploaded_at", "uploaded_by", "note", "sizes", "size_labels", "files",
                                 "view_sha256", "zip_sha256", "view_bytes", "zip_bytes", "source")}
    out["backup"] = None if backup is None else {"ok": bool(backup.get("ok")), "skipped": bool(backup.get("skipped")),
                                                 "restored": bool(backup.get("restored")), "reason": backup.get("reason"),
                                                 "at": backup.get("at")}
    return out


def _can_upload(request: Request) -> bool:
    return (not auth_required()) or getattr(request.state, "role", None) == "admin"


@router.get("/me")
def cad_me(request: Request) -> Dict[str, Any]:
    """화면이 «올리기» 단추를 보여 줄지 묻는다(관리자이거나 로컬 무인증)."""
    base, _ = _sb_config()
    return {"can_upload": _can_upload(request), "auth_required": auth_required(), "storage": bool(base)}


@router.get("/styles")
def list_styles(request: Request) -> Dict[str, Any]:
    restore = restore_missing_with_token(_bearer(request))                 # 재배포 뒤 첫 로그인 사용자가 복원을 일으킨다
    out = []
    root = cad_dir()
    for sid in sorted(os.listdir(root)):
        if STYLE_ID_RE.fullmatch(sid) and os.path.isdir(os.path.join(root, sid)):
            s = _style_summary(sid)
            if s:
                out.append(s)
    return {"styles": out, "restore": restore}


@router.get("/styles/{style_id}")
def get_style(style_id: str, request: Request) -> Dict[str, Any]:
    _check_style_id(style_id)
    if not _versions_on_disk(style_id):
        restore_missing_with_token(_bearer(request))
    vs = _versions_on_disk(style_id)
    if not vs:
        raise HTTPException(status_code=404, detail="그 스타일이 없습니다.")
    s = _style_summary(style_id)
    if s is None:                                                           # meta.json 이 깨졌다 — 없는 것으로 본다
        raise HTTPException(status_code=404, detail="그 스타일의 정보(meta)를 읽지 못했습니다.")
    s["history"] = [_public_meta(m, _read_backup(style_id, v)) for v in vs for m in [_read_meta(style_id, v)] if m]
    return s


@router.get("/styles/{style_id}/v/{ver}/view")
def get_view(style_id: str, ver: str):
    _check_style_id(style_id)
    v = _resolve_ver(style_id, ver)
    return FileResponse(os.path.join(_vdir(style_id, v), "view.json"), media_type="application/json",
                        headers={"Cache-Control": "private, max-age=300", "X-Cad-Version": str(v)})


def _disposition(ascii_name: str, orig: Optional[str]) -> str:
    from urllib.parse import quote
    d = f'attachment; filename="{ascii_name}"'
    if orig and orig != ascii_name:
        d += f"; filename*=UTF-8''{quote(orig)}"
    return d


@router.get("/styles/{style_id}/v/{ver}/files/{kind}")
def get_file(style_id: str, ver: str, kind: str, size: Optional[str] = None):
    """kind=zip(전체) · dxf/pdf/ai(?size=S) · aama · rul · allsizes · a4 — 올린 그대로(지문 동일) 내려준다."""
    _check_style_id(style_id)
    v = _resolve_ver(style_id, ver)
    if kind not in FILE_KINDS:
        raise HTTPException(status_code=400, detail="파일 종류는 " + " · ".join(FILE_KINDS) + " 중 하나입니다.")
    vd = _vdir(style_id, v)
    meta = _read_meta(style_id, v) or {}
    if kind == "zip":
        name = f"{style_id}_v{v}.zip"
        return FileResponse(os.path.join(vd, "exports.zip"), media_type="application/zip",
                            headers={"Content-Disposition": _disposition(name, None), "X-Content-SHA256": meta.get("zip_sha256", "")})
    files = [f for f in (meta.get("files") or []) if f.get("kind") == kind]
    if size:
        files = [f for f in files if f.get("size") == size]
    elif len(files) > 1:
        raise HTTPException(status_code=400, detail="사이즈를 골라 주세요(?size=S 처럼). 있는 사이즈: "
                            + ", ".join(str(f.get("size")) for f in files))
    if not files:
        raise HTTPException(status_code=404, detail="그 파일은 이 버전에 없습니다.")
    f = files[0]
    with zipfile.ZipFile(os.path.join(vd, "exports.zip")) as zf:
        if zf.getinfo(f["path"]).file_size > MAX_UNZIPPED_FILE:              # 올릴 때 검사했지만 한 번 더(디스크 사본이 바뀐 경우)
            raise HTTPException(status_code=500, detail="저장된 파일이 비정상적으로 큽니다. 관리자에게 알려 주세요.")
        data = zf.read(f["path"])
    if _sha256(data) != f.get("sha256"):                                    # 내보내기 직전에 한 번 더 — 손상 파일은 내보내지 않는다
        raise HTTPException(status_code=500, detail="저장된 파일 지문이 맞지 않습니다(손상). 관리자에게 알려 주세요.")
    ascii_name = f"{style_id}_v{v}_" + f["path"].rsplit("/", 1)[-1]
    return Response(content=data, media_type=FILE_KINDS[kind][0],
                    headers={"Content-Disposition": _disposition(ascii_name, f.get("orig")), "X-Content-SHA256": f["sha256"]})


@router.post("/styles", dependencies=[Depends(admin_required)])
async def upload_style(request: Request, view: UploadFile = File(...), exports: UploadFile = File(...),
                       note: str = Form("")) -> JSONResponse:
    """🛡 관리자 — view.json + exports.zip 를 새 버전으로 쌓는다(덮어쓰기 없음). 디스크 → 창고 백업 → 되읽기 확인."""
    view_bytes = await view.read(MAX_VIEW_BYTES + 1)
    zip_bytes = await exports.read(MAX_ZIP_BYTES + 1)
    v = validate_upload(view_bytes, zip_bytes)
    style = v["style"]; sid = style["id"]
    jwt = _bearer(request)
    restore_missing_with_token(jwt, force=True)                            # 창고에만 있는 옛 버전과 번호가 겹치지 않게
    with _LOCK:
        nums = _versions_on_disk(sid)
        stored = _sb_list(sid + "/", jwt) if (jwt and _sb_config()[0]) else None
        for it in stored or []:
            m = re.fullmatch(r"v([1-9][0-9]{0,5})", (it.get("name") or "") if isinstance(it, dict) else "")
            if m:
                nums.append(int(m.group(1)))
        ver = (max(nums) + 1) if nums else 1
        meta = {"style_id": sid, "version": ver, "name": style.get("name"), "garment": style.get("garment"),
                "group": style.get("group"), "sizes": style.get("sizes"), "size_labels": style.get("size_labels"),
                "base_size": style.get("base_size"), "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "uploaded_by": getattr(request.state, "email", None), "note": (note or "")[:500],
                "view_sha256": _sha256(view_bytes), "zip_sha256": _sha256(zip_bytes),
                "view_bytes": len(view_bytes), "zip_bytes": len(zip_bytes), "source": v.get("source"),
                "files": v.get("files") or [], "view_name": view.filename, "zip_name": exports.filename}
        _write_version(sid, ver, {"view.json": view_bytes, "exports.zip": zip_bytes,
                                  "meta.json": json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8")})
    backup = backup_version(sid, ver, jwt)
    if not backup.get("ok") and not backup.get("skipped"):
        # 창고에 못 넣은 버전은 디스크에서 지운다 — 남겨 두면 «있는 것처럼» 보이다가 재배포 때 조용히 사라진다.
        # 창고는 덮어쓰기·삭제 규칙이 없어 반쯤 올라간 조각은 남는다 → 다음 올리기는 다음 번호를 쓴다.
        # 복원은 meta 가 없거나 지문이 다르면 건너뛰므로 반쪽 조각이 되살아나지 않는다.
        with _LOCK:
            shutil.rmtree(_vdir(sid, ver), ignore_errors=True)
        print(f"[cad] 창고 백업 실패로 v{ver} 를 디스크에서 지움: {sid}")
        return JSONResponse(status_code=502, content={
            "detail": f"창고(pattern-cad)에 보관하지 못해 v{ver} 올리기를 취소했습니다. 잠시 후 다시 올려 주세요. "
                      f"(사유: {backup.get('reason') or '알 수 없음'})", "style_id": sid, "version": ver, "backup": backup})
    print(f"[cad] 새 버전: {sid} v{ver} (view {len(view_bytes):,} B · zip {len(zip_bytes):,} B)")
    return JSONResponse(status_code=201, content={"style_id": sid, "version": ver, "backup": backup,
                                                  "view_sha256": meta["view_sha256"], "zip_sha256": meta["zip_sha256"]})
