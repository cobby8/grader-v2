# -*- coding: utf-8 -*-
"""등록 패턴 파일 영속화 - Supabase Storage 백업/복원 헬퍼(Phase B).

왜 이 파일이 필요한가(쉬운 비유):
  우리 서버(Render)의 저장 공간은 '임시 사물함' 이라, 재배포(업데이트)를 하면
  그동안 화면에서 등록한 패턴 폴더(data/patterns/{id}/)가 통째로 사라진다.
  그래서 이 모듈이 '영구 창고(Supabase Storage 의 pattern-presets 버킷)' 에
  등록 직후 패턴을 zip 으로 백업해 두고, 서버가 켜질 때(startup) 로컬에 없어진
  것만 다시 꺼내와 복원한다. (사물함이 새것으로 바뀌어도 창고엔 남아 있으니까.)

이 모듈의 3가지 일:
  1) backup_pattern(pattern_id, user_jwt)  - 폴더 → 메모리 zip → 창고에 업로드(백업)
  2) list_backups()                        - 창고에 어떤 zip 이 있는지 목록 조회
  3) restore_missing()                     - 로컬에 없는 것만 창고에서 내려받아 압축해제(복원)

⚠️ 비밀키 규칙(절대 준수):
  - 업로드(쓰기)는 SERVICE_ROLE 같은 비밀키를 절대 쓰지 않는다. 대신 등록을 요청한
    '관리자(admin) 사용자의 로그인 토큰(user_jwt)' 을 그대로 Storage 에 릴레이한다
    → Supabase 의 RLS 규칙이 'admin 만 쓰기' 를 강제한다.
  - 헤더의 apikey 에는 '공개키(SUPABASE_PUBLISHABLE_KEY)' 만 쓴다(프런트 노출용 키).
  - 토큰(JWT)·키 값은 로그(print)에 절대 남기지 않는다.

⚠️ degrade(있으면 좋은 부가기능) 원칙:
  Storage 미설정(env 없음)·업로드 실패·Supabase 장애가 나도 절대 예외를 위로
  던지지 않는다. 백업 실패는 '등록' 을, 복원 실패는 '부팅' 을 막지 않아야 한다.
  (로컬 개발은 토큰·env 가 없어 자동으로 전부 skip = 기존 동작 그대로.)
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from typing import List, Optional, Tuple

import httpx

from . import state

# ── 상수 ─────────────────────────────────────────────────────────────────
# 창고(버킷) 이름. 설정가이드(Phase-B-Supabase-Storage-설정가이드.md)의 버킷명과
# 반드시 정확히 일치해야 한다(오타 시 조용히 실패).
BUCKET = "pattern-presets"

# Storage REST 호출 타임아웃(초). 느린 네트워크에서 부팅/등록이 무한정 매달리지 않게.
_HTTP_TIMEOUT = 15.0

# preset.json 이 없는 zip 은 '손상' 으로 보고 복원에서 건너뛴다(패턴은 이게 필수).
_REQUIRED_ENTRY = "preset.json"


def _config() -> Tuple[Optional[str], Optional[str]]:
    """Supabase 접속 설정(base_url, publishable)을 환경변수에서 읽는다.

    auth.py 와 동일한 변수명을 쓴다(SUPABASE_URL·SUPABASE_PUBLISHABLE_KEY).
    둘 중 하나라도 없으면 (None, None) 을 돌려 '미설정' 임을 알린다.
    """
    base = os.environ.get("SUPABASE_URL")
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if not base or not publishable:
        return None, None
    return base.rstrip("/"), publishable


def is_enabled() -> bool:
    """백업/복원 기능을 쓸 수 있는 상태인지(env 설정 여부) 판정한다.

    False 면 이 모듈의 모든 동작이 no-op(아무것도 안 함) 로 조용히 넘어간다.
    """
    base, publishable = _config()
    return bool(base and publishable)


def _sanitize_pattern_id(pattern_id: str) -> str:
    """pattern_id 를 안전한 zip 파일명 조각으로 다듬는다(경로조작 차단).

    창고에 올릴 때는 '{pattern_id}.zip' 을 쓰는데, pattern_id 에 '/' 나 '..' 가
    섞이면 엉뚱한 경로로 새어나갈 수 있다(zip-slip 계열). 그래서 경로 구분자와
    상위경로 표기를 전부 제거한다. (원래 등록 시 _safe_pattern_dirname 로 이미
    폴더명이 안전하지만, 복원은 '외부 창고' 에서 온 이름이라 한 번 더 방어한다.)
    """
    name = (pattern_id or "").strip()
    # 폴더 구분자·상위경로·금지문자 제거. 한글/영문/숫자/._- 만 남긴다.
    name = name.replace("\\", "/").split("/")[-1]   # 경로면 마지막 조각만
    name = name.replace("..", "")                    # 상위경로 표기 제거
    name = re.sub(r'[\x00-\x1f<>:"|?*]', "", name)   # 제어문자·윈도 금지문자 제거
    name = name.strip(". ")                          # 양끝 점/공백 제거
    return name


def _object_url(base: str, path: str) -> str:
    """Storage 오브젝트(파일) 하나의 REST URL 을 만든다.

    형식: {base}/storage/v1/object/{bucket}/{path}
    (업로드 POST · 다운로드 GET 이 같은 URL 을 쓴다.)
    """
    return f"{base}/storage/v1/object/{BUCKET}/{path}"


# ══════════════════════════════════════════════════════════════════════════
#  1) 백업(업로드) - 폴더 → 메모리 zip → 창고
# ══════════════════════════════════════════════════════════════════════════
def _zip_pattern_folder(pattern_dir: str) -> Optional[bytes]:
    """패턴 폴더(data/patterns/{id}/)를 통째로 메모리 zip 바이트로 묶는다.

    job_zip(api.py:926)의 io.BytesIO + zipfile.ZipFile 패턴을 재사용한다.
    zip 안의 파일 경로(arcname)는 폴더 기준 상대경로라, 나중에 그 폴더에
    그대로 풀면 원본 구조가 복원된다(예: 'preset.json', 'XL.svg').

    반환: zip 바이트(성공) / None(폴더 없음·비어있음).
    """
    if not os.path.isdir(pattern_dir):
        return None
    buf = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(pattern_dir):
            for fn in files:
                src = os.path.join(root, fn)
                # 폴더 기준 상대경로를 arcname 으로(구분자는 zip 표준인 '/').
                arc = os.path.relpath(src, pattern_dir).replace("\\", "/")
                zf.write(src, arc)
                file_count += 1
    if file_count == 0:
        return None
    buf.seek(0)
    return buf.getvalue()


def backup_pattern(pattern_id: str, user_jwt: Optional[str]) -> bool:
    """등록된 패턴 폴더를 zip 으로 묶어 Supabase Storage 에 업로드(백업)한다.

    호출 위치(예정): 패턴 등록 성공 직후(create_pattern·from-drive return 직전).
    실패해도 등록을 막지 않도록, 어떤 경우에도 예외를 던지지 않고 True/False 만 준다.

    skip(=False) 하는 경우:
      - 기능 미설정(env 없음)
      - user_jwt 없음(로컬 무인증 - 로컬은 디스크가 영속이라 백업 불필요)
      - 폴더가 없거나 비어 있음
    업로드 성공 시에만 True.

    비밀키 규칙: 헤더 apikey=공개키, Authorization=Bearer {요청자 admin JWT}.
      (SERVICE_ROLE 등 비밀키 미사용. RLS 가 admin 쓰기를 강제한다.)
    upsert: 같은 패턴을 다시 등록하면 창고의 zip 을 최신본으로 덮어쓴다(x-upsert=true).
    """
    base, publishable = _config()
    if not base or not publishable:
        print("[storage_backup] skip 백업: Supabase Storage 미설정(env 없음)")
        return False
    # 로컬 무인증(토큰 없음)이면 백업하지 않는다(로컬은 디스크 영속이라 불필요).
    if not user_jwt:
        print("[storage_backup] skip 백업: 로그인 토큰 없음(로컬 무인증)")
        return False

    safe_id = _sanitize_pattern_id(pattern_id)
    if not safe_id:
        print("[storage_backup] skip 백업: pattern_id 가 비었거나 안전하지 않음")
        return False

    pattern_dir = os.path.join(state.get_patterns_dir(), safe_id)
    data = _zip_pattern_folder(pattern_dir)
    if not data:
        print(f"[storage_backup] skip 백업: 폴더 없음/비어있음 ({safe_id})")
        return False

    url = _object_url(base, f"{safe_id}.zip")
    try:
        resp = httpx.post(
            url,
            content=data,
            headers={
                "apikey": publishable,                       # 공개키만(비밀키 금지)
                "Authorization": f"Bearer {user_jwt}",       # 요청자 admin JWT 릴레이
                "Content-Type": "application/zip",
                "x-upsert": "true",                          # 재등록 시 최신본으로 덮어씀
            },
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        # 네트워크 단절·타임아웃 등 - 등록은 막지 않는다(degrade). 키/토큰은 로그 금지.
        print(f"[storage_backup] 백업 실패(네트워크): {safe_id} - {type(e).__name__}")
        return False

    if resp.status_code in (200, 201):
        print(f"[storage_backup] 백업 성공: {safe_id}.zip ({len(data)} bytes)")
        return True
    # 권한(403)·기타 오류 - 사유 코드만 남기고(본문에 키 노출 위험 없게 status 만) 넘어간다.
    print(f"[storage_backup] 백업 실패(status {resp.status_code}): {safe_id}")
    return False


# ══════════════════════════════════════════════════════════════════════════
#  2) 목록 조회 - 창고에 어떤 zip 이 있나
# ══════════════════════════════════════════════════════════════════════════
def list_backups() -> List[str]:
    """Storage 의 pattern-presets 창고에 있는 zip 파일 이름 목록을 돌려준다.

    읽기는 RLS 가 개방(anon 허용)이라 공개키만으로 조회한다(로그인 토큰 불필요).
    실패/미설정 시 빈 리스트(복원이 그냥 아무 것도 안 하게).

    반환: ['농구_V넥_양면.zip', ...] 같은 파일명 리스트.
    """
    base, publishable = _config()
    if not base or not publishable:
        return []

    # Storage list 엔드포인트는 POST + JSON 바디(prefix/limit)를 쓴다.
    url = f"{base}/storage/v1/object/list/{BUCKET}"
    try:
        resp = httpx.post(
            url,
            headers={
                "apikey": publishable,
                "Authorization": f"Bearer {publishable}",   # 읽기는 공개키(anon 역할)
                "Content-Type": "application/json",
            },
            json={"prefix": "", "limit": 1000, "offset": 0},
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        print(f"[storage_backup] 목록 조회 실패(네트워크): {type(e).__name__}")
        return []

    if resp.status_code != 200:
        print(f"[storage_backup] 목록 조회 실패(status {resp.status_code})")
        return []

    try:
        items = resp.json() or []
    except Exception:
        return []

    names: List[str] = []
    for it in items:
        if isinstance(it, dict):
            nm = it.get("name")
            # zip 파일만 대상(폴더/placeholder 제외).
            if isinstance(nm, str) and nm.lower().endswith(".zip"):
                names.append(nm)
    return names


# ══════════════════════════════════════════════════════════════════════════
#  3) 복원(다운로드+해제) - 로컬에 없는 것만
# ══════════════════════════════════════════════════════════════════════════
def _download_zip(base: str, publishable: str, object_name: str) -> Optional[bytes]:
    """창고에서 zip 파일 하나를 내려받아 바이트로 돌려준다(실패 시 None).

    읽기는 RLS 개방이라 공개키(anon 역할)만으로 다운로드한다.
    """
    url = _object_url(base, object_name)
    try:
        resp = httpx.get(
            url,
            headers={
                "apikey": publishable,
                "Authorization": f"Bearer {publishable}",   # 읽기는 공개키(anon 역할)
            },
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        print(f"[storage_backup] 다운로드 실패(네트워크): {object_name} - {type(e).__name__}")
        return None
    if resp.status_code != 200:
        print(f"[storage_backup] 다운로드 실패(status {resp.status_code}): {object_name}")
        return None
    return resp.content


def _safe_extract(zip_bytes: bytes, dest_dir: str) -> bool:
    """zip 바이트를 dest_dir 안에 안전하게 압축해제한다(zip-slip 방어).

    zip-slip 이란(비유): zip 안의 파일 이름에 '../../etc/passwd' 처럼 상위경로를
    심어두면, 순진하게 풀 때 목표 폴더 '밖' 으로 파일이 튀어나가 시스템 파일을
    덮어쓸 수 있는 공격이다. 그래서 각 엔트리의 '최종 경로' 가 반드시 dest_dir
    안쪽인지 확인하고, 벗어나면 그 엔트리를 건너뛴다. 또 preset.json 이 없는
    zip 은 손상으로 보고 아무 것도 풀지 않는다(전부 or 아무것도).

    반환: True(해제 성공) / False(손상·차단으로 실패).
    """
    dest_abs = os.path.abspath(dest_dir)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            # preset.json 이 없는 zip 은 패턴으로 볼 수 없다 → 손상 취급, 통째로 skip.
            if not any(os.path.basename(n) == _REQUIRED_ENTRY for n in names):
                print("[storage_backup] 손상 zip(preset.json 없음) - 복원 건너뜀")
                return False

            # 1차 검사: 모든 엔트리가 dest_dir 안쪽인지 미리 확인(하나라도 밖이면 전부 취소).
            for n in names:
                if n.endswith("/"):
                    continue  # 디렉터리 엔트리는 건너뜀(파일 쓸 때 폴더 자동 생성)
                # 절대경로·상위경로 차단.
                if n.startswith("/") or n.startswith("\\") or ".." in n.replace("\\", "/").split("/"):
                    print(f"[storage_backup] zip-slip 의심 엔트리 차단 - 복원 건너뜀: {n}")
                    return False
                target = os.path.abspath(os.path.join(dest_abs, n))
                # 최종 경로가 dest_dir 안쪽이 아니면(경계 이탈) 차단.
                if os.path.commonpath([dest_abs, target]) != dest_abs:
                    print(f"[storage_backup] 경로 이탈 엔트리 차단 - 복원 건너뜀: {n}")
                    return False

            # 2차: 검증 통과 → 실제 해제.
            os.makedirs(dest_abs, exist_ok=True)
            for n in names:
                if n.endswith("/"):
                    continue
                target = os.path.abspath(os.path.join(dest_abs, n))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(n) as src, open(target, "wb") as out:
                    out.write(src.read())
    except zipfile.BadZipFile:
        print("[storage_backup] 손상 zip(형식 오류) - 복원 건너뜀")
        return False
    except Exception as e:
        print(f"[storage_backup] 해제 실패: {type(e).__name__} - 복원 건너뜀")
        return False
    return True


def restore_missing() -> int:
    """창고의 백업 중 '로컬에 없는 패턴' 만 내려받아 복원한다.

    호출 위치(예정): 앱 startup 훅(main.py). 부팅을 막지 않도록 어떤 예외도
    밖으로 던지지 않는다(각 패턴 실패는 개별적으로 삼키고 다음으로 넘어간다).

    복원 규칙(로컬 우선):
      - 로컬 data/patterns/{id}/ 폴더가 이미 있으면 건드리지 않는다(덮어쓰기 금지).
        → 코드에 원래 들어있던 커밋본·기존 등록이 그대로 유지된다(회귀 0).
      - 로컬에 없는 것만 다운로드 → zip-slip 방어 해제.

    반환: 실제로 복원한 패턴 개수(0 이상). 미설정/실패면 0.
    """
    base, publishable = _config()
    if not base or not publishable:
        print("[storage_backup] 복원 skip: Supabase Storage 미설정(env 없음)")
        return 0

    names = list_backups()
    if not names:
        print("[storage_backup] 복원할 백업 없음(또는 목록 조회 실패)")
        return 0

    patterns_dir = state.get_patterns_dir()
    restored = 0
    for obj_name in names:
        try:
            # 파일명에서 pattern_id 복원('농구_V넥.zip' → '농구_V넥') + 안전화.
            pid = _sanitize_pattern_id(obj_name[:-4] if obj_name.lower().endswith(".zip") else obj_name)
            if not pid:
                continue
            local_dir = os.path.join(patterns_dir, pid)
            # 로컬에 이미 있으면 skip(로컬 우선 - 덮어쓰기 금지).
            if os.path.isdir(local_dir):
                continue
            data = _download_zip(base, publishable, obj_name)
            if not data:
                continue
            if _safe_extract(data, local_dir):
                restored += 1
                print(f"[storage_backup] 복원 성공: {pid}")
        except Exception as e:
            # 개별 패턴 실패는 삼키고 계속(한 개 실패가 전체 복원·부팅을 막지 않게).
            print(f"[storage_backup] 복원 중 오류(건너뜀): {obj_name} - {type(e).__name__}")
            continue

    print(f"[storage_backup] 복원 완료: {restored}개")
    return restored
