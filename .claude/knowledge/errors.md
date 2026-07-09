# 에러 및 함정 모음
<!-- 담당: debugger, tester | 최대 30항목 -->
<!-- 이 프로젝트에서 반복되는 에러 패턴, 함정, 주의사항을 기록 -->

### [2026-07-09] Supabase Storage 는 오브젝트 키에 **비ASCII(한글)·`%` 를 거부(400 InvalidKey)** — httpx가 퍼센트인코딩해도 서버가 디코딩 후 재검증. degrade가 실패를 숨겨 "조용히 백업 안 됨"
- **분류**: error
- **발견자**: debugger
- **내용**: Phase B 백업이 실서버에서 **조용히 실패**(등록은 성공·패턴목록 늘어남, 그런데 Storage 버킷 `pattern-presets` 에 zip 안 생김). 인프라(버킷·RLS admin쓰기·anon읽기·publishable·JWT릴레이)는 직접 upload 200 으로 전부 정상 확정. **근본원인**: `storage_backup.backup_pattern` 이 업로드 URL `.../object/pattern-presets/{pattern_id}.zip` 을 만들 때 pattern_id 가 한글(예 `V넥_상의_슬림(암홀O)`)인데, **Supabase Storage 의 오브젝트 키 검증이 비ASCII 문자를 거부**한다 → HTTP 400 `{"error":"InvalidKey"}`. `backup_pattern` 은 200/201 만 성공으로 보고 그 외 status 는 `백업 실패(status 400)` 로그만 남기고 `return False`(degrade) → 등록은 정상, 백업만 조용히 skip. **실측 격리(anon 키로 키검증만 관찰: 유효키=403 RLS 도달, 무효키=400 InvalidKey)**: `abc.zip`·`abc(def).zip`·`abc def.zip`=키OK(**괄호·공백은 무해**), `농구.zip`·`농구_U넥.zip`·`V넥.zip`=전부 **400 InvalidKey**(=한글만 원인). **중요 함정**: (1) httpx 는 URL path 의 한글을 이미 `%EB%84%A5…` 로 퍼센트인코딩해서 보낸다 — 그런데 Supabase 가 **디코딩한 뒤 원래 키(한글)를 검증**하므로 `urllib.parse.quote` 를 코드에 더 넣어도 소용없다(오히려 `%` 자체도 InvalidKey 로 거부됨=실측). (2) 이 프로젝트는 **모든 패턴명이 한글**이라 백업이 사실상 100% 실패였는데, 로컬 커밋본 2개(농구_U넥/농구_V넥)는 git 으로 들어와 업로드를 한 번도 안 탔고, 단위/모킹 테스트도 실 Supabase 키검증을 안 거쳐서 여태 안 드러났다. (3) degrade(예외 안 던지고 False)가 "있으면 좋은 부가기능" 을 위해 설계됐지만, **정상 경로가 항상 실패하는 상황까지 조용히 숨겨** 버렸다. **해결(developer 예정)**: 오브젝트 키를 ASCII-only 가역 인코딩으로 바꾼다 — **실측 통과+가역 확인**: `hex`(`name.encode('utf-8').hex()+'.zip'`, `bytes.fromhex` 로 복원)·`base64.urlsafe`(패딩 제거/복원 시 재부착) 둘 다 키검증 통과. 로컬 폴더명은 한글 그대로 두고(파일시스템 무관), **Storage 오브젝트 키만** 인코딩. `backup_pattern`(인코딩)·`restore_missing`(디코딩)·필요시 `list_backups` 를 같은 스킴으로 일치시켜야 함(list_backups 는 restore 내부에서만 쓰이므로 restore 에서 디코딩하면 됨). 기존 백업 0개라 마이그레이션 불필요. **예방규칙**: (1) 외부 저장소(S3/Storage) 키에 사용자 유래 문자열(한글 패턴명 등)을 그대로 쓰지 말고 ASCII-safe 인코딩/해시로 변환. (2) "실패해도 진행"(degrade)하는 부가기능은 **정상 경로가 성공하는지 실측 e2e 한 번은 반드시** 거친다 — degrade 는 예외 상황을 숨기라고 있는 것이지 정상 경로 실패를 숨기라고 있는 게 아니다. 실패 status 를 로그로 남기는 것만으론 부족(아무도 안 봄) → 최소 1회 실 업로드 검증. (3) httpx 등 클라이언트가 URL 을 자동 인코딩하는지와, **서버가 디코딩 후 무엇을 검증하는지**는 별개다 — "인코딩 안 해서 실패" 라고 단정 말고 실제 요청/응답으로 확인.
- **참조횟수**: 0

