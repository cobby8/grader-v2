# 작업 스크래치패드

## 현재 작업
- **요청**: 4화면(work/patterns/history/settings) 상단 도움말(help_outline) 버튼 동작 — 클릭 시 사용안내 모달(.pwmodal 패턴 재사용, 제목"사용 안내", 닫기·배경클릭, 스크롤). 본문=직원용 한국어(비번변경·5단계·로그아웃·FAQ, 직원사용안내.md 골자). 빌드0·백엔드/엔진/인증 무영향.
- **상태**: ✅ **완료·커밋대기**. tester 84/84 PASS(jsdom 실증). 백엔드/엔진 무변경(4화면만). **푸시 예정**.
- **현재 담당**: pm

## 진행 현황 (완료 — 상세는 git 히스토리 + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 합성1·2·3 | 자동매핑·cover+블리드·재단선1줄·패턴선 OCG제거 | ✅ tester12/12·rev통과 |
| 배번 글리프셋 | 자간(advance 0.6611)+"1" lsb 보정 | ✅ selftest·verify4/4 |
| 합성 A+B | 본체색 채움(Piece.bg_cmyk)+사이즈별 자동블리드 | ✅ tester6/6·rev통과 |
| 배포 Phase1(JWT) | Docker+Render+JWT 게이트 | ✅ ef33874(introspection으로 대체) |
| 배포 Phase1 갱신 | introspection 인증+admin게이트+프런트 로그인흐름(루트/login 404 수정) | ✅ tester36/36·rev치명0·푸시 d0c4284 |
| 계정 기능 | 4화면 계정메뉴(이메일+드롭다운)·비번변경 모달(updateUser)·로그아웃(signOut) | ✅ tester8/8·rev통과 치명0 |
| **도움말 모달** | 4화면 ? 버튼→사용안내 모달(.pwmodal 재사용·스크롤·닫기3종, 직원안내 본문) | ✅ tester84/84 PASS |

