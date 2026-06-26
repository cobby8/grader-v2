# 작업 스크래치패드

## 현재 작업
- **요청**: 배포본 계정 기능 — "비밀번호 변경"(supabase updateUser, 세션기준·SMTP불필요) + "로그아웃"(signOut). 4화면 topbar 공통 계정 메뉴. 빌드0.
- **상태**: ✅ **완료·커밋대기**. tester8/8 합격·reviewer 통과 치명0. 백엔드/엔진 무변경(4화면만). **푸시 예정**(완료기준④ push→Render 자동재배포).
- **현재 담당**: pm

## 진행 현황 (완료 — 상세는 git 히스토리 + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 합성1·2·3 | 자동매핑·cover+블리드·재단선1줄·패턴선 OCG제거 | ✅ tester12/12·rev통과 |
| 배번 글리프셋 | 자간(advance 0.6611)+"1" lsb 보정 | ✅ selftest·verify4/4 |
| 합성 A+B | 본체색 채움(Piece.bg_cmyk)+사이즈별 자동블리드 | ✅ tester6/6·rev통과 |
| 배포 Phase1(JWT) | Docker+Render+JWT 게이트 | ✅ ef33874(introspection으로 대체) |
| 배포 Phase1 갱신 | introspection 인증+admin게이트+프런트 로그인흐름(루트/login 404 수정) | ✅ tester36/36·rev치명0·푸시 d0c4284 |
| **계정 기능** | 4화면 계정메뉴(이메일+드롭다운)·비번변경 모달(updateUser)·로그아웃(signOut) | ✅ tester8/8·rev통과 치명0 |

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