### [2026-07-09] 라우트 등록 검증 시 `app.routes` 를 순회하면 서브라우트가 안 보인다 — 이 FastAPI 버전은 include_router 를 `_IncludedRouter` 로 지연 마운트
- **분류**: error
- **발견자**: tester
- **내용**: Phase B 3·4단계에서 `create_pattern` 에 `request: Request` 를 추가해 **라우팅이 안 깨졌는지** 검증하려고 `webapp.main.app.routes` 를 순회해 `/api/patterns` 를 찾았더니 **하나도 안 나오고**, 심지어 `r.path` 접근 시 `AttributeError: '_IncludedRouter' object has no attribute 'path'` 가 났다. 원인은 코드 버그가 아니라 **이 FastAPI/Starlette 버전이 `app.include_router(...)` 를 즉시 펼치지 않고 `_IncludedRouter` 라는 지연 마운트 객체로 담아둔다**는 것. `app.routes` 최상위엔 openapi/docs/Mount(static)/`_IncludedRouter`×2/@app.get 라우트만 보이고, 실제 `/api/*` 서브라우트는 그 안에 접혀 있다. **함정**: 이걸 모르면 "라우트가 사라졌다=시그니처가 깨졌다" 로 오판하거나, `getattr(r,'path')` KeyError 로 검증 스크립트가 죽는다. **올바른 검증법**: (1) 서브라우트 목록은 `webapp.api.router.routes` 를 **직접** 순회한다(여기엔 `/api/patterns` 등이 정상 노출·endpoint 함수명·methods 확인 가능). (2) **시그니처 무결성(dependant 분석)** 은 `TestClient(app)` 를 생성하면 그 시점에 전 라우트를 build 하므로, `Request`+`Form(...)` 공존이 깨졌다면 **TestClient 생성 자체가 예외** → 생성 성공 = 시그니처 정상. 추가로 빈 POST 로 422(FormData 필수검증 도달) 를 확인하면 라우트 실동작까지 증명된다. `getattr(r,'path',None)` 로 방어하는 건 필수.
- **참조횟수**: 0

### [2026-06-29] 배포본 404 디버깅: 404 응답 본문이 "Cannot GET"이면 우리 앱이 아니다(Express=타인 앱·이름선점). 먼저 URL부터 의심
- **분류**: error
- **발견자**: pm
- **내용**: Render 배포 검증 중 `grader-v2.onrender.com`이 루트 `/`·`/static/screens/login.html`·`/api/public-config` 전부 **404**, 그런데 `/api/health`만 200이라 "최신 코드 미반영"으로 오인하기 쉬웠다. **결정적 단서**: 404 응답 본문이 `Cannot GET /api/public-config` + `<title>Error</title>` HTML이었는데, 이건 **Express(Node.js)** 의 기본 404 문구다. 우리 앱은 **FastAPI(Python)** 이라 없는 경로엔 `{"detail":"Not Found"}` JSON을 준다. 즉 그 도메인에 떠 있는 건 **우리 앱이 아니라 이름(`grader-v2`)을 선점한 타인의 Express 앱**이었다. Render는 서비스명이 겹치면 `grader-v2-<해시>.onrender.com` 으로 실제 URL을 만든다. **여파**: 그 전 세션의 "배포본 루트/login 404" 증상으로 introspection 마이그레이션까지 했는데, 실제로는 **코드가 멀쩡한데 엉뚱한 URL을 보고 있었을** 가능성이 크다(GitHub 미푸시0, 코드 정상). **예방규칙**: 배포본이 404·이상동작이면 코드를 의심하기 전에 **(1) 응답 본문의 서버 시그니처 확인**(`Cannot GET`=Express, `{"detail":...}`=FastAPI, nginx/cloudflare 페이지 등) — 프레임워크가 우리 것과 다르면 그 URL은 우리 앱이 아니다. **(2) 실제 배포 URL을 대시보드에서 확인**(이름 선점 시 해시 suffix). **(3) 서비스 존재 여부**(없으면 배포 연결 자체가 안 된 것). health 200 하나로 "우리 서버 살아있음"이라 단정 금지(타인 앱도 /health를 가질 수 있다).
- **참조횟수**: 0