## 백로그 (차단 아님, 후속)
- **[계정 후속]** 비번변경 '변경'버튼 더블클릭 disabled 방어(현재 멱등이라 무손상·UX만). toast 지속시간 화면별 미세차(work 4초/settings 3.2초) 통일.
- **[_handoff 비대칭 확대]** apiFetch·인증·**계정/비번변경/로그아웃 JS** 전부 webapp/static에만 → _handoff 재복사 시 통째 소실 위험(conventions.md). login.html만 원본↔복사 동일.
- **[인증 후속]** auth.py 토큰캐시 만료정리(조회시에만 만료→미사용 토큰 잔류, 위험낮음). login.html getSession 핑퐁(발생률 극저).
- **[배포 Phase 2~3]** Storage(업로드/산출물 영속) + Postgres/RLS. 현 Phase1은 Render 임시디스크(재배포시 소실).
- **[U넥 자산]** design_XL.ai .gitignore 자산 로컬부재 → 합성 A+B full job 시각회귀 미실시. **[합성 일반화]** hide_design_cutline_layer V넥 한정. **[웹앱]** 업로드 검증+TTL 정리. **[디자이너 대기]** 재단선 .ai 재출력/3XL.ai 재확보. **[job.py:732]** _auto_bleed svg_index 가드(비치명).

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만, 단 fetch/인증/계정 JS는 static에만=비대칭). 커밋 전 ast.parse/py_compile. **--workers 1 유지**(_JOBS·인증캐시 일관). 비밀키(SECRET) 레포·프런트 금지.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→cover(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, cover_bleed preset 키 있을때만(없으면 contain=U넥 회귀0).
- **사이즈별 자동 블리드**: cover_bleed가 `{auto:true,k:1.3,min:1.0,max:1.12}` dict면 앞판 기준 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1+k·dev,lo,hi)` 단일값→전 조각 등방. float=기존 단일·None=contain. XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036.
- **본체색 채움(흰틈)**: Piece.bg_cmyk(기본None) 있으면 place_block이 클립(W n)직후·Do앞 폴리곤 **재경로** 후 device k+f 채움(⚠️W n이 경로소비→재경로 필수). run_job 본체색 1회: preset.body_fill([0.8,0.5,0,0.1]) > detect_background_cmyk > None.
- **재단선**: 조각 SVG poly.points를 시트좌표 그대로 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). draw_from="svg_polygon".
- **디자인 패턴선 두 줄 방지**: OCG OFF는 Form 합성에 무효 → 콘텐츠 BDC…EMC 삭제(빨강1색만·5색 무손실). hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=design_region. SVG 넥깊이로 앞(svg1)/뒤(svg0)/밴드(svg2).
- 글자주입: place_*(잉크bbox 중앙정렬)→조각 transform 감싸 extra_ops(클립밖, Do뒤). 번호: glyph_source 있으면 글리프셋(advance0.6611·글자별lsb), 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체 포함(아니면 3.4KB 흰화면). 정상 빈본체=88KB.
- **출력형식**: flatten Form투명도그룹 제거·페이지그룹 /CS 보존. eps2write. EPS 305KB 벡터.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2. 12사이즈(3XL disabled, disabled_sizes는 sizes 밖).
- **배포/GS/포트**: GS경로=eps.find_ghostscript 맨앞 GS_BIN env 우선(없으면 settings_path→Windows절대→PATH 폴백). state.DEFAULT_PORT=int(PORT env,8000). Dockerfile CMD shell form `${PORT:-8000}`(Render $PORT 호환). --workers 1.
- **인증(introspection)**: webapp/auth.py require_auth — **GRADER_REQUIRE_AUTH 토글**(로컬 미설정=무인증 통과·배포=1=검증). ON이면 `httpx.get({SUPABASE_URL}/auth/v1/user, apikey=PUBLISHABLE, Bearer, timeout=5)` → 200이면 id·email·app_metadata.role을 request.state, 비200/예외=401. **토큰별 60초 캐시**(_TOKEN_CACHE+Lock). **admin_required**(role!=admin→403, 토글OFF통과)를 POST /api/patterns·PUT /api/settings에만. **/api/health·/api/public-config 무인증**(public_router, health 막으면 Render 부팅실패). **/api/public-config**={supabase_url,supabase_publishable_key}만(SECRET 금지). 프런트 apiFetch: Bearer 부착·401시 sessionStorage(grader_access_token) clear+login. **루트 / → login.html**(미인증 우회 차단). SECRET·SERVICE_ROLE·JWT_SECRET·pyjwt 전부 제거.
- **계정 기능(프런트)**: 4화면(work/patterns/history/settings) topbar 계정메뉴 = 이메일표시(getUser→getSession)+드롭다운[비번변경/로그아웃]. supabase 클라(login.html 패턴: public-config→createClient, **publishable만**). 비번변경=모달(새비번+확인, 6자/일치 한국어가드 후 `updateUser({password})`, 세션유지). 로그아웃=`signOut()`+removeItem(TOKEN_KEY)+login. auth_required=false(로컬)면 계정메뉴 숨김.
- ⚠️ 함정(errors.md): 변환 viewBox통일·미리보기육안. 인접사이즈 좌표동일=자산결함. 브라우저 드롭 document가드+좌표. W n 경로소비→fill 재경로. 프런트 인증게이트=루트→login+클라세션판정+apiFetch401가드.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job(cover/auto_bleed+본체색채움+재단선polygon+OCG제거+disabled+out_format)·svg_normalize·order·flatten(+detect_background_cmyk)·eps(+GS_BIN env)·compose(+Piece.bg_cmyk)·pdfutil(place_block+bg_cmyk)·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main(루트→login·라우터분리)·auth(introspection+admin_required+60초캐시)·api(health·public-config 무인증 + patterns·settings[admin]·order·design·jobs·preview·zip·기록·등록)·state(PORT env)·run.py·run.bat. static 4화면=apiFetch+계정메뉴(static에만, 비대칭). login.html(supabase-js).
- 배포: Dockerfile(${PORT})·render.yaml(env URL·PUBLISHABLE·SECRET·GS_BIN·GRADER_REQUIRE_AUTH)·.dockerignore·.env.example. 데이터: data/patterns/{농구_U넥_양면,농구_V넥_양면}. data/{jobs,uploads}/·settings.json(.gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋·_완성본. 주문서: Desktop/새 폴더/260213_…xlsx. 폰트 HY헤드라인M.ttf. 로컬 GS gswin64c.
- 테스트 산출물 `_abtest/`·`_glyphtest/`는 .gitignore. 로컬 .env(키 PUBLISHABLE/SECRET, git/docker 제외=안전·코드 정합). node_modules .gitignore 미등록(추후).
- git: origin=cobby8/grader-v2, main. 의뢰서/사용설명서 .md 미추적(커밋 제외).

## 구현/테스트/리뷰/기획설계
(완료분 상세는 git+knowledge. 계정기능: tester8/8 합격·reviewer 통과 치명0, SECRET 누출0·백엔드 무변경)

### 테스트 결과 (tester) — 도움말 사용안내 모달 [2026-06-26, jsdom 실증]

검증 방식: jsdom(--no-save 임시설치, 검증후 제거·git 무영향)으로 4화면 인라인 스크립트를 실제 실행 → 버튼클릭/닫기3종/패널내부무반응/회귀를 DOM으로 실증. 정적 diff로 4화면 일관성·범위·SECRET 병행.

| # | 검증 항목 | 결과 | 근거 |
|---|----------|------|------|
| 1 | 도움말 버튼→모달 표시(4화면 일관) | ✅ PASS | helpBtn 클릭 시 #helpModal hidden 해제(4화면 실행). id 카운트 4화면 균등(helpModal/helpBtn/helpClose/helpTitle 각 1). 마크업·JS·CSS 4화면 diff 동일(유일 차=initAccount 주석문구, 무관) |
| 2 | 본문 4섹션 존재·한국어 | ✅ PASS | h3 4개=①비번변경(6자)②5단계(패턴→디자인[빈본체·PDF호환·자동점검]→주문서xlsx→생성→검수ZIP)③로그아웃(공용PC)④FAQ. 핵심 키워드(비번변경·6자·주문서·검수·ZIP·로그아웃·공용PC·30초·PDF호환·빈본체·admin) 전수 포함, 누락0. 한글 포함 |
| 3 | 닫기 3종(버튼·배경·ESC), 패널내부 무반응 | ✅ PASS | 닫기버튼/오버레이자기자신클릭/ESC 모두 닫힘 실증. 패널(.helpmodal__panel)·깊은자식(h3) 클릭은 유지(e.target===helpModal 가드). 재오픈 OK |
| 4 | 스크롤(70vh+overflow) | ✅ PASS | .helpmodal__body{max-height:70vh;overflow-y:auto} 규칙 존재(정규식 매치). 본문에 클래스 적용됨 |
| 5 | 회귀(비번모달·계정메뉴·ESC 공존) | ✅ PASS | 계정메뉴 토글·비번변경 모달 열기/취소/배경닫기 정상. ESC 핸들러 3개(계정메뉴·검수lightbox·도움말) 공존, 각자 own 가드(lightbox=hidden시 return, help=!hidden시만). help 열린 채 ESC→help만 닫히고 pw모달 상태 불변. 닫힌상태 ESC 무해 |
| 6 | 불변/무영향·SECRET·빌드0 | ✅ PASS | git diff=webapp/static 4화면+scratchpad만. engine·api.py·auth.py·main.py·_handoff 무변경. SECRET 노출0(유일매치="SECRET 미사용" 주석). 빌드0 |
| 7 | HTML 유효성(태그균형·중복선언·런타임에러) | ✅ PASS | 4화면 div·script 균형. helpModal/helpBtn const·openHelpModal/closeHelpModal 각 1(중복0→jsdom 로드성공이 SyntaxError 부재 실증). jsdom virtualConsole 런타임에러 0건×4 |

📊 종합: **84개 어서션 중 84 PASS / 0 FAIL** (4화면×21) + 정적 7항목 전부 PASS. **합격**.
- 참고(비차단): 계정메뉴 ESC 핸들러(work.html:1406 등)는 own 가드 없이 항상 closeAcctMenu() 호출하나, add("hidden") 멱등이라 도움말/pw모달 무영향(기존 코드, 이번 변경 아님). 수정요청 아님.

### 구현 기록 (developer)

📝 구현한 기능: 4화면 상단 도움말(?) 버튼 → 사용 안내 모달(.pwmodal 패턴 재사용)

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| webapp/static/screens/work.html | 도움말 버튼 id=helpBtn·#helpModal 마크업·.helpmodal CSS·열기/닫기/배경/ESC JS | 수정 |
| webapp/static/screens/history.html | 동일(4화면 복붙 일관) | 수정 |
| webapp/static/screens/patterns.html | 동일 | 수정 |
| webapp/static/screens/settings.html | 동일 | 수정 |

구현 방식(4화면 100% 동일):
- **도움말 버튼**: 기존 `<button class="icon-btn" aria-label="도움말">`(핸들러 없었음)에 `id="helpBtn"` 부여 → 클릭 시 모달 열림.
- **.pwmodal 재사용**: 오버레이/패널/타이틀/actions 클래스는 비번모달 것 그대로. 추가 CSS는 최소(`.helpmodal__panel` max-width 560px + `.helpmodal__body` max-height:70vh+overflow-y:auto 스크롤 + h3/ol/ul/li/p 타이포만). 색은 모두 CSS 변수.
- **닫기 3종**: 닫기 버튼(#helpClose) + 배경(오버레이=#helpModal 자기자신) 클릭 + ESC(열려있을 때만). 비번모달과 동일 패턴.
- **본문(직원사용안내.md 골자 반영함)**: ①첫 로그인 후 비번변경(우측상단 이메일→비번변경, 6자) ②5단계(패턴→디자인[빈본체·PDF호환·자동점검]→주문서xlsx→생성→검수ZIP) ③로그아웃(공용PC 주의) ④FAQ(첫화면30초·로그인필요 재로그인·본체누락 PDF호환체크+빈본체·패턴등록 admin·비번분실 관리자재발급). 섹션 h3+ol/ul로 가독성. 임시비번 문자열은 노출하지 않고 "관리자에게 받은 임시 비밀번호"로 일반화.
- **위치**: 모달 마크업은 비번모달 옆(.toaster 앞), JS는 initAccount() 직전 삽입. 변수(helpModal/helpBtn) 중복선언 없음(각 1회), id 4종 4화면 각 1개씩(grep 12카운트 동일).

💡 tester 참고:
- 테스트 방법: 4화면(work/patterns/history/settings) 각각 상단 우측 **? 아이콘(도움말) 클릭** → "사용 안내" 모달 표시.
- 정상 동작: 모달 뜸 / 본문에 4개 섹션(비번변경·5단계·로그아웃·FAQ) 존재 / 본문 길면 내부 스크롤(70vh) / **닫기버튼·배경클릭·ESC** 모두 닫힘.
- 회귀 확인: 기존 **비밀번호 변경 모달**(계정메뉴→비번변경) 정상 동작(ESC 핸들러 2개 공존해도 서로 무간섭) / 계정메뉴 토글 정상.
- 주의 입력: 좁은 화면(모바일)에서 모달 스크롤로 끝까지 읽히는지 / 배경 클릭 시 패널 내부 클릭은 안 닫혀야(오버레이 자기자신만 닫힘).

⚠️ reviewer 참고:
- ESC keydown 리스너를 화면당 3개(계정메뉴·검수모달[work]·도움말) 등록 — 각자 own 가드라 충돌 없음. 도움말은 `!hidden`일 때만 닫음.
- 백엔드/엔진/auth/main 무수정. _handoff 무수정(비대칭 규칙 준수, static 4화면만). SECRET 무관(안내 텍스트뿐).

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성·재확보 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-25 | dev/test/rev/pm | 합성 A+B 구현·검증·커밋 | tester6/6·푸시 6d5dd9c |
| 2026-06-25 | 팀 | 배포 Phase1(JWT) | tester24/24·ef33874·푸시 |
| 2026-06-25 | planner | 배포 갱신본 introspection 설계 | auth전면교체·admin게이트·$PORT 권고 |
| 2026-06-26 | dev | introspection+프런트 로그인흐름 통합구현 | 404 근본원인(루트 work직행) 수정·pyjwt제거 |
| 2026-06-26 | tester | 갱신본 검증(httpx 모킹) | 36/36 합격·캐시·admin403·SECRET0 |
| 2026-06-26 | reviewer | 갱신본 리뷰 | 통과 치명0·timeout5·캐시Lock |
| 2026-06-26 | dev | 되돌림2: apiFetch 401 sessionStorage clear | 4화면 removeItem |
| 2026-06-26 | pm | introspection 갱신 커밋+회고+푸시 | d0c4284·미푸시0 |
| 2026-06-26 | dev | 계정기능(비번변경+로그아웃) 4화면 | updateUser·signOut·public-config·publishable만. 백엔드 무변경 |
| 2026-06-26 | test/rev/pm | 계정기능 검증·커밋 | tester8/8·rev치명0·SECRET0·jsdom DOM실증 |
| 2026-06-26 | dev | 4화면 도움말? →사용안내 모달(.pwmodal 재사용) | helpBtn·helpModal·닫기3종(버튼/배경/ESC)·본문4섹션(직원안내.md골자)·static만·_handoff무수정 |
| 2026-06-26 | tester | 도움말 모달 검증(jsdom 실증, reviewer없이 단독) | 84/84 PASS·정적7항목 PASS·4화면diff동일·범위/SECRET0/회귀OK·합격 |
