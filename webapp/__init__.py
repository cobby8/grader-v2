# -*- coding: utf-8 -*-
"""grader-v2 webapp — 엔진(engine/)을 사내 웹 도구로 노출하는 FastAPI 백엔드.

설계 원칙(의뢰서-CLI-FastAPI-구동.md):
  - 엔진 공개 API 는 import/호출만 한다. 절대 수정하지 않는다.
  - 빌드 0: 정적 HTML/CSS/JS 를 그대로 서빙(번들러 없음).
  - 상태 저장 = 폴더 + JSON(DB 없음).
  - 각 API 는 curl 한 줄로 단독 검증 가능.
  - 에러는 비개발자 직원을 위해 한국어로 "원인 + 다음 행동"을 함께 알린다.

1단계 범위: FastAPI 뼈대 + 정적 서빙 + /api/health·/api/patterns·/api/settings(읽기).
"""