### [2026-06-26] 프런트 인증 게이트: 루트가 앱 화면으로 직행하면 미인증자도 화면이 뜬다 — 루트는 login으로, 서빙 404는 StaticFiles 마운트부터
- **분류**: error
- **발견자**: developer
- **내용**: 배포본에서 ①루트 `/` 404("Cannot GET /") ②`/static/screens/login.html` 404 ③로그인 안 했는데 work 화면이 떠서 첫 `/api/patterns`만 401로 막힘 — "프런트 로그인 흐름 통째 누락" 증상. **근본원인**: 서버는 토큰을 못 본다(sessionStorage·Authorization 헤더는 fetch에만 붙음). 그래서 루트 `/`가 곧장 work 화면으로 RedirectResponse하면 **미인증자에게도 work가 뜨고**, 화면이 첫 API를 호출해 401을 받아야만 비로소 튕긴다(나쁜 UX·게이트 우회처럼 보임). **해결**: 루트 `/`는 **login.html로 리다이렉트**하고, login.html이 (a)로컬 무인증이면 즉시 work (b)유효 세션 있으면 getSession()으로 work 직행 (c)없으면 로그인 폼을 보이게 한다. 그리고 공통 fetch 래퍼(apiFetch)는 **401 시 sessionStorage 토큰 clear 후** login 리다이렉트(만료 토큰 잔류 방지). **예방규칙**: SPA식 인증 게이트는 "서버 라우트 분기(토큰 모름)"가 아니라 "루트→login 진입 + 클라이언트 세션 판정 + apiFetch 401 가드(토큰 clear 포함)" 3종을 모두 둔다. login.html 자체가 404면 코드 문제가 아니라 StaticFiles 마운트 경로/파일 실재/`_handoff→static` 복사 누락부터 확인(라우트 우선순위도). 인증코드(apiFetch)가 webapp/static에만 있고 _handoff 원본엔 없는 **비대칭**이면 _handoff 재복사 시 통째 소실되니 주의.
- **참조횟수**: 0

### [2026-06-25] PDF 클립 `W n`은 현재 경로를 소비한다 — 클립영역을 fill하려면 폴리곤을 다시 그려야
- **분류**: error
- **발견자**: developer / reviewer
- **내용**: 조각 클립은 `폴리곤(m/l…h) → W n`으로 구성되는데, **`W n`(또는 `W`+path-painting no-op `n`)은 클립 경로로 등록하면서 현재 경로를 비운다**(consume). 그래서 클립영역 안을 본체색으로 채우려고 `W n` 직후 곧바로 `k`(색)+`f`(fill)를 쓰면 **그릴 경로가 없어 아무것도 안 칠해진다**(흰틈 잔존). 반드시 fill용 폴리곤을 `m l…h`로 **다시 그린 뒤 `f`** 해야 한다(clip_path_ops 문자열 재사용 금지 — 그건 `W n`으로 끝남). 올바른 순서: `q / 폴리곤 W n(클립) / k / 폴리곤 재경로 h f(채움) / cm / Do(디자인) / Q`. 단 fill용·clip용 폴리곤은 **동일 좌표(piece.outline=시트좌표)** 여야 어긋남이 없다. 검증: fill이 클립영역 안·Do 앞에 위치 → 디자인 있는 곳은 디자인이 덮고 투명(빈)곳만 본체색. device k(4채널)+f라 투명도0·CMYK·벡터 유지(verify PASS), fill은 Do가 아니라 배치횟수 검증 영향 0.
- **참조횟수**: 0

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

