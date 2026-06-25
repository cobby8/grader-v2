# 작업 스크래치패드

## 현재 작업
- **요청**: 인터넷 배포 Phase 1 — Docker 컨테이너화 + Render + Supabase Auth 로그인 게이트.
- **상태**: ✅ **완료·커밋**(ef33874). tester24/24 합격·reviewer 조건부통과 치명0·되돌림1(PORT)해결. **미푸시 2개**(합성A+B, 배포Phase1). 배포하려면 푸시 필요.
- **현재 담당**: pm
- **⚠️ 배포 전 사용자 액션**: ①푸시 ②Supabase(이메일로그인+키4개) ③Render(GitHub연결→env입력→배포). **Render env 키 이름은 코드가 읽는 정확한 이름으로**: SUPABASE_URL·SUPABASE_ANON_KEY·SUPABASE_SERVICE_ROLE_KEY·SUPABASE_JWT_SECRET (로컬 .env의 PUBLISHABLE/SECRET/JWKS 이름과 다름!).

## 진행 현황 (완료 — 상세는 git 히스토리 + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 웹앱1~5 | FastAPI 풀스택(order/design/jobs비동기/기록/등록/설정)+run.bat | ✅ rev종합 치명0 |
| 화면버그+실OS드롭 | both/EPS·드래그앤드롭·헤더·3XL칩·푸터 / document가드+좌표 | ✅ tester9/9·debugger |
| 합성1·2·3 | 자동매핑·cover+블리드·재단선1줄(svg_polygon)·패턴선 OCG제거 | ✅ tester12/12·rev통과 |
| 배번 글리프셋 | 자간(advance 0.6611)+"1" lsb 보정 | ✅ selftest PASS·verify4/4 |
| 합성 A+B | 본체색 채움(Piece.bg_cmyk)+사이즈별 자동블리드(auto_bleed) | ✅ tester6/6·rev통과 |
| **배포 Phase 1** | Docker+Render+Supabase Auth 게이트(GRADER_REQUIRE_AUTH 토글) | ✅ tester24/24·rev조건부통과 |

