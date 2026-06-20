# -*- coding: utf-8 -*-
"""직원용 기동 스크립트 — uvicorn 으로 서버를 켜고 브라우저를 자동으로 연다.

사용법:
  python -m webapp.run        (또는 run.bat 더블클릭)

비유: 직원은 '시동 버튼' 하나만 누르면 된다. 이 파일이 서버를 켜고(uvicorn),
브라우저로 작업 화면(localhost:8000)을 대신 열어 준다.
"""
from __future__ import annotations

import threading
import webbrowser

import uvicorn

from .state import DEFAULT_PORT


def _open_browser_later(port: int) -> None:
    """서버가 막 켜진 직후 브라우저를 연다.

    이유: 서버가 완전히 뜨기 전에 브라우저를 열면 '연결 실패' 화면이 보인다.
    그래서 1.2초 뒤(서버 기동 여유)에 한 번 열도록 타이머로 약간 미룬다.
    """
    threading.Timer(
        1.2, lambda: webbrowser.open(f"http://localhost:{port}")
    ).start()


def main() -> None:
    """서버를 기동한다(개발서버 reload 없이 단일 프로세스)."""
    _open_browser_later(DEFAULT_PORT)
    # 직원 PC 단일 기동이라 reload=False. 외부 노출 없이 로컬만 듣는다.
    uvicorn.run("webapp.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    main()
