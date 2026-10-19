# -*- coding: utf-8 -*-
"""경로 헬퍼 + 설정 JSON 읽기/기본값.

왜 이 파일이 따로 있나(비유):
  웹앱의 다른 코드들이 "패턴 폴더가 어디지?", "설정값이 뭐지?" 를 매번
  직접 계산하면 실수가 생긴다. 그래서 '주소록(경로 헬퍼)' 과 '환경설정 창구
  (설정 JSON 읽기)' 를 이 파일 한 곳에 모아 둔다. 다른 파일은 여기에만 물어본다.

1단계에서는 설정은 '읽기' 만 한다(쓰기/PUT 은 후속 단계).
"""
from __future__ import annotations

import contextlib

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
# 배포(Render 등)는 PORT 환경변수로 포트를 지정한다 → 있으면 그 값, 없으면 8000.
# (로컬은 PORT 를 안 켜므로 기존 8000 그대로 = 회귀 0)
DEFAULT_PORT = int(os.environ.get("PORT", 8000))

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


def get_uploads_dir() -> str:
    """업로드 임시저장 폴더(data/uploads, 절대경로) 를 돌려준다.

    save_upload 와 cleanup_old_files 가 같은 곳을 보게 하는 단일 창구. 테스트는 이 함수를
    monkeypatch 해 임시 폴더로 돌린다(실제 data/uploads 를 건드리지 않게).
    """
    return UPLOADS_DIR


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


def write_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    """설정 JSON 을 '머지' 방식으로 저장하고, 저장 후 전체 설정을 돌려준다.

    왜 머지(부분 갱신)인가(비유):
      설정 화면이 '출력 형식' 하나만 바꿔 보내도, 다른 칸(GS 경로·색 메모)이
      날아가면 안 된다. 그래서 기존에 저장돼 있던 값 위에 이번에 바뀐 값만
      덮어쓴다(빈 종이에 새로 쓰는 게 아니라, 기존 장부에 줄만 고쳐 쓴다).

    안전장치:
      - 받은 patch 중 dict 가 아니거나 None 이면 무시한다.
      - data/ 폴더가 없으면 만든다(첫 실행이면 정상적으로 없음).
      - UTF-8 로 저장(한글 색 메모 보존).

    반환: 저장 직후의 '전체' 설정 dict(화면이 곧장 반영할 수 있게).
    """
    # 1) 현재 저장된(또는 기본) 설정을 먼저 읽어 온다.
    current = read_settings()
    # 2) 이번에 들어온 부분 값(patch)만 덮어쓴다(부분 갱신 = 머지).
    if isinstance(patch, dict):
        for k, v in patch.items():
            current[k] = v
    # 3) data/ 폴더 보장 후 JSON 으로 영구 저장(UTF-8, 사람이 읽기 쉽게 indent).
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


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
            # 완료·실패로 넘어가는 순간을 기록해 둔다(메모리 정리 prune_finished_jobs 의 기준 시각).
            if fields.get("status") in ("done", "error") and "finished_at" not in fields:
                fields["finished_at"] = time.time()
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


