# 작업 스크래치패드

## 현재 작업
- **상태**: ✅✅ **Google Drive 패턴 연동 — 전 과정 완료**(백엔드1a~1d + 프론트2-1~2-4 + 푸시·배포·admin권한). 2026-07-06 사용자 "완료" 보고. 의뢰서 완료기준(트리탐색→미리보기→등록→카드) 실서버 동작.
- **현재 담당**: pm → debugger (**Drive SSL 버그 수정**). 배포 후 폴더 하위 지연로딩 동시호출 시 `[SSL] record layer failure` — 원인=gdrive.py `_SERVICE` 전역캐시(httplib2 비스레드세이프)를 FastAPI 스레드풀 스레드들이 공유→동시 execute 충돌. 수정: 스레드로컬 서비스 + 일시적 SSL/연결에러 재시도(리셋 후). 사용자 승인 완료. 이하 이전 완료상태: 푸시완료 origin/main 59d0417 미푸시0. **2026-07-06 브라우저 라이브 검증 성공**: 배포사이트(onrender.com) 로그인상태→[드라이브에서 등록]→**실제 공유드라이브 트리 정상 노출**(0.농구유니폼/1.야구저지/2.배구/3.럭비티/슈팅셔츠/라운드반팔/축구복 등 실폴더+지연로딩 "불러오는중" 작동). admin+env+폴더공유 전부 정상 확정. **admin 403 이슈 해결**: Supabase app_metadata.role="admin"(사용자 SQL, grader Supabase begxkadzvcczdlewcmrj는 Claude MCP 접근불가). errors.md 기록. **남은 관찰(의뢰서6)**: 반팔/긴팔/하의/야구/축구 등 비농구 합성품질 미검증(농구 V넥 기준 튜닝)—등록은 되나 결과는 테스트가이드북대로 관찰대상. 로컬 서버(127.0.0.1:8000)도 병행 사용중.
- **목표**: 패턴 관리에서 ①공유드라이브 폴더 트리 탐색 ②폴더선택→사이즈미리보기→등록(기존 create_pattern 재사용) ③등록패턴 카드노출·선택. 서버가 서비스계정으로 Drive 읽기전용.
- **Phase 2 커밋(미푸시)**: 2-1 카드 glyphset배지+클릭이동 `322cea0`(tester7/7) · 2-2 driveMode+트리 지연로딩 `30a18f9`(8/8) · 2-3 우측 사이즈미리보기 `e16314a`(12/12) · 2-4 from-drive 등록연결 `f69f937`(20/20). 전부 rev 치명0.
- **⏳ 남은 것(Phase 3)**: (1) **사용자 Google Cloud 설정** — 서비스계정 JSON키 발급 + 드라이브 폴더를 서비스계정 이메일에 공유 + Render env 2개(GDRIVE_SA_JSON, GDRIVE_ROOT_FOLDER_ID). (2) **git push** → Render 자동 재배포. (3) 실드라이브 왕복(다운로드→변환→카드노출) 검증. **로컬 GDRIVE 미설정이라 현재 스텁으로 전 분기 결정론 검증만 완료** — 실드라이브 검증은 env 설정 후.

