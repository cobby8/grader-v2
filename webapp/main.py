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

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import state
from .api import router as api_router

app = FastAPI(
    title="STIZ grader-v2",
    description="사내 유니폼 출력 자동화 웹 도구(엔진 래퍼)",
)

# ── /api 라우터 연결 ──
# 데이터 API 를 먼저 붙인다. (정적 마운트보다 먼저 등록해 경로가 가려지지 않게.)
app.include_router(api_router)

# ── 정적 화면 마운트 ──
# webapp/static 폴더(핸드오프 복사본)를 /static 아래로 통째 서빙한다.
# html=True 면 디렉터리 접근 시 index.html 을 자동으로 찾아 준다.
STATIC_DIR = state.get_static_dir()
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/")
def root():
    """루트 접속 시 작업 화면(work.html)으로 보낸다.

    왜 '직접 반환' 이 아니라 '리다이렉트' 인가:
      work.html 의 마크업은 screens/ 폴더 안에서 열리도록 자산을 상대경로
      (예: ../styles.css)로 참조한다. 루트(/)에서 그대로 내려보내면 브라우저가
      ../styles.css 를 /styles.css 로 잘못 풀어 스타일이 깨진다. 그래서 원본
      마크업을 건드리지 않고, 브라우저 기준 경로가 /static/screens/ 가 되도록
      그 주소로 보내 준다(상대경로가 /static/styles.css 로 정확히 풀린다).
    """
    work_html = os.path.join(STATIC_DIR, "screens", "work.html")
    if not os.path.exists(work_html):
        # 정적 복사본이 빠졌을 때 비개발자도 알 수 있게 한국어로 안내한다.
        return JSONResponse(
            status_code=500,
            content={
                "error": "작업 화면 파일을 찾지 못했습니다.",
                "detail": "webapp/static/screens/work.html 이 있는지 확인하세요. "
                          "디자인 갱신 시 _handoff/grader-v2-static 을 다시 복사해야 합니다.",
            },
        )
    return RedirectResponse(url="/static/screens/work.html")
