# -*- coding: utf-8 -*-
"""FastAPI 앱 진입점 — 정적 화면 서빙 + /api 라우터 연결.

구성(비유):
  - /static/*  : 디자인 클로드가 만든 화면(HTML/CSS/JS)을 그대로 내려보내는 '창고'.
  - /api/*     : 화면이 데이터를 물어보는 '안내 데스크'(api.py).
  - GET /      : 직원이 주소만 치고 들어오면 곧장 작업 화면(work.html)으로 보낸다.

빌드 0 원칙: 번들러 없이 정적 파일을 그대로 마운트한다.
"""
from __future__ import annotations

import os
import threading
import time

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import state
from . import storage_backup  # 등록 패턴 파일 영속화(Phase B): startup 자동 복원.
from .api import router as api_router, public_router
from .auth import require_auth

app = FastAPI(
    title="STIZ grader-v2",
    description="사내 유니폼 출력 자동화 웹 도구(엔진 래퍼)",
)

# ── /api 라우터 연결 ──
# 데이터 API 를 먼저 붙인다. (정적 마운트보다 먼저 등록해 경로가 가려지지 않게.)
#
# 인증 게이트(배포 전용, 로컬은 무인증 통과):
#   · public_router : /api/health — 무인증(Render 헬스체크가 토큰 없이 부른다).
#   · api_router    : 나머지 모든 /api/* — require_auth 를 '전역' 으로 건다.
#     (require_auth 는 GRADER_REQUIRE_AUTH 가 꺼져 있으면 검증 없이 통과 = 로컬 회귀 0)
app.include_router(public_router)
app.include_router(api_router, dependencies=[Depends(require_auth)])

# ── 정적 화면 마운트 ──
# webapp/static 폴더(핸드오프 복사본)를 /static 아래로 통째 서빙한다.
# html=True 면 디렉터리 접근 시 index.html 을 자동으로 찾아 준다.
STATIC_DIR = state.get_static_dir()
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


# ── 등록 패턴 파일 자동 복원(Phase B: 파일 영속화) ────────────────────────────
#   왜: Render 는 재배포하면 디스크가 새것으로 바뀌어 그동안 등록한 패턴 폴더가
#   사라진다. 그래서 서버가 켜질 때(startup) Supabase Storage 에 백업해 둔 zip 중
#   '로컬에 없는 것만' 내려받아 복원한다(로컬 우선 — 커밋본·기존 등록은 안 건드림).
#
#   ⚠️ 부팅/헬스체크를 막지 않는다(reviewer 권고 필수 반영):
#     restore_missing() 은 동기(네트워크 대기)라, Storage 가 느리거나 장애면 최악의
#     경우 부팅이 수십 초 매달릴 수 있다(각 다운로드 최대 15초). Render 헬스체크가
#     그 사이 실패하면 배포가 통째로 막힌다. 그래서 '별도 백그라운드 스레드'
#     (daemon)로 돌려, 앱은 즉시 요청을 받기 시작하고 복원은 뒤에서 진행되게 한다.
#     (--workers 1 유지 — 프로세스 1개라 스레드 1개면 충분하고 중복 복원도 없다.)
#
#   ⚠️ degrade: 복원 실패가 부팅을 절대 막지 않는다(전체를 try 로 감싼다). 미설정
#     (env 없음)이면 storage_backup 이 알아서 no-op = 로컬 개발도 기존 동작 그대로.
def _restore_patterns_background() -> None:
    """백그라운드에서 등록 패턴을 Storage 에서 복원한다(부팅과 분리)."""
    try:
        print("[startup] 등록 패턴 복원 시작(백그라운드)")
        restored = storage_backup.restore_missing()  # 로컬에 없는 것만 복원, 개수 반환
        print(f"[startup] 등록 패턴 복원 완료: {restored}개")
    except Exception as e:
        # 복원 실패는 앱 동작에 영향을 주지 않는다(백업본이 없거나 네트워크 문제일 뿐).
        print(f"[startup] 등록 패턴 복원 건너뜀(부팅에는 영향 없음): {type(e).__name__}")


# ── 오래된 업로드·작업 폴더 자동 정리(디스크 청소) ────────────────────────────
#   왜: data/uploads(주문서·디자인 임시본)와 data/jobs(web_ 결과 폴더)는 쌓이기만 하고
#   지우는 코드가 없었다. 하루 한 번 청소부 스레드가 돌며 오래된 것만 치운다
#   (규약·제외 대상은 state.cleanup_old_files 주석 참고). 복원 스레드와 같은 이유로
#   부팅을 막지 않는 daemon 스레드이며, 실패해도 서버에는 영향이 없다.
#   끄기: GRADER_CLEANUP_DISABLED=1 (로컬 개발자가 산출물을 보관하고 싶을 때).
CLEANUP_INTERVAL_SEC = 24 * 3600      # 하루 한 번
_TRUTHY = ("1", "true", "yes", "on")


def _cleanup_disabled() -> bool:
    return os.environ.get("GRADER_CLEANUP_DISABLED", "").strip().lower() in _TRUTHY