### [2026-06-16] STIZ 주문서 xlsx는 다중 접수분 시트 누적 — "행 최다 시트 채택"은 과거 주문을 잘못 고른다
- **분류**: error
- **발견자**: tester
- **내용**: STIZ 표준 주문서 한 xlsx 파일에는 **여러 접수일 시트가 누적**돼 있다(시트명=날짜 6자리). 이번 주문은 **첫 시트**이며, 첫 시트 상단에 `주문번호: <폴더명과 일치>`와 `수량: 상의 NEA`(N=이번 주문 인원)가 명시된다. 나머지 시트는 같은 양식이지만 **과거의 다른 주문**(연습복/작년 접수분 등)이라 인원이 더 많을 수 있다. A-5 order.py가 시트를 고를 때 `len(parsed) > len(best)`(행 가장 많은 시트 채택) 폴백을 쓰는데, 이 때문에 **과거 대량 접수분 시트를 골라 이번 주문이 아닌 데이터를 반환**한다. 전수 86개 중 13개(15%)가 이 함정에 걸렸다(줄넘기 첫시트49→채택73, 중앙고 1→24, LG 8→16 등). **함정**: 검증을 '대표 5개'로만 하면 통과한다 — 우연히 그 5개는 첫 시트가 행 최다였기 때문. 정적 코드리뷰로도 안 보인다(실데이터 다종 표본 필요). **예방규칙**: 다중 시트 주문서는 (1)첫 시트 우선, 또는 (2)상단 `주문번호:`/`수량:상의 NEA`가 해당 건과 일치하는 시트 우선으로 채택하고, '행 최다'는 최후 폴백으로만 쓴다. 파서 검증 시 반드시 **시트가 2개 이상인 파일**을 표본에 포함하고, 첫시트 r1의 `상의 NEA` 수량과 결과 행수를 대조한다.
- **참조횟수**: 0

### [2026-06-20] preset "disabled" 사이즈 봉인은 한 경로(job)만 막고 다른 경로(grade)는 그대로 통과 — 삭제한 pattern_file을 읽다 크래시 [해결됨]
- **분류**: error
- **발견자**: tester
- **해결(2026-06-20 developer)**: sizes 내부 `"disabled": true` 표식은 build_layouts가 인지 못해 실패했다. **결함 사이즈를 sizes에서 아예 빼고 preset 최상위 `disabled_sizes` 섹션으로 이동**하는 방식으로 일원화해 해결. build_layouts/grade는 `preset["sizes"]`만 순회하므로 3XL이 sizes에 없으면 3XL.svg를 읽지 않아 크래시가 사라진다(grade.py 무수정). job은 `preset.disabled_sizes`(=`{이름→사유}`)에서 disabled_map을 읽어 결함 사이즈 주문을 명확 사유로 skip(5XL 대체 0). 검증: V넥 grade 배치 36회(12사이즈×3조각) PASS·FileNotFoundError 없음, job 3XL 2건 skip·5XL 오출고 0·verify 5/5, U넥(disabled_sizes 키 없음) 회귀 0, 단조성 가드 정상 12개 통과/결함 검출. **남는 교훈**: 사이즈/조각을 "비활성"하는 표식을 도입할 때, **표식을 모르는 경로가 있으면 표식이 아니라 데이터 자체를 그 경로의 순회 대상에서 빼는 것**(섹션 분리)이 더 견고하다. 한 경로만 검증하고 "안전"이라 결론내지 말 것 — disabled/skip 로직은 경로별로 독립이다.
- **참조횟수**: 1

