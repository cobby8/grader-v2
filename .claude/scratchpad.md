# 작업 스크래치패드

## 현재 작업
- **요청**: 인터넷 배포 Phase 1 — 컨테이너화(Dockerfile)+Render(render.yaml)+Supabase Auth 로그인 게이트. 저장은 Render 임시디스크 허용(Storage/DB는 Phase 2~3). 정본: 의뢰서-CLI-클라우드배포-Supabase-Render.md Phase 1.
- **상태**: 🔵 진행중 — 되돌림 루프1(developer: Dockerfile PORT 폴백 수정). tester24/24 합격·reviewer 조건부통과(주의1=PORT). 사용자 결정: 로컬 무인증 토글.
- **현재 담당**: developer (되돌림)

### 의뢰서 Phase 1 핵심
1. **Dockerfile**(루트): python:3.11-slim + ghostscript·fontconfig apt설치, requirements설치, GRADER_NO_BROWSER=1·GS_BIN=gs, EXPOSE 8000, uvicorn webapp.main:app --workers 1.
2. **GS 경로 환경변수화**: EPS 호출부가 os.environ["GS_BIN"](기본 gs) 우선 > preset/settings ghostscript_path. Windows 절대경로 폴백은 로컬용 유지. DEFAULT_PORT=int(os.environ.get("PORT",8000)). run.bat/run.py(127.0.0.1) 로컬 경로 그대로.
3. **render.yaml**(루트): web/docker/starter, healthCheckPath /api/health, envVars(sync:false) SUPABASE_URL·ANON_KEY·SERVICE_ROLE_KEY·JWT_SECRET·GS_BIN=gs.
4. **인증 게이트(Supabase Auth)**: requirements에 pyjwt·httpx. FastAPI Dependency가 /api/*(/api/health 제외) Authorization: Bearer 토큰을 SUPABASE_JWT_SECRET(HS256) 검증, 실패401, user id/role→request.state. 프런트 login.html(@supabase/supabase-js CDN 이메일+비번)→access_token 저장+공통 fetch 래퍼가 모든 /api에 Authorization 부착, 미인증 리다이렉트. URL/ANON_KEY 프런트 노출OK, SERVICE_ROLE·JWT_SECRET 백엔드 env 전용(레포·프런트 금지).
- **불변**: 엔진 공개 API 무수정. CMYK·투명도없음·벡터 verify 유지. 비밀키 레포 금지. --workers 1 유지.
- **완료기준**: ①Render URL 미로그인 차단→로그인후 5단계(패턴→디자인→주문서→생성→검수→ZIP) 동작 ②산출물 1건 다운로드 정상(앞뒤·채움·재단선·번호·자간) ③로컬 run.bat 회귀0.
- **사용자 준비물**: Supabase(이메일로그인+키4개), Render(GitHub 연결→env입력→배포).

## 진행 현황 (완료 — 상세는 git 히스토리 + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 출력형식 PDF/EPS/both | flatten Group제거·eps2write·verify_eps·--format | ✅ tester13/13 |
| 웹앱1~5 | FastAPI 풀스택(order/design/jobs비동기/기록/등록/설정)+run.bat | ✅ rev종합 치명0 |
| 화면버그+실OS드롭 | both/EPS·드래그앤드롭·헤더·3XL칩·푸터 / document가드+좌표 | ✅ tester9/9·debugger |
| 합성1·2·3 | 자동매핑·cover+블리드·재단선1줄(svg_polygon)·패턴선 OCG제거 | ✅ tester12/12·rev통과 |
| 배번 글리프셋 | 자간(advance 0.6611)+"1" lsb 보정 | ✅ selftest PASS·verify4/4 |
| **합성 A+B** | 본체색 채움(Piece.bg_cmyk)+사이즈별 자동블리드(auto_bleed) | ✅ tester6/6·rev통과 치명0 |

## 백로그 (차단 아님, 후속)
- **[U넥 자산]** 농구_U넥_양면 design_XL.ai가 .gitignore 자산이라 로컬 부재 → A+B 후 full job 시각회귀 미실시(코드 동등성으로 하위호환 본질만 검증). 자산 확보 시 권장.
- **[합성 일반화]** hide_design_cutline_layer(OCG 콘텐츠삭제)는 V넥 BDC구조·레이어명("패턴선")·page0 한정 → 신규 디자인 온보딩 시 재확인 체크리스트. 재단선 보존체크 n_out>=expected라 '과다(두줄)' 못 거름(시각검증 보완).
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·_JOBS·_design_no_cutline TTL 정리(디스크/메모리 누적). progress 콜백.
- **[디자이너 입력 대기]** 재단선 PDF포함 .ai 재출력 / 올바른 3XL.ai 재확보(현 disabled).
- **[job.py:732 주의]** _auto_bleed 직전 `polys[front svg_index]` 범위가드 부재(행 try/except엔 잡힘, 비치명). 자산결함 시 보강 가능.
- cowork 최종 오버레이 검증(번호글리프셋·밴드·재단선·본체·합성). band design_region 정밀재추출.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). CLI/curl 단독검증. GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만). 커밋 전 ast.parse/py_compile.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→**cover**(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, **cover_bleed preset 키 있을때만**(없으면 contain=U넥 회귀0). clip이 넘침 차단.
- **사이즈별 자동 블리드**: preset cover_bleed가 `{auto:true,k:1.3,min:1.0,max:1.12}` dict면 _build_precise_layout이 앞판 기준 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1+k·dev,lo,hi)` 단일값 산출→전 조각 등방 적용(번호/이름 무왜곡). float이면 기존 단일. None이면 contain. XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036.
- **본체색 채움(흰틈 제거)**: Piece.bg_cmyk(기본 None) 있으면 place_block이 클립(`W n`)직후·`Do`앞 폴리곤 **재경로** 후 device k+f로 채움(⚠️W n이 경로 소비→fill용 재경로 필수, errors.md). run_job이 본체색 1회 결정: preset.body_fill(이번값[0.8,0.5,0,0.1]) > detect_background_cmyk(pikepdf.Pdf객체) > None. 디자인이 위를 덮어 빈 곳만 본체색=등방.
- **재단선**: 조각 SVG poly.points(=clip outline 동일좌표·너치 포함)를 시트좌표 그대로 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). cutline.draw_from="svg_polygon". transform 안 감쌈.
- **디자인 패턴선 두 줄 방지**: OCG D.OFF는 Form 합성에 무효 → 콘텐츠 /OC /MCx BDC…EMC 구간 삭제(깊이카운트 짝맞춤, 빨강1색만 제거·5색 무손실). hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=조각 design_region. SVG 넥깊이로 앞(V넥깊은=svg1)/뒤(라운드=svg0)/밴드(높이최소=svg2) 매칭.
- 글자주입: text place_*(잉크 bbox 중앙정렬, 디자인좌표)→조각 transform 감싸 extra_ops(클립 밖, Do 뒤). 번호: glyph_source 있으면 글리프셋(advance 0.6611·글자별 lsb), 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체 PDF 포함(아니면 3.4KB 흰화면). 정상 빈본체=88KB.
- **출력형식**: flatten Form투명도그룹 제거(EPS 래스터화 트리거)·페이지그룹 /CS 보존. eps2write. EPS 305KB 벡터.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2. 12사이즈(3XL disabled, disabled_sizes는 sizes 밖).
- ⚠️ 변환함정(errors.md): 조각수+verify만으론 부족→viewBox통일·양수·미리보기 육안. 인접사이즈 좌표동일=자산결함. 브라우저 드롭은 document가드+좌표판정.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference(+build_pieces_preset/extract_design_pieces)·job(정밀배치+cover/auto_bleed+본체색채움+재단선polygon+OCG제거+disabled+out_format)·svg_normalize·order(①②③STIZ)·flatten(+Group제거+detect_background_cmyk)·eps·compose(+Piece.bg_cmyk)·pdfutil(place_block+bg_cmyk fill)·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main·api(health/patterns/settings·order/parse·design/check5·jobs비동기+progress+preview+zip·기록·등록)·state·run.py·run.bat. webapp/static=_handoff/grader-v2-static 복사본(원본 보존, 갱신시 재복사).
- 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면(SVG12+preset+number_glyphs.json)}. data/{jobs,uploads}/·settings.json(.gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋_아트보드2.ai·_완성본_본체포함_XL.ai.
- 주문서: C:/Users/user/Desktop/새 폴더/260213_…추가주문서.xlsx. 폰트 data/fonts/HY헤드라인M.ttf. GS C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- 테스트 산출물 `_abtest/`는 .gitignore 대상 아님(커밋 제외 주의). cowork PNG: _abtest/out_allsize/preview/{5XS,XL,M,5XL}_20_*.png.
- git: origin=cobby8/grader-v2, main. **미푸시 1개**(합성 A+B).

## 구현/테스트/리뷰/기획설계
(완료 — 상세 git 히스토리 + knowledge. A+B: tester6/6 PASS·reviewer 통과 치명0, bleed 검산 cowork값 정확일치)

### 테스트 결과 (tester) — 배포 Phase 1 독립검증 [2026-06-25]

🔬 환경: Python 3.11.9, fastapi 0.138.0/starlette 1.3.1, pyjwt 2.10.1, httpx 0.28.1. Docker 미설치(7번 빌드 SKIP). GS: PATH에 gswin64c·절대경로 존재(gs는 PATH에 없음). TestClient(starlette)+테스트시크릿 직접 HS256 서명으로 검증. 코드 무수정(검증 임시파일 _qa_verify.py 작성→실행→삭제).

| # | 검증 항목 | 결과 | 근거 |
|---|----------|------|------|
| 1 | **로컬 무인증 회귀(치명)** | ✅ PASS | env 미설정: auth_required()=False / GET /api/patterns 200(토큰없이, n=2) / /api/settings 200 / /api/health 200 / DEFAULT_PORT=8000 / find_ghostscript() GS_BIN미설정시 절대경로 폴백 / PORT=10000 주입시 DEFAULT_PORT=10000 |
| 2 | **배포 인증 게이트** | ✅ PASS | GRADER_REQUIRE_AUTH=1: 토큰없음401·유효토큰200·잘못된서명401·만료401·잘못된aud401·Bearer접두어없음401·빈토큰401 (7케이스 전부 기대대로) |
| 3 | **/api/health 무인증(치명)** | ✅ PASS | 인증ON+토큰없이 /api/health 200·/api/config 200. config 응답에 비밀키 미포함(auth_required/supabase_url/anon_key만) |
| 4 | **GS env 폴백 단위** | ✅ PASS | 시그니처 불변(settings_path 기본None→Optional[str]) / GS_BIN미설정→기존체인 / GS_BIN=gswin64c(PATH존재)→그걸우선(which일치) / GS_BIN=없는실행→무시·폴백 / settings_path존재→그대로 / 반환 str|None |
| 5 | **비밀키 레포 부재** | ✅ PASS | eyJ(JWT형태) 0건·SERVICE_ROLE/JWT_SECRET 실제값 0건. 코드는 os.environ.get 참조뿐. render.yaml 비밀4개(URL·ANON·SERVICE_ROLE·JWT_SECRET) 모두 sync:false. .gitignore에 .env 3패턴·추적되는 .env 0건. (참고: 로컬 .env에 사용자 실값 있으나 git/docker 둘다 제외=안전) |
| 6 | **프런트 인증 흐름(정적)** | ✅ PASS | login.html: supabase-js CDN·signInWithPassword·access_token→sessionStorage(키 grader_access_token)·auth_required=false면 work직행. work/patterns/settings/history 4화면 모두 apiFetch 정의1·Authorization부착·401리다이렉트·raw fetch("/api 0건(전부 apiFetch교체). FormData(uploadDesign/Order)는 body:fd만 넘겨 Content-Type 미지정(boundary보존). preview/zip은 apiFetch+blob URL+revokeObjectURL. TOKEN_KEY 3화면 동일. login 원본=복사본 동일(diff) |
| 7 | **Docker 빌드 스모크** | ⚪ SKIP→정적PASS | Docker 미설치로 빌드 SKIP. 대신 정적점검: webapp.main:app import OK(FastAPI)·requirements 9개 전부 importable·base python:3.11-slim↔requirements 3.11 일치·apt ghostscript/fontconfig↔GS_BIN=gs 정합·ENV 3개·CMD --workers 1 유지 |
| 8 | **selftest 회귀** | ✅ PASS | python -m engine selftest 종합 PASS(6사이즈24배치·디자인무손실·CMYK·투명도없음·Do 24회·inkcov 편차0.000000) |

📊 **종합 판정: 합격** — 24개 자동검증 중 24개 통과(4-a "시그니처불변 FAIL"은 from __future__ annotations로 인한 문자열어노테이션 표기 차이일 뿐 시그니처 실불변=실질PASS). 치명항목(1 로컬회귀·3 health무인증) 모두 엄격 통과. 로컬 무인증 회귀 0, 배포 인증게이트·health무인증 정상.

⚠️ 비차단 참고(배포 시 사용자 안내 필요): 로컬 `.env`의 키 이름이 코드 기대값과 불일치(.env: SUPABASE_PUBLISHABLE_KEY/SECRET_KEY/JWKS_URL ↔ 코드: SUPABASE_ANON_KEY/JWT_SECRET). Render env 입력 시 코드가 읽는 정확한 키이름(SUPABASE_ANON_KEY·SUPABASE_JWT_SECRET·SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY)으로 등록해야 함. Phase1 코드동작 검증 범위 밖이라 비차단.

### 구현 기록 (developer) — 배포 Phase 1 [2026-06-25]

📝 구현한 기능: 로컬 전용 웹앱을 "로그인해야 들어가는 인터넷 사내도구"로 — Docker 컨테이너화 + Render 배포 + Supabase Auth 게이트. **GRADER_REQUIRE_AUTH 토글로 로컬 무인증/배포 인증 분기**(로컬 회귀 0).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/eps.py | find_ghostscript 맨 앞 GS_BIN env 분기(shutil.which 채택, 기존 체인 보존) | 수정 |
| webapp/state.py | DEFAULT_PORT=int(os.environ.get("PORT",8000)) | 수정 |
| webapp/auth.py | FastAPI Dependency require_auth: 인증 꺼지면 통과(state.user_id=None), 켜지면 Bearer JWT HS256(aud=authenticated) 검증·실패401·성공시 sub/role 채움 | 신규 |
| webapp/api.py | health를 public_router(무인증)로 분리 + /api/config(공개키 노출, 비밀키X) 추가 | 수정 |
| webapp/main.py | public_router(무인증)·api_router(Depends(require_auth) 전역) 붙임 + /login 라우트 | 수정 |
| requirements.txt | pyjwt==2.10.1, httpx==0.28.1 추가 | 수정 |
| _handoff/.../screens/login.html | Supabase JS CDN 이메일+비번 로그인 → sessionStorage 토큰 저장 → work.html | 신규 |
| webapp/static/screens/login.html | 위 원본 복사본(동일성 확인 OK) | 신규(복사) |
| webapp/static/screens/{work,patterns,settings,history}.html | 공통 apiFetch 래퍼(토큰 부착·401 리다이렉트·FormData headers만 머지)+기존 fetch→apiFetch 교체. work는 preview/zip을 blob방식으로(img src/href는 토큰 못붙음 대응) | 수정 |
| Dockerfile (루트) | python:3.11-slim+ghostscript·fontconfig, ENV GRADER_NO_BROWSER=1 GS_BIN=gs GRADER_REQUIRE_AUTH=1, uvicorn --workers 1 | 신규 |
| render.yaml (루트) | web/docker/starter, healthCheckPath /api/health, env(sync:false 4 비밀 + GS_BIN/GRADER_REQUIRE_AUTH 값) | 신규 |
| .dockerignore (루트) | data/jobs·uploads·.venv·_abtest·design_source·.git·_handoff·.env 제외 | 신규 |
| .env.example (루트) | 로컬/배포 env 키 안내(비밀값 없이 이름만) | 신규 |
| .gitignore | .env·.env.local·.env.*.local 추가 | 수정 |

⚠️ **설계와 다르게 처리한 점(중요)**: 설계는 "_handoff 원본 먼저 고치고 webapp/static 복사"였으나, **실파일 비교 결과 fetch(/api) 코드는 webapp/static 복사본에만 있고 _handoff 원본엔 없음**(이전 단계에서 static에 직접 API연동 추가, 원본 역반영 안 됨 — work 40KB vs 62KB). 원본대로 복사하면 동작중인 API연동이 전부 사라지는 회귀 발생 → 불변제약 위반. 그래서 **fetch 있는 4화면은 webapp/static을 실수정 대상**으로 삼고, login.html(신규)만 원본→복사 동일성 유지. _handoff work 등은 fetch 없어 인증 끼울 대상 없음(무수정).

🔑 GRADER_REQUIRE_AUTH 토글 동작:
- 미설정/0/false(로컬 기본): require_auth 검증 스킵=통과, state.user_id=None. GS_BIN·PORT 미설정시 기존 폴백/8000. → **회귀 0**.
- 1/true/yes/on(배포): Bearer 토큰 필수, SUPABASE_JWT_SECRET(env전용)로 HS256 검증. /api/health·/api/config만 무인증(Render healthCheck·프런트 공개키 로드).

💡 tester 참고:
- **로컬 무인증 회귀**: env 안 켜고 run.bat → 5단계(패턴→디자인→주문서→생성→검수→ZIP) 그대로. patterns/jobs 200, login리다이렉트 안 일어남.
- **미로그인 401**: `GRADER_REQUIRE_AUTH=1 SUPABASE_JWT_SECRET=x` 켜고 토큰없이 /api/patterns → 401. /api/health → **200**(반드시. Render부팅).
- **로그인 후**: /api/config로 supabase 키 받아 login.html에서 로그인 → sessionStorage 토큰 → work 5단계.
- **GS env 폴백**: GS_BIN 미설정시 기존 Windows절대경로, GS_BIN=gs면 PATH gs. (검증완료: 미설정/유효/무효 3케이스 폴백일치)
- 검증 완료(개발 스모크): auth A토큰없음401/B잘못된토큰401/C유효토큰통과, 앱레벨 health200(인증ON)·patterns401(토큰없음)·유효토큰200, PORT/GS_BIN/포트 회귀, login.html 원본=복사본.

⚠️ reviewer 참고:
- 불변제약: engine 공개API(find_ghostscript 시그니처·반환 불변, 분기1개만 맨앞 추가). --workers 1 유지. compose/verify 무수정.
- 비밀키 부재: grep 결과 JWT토큰형태(eyJ)·실제 시크릿값 레포/프런트/Dockerfile **0건**. SUPABASE_*는 os.environ.get 또는 render.yaml sync:false(키이름만). 프런트엔 URL/ANON_KEY만(/api/config로 런타임 주입).
- 인증 끼움점: public_router(health/config 무인증) vs api_router(Depends(require_auth) 전역). main.py include_router 2개로 분리. /api/health에 인증 안 걸림 재확인 요망.
- FormData 머지: apiFetch가 Content-Type 안 건드리고 Headers에 Authorization만 set(브라우저 boundary 보존). work의 design/check·order/parse·patterns POST 확인.
- preview/zip blob처리: img src/a href는 토큰 못붙어 401 → work만 apiFetch+blob URL로 변경(loadJobResult preview, downloadZip). objectURL revoke 포함.

✅ ast.parse+py_compile: 5개 .py 전체 OK. 비밀키 grep: 0건. 배포파일 4개 존재확인 OK. login 원본=복사본 동일 OK.

#### 수정 이력
| 회차 | 날짜 | 수정 내용 | 수정 파일 | 사유 |
|------|------|----------|----------|------|
| 1차 | 2026-06-25 | Dockerfile CMD를 exec form `--port 8000` 고정 → shell form `["sh","-c","python -m uvicorn ... --port ${PORT:-8000} --workers 1"]`로 변경(Render 주입 $PORT 호환, 없으면 8000 폴백). exec form(JSON 배열)은 환경변수 확장 불가 → shell form(sh -c)이어야 ${PORT:-8000} 확장됨을 주석으로 명시. EXPOSE 8000은 문서용이라 유지(주석으로 $PORT 동작 보강). 로컬 docker run·run.bat/run.py 무영향. --workers 1 유지. | Dockerfile | reviewer 요청: Render Docker 웹서비스가 $PORT(보통 10000)로 헬스체크를 보내는데 8000 고정이면 부팅 unhealthy 차단 가능 |

### 기획설계 (planner-architect) — 배포 Phase 1 [2026-06-25]

🎯 목표: 로컬 전용 웹앱을 "로그인해야 들어가는 인터넷 사내도구"로 — Docker 컨테이너화 + Render 배포 + Supabase Auth 게이트 (저장은 Render 임시디스크 허용, Storage/DB는 Phase 2~3).

📍 만들 위치와 구조:
| 파일 경로 | 역할 | 신규/수정 |
|----------|------|----------|
| Dockerfile (루트) | python:3.11-slim+ghostscript·fontconfig, GS_BIN=gs, uvicorn webapp.main:app --workers 1 | 신규 |
| render.yaml (루트) | web/docker/starter, healthCheckPath /api/health, env 5개(sync:false 4 + GS_BIN=gs) | 신규 |
| .dockerignore (루트) | data/jobs·uploads·.venv·_abtest·design_source 제외(이미지 경량+비밀 차단) | 신규 |
| webapp/auth.py | FastAPI Dependency: Bearer JWT를 SUPABASE_JWT_SECRET(HS256) 검증, request.state에 user | 신규 |
| _handoff/grader-v2-static/screens/login.html | Supabase JS(CDN) 이메일+비번 로그인 화면(원본) | 신규 |
| webapp/static/screens/login.html | 위 원본의 복사본(서빙 대상) | 신규(복사) |
| engine/eps.py | find_ghostscript에 GS_BIN env 최우선 분기 추가(Windows 폴백 보존) | 수정 |
| webapp/state.py | DEFAULT_PORT=int(os.environ.get("PORT",8000)) | 수정 |
| webapp/main.py | api_router에 인증 Dependency 연결 + /(루트) 인증분기 + login.html 라우트 | 수정 |
| webapp/api.py | router에 Depends(require_auth) 적용(/api/health 제외) | 수정 |
| requirements.txt | pyjwt, httpx 추가 | 수정 |
| _handoff/grader-v2-static/screens/*.html (work 등 4개) | 공통 fetch 래퍼+Authorization 헤더+미인증 리다이렉트(원본) | 수정 |
| webapp/static/screens/*.html | 위 복사본(서빙 대상) | 수정(복사) |
| .env.example (루트, 선택) | 로컬 env 키 안내(비밀값 없이 키 이름만) | 신규 |

🔗 핵심 구조 사실(정밀분석):
- **라우트/마운트**: main.py가 ①app.include_router(api_router) ②app.mount("/static", StaticFiles(html=True)) ③GET "/"는 work.html로 RedirectResponse. api.py router=APIRouter(prefix="/api"), /api/health 포함 모든 핸들러가 여기 묶임.
- **GS 체인**: job.py:907 gs_path=preset.output.ghostscript_path → eps.py:find_ghostscript(gs_path)가 ①settings_path(존재시) ②_GS_ABS_CANDIDATES(Win절대경로) ③PATH(gswin64c/gswin32c/gs). verify.py:gs_exe()는 inkcov 선택검증용(PATH기반 gs 이미 OK). → GS_BIN env 주입점=eps.py:find_ghostscript 맨 앞 1개.
- **정적 fetch**: 각 화면 단일 inline <script>(work.html 136~1172줄), 별도 .js 없음. fetch("/api/...") 같은 절대상대경로 직접호출 다수(work 16곳·patterns·history·settings). 공통 래퍼 없음 → 새로 도입 필요.
- **_handoff 규칙**: webapp/static = _handoff/grader-v2-static 복사본. README 명시 "원본 무수정 갱신시 재복사" → 원본 먼저 만들고/고치고 webapp/static으로 복사.
- **포트**: state.py:36 DEFAULT_PORT=8000 하드코딩(api/health·run.py가 참조). run.py는 127.0.0.1 고정(로컬용, 무수정). Docker CMD가 0.0.0.0:8000 직접 지정.

📋 실행 계획(7단계):
| 순서 | 작업 | 담당 | 선행 |
|------|------|------|------|
| 1 | GS_BIN 환경변수화(eps.py find_ghostscript 1순위) + DEFAULT_PORT env(state.py) | developer | 없음 |
| 2 | requirements(pyjwt,httpx) + webapp/auth.py(JWT Dependency) + main/api 연결(/health 제외) | developer | 1 |
| 3 | login.html 원본 작성(_handoff) + 공통 fetch 래퍼 주입(원본 work 등) | developer | 없음(2와 병렬가능) |
| 4 | _handoff→webapp/static 복사(login.html+수정 화면) | developer | 3 |
| 5 | Dockerfile + .dockerignore + render.yaml + .env.example | developer | 1,2 |
| 6 | 로컬 회귀(run.bat 5단계·GS 폴백·미로그인 401) + Docker 빌드 스모크 | tester + reviewer(병렬) | 4,5 |
| 7 | 사용자 준비물 안내(Supabase·Render 체크리스트) + 커밋 | pm | 6 |

⚠️ developer 주의사항:
- 엔진 무수정: eps.py find_ghostscript는 신규 분기 1개만 맨 앞에 추가(기존 폴백 체인 그대로). pdf_to_eps/verify_eps 시그니처 무수정.
- /api/health는 절대 인증 막지 말 것(Render healthCheck가 부팅 차단됨). Dependency를 health 핸들러에만 제외하거나, router 전역 적용 후 health를 분리.
- 비밀키(JWT_SECRET·SERVICE_ROLE) 레포·프런트·로그 금지. .gitignore에 .env 추가 확인(settings.json은 이미 제외).
- 프런트 Authorization 헤더는 FormData 업로드(/order/parse·/design/check·/patterns)에도 붙여야 함(Content-Type 자동설정 깨지 않게 headers만 머지).
- 미인증시 login.html 리다이렉트는 토큰 없을 때+401 응답 둘 다 처리.
- run.py/run.bat 127.0.0.1 무수정(로컬 회귀0). state.py는 DEFAULT_PORT 1줄만.

### 리뷰 결과 (reviewer) — 배포 Phase 1 [2026-06-25]

📊 종합 판정: **조건부 통과** (치명0, 주의1=PORT 바인딩, 제안 몇 건). 보안·인증·불변제약은 전부 통과. 주의 1건만 배포 전 확인 권장.

✅ 잘된 점:
- **비밀키 노출 0건**(검증됨): 레포 전체 grep(eyJ 토큰형·service_role·JWT_SECRET 값할당) 결과 실제 비밀값 0. 유일 매치는 의뢰서.md의 "키 확보하라" 안내문(값 아님). render.yaml 비밀4개(URL·ANON·SERVICE_ROLE·JWT_SECRET) 전부 sync:false(키이름만). 프런트(login.html)는 /api/config 런타임 주입으로 URL/ANON_KEY만 받음. /api/config가 SUPABASE_JWT_SECRET·SERVICE_ROLE 절대 안 내보냄(auth_required·url·anon_key 3개만 return). .env는 .gitignore+.dockerignore 양쪽 차단.
- **JWT 검증 견고**(auth.py): algorithms=["HS256"] 명시 고정(alg=none·RS256 혼동 우회 차단), audience="authenticated" 체크, 서명검증 PyJWT 기본 ON. secret 없으면 500(검증 스킵 아님), 토큰 없음/빈토큰/검증실패 전부 401. 예외는 통째로 잡아 401(원인은 서버로그만, 화면 한국어).
- **인증 끼움점 정확**: public_router(/api/health·/api/config 무인증) vs api_router(main.py가 include 시 dependencies=[Depends(require_auth)] 전역). health에 인증 안 걸림 확인 → Render 헬스체크 통과. 토글 꺼짐(로컬)=request.state.user_id/role=None 안전기본값 박고 통과(회귀0), 켜짐(배포)=Bearer 필수.
- **불변제약 준수**: eps.find_ghostscript 시그니처·반환 불변, GS_BIN 분기 1개만 맨앞 추가(shutil.which로 실재확인 후 채택, 없으면 기존 체인 폴백 그대로 → 로컬 회귀0). state.py DEFAULT_PORT 1줄. --workers 1 유지. compose/verify/엔진 무수정.
- **프런트 apiFetch 정확**: Headers에 Authorization만 set(FormData Content-Type 안 건드림→boundary 보존). 401→login 리다이렉트+throw. 토큰 없으면 헤더 미부착(로컬 통과). preview(img src)·zip(a href)는 토큰 못붙어 401날 것을 정확히 간파→blob방식(apiFetch로 받아 createObjectURL, revoke로 누수방지). 4개 화면 전부 apiFetch 일관 적용, 직접 fetch( 잔존은 래퍼 내부 1회뿐.
- **Dockerfile/render.yaml 품질**: apt ghostscript·fontconfig + --no-install-recommends + apt캐시 삭제 1 RUN(경량). requirements 먼저 COPY(레이어캐시). .dockerignore가 data/jobs·uploads·_abtest·design_source·.git·_handoff·.env 제외(경량+비밀차단). healthCheckPath /api/health 정합. login.html 원본=복사본 diff 동일 확인.

🟡 주의 (배포 전 확인 — 부팅 차단 가능성):
- [Dockerfile:41 + render.yaml] **PORT 바인딩 불일치 가능성**. Render의 Docker 웹서비스는 컨테이너에 PORT 환경변수를 주입하고 그 포트(보통 10000)로 헬스체크·트래픽을 보낸다. 그런데 CMD가 `--port 8000` **고정**이라 uvicorn은 8000에서만 listen → Render가 $PORT로 /api/health를 찌르면 연결 실패로 "부팅 unhealthy"가 될 수 있음. (Render가 EXPOSE 포트를 자동감지하는 경우 동작할 수도 있어 '확정 치명'은 아니나, 배포 첫 시도에서 가장 깨지기 쉬운 지점.) → 권장: CMD를 `sh -c 'uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1'` 로 바꿔 $PORT 우선·없으면 8000 폴백. (state.py·health의 port표시값은 이미 $PORT를 읽으므로, 실제 listen 포트와 일치시키면 표시도 정합.) **developer 판단 필요 — 코드 미수정(검토만).**

💡 제안 (비차단, 후속 가능):
- [api.py:84 health port] health가 돌려주는 port=DEFAULT_PORT(=$PORT or 8000)는 '표시용'. 위 PORT 수정 시 자동 정합. 미수정 시 배포에서 표시 포트(예 10000)≠실listen(8000) 불일치하나 기능 영향 0.
- [auth.py:108~110 role] app_metadata.role만 읽음. Supabase는 보통 role을 'user_metadata' 또는 최상위 'role'(=authenticated)에 둠 → app_metadata.role은 대개 None일 것(현재 인가에 role 미사용이라 무해, 추후 권한분기 도입 시 위치 재확인).
- [백로그 유지] 업로드 확장자/용량 검증·uploads TTL 정리(디스크 누적)는 기존 백로그대로. Render 임시디스크라 재시작시 비워져 Phase1 한정 비차단.
- [_handoff 비대칭 주의 — 영구 기록 권장] fetch 있는 4화면(work/patterns/settings/history)은 webapp/static을 '실수정 대상'으로 삼았고 _handoff 원본엔 apiFetch/인증 코드가 없음. → **추후 디자인 갱신으로 _handoff→webapp/static 재복사하면 인증·apiFetch가 통째로 사라지는 회귀** 발생. developer의 이번 판단(비대칭 상황에서 static 직접수정)은 타당하나, 재복사 규칙과 충돌하는 구조적 함정이므로 conventions.md에 명시 기록함(PM 승격 권장).

📁 검토 파일(전부 절대경로): webapp/auth.py, main.py, api.py(1~106·public_router), state.py, engine/eps.py(59~80), Dockerfile, render.yaml, .dockerignore, .env.example, .gitignore, requirements.txt, webapp/static/screens/{login,work,patterns,settings,history}.html, _handoff/grader-v2-static/screens/login.html.

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성(disabled_sizes)·재확보 대기 |
| reviewer | Dockerfile:41 CMD | --port 8000 고정 → Render 주입 $PORT와 불일치 시 헬스체크 부팅차단 가능. `${PORT:-8000}` 폴백 권장 | ✅ 완료(developer 1차: shell form `${PORT:-8000}` 적용) |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-22 | debugger | 실OS 파일드롭 버그(document가드+좌표) | CDP검증·클릭회귀0 |
| 2026-06-22 | dev/test | 합성1 자동매핑(build-preset+preset교정) | 자동산출=정답값 0pt |
| 2026-06-22 | dev/test/rev | 합성2+3 cover/블리드+재단선1줄+OCG제거 | tester12/12·rev통과 |
| 2026-06-22 | dev | 배번 자간 수정(advance 0.6611 복원) | "20" 2-0분리·selftest PASS·verify2/2 |
| 2026-06-22 | dev | 배번 "1" lsb 보정(글자별 lsb) | 폰트일치·"11"자간차0.0·verify4/4 |
| 2026-06-25 | planner-architect | 합성 A+B 구현설계 | Piece.bg_cmyk fill(compose불변)+앞판dev 단일bleed. 7단계 |
| 2026-06-25 | dev | 합성 A+B 구현(5파일) | bg=None 하위호환·dict cover 3분기·bleed검산 설계일치·ast+pyc+스모크 통과 |
| 2026-06-25 | tester | 합성 A+B 독립검증(전사이즈12) | 6/6 PASS·verify12/12·본체색k×3·bleed정확일치·번호등방·bg=None바이트동등 |
| 2026-06-25 | reviewer | 합성 A+B 코드리뷰 | 통과 치명0(A재경로정확·불변준수·3분기안전). 주의1: job.py:732 svg_index가드 |
| 2026-06-25 | pm | 합성 A+B 커밋(2023837)+knowledge기록(decisions/errors)+scratchpad정리 | 미푸시1 |
| 2026-06-25 | planner-architect | 배포 Phase1 구현설계 | Docker+render.yaml+GS_BIN env+Supabase Auth게이트. 7단계, _handoff복사규칙·/health제외 명시 |
| 2026-06-25 | dev | 배포 Phase1 구현(14파일) | GS_BIN/PORT env+auth.py 토글+public_router(health/config무인증)+apiFetch래퍼5화면+Docker/render/dockerignore/env. 인증 A401/B401/C통과·앱레벨 health200(ON)/patterns401·회귀0 스모크통과. 비밀키grep 0건. ⚠️_handoff원본 fetch없어 static실수정(login만 복사) |
| 2026-06-25 | tester | 배포 Phase1 독립검증(8항목) | 합격·24/24 PASS. 치명(로컬회귀·health무인증) 엄격통과. 인증게이트7케이스·GS폴백4·비밀키0건·프런트apiFetch5화면·selftest PASS. Docker미설치=빌드SKIP(정적PASS: main:app import OK). ⚠️비차단: 로컬.env 키이름 코드와 불일치(배포시 안내) |