# ── 무거운 작업 순서 세우기(합성 ↔ 재단 패턴 엔진) ─────────────────────────────
# 왜(비유): 서버 상자(Render starter)는 메모리가 512MB 하나다. 합성(배번·이름 PDF)과 재단 패턴 엔진(일꾼 프로세스
#   약 180~210MB)이 동시에 돌면 상자가 넘쳐 서버가 통째로 재시작될 수 있다(진행 중인 모든 작업이 날아간다).
#   그래서 «합성끼리는 지금처럼 같이 돌되(shared), 엔진은 혼자 돈다(exclusive)» 규칙을 둔다.
#     · 엔진이 차례를 기다리기 시작하면 새 합성은 엔진이 끝날 때까지 기다린다(엔진이 영영 밀리지 않게 — 쓰기 우선)
#     · 엔진은 이미 돌고 있는 합성이 끝나기를 기다린다(돌던 것을 끊지 않는다)
#   엔진은 관리자가 가끔 누르는 1분짜리라, 합성이 그동안 잠깐 기다리는 비용이 «둘 다 죽는» 위험보다 훨씬 작다.
class HeavyGate:
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self.shared = 0              # 지금 도는 합성 수
        self.exclusive = False       # 엔진이 도는 중
        self.waiting_excl = 0        # 차례를 기다리는 엔진 수

    @contextlib.contextmanager
    def shared_use(self, on_wait=None):
        """합성 차례. on_wait — 엔진 때문에 «기다려야 할 때» 한 번 불린다(작업 화면에 «재단 패턴 작업이 끝나기를 기다림»)."""
        with self._cv:
            told = False
            while self.exclusive or self.waiting_excl:
                if on_wait and not told:
                    told = True
                    try:
                        on_wait()
                    except Exception:
                        pass                     # 표시 실패로 합성이 멈추면 안 된다
                self._cv.wait()
            self.shared += 1
        try:
            yield
        finally:
            with self._cv:
                self.shared -= 1
                self._cv.notify_all()

    @contextlib.contextmanager
    def exclusive_use(self, timeout=None):
        """엔진 차례. timeout(초) 안에 돌던 합성이 안 끝나면 TimeoutError — 엔진 작업은 실패로 끝나고 «대기 표시» 가 풀린다.
        (상한이 없으면 멈춘 합성 하나에 엔진·그 뒤 합성까지 영영 묶인다 — 2단계 리뷰 지적)"""
        deadline = None if timeout is None else time.monotonic() + float(timeout)
        with self._cv:
            self.waiting_excl += 1
            try:
                while self.exclusive or self.shared:
                    left = None if deadline is None else deadline - time.monotonic()
                    if left is not None and left <= 0:
                        raise TimeoutError("합성 작업이 끝나기를 기다리다 시간이 다 됐습니다")
                    self._cv.wait(left)
            finally:
                self.waiting_excl -= 1
                self._cv.notify_all()            # 기다리다 포기(예외)해도 «엔진 뒤에 선» 합성들이 깨어나 다시 본다
            self.exclusive = True
        try:
            yield
        finally:
            with self._cv:
                self.exclusive = False
                self._cv.notify_all()

    def snapshot(self) -> Dict[str, Any]:
        with self._cv:
            return {"shared": self.shared, "exclusive": self.exclusive, "waiting_excl": self.waiting_excl}


HEAVY = HeavyGate()


# ── 오래된 업로드·작업 폴더 자동 정리(디스크 청소) ─────────────────────────────
# 왜 필요한가(비유):
#   업로드(data/uploads)는 '우편함' 이라 주문서·디자인이 들어올 때마다 쌓이는데, 엔진이
#   읽고 난 뒤 치우는 코드가 없었다(2026-09-22 실측 48개). 작업 결과(data/jobs)도 마찬가지
#   (49개). Render 는 재배포 때 디스크가 새것이 되지만, 오래 켜 두면 디스크가 찬다.
#   그래서 '청소부(스레드)' 가 하루 한 번 돌며 오래된 것만 치운다.
#
# 규약(TTL):
#   · uploads : 7일  — 엔진이 읽는 순간 용도가 끝난다(결과는 jobs 에 남는다).
#   · jobs    : 30일 — history.html 이 목록·ZIP 재다운로드에 읽으므로 넉넉히 둔다.
#   · 환경변수 GRADER_UPLOADS_TTL_DAYS / GRADER_JOBS_TTL_DAYS 로 덮어쓸 수 있다.
#
# 🚫 절대 안 건드리는 것:
#   · data/patterns/ (등록 패턴) · _trash/ · .tombstones.json — 청소 대상 폴더가 아니다.
#   · jobs 안에서 이름이 `web_` 로 시작하지 않는 폴더(_qa_* 등 사람이 만든 검수 폴더).
#   · 심볼릭 링크·정리 대상 폴더 밖을 가리키는 경로(realpath 로 확인) — 경로 이탈 방어.
#   · 아직 실행 중(running)인 job 의 결과 폴더.
UPLOADS_TTL_DAYS_DEFAULT = 7
JOBS_TTL_DAYS_DEFAULT = 30
_JOB_CLEANUP_PREFIX = "web_"          # 웹앱이 만든 job 폴더만 정리 대상(api.py create_job_endpoint 규칙)