### [2026-06-22] 실제 OS 파일 드롭 실패 — 드롭존 요소에만 리스너를 달면 자식 span/패딩 드롭이 브라우저 기본동작(새 탭)으로 샌다. playwright 합성 drop 은 이 함정을 못 잡는다 [해결됨]
- **분류**: error
- **발견자**: debugger
- **내용**: work.html 드롭존이 `<button class="dropzone">` + 자식 `<span>`(아이콘/제목/힌트) 구조인데, `wireDropzone`이 그 **button 요소에만** dragenter/dragover/dragleave/drop 리스너를 달았다. 실제 마우스로 파일을 끌어 놓으면 커서가 박스 정중앙이 아니라 **자식 span(글씨) 위·패딩·여백**에 떨어지기 쉽다. span 위 drop 이벤트는 button 핸들러로 안 잡히고 **document 까지 버블링**되는데, document/window 레벨에 dragover/drop `preventDefault` 가드가 없으면 브라우저 **기본동작(파일을 새 탭에서 열기/무시)** 으로 빠져 "끌어다 놔도 아무 반응 없음(첨부 안 됨)"이 된다. 클릭 업로드는 별개 경로라 정상. **결정적 함정**: playwright `dispatchEvent`/합성 drop 은 핸들러가 달린 요소에 이벤트를 **직접** 쏘므로(좌표 빗나감·버블링 함정이 없음) 항상 PASS 한다 → **합성이벤트 PASS 만으로 실제 OS 드롭이 된다고 결론내면 안 된다.** 부차로 StaticFiles 는 etag/last-modified 캐시를 줘서 수정한 work.html 이 옛 버전(드롭 핸들러 없는)으로 떠 있을 수 있다.
- **해결(2026-06-22)**: (1) 요소별 리스너를 버리고 **document 레벨 단일 dragover/dragleave/drop 가드**로 전환. dragover 에서 `preventDefault`(이게 있어야 drop 이벤트가 발생) + `dropEffect="copy"`. drop 에서도 `preventDefault` 로 어디에 떨어뜨려도 새 탭 열기를 원천 차단. (2) 드롭 좌표(clientX/clientY)를 각 드롭존의 `getBoundingClientRect()` 박스와 비교해 **영역 판정**으로 라우팅 → 자식 span·패딩 어디에 떨어져도 디자인→uploadDesign(/api/design/check)·주문→uploadOrder(/api/order/parse)로 클릭과 동일 경로로 흐른다. `wireDropzone`은 시그니처 유지하되 id→onFile 등록만 담당(렌더 재생성마다 최신 콜백 갱신). (3) work.html `<head>`에 `Cache-Control: no-cache, no-store, must-revalidate` + Pragma + Expires meta 추가(옛 버전 캐시 방지, 강력새로고침 불필요). **검증**: CDP/좌표 기반 drop 으로 **자식 span 좌표(SPAN.dropzone__title)에 직접** 드롭 → 디자인 /api/design/check 호출+filecard, 주문 /api/order/parse 호출+12행. 드롭존 밖(5,5) 드롭 → URL 변경 0·탭 1개(새 탭 안 열림). 클릭 업로드 회귀 0.
- **예방규칙**: 브라우저 파일 드롭은 (1) **반드시 document/window 레벨에 dragover+drop preventDefault 가드**를 깔고(요소 리스너만으론 자식/패딩 드롭이 샌다), (2) 드롭존 판정은 요소 타겟이 아니라 **좌표 vs getBoundingClientRect**로 하며, (3) 검증은 합성 dispatchEvent 가 아니라 **드롭존 자식 요소 좌표·드롭존 밖 좌표**에 실제 드롭을 흘려 새 탭 미발생·API 호출을 함께 확인한다. 정적 화면 수정이 안 먹는 것 같으면 캐시(etag/304)부터 의심하고 no-cache 헤더/meta 를 확인한다.
- **참조횟수**: 0

### [2026-06-19] 패턴 SVG 변환은 "조각수=2 + verify PASS"만으로 정상이 아니다 — viewBox/좌표계가 사이즈별로 섞이면 그레이딩이 깨진다
- **분류**: error
- **발견자**: tester
- **내용**: V넥 13개 패턴 SVG 중 **XL만 viewBox 가로(4478x3401)·양수 좌표**이고, 나머지 12개(5XS~L, 2XL~5XL)는 **viewBox 세로(4478x5669) + 조각 x좌표가 음수**(예 M 앞판 x[-1341..313])다. 원본 .ai 13개를 PyMuPDF로 변환하면 **전부 viewBox 가로(3401)·양수**가 나오는데(변환기 svg_normalize.py 자체는 정확 — d파서 M/H/L/V 전개·matrix 적용 수동검산 일치, XL은 .ai 변환과 커밋본이 완전 일치), 커밋된 12개는 **XL과 다른 출처 SVG**(위·아래 2벌 중복된 세로 5669본)에서 변환돼 좌표계가 어긋났다. **함정**: (1)parse_svg 조각수는 13개 모두 정상 2개로 나온다(중복제거가 잘 돼서). (2)svg_index 앞=0/뒤=1 일관성도 13개 전수 OK로 나온다. (3)verify_output도 PASS한다(verify는 "디자인 Form 무손실 임베드"만 보지 위치/캔버스 크기를 안 봄). (4)job도 produced/verify_pass가 정상 카운트된다. -> 이 4개 신호가 전부 초록불이어도 실제 출력은 깨진다. 음수좌표 조각을 contain 정합하느라 cm translate가 -1788pt까지 밀리고, 출력 페이지가 세로 길쭉(2811x5351)이 되며 앞판이 캔버스 밖으로 나가 소실(미리보기에 뒤판만 보임). XL(올바른 좌표)만 앞·뒤 정상. **유일하게 잡아낸 검증**: 사이즈별로 (a)변환본 viewBox가 동일한지 + 조각 x좌표가 viewBox[0..W] 안에 드는지(음수/초과 금지) 점검, (b)출력 PDF page rect가 사이즈 무관 동일 비율(가로)인지, (c)미리보기 PNG 육안(앞판 존재 여부). **예방규칙**: 패턴 변환 검증은 "조각수=2 + verify PASS"로 끝내지 말고 (1)13개 viewBox 전수 동일 (2)조각 bbox가 viewBox 안(min>=0, max<=W/H) (3)모든 사이즈 미리보기 육안(스모크를 XL 1개만 보면 통과해버림 — 깨진 건 비-XL 12개라서)을 필수로 한다. 변환 입력 원본의 출처(.ai 직변환본인지)를 사이즈마다 통일해야 한다.
- **참조횟수**: 0