def _run_cleanup_once() -> None:
    """청소 한 바퀴: 디스크(uploads·jobs) + 메모리(_JOBS) → 결과를 state 에 기록."""
    started = time.time()
    try:
        result = state.cleanup_old_files()
        result["jobs_pruned"] = state.prune_finished_jobs()
        state.record_maintenance(
            runs=state.get_maintenance_status().get("runs", 0) + 1,
            last_run=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
            last_result=result,
            last_error=None,
        )
        print(f"[cleanup] 업로드 {result['uploads_removed']}개 · 작업 {result['jobs_removed']}개 · "
              f"{result['freed_bytes']:,}바이트 정리"
              + (f" · 실패 {len(result['errors'])}건" if result["errors"] else ""))
    except Exception as e:
        # 청소 실패는 서버 동작에 영향을 주지 않는다 — 기록만 남기고 다음 주기를 기다린다.
        state.record_maintenance(
            last_run=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
            last_error=f"{type(e).__name__}: {e}",
        )
        print(f"[cleanup] 정리 실패(서버에는 영향 없음): {type(e).__name__}: {e}")


def _cleanup_loop() -> None:
    """부팅 직후 1회, 이후 24시간마다 청소를 반복한다(daemon 스레드 본체)."""
    while True:
        _run_cleanup_once()
        next_at = time.time() + CLEANUP_INTERVAL_SEC
        state.record_maintenance(
            next_run=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(next_at)))
        time.sleep(CLEANUP_INTERVAL_SEC)


@app.on_event("startup")
def _on_startup() -> None:
    """앱 시작 시 패턴 복원·디스크 청소를 '백그라운드 스레드' 로 띄운다(부팅을 막지 않게).

    여기서는 스레드를 시작만 하고 곧바로 반환한다 → 헬스체크/요청 처리는 지연 0.
    복원 자체는 storage_backup.restore_missing() 이 뒤에서 조용히 진행한다.
    """
    try:
        threading.Thread(
            target=_restore_patterns_background,
            name="pattern-restore",
            daemon=True,  # 데몬 = 앱 종료 시 이 스레드가 종료를 붙잡지 않는다.
        ).start()
    except Exception as e:
        # 스레드 생성 자체가 실패해도 부팅은 계속(복원만 생략).
        print(f"[startup] 복원 스레드 시작 실패(부팅은 계속): {type(e).__name__}")

    # 디스크 청소 스레드(위와 같은 방식). 환경변수로 껐으면 상태만 남기고 띄우지 않는다.
    if _cleanup_disabled():
        state.record_maintenance(enabled=False)
        print("[startup] 자동 정리 꺼짐(GRADER_CLEANUP_DISABLED)")
        return
    try:
        threading.Thread(target=_cleanup_loop, name="disk-cleanup", daemon=True).start()
    except Exception as e:
        print(f"[startup] 정리 스레드 시작 실패(부팅은 계속): {type(e).__name__}")


@app.get("/login")
def login():
    """로그인 화면(login.html)으로 보낸다(무인증 정적 서빙).

    배포에서 토큰이 없거나 만료되면 프런트가 이 주소로 보낸다. login.html 은
    상대경로 자산(../app.css)을 쓰므로 work.html 과 같은 이유로 리다이렉트한다.
    """
    return RedirectResponse(url="/static/screens/login.html")


@app.get("/")
def root():
    """루트 접속 시 로그인 화면(login.html)으로 보낸다.

    왜 work 가 아니라 login 인가(배포본 404·미인증 우회 버그 수정):
      서버는 브라우저의 sessionStorage 토큰을 모른다(토큰은 fetch 헤더에만 실린다).
      그래서 루트에서 곧장 work.html 로 보내면, 배포(인증 ON)에서 '로그인 안 한
      사람도 일단 work 화면이 뜨고' 첫 /api 호출이 401 나야 비로소 로그인으로
      튕긴다(증상: 로그인 없이 work 떠서 막힘). 대신 루트를 login.html 로 보내면:
        · 미로그인: 로그인 화면이 먼저 보인다(완료기준 충족).
        · 이미 유효 세션: login.html 의 JS 가 이를 감지해 곧장 work 로 보낸다.
      로컬(인증 OFF)에서도 login.html 이 /api/public-config 의 auth_required=false
      를 보고 즉시 work 로 넘기므로 직원 흐름은 그대로다(회귀 0).

    왜 '직접 반환' 이 아니라 '리다이렉트' 인가:
      login.html 의 마크업은 screens/ 폴더 안에서 열리도록 자산을 상대경로
      (예: ../styles.css)로 참조한다. 루트(/)에서 그대로 내려보내면 브라우저가
      ../styles.css 를 /styles.css 로 잘못 풀어 스타일이 깨진다. 그래서 원본
      마크업을 건드리지 않고, 브라우저 기준 경로가 /static/screens/ 가 되도록
      그 주소로 보내 준다(상대경로가 /static/styles.css 로 정확히 풀린다).
    """
    login_html = os.path.join(STATIC_DIR, "screens", "login.html")
    if not os.path.exists(login_html):
        # 정적 복사본이 빠졌을 때 비개발자도 알 수 있게 한국어로 안내한다.
        return JSONResponse(
            status_code=500,
            content={
                "error": "로그인 화면 파일을 찾지 못했습니다.",
                "detail": "webapp/static/screens/login.html 이 있는지 확인하세요. "
                          "디자인 갱신 시 _handoff/grader-v2-static 을 다시 복사해야 합니다.",
            },
        )
    return RedirectResponse(url="/static/screens/login.html")
