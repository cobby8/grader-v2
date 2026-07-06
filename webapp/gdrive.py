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

성능/동시성(중요):
  서비스 클라이언트(build 결과)는 만드는 데 비용이 있으므로 캐시한다. 단, 내부 HTTP 연결
  (httplib2.Http)은 '스레드 세이프가 아니다' — 한 연결(=TLS 소켓 1개)을 여러 스레드가
  동시에 쓰면 소켓에 write 가 겹쳐 `[SSL] record layer failure` 로 깨진다. FastAPI 는
  sync 엔드포인트(drive_tree 등)를 스레드풀에서 '동시에' 돌리므로, 전역 1개를 공유하면
  폴더 하위를 여러 개 동시에 펼칠 때 이 충돌이 난다.
  → 그래서 전역 공유 대신 **스레드마다 자기 서비스(=자기 httplib2 연결)** 를 갖게 한다
    (threading.local). 스레드풀 스레드는 재사용되므로 스레드당 build 1회 후 캐시된다.
  → 추가로, 전송계층 일시 실패(SSL/연결 끊김 등)는 그 스레드의 연결을 폐기·재생성해서
    새 연결로 딱 한 번 더 시도한다(_call_with_retry). 권한/없음(HttpError)은 재시도 안 함.
  (--workers 1 = 프로세스 1개 전제는 그대로. 스레드는 여러 개.)
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

# ── 서비스 클라이언트 캐시(스레드마다 따로) ────────────────────────────────
# httplib2 연결이 스레드 비세이프라, 전역 1개를 공유하지 않고 '스레드별'로 캐시한다.
# threading.local() = 스레드마다 독립된 서랍. 각 스레드가 자기 서랍(.service)에만 손댄다.
# 스레드풀 스레드는 재사용되므로 스레드당 build 1회 후 그 스레드 서랍에 남아 재사용된다.
_THREAD_LOCAL = threading.local()

# 전송계층 '일시 실패' 로 볼 예외들(모듈 로드시가 아니라 처음 필요할 때 만들어 캐시).
# 이 예외면 그 스레드의 연결을 폐기·재생성해 1회 재시도한다. HttpError(권한/없음)는 제외.
_TRANSIENT_ERRORS_CACHE: Optional[tuple] = None


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


def _build_service() -> Any:
    """Drive v3 클라이언트를 '새로' 만든다(캐시 안 함). get_service/_reset_service 내부용.

    무거운 부분(google import·자격증명 생성)은 여기 그대로 둔다 — 이 기능을 실제로
    쓰는 스레드에서만 돈다(로컬 미사용 시 import 비용 0).
    실패 시 DriveConfigError(키/설치 문제) 를 던진다 — 호출부(api.py)가 처리.
    """
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
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_service() -> Any:
    """현재 스레드의 Drive v3 클라이언트를 반환(스레드마다 최초 1회 생성 후 캐시).

    비유: 스레드(창구 직원) 저마다 자기 전화기(연결)를 든다. 옆 창구와 전화선을 나눠 쓰지
    않으니, 여러 창구가 '동시에' 창고에 물어봐도 통화가 섞이지 않는다(=SSL 충돌 없음).
    실패 시 DriveConfigError(키 문제) 를 던진다 — 호출부(api.py)가 500 으로 감싸면 된다.
    """
    svc = getattr(_THREAD_LOCAL, "service", None)
    if svc is not None:
        return svc
    svc = _build_service()
    _THREAD_LOCAL.service = svc  # 이 스레드 서랍에만 저장(다른 스레드와 공유 안 함)
    return svc


def _reset_service() -> None:
    """현재 스레드의 캐시된 서비스를 폐기한다(다음 get_service 가 새 연결로 재생성).

    전송계층 일시 실패(SSL/연결 끊김 등) 후, 망가졌을 수 있는 이 스레드의 httplib2 연결을
    버리고 다음 호출에서 깨끗한 새 연결을 쓰게 한다.
    """
    if getattr(_THREAD_LOCAL, "service", None) is not None:
        _THREAD_LOCAL.service = None