### [2026-07-06] Drive 폴더 동시 펼침 시 `[SSL] record layer failure` — google-api-python-client의 httplib2는 스레드 비세이프인데 전역 service 를 FastAPI 스레드풀이 공유
- **분류**: error
- **발견자**: debugger
- **내용**: 배포본에서 [드라이브에서 등록] 루트 트리는 정상인데, 폴더 하위를 **동시에 여러 개** 펼치면 `Drive 접근 실패: Drive 폴더 목록 조회 실패: [SSL] record layer failure (_ssl.c:2590)`(502 DriveError). **근본원인**: `gdrive.py`가 `build()` 결과 Drive 클라이언트를 전역 `_SERVICE` 1개로 캐시했는데, 그 내부 HTTP 계층 `httplib2.Http`는 **스레드 세이프가 아니다**(TLS 소켓 1개를 여러 스레드가 동시에 write 하면 레코드가 섞여 SSL 계층이 깨짐). FastAPI 는 **sync 엔드포인트(def drive_tree 등)를 스레드풀에서 동시 실행**하므로, 트리 하위를 여러 개 동시에 펼치면 같은 전역 service(=같은 소켓)에 execute 가 겹쳐 충돌한다. 루트는 호출 1건이라 우연히 통과. `_SERVICE_LOCK`은 **service 생성만 보호**하고 실제 `.execute()`는 보호하지 않아 무력. **함정**: 로컬(단일 요청 수동 클릭)·모킹 테스트에선 동시성이 없어 안 보인다 — "동시 다중 펼침"이라는 실사용 동시성에서만 재현. **해결**: (1) 전역 공유를 없애고 `threading.local()`로 **스레드마다 자기 service(=자기 httplib2 연결)**를 캐시(스레드풀 스레드는 재사용→스레드당 build 1회). (2) 전송계층 일시 실패(`ssl.SSLError`·`OSError`/`socket.error`·`ConnectionError`·`BrokenPipeError`·`http.client.HTTPException`·httplib2 `ServerNotFoundError`/`HttpLib2Error`)면 그 스레드 연결을 폐기·재생성해 **새 연결로 1회 재시도**(총 2회). **⚠️ HttpError(googleapiclient) 403/404 는 재시도 금지**(권한/없음=일시적 아님) → 그대로 DriveError. (3) `get_service()`를 try 밖에서 선호출해 미설정 `DriveConfigError` 가 `DriveError` 로 안 감싸지게(api.py 분리처리 보존). **예방규칙**: 스레드/이벤트루프에서 병렬로 쓰는 SDK 클라이언트는 "스레드 세이프인지" 먼저 확인. httplib2 기반(google-api-python-client 기본) 은 **연결 공유 금지** → 스레드로컬 또는 요청마다 생성. 전역 캐시 + Lock 은 '생성'만 직렬화할 뿐 '동시 사용'은 못 막는다. 동시성 버그는 로컬 수동테스트로 안 잡히니, 재현 시 **동일 자원 동시호출**을 의심.
- **참조횟수**: 0

