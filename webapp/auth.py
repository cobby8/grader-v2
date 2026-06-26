# -*- coding: utf-8 -*-
"""배포용 인증 게이트 — Supabase Auth 토큰 introspection 검증 Dependency.

핵심 설계(로컬 무인증 / 배포 인증 토글):
  이 도구는 두 가지 모드로 돈다.
    · 로컬(개발):  무인증. 직원 PC 에서 바로 쓰던 흐름 그대로 — 회귀 0.
    · 배포(인터넷): 로그인 필수. Supabase 가 발급한 access token 을 검증해 통과시킨다.
  이 둘을 가르는 스위치가 환경변수 GRADER_REQUIRE_AUTH 다.
    - 꺼짐(미설정/0/false): 검증을 통째로 건너뛰고 무조건 통과(로컬 기본).
    - 켜짐(1/true/yes/on): Authorization: Bearer <token> 을 반드시 검증.

비유:
  GRADER_REQUIRE_AUTH 는 건물 정문의 '경비 배치' 스위치다. 꺼두면(사내 자리)
  누구나 드나든다. 켜두면(인터넷 노출) 경비가 출입증(token)을 검사한다.

검증 방식 = introspection(토큰을 '직접 풀지' 않고 Supabase 에 '이 토큰 누구야?' 물어봄):
  이전 방식은 JWT 시크릿(HS256)으로 토큰 서명을 우리가 직접 풀었다(로컬 검증).
  이번엔 Supabase Auth 의 `GET {SUPABASE_URL}/auth/v1/user` 에 토큰을 들고 가서
  "이 토큰 주인이 누구냐"를 물어본다(introspection). 200 이면 사용자 정보(id·email·
  app_metadata.role)를 받아 통과시키고, 그 외/네트워크 실패면 막는다(401).
  장점: 시크릿을 서버에 둘 필요가 없고, Supabase 가 즉시 만료/차단을 반영한다.

⚠️ 비밀키 규칙:
  introspection 헤더의 apikey 에는 '공개키(SUPABASE_PUBLISHABLE_KEY)' 만 쓴다
  (프런트 노출용으로 설계된 키). SUPABASE_SECRET_KEY 는 여기서 안 쓰며,
  코드·레포·프런트 어디에도 값을 적지 않는다(Render env 로만 주입).

성능(60초 토큰 캐시):
  매 /api 요청마다 Supabase 에 물어보면 느리고 호출량이 폭증한다. 그래서 한 번
  확인한 토큰은 60초 동안 '확인됨' 으로 메모(캐시)해 두고 재사용한다. 비유하면
  경비가 방금 본 출입증은 1분간 얼굴을 기억해 다시 안 들여다보는 셈.
  (--workers 1 = 프로세스 1개라 캐시가 한 곳에 모여 일관적이다.)
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import Request, HTTPException, Depends


# 인증을 '켜짐' 으로 인정하는 값들(대소문자 무시). 그 외(미설정 포함)는 모두 '꺼짐'.
_TRUTHY = {"1", "true", "yes", "on"}

# introspection 캐시 TTL(초). 한 번 확인한 토큰은 이 시간 동안 재확인 없이 통과시킨다.
_CACHE_TTL = 60.0

# introspection HTTP 호출 타임아웃(초). 느린 네트워크에서 요청이 무한정 매달리지 않게.
_HTTP_TIMEOUT = 5.0

# ── 토큰 캐시(모듈 전역) ────────────────────────────────────────────────
# 구조: { token(str): (user(dict), expire_ts(float)) }
#   - user      : Supabase 가 돌려준 사용자 정보에서 추린 {user_id, email, role}.
#   - expire_ts : 이 캐시 항목이 만료되는 시각(time.time() 기준). 지나면 무효.
# 여러 요청 스레드가 동시에 만지므로 자물쇠(Lock)로 보호한다(--workers 1이라 프로세스 1개).
_TOKEN_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
_CACHE_LOCK = threading.Lock()


def auth_required() -> bool:
    """현재 인증이 켜져 있는지(GRADER_REQUIRE_AUTH) 판정한다.

    환경변수가 없거나 '0/false' 류면 False(로컬 무인증). '1/true' 류면 True(배포).
    """
    return os.environ.get("GRADER_REQUIRE_AUTH", "").strip().lower() in _TRUTHY


def _cache_get(token: str) -> Optional[Dict[str, Any]]:
    """캐시에서 유효한(만료 안 된) 토큰 사용자 정보를 꺼낸다(없거나 만료면 None).

    만료된 항목은 꺼내는 김에 정리한다(메모리 누수 방지).
    """
    now = time.time()
    with _CACHE_LOCK:
        item = _TOKEN_CACHE.get(token)
        if not item:
            return None
        user, expire_ts = item
        if expire_ts <= now:
            # 만료 → 제거하고 miss 로 취급(다시 Supabase 에 물어보게).
            _TOKEN_CACHE.pop(token, None)
            return None
        return user


def _cache_put(token: str, user: Dict[str, Any]) -> None:
    """확인된 토큰 사용자 정보를 60초 TTL 로 캐시에 저장한다."""
    with _CACHE_LOCK:
        _TOKEN_CACHE[token] = (user, time.time() + _CACHE_TTL)


def _introspect(token: str) -> Dict[str, Any]:
    """Supabase Auth 에 토큰 주인을 물어본다(GET /auth/v1/user). 실패면 401.

    흐름:
      1) SUPABASE_URL·SUPABASE_PUBLISHABLE_KEY 환경변수 확인(없으면 500 = 서버 설정 오류).
      2) GET {URL}/auth/v1/user (headers: apikey=PUBLISHABLE, Authorization=Bearer token).
      3) 200 → 응답 JSON 에서 id·email·app_metadata.role 을 추려 dict 로 반환.
         비200 → 401(토큰 무효/만료). 네트워크 예외(timeout 등) → 401.

    반환: {"user_id": ..., "email": ..., "role": ...} (role 은 없으면 None)
    """
    base = os.environ.get("SUPABASE_URL")
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    # 인증이 켜졌는데 공개 설정이 없으면 '서버 설정 오류'(401 아님 — 운영자가 고쳐야 함).
    if not base or not publishable:
        raise HTTPException(
            status_code=500,
            detail="서버 인증 설정 오류: SUPABASE_URL 또는 SUPABASE_PUBLISHABLE_KEY "
                   "환경변수가 없습니다. 배포 환경변수를 확인하세요.")

    url = f"{base.rstrip('/')}/auth/v1/user"
    try:
        # apikey 에는 공개키만(비밀키 금지). Authorization 에는 사용자 토큰.
        resp = httpx.get(
            url,
            headers={
                "apikey": publishable,
                "Authorization": f"Bearer {token}",
            },
            timeout=_HTTP_TIMEOUT,
        )
    except Exception:
        # 네트워크 단절·타임아웃 등 — 검증 자체를 못 했으므로 안전하게 차단(401).
        raise HTTPException(
            status_code=401,
            detail="로그인 확인 중 네트워크 문제가 발생했습니다. 다시 시도해 주세요.")

    # 비200(401/403 등) = 토큰이 무효이거나 만료됨 → 로그인 다시 받게 한다.
    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="로그인이 만료되었거나 토큰이 올바르지 않습니다. 다시 로그인해 주세요.")

    # 응답 본문(사용자 정보)을 안전하게 파싱(깨졌으면 401).
    try:
        data = resp.json() or {}
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="로그인 정보를 해석하지 못했습니다. 다시 로그인해 주세요.")

    # app_metadata.role 을 안전하게 꺼낸다(없으면 None = 일반 직원으로 취급).
    app_meta = data.get("app_metadata") or {}
    role = app_meta.get("role") if isinstance(app_meta, dict) else None
    return {
        "user_id": data.get("id"),
        "email": data.get("email"),
        "role": role,
    }


def require_auth(request: Request) -> Optional[str]:
    """FastAPI Dependency — 보호된 /api 핸들러 앞에서 출입증(토큰)을 검사한다.

    동작:
      · 인증 꺼짐(로컬): 즉시 통과. request.state.user_id=None, role=None 으로
        안전 기본값을 박아 두고 None 을 돌려준다(핸들러가 user 를 봐도 안 깨짐).
      · 인증 켜짐(배포): Authorization: Bearer <token> 헤더를 꺼내 Supabase 에
        introspection(GET /auth/v1/user)으로 검증한다. 60초 캐시를 먼저 보고,
        없으면 실제 호출한다. 실패하면 401 로 막는다(한국어 사유).
        성공 시 request.state.user_id·email·role 을 채운다.

    반환: user_id 또는 None. (핸들러가 굳이 안 받아도 됨 — side effect 로 state 채움)
    """
    # ── 로컬 무인증 모드: 검증 없이 통과(회귀 0). 안전 기본값만 세팅. ──
    if not auth_required():
        request.state.user_id = None
        request.state.email = None
        request.state.role = None
        return None

    # ── 배포 인증 모드: 여기서부터는 토큰이 반드시 있어야 한다. ──
    # 1) Authorization 헤더에서 Bearer 토큰 추출.
    authz = request.headers.get("Authorization") or request.headers.get("authorization")
    if not authz or not authz.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다(인증 토큰 없음). 다시 로그인해 주세요.")
    token = authz.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다(빈 토큰). 다시 로그인해 주세요.")

    # 2) 60초 캐시 조회 — hit 면 Supabase 호출 없이 재사용(빠르고 호출량 절감).
    user = _cache_get(token)
    if user is None:
        # 3) miss → 실제 introspection(여기서 401/500 이 날 수 있음). 성공 시 캐시 저장.
        user = _introspect(token)
        _cache_put(token, user)

    # 4) 통과: 사용자 식별자/역할을 request.state 에 채운다(핸들러·admin 게이트가 사용).
    request.state.user_id = user.get("user_id")
    request.state.email = user.get("email")
    request.state.role = user.get("role")
    return request.state.user_id


def admin_required(request: Request, _: Optional[str] = Depends(require_auth)) -> None:
    """FastAPI Dependency — '관리자 전용' 핸들러 앞에서 역할(role)을 검사한다.

    require_auth 에 의존한다(먼저 토큰 검증 → request.state.role 채움). 그 후:
      · 인증 꺼짐(로컬): admin 검사도 통과한다. 로컬은 무인증 일관성을 위해
        admin 작업도 막지 않는다(회귀 0 — 직원 PC 에서 패턴 등록·설정 저장 그대로).
      · 인증 켜짐(배포): request.state.role 이 'admin' 이 아니면 403 으로 막는다.

    비유: require_auth 가 '출입증 확인' 이라면, admin_required 는 그 출입증에
      '관리자' 도장이 찍혀 있는지 한 번 더 보는 안쪽 문이다.
    """
    # 로컬 무인증이면 admin 도 통과(무인증 일관). require_auth 가 이미 state=None 세팅.
    if not auth_required():
        return None
    role = getattr(request.state, "role", None)
    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="이 작업은 관리자만 할 수 있습니다(권한 부족). 관리자 계정으로 로그인해 주세요.")
    return None
