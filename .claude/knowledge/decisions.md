# 기술 결정 이력
<!-- 담당: planner-architect | 최대 30항목 -->
<!-- "왜 A 대신 B를 선택했는지" 기술 결정의 배경과 이유를 기록 -->

### [2026-07-07] 패턴 폴더 자동 스캔: 벌크 2쿼리(폴더+파일) → 부모별 그룹핑 + 카드 그리드(발견 전용, 등록은 기존 정확경로 재사용)
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 깊은 트리(예 0.농구>단면>U넥>스탠다드>스탠다드-A 5단계)를 일일이 펼치는 대신, 등록 가능한 패턴 폴더를 **자동 발견해 카드 그리드**로 노출. **핵심 결정 3가지.** **(1) 스캔 방식=재귀 대신 벌크 2쿼리.** 재귀(폴더당 list_children)는 폴더 수 N에 비례한 N회 호출(수백 회 가능)로 느리고 쿼터 폭증. 대신 ①전 폴더 1쿼리(q="mimeType='application/vnd.google-apps.folder' and trashed=false", fields="files(id,name,parents)", pageSize=1000) → id→{name,parents} 맵 ②전 비폴더 파일 1쿼리 → 부모폴더별로 묶어 파일명에 기존 `_parse_size_from_filename` 적용, 사이즈 1개 이상 인식 폴더만 "패턴 폴더" 채택. 호출 수가 O(폴더수)→**O(페이지수)**(보통 각 1~수 페이지)로 급감. 경로는 폴더맵으로 부모를 따라 올라가 조립(**추가 API 0**). **(2) 파일 쿼리는 `name contains '.ai'` 금지 → 전 파일 fetch + 확장자 endswith 서버필터.** 근거: Google Drive `name contains`는 **임의 substring이 아니라 토큰 prefix 매칭**이라 확장자(".ai/.pdf/.svg")에 대해 신뢰 불가 → **누락(under-match) 위험**(진짜 .ai 파일을 못 찾아 폴더 자체가 목록에서 사라짐=발견 실패). over-match만 endswith 2차필터로 막는 제안의 원안은 under-match를 못 막음. 따라서 비폴더 파일을 전부 받아 `_PATTERN_FILE_EXTS`(.ai/.pdf/.svg) endswith로 서버에서 정확 필터(서비스계정은 공유 폴더=패턴 라이브러리만 보이므로 총량 바운드). **(3) 카드 그리드는 발견/목록 전용, 미리보기·등록은 기존 정확 경로 재사용.** 카드 [등록] 클릭→기존 `renderDrivePreview({id,name})`→GET /patternfiles(폴더당 정확 스캔), 등록→POST /from-drive→`_scan_folder_pattern_files`(정확 재스캔). 즉 벌크 스캔의 사이즈수 배지가 근사여도 **실제 등록되는 것은 항상 정확 경로가 결정** → 벌크 근사 오차가 등록을 오염 안 함(중복 UI 0). **엔드포인트**: GET /api/drive/scan?refresh=1 (admin), 반환 {configured,cached,scanned_at,count,folders:[{id,name,path,size_count,sizes[]}]}, 정렬=path→name(카테고리 클러스터), 미설정=200 {configured:false}(기존 `_drive_not_configured_payload` 재사용)·500 DriveConfigError·502 DriveError(기존 규약). **캐시**: 서버 메모리 dict+threading.Lock+TTL(5~10분), --workers 1이라 일관, ?refresh=1 강제 재스캔(스캔 수 초 소요). **루트 스코프**: 각 폴더 조상추적으로 GDRIVE_ROOT_FOLDER_ID 자손만 채택(corpora=allDrives가 타 공유드라이브 폴더를 반환할 수 있어 필터 필수·조상체인 끊긴 폴더=경로 조립 불가라 자동 제외). **shared drive 부모=단일**(다중부모 폐지)이라 경로 유일. **gdrive.py 헬퍼 2개 신설**(list_all_folders/list_all_pattern_files, 기존 list_children 패턴=스레드로컬+_call_with_retry+페이지네이션+supportsAllDrives 복제, 확장자/사이즈 판정은 api.py). **프론트**: driveMode에 세그먼트 토글 [자동 찾기 | 폴더 트리], 자동찾기=기본. 카드톤은 renderPatternGrid 재사용(card--interactive/badge--info "N사이즈"/캡션=경로 breadcrumb/[등록]). renderDrivePreview(folder, panel) 파라미터화(기본 #drivePanel=트리 하위호환)로 스캔 패널과 ID 충돌 방지, registerFromDrive(panel)로 하드닝(최소·하위호환). 로딩/빈결과/403/미설정/오류는 classifyDriveRes+driveEmptyHtml 재사용, 새로고침 버튼+최신성 표시. **불변**: 엔진/인증/기존 Drive 3엔드포인트/등록흐름 무변경(추가만)·빌드0·var(--*)·Material Symbols·admin전용·Drive 읽기전용·비밀키0·--workers 1. **대안 기각**: (a)재귀 스캔=호출 폭증 (b)name contains 필터=누락 위험 (c)스캔 결과로 별도 등록 UI 신설=중복(기존 renderDrivePreview 재사용이 단순).
- **참조횟수**: 0

### [2026-07-06] Drive 연동 Phase 2(프론트 UI): 독립 #driveMode 채택 + 카드 glyphset배지·클릭이동
- **분류**: decision
- **발견자**: planner-architect
- **내용**: patterns.html에 Drive 폴더 트리→미리보기→등록 UI를 얹을 때 배치 3안 비교. **A(독립 #driveMode 섹션, listMode/registerMode의 형제) 채택.** 근거 2개: ①**from-drive는 원샷 서버호출**이다(folderId+name→create_pattern 재사용이 다운로드·변환·매핑·preset 생성을 서버에서 전부 처리). ②**현 로컬 savePattern은 subB(디자인↔조각 매핑)·subC(배번/이름 영역) 드래그 결과를 서버로 전송하지 않는다**(name/base_size/files/glyphset/reference만 FormData 전송, api.py savePattern 954~963). 즉 매핑은 create_pattern이 OCG "패턴선" 자동매핑으로 수행 → Drive 흐름은 subA/B/C 없이 **폴더선택+이름만으로 완결**된다. 따라서 트리 UI를 registerMode 3단계에 끼울 필요가 없고, 독립 패널이 가장 단순·기존흐름 충돌0. **대안 B(registerMode 앞에 Drive 0단계 서브스텝)**=의뢰서 "3단계 플로우 연결" 문구엔 가깝지만 stepper·로컬 savePattern 경로를 복잡화하고 from-drive가 subB/C를 우회해 어색 → 기각. **대안 C(listMode 인라인 접이식 트리)**=단일화면 장점이나 실제 트리가 깊고(4대 카테고리×핏×암홀×원본) 넓어 카드 그리드와 공간 경합 → 기각. **카드 개선**: GET /api/patterns가 이미 **glyph_source(bool)** 반환(api.py:116,153) → 카드 glyphset 배지는 프론트만으로 추가(백엔드 무변경). 카드 클릭→작업이동은 **sessionStorage `grader_selected_pattern`=p.id 후 work.html 이동**, work.html이 PATTERNS 로드 후 그 키를 읽어 patternId 프리셀렉트+키 삭제(URL 파싱보다 단순, 양쪽 이미 sessionStorage 사용). work.html이 유일한 크로스파일 접촉(리더 소량 추가, 키 없으면 기존 동작 무변경). **admin 게이트**: Drive 엔드포인트 전부 admin_required → 로컬 무인증=통과, 배포 non-admin=403. apiFetch는 401만 특수처리하므로 403은 r.ok=false로 떨어져 트리/미리보기 영역이 "관리자(admin) 권한이 필요합니다" 빈상태로 안내(configured:false와 동일 톤). **미설정**(GDRIVE_* env 없음)=200+{configured:false}+message → 같은 빈상태. **불변**: 엔진/인증/기존 등록흐름 무수정, 빌드0(정적+fetch), 하드코딩색 금지→var(--*)만, Material Symbols, _handoff 원본 아닌 webapp/static 복사본만. **1차 범위 축소**: glyph_file_id·reference_file_id(폴더 내 글리프셋/완성본 지정)는 from-drive가 지원하나 Phase2 UI에선 생략(create_pattern이 없으면 폰트 폴백) → 백로그. **리스크**: from-drive는 .ai 다수 다운로드로 느릴 수 있어 "등록 중…(드라이브 다운로드·변환)" 진행표시+saving 가드 필수. 이름 자동제안은 선택 폴더명 trim+연속공백 정규화(실데이터에 "v넥 상의 스탠다드  XS" 등 중복공백 존재), 편집 가능.
- **참조횟수**: 0

### [2026-06-25] 배포 Phase 1 갱신본: JWT secret(HS256) → Supabase 토큰 introspection 교체
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 2025 Supabase 비대칭 JWT 서명키 도입으로 **HS256 secret 로컬검증 폐기**, `GET {SUPABASE_URL}/auth/v1/user` introspection으로 교체(서명 알고리즘 무관·가장 견고). **auth.py require_auth 전면교체**: 토글 OFF=즉시통과(로컬 회귀0 보존), ON=Authorization Bearer 추출→httpx.get(headers={apikey:PUBLISHABLE, Authorization:Bearer token})→200이면 user(id·email·app_metadata.role)을 request.state, 비200/네트워크예외=401. **성능: 토큰별 60초 메모리캐시**(`_TOKEN_CACHE: dict[token, (user, expire_ts)]` + threading.Lock, 모듈전역, --workers 1이라 일관). **제거**: pyjwt(requirements·auth.py의 import jwt/jwt.decode/secret분기/안내500 전부). **env 이름 정합**: SUPABASE_ANON_KEY/SERVICE_ROLE_KEY/JWT_SECRET 폐기 → URL/PUBLISHABLE_KEY/SECRET_KEY(로컬 .env가 이미 새이름이라 정합·.env.example만 옛이름이라 동기 필요). SECRET_KEY는 introspection 미사용이나 env엔 유지(향후 admin API), public-config·프런트 절대금지. **admin 게이트 신규**: admin_required Dependency(role!='admin'이면 403, 단 토글 OFF시 통과=로컬일관)를 POST /api/patterns·PUT /api/settings 데코레이터 dependencies에만. **/api/config→/api/public-config**: supabase_anon_key→supabase_publishable_key. **프런트**: login.html 2곳(webapp/static+_handoff 동기) /api/public-config·publishable 키명. apiFetch 래퍼는 무변경(토큰명·Authorization 동일). **Dockerfile PORT**: 정본 exec form --port 8000 고정 대신 **현 ${PORT:-8000} shell form 유지 권고** — 근거 Render 공식문서(Docker web service에 PORT 주입·기본 10000·$PORT 바인딩 권장), 8000 고정은 10000과 미스매치로 헬스체크 실패 위험. **tester는 외부 Supabase 호출이라 httpx 모킹 필수**(200/401/timeout·60초캐시 call_count·admin403·로컬토글회귀·SECRET미노출·미로그인401). 불변: 엔진 공개API 무수정·--workers 1·SECRET 레포금지·GRADER_REQUIRE_AUTH 토글 보존.
- **참조횟수**: 0

### [2026-06-25] 배포 Phase 1: Docker+Render+Supabase Auth 게이트 설계(GS env 우선·인증 끼움점·_handoff 복사규칙)
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 로컬 전용 웹앱→인터넷 사내도구. **GS 경로 env화 끼움점**=`engine/eps.py:find_ghostscript` **맨 앞에 `os.environ.get("GS_BIN")` 최우선 분기** 추가(있고 shutil.which로 실행가능하면 즉채택). 이유: GS 호출 체인이 job.py→find_ghostscript 단일경유라 여기 1곳이면 EPS 전부 커버, 기존 폴백(settings_path→Windows절대경로→PATH)은 **로컬용으로 그대로 보존**(env 미설정 로컬=무회귀). Docker는 ENV GS_BIN=gs라 리눅스 `gs` 채택. preset의 ghostscript_path보다 env 우선(컨테이너가 로컬 Windows 절대경로 무시). **인증 끼움점**=api.py router 전역 `Depends(require_auth)` 적용하되 **/api/health만 제외**(Render healthCheckPath라 인증 막으면 부팅 실패). 방법2택: ①health 핸들러를 별도 무인증 router로 분리 ②전역 적용+health 내부에서 검사스킵. ①권장(명확). JWT는 SUPABASE_JWT_SECRET(HS256) 검증, user id/role→request.state. **--workers 1 유지 이유**=_JOBS 인메모리 레지스트리 일관성(Phase3 DB이전시 완화). **프런트**=화면별 inline <script>에 공통 fetch 래퍼(`apiFetch`) 도입—기존 16곳 `fetch("/api/...")`를 래퍼로 교체, sessionStorage access_token을 Authorization 헤더로 부착, 401/토큰부재시 login.html 리다이렉트. FormData 업로드는 headers만 머지(Content-Type 자동설정 보존). **_handoff 복사규칙**: login.html·수정 화면은 `_handoff/grader-v2-static`(원본) 먼저 작업→`webapp/static`으로 복사(README 무수정 규칙). **불변 준수**: 엔진 공개API 무수정(eps 분기 1개·시그니처 불변), 비밀키(JWT_SECRET·SERVICE_ROLE) 레포·프런트 금지(render env sync:false), run.py/run.bat 127.0.0.1 무수정(로컬 회귀0), state.py는 DEFAULT_PORT=int(os.environ.get("PORT",8000)) 1줄만. **저장은 Phase1에선 Render 임시디스크 허용**(재배포시 소실, Storage/DB는 Phase2~3).

### [2026-06-25] 합성 흰틈/극소형 미달 해소: A 본체색 채움(Piece.bg_cmyk) + B 사이즈별 자동 블리드
- **분류**: decision
- **발견자**: planner-architect / developer
- **내용**: 두 문제를 한 작업으로 해결. **문제1**=패턴선 안쪽 디자인 본체(투명) 빈틈이 흰색으로 남음. **문제2**=XL base 1장을 다른 사이즈로 등방 cover하면 비균일 그레이딩 탓에 극소형(5XS 등)에서 흰 요소(줄무늬)가 재단선까지 못 닿음. **A 채택**: 본체 fill은 클립(`W n`)직후·`Do`앞이어야 디자인이 그 위를 덮음(디자인 있는 곳=디자인색, 빈 곳만 본체색). 호출자 compose는 불변이므로 **Piece에 `bg_cmyk: Optional=None` 필드 추가**(A-4 extra_ops 선례와 동일)→`place_block(...,bg_cmyk=None)`이 fill 주입. 본체색은 run_job이 1회 결정: **preset.body_fill(이번값[0.8,0.5,0,0.1]) > flatten.detect_background_cmyk(pikepdf.Pdf객체, 면적최대 불투명 k) > None(채움생략=하위호환)**. **B 채택**: `_build_precise_layout`에서 앞판(front) 1개 기준 `dev=|(앞판폴리곤 pw/ph)/(디자인영역 dw/dh)-1|`, `bleed=clamp(1.0+k·dev, lo, hi)` **단일값 1회 산출→전 조각 동일 적용**(조각마다 비율 다르므로 통일, 등방 유지=번호/이름 무왜곡). preset `cover_bleed`를 float(기존) 또는 `{auto:true,k:1.3,min:1.0,max:1.12}` dict 둘 다 허용(3분기: dict-auto/float/None). 검증값 XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036(cowork 일치). **불변 준수**: compose/_job_piece_transform(bleed 인자 기존존재) 시그니처 무수정, 신규 전부 기본값. device k+f(CMYK·불투명·벡터)→verify PASS, fill은 Do아님→배치횟수 불변. tester 6/6 PASS·reviewer 통과 치명0.
- **참조횟수**: 0

### [2026-06-19] Phase D: 기존 path SVG 활용 + path→polyline 전처리 변환기(parse_svg 무수정)
- **분류**: decision
- **발견자**: planner-architect
- **내용**: V넥 패턴 SVG 13개(5XS~5XL, 직선 폴리라인 path)가 G드라이브에 이미 존재함을 발견. 형식은 inkscape/PyMuPDF류 `<path>`+`matrix(1,0,0,-1,tx,ty)`로 **곡선명령 전무**(M/H/L/V만, 실측). parse_svg는 polyline/polygon만 읽어 이 SVG를 **0조각**으로 반환(검증). **결정: parse_svg를 고치지 않고(불변제약 §6), path SVG를 읽어 U넥과 동일한 polyline SVG로 다시 써주는 전처리 변환기 `engine/svg_normalize.py`를 신규 모듈로 추가.** 대안 비교 — ①Phase D-1 ai_to_svg.jsx(일러 GUI 재내보내기): 소매 보존되나 사용자 수동·13개 재작업·GUI의존. ②PyMuPDF get_drawings 재생성: 소매 분리선 재구성 추측영역·정합위험. ③(채택) 기존 path SVG 직접 변환: 이미 있는 13개 즉시 활용, matrix+직선전개는 결정적·정확, parse_svg 무수정, 1회성 변환. ③이 가장 단순·안전(이미 만든 자산 재사용). **변환 핵심**: path d 직선전개(M/H/L/V 절대·상대) + matrix(a,b,c,d,e,f) 적용 → viewBox좌표 polyline points(flip_y는 parse_svg가 하므로 변환기는 안 함=이중flip 방지) → U넥형 SVG. 보조선(열린/세로/수평선) 필터로 닫힌 조각만. **실측 확정사실**: V넥 XL.svg 닫힌조각=앞판(path1,V넥,h2354)·뒤판(path0,h2352) **2개뿐, 소매 윤곽 부재**. 변환후 parse_svg 높이정렬→**앞=idx0/뒤=idx1**(U넥 뒤0앞1소매2와 반대순서 주의). design_region_pt는 펼침본(4478×5669) 좌표로 적고 _piece_transform이 마커시트 조각bbox에 앵커+contain 자동정합(Phase C 방식A 무수정). **잔존 차단**: ①소매 조각 부재(앞/뒤 2조각 1차, 사용자 결정 필요) ②빈템플릿 미확보(design_file placeholder) ③design_region_pt U넥값 재사용→V넥 reference 재추출 권장 ④svg_index 정렬역전(앞뒤 높이차2pt) 단계검증. **Phase D-1 ai_to_svg.jsx는 폐기 아님**(곡선섞인 다른 패턴·소매 별도확보 시 폴백 경로로 보존).
- **참조횟수**: 0

### [2026-06-18] job split 기본값 per_player(파일별 PDF) 확정 + 사이즈필터=preset 복제 방식
- **분류**: decision
- **발견자**: planner-architect (split 기본값은 사용자 2026-06-18 확정)
- **내용**: job(선수별 통합 출력) 설계 시 두 결정. **(1) split 기본값=per_player**(선수마다 별도 PDF) 채택, single(다페이지 1PDF)은 옵션 유지. 이유: 실작업 단위가 선수별(같은 사이즈도 이름·배번 다름)이고 공장/작업자가 선수 단위 파일·ZIP을 다루기 쉬움. 과거 A-1 결정의 "다페이지 1PDF"는 디자인1장 전사이즈 케이스라 job(선수 단위)과 층위가 다름 → 충돌 아님(single로 보존). **(2) 사이즈 필터를 build_layouts 신규 인자 대신 "preset dict 얕은복제 후 sizes 1개로 좁히기"로 구현** 채택. 대안(build_layouts에 size_filter 인자 추가)을 버린 이유: 불변 제약(engine/응용 공개 함수 시그니처 변경 금지, 신규 인자도 최소화)을 지키고, 선수는 자기 사이즈 1페이지만 필요한데 build_layouts는 preset.sizes 전체를 순회하므로 입력 데이터(preset)를 좁히는 게 코드 변경 0으로 가장 단순. `{**preset, "sizes":[one]}`로 복제하면 원본 preset·_dir·area 보존되고 build_layouts는 그대로 1개만 처리. **부가 결정**: ①폰트 인자(font_path)는 인터페이스 안정성 위해 받되 1차 미사용(area.font가 preset에 박힘) — 추후 area.font 오버라이드 훅으로 활용. ②미존재/빈 사이즈 행은 skip+사유기록(부분성공, 전부 실패일 때만 비정상 종료) — A-2 전사이즈 확보 전 흔하므로. ③원자적 쓰기 tmp→os.replace. ④폴더명 결정은 CLI, run_job은 out_dir만 채움. ⑤백로그⑦(상하의 분리)는 1차 범위 밖(상의만), order_rows에 top/bottom 분리 들어오면 run_job 루프를 행×garment로 확장(기본값 호환).
- **참조횟수**: 0

### [2026-06-15] A-5 주문서 파싱 1차 범위: 「선수별 행」 양식 메인 + 「집계」 best-effort, 상의 사이즈 기준
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 실데이터 86개 전수 스캔으로 STIZ 표준 양식이 2종임을 확인(①선수별행 81개 ②사이즈집계 5개). "86개 100% 자동" 대신 **①을 메인 완성, ②는 기존 grader order_parser.py 규칙 이식으로 best-effort, 나머지 변형은 부분실패(빈값)+경고로 흘림**으로 범위 확정(웹에서 붉게 강조→수기입력이 안전망). 파싱 핵심 규칙 3가지 채택: (a) 헤더 행 위치가 2/3행으로 양식버전마다 달라 **행 고정 금지·"이니셜" 키워드로 헤더 탐색** (b) 사이즈 정규화는 **긴 것부터 매칭**(SIZE_KEYWORDS 길이 내림차순; 5XL이 XL로 오인 안 되게) + 공백/하이픈 흡수 + **아동 호수 N호 지원** (c) "○○호" 오탐(이름 끝글자 '호')은 `^\d{1,2}호$`로만 사이즈 인정. 반환은 `[{name,number,size,qty}]` 전부 str·실패="", 행은 유지(크래시 금지). **상의/하의 사이즈가 행마다 다를 수 있으나 1차는 상의(C열) 기준**(하의 분리·qty 추가벌 파싱은 백로그, job 설계와 연동). data_only=True+read_only=True로 로드. Custom Properties 몽키패치는 현 데이터 미발생이나 외부 xlsx 대비 무해 방어로 이식.
- **참조횟수**: 0

### [2026-06-15] A-2 패턴 로딩 계층 분리: engine/pattern_loader.py 신설 (pattern.py 추가 X)
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 다중 사이즈 SVG 로딩(사이즈 순회→경로탐색→parse_svg→Piece 변환)을 grade.py `build_layouts`에서 떼어 **응용 계층 신규 모듈 `engine/pattern_loader.py`**로 분리. pattern.py에 함수 추가하지 않는 이유: pattern.py는 `parse_svg/Polyline`을 제공하는 engine 공개 모듈로 preset을 몰라야 함(계층 분리). preset 규약을 아는 코드는 grade.py와 같은 응용 계층에 둔다. 방식A transform(_piece_transform)은 A-1 확정 자산이라 grade.py에 그대로 유지하고 loader가 import. 공개 API(parse_svg 등) 불변 제약 준수.
- **참조횟수**: 0

### [2026-06-15] A-4 글자 결합 방식: Piece.extra_ops 필드(기본값 "") + 글리프 큐빅 경로
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 배번/이름 벡터 렌더(engine/text.py)에서 글자를 디자인에 얹는 방법으로 (A)페이지 콘텐츠에 글자블록 append vs (B)Piece에 extra_ops 필드 추가 중 **(B) 채택**. 이유: 글자는 "특정 조각의 특정 칸"에 종속된 정보라 Piece에 묶는 게 의미상 맞고, compose 변경이 루프 안 1줄(`if piece.extra_ops: blocks.append(...)`)로 끝나 가장 작다. Piece dataclass에 `extra_ops: str = ""` **기본값 빈문자열**로 추가 → 공개 API "기존 인자 불변+신규는 기본값" 원칙 유지(기존 호출 전부 무수정 동작), compose 시그니처 자체는 불변. 디자인 Form은 손대지 않으므로 바이트동일/단일임베드 검증 영향 0. 글자는 CMYK `k` fill·투명도 미사용·이미지 0생성·`Do` 미사용 → verify_output 전항목(래스터미추가·CMYK유지·배치횟수==placements) 그대로 PASS. **폰트 확정**: Pretendard-Black/Bold.otf는 CFF(큐빅 베지어) 아웃라인(glyf 아님), unitsPerEm=2048 → 펜의 curveTo가 PDF `c`(큐빅)에 1:1 대응(곡선 근사 불필요). 한글은 글리프 경로 좌표로 펴지므로 ascii 콘텐츠에 한글 바이트가 안 들어감(compose가 .encode("ascii")라도 안전). 글리프 누락 시 해당 텍스트(선수) 전체 미출력+경고(부분 글자 누락이 이름 깨짐보다 위험). 단독 테스트는 CLI `--number`/`--name` 플래그(job 단계 전이므로).
- **참조횟수**: 0

### [2026-06-15] A-2 사이즈 SVG 탐색 규약 + 누락 부분성공 정책
- **분류**: decision
- **발견자**: planner-architect
- **내용**: 사이즈별 SVG 경로 탐색은 2단계 폴백 — ①`size.pattern_file` 명시 시 그대로(현행) ②없으면 파일명 컨벤션 `<size.name>.svg` 자동 탐색. → 신규 사이즈는 SVG 파일 넣고 sizes에 `{"name":"S"}` 한 줄만 추가하면 코드수정 0으로 동작(사용자 요구). preset.json 구조 변경 없음(pattern_file을 필수→선택으로 문서 완화만). 누락 사이즈는 **에러 대신 경고+건너뜀(부분 성공)**: 있는 사이즈만 합성, 전부 누락일 때만 에러. 높이정렬(svg_index) 역전 위험은 A-2에서 (a)조각 개수 검증 (b)종횡비 교차검증 경고로 방어하되, piece_id↔SVG id 근본매칭은 현 SVG에 조각 id가 없어 보류(백로그⑤ 별도 결정).
- **참조횟수**: 0

### [2026-06-10] 공장 출력 포맷: EPS → PDF 전환
- **분류**: decision
- **발견자**: pm / planner-architect
- **내용**: 설계서(DESIGN.md)는 Ghostscript eps2write로 EPS 출력 예정이었으나, 공장이 PDF 수용 가능 확인 → PDF로 확정. eps.py 단계 폐기. 이유: EPS는 투명도 미지원 구포맷이라 투명도 1%만 있어도 페이지 전체 래스터화 + ICC 색 변형 위험(공식문서 확인). PDF는 device CMYK·벡터·투명도 그대로 보존 가능.
- **절대 조건**: ① CMYK 완전 보존(device CMYK 그대로 통과, RGB/ICC 변환 금지) ② 파일 경량(Form XObject로 디자인 1회 임베드 후 N×M 참조).
- **참조횟수**: 0

### [2026-06-15] A-1 좌표정합 방식: ✅ "앵커 기반 정합"(방식 A) 확정 (시험렌더 검증)
- **분류**: decision
- **발견자**: planner-architect 제안 → developer 시험렌더 → 사용자 확정
- **내용**: 디자인↔패턴 좌표 관계 3안 중 **방식 A(앵커 기반 정합) 최종 확정**. 사용자가 "실파일로 먼저 검증" 후 결정하기로 하여, 실데이터(design_XL.ai + pattern_XS.svg)로 방식A(조각별 design_region을 조각 윤곽 bbox에 앵커정렬+등방스케일) vs 방식B(디자인 전체를 패턴시트에 1회 정렬 후 조각 윤곽 클리핑)를 grading_compare/compare_mapping.py로 실제 합성·미리보기 비교. **결과: 방식A=앞/뒤/소매가 옷 형태 그대로 완벽 배치, 방식B=디자인이 조각 경계서 잘리고 어긋남(YONSE/김ㅎ 등 일부만)→사용불가.** 방식A는 일러 면적비+상대벡터 철학과 일치, engine Piece.transform(cm)에 1:1 대응, device CMYK 무손실 유지. 실측 매칭: 디자인 앞판→패턴조각idx1, 뒤판→idx0, 소매→idx2(종횡비 일치). → preset.json은 방식A 기준(조각별 design_region_pt + 앵커정렬)으로 확정.
- **주의(다음 구현 반영)**: 앵커 정합 시 transform 오프셋(e/f)이 음수가 될 수 있어 engine verify.py의 cm 검증 정규식(음수 미허용)이 "스케일 적용"을 FAIL로 오판 → A-3 구현 시 verify 정규식 보강 또는 좌표 오프셋 양수화 검토 필요(engine 수정은 별도 승인). 합성 자체는 정상.
- **참조횟수**: 0

### [2026-06-15] 출력 PDF 단위: ✅ 다페이지 1PDF(사이즈=페이지) 확정 (사용자) — 단 공장 RIP 수용성 추후 확인
- **분류**: decision
- **발견자**: planner-architect
- **내용**: engine.compose는 SizeLayout 리스트를 받아 "한 사이즈=한 페이지"인 다페이지 PDF 1개를 만든다(이미 구현됨, selftest 6사이즈 1PDF 검증). 일러 구버전은 사이즈별 개별 EPS였다. 다페이지 1PDF는 디자인 임베드 1회·관리 단순 장점. 단 공장 RIP/작업자가 "사이즈별 개별 파일"을 요구하면 페이지 분할 출력 옵션 필요 → 사용자 결정사항. preset.json 스키마는 두 경우 모두 수용(레이아웃 생성은 동일, 저장 단위만 분기)하도록 설계.
- **참조횟수**: 0

### [2026-06-10] 합성 엔진: pikepdf 중심, PyMuPDF는 미리보기 전용
- **분류**: decision
- **발견자**: planner-architect
- **내용**: PDF 합성은 pikepdf(Form XObject 재사용 + W n 클리핑 + cm 스케일)로 무손실 벡터·CMYK 보존. PyMuPDF는 PNG 렌더 시 RGB 변환되므로 검수 미리보기에만 쓰고 출력 경로엔 절대 사용 금지.
- **참조횟수**: 0
