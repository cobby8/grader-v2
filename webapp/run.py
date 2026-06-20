# -*- coding: utf-8 -*-
"""직원용 기동 스크립트 — uvicorn 으로 서버를 켜고 브라우저를 자동으로 연다.

사용법:
  python -m webapp.run        (또는 run.bat 더블클릭)

비유: 직원은 '시동 버튼' 하나만 누르면 된다. 이 파일이 서버를 켜고(uvicorn),
브라우저로 작업 화면(localhost:8000)을 대신 열어 준다.

왜 점검 로직이 여기(파이썬)에 있나:
  Windows 배치파일(run.bat)에 한국어 안내를 많이 넣으면 글자가 깨져서
  명령으로 잘못 읽히는 문제가 있다. 그래서 배치파일은 '파이썬 실행'만 하는
  얇은 껍데기로 두고, 똑똑한 점검과 한국어 안내는 UTF-8 을 완벽히 다루는
  파이썬(이 파일)이 담당한다.
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser

from .state import DEFAULT_PORT


def _check_dependencies() -> bool:
    """서버 핵심 부품(fastapi/uvicorn)이 깔려 있는지 확인한다.

    이유: 부품이 없으면 uvicorn import 단계에서 못생긴 영어 에러가 뜬다.
    직원이 당황하지 않게, 먼저 점검해서 '무엇을 어떻게 설치하라'고 한국어로 안내한다.
    반환: 부품이 다 있으면 True, 하나라도 없으면 False(+안내 출력).
    """
    missing = []
    for mod in ("fastapi", "uvicorn"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if not missing:
        return True

    # 어떤 파이썬으로 설치해야 하는지 현재 실행 중인 파이썬 경로를 그대로 안내한다.
    py = sys.executable or "python"
    print("")
    print("=" * 56)
    print("  [문제] 필요한 라이브러리가 아직 설치되지 않았습니다.")
    print("=" * 56)
    print("")
    print("  없는 부품:", ", ".join(missing))
    print("")
    print("  아래 명령을 한 번만 실행하면 됩니다(복사해 붙여넣기):")
    print("")
    print(f'      "{py}" -m pip install -r requirements.txt')
    print("")
    print("  설치가 끝나면 run.bat 을 다시 더블클릭하세요.")
    print("  (인터넷 연결이 필요합니다. 사내 오프라인 환경이면 관리자에게 문의)")
    print("")
    return False


def _open_browser_later(port: int) -> None:
    """서버가 막 켜진 직후 브라우저를 연다.

    이유: 서버가 완전히 뜨기 전에 브라우저를 열면 '연결 실패' 화면이 보인다.
    그래서 1.2초 뒤(서버 기동 여유)에 한 번 열도록 타이머로 약간 미룬다.

    참고: 자동 테스트 등에서 실제 브라우저를 띄우고 싶지 않을 때를 위해
    환경변수 GRADER_NO_BROWSER=1 이면 자동 열기를 건너뛴다(서버 기동에는 영향 없음).
    """
    if os.environ.get("GRADER_NO_BROWSER") == "1":
        return
    threading.Timer(
        1.2, lambda: webbrowser.open(f"http://localhost:{port}")
    ).start()


def main() -> None:
    """서버를 기동한다(개발서버 reload 없이 단일 프로세스)."""
    # 1) 부품 점검 — 없으면 한국어 안내 후 정상 종료(크래시 아님).
    if not _check_dependencies():
        sys.exit(1)

    # 2) 부품 확인 후에야 uvicorn 을 import 한다(없을 때 ImportError 회피).
    import uvicorn

    print("")
    print(f"[시작] 서버를 켜는 중입니다... 브라우저가 곧 자동으로 열립니다.")
    print(f"       열리지 않으면 주소창에  http://localhost:{DEFAULT_PORT}  를 입력하세요.")
    print(f"       (이 창은 닫지 말고 그대로 두세요. 닫으면 서버가 꺼집니다.)")
    print("")

    _open_browser_later(DEFAULT_PORT)
    # 직원 PC 단일 기동이라 reload=False. 외부 노출 없이 로컬만 듣는다.
    uvicorn.run("webapp.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    main()