## 백로그 (차단 아님, 후속)
- **[배포 Phase 2~3]** Storage(업로드/산출물 영속) + Postgres/RLS(기록 DB). 현 Phase1은 Render 임시디스크(재배포시 소실).
- **[_handoff 비대칭]** fetch/인증 코드가 webapp/static에만 있음 → _handoff 재복사 시 인증 통째 소실 위험(conventions.md 기록). login.html만 원본↔복사 동일.
- **[U넥 자산]** 농구_U넥_양면 design_XL.ai .gitignore 자산이라 로컬 부재 → 합성 A+B full job 시각회귀 미실시(코드 동등성으로 본질 검증). 자산 확보 시 권장.
- **[합성 일반화]** hide_design_cutline_layer는 V넥 BDC구조·"패턴선"·page0 한정 → 신규 디자인 온보딩 체크리스트. 재단선 보존체크 과다(두줄) 못 거름(시각보완).
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·_JOBS TTL 정리. progress 콜백.
- **[디자이너 대기]** 재단선 PDF포함 .ai 재출력 / 올바른 3XL.ai 재확보(현 disabled).
- **[job.py:732]** _auto_bleed 직전 front svg_index 범위가드 부재(행 try/except엔 잡힘, 비치명).

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). CLI/curl 단독검증. GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만, 단 fetch/인증코드는 static에만=비대칭). 커밋 전 ast.parse/py_compile. **--workers 1 유지**(_JOBS 인메모리). 비밀키 레포 금지.

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
- **배포/인증(Phase1)**: GS경로=eps.find_ghostscript 맨앞 GS_BIN env 우선(없으면 settings_path→Windows절대→PATH 폴백, 로컬회귀0). 인증=webapp/auth.py require_auth, **GRADER_REQUIRE_AUTH 토글**(로컬 미설정=무인증 통과·배포 =1=JWT HS256+aud 검증·실패401). **/api/health·/api/config는 public_router(무인증)** — health 막으면 Render 부팅실패. 나머지 /api/* 전역 Depends(require_auth). 프런트 apiFetch 래퍼(Authorization부착·401리다이렉트·FormData boundary보존·preview/zip blob). /api/config로 공개키(URL·ANON) 런타임 주입. 비밀키 env 전용. Dockerfile CMD shell form `${PORT:-8000}`(Render $PORT 호환). --workers 1.
- ⚠️ 변환함정(errors.md): 조각수+verify만으론 부족→viewBox통일·양수·미리보기 육안. 인접사이즈 좌표동일=자산결함. 브라우저 드롭은 document가드+좌표판정.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job(정밀배치+cover/auto_bleed+본체색채움+재단선polygon+OCG제거+disabled+out_format)·svg_normalize·order(①②③STIZ)·flatten(+detect_background_cmyk)·eps(+GS_BIN env)·compose(+Piece.bg_cmyk)·pdfutil(place_block+bg_cmyk fill)·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main(public/api 라우터 분리+인증)·auth(require_auth)·api(health·config무인증 + patterns·settings·order/parse·design/check5·jobs비동기·preview·zip·기록·등록)·state(PORT env)·run.py·run.bat. static=_handoff 복사본(단 fetch/인증코드는 static에만). login.html(supabase-js).
- 배포: Dockerfile·render.yaml·.dockerignore·.env.example(루트). 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면}. data/{jobs,uploads}/·settings.json(.gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋·_완성본.
- 주문서: C:/Users/user/Desktop/새 폴더/260213_…추가주문서.xlsx. 폰트 HY헤드라인M.ttf. 로컬 GS C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- 테스트 산출물 `_abtest/`·`_glyphtest/`는 .gitignore. cowork PNG: _abtest/out_allsize/preview/{5XS,XL,M,5XL}_20_*.png.
- 로컬 .env 존재(git/docker 제외=안전). 단 키 이름이 코드 기대와 다름(배포 시 정확한 이름으로 Render 등록 필요).
- git: origin=cobby8/grader-v2, main. **미푸시 2개**(합성A+B, 배포Phase1).

## 구현/테스트/리뷰/기획설계
(완료 — 상세 git 히스토리 + knowledge. 배포 Phase1: tester24/24 합격·reviewer 조건부통과 치명0, PORT 폴백 되돌림1 해결)

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer | Dockerfile PORT | --port 8000 고정→Render $PORT 미스매치 | ✅ 완료(shell form ${PORT:-8000}) |
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성(disabled_sizes)·재확보 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-22 | dev | 배번 자간+lsb 보정 | selftest PASS·verify |
| 2026-06-25 | planner-architect | 합성 A+B 구현설계 | Piece.bg_cmyk fill+앞판 단일bleed |
| 2026-06-25 | dev/test/rev | 합성 A+B 구현·검증 | tester6/6·rev치명0·bleed cowork일치·푸시완료 |
| 2026-06-25 | pm | 합성 A+B 커밋·회고·정리 | 푸시완료(6d5dd9c) |
| 2026-06-25 | planner-architect | 배포 Phase1 설계 | GS env끼움점·인증/api/health제외·_handoff복사·로컬토글 |
| 2026-06-25 | dev | 배포 Phase1 구현(신규8+수정8) | Docker·render·auth·login·apiFetch. GRADER_REQUIRE_AUTH 토글. ast/grep통과 |
| 2026-06-25 | tester | 배포 Phase1 독립검증 | 24/24 합격. 로컬회귀0·인증7케이스·health무인증·비밀키0·selftest PASS |
| 2026-06-25 | reviewer | 배포 Phase1 리뷰 | 조건부통과 치명0. 주의1=Dockerfile PORT. 비밀키0·JWT견고·끼움점정확 |
| 2026-06-25 | dev | 되돌림1: Dockerfile PORT 폴백 | exec→shell form ${PORT:-8000}, Render $PORT 호환 |
| 2026-06-25 | pm | 배포 Phase1 커밋(ef33874)+scratchpad정리 | 미푸시2(배포 위해 푸시 필요) |
