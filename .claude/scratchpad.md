# 작업 스크래치패드

## 현재 작업
- **상태**: ✅ **Google Drive 패턴 연동 — Phase 2(프론트 UI) 완결**. 1a~1d 백엔드(검증 재확인 2026-07-06 8영역 done) + Phase 2 프론트 4단계 전부 구현·검증·커밋. 각 단계 tester+reviewer 병렬 통과(치명 0).
- **현재 담당**: pm (Phase 2 완료 보고 + 마무리). 다음은 사용자 결정 대기.
- **목표**: 패턴 관리에서 ①공유드라이브 폴더 트리 탐색 ②폴더선택→사이즈미리보기→등록(기존 create_pattern 재사용) ③등록패턴 카드노출·선택. 서버가 서비스계정으로 Drive 읽기전용.
- **Phase 2 커밋(미푸시)**: 2-1 카드 glyphset배지+클릭이동 `322cea0`(tester7/7) · 2-2 driveMode+트리 지연로딩 `30a18f9`(8/8) · 2-3 우측 사이즈미리보기 `e16314a`(12/12) · 2-4 from-drive 등록연결 `f69f937`(20/20). 전부 rev 치명0.
- **⏳ 남은 것(Phase 3)**: (1) **사용자 Google Cloud 설정** — 서비스계정 JSON키 발급 + 드라이브 폴더를 서비스계정 이메일에 공유 + Render env 2개(GDRIVE_SA_JSON, GDRIVE_ROOT_FOLDER_ID). (2) **git push** → Render 자동 재배포. (3) 실드라이브 왕복(다운로드→변환→카드노출) 검증. **로컬 GDRIVE 미설정이라 현재 스텁으로 전 분기 결정론 검증만 완료** — 실드라이브 검증은 env 설정 후.

## (보류) 실사용 검증 — 배포 정상
- 배포 정상: URL=**https://grader-v2-47gd.onrender.com**. 로그인·work 렌더 OK(cobby8@stiz.kr). ⚠️ 브라우저 file_upload가 host 경로 차단→디자인 .ai 자동업로드 불가. 실5단계 검증은 사용자 직접 업로드 필요.

## 진행 현황 (완료 — 상세는 git + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 합성1·2·3 / 배번 글리프셋 / 합성 A+B | 자동매핑·cover블리드·재단선·본체색채움 | ✅ tester·rev 통과 |
| 배포 Phase1 | Docker+Render+introspection 인증+admin게이트 | ✅ 푸시 d0c4284 |
| 계정/도움말 모달 | 4화면 계정메뉴·비번변경·로그아웃·도움말 | ✅ 푸시 0b8f4e9 |
| **Drive Phase 1(백엔드)** | gdrive.py + tree/patternfiles/from-drive + 사이즈파서 | ✅ 커밋4(미푸시)·mock검증·기존영향0 |
| **Drive Phase 2(프론트)** | 카드배지+클릭 / driveMode+트리 / 미리보기 / 등록연결 | ✅ 커밋4(미푸시)·tester 47건·rev 치명0 |

