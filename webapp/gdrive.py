# -*- coding: utf-8 -*-
"""Google Drive 연동 — 서비스 계정(로봇 계정)으로 공유드라이브를 '읽기 전용' 탐색.

왜 이 파일이 따로 있나(비유):
  패턴(.ai 모음)은 회사 '공유 드라이브'라는 창고에 들어 있다. 이 앱(Render 서버)이
  그 창고를 직접 열어보려면 '출입증'이 필요하다. 직원마다 구글 로그인을 시키는 대신,
  앱 전용 '로봇 계정(서비스 계정)'에게 창고 열쇠(JSON 키)를 주고, 앱은 그 로봇을
  통해 창고 목록을 읽는다. 이 파일이 '로봇에게 창고를 열게 하는 창구'다.
  다른 코드(api.py)는 여기 함수만 부르고, 구글 API 세부는 몰라도 된다.

핵심 설계(auth.py 와 같은 규칙):
  · 비밀키 노출 0 : 서비스계정 JSON 은 코드·레포에 절대 없다. 환경변수(GDRIVE_SA_JSON)로만
                    주입한다(Render 대시보드). .env(로컬)도 git 제외.
  · 읽기 전용     : 스코프를 drive.readonly 로 못박아, 실수로도 창고를 바꾸거나 지울 수 없다.
  · 토글          : GDRIVE_SA_JSON / GDRIVE_ROOT_FOLDER_ID 가 없으면 '미설정'으로 간주.
                    이 기능을 안 쓰는 로컬·기존 배포는 아무 영향 없음(회귀 0).
  · 공유드라이브  : 목록/다운로드 호출에 supportsAllDrives=True, includeItemsFromAllDrives=True
                    를 붙여야 '공유 드라이브(My Drive 아님)' 항목이 보인다.

환경변수:
  GDRIVE_SA_JSON        : 서비스계정 JSON. '원본 JSON 문자열' 또는 'base64 로 인코딩한 한 줄'
                          둘 다 받는다(JSON 은 줄바꿈이 많아 env 에 넣기 까다로우므로 base64 권장).
  GDRIVE_ROOT_FOLDER_ID : 트리 탐색의 시작(루트) 폴더 ID. Drive URL .../folders/<이 값>.

성능:
  서비스 클라이언트(build 결과)는 만드는 데 비용이 있으므로 모듈 전역에 1회 캐시한다.
  (--workers 1 = 프로세스 1개라 캐시가 한 곳에 모여 일관적이다. auth.py 캐시와 같은 전제.)
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
import threading
from typing import Any, Dict, List, Optional

# 읽기 전용 스코프 — 창고를 '보기만' 한다(수정/삭제 권한 없음).
_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Drive 폴더를 나타내는 특수 MIME 타입(이게 아니면 일반 파일=잎).
_FOLDER_MIME = "application/vnd.google-apps.folder"

# ── 서비스 클라이언트 캐시(모듈 전역) ──────────────────────────────────────
# 한 번 만든 Drive 클라이언트를 재사용한다. 여러 요청 스레드가 동시에 만질 수 있어 Lock 보호.
_SERVICE: Any = None
_SERVICE_LOCK = threading.Lock()


class DriveConfigError(RuntimeError):
    """서비스계정/루트폴더 env 가 없거나 형식이 잘못됨(=서버 설정 오류, 500 대상)."""


class DriveError(RuntimeError):
    """Drive API 호출 자체가 실패함(권한 없음·네트워크·잘못된 폴더ID 등)."""


def is_configured() -> bool:
    """이 기능을 쓸 수 있는 상태인지(두 env 가 모두 채워졌는지) 여부.

    api.py 는 이 값이 False 면 사용자에게 '관리자 설정 필요' 안내를 돌려주면 된다.
    """
    return bool(_get_sa_raw()) and bool(root_folder_id())


def root_folder_id() -> str:
    """트리 탐색의 기본 시작 폴더 ID(GDRIVE_ROOT_FOLDER_ID). 없으면 빈 문자열."""
    return (os.environ.get("GDRIVE_ROOT_FOLDER_ID") or "").strip()


def _get_sa_raw() -> str:
    """환경변수에서 서비스계정 JSON 원문(문자열)만 꺼낸다(파싱 전). 없으면 빈 문자열."""
    return (os.environ.get("GDRIVE_SA_JSON") or "").strip()


def _load_sa_info() -> Dict[str, Any]:
    """GDRIVE_SA_JSON 을 dict 로 해석한다.

    두 입력 형태를 모두 받는다:
      1) 원본 JSON 문자열 : 그대로 json.loads.
      2) base64 한 줄     : 먼저 base64 디코드 → json.loads.
    판별 순서: '{' 로 시작하면 원본 JSON 으로 우선 시도, 아니면 base64 로 시도.
    (base64 결과가 다시 JSON 이어야 하므로, 둘 다 실패하면 설정 오류로 본다.)
    """
    raw = _get_sa_raw()
    if not raw:
        raise DriveConfigError(
            "GDRIVE_SA_JSON 환경변수가 비어 있습니다(서비스계정 키 미설정)."
        )

    # 1) 원본 JSON 우선(관리자가 JSON 을 그대로 붙여넣은 경우).
    if raw.lstrip().startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:  # 깨진 JSON
            raise DriveConfigError(f"GDRIVE_SA_JSON JSON 파싱 실패: {exc}") from exc

    # 2) base64 로 인코딩된 한 줄(권장) — 디코드 후 JSON.
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise DriveConfigError(
            "GDRIVE_SA_JSON 을 해석할 수 없습니다(원본 JSON 도 base64 도 아님)."
        ) from exc
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise DriveConfigError(
            f"GDRIVE_SA_JSON base64 디코드 후 JSON 파싱 실패: {exc}"
        ) from exc


def get_service() -> Any:
    """Drive v3 클라이언트를 반환(최초 1회 생성 후 캐시).

    비유: 로봇에게 열쇠(JSON)를 쥐여주고 '창고 담당자' 로 세워 두는 일. 한 번 세워 두면
    다음부터는 그 담당자에게 바로 목록을 물어본다.
    실패 시 DriveConfigError(키 문제) 를 던진다 — 호출부(api.py)가 500 으로 감싸면 된다.
    """
    global _SERVICE
    if _SERVICE is not None:
        return _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is not None:  # 다른 스레드가 먼저 만들었을 수 있음
            return _SERVICE
        # 무거운 import 는 이 기능을 실제로 쓸 때만(로컬 미사용 시 import 비용 0).
        try:
            from google.oauth2 import service_account  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except ImportError as exc:  # 라이브러리 미설치
            raise DriveConfigError(
                "google-auth/google-api-python-client 가 설치되어 있지 않습니다."
            ) from exc

        info = _load_sa_info()
        try:
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=_SCOPES
            )
        except (ValueError, KeyError) as exc:  # JSON 은 맞는데 서비스계정 형식이 아님
            raise DriveConfigError(f"서비스계정 자격증명 생성 실패: {exc}") from exc

        # cache_discovery=False : 디스크에 API 스키마 캐시를 안 남긴다(경고·쓰기 방지).
        _SERVICE = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _SERVICE


def list_children(folder_id: str) -> List[Dict[str, Any]]:
    """폴더 하나의 '바로 아래' 항목(하위 폴더·파일)만 1단계 나열(지연 로딩용).

    반환: [{id, name, isFolder(bool), mimeType}, ...] — 폴더 먼저, 그 안에서 이름순.
    공유드라이브 항목까지 보이도록 supportsAllDrives/includeItemsFromAllDrives 를 켠다.
    항목이 많으면 nextPageToken 으로 끝까지 모은다(페이지네이션).
    """
    folder_id = (folder_id or "").strip()
    if not folder_id:
        raise DriveError("folder_id 가 비어 있습니다.")

    service = get_service()
    # q: 이 폴더를 부모로 두고, 휴지통에 없는 것만.
    query = f"'{folder_id}' in parents and trashed = false"
    items: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    try:
        while True:
            resp = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType)",
                    orderBy="folder,name",
                    pageSize=200,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora="allDrives",
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                items.append(
                    {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "mimeType": f.get("mimeType"),
                        "isFolder": f.get("mimeType") == _FOLDER_MIME,
                    }
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except Exception as exc:  # googleapiclient.errors.HttpError 등
        raise DriveError(f"Drive 폴더 목록 조회 실패: {exc}") from exc
    return items


def download_file(file_id: str, dest_path: str) -> str:
    """파일 하나를 dest_path 로 내려받는다(패턴 등록 시 .ai 원본 가져오기용).

    get_media = 구글 문서 export 가 아니라 '올려둔 원본 바이너리'를 그대로 받는다(.ai/.pdf).
    반환: dest_path(성공 시). 실패 시 DriveError.
    """
    file_id = (file_id or "").strip()
    if not file_id:
        raise DriveError("file_id 가 비어 있습니다.")

    service = get_service()
    try:
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore
    except ImportError as exc:
        raise DriveConfigError(
            "google-api-python-client 가 설치되어 있지 않습니다."
        ) from exc

    try:
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        with io.FileIO(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
    except Exception as exc:
        raise DriveError(f"Drive 파일 다운로드 실패(file_id={file_id}): {exc}") from exc
    return dest_path


def get_file_meta(file_id: str) -> Dict[str, Any]:
    """파일/폴더 1개의 메타(id, name, mimeType). 이름 기반 자동 제안 등에 사용."""
    file_id = (file_id or "").strip()
    if not file_id:
        raise DriveError("file_id 가 비어 있습니다.")
    service = get_service()
    try:
        f = (
            service.files()
            .get(fileId=file_id, fields="id, name, mimeType", supportsAllDrives=True)
            .execute()
        )
    except Exception as exc:
        raise DriveError(f"Drive 메타 조회 실패(file_id={file_id}): {exc}") from exc
    return {
        "id": f.get("id"),
        "name": f.get("name"),
        "mimeType": f.get("mimeType"),
        "isFolder": f.get("mimeType") == _FOLDER_MIME,
    }
