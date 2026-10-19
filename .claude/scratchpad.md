# 작업 스크래치패드

## 현재 작업
- **2026-09-22 (Fable 5.1 세션)**: 실사용 개선 TOP7 — **#1·#2·#3(삭제)·#5·#6·#7 완료**, #4 는 정직 안내만(좌표 전송 미구현). + toast XSS·`_find_job_dir` 남의 ZIP 버그 수정. 커밋 0ae5f26·a2f2d08·2f316c8 (**미푸시 3**).
- **🚨 운영 서버 grader-v2-47gd.onrender.com 이 Render 에서 «suspended»(503, x-render-routing: suspend)** — 코드가 아니라 계정/플랜. 사장님이 Render 대시보드에서 확인 필요. 직원은 지금 접속 불가.
- **실사용 e2e(로컬, 실주문서 연세대 38행 + 실디자인 .ai)**: 파싱 38/38 정확 · V넥 12행 생성 14초 · 검사 전부 PASS · EPS 11/11 · 미리보기 육안 정상. **3XL 5명(13%)은 자산 결함으로 생성 불가**(skip 배너로 표시됨).
- **제안 3~7 전부 구현 완료**(③ 37498cc ④ a273ff2 ⑤ 8c29327 ⑥ 96df4d3 ⑦ 커밋 대기). 남은 것: ① Render 복구 ② 3XL.ai 재확보.

## 완료 기록 요약 (2026-10-20 정리)
- F10 재단 패턴 1~6단계(보기·서버 다시 만들기·다시 그레이딩·잠금·마커·들여오기) — 단계마다 독립 시험+보안 리뷰 통과 후 커밋 c5d82e7·4f84d70·a72d8c8·fc18f26·0cefb64(미푸시). 상세는 각 커밋 본문. 남은 것: Render 배포 후 리눅스 메모리(marker_vm_peak_mb)·느린 서버 배수(GRADER_MARKER_SLOW) 실측
- 2026-09-22 제안④~⑦·ZIP 주문요약 — 전부 커밋·배포(상세 git)

## TOP7 진행표 (2026-07-16 진단 · 2026-09-22 현재)
| # | 문제 | 축 | 위치 | 심각도 | 빈도 | 난이도 | 쉬운말 한줄 |
|---|------|----|------|--------|------|--------|-----------|
| 1 | 데모 가짜주문 48명이 초기 ORDER에 남아 미업로드 상태로 생성 가능 | 안정성 | work.html:325,1261 | 높음 | 매 작업 | 쉬움 | "주문서 안 올려도 넘어가져서 가짜 선수로 출력될 수 있어요" |
| 2 | GET /api/patterns 실패가 "패턴 0개"로 위장(콜드스타트 포함) | 안정성 | work:1354 / patterns:648 | 높음 | 매 첫로드 | 쉬움 | "서버가 느리거나 죽었을 때 '패턴 없음'처럼 보여 오해해요" |
| 3 | 패턴 수정·삭제 버튼이 눌러도 무반응(실기능 없음) | 편의성 | patterns:612~630 | 높음 | 잦음 | 중간 | "잘못 등록해도 화면에서 고치거나 지울 수가 없어요" |
| 4 | B/C 매핑·번호영역 편집이 저장 안 되는데 "저장됩니다"로 거짓안내 | 안정성 | patterns:344,1128 | 높음 | 매 등록 | 중간 | "화면에서 위치를 맞춰도 실제론 안 쓰이고 자동추정돼요(어긋남 위험)" |
| 5 | 콜드스타트 중 "서버 연결됨" 거짓표시+로딩안내 부재 | 편의성 | work:92 / patterns:235 | 중간 | 매 첫로드 | 쉬움 | "서버 깨는 30초 동안 연결된 척 보이고 빈 화면만 떠요" |
| 6 | 등록 실패 메시지 비일관/암호문(403·409·502 처리 누락) | 안정성 | patterns:1147~1150 | 중간 | 실패 시 | 쉬움 | "등록 실패해도 왜 실패했는지 알 수 없는 영어에러가 떠요" |
| 7 | 백업/복원 실패가 콘솔에만 남아 패턴 소실이 조용히 진행 | 안정성 | storage_backup 전반 | 중간 | 드묾·치명 | 중간 | "백업이 몰래 실패하면 재배포 때 패턴이 통째로 사라져도 몰라요" |