## 구현 기록 (debugger) — Drive SSL 동시호출 버그 수정 (2026-07-06)
- **무엇을**: `webapp/gdrive.py` 단일 파일. 전역 `_SERVICE`(httplib2 1개) 공유 → 스레드로컬 서비스 + 전송에러 재시도로 교체.
- **왜**: googleapiclient의 httplib2.Http는 스레드 비세이프. FastAPI가 sync Drive 엔드포인트(drive_tree 등)를 스레드풀에서 동시 실행 → 한 TLS 소켓에 동시 write 겹침 → `[SSL] record layer failure`(루트=1건 OK, 하위 동시펼침=충돌). `_SERVICE_LOCK`은 생성만 보호·execute 미보호였음.
- **어떻게**: (1) `_THREAD_LOCAL=threading.local()`로 스레드마다 자기 service(=자기 연결) 캐시. `_SERVICE`/`_SERVICE_LOCK` 제거, `_build_service()`(무거운 google import·creds 지연 유지)/`get_service()`(스레드 서랍 캐시)/`_reset_service()`(연결 폐기) 분리. (2) `_call_with_retry(fn)`: 전송계층 예외(ssl.SSLError·OSError·ConnectionError·BrokenPipeError·http.client.HTTPException·httplib2 ServerNotFoundError/HttpLib2Error) 시 리셋+새연결 1회 재시도(총2회). **HttpError는 미포함=재시도 안 함**(권한/없음은 일시적 아님). (3) list_children는 페이지단위 재시도(같은 pageToken 재실행·모은 items 유지). download_file/get_file_meta도 래핑. 최종실패는 기존대로 DriveError. get_service()를 try 밖 선호출로 **DriveConfigError는 DriveError로 안 감싸짐**(api.py 분리처리 보존).
#### 수정 이력
| 회차 | 수정 내용 | 수정 파일 | 비고 |
|------|----------|----------|------|
| 1차 | 스레드로컬 서비스 + 전송에러 재시도 | webapp/gdrive.py | 원래 요청(SSL record layer failure). 새 에러 발생 없음 |
- **검증**: 모킹 단위테스트 17항목 전통과 — 스레드로컬 분리(Barrier로 4스레드 동시=4 distinct service)·재시도 성공(첫 SSLError→리셋+재빌드→성공)·HttpError 즉시전파(재시도0)·재시도소진 전파·미설정 DriveConfigError 전파·정상 페이지네이션·중간 transient 복구. py_compile 통과. 공개 시그니처·반환형 무변경, 회귀0.
- **제약 준수**: gdrive.py만 수정. api.py/프론트/엔진/인증 무변경. --workers 1 전제·supportsAllDrives 등 Drive 파라미터 그대로. **커밋은 PM이**.

## 테스트 결과 (tester) — Drive SSL 수정 검증 (2026-07-06)
독립 모킹 단위검증(google/httplib2 미설치 환경, 네트워크 0). build/creds 몽키패치 + Barrier로 동시성 강제.

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| py_compile | ✅ 통과 | webapp/gdrive.py 컴파일 OK |
| 1. import + 필수 심볼 | ✅ 통과 | get_service/_build_service/_reset_service/_call_with_retry/_transient_errors/_THREAD_LOCAL 등 전부 존재 |
| 2. 스레드로컬 격리(핵심) | ✅ 통과 | Barrier로 **8스레드 동시** get_service→**8개 고유 서비스**(build tag·id 모두 8 distinct)·스레드당 build 정확히 1회·스레드 내 3회 재호출 동일객체(캐시). *1차엔 id() GC재사용 오탐→tag기반 재검증으로 확정* |
| 3. 전역 _SERVICE 공유 제거 | ✅ 통과 | webapp 전체 `_SERVICE`/`_SERVICE_LOCK` 0건(grep), `_THREAD_LOCAL`=threading.local |
| 4. 재시도 성공 | ✅ 통과 | 1차 execute SSLError→리셋(재빌드)→2차 성공. fn 2회·build 2회 |
| 5. HttpError 비재시도(중요) | ✅ 통과 | HttpError(403)는 전송에러튜플∉→재시도 안 함·즉시 전파(fn 1회). list_children 경유 시 execute 1회 후 DriveError |
| 6. 재시도 소진 | ✅ 통과 | SSLError 2연속→execute 정확히 2회 후 DriveError(무한재시도 없음) |
| 7a. 미설정 회귀 | ✅ 통과 | env 없음→is_configured=False·list_children이 **DriveConfigError 그대로** 전파(DriveError로 안 감싸짐) |
| 7b. 정상 페이지네이션 회귀 | ✅ 통과 | nextPageToken 2페이지 items 전수수집·folder먼저 순서유지·구조 {id,name,isFolder,mimeType}·supportsAllDrives/includeItemsFromAllDrives/corpora=allDrives/orderBy=folder,name 유지 |
| 7c. 공개 시그니처 무변경 | ✅ 통과 | is_configured()/root_folder_id()/list_children(folder_id)/download_file(file_id,dest_path)/get_file_meta(file_id) 동일 |
| 추가 EC. 페이지단위 재시도 items유지 | ✅ 통과 | 2페이지째 transient→같은 pageToken 재실행·이미 모은 items 유지·중복0 |
| 추가 ED. download_file 재truncate | ✅ 통과 | 다운로드 중 SSLError→재시도 시 FileIO"wb"로 파일 새로 비움→부분데이터 잔존 안 함 |
| 추가 T. 전송에러 튜플 구성 | ✅ 통과 | ssl.SSLError·OSError·ConnectionError·BrokenPipeError·http.client.HTTPException + fake httplib2 시 HttpLib2Error/ServerNotFoundError 분기 포함 |
| 8. api.py 상태코드/제약 | ✅ 통과 | DriveConfigError→500·DriveError→502(3엔드포인트 동일). 추적 소스 diff=gdrive.py 1개뿐(api.py/프론트/엔진 무변경) |

