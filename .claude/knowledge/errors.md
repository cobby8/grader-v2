# 에러 및 함정 모음
<!-- 담당: debugger, tester | 최대 30항목 -->
<!-- 이 프로젝트에서 반복되는 에러 패턴, 함정, 주의사항을 기록 -->

### [2026-06-15] pikepdf 출력은 비결정적 — "바이트 동일" 회귀는 XObject 이름 통일 후 비교
- **분류**: error
- **발견자**: developer
- **내용**: compose 가 페이지 리소스에 디자인 Form 을 등록할 때 `page.add_resource()` 가 매 실행마다 **랜덤 22자 XObject 이름**(예 `/m7sgcvE74pBb70-IpyYT_A` vs `/uUgSFUmMJ1num_FR8x8Usg`)을 부여한다. 그래서 같은 코드·같은 입력으로 두 번 돌려도 **PDF 바이트가 다르다**(콘텐츠 스트림 안 `/이름 Do` 와 리소스 딕셔너리의 이름이 매번 달라짐, 압축 스트림이라 통째로 바뀜). 파일 크기는 동일·구조도 동일. **함정**: A-2/A-4 회귀 기준 "previewA/출력과 바이트 동일"을 `cmp`/`md5sum` 순수 바이트로 검증하면 코드가 정상이어도 항상 FAIL 처럼 보인다. **올바른 회귀 검증법**: pikepdf 로 양쪽을 열어 `page.obj.Contents.read_bytes()`(압축 해제됨)를 꺼내, 페이지 Resources.XObject 의 이름을 공통 토큰('/X')으로 치환한 뒤 콘텐츠 문자열을 비교한다(A-4 검증에서 길이 4097 100% 일치 확인). 또는 verify_output 의 "디자인 Form 바이트 동일/단일임베드/래스터 미추가" PASS 로 무손실을 간접 증명한다.
- **참조횟수**: 0

### [2026-06-15] fontTools 글리프 좌표는 '폰트단위' — em→pt 배율(scale) 말고 폰트단위→pt 배율(u=scale/upm)을 곱해야
- **분류**: error
- **발견자**: developer
- **내용**: text.py 글리프→PDF경로 변환에서 `_glyph_path_ops` 가 글리프 윤곽 좌표에 배율을 곱하는데, 글리프 좌표는 0~unitsPerEm(2048) 범위의 '폰트단위'다. 여기에 em→pt 배율 `scale`(=칸에 맞춘 글자높이) 을 그대로 곱하면 좌표가 **upm(2048)배 폭주**(100pt 칸에 '7' 한 글자가 16000pt 로 나옴). 반드시 폰트단위→pt 배율 `u = scale / upm` 을 곱해야 한다. 구분: scale=em(1글자칸)→pt, u=폰트내부단위→pt. advance(글자 진행폭)도 폰트단위라 `adv * u` 로 전진. 첫 렌더 좌표가 비정상적으로 크면 이 단위 혼동을 의심.
- **참조횟수**: 0

### [2026-06-15] 한글 Windows cp949 콘솔 UnicodeEncodeError
- **분류**: error
- **발견자**: debugger
- **내용**: 한글 Windows 기본 콘솔 인코딩은 cp949. 파이썬 프로그램이 '—'(U+2014), '→'(U+2192) 등 cp949에 없는 유니코드 문자를 print하면 UnicodeEncodeError로 크래시. 엔진 로직과 무관(PYTHONUTF8=1이면 PASS). 해결: 진입점에서 sys.stdout/sys.stderr.reconfigure(encoding="utf-8")로 출력 스트림 UTF-8 고정. 예방규칙: 한글 Win에서 도는 모든 파이썬 CLI는 진입점에서 stdout/stderr UTF-8 고정 + 파일은 open(encoding="utf-8") 명시.
- **참조횟수**: 0