def _transient_errors() -> tuple:
    """'일시적 전송계층 실패'로 볼 예외 타입 튜플(처음 호출 때 만들어 캐시).

    이 예외들이면 연결이 순간적으로 깨진 것으로 보고 연결을 새로 만들어 재시도한다.
    ⚠️ googleapiclient 의 HttpError(403/404 등 권한·없음)는 '일시적'이 아니므로 포함하지
       않는다 → 재시도 없이 그대로 전파돼 DriveError 로 감싸진다.
    """
    global _TRANSIENT_ERRORS_CACHE
    if _TRANSIENT_ERRORS_CACHE is not None:
        return _TRANSIENT_ERRORS_CACHE

    import http.client  # 표준 라이브러리(가벼움). 처음 필요할 때만 로드.
    import ssl

    # ssl.SSLError / ConnectionError / BrokenPipeError / socket.error 는 모두 OSError 하위라
    # OSError 하나로도 포함되지만, 의도를 드러내려고 대표 타입을 명시한다.
    types: list = [
        ssl.SSLError,  # [SSL] record layer failure 등 TLS 계층 실패
        OSError,  # socket.error·ConnectionError·BrokenPipeError 상위 = 전송계층 일반
        ConnectionError,  # (명시) 연결 리셋/중단
        BrokenPipeError,  # (명시) 소켓 파이프 깨짐
        http.client.HTTPException,  # BadStatusLine·IncompleteRead·RemoteDisconnected 등
    ]
    # httplib2 가 설치돼 있으면(=Drive 기능 사용 환경) 그 전송 예외도 포함.
    try:
        from httplib2 import HttpLib2Error, ServerNotFoundError  # type: ignore

        types.extend([ServerNotFoundError, HttpLib2Error])
    except ImportError:
        pass

    _TRANSIENT_ERRORS_CACHE = tuple(types)
    return _TRANSIENT_ERRORS_CACHE


def _call_with_retry(fn: Any) -> Any:
    """fn(service) 를 실행하되, '전송계층 일시 실패'면 연결을 새로 만들어 1회만 더 시도한다.

    총 2회 시도(원래 1 + 재시도 1). 재시도 전에 현재 스레드 서비스를 폐기(_reset_service)해
    깨끗한 새 연결(get_service 가 재생성)로 다시 부른다.
    ⚠️ HttpError(권한/없음) 등 비-전송 예외는 여기서 안 잡히고 그대로 위로 전파된다
       → 호출부의 except 가 DriveError 로 감싼다(재시도 안 함).
    """
    try:
        return fn(get_service())
    except _transient_errors():
        # 이 스레드의 (아마 망가진) 연결을 버리고, 새 연결로 딱 한 번 더.
        _reset_service()
        return fn(get_service())


def list_children(folder_id: str) -> List[Dict[str, Any]]:
    """폴더 하나의 '바로 아래' 항목(하위 폴더·파일)만 1단계 나열(지연 로딩용).

    반환: [{id, name, isFolder(bool), mimeType}, ...] — 폴더 먼저, 그 안에서 이름순.
    공유드라이브 항목까지 보이도록 supportsAllDrives/includeItemsFromAllDrives 를 켠다.
    항목이 많으면 nextPageToken 으로 끝까지 모은다(페이지네이션).
    """
    folder_id = (folder_id or "").strip()
    if not folder_id:
        raise DriveError("folder_id 가 비어 있습니다.")

    # 설정 검증은 여기서(try 밖) — 미설정이면 DriveConfigError 를 그대로 전파(아래 try 에
    # 안 감싸지게). 실제 호출은 _call_with_retry 가 스레드 서비스를 다시 받아 쓴다.
    get_service()
    # q: 이 폴더를 부모로 두고, 휴지통에 없는 것만.
    query = f"'{folder_id}' in parents and trashed = false"
    items: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    try:
        while True:
            # 각 페이지의 .execute() 를 재시도 단위로 감싼다. 재시도 시 같은 pageToken 으로
            # 재실행(서버측 토큰이라 유효)하고, 이미 모은 items 는 그대로 유지된다.
            # pt=page_token 으로 현재 값을 바인딩(재시도해도 같은 페이지를 다시 부름).
            resp = _call_with_retry(
                lambda svc, pt=page_token: svc.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType)",
                    orderBy="folder,name",
                    pageSize=200,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora="allDrives",
                    pageToken=pt,
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

    # 설정 검증은 try 밖에서(미설정이면 DriveConfigError 그대로 전파).
    get_service()
    try:
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore
    except ImportError as exc:
        raise DriveConfigError(
            "google-api-python-client 가 설치되어 있지 않습니다."
        ) from exc

    # 다운로드 한 번(요청 생성→파일 열기→청크 루프)을 재시도 단위로 감싼다. 전송계층이
    # 순간 끊기면 연결을 새로 만들어 처음부터 다시 받는다(FileIO "wb" 가 파일을 새로 비움).
    def _do_download(svc: Any) -> str:
        request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        with io.FileIO(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
        return dest_path

    try:
        return _call_with_retry(_do_download)
    except Exception as exc:
        raise DriveError(f"Drive 파일 다운로드 실패(file_id={file_id}): {exc}") from exc


def get_file_meta(file_id: str) -> Dict[str, Any]:
    """파일/폴더 1개의 메타(id, name, mimeType). 이름 기반 자동 제안 등에 사용."""
    file_id = (file_id or "").strip()
    if not file_id:
        raise DriveError("file_id 가 비어 있습니다.")
    # 설정 검증은 try 밖에서(미설정이면 DriveConfigError 그대로 전파).
    get_service()
    try:
        f = _call_with_retry(
            lambda svc: svc.files()
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
