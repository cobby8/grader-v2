# 코딩 규칙 및 스타일
<!-- 담당: developer, reviewer | 최대 30항목 -->
<!-- 이 프로젝트만의 코드 스타일, 네이밍 규칙, 패턴을 기록 -->

### [2026-06-15] engine 공개 API 불변 — 새 기능은 import만
- **분류**: convention
- **발견자**: reviewer
- **내용**: 검증된 출력 코어 engine/{compose,pattern,pdfutil,preview,verify}.py 는 "주어진 것"으로 절대 수정 금지. 새 기능(grade.py 등)은 이들을 **import만** 해서 조립한다. CLI 진입점 engine/cli.py 만 예외적으로 기존 selftest/build/parse를 깨지 않는 **최소 서브커맨드 추가** 허용. 이유: 무손실 CMYK 보장이 검증된 코어를 건드리면 그 보장이 깨질 위험.
- **참조횟수**: 0

### [2026-06-15] 무손실 좌표 분리 — 합성 로직은 transform만 계산
- **분류**: convention
- **발견자**: reviewer
- **내용**: 디자인 배치/그레이딩 로직은 좌표(Piece.transform=cm 행렬)와 클립 윤곽만 계산한다. 색공간/이미지/스트림을 재인코딩·재압축·변환하는 코드는 절대 넣지 않는다(device CMYK 바이트 동일 보존). 색을 만지는 순간 "완전 보존" 가설이 깨진다.
- **참조횟수**: 0

### [2026-06-15] 입력/preset 선검증 — 친절한 한글 에러
- **분류**: convention
- **발견자**: developer/reviewer
- **내용**: preset.json·디자인·패턴 등 입력은 사용 전에 파일존재/JSON파싱/필수키/값 길이를 먼저 검사하고, 실패 시 비개발자가 이해할 한글 메시지로 즉시 중단한다. 바이브 코더가 잘못된 입력을 바로 알아채게 하기 위함.
- **참조횟수**: 0

### [2026-06-25] _handoff↔webapp/static 비대칭 — 재복사 시 API/인증 코드 소실 주의
- **분류**: convention
- **발견자**: reviewer
- **내용**: 규칙상 webapp/static은 _handoff/grader-v2-static 복사본(원본 무수정, 갱신시 재복사). 그러나 **fetch(/api) 호출·apiFetch 인증 래퍼는 webapp/static 화면(work/patterns/settings/history)에만 있고 _handoff 원본엔 없다**(이전 단계에서 static에 직접 API연동 추가, 원본 역반영 안 됨). → _handoff를 그대로 재복사하면 동작중인 API연동+인증이 통째로 사라지는 회귀 발생. **대응**: ①가급적 _handoff 원본에 동일 코드를 역반영해 비대칭을 해소하거나, ②재복사 전 반드시 webapp/static의 apiFetch·fetch 블록을 보존(diff 확인)한다. login.html(신규)만 원본=복사본 동일 유지 중.
- **참조횟수**: 0