📊 **종합: 15항목 전통과 / 0 실패** (모킹 13 + api.py·제약 코드확인 2). debugger 자체검증 17항목 독립 재현 완료. **회귀 0·치명결함 없음 → 커밋 가능.**

⚠️ **본 수정과 무관한 별도 보안 발견**: 작업 디렉토리에 서비스계정 키 `stiz-269705-c141ba6a4825.json`이 **gitignore 안 된 채** untracked 존재(git check-ignore 미매칭) → 실수 커밋 시 비밀키 유출 위험(불변제약 "GDRIVE_SA_JSON 레포 금지"). .gitignore에 `*.json`/해당패턴 추가 또는 파일 이동 권고. gdrive.py 수정과 별개라 커밋 차단은 아님 — PM/사용자 조치.

## 리뷰 결과 (reviewer) — Drive SSL 동시성 수정 (2026-07-06)
📊 **종합 판정: 통과** (치명 0 · 회귀 0 · 제약위반 0). 근본원인 정합·재시도 안전·예외계층 보존 모두 확인. 커밋 가능.

✅ 잘된 점:
- 근본원인 정확 해소: `threading.local()`로 스레드마다 자기 service(=자기 httplib2 연결). `_SERVICE`/`_SERVICE_LOCK` 완전 제거(코드 잔재 0, grep 확인 — 문서에만 남음). `_reset_service`가 현 스레드 캐시만 None→다음 get_service 재빌드.
- 재시도 안전(핵심) OK: 전송계층 집합만(ssl.SSLError·OSError[=ConnectionError/BrokenPipe/socket.timeout 상위]·http.client.HTTPException·httplib2). **HttpError는 Exception 하위라 미포함=재시도 안 함**→그대로 DriveError. 정확히 총 2회(1+재시도1), 2번째 실패는 전파(무한재시도 없음).
- 페이지네이션 재시도 무손실: 실패 페이지는 execute 성공 후에만 items append하므로 중복/유실 0. 재시도는 `pt=page_token` 기본인자 바인딩으로 **같은 토큰 재요청**(서버 stateless 커서=같은 페이지) → 안전.
- 예외계층 보존: 세 함수 모두 `get_service()`를 try 밖 선호출 → DriveConfigError가 DriveError로 안 감싸짐. api.py가 500(config)/502(error) 분리 처리하는 것과 정합.
- download_file 재시도 안전: `with io.FileIO(dest,"wb")`가 매 시도 파일 truncate+핸들 close(컨텍스트매니저) → 부분파일/핸들누수 0. 매 시도 request/downloader 새로 생성.
- 제약 준수: gdrive.py 단일·공개 시그니처/반환형 무변경·supportsAllDrives 등 유지·지연 import 유지(google/MediaIoBaseDownload/ssl·httplib2)·에러메시지 비밀키 노출 0. py_compile OK.

🔴 필수 수정: **없음**