| # | 상태 |
|---|---|
| 1 | ✅ 0ae5f26 |
| 2·5·6 | ✅ a2f2d08 |
| 3 | ✅ 삭제만 2f316c8 (_trash 이동·Storage zip 잔존 경고). 수정은 "준비 중" |
| 4 | ✅ 좌표 실제 저장(제안⑤, 커밋 대기) — 2f316c8 정직 안내 → layout 전송 |
| 7 | ✅ backup-status/backup API + 관리자 UI 2f316c8 |

## 진행 현황 (완료 — 상세는 git + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 합성/글리프셋/합성A+B | 자동매핑·cover블리드·재단선·본체색채움 | ✅ 푸시 |
| 배포Phase1 / 계정·도움말 | Docker+Render+introspection admin게이트 / 4화면 계정메뉴 | ✅ 푸시 d0c4284·0b8f4e9 |
| **Drive 연동(백+프론트)** | gdrive+tree/patternfiles/from-drive + driveMode 트리/미리보기/등록 | ✅ 배포·실서버검증(트리·미리보기·등록) |
| **Drive SSL 수정** | httplib2 비스레드세이프→스레드로컬+재시도 | ✅ 4783a12 배포·실서버 무재발 |
| **패턴폴더 자동스캔** | GET /drive/scan(벌크2쿼리+캐시) + [자동찾기]탭 카드그리드 | ✅ f3b3257·25f490c 배포·실서버 74폴더 확인 |
| **즐겨찾기+자동분류** | pattern_meta(Supabase RLS) + 카테고리그룹/별표 + work필터 | ✅ 27b96db 미푸시·tester113·rev치명0 |
| **TOP7 #1** | 데모 가짜주문 48명 제거·미업로드 게이트 | ✅ 0ae5f26 (tester 5/5) |
| **TOP7 #2·#5·#6** | 콜드스타트 거짓표시 3종(목록 실패 구분·서버 핀 4상태·등록 실패 한글) | ✅ a2f2d08 (tester 59항목) |
| **TOP7 #3·#4·#7 + XSS + ZIP탐색** | 패턴 삭제(_trash)·정직 안내·백업 상태 UI·toast 이스케이프·_find_job_dir 정확일치 | ✅ 2f316c8 (tester 52/52) |

