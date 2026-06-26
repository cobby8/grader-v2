# 작업 스크래치패드

## 현재 작업
- **요청**: 배포 Phase 1 갱신본 — 인증 JWT secret → **토큰 introspection** 교체 + 배포본 프런트 로그인 흐름 버그수정(루트/login 404·미인증 우회).
- **상태**: ✅ **완료·커밋대기**(introspection+로그인흐름). tester36/36 합격·reviewer 통과 치명0·되돌림2(PORT·sessionStorage clear) 해결. **푸시 예정**(완료기준에 push 명시).
- **현재 담당**: pm
- **⚠️ 배포 액션(수빈)**: Render env를 **정확한 이름**으로: SUPABASE_URL·SUPABASE_PUBLISHABLE_KEY·SUPABASE_SECRET_KEY (로컬 .env 이름과 정합). Supabase 이메일 로그인+직원계정(admin은 app_metadata.role=admin). 재배포 후 루트→login→로그인→work→5단계 확인.

## 진행 현황 (완료 — 상세는 git 히스토리 + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 웹앱1~5 | FastAPI 풀스택(order/design/jobs비동기/기록/등록/설정)+run.bat | ✅ rev종합 치명0 |
| 화면버그+실OS드롭 | both/EPS·드래그앤드롭·헤더·3XL칩·푸터 / document가드+좌표 | ✅ tester9/9·debugger |
| 합성1·2·3 | 자동매핑·cover+블리드·재단선1줄(svg_polygon)·패턴선 OCG제거 | ✅ tester12/12·rev통과 |
| 배번 글리프셋 | 자간(advance 0.6611)+"1" lsb 보정 | ✅ selftest PASS·verify4/4 |
| 합성 A+B | 본체색 채움(Piece.bg_cmyk)+사이즈별 자동블리드(auto_bleed) | ✅ tester6/6·rev통과 |
| 배포 Phase1(JWT) | Docker+Render+JWT 인증 게이트 | ✅ tester24/24 (ef33874, introspection으로 대체됨) |
| **배포 Phase1 갱신** | introspection 인증+admin게이트+프런트 로그인흐름(루트/login 404 수정) | ✅ tester36/36·rev통과 치명0 |