def ttl_days_from_env(name: str, default: int) -> int:
    """환경변수에서 TTL(일)을 읽는다. 없거나 숫자가 아니거나 1 미만이면 기본값.

    0·음수를 거부하는 이유: '0일' 은 방금 올린 파일까지 지우게 되어 사고로 이어진다.
    끄고 싶으면 GRADER_CLEANUP_DISABLED=1 을 쓴다.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        days = int(raw)
    except ValueError:
        return default
    return days if days >= 1 else default


def _is_inside(path: str, base: str) -> bool:
    """path 가 base 폴더 '안' 인지 realpath 로 판정한다(심볼릭 링크·`..` 이탈 방어)."""
    try:
        real_path = os.path.realpath(path)
        real_base = os.path.realpath(base)
        return os.path.commonpath([real_path, real_base]) == real_base and real_path != real_base
    except (ValueError, OSError):
        # 드라이브가 다르면 commonpath 가 ValueError — 당연히 '밖' 이다.
        return False


def _tree_bytes(path: str) -> int:
    """폴더(또는 파일) 크기 합계. 실패한 항목은 0 으로 센다(집계용이라 정확도보다 안전)."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(root, fn))
            except OSError:
                pass
    return total


def _running_job_dirs() -> set:
    """지금 실행 중(running)인 job 들의 결과 폴더(realpath) 집합 — 청소에서 제외한다."""
    out = set()
    with _JOBS_LOCK:
        for j in _JOBS.values():
            if j.get("status") == "running" and j.get("out_dir"):
                out.add(os.path.realpath(str(j["out_dir"])))
    return out


def cleanup_old_files(uploads_ttl_days: Optional[int] = None,
                      jobs_ttl_days: Optional[int] = None,
                      dry_run: bool = False) -> Dict[str, Any]:
    """오래된 업로드 파일·web_ job 폴더를 mtime 기준으로 지운다(dry_run 이면 집계만).

    인자를 안 주면 환경변수(GRADER_*_TTL_DAYS) → 기본값(7일/30일) 순으로 정한다.
    반환: {uploads_removed, jobs_removed, freed_bytes, errors[], dry_run, uploads_ttl_days, jobs_ttl_days}
      · 항목 하나가 실패해도 멈추지 않고 errors 에 적고 계속 간다.
    """
    if uploads_ttl_days is None:
        uploads_ttl_days = ttl_days_from_env("GRADER_UPLOADS_TTL_DAYS", UPLOADS_TTL_DAYS_DEFAULT)
    if jobs_ttl_days is None:
        jobs_ttl_days = ttl_days_from_env("GRADER_JOBS_TTL_DAYS", JOBS_TTL_DAYS_DEFAULT)

    now = time.time()
    result: Dict[str, Any] = {
        "uploads_removed": 0, "jobs_removed": 0, "freed_bytes": 0, "errors": [],
        "dry_run": bool(dry_run),
        "uploads_ttl_days": int(uploads_ttl_days), "jobs_ttl_days": int(jobs_ttl_days),
    }

    # ① 업로드 파일: uploads 폴더 '바로 아래' 의 일반 파일만(하위 폴더·링크는 건너뜀).
    uploads_dir = get_uploads_dir()
    uploads_cutoff = now - uploads_ttl_days * 86400
    if os.path.isdir(uploads_dir):
        for fn in sorted(os.listdir(uploads_dir)):
            path = os.path.join(uploads_dir, fn)
            try:
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                if not _is_inside(path, uploads_dir):
                    continue  # 경로 이탈(링크 등) — 만지지 않는다
                if os.path.getmtime(path) > uploads_cutoff:
                    continue  # 아직 신선하다
                size = _tree_bytes(path)
                if not dry_run:
                    os.remove(path)
                result["uploads_removed"] += 1
                result["freed_bytes"] += size
            except Exception as e:
                result["errors"].append(f"uploads/{fn}: {type(e).__name__}: {e}")

    # ② job 폴더: 이름이 web_ 로 시작하는 폴더만. 실행 중인 job 은 제외.
    jobs_dir = get_jobs_dir()
    jobs_cutoff = now - jobs_ttl_days * 86400
    running = _running_job_dirs()
    if os.path.isdir(jobs_dir):
        for fn in sorted(os.listdir(jobs_dir)):
            if not fn.startswith(_JOB_CLEANUP_PREFIX):
                continue  # _qa_* · 사람이 만든 폴더 — 절대 안 건드린다
            path = os.path.join(jobs_dir, fn)
            try:
                if os.path.islink(path) or not os.path.isdir(path):
                    continue
                if not _is_inside(path, jobs_dir):
                    continue  # 경로 이탈 방어
                if os.path.realpath(path) in running:
                    continue  # 아직 만드는 중
                if os.path.getmtime(path) > jobs_cutoff:
                    continue
                size = _tree_bytes(path)
                if not dry_run:
                    shutil.rmtree(path)
                result["jobs_removed"] += 1
                result["freed_bytes"] += size
            except Exception as e:
                result["errors"].append(f"jobs/{fn}: {type(e).__name__}: {e}")

    return result