## 백로그 (차단 아님, 후속)
- **[Phase B: 등록패턴 파일 영속화]** Render 임시디스크→재배포 시 등록 preset 소실(현 repo커밋 2개만 잔존). 복구=재스캔등록(같은이름이면 메타 자동재적용). preset 20~88KB 소형→Supabase Storage 백업/복원 별도 승인단위로.
- **[즐겨찾기/분류 후속]** updated_by 프론트 미전송(SQL nullable이라 OK). 별표 이중클릭 debounce 없음(멱등). 카테고리 라벨 정규화 목록(PM_KNOWN_CATEGORIES) 조정 여지.
- **[Drive UI 후속]** DRIVE_SIZE_ORDER=백엔드 _SIZE_TOKENS 프론트복제(동기화 의무). glyph_file_id/reference_file_id 미노출(서버지원). 카드 **수정** 무동작(disabled "준비 중" — 수정 API 없음).
- **[패턴 삭제 후속 · 2026-09-22]** ~~Storage zip 잔존→재배포 부활~~ 제안⑥으로 해결(delete_backup+묘비). 남은 것: `_trash/` 영구 정리(TTL) 없음 · pattern_meta(즐겨찾기) 행은 삭제 시 안 지움 · 묘비 파일도 임시디스크라 창고 삭제가 끝내 실패한 채 재배포하면 부활(백업 상태 «창고에서 삭제» 로 재시도).
- **[_handoff 비대칭]** apiFetch·인증·계정·도움말·drive·pm(즐겨찾기) JS 전부 webapp/static에만 → _handoff 재복사 시 소실 위험(conventions.md).
- **[인증/자산]** auth.py 토큰캐시 만료정리. design_XL.ai 로컬부재. hide_design_cutline_layer V넥한정. 3XL.ai 재확보. job.py:732 _auto_bleed svg_index 가드.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적). 폴더+JSON(등록패턴). GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만, fetch/인증/계정/drive/pm JS는 static에만=비대칭). 커밋 전 py_compile(HTML은 vm.Script/new Function). **--workers 1**. 비밀키(SECRET·SERVICE_ROLE·GDRIVE_SA_JSON) 레포·백엔드·프런트 금지(프론트는 publishable만).

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→cover(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, cover_bleed preset 키 있을때만(없으면 contain=U넥 회귀0).
- **사이즈별 자동 블리드**: cover_bleed `{auto:true,k:1.3,min:1.0,max:1.12}` dict면 앞판 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1+k·dev,lo,hi)` 등방. float=단일·None=contain. XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036.
- **본체색 채움(흰틈)**: Piece.bg_cmyk 있으면 place_block이 클립(W n)직후·Do앞 폴리곤 **재경로** 후 device k+f(⚠️W n이 경로소비→재경로 필수). run_job: preset.body_fill([0.8,0.5,0,0.1])>detect_background_cmyk>None.
- **재단선**: 조각 SVG poly.points 시트좌표 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). draw_from="svg_polygon".
- **디자인 패턴선 두줄방지**: OCG OFF 무효→콘텐츠 BDC…EMC 삭제. hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=design_region. SVG 넥깊이로 앞(svg1)/뒤(svg0)/밴드(svg2).
- 글자주입: place_*(잉크bbox중앙)→조각 transform 감싸 extra_ops(클립밖,Do뒤). 번호: glyph_source면 글리프셋(advance0.6611·글자별lsb), 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체(아니면 3.4KB 흰화면). 정상 빈본체=88KB. **출력형식**: flatten Form그룹제거·페이지 /CS보존·eps2write. EPS 305KB.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2. 12사이즈(3XL disabled).
- **배포/GS/포트**: GS_BIN env 우선. state.DEFAULT_PORT=int(PORT env,8000). Dockerfile CMD `${PORT:-8000}`. render.yaml name=grader-v2(실URL=grader-v2-47gd). --workers 1.
- **인증(introspection)**: auth.py require_auth — GRADER_REQUIRE_AUTH 토글(로컬 미설정=통과·배포=1). httpx.get(SUPABASE_URL/auth/v1/user, apikey=PUBLISHABLE)→200이면 id·email·role(app_metadata.role)을 request.state. 60초캐시. **admin_required**(role!=admin→403)를 POST patterns·PUT settings·**전 Drive 엔드포인트**에. health·public-config 무인증. apiFetch: Bearer·**401만** 처리(403=r.ok=false). SECRET·JWT 제거. **admin 권한=Supabase app_metadata.role='admin'(사용자 SQL로 부여, grader Supabase begxkadzvcczdlewcmrj는 Claude MCP 접근불가)**.
- **Drive 백엔드**: gdrive.py(서비스계정 drive.readonly·supportsAllDrives·SA_JSON base64/JSON·**스레드로컬 서비스+전송에러재시도**[httplib2 비스레드세이프]·is_configured/list_children/download_file/get_file_meta/root_folder_id/**list_all_folders/list_all_pattern_files**). api.py: GET /drive/tree(1단계 지연) / GET /drive/folder/{id}/patternfiles(사이즈파서+미리보기) / POST /patterns/from-drive(_DriveUpload 어댑터→**기존 create_pattern 재사용**) / **GET /drive/scan?refresh(벌크 폴더+파일 2쿼리→부모그룹핑→_parse_size_from_filename 선별→루트스코프+경로 breadcrumb·TTL캐시300 Lock·admin)**. 전부 admin전용·미설정=200 configured:false·500 Config·502 Drive. _SIZE_TOKENS 정확토큰일치. **name contains 금지→endswith 서버필터**.
- **Drive 프론트(patterns.html)**: 목록/로컬등록/**#driveMode** 3모드. #driveMode 안 **[자동찾기|폴더트리] 탭**. 자동찾기=GET /drive/scan→**카드그리드**(발견전용). 트리=/drive/tree 지연로딩. 카드/폴더→renderDrivePreview(**panel 인자화**·기본 #drivePanel)=/patternfiles(DRIVE_SIZE_ORDER 인덱스정렬[문자열정렬 금지])→registerFromDrive(**activeDrivePanel 스코프**로 #driveName 중복방어·driveSaving 가드)→POST from-drive. classifyDriveRes 4갈래·경쟁조건 가드·driveEsc. 카드클릭→sessionStorage grader_selected_pattern→work 프리셀렉트. glyph_source→'글리프셋' badge.
- **즐겨찾기+자동분류(프론트, Supabase)**: 표 **pattern_meta{pattern_id PK,is_favorite,category,updated_by,updated_at}** RLS(authenticated SELECT 전체 / admin만 쓰기 `auth.jwt()->'app_metadata'->>'role'='admin'`). 프론트 직접 read/write(public-config→createClient publishable+세션JWT, 백엔드 0줄). patterns.html=카테고리 필터/그룹+별표(admin토글 upsert/전원읽기)+카테고리 select변경(admin)+즐겨찾기만보기. work.html step1=즐겨찾기 상단+카테고리 필터(읽기전용·선택흐름 무변경). 카테고리=드라이브 최상위폴더 캡처(registerFromDrive 성공 upsert)??이름파생(pmMatchKnownCategory)??미분류. 기존 render **감싸기**(원본 재대입·본문0변경·.pm-added 재부착 누수0). **degrade**(Supabase 미설정/실패→별표없음+파생카테고리, 목록·작업 정상). isAdmin=app_metadata.role.
- ⚠️ 함정(errors.md): viewBox통일·미리보기육안. 인접사이즈 좌표동일=자산결함. W n 경로소비→재경로. **배포 URL 혼동(Cannot GET=타인앱)**. **프론트 사이즈정렬=순서표 인덱스(문자열정렬 금지)**. **httplib2 스레드공유=SSL record layer failure→스레드로컬**. jsdom innerHTML 재직렬화 이스케이프 검증함정.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job·svg_normalize·order·flatten·eps·compose·pdfutil·verify·preview·grade. CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest.
- webapp/: main(루트→login)·auth(introspection+admin)·api(health·public-config 무인증 + patterns·settings·order·design·jobs·preview·zip·**drive tree/patternfiles/from-drive/scan[admin]**)·state·gdrive.py. static 4화면=apiFetch+계정메뉴+도움말. **patterns.html=목록/로컬등록/#driveMode(트리+자동찾기카드) + 즐겨찾기·카테고리(pattern_meta)**. work.html step1=즐겨찾기·카테고리 필터. login.html(supabase-js).
- 배포: Dockerfile·render.yaml(env: SUPABASE_URL·PUBLISHABLE·SECRET·GS_BIN·GRADER_REQUIRE_AUTH·GDRIVE_SA_JSON·GDRIVE_ROOT_FOLDER_ID). data/patterns/{농구_U넥_양면,농구_V넥_양면}. Supabase: auth + **pattern_meta 표(즐겨찾기/분류)**.

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·글리프셋·완성본. 폰트 HY헤드라인M.ttf. 로컬 GS gswin64c. **stiz-*.json(서비스계정 키)=gitignore됨(커밋금지)**.
- git: origin=cobby8/grader-v2, main. **미푸시 3(0ae5f26·a2f2d08·2f316c8, 2026-09-22)**. 미추적 .md 5개+google-drive-setup-guide.html(작업산출물 아님, 커밋제외).

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성·재확보 대기 |
| tester | webapp/static/screens/patterns.html regFailMsg(≈1180) | [TOP7 #6 회귀] 502/503/504 에서 body.error(서버 JSON, 예: from-drive "Drive 접근 실패: …")가 있어도 "서버가 깨어나는 중"으로 덮음 → 드라이브 권한 문제를 콜드스타트로 오안내. 수정안: body.error 있으면 그걸 우선, 없을 때(HTML 게이트웨이 응답)만 깨우는중 문구 | ✅ 완료 a2f2d08 (2026-10-15 재확인: 502+error→이유 그대로·HTML만→깨우는중) |
| tester | webapp/api.py `_manifest_table`(≈1290)·`_manifest_xlsx_bytes` | [수정 권장·회귀 아님] 주문요약 인젝션 — `=1+1` 이 CSV 그대로, xlsx 는 openpyxl 수식 셀('f'). 수정안: `=+-@\t\r` 접두 문자열에 `'` 접두 + xlsx `data_type='s'` | ✅ 완료 37498cc `_safe_cell` (2026-10-15 재확인: CSV·xlsx 모두 `'=1+1` 글자 셀) |
| reviewer | webapp/cad.py:628-630 `_engine_env` | [F10-2 중간] 빼기 목록(SUPABASE_/GDRIVE_/GOOGLE_)이라 ANTHROPIC_API_KEY 등 나머지 비밀이 일꾼에 넘어감 → 허용 목록(PATH·HOME·LANG·LC_*·TMP*·SYSTEMROOT·PYTHON*·PATTERN_ENGINE_*)으로 | ✅ 2026-10-19 재리뷰 확인(메모리는 아래 «실측» 줄로 이어짐) |
| reviewer | webapp/cad.py:646-657 | [F10-2 중간] 엔진 결과 `checks_bad`(검산 실패)를 안 보고 새 최신 버전으로 저장 → 비어 있지 않으면 저장 거절(또는 meta 에 경고 표시) | ✅ 2026-10-19 재리뷰 확인(메모리는 아래 «실측» 줄로 이어짐) |
| reviewer | cad.py:637-645 + Dockerfile | [F10-2 중간] 메모리: 일꾼 175~207MB(윈도우 실측)만 512MB 와 비교, 서버 본체+동시 합성 작업 합은 미측정 → Render 실측 + 엔진 중 합성 작업 막기(또는 일꾼 RLIMIT_AS) | ✅ 2026-10-19 재리뷰 확인(메모리는 아래 «실측» 줄로 이어짐) |
| reviewer | Dockerfile:19 · vendor ENGINE_VERSION.json | [F10-2 중간] 지문 시험이 빌드에서 안 돎(Dockerfile 에 시험 없음·런타임 검사 없음) + 사본 판이 `f4fb9def+dirty`(service.py 가 stizshop 에 미커밋) → stizshop 커밋 후 재동기화 + Dockerfile 에 `RUN python -m unittest tests.test_engine_vendor` | ✅ 2026-10-19 재리뷰 확인(메모리는 아래 «실측» 줄로 이어짐) |
| reviewer | engine_child/sitecustomize.py:28-45 · cad.py:625 | [F10-2 재리뷰 중간] RLIMIT_AS 1024MB·oom_score_adj 의 리눅스 실측 기록 없음 + 걸렸는지 결과(GRADER_ENGINE_GUARD)를 아무도 안 읽음(실패해도 조용함) → 안전띠가 stderr 로 한 줄 남기고 engine_run 에 guard·VmPeak 기록, 배포 직후 1회 다시 만들기로 확인 | 대기 |
| reviewer | 커밋 묶음 | [F10-2 재리뷰 중간] vendor/·webapp/engine_child/·tests/test_engine_vendor.py·tests/test_cad_rebuild.py·scripts/sync_pattern_engine.py 가 미추적(??) — vendor 빠지면 빌드 RUN 실패(배포 막힘), engine_child 빠지면 안전띠 없이 조용히 돎 → 함께 커밋(다른 ?? 문서·data/patterns 새 폴더는 섞지 말 것) | 대기 |
| tester | cad.py `_rebuild_thread` · state.HeavyGate.exclusive_use | [권장·회귀 아님] 엔진의 «합성 끝나기 기다림» 에 상한 없음 — 합성 하나가 멈추면 엔진+뒤 합성 전부 대기. 수정안: 기다림 상한(예 10분) 넘으면 엔진 작업 error·waiting_excl 해제 | ✅ 2026-10-20 리뷰 확인(600초·notify_all) |
| reviewer | cad.py restore_missing_with_token (`_sb_list(f"{sid}/v{ver}/") or []`) | [F10-3·5 중간] 버전 폴더 목록 읽기 실패(None)면 빈 목록으로 보고 lock·rules 를 건너뛴 채 복원 → 재배포 뒤 «공장 보냄» 잠금이 조용히 풀림. 수정: None 이면 ValueError 로 그 버전 복원 보류 + meta.rules_sha256 있는데 rules 없으면 보류 | 대기 |
| reviewer | cad.py `_regrade_thread`(저장) · `_store_from_engine` 직전 | [F10-3·5 중간] 잠금 확인이 요청 때만 — 저장 1분 사이 그 판을 잠그면 잠긴 판에서 v n+1 이 생김. 수정: 저장 직전 `_lock_info(style_id, from_ver)` 다시 보고 있으면 실패 | 대기 |
| reviewer | cad.py export_files | [F10-5 중간] 고른 파일을 메모리(BytesIO)에 다 담음 — 상한 200MB·직원 누구나·HEAVY 게이트 밖 → 엔진과 겹치면 512MB 위험. 수정: 임시파일(SpooledTemporaryFile/NamedTemporaryFile)+FileResponse 또는 합계 상한을 실측 크기(현 최대 zip 6MB) 맞춰 낮춤 | 대기 |
| reviewer | 배포 순서 | [F10-3·5 배포 차단] ENGINE_VERSION.json dirty_files 2개 → Dockerfile RUN test_engine_vendor 실패. stizshop 엔진 2파일+test_regrade 먼저 커밋 → sync 재실행 → grader 커밋(tests/test_cad_regrade.py ?? 포함) | 대기 |
| tester | webapp/static/screens/cad.html loadRules(≈867) | [F10-3 화면] 그레이딩 탭이 규칙만 읽히면 직원에게도 보임(보기 전용). 요구는 «관리자에게만» — `!G.rules0 \|\| !S.canUpload` 로 숨길지, 직원 보기 허용이 의도인지 PM 결정 | 대기 |
| reviewer | stizshop service.py:99 · marker.py:767-788 | [F10-4 높음] 벌수 상한 200 근거 없음 — 14벌 quick 379MB(+서버 151 = 512 초과)·28벌 617MB/73초, budget 은 ①②⑥ 못 막아 실상한 1200초 동안 합성 정지. 수정: Render 실측 기반 서버 상한(예 10~12벌·초과 quick 강제/거절) | 대기 |
| reviewer | cad.py:1346 · engine/order.py:483 | [F10-4 높음] xlsx 빈 행 폭탄 4.8KB→248MB(서버 프로세스·async 안이라 루프 정지). 수정: iter_rows(max_row·max_col 상한)+zip 풀린 크기 검사+스레드풀 | 대기 |
| reviewer | 배포 순서 | [F10-4 배포 차단] ENGINE_VERSION dirty service.py → stizshop 커밋→sync→grader 커밋(test_cad_marker.py·vendor marker.py ?? 포함) | 대기 |
| reviewer | cad.py:1287-1301 · 큐 858-880 | [F10-4 중간] AS 1536 은 512MB 방어 아님(oom_adj 리눅스 실측 필요)·운영자 값 max()로 덮음 / 대기열 3칸 관리자와 공유·사람별 제한·취소 없음 | 대기 |
| tester | webapp/cad.py order_counts · engine/order.py | [F10-4] 하의만 산 줄 누락: 양식③ 이름·배번·상의 빈 «하의만» 줄은 parse_order 가 버림 · 양식① 배번 없는 하의만 줄에서 parse_order 가 멈춰 뒤 사람 전부 누락(경고 없음) → 하의 벌수가 조용히 적게 나옴 | 대기 |
| tester | tests/test_cad_marker.py | [F10-4 낮음] 주문서 업로드가 실제 data/uploads 에 남음(매 회 8개) — state.UPLOADS_DIR 임시 폴더로 패치 | 대기 |
| tester | 기본 탐색(서버 설정 jobs1·120초) | [F10-4 결정] 가스 상의 8벌에서 time_budget_hit — «빠르게»와 같은 길이를 4배 시간에, 결과가 기계 속도에 좌우. 예산·기본값 PM 판단 | 대기 |
| tester | webapp/cad.py `_order_qty` | [F10-4 중간] 수량 칸 후보에 «비고» 가 들어가 자유 글자의 숫자를 벌수로 읽음 — 3명 주문서에 비고 «11번으로 변경» → 상의 M 11벌·하의 M 11벌(경고 없음). «2024 우승기념»→2024 · «010-1234-5678»→10 · «5XL 요청»→5. 수정안: «N장/N벌/N개» 또는 숫자만인 칸만 수량으로, 그 밖 숫자는 무시+경고 | 대기 |
| tester | webapp/cad.py `_order_qty` | [F10-4 낮음] «상의2장» 만 적힌 줄은 하의 0벌 — 하의 사이즈가 차 있어도 빠짐(«하의 1장»도 상의 0). 하의 칸이 차 있으면 1로 보는지 PM 판단 | 대기 |
| tester | stizshop service.py admit_marker | [F10-4 정보] 기본값(느림 2·180초)에선 시간이 먼저 막혀 forced_quick 이 1~200벌 어디서도 안 생김 — «빠르게 강제» 단계는 사실상 죽은 길(직원은 원래 빠르게). 문구·시험 기대만 맞출 것 | 대기 |

## 작업 로그 (최근 10건)

