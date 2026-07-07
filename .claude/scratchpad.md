# 작업 스크래치패드

## 현재 작업
- **상태**: ✅ **즐겨찾기 + 자동분류(폴더 트리 기준) 완성·커밋**(feat 27b96db·docs 685b745, tester 113assert/0·rev 치명0). Supabase pattern_meta에 프론트 직접 read/write(백엔드 키리스). 미푸시 2.
- **현재 담당**: pm. **⏳ 남은 것**: (1)사용자 Supabase SQL 실행(pattern_meta 표+RLS — 정확 SQL은 커밋 685b745 docs/decisions 또는 아래 참고) (2)git push→재배포 (3)라이브 검증: 비관리자 쓰기 막힘·관리자 쓰기 성공·별표/카테고리 저장(updated_by nullable 확인). 로컬은 GDRIVE+Supabase 없어 degrade만.
- **최근 완료(2026-07-06~07, 상세는 git+아래 작업로그)**: Drive Phase1(백엔드)+Phase2(프론트 트리/미리보기/등록)+배포+admin권한(Supabase role) → SSL동시성수정(스레드로컬) → **패턴폴더 자동스캔**(GET /drive/scan+카드그리드) → **즐겨찾기+자동분류**. 배포 URL grader-v2-47gd.onrender.com. 로컬 127.0.0.1:8000 병행.
- **카테고리 라벨 정책(사용자 확인 여지)**: 최상위폴더/이름을 pmMatchKnownCategory로 "0.농구→농구" 정규화. 원하는 라벨 다르면 PM_KNOWN_CATEGORIES 조정. 관리자 override 가능.

## 진행 현황 (완료 — 상세는 git + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 합성/글리프셋/합성A+B | 자동매핑·cover블리드·재단선·본체색채움 | ✅ 푸시 |
| 배포Phase1 / 계정·도움말 | Docker+Render+introspection admin게이트 / 4화면 계정메뉴 | ✅ 푸시 d0c4284·0b8f4e9 |
| **Drive 연동(백+프론트)** | gdrive+tree/patternfiles/from-drive + driveMode 트리/미리보기/등록 | ✅ 배포·실서버검증(트리·미리보기·등록) |
| **Drive SSL 수정** | httplib2 비스레드세이프→스레드로컬+재시도 | ✅ 4783a12 배포·실서버 무재발 |
| **패턴폴더 자동스캔** | GET /drive/scan(벌크2쿼리+캐시) + [자동찾기]탭 카드그리드 | ✅ f3b3257·25f490c 배포·실서버 74폴더 확인 |
| **즐겨찾기+자동분류** | pattern_meta(Supabase RLS) + 카테고리그룹/별표 + work필터 | ✅ 27b96db 미푸시·tester113·rev치명0 |

## 백로그 (차단 아님, 후속)
- **[Phase B: 등록패턴 파일 영속화]** Render 임시디스크→재배포 시 등록 preset 소실(현 repo커밋 2개만 잔존). 복구=재스캔등록(같은이름이면 메타 자동재적용). preset 20~88KB 소형→Supabase Storage 백업/복원 별도 승인단위로.
- **[즐겨찾기/분류 후속]** updated_by 프론트 미전송(SQL nullable이라 OK). 별표 이중클릭 debounce 없음(멱등). 카테고리 라벨 정규화 목록(PM_KNOWN_CATEGORIES) 조정 여지.
- **[Drive UI 후속]** DRIVE_SIZE_ORDER=백엔드 _SIZE_TOKENS 프론트복제(동기화 의무). glyph_file_id/reference_file_id 미노출(서버지원). 카드 수정/삭제 무동작(서버 삭제API 없음). toast 헬퍼 미이스케이프(savePattern 관례·admin·저위험).
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
- git: origin=cobby8/grader-v2, main. **미푸시 2(즐겨찾기 feat+docs)**. 미추적 .md 5개+google-drive-setup-guide.html(작업산출물 아님, 커밋제외).

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성·재확보 대기 |
| tester | stiz-*.json 키 | gitignore 누락(유출위험) | ✅해결 07-06: .gitignore stiz-*.json 추가 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-07-07 | dev/tester/rev | 즐겨찾기+자동분류 프론트(patterns/work, Supabase pattern_meta 직접) | feat 27b96db·tester113assert/0·rev치명0. degrade·트리회귀0·work선택흐름무변경·별표 admin쓰기/전원읽기·카테고리=폴더트리최상위 |
| 2026-07-07 | planner-architect | 즐겨찾기+자동분류 설계 | 프론트direct Supabase+RLS·단일표 pattern_meta·카테고리 폴더트리·파일영속화 Phase B 분리 |
| 2026-07-07 | dev/tester/rev | 패턴폴더 자동스캔 프론트([자동찾기]탭+카드그리드) | 25f490c·tester69/69·트리회귀0·입력칸중복0. 배포 실서버 74폴더 카드 확인 |
| 2026-07-07 | dev/tester/rev | 패턴폴더 자동스캔 백엔드(GET /drive/scan 벌크2쿼리+캐시) | f3b3257·tester68/68·회귀0·추가만271 |
| 2026-07-07 | planner-architect | 자동스캔 설계 | 벌크2쿼리 발견전용·등록은 기존 정확경로·name contains 금지 |
| 2026-07-06 | debug/tester/rev | Drive SSL 동시성 수정(gdrive 스레드로컬+재시도) | 4783a12·tester15/15·rev치명0. 배포 실서버 5단계깊이 무재발. +키 gitignore ac785a5 |
| 2026-07-06 | pm | Drive 연동 배포+admin권한(Supabase role=admin 사용자SQL) | 실서버 트리·미리보기·등록 동작. push 59d0417 |
| 2026-07-06 | dev/tester/rev×4 | Drive Phase2 프론트 4단계(카드배지/트리/미리보기/등록) | tester 47건·rev치명0·커밋 322cea0~f69f937 |
| 2026-07-06 | pm(workflow×8) | 의뢰서 대비 Drive 진척 코드대조 | 백엔드done·프론트미착수 확인→Phase2 착수 |
| 2026-07-01 | pm | Drive Phase1 백엔드(1a~1d) | tree/patternfiles/from-drive·파서·mock검증·커밋4 |
