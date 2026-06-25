# -*- coding: utf-8 -*-
"""배포용 인증 게이트 — Supabase Auth(JWT) 검증 Dependency.

핵심 설계(로컬 무인증 / 배포 인증 토글):
  이 도구는 두 가지 모드로 돈다.
    · 로컬(개발):  무인증. 직원 PC 에서 바로 쓰던 흐름 그대로 — 회귀 0.
    · 배포(인터넷): 로그인 필수. Supabase 가 발급한 JWT 를 검증해 통과시킨다.
  이 둘을 가르는 스위치가 환경변수 GRADER_REQUIRE_AUTH 다.
    - 꺼짐(미설정/0/false): 검증을 통째로 건너뛰고 무조건 통과(로컬 기본).
    - 켜짐(1/true/yes/on): Authorization: Bearer <token> 을 반드시 검증.

비유:
  GRADER_REQUIRE_AUTH 는 건물 정문의 '경비 배치' 스위치다. 꺼두면(사내 자리)
  누구나 드나든다. 켜두면(인터넷 노출) 경비가 출입증(JWT)을 검사한다.

⚠️ 비밀키 규칙:
  토큰 서명 검증에 쓰는 SUPABASE_JWT_SECRET 은 '오직 환경변수' 로만 받는다.
  코드·레포·프런트 어디에도 값을 적지 않는다(Render env 로만 주입).
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Request, HTTPException

# JWT 검증 라이브러리(PyJWT). 로컬 무인증 모드에서는 호출되지 않으므로,
# 만약 패키지가 없더라도 import 단계에서 죽지 않게 지연 import 로 감싼다.
try:
    import jwt  # PyJWT
except Exception:  # pragma: no cover
    jwt = None  # 인증 켜졌을 때만 실제로 필요(아래에서 친절히 안내)


# 인증을 '켜짐' 으로 인정하는 값들(대소문자 무시). 그 외(미설정 포함)는 모두 '꺼짐'.
_TRUTHY = {"1", "true", "yes", "on"}


def auth_required() -> bool:
    """현재 인증이 켜져 있는지(GRADER_REQUIRE_AUTH) 판정한다.

    환경변수가 없거나 '0/false' 류면 False(로컬 무인증). '1/true' 류면 True(배포).
    """
    return os.environ.get("GRADER_REQUIRE_AUTH", "").strip().lower() in _TRUTHY


def require_auth(request: Request) -> Optional[str]:
    """FastAPI Dependency — 보호된 /api 핸들러 앞에서 출입증(JWT)을 검사한다.

    동작:
      · 인증 꺼짐(로컬): 즉시 통과. request.state.user_id=None, role=None 으로
        안전 기본값을 박아 두고 None 을 돌려준다(핸들러가 user 를 봐도 안 깨짐).
      · 인증 켜짐(배포): Authorization: Bearer <token> 헤더를 꺼내 Supabase
        JWT 시크릿(HS256)으로 검증한다. 실패하면 401 로 막는다(한국어 사유).
        성공 시 request.state.user_id=sub, role=app_metadata.role 을 채운다.

    반환: user_id(sub) 또는 None. (핸들러가 굳이 안 받아도 됨 — side effect 로 state 채움)
    """
    # ── 로컬 무인증 모드: 검증 없이 통과(회귀 0). 안전 기본값만 세팅. ──
    if not auth_required():
        request.state.user_id = None
        request.state.role = None
        return None

    # ── 배포 인증 모드: 여기서부터는 토큰이 반드시 있어야 한다. ──
    # 1) JWT 라이브러리 존재 확인(켜졌는데 미설치면 서버 설정 문제 → 명확히 알림).
    if jwt is None:
        raise HTTPException(
            status_code=500,
            detail="서버 인증 설정 오류: PyJWT 가 설치되어 있지 않습니다. "
                   "requirements.txt(pyjwt) 설치를 확인하세요.")

    # 2) 시크릿 확인(환경변수로만 받는다 — 코드·레포에 값 없음).
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="서버 인증 설정 오류: SUPABASE_JWT_SECRET 환경변수가 없습니다. "
                   "배포 환경변수에 Supabase JWT 시크릿을 등록하세요.")

    # 3) Authorization 헤더에서 Bearer 토큰 추출.
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

    # 4) JWT 검증(HS256, audience=authenticated — Supabase 기본값).
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except Exception as e:
        # 만료·서명불일치 등 모든 검증 실패 → 401(원인은 서버 로그에만, 화면엔 한국어).
        raise HTTPException(
            status_code=401,
            detail="로그인이 만료되었거나 토큰이 올바르지 않습니다. 다시 로그인해 주세요.")

    # 5) 통과: 사용자 식별자/역할을 request.state 에 채운다(핸들러가 필요 시 사용).
    request.state.user_id = payload.get("sub")
    app_meta = payload.get("app_metadata") or {}
    request.state.role = app_meta.get("role") if isinstance(app_meta, dict) else None
    return request.state.user_id
