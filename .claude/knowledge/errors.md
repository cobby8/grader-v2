# 에러 및 함정 모음
<!-- 담당: debugger, tester | 최대 30항목 -->
<!-- 이 프로젝트에서 반복되는 에러 패턴, 함정, 주의사항을 기록 -->

### [2026-06-15] 한글 Windows cp949 콘솔 UnicodeEncodeError
- **분류**: error
- **발견자**: debugger
- **내용**: 한글 Windows 기본 콘솔 인코딩은 cp949. 파이썬 프로그램이 '—'(U+2014), '→'(U+2192) 등 cp949에 없는 유니코드 문자를 print하면 UnicodeEncodeError로 크래시. 엔진 로직과 무관(PYTHONUTF8=1이면 PASS). 해결: 진입점에서 sys.stdout/sys.stderr.reconfigure(encoding="utf-8")로 출력 스트림 UTF-8 고정. 예방규칙: 한글 Win에서 도는 모든 파이썬 CLI는 진입점에서 stdout/stderr UTF-8 고정 + 파일은 open(encoding="utf-8") 명시.
- **참조횟수**: 0