## 백로그 (차단 아님, 후속)
- **[Drive toast 이스케이프]** registerFromDrive의 성공/경고 toast가 drive_warnings 파일명·서버 error를 innerHTML raw 주입(3단계 미리보기는 driveEsc, 4단계 토스트는 안 함=비대칭). savePattern과 동일 관례·admin전용·저위험. 향후 toast 헬퍼 자체에 이스케이프 넣으면 근본 해소.
- **[Drive UI 후속]** DRIVE_SIZE_ORDER는 백엔드 _SIZE_TOKENS 프론트 복제본(주석 동기화 의무) — 사이즈 목록 확장 시 양쪽 수정. 폴더 글리프셋/완성본 파일 콕집어 지정(glyph_file_id/reference_file_id) 미노출(서버는 지원). 카드 수정/삭제 버튼 무동작(서버 삭제 API 없음).
- **[계정 후속]** 비번변경 버튼 더블클릭 disabled 방어. toast 지속시간 화면별 통일.
- **[_handoff 비대칭]** apiFetch·인증·계정·도움말·drive JS 전부 webapp/static에만 → _handoff 재복사 시 소실 위험(conventions.md).
- **[인증 후속]** auth.py 토큰캐시 만료정리. login.html getSession 핑퐁(극저).
- **[배포 Phase 2~3]** Storage(업로드/산출물 영속)+Postgres/RLS. 현재 Render 임시디스크(재배포시 소실).
- **[자산/합성]** design_XL.ai .gitignore 로컬부재. hide_design_cutline_layer V넥 한정. 재단선 .ai 재출력/3XL.ai 재확보. job.py:732 _auto_bleed svg_index 가드.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만, 단 fetch/인증/계정/도움말/drive JS는 static에만=비대칭). 커밋 전 ast.parse/py_compile(HTML은 vm.Script/new Function 파싱). **--workers 1 유지**. 비밀키(SECRET·GDRIVE_SA_JSON) 레포·프런트 금지.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→cover(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, cover_bleed preset 키 있을때만(없으면 contain=U넥 회귀0).
- **사이즈별 자동 블리드**: cover_bleed가 `{auto:true,k:1.3,min:1.0,max:1.12}` dict면 앞판 기준 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1+k·dev,lo,hi)` 단일값→전 조각 등방. float=단일·None=contain. XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036.
- **본체색 채움(흰틈)**: Piece.bg_cmyk(기본None) 있으면 place_block이 클립(W n)직후·Do앞 폴리곤 **재경로** 후 device k+f 채움(⚠️W n이 경로소비→재경로 필수). run_job: preset.body_fill([0.8,0.5,0,0.1]) > detect_background_cmyk > None.
- **재단선**: 조각 SVG poly.points를 시트좌표 그대로 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). draw_from="svg_polygon".
- **디자인 패턴선 두 줄 방지**: OCG OFF는 Form 합성에 무효 → 콘텐츠 BDC…EMC 삭제. hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=design_region. SVG 넥깊이로 앞(svg1)/뒤(svg0)/밴드(svg2).
- 글자주입: place_*(잉크bbox 중앙정렬)→조각 transform 감싸 extra_ops(클립밖, Do뒤). 번호: glyph_source 있으면 글리프셋(advance0.6611·글자별lsb), 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체 포함(아니면 3.4KB 흰화면). 정상 빈본체=88KB.
- **출력형식**: flatten Form투명도그룹 제거·페이지그룹 /CS 보존. eps2write. EPS 305KB 벡터.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2. 12사이즈(3XL disabled).
- **배포/GS/포트**: GS경로=eps.find_ghostscript GS_BIN env 우선(→settings→Windows절대→PATH). state.DEFAULT_PORT=int(PORT env,8000). Dockerfile CMD `${PORT:-8000}`. render.yaml name=grader-v2(이름선점, 실URL=grader-v2-47gd). --workers 1.
- **인증(introspection)**: auth.py require_auth — GRADER_REQUIRE_AUTH 토글(로컬 미설정=통과·배포=1=검증). ON이면 httpx.get(SUPABASE_URL/auth/v1/user, apikey=PUBLISHABLE, Bearer)→200이면 id·email·role을 request.state, 비200/예외=401. 토큰별 60초 캐시. **admin_required**(role!=admin→403, 토글OFF통과)를 POST /api/patterns·PUT /api/settings·**전 Drive 엔드포인트**에. /api/health·/api/public-config 무인증. 프런트 apiFetch: Bearer 부착·**401만** 처리(403은 r.ok=false)·401시 세션clear+login. 루트/→login.html. SECRET·JWT 전부 제거.
- **Drive 백엔드(webapp)**: gdrive.py(서비스계정 drive.readonly·supportsAllDrives·SA_JSON base64/JSON 둘다·is_configured/list_children/download_file/get_file_meta/root_folder_id). api.py: GET /api/drive/tree(1단계 지연로딩·folder먼저정렬) / GET /drive/folder/{id}/patternfiles(사이즈파서+미리보기, files+warnings) / POST /api/patterns/from-drive(다운로드→_DriveUpload 어댑터→**기존 create_pattern 재사용**·JSON body {folderId,name,base_size?}·성공 dict {ok,pattern_id,pieces,active_sizes,glyph_source,warnings,drive_warnings}). 전부 admin전용, 미설정=200 {configured:false,message}, 500 DriveConfigError·502 DriveError. 사이즈파서 _SIZE_TOKENS=[5XS,4XS,3XS,2XS,XS,S,M,L,XL,2XL,3XL,4XL,5XL,6XL,7XL] 정확토큰일치(부분매칭 금지).
- **Drive 프론트(patterns.html, Phase2)**: 목록/로컬등록과 형제인 **#driveMode**(상호배타, backToList가 셋 다 제어). 좌 #driveTree=/api/drive/tree 지연로딩(폴더 펼침마다 자식 호출·loaded 성공시만 캐시·파일=잎). 우 renderDrivePreview(driveSelectedFolder{id,name})=/patternfiles(사이즈칩 **DRIVE_SIZE_ORDER 인덱스정렬**[문자열정렬 금지·백엔드 _SIZE_TOKENS 복제]·경고 alert--warn·#driveName 자동제안[폴더명 trim+공백1]·#driveBaseSize XL기본). #btnDriveRegister→registerFromDrive: JSON POST from-drive(**driveSaving 재진입가드**·성공 pass토스트+reloadPatterns+backToList·실패 403/400/409/500/502/configured:false/네트워크). classifyDriveRes 4갈래. **경쟁조건 가드**(응답 도착 시 driveSelectedFolder.id 일치할 때만 렌더). 카드 클릭→sessionStorage `grader_selected_pattern`→work.html 프리셀렉트, glyph_source→'글리프셋' badge--info. 외부값 driveEsc(단 toast 헬퍼는 미이스케이프=savePattern 관례, 백로그).
- ⚠️ 함정(errors.md): 변환 viewBox통일·미리보기육안. 인접사이즈 좌표동일=자산결함. W n 경로소비→fill 재경로. 프런트 인증게이트=루트→login+apiFetch401가드. **배포 URL 혼동(Cannot GET=Express=타인앱, 이름선점)**. **프론트 사이즈 정렬은 문자열정렬 금지→순서표 인덱스**(2XL이 XL 앞 오탐).

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job·svg_normalize·order·flatten·eps·compose·pdfutil·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main(루트→login)·auth(introspection+admin_required)·api(health·public-config 무인증 + patterns·settings[admin]·order·design·jobs·preview·zip·기록·**drive tree/patternfiles/from-drive[admin]**)·state(PORT env)·gdrive.py. static 4화면(work/patterns/history/settings)=apiFetch+계정메뉴+도움말모달. **patterns.html=목록/로컬등록/#driveMode(트리+미리보기+from-drive) 3모드**. login.html(supabase-js).
- 배포: Dockerfile·render.yaml(env: SUPABASE_URL·PUBLISHABLE·SECRET·GS_BIN·GRADER_REQUIRE_AUTH·**GDRIVE_SA_JSON·GDRIVE_ROOT_FOLDER_ID sync:false**)·.env.example. 데이터: data/patterns/{농구_U넥_양면,농구_V넥_양면}.

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋·_완성본. 폰트 HY헤드라인M.ttf. 로컬 GS gswin64c.
- git: origin=cobby8/grader-v2, main. **미푸시 8**(Drive Phase1 4 + Phase2 4). 미추적 .md 5개(의뢰서/사용설명서/직원사용안내/테스트가이드북 등 — 작업산출물 아님, 커밋 제외 유지).

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성·재확보 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-07-06 | pm | Drive Phase2 완결 — 프론트 4단계 커밋(322cea0/30a18f9/e16314a/f69f937) | 트리→미리보기→등록 흐름 완성. 미푸시8. scratchpad 압축(324→~100줄) |
| 2026-07-06 | dev/tester/rev | Phase2 4단계 — from-drive 등록연결(registerFromDrive) | tester20/20·rev치명0. 검증→진행→성공/실패5갈래·driveSaving가드·회귀0 |
| 2026-07-06 | dev/tester/rev | Phase2 3단계 — 우측 사이즈 미리보기(/patternfiles) | tester12/12·rev치명0. 표준정렬(문자열함정회피)·이름자동제안·경쟁가드 |
| 2026-07-06 | dev/tester/rev | Phase2 2단계 — driveMode+폴더트리 지연로딩 | tester8/8·rev치명0. 3화면 상호배타·configured:false 4갈래·캐시·회귀0 |
| 2026-07-06 | dev/tester/rev | Phase2 1단계 — 카드 glyphset배지+클릭→work 프리셀렉트 | tester7/7·rev치명0. 실브라우저 클릭검증·회귀0 |
| 2026-07-06 | planner-architect | Drive Phase2 프론트 설계 | 독립 #driveMode 레이아웃A·4단계·decisions기록 |
| 2026-07-06 | pm(workflow×8) | 의뢰서 대비 Drive 작업 진척 코드대조 검증 | 백엔드 done·프론트 미착수·미푸시 확인→Phase2 착수 결정 |
| 2026-07-01 | pm | Drive Phase1 백엔드 완결(1a~1d) | tree/patternfiles/from-drive·파서12/12·mock검증·커밋4·기존영향0 |
| 2026-06-26 | dev/test/pm | introspection 인증+계정+도움말 4화면 | tester36/36·8/8·84/84·푸시 완료 |
| 2026-06-29 | pm | 배포본 접속검증 | 실URL grader-v2-47gd 확정·타인앱 이름선점 발견 |
