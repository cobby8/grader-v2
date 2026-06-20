# -*- coding: utf-8 -*-
"""경로 헬퍼 + 설정 JSON 읽기/기본값.

왜 이 파일이 따로 있나(비유):
  웹앱의 다른 코드들이 "패턴 폴더가 어디지?", "설정값이 뭐지?" 를 매번
  직접 계산하면 실수가 생긴다. 그래서 '주소록(경로 헬퍼)' 과 '환경설정 창구
  (설정 JSON 읽기)' 를 이 파일 한 곳에 모아 둔다. 다른 파일은 여기에만 물어본다.

1단계에서는 설정은 '읽기' 만 한다(쓰기/PUT 은 후속 단계).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

# ── 프로젝트 루트 경로 계산 ──────────────────────────────────────────────
# 이 파일은 <루트>/webapp/state.py 이므로, 상위 폴더가 webapp, 그 상위가 루트다.
# os.path 로 자기 위치를 기준으로 잡아야, 어디서 실행해도(어느 폴더에서
# uvicorn 을 켜도) 경로가 흔들리지 않는다.
WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))         # <루트>/webapp
PROJECT_ROOT = os.path.dirname(WEBAPP_DIR)                       # <루트>

# 자주 쓰는 폴더들의 절대경로. 다른 파일은 이 상수들만 가져다 쓴다.
STATIC_DIR = os.path.join(WEBAPP_DIR, "static")                  # 정적 화면(복사본)
PATTERNS_DIR = os.path.join(PROJECT_ROOT, "data", "patterns")    # 패턴 프리셋들
JOBS_DIR = os.path.join(PROJECT_ROOT, "data", "jobs")            # 생성 작업 결과
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "data", "settings.json")  # 설정 JSON

# 서버가 띄워질 기본 포트(헬스체크 응답·브라우저 자동오픈에서 공통 사용).
DEFAULT_PORT = 8000

# ── 설정 기본값 ──────────────────────────────────────────────────────────
# 설정 JSON 이 아직 없을 때 돌려줄 안전한 기본값.
# (직원 PC 첫 실행이면 settings.json 이 없는 게 정상이므로, 죽지 말고 기본값을 준다.)
DEFAULT_SETTINGS: Dict[str, Any] = {
    "output_format": "pdf",                 # 출력 형식 기본값(pdf|eps|both)
    "ghostscript_path": "C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe",  # EPS 변환용 GS 경로
    "preview_enabled": True,                # 검수용 미리보기 PNG 생성 여부
    "color_note": "색은 참고용이며 실제 출력색은 공장 기준입니다.",  # 화면에 보여줄 색 메모
}


def get_static_dir() -> str:
    """정적 화면 폴더(절대경로) 를 돌려준다."""
    return STATIC_DIR


def get_patterns_dir() -> str:
    """패턴 프리셋 폴더(절대경로) 를 돌려준다."""
    return PATTERNS_DIR


def read_settings() -> Dict[str, Any]:
    """설정 JSON 을 읽어 dict 로 돌려준다. 파일이 없거나 깨졌으면 기본값을 준다.

    이유: 설정 파일이 없는 건 '에러' 가 아니라 '아직 안 만든 정상 상태' 다.
    그래서 없으면 조용히 기본값을 돌려주고, 있으면 기본값 위에 사용자 값을 덮어
    써서(merge) 일부 키만 저장돼 있어도 빠진 키는 기본값으로 채운다.
    """
    settings = dict(DEFAULT_SETTINGS)  # 기본값 복사본에서 시작(원본 보호)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                settings.update(saved)  # 사용자가 저장한 값으로 덮어쓰기(부분 키 허용)
        except (json.JSONDecodeError, OSError):
            # 파일이 깨졌어도 화면이 죽으면 안 되므로 기본값으로 진행한다.
            pass
    return settings