def prune_finished_jobs(max_age_sec: float = 86400.0) -> int:
    """완료(done)·실패(error) 후 max_age_sec 이 지난 _JOBS 메모리 항목을 지운다. 반환: 지운 개수.

    왜: _JOBS 는 진행바 폴링용 메모장이라 완료 뒤엔 쓸모가 없는데 지우는 코드가 없어
    서버를 오래 켜 두면 항목이 계속 쌓였다. 결과 자체는 data/jobs/<id>/job.json 에 있으므로
    메모리에서 지워도 기록 화면·ZIP 재다운로드는 그대로 된다. running 은 절대 안 지운다.
    """
    cutoff = time.time() - max_age_sec
    removed = 0
    with _JOBS_LOCK:
        for job_id in list(_JOBS.keys()):
            j = _JOBS[job_id]
            if j.get("status") not in ("done", "error"):
                continue
            finished = j.get("finished_at") or j.get("started_at") or 0
            if finished < cutoff:
                del _JOBS[job_id]
                removed += 1
    return removed


# ── 정리 실행 결과(관리자 화면 표시용) ───────────────────────────────────────
# main.py 의 청소 스레드가 한 바퀴 돌 때마다 여기에 마지막 결과·다음 예정 시각을 적는다.
# GET /api/maintenance/status 가 이걸 그대로 돌려준다(값 복사본).
_MAINT: Dict[str, Any] = {
    "enabled": True,          # GRADER_CLEANUP_DISABLED=1 이면 False
    "runs": 0,                # 지금까지 돈 횟수
    "last_run": None,         # 마지막 실행 시각(ISO)
    "last_result": None,      # cleanup_old_files 결과 + jobs_pruned
    "last_error": None,       # 마지막 실행이 통째로 실패했으면 사유
    "next_run": None,         # 다음 예정 시각(ISO)
}
_MAINT_LOCK = threading.Lock()


def record_maintenance(**fields: Any) -> None:
    """정리 상태 일부 필드를 갱신한다(자물쇠로 보호)."""
    with _MAINT_LOCK:
        _MAINT.update(fields)


def get_maintenance_status() -> Dict[str, Any]:
    """정리 상태 사본을 돌려준다(호출자가 만져도 안전)."""
    with _MAINT_LOCK:
        return json.loads(json.dumps(_MAINT, ensure_ascii=False, default=str))
