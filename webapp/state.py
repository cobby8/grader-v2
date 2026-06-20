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
import shutil
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

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
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")      # 업로드 임시저장
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


def get_jobs_dir() -> str:
    """생성 작업 결과 폴더(data/jobs, 절대경로) 를 돌려준다."""
    return JOBS_DIR


def save_upload(upload) -> str:
    """업로드된 파일(UploadFile)을 data/uploads/ 에 임시 저장하고 절대경로를 돌려준다.

    왜 디스크에 한 번 떨어뜨리나(비유):
      엔진(parse_order, flatten_transparency)은 '메모리에 떠 있는 업로드 덩어리'가
      아니라 '디스크에 있는 파일 주소(경로)'를 받아서 일한다. 그래서 브라우저가
      올린 파일을 우편함(uploads 폴더)에 한 번 내려놓고, 그 주소를 엔진에 건넨다.

    충돌 방지: 같은 이름의 파일을 여러 번 올려도 덮어쓰지 않도록 파일명 앞에
      '시각+랜덤8자리' 접두어를 붙인다(예: 1718900000_ab12cd34__주문서.xlsx).

    반환: 저장된 파일의 절대경로(str).
    """
    # uploads 폴더가 없으면 만든다(첫 실행이면 정상적으로 없음).
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    # 원본 파일명에서 폴더 구분자를 떼어 파일명만 안전하게 추린다(경로 조작 방지).
    raw_name = os.path.basename(upload.filename or "upload.bin")

    # 시각(초)+랜덤8자리 접두어로 충돌·덮어쓰기를 막는다.
    prefix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}__"
    dest = os.path.join(UPLOADS_DIR, prefix + raw_name)

    # 업로드 스트림을 처음으로 되감은 뒤(이전에 읽혔을 수 있음) 디스크로 복사한다.
    try:
        upload.file.seek(0)
    except Exception:
        pass
    with open(dest, "wb") as out:
        shutil.copyfileobj(upload.file, out)

    return dest


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


# ── 비동기 작업(job) 진행상태 메모리 저장소 ──────────────────────────────────
# 왜 메모리 딕셔너리인가(비유):
#   생성은 시간이 걸린다(수십 개 파일 합성·검증). 브라우저가 "생성 시작" 버튼을
#   누르면 곧장 끝나길 기다리게 하면 화면이 멈춘 듯 보인다. 그래서 주방(백그라운드
#   스레드)에 주문을 넣고 '주문표(job_id)' 만 즉시 돌려준 뒤, 화면이 주기적으로
#   "다 됐어요?(progress)" 를 물어보게 한다. 그 진행상태를 잠깐 들고 있을 메모장이
#   바로 이 딕셔너리다. 서버가 떠 있는 동안만 유효하면 충분하다(결과 자체는
#   data/jobs/<id>/job.json 에 영구 저장되므로 재시작해도 결과 조회는 가능).
#
# 구조: { job_id: {status, total, done, error, out_dir, started_at, ...} }
#   - status : "running" | "done" | "error"
#   - total  : 전체 주문 행 수(진행바 분모)
#   - done   : 완료(생성+검증)된 출력 수(진행바 분자)
#   - error  : 실패 시 한국어 사유(없으면 None)
#   - out_dir: 결과 폴더 절대경로(완료 후 job.json 위치)
_JOBS: Dict[str, Dict[str, Any]] = {}
# 여러 스레드가 동시에 _JOBS 를 만지므로(요청 스레드 vs 작업 스레드) 자물쇠로 보호.
_JOBS_LOCK = threading.Lock()


def create_job(total: int) -> str:
    """새 job 을 등록하고 job_id 를 돌려준다(상태=running).

    total: 진행바 분모로 쓸 전체 주문 행 수(화면이 0/total 로 그린다).
    """
    job_id = uuid.uuid4().hex[:12]  # 12자리면 충돌 사실상 0(폴더명에도 안전).
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "running",
            "total": int(total),
            "done": 0,
            "error": None,
            "out_dir": None,
            "started_at": time.time(),
        }
    return job_id


def update_job(job_id: str, **fields: Any) -> None:
    """job 의 일부 필드를 갱신한다(자물쇠로 보호). 모르는 job_id 는 조용히 무시."""
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)


def bump_job_done(job_id: str, n: int = 1) -> None:
    """완료 카운트를 n 만큼 올린다(total 을 넘지 않게 보정). 진행바 갱신용."""
    with _JOBS_LOCK:
        j = _JOBS.get(job_id)
        if j:
            j["done"] = min(j["total"], j["done"] + n)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """job 진행상태 사본을 돌려준다(없으면 None). 사본이라 호출자가 만져도 안전."""
    with _JOBS_LOCK:
        j = _JOBS.get(job_id)
        return dict(j) if j else None