🟡 권장(선택, 차단 아님):
- Google의 일시적 HttpError(429/503 등)는 HttpError라 재시도 안 됨 — 원래도 재시도 0이었으니 회귀 아님. 이번 버그(SSL 전송충돌) 범위 밖. 후속 여력 시 status 429/5xx만 선별 재시도 고려 가능.
- (관찰) 재시도 중 _build_service가 DriveConfigError를 낸다면 list_children의 except Exception이 DriveError로 감쌀 수 있으나, 첫 빌드 성공 후 동일 프로세스 재빌드 실패는 사실상 불가(env 불변)=무시가능.
- (관찰) `_TRANSIENT_ERRORS_CACHE` 무락 초기화는 멱등·GIL 원자대입이라 무해.

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
| tester | stiz-*.json 서비스계정 키 | 키가 gitignore 안 된 채 작업트리 존재(유출위험) | ✅해결 2026-07-06: .gitignore에 stiz-*.json 등 추가(미추적→무시 확인, 유출 전 차단) |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-07-06 | tester | Drive SSL 수정 독립 검증(gdrive.py, 모킹) | **15/15 통과**·회귀0·치명0. 8스레드 Barrier 동시=8 distinct service·재시도 성공/HttpError 미재시도/소진 전파/DriveConfigError 분리/페이지네이션·다운로드 재truncate 재현. 별도 보안발견: SA키 json gitignore 누락(수정요청). 커밋 가능 |
| 2026-07-06 | reviewer | Drive SSL 동시성 수정 리뷰(gdrive.py) | **통과**·치명0·회귀0·제약위반0. 스레드로컬 정합·재시도 총2회·HttpError 미재시도·페이지네이션 무손실·DriveConfigError/DriveError 분리·다운로드 truncate 안전 확인. py_compile OK |
| 2026-07-06 | debugger | Drive SSL record layer failure 수정(gdrive.py 스레드로컬+재시도) | 근본원인=httplib2 비스레드세이프 전역공유. 스레드로컬 서비스+전송에러 1회재시도. 단위17/17·py_compile OK·회귀0. 커밋 대기(PM) |
| 2026-07-06 | pm | Drive 연동 전과정 완료 — 푸시·배포·admin권한 부여 | origin/main 59d0417 배포. 스모크 통과. admin 403→Supabase role=admin(사용자 SQL)→해결. 실서버 동작 |
| 2026-07-06 | pm | Drive Phase2 완결 — 프론트 4단계 커밋(322cea0/30a18f9/e16314a/f69f937) | 트리→미리보기→등록 흐름 완성. scratchpad 압축(324→~100줄) |
| 2026-07-06 | dev/tester/rev | Phase2 4단계 — from-drive 등록연결(registerFromDrive) | tester20/20·rev치명0. 검증→진행→성공/실패5갈래·driveSaving가드·회귀0 |
| 2026-07-06 | dev/tester/rev | Phase2 3단계 — 우측 사이즈 미리보기(/patternfiles) | tester12/12·rev치명0. 표준정렬(문자열함정회피)·이름자동제안·경쟁가드 |
| 2026-07-06 | dev/tester/rev | Phase2 2단계 — driveMode+폴더트리 지연로딩 | tester8/8·rev치명0. 3화면 상호배타·configured:false 4갈래·캐시·회귀0 |
| 2026-07-06 | dev/tester/rev | Phase2 1단계 — 카드 glyphset배지+클릭→work 프리셀렉트 | tester7/7·rev치명0. 실브라우저 클릭검증·회귀0 |
| 2026-07-06 | planner-architect | Drive Phase2 프론트 설계 | 독립 #driveMode 레이아웃A·4단계·decisions기록 |
| 2026-07-06 | pm(workflow×8) | 의뢰서 대비 Drive 작업 진척 코드대조 검증 | 백엔드 done·프론트 미착수·미푸시 확인→Phase2 착수 결정 |
| 2026-07-01 | pm | Drive Phase1 백엔드 완결(1a~1d) | tree/patternfiles/from-drive·파서12/12·mock검증·커밋4·기존영향0 |
| 2026-06-26 | dev/test/pm | introspection 인증+계정+도움말 4화면 | tester36/36·8/8·84/84·푸시 완료 |