## 백로그 (차단 아님, 후속)
- **[인증 후속]** auth.py 토큰캐시 만료정리(조회시에만 만료→미사용 토큰 잔류, 이론적 증식; --workers1·60초TTL·사내소규모라 위험낮음). login.html getSession 핑퐁(refresh 살아있는데 introspection 일시401 시 work↔login 짧은반복, 발생률 극저).
- **[배포 Phase 2~3]** Storage(업로드/산출물 영속) + Postgres/RLS(기록 DB). 현 Phase1은 Render 임시디스크(재배포시 소실).
- **[_handoff 비대칭]** fetch/인증 코드가 webapp/static에만 → _handoff 재복사 시 인증 소실 위험(conventions.md). login.html만 원본↔복사 동일.
- **[U넥 자산]** 농구_U넥_양면 design_XL.ai .gitignore 자산 로컬부재 → 합성 A+B full job 시각회귀 미실시(코드 동등성 검증). 자산 확보 시 권장.
- **[합성 일반화]** hide_design_cutline_layer는 V넥 BDC구조·"패턴선"·page0 한정 → 신규 디자인 온보딩 체크리스트.
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·_JOBS TTL 정리. progress 콜백.
- **[디자이너 대기]** 재단선 PDF포함 .ai 재출력 / 올바른 3XL.ai 재확보(현 disabled). **[job.py:732]** _auto_bleed 직전 front svg_index 범위가드 부재(비치명).

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만, 단 fetch/인증코드는 static에만=비대칭). 커밋 전 ast.parse/py_compile. **--workers 1 유지**(_JOBS 인메모리·인증캐시 일관). 비밀키(SECRET) 레포·프런트 금지.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→cover(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, cover_bleed preset 키 있을때만(없으면 contain=U넥 회귀0).
- **사이즈별 자동 블리드**: cover_bleed가 `{auto:true,k:1.3,min:1.0,max:1.12}` dict면 앞판 기준 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1+k·dev,lo,hi)` 단일값→전 조각 등방. float=기존 단일·None=contain. XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036.
- **본체색 채움(흰틈)**: Piece.bg_cmyk(기본None) 있으면 place_block이 클립(W n)직후·Do앞 폴리곤 **재경로** 후 device k+f 채움(⚠️W n이 경로소비→재경로 필수). run_job 본체색 1회 결정: preset.body_fill([0.8,0.5,0,0.1]) > detect_background_cmyk > None.
- **재단선**: 조각 SVG poly.points를 시트좌표 그대로 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). draw_from="svg_polygon".
- **디자인 패턴선 두 줄 방지**: OCG OFF는 Form 합성에 무효 → 콘텐츠 BDC…EMC 삭제(빨강1색만·5색 무손실). hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=design_region. SVG 넥깊이로 앞(svg1)/뒤(svg0)/밴드(svg2).
- 글자주입: place_*(잉크bbox 중앙정렬)→조각 transform 감싸 extra_ops(클립밖, Do뒤). 번호: glyph_source 있으면 글리프셋(advance0.6611·글자별lsb), 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체 포함(아니면 3.4KB 흰화면). 정상 빈본체=88KB.
- **출력형식**: flatten Form투명도그룹 제거·페이지그룹 /CS 보존. eps2write. EPS 305KB 벡터.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2. 12사이즈(3XL disabled, disabled_sizes는 sizes 밖).
- **배포/GS/포트**: GS경로=eps.find_ghostscript 맨앞 GS_BIN env 우선(없으면 settings_path→Windows절대→PATH 폴백, 로컬회귀0). state.DEFAULT_PORT=int(PORT env, 8000). Dockerfile CMD shell form `${PORT:-8000}`(Render $PORT 호환, 정본 8000고정 대신 채택). --workers 1.
- **인증(introspection, 갱신본)**: webapp/auth.py require_auth — **GRADER_REQUIRE_AUTH 토글**(로컬 미설정=무인증 통과·배포 =1=검증). ON이면 Bearer 토큰으로 `httpx.get({SUPABASE_URL}/auth/v1/user, apikey=PUBLISHABLE, Authorization=Bearer, timeout=5)` → 200이면 id·email·app_metadata.role을 request.state, 비200/예외=401. **토큰별 60초 캐시**(_TOKEN_CACHE+_CACHE_LOCK). **admin_required**(role!=admin→403, 토글OFF면 통과)를 POST /api/patterns·PUT /api/settings에만. **/api/health·/api/public-config 무인증**(public_router) — health 막으면 Render 부팅실패. 나머지 /api/* 전역 Depends. **/api/public-config**={supabase_url, supabase_publishable_key}만(SECRET 절대 금지). 프런트 apiFetch: Bearer 부착·401시 sessionStorage(키 grader_access_token) clear+login 리다이렉트·FormData boundary보존·preview/zip blob. **루트 / → login.html 리다이렉트**(미인증 우회 차단, errors.md). login.html=supabase-js CDN createClient(URL,PUBLISHABLE)·signInWithPassword·유효세션시 work직행. SECRET·SERVICE_ROLE·JWT_SECRET·pyjwt 전부 제거.
- ⚠️ 함정(errors.md): 변환 viewBox통일·미리보기육안. 인접사이즈 좌표동일=자산결함. 브라우저 드롭 document가드+좌표. W n 경로소비→fill 재경로. 프런트 인증 게이트=루트→login+클라세션판정+apiFetch401가드.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job(cover/auto_bleed+본체색채움+재단선polygon+OCG제거+disabled+out_format)·svg_normalize·order(①②③STIZ)·flatten(+detect_background_cmyk)·eps(+GS_BIN env)·compose(+Piece.bg_cmyk)·pdfutil(place_block+bg_cmyk fill)·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main(루트→login·public/api 라우터 분리)·auth(introspection require_auth+admin_required+60초캐시)·api(health·public-config 무인증 + patterns·settings[admin]·order/parse·design/check5·jobs비동기·preview·zip·기록·등록)·state(PORT env)·run.py·run.bat. static=_handoff 복사본(단 fetch/인증코드는 static에만). login.html(supabase-js).
- 배포: Dockerfile(${PORT})·render.yaml(env URL·PUBLISHABLE·SECRET·GS_BIN·GRADER_REQUIRE_AUTH)·.dockerignore·.env.example(루트). 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면}. data/{jobs,uploads}/·settings.json(.gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋·_완성본.
- 주문서: C:/Users/user/Desktop/새 폴더/260213_…추가주문서.xlsx. 폰트 HY헤드라인M.ttf. 로컬 GS C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- 테스트 산출물 `_abtest/`·`_glyphtest/`는 .gitignore. 로컬 .env(키 PUBLISHABLE/SECRET, git/docker 제외=안전·코드 기대와 정합).
- git: origin=cobby8/grader-v2, main. 의뢰서/사용설명서 .md는 미추적(커밋 제외). **푸시 후 미푸시 갱신**.

## 구현/테스트/리뷰/기획설계
(완료분 상세는 git+knowledge. introspection 갱신: tester36/36 합격·reviewer 통과 치명0, 되돌림2 해결[PORT·sessionStorage clear])

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| tester/reviewer | apiFetch 401 | sessionStorage clear 누락(의뢰서4) | ✅ 완료(4화면 removeItem) |
| reviewer | Dockerfile PORT | 8000고정→$PORT 미스매치 | ✅ 완료(shell form ${PORT:-8000}) |
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성·재확보 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-25 | dev/test/rev | 합성 A+B 구현·검증·커밋 | tester6/6·rev치명0·푸시(6d5dd9c) |
| 2026-06-25 | planner→dev→test→rev→pm | 배포 Phase1(JWT) | tester24/24·커밋ef33874·푸시 |
| 2026-06-25 | planner-architect | 배포 갱신본 introspection 마이그레이션 설계 | auth전면교체·env PUBLISHABLE/SECRET·admin게이트·Dockerfile $PORT 권고 |
| 2026-06-26 | dev | introspection+프런트 로그인흐름 통합구현 | auth introspection+60초캐시+admin, 루트→login, public-config, pyjwt제거. 404 근본원인(루트 work직행) 수정. ast/grep통과 |
| 2026-06-26 | tester | 갱신본 독립검증(httpx 모킹) | 36/36 합격. 로컬회귀0·인증·60초캐시·admin403·SECRET0·루트/login·selftest PASS |
| 2026-06-26 | reviewer | 갱신본 리뷰 | 통과 치명0. SECRET0·timeout5·캐시Lock·루트404해결. 권장2(캐시정리·핑퐁) |
| 2026-06-26 | dev | 되돌림2: apiFetch 401 sessionStorage clear | 4화면 removeItem(TOKEN_KEY), login.html 키 일치 |
| 2026-06-26 | pm | introspection 갱신 커밋+회고(errors/decisions)+scratchpad정리+푸시 | — |