### [2026-07-07] jsdom 로 이스케이프 검증 시 element.innerHTML 를 되읽으면 텍스트 노드의 " ' 가 리터럴로 환원돼 오탐(FAIL) — raw 생성문자열/속성값으로 검증하라
- **분류**: error
- **발견자**: tester
- **내용**: 프론트 driveEsc(사용자 폴더명 이스케이프)를 검증하며, 요소에 `innerHTML=driveScanCardHtml(...)` 을 넣은 뒤 `grid.innerHTML` 를 되읽어 `&quot;`/`&#39;` 문자열을 찾았더니 **매칭 실패(FAIL)**. 실제 driveEsc 는 정상(`"`→`&quot;`, `'`→`&#39;`)인데도 오탐이다. **원인**: HTML **텍스트 노드**에서는 `"` 와 `'` 를 이스케이프하지 **않는다**(직렬화 시 `&`,`<`,`>`,nbsp 만 이스케이프). 그래서 소스 문자열의 `&quot;반팔&quot;` 은 DOM 파싱 때 텍스트 `"반팔"` 로 변하고, `innerHTML` 재직렬화 시 텍스트의 `"`/`'` 는 **리터럴 그대로** 나온다(`&amp;` 만 그대로 유지). 즉 innerHTML 왕복이 표현을 바꾼다. **함정**: 이 오탐을 실제 이스케이프 버그로 오인하면 안 된다(텍스트 위치의 `"`/`'` 는 보안상 무해하기도 함 — 각괄호만 태그 인젝션 위험이라 `<img>`→`&lt;img` 만 확인하면 텍스트 컨텍스트는 충분). **예방규칙**: 이스케이프 정확성은 (1) 헬퍼 반환 **raw 문자열**(`driveEsc('a&b<c>"e\'f')` === `a&amp;b&lt;c&gt;&quot;e&#39;f`)로 직접 단언, (2) **속성 컨텍스트**(예 `value="${driveEsc(x)}"`)는 XSS 관점으로 — 탈출 시도 문자열 주입 후 `querySelectorAll('[onload]').length===0` + `input.value` 리터럴 보존으로 검증한다. innerHTML 되읽기 매칭은 텍스트의 따옴표에 대해 신뢰하지 말 것.
- **참조횟수**: 0

### [2026-07-06] 배포 후 Drive/admin 기능 403 "관리자 권한 필요" — Supabase app_metadata.role 누락
- **분류**: error
- **발견자**: pm
- **내용**: 배포(GRADER_REQUIRE_AUTH=1) 환경에서 Drive 엔드포인트(tree/patternfiles/from-drive)·POST patterns·PUT settings가 403. 원인은 코드 버그가 아니라 **로그인 계정의 Supabase `app_metadata.role`이 "admin"이 아님**(auth.py admin_required가 role!="admin"→403, 로컬 무인증은 통과라 로컬에선 안 보이던 함정). 화면엔 "관리자(admin) 권한이 필요합니다"(정상 안내=인증 정상 작동 증거). **해결**: Supabase SQL Editor에서 `update auth.users set raw_app_meta_data = coalesce(raw_app_meta_data,'{}'::jsonb) || '{"role":"admin"}'::jsonb where email='...';` 후 **로그아웃→재로그인**(새 토큰+60초 캐시 회피). 확인: `select raw_app_meta_data->>'role'`. ⚠️ grader-v2 Supabase(begxkadzvcczdlewcmrj)는 Claude MCP 연결분(mybdr 계열)에 없어 대행 불가=사용자 직접. role은 app_metadata(raw_app_meta_data)에 넣어야 함(user_metadata 아님).
- **참조횟수**: 0

### [2026-07-07] jsdom 하니스로 이 앱 화면(patterns/work.html) 통째 로드 시 — auth_required=true인데 window.supabase(CDN) 부재면 기존 initAccount가 async 예외로 node 프로세스 크래시. process 'unhandledRejection' 가드 필수
- **분류**: error
- **발견자**: tester
- **내용**: `JSDOM(html, {runScripts:"dangerously"})` 로 patterns/work.html 을 실제 스크립트 실행으로 로드해 검증할 때, `/api/public-config` 스텁을 `{auth_required:true, supabase_url, supabase_publishable_key}` 로 주면서 **window.supabase(CDN `@supabase/supabase-js`)는 스텁 주입 안 하면**, 기존(diff 밖) `initAccount()` 가 `acctSupa = window.supabase.createClient(...)` 에서 `TypeError: Cannot read properties of undefined (reading 'createClient')` 를 던진다. initAccount 는 `async` 이고 `await` 없이 호출돼 **unhandled promise rejection** 이 되는데, jsdom 이 이를 Node process 로 re-throw 해 **테스트 러너가 그 자리에서 크래시**(그 하니스의 나머지 assert 미실행). 실브라우저에선 콘솔 경고로 끝나 페이지가 안 죽지만, jsdom+Node 조합에서만 프로세스가 죽는 함정. **주의**: 이건 검증 대상 기능(즐겨찾기/자동분류)의 결함이 아니라 **하니스 아티팩트 + 기존 initAccount 의 병리조합**(auth 필요한데 CDN 미로딩=login/계정메뉴도 불가한 상태)일 뿐. 신규 pm 코드(pmGetSb)는 `!window.supabase` 가드로 정상 degrade 함. **예방규칙**: (1) 이 앱 화면을 jsdom runScripts 로 로드하는 하니스는 반드시 `process.on("unhandledRejection", …)` 를 걸어 기존 async 코드(initAccount 등)의 예외로 러너가 죽지 않게 하고 그 rejection 을 **별도 배열에 기록**(jsdomError 와 분리). (2) auth 경로를 테스트하려면 `beforeParse` 에서 `window.supabase = {createClient(){…}}` 스텁을 반드시 주입한다(CDN 은 resources 미로딩이라 실제로 안 받아짐). (3) 크래시가 나면 먼저 "그게 검증 대상 코드인지 기존 코드인지" 스택트레이스로 구분 — 여기선 patterns.html initAccount(라인 ~1339) 로 즉시 판별됨.
- **참조횟수**: 0

### [2026-07-07] 번호·이름 area 에 piece_id 가 없으면 엔진이 '조용히' 건너뛴다(에러 0) — 경고 로그+preview 육안까지 봐야 잡힌다
- **분류**: error
- **발견자**: tester
- **내용**: 엔진 job._inject 는 `area.piece_id` → `_find_piece_index(pieces, piece_id)` 로 조각을 찾아 그 위에 번호·이름을 얹는다. piece_id 가 **없거나(None)** pieces 에 없는 값이면 `pidx is None` → `🟡 …piece_id='None' 를 조각 목록에서 찾지 못해 '7' 를 그리지 않습니다` **경고만 남기고 return**(크래시·에러 0, run_job 정상 종료·output PDF 도 생성됨). 완성본 자동추출 `reference.build_area_preset` 이 만든 area 3종(front/back number, back name)에는 **piece_id 키가 아예 없어서**(center/cap_height/color_cmyk/font 만) 이 구멍에 걸린다 → 스캔/드라이브/로컬 등록 패턴이 주문 시 번호·이름이 몸판만 나오고 **조용히 누락**. **함정**: (1) run_job status·output 파일 존재만 보면 PASS 로 보인다(번호 유무는 안 봄). (2) preset 에 area 키는 있으니 has_number_area 플래그도 True. (3) 정상 preset(수작업 piece_id 있음)만 스모크하면 안 걸린다. **유일하게 잡는 검증법**: ① build_area_preset 반환 area 에 `'piece_id' in a` 가 False 인지(구멍 원상태 확인) ② 등록 후 preset area piece_id 가 `_find_piece_index` 로 실제 조각을 찾는지(front→idx0 앞판·back번호/이름→idx1 뒤판) ③ **run_job 실제 실행 → 경고 로그 '그리지 않습니다' 유무 + preview PNG 에 번호·이름 실제 렌더 육안**. 수정 전(piece_id 제거)=경고 N건·preview 번호없음, 수정 후=경고0·preview 번호/이름 출력으로 **대조**해야 결정적. **예방규칙**: area 를 새로 조립·자동추출하는 경로를 추가하면 반드시 piece_id 를 `pieces`(실제 조각 목록)의 id 로 채운다(하드코딩 문자열 말고). '경고=미출력'인 silent-skip 은 경고 로그를 실패로 승격하거나 preview 육안을 검증에 넣지 않으면 통과처럼 보인다.
- **참조횟수**: 0
