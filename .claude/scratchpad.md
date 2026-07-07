# 작업 스크래치패드

## 현재 작업
- **상태**: ✅✅ **Google Drive 패턴 연동 — 전 과정 완료**(백엔드1a~1d + 프론트2-1~2-4 + 푸시·배포·admin권한). 2026-07-06 사용자 "완료" 보고. 의뢰서 완료기준(트리탐색→미리보기→등록→카드) 실서버 동작.
- **현재 담당**: pm → planner-architect (**신규기능: 즐겨찾기+자동분류+영속저장**). 사용자 확정: 저장=Supabase(영구·공유·무료, 관리자 SQL 1회) / 분류=자동(경로기반 옷종류) / 대상=등록된 패턴(작업용) / 직원도 열람·사용·관리자만 정리·등록. ⚠️확인결과: Render 영구디스크 없음→등록패턴도 재배포시 소실(현재 repo커밋 2개만 잔존), Supabase는 auth전용(DB쓰기 0, SECRET/SERVICE_ROLE 제거상태=백엔드 키리스 유지 필요→프론트direct Supabase+RLS 또는 user JWT프록시). architect가 스키마+RLS SQL·자동분류·권한·UI(patterns목록+work step1)·등록패턴 영속화 단계분리 여부 설계중. 아래 완료분:
- **[이전]** ✅ **패턴 폴더 자동 스캔 완성·배포**: 백엔드 f3b3257(/api/drive/scan 대량조회+캐시·tester68/68) + 프론트 25f490c([자동찾기|트리]탭+카드그리드·tester69/69·트리회귀0·입력칸중복0) + docs f977d75. origin/main f977d75 미푸시0. 재배포 스모크통과(scan 401·프론트 마커). **사용자 실서버 [자동찾기] 카드 확인 대기**. 스캔=발견전용·등록은 기존 정확경로. 남은 관찰(의뢰서6): 비농구(야구/축구/반팔/하의) 합성품질 미검증(농구V넥 튜닝)=관찰대상.
- **이전 완료(2026-07-06~07)**: Drive Phase1(백엔드)+Phase2(프론트 트리/미리보기/등록)+배포+admin권한(Supabase role=admin, grader Supabase는 Claude MCP 접근불가)+SSL동시성수정(gdrive 스레드로컬+재시도 4783a12)+키 gitignore(ac785a5). 실서버 트리탐색·5단계깊이·미리보기 브라우저 검증 성공. 배포 URL grader-v2-47gd.onrender.com. 로컬(127.0.0.1:8000)도 병행.
- **목표**: 패턴 관리에서 ①공유드라이브 폴더 트리 탐색 ②폴더선택→사이즈미리보기→등록(기존 create_pattern 재사용) ③등록패턴 카드노출·선택. 서버가 서비스계정으로 Drive 읽기전용.
- **Phase 2 커밋(미푸시)**: 2-1 카드 glyphset배지+클릭이동 `322cea0`(tester7/7) · 2-2 driveMode+트리 지연로딩 `30a18f9`(8/8) · 2-3 우측 사이즈미리보기 `e16314a`(12/12) · 2-4 from-drive 등록연결 `f69f937`(20/20). 전부 rev 치명0.
- **⏳ 남은 것(Phase 3)**: (1) **사용자 Google Cloud 설정** — 서비스계정 JSON키 발급 + 드라이브 폴더를 서비스계정 이메일에 공유 + Render env 2개(GDRIVE_SA_JSON, GDRIVE_ROOT_FOLDER_ID). (2) **git push** → Render 자동 재배포. (3) 실드라이브 왕복(다운로드→변환→카드노출) 검증. **로컬 GDRIVE 미설정이라 현재 스텁으로 전 분기 결정론 검증만 완료** — 실드라이브 검증은 env 설정 후.

### 기획설계 — 등록패턴 즐겨찾기+자동분류+메타 영구저장 [2026-07-07 planner-architect]

🎯 목표: 등록된 패턴을 (자동분류된) 카테고리로 묶어 보여주고, 관리자가 즐겨찾기(별표)를 지정하면 전 직원이 공유·열람. 저장=Supabase(begxkadzvcczdlewcmrj), 백엔드 키리스 유지.

🔑 핵심 확정(설계):
- **읽기/쓰기 아키텍처 = (a) 프론트 직접 Supabase**(publishable 클라 + 로그인 세션 JWT). 백엔드 무변경·service_role 0. login/계정메뉴가 이미 쓰는 `window.supabase.createClient(url, publishable)` 재사용. RLS가 권한 강제.
- **RLS**: SELECT=로그인 전체(`to authenticated using(true)`), INSERT/UPDATE/DELETE=admin만(`(auth.jwt()->'app_metadata'->>'role')='admin'`). auth.py의 app_metadata.role 판정과 정합.
- **스키마**: 단일 표 `pattern_meta{pattern_id text PK(=폴더명=/api/patterns id), is_favorite bool default false, category text(override, null이면 파생값 사용), updated_by uuid, updated_at timestamptz}`.
- **자동분류 = 키워드 사전 파생(프론트)**: 패턴명에서 옷종류 키워드(농구/야구/배구/축구/슈팅저지/라운드반팔/하의…) 매칭→category. 무매칭=미분류. 관리자 override는 Supabase에 저장. **유효 카테고리=override ?? 파생**. 기존 2개(농구_U넥/V넥)=이름파생 "농구"로 즉시 커버(마이그레이션 0). Drive 최상위폴더 캡처(정확도↑)는 create_pattern/from-drive 수정 필요 → **후속 단계로 미룸**.
- **등록패턴 파일 영속화 = 이번 범위 제외(별도 Phase B)**: preset 폴더가 작음(U넥 20KB·V넥 88KB, SVG는 정규화 path). Storage 백업 가능하나 백엔드 변경 수반. 이번엔 **메타만** 저장. 재배포 소실 시 from-drive 재등록으로 복구(Drive=원본), 같은 이름 재등록 시 pattern_id 동일→메타 자동 재부착.

📍 만들 위치: webapp/static/screens/patterns.html + work.html (프론트만·추가) + docs SQL 1장(사용자 1회 실행).

📋 실행계획(각 독립 커밋, 최대 6):
| 순서 | 작업 | 담당 | 선행 |
|------|------|------|------|
| 1 | Supabase SQL(표+RLS) 문서 작성 → **사용자가 SQL Editor 1회 실행** | developer(문서)+사용자(실행) | 없음 |
| 2 | 프론트 공용 메타 유틸(getSupaClient·fetchMeta·deriveCategory·isAdmin) + patterns.html 목록에 카테고리 필터/그룹 + 별표 읽기표시 | developer | 1 |
| 3 | patterns.html 쓰기(admin): 별표 토글·카테고리 지정 upsert(RLS 이중방어·UI admin 게이트) | developer | 2 |
| 4 | work.html step1: 즐겨찾기 상단+카테고리 필터(선택흐름 무변경) | developer | 2 |
| 5 | tester+reviewer 병렬(권한/오프라인폴백/회귀) | tester+reviewer | 3,4 |

⚠️ developer 주의: 기존 renderPatternGrid/renderPatterns/loadPatterns=확장만(교체 금지). Supabase 실패·로컬 미설정=파생카테고리+별표없음으로 degrade(기본 목록 정상). 별표 쓰기 UI는 admin에게만 노출+RLS 이중. var(--*)·Material Symbols(star/star_border). apiFetch·기존 card/badge/seg/chip 재사용.

## 구현 기록 (developer) — 즐겨찾기 + 자동분류 프론트 [2026-07-07]

📝 구현한 기능: 등록패턴을 **옷 종류 카테고리로 묶고 별표(즐겨찾기)** 를 달아 전 직원이 공유·열람. 저장=**Supabase pattern_meta 표에 프론트가 로그인 세션으로 직접 read/write**(백엔드 키리스 무변경). patterns.html=관리자 정리 화면(별표 토글·카테고리 변경·필터), work.html=직원 선택 화면(즐겨찾기 상단+카테고리 필터, 읽기 전용). 빌드0·var(--*)·Material Symbols(star/star_border).

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| webapp/static/screens/patterns.html | PM CSS(+필터바/별표/select) · #pmFilterBar 마크업 · openDriveScanFolder path 캡처 · registerFromDrive 성공 시 카테고리 upsert · PM JS블록(유틸+렌더감싸기+admin쓰기) | 수정(추가 377/삭제 1) |
| webapp/static/screens/work.html | PM CSS(필터바) · #pmWorkFilterBar 마크업 · PM JS블록(읽기전용 유틸+렌더/showPanel 감싸기) | 수정(추가 180/삭제 0) |

🔑 재사용한 Supabase 클라 방식(계정메뉴 initAccount 그대로): `fetch('/api/public-config')`→`{auth_required, supabase_url, supabase_publishable_key}`→`window.supabase.createClient(url, publishable)`. 세션은 supabase-js SDK가 localStorage에 보관 → `.from('pattern_meta').select/upsert`가 로그인 JWT 자동 첨부(SELECT=전원, upsert=관리자만 RLS 통과). role 판정=`sb.auth.getUser()` → `user.app_metadata.role==='admin'`(auth.py와 정합). **SECRET 미사용·publishable만**. 클라는 pm 전용 캐시(pmSupaClient)로 1회 생성.

🧩 공용 유틸(양 화면 인라인): `pmGetSb()`(캐시·실패/미설정=null degrade) · `pmLoadMeta()`(select→{pid:{is_favorite,category}} 맵, 실패=빈맵) · `pmIsAdmin()`(patterns만) · `pmUpsertMeta(pid,patch)`(patterns만, {ok}/{ok:false,error}) · `pmCatOf(p,map)`=**저장값 ?? 이름최선매칭 ?? 미분류** · `pmMatchKnownCategory`(PM_KNOWN_CATEGORIES 구체키 우선) · `pmCleanCategoryLabel`("숫자. " 접두 제거+공백정리) · `pmCategoryFromPath`(경로 "A › B › C"→최상위폴더→키워드정규화).

🎯 카테고리 결정(드라이브 폴더 트리 기준): **캡처 지점=registerFromDrive 성공 시**. openDriveScanFolder에서 driveSelectedFolder에 `path` 추가 보존 → registerFromDrive 시작 시 지역변수 pmCapturedPath로 붙잡음(비동기 중 변경 방어) → 성공 dict의 body.pattern_id + pmCategoryFromPath(path)로 `upsertMeta(pattern_id,{category})`. 최상위폴더 "0.농구"→"농구"(숫자접두 제거+키워드매칭). **from-drive는 admin전용이라 호출자=관리자→RLS 통과**. 트리 탭 등록은 path 없음→카테고리 upsert 생략(이름파생 폴백). 기존 로컬 농구_U넥/V넥(path·저장값 없음)=이름에 "농구"→"농구"로 자동 커버.

🔧 기존 렌더 '감싸기'(교체 금지 준수): `renderPatternGrid`/`reloadPatterns`(patterns), `renderPatterns`/`showPanel`(work)를 원본 캡처 후 `함수=function(){orig.apply(...); pm후처리();}`로 재대입. 원본 본문 0줄 수정. pm후처리=카드에 별표+카테고리 덧대기(.pm-added, 재렌더마다 제거 후 재부착=중복0)+필터바 빌드+표시/정렬(즐겨찾기 우선, 안정정렬). **pm후처리는 renderPatternGrid를 절대 재호출 안 함(무한루프 방지)**.

🖼️ UI: (patterns) 목록 위 카테고리 칩(전체·<카테고리>·미분류 count)+즐겨찾기만 토글 / 카드 좌상단 별표(admin=클릭 upsert 토글·낙관적갱신+실패원복토스트, 비admin=fav일때만 표시) / 카드 하단 카테고리(admin=select[사용중∪알려진∪미분류∪현재+직접입력]→upsert, 비admin=badge). (work) 패턴선택 step0 위 카테고리 칩 + 카드에 별표(표시)+카테고리 배지, 즐겨찾기 상단 정렬. **선택흐름(patternId)·stepper·기존 카드/클릭이동/수정삭제 무변경(덧댐만)**.

🛡️ degrade: pmGetSb=null이면 pmLoadMeta={}, pmIsAdmin=false → 별표 없음·카테고리는 이름파생/미분류·필터칩은 파생값으로 구성(직원도 스캔 없이 열람). upsert는 미설정 시 no-op. `.pm-filterbar.hidden{display:none}`은 `.hidden !important`와 중복(무해, 의도명시).

💡 tester 참고:
- **테스트 방법**: 배포/로컬 로그인 후 patterns/work 진입. Supabase pattern_meta 표+RLS가 사용자 SQL로 생성돼 있어야 쓰기 검증 가능(미생성 시 degrade만 확인).
- **정상 동작**: (1) 카테고리 칩으로 그룹 필터·즐겨찾기만 토글. (2) 관리자=별표 클릭 시 즉시 채워짐+DB저장, 카테고리 select 변경 시 저장+토스트. (3) 비관리자=별표/카테고리 표시만(쓰기 UI 없음), 별표 없는 카드엔 빈별 미노출. (4) work step1=즐겨찾기 패턴 맨 위+카테고리 칩, 선택→다음 흐름 그대로. (5) 스캔카드로 등록→목록에 그 옷종류 카테고리 배지.
- **꼭 볼 검증 포인트**: ①카테고리 그룹/필터(전체/특정/미분류·빈결과 안내) ②별표 admin쓰기/전원읽기 ③**RLS 이중**(비관리자가 콘솔로 upsert 시도→거부, UI엔 애초 버튼없음) ④**degrade**(Supabase 미설정/로컬→목록·선택·작업 안 깨짐, 이름파생 카테고리) ⑤**트리회귀0**(드라이브 트리 탐색·미리보기·등록 그대로) ⑥**work 선택흐름 무변경**(patternId·stepper·프리셀렉트·자동첫선택) ⑦**캡처**(스캔카드 등록→pattern_meta.category=최상위폴더, 트리등록은 이름파생) ⑧낙관적갱신 실패 시 원복+토스트.
- **주의 입력**: 폴더명/카테고리에 `<>&"'`(esc/driveEsc 확인, select 옵션·배지). 카테고리 select "직접 입력…" 취소. 저장된 카테고리 사라진 뒤 필터(전체로 리셋). updated_by 컬럼(내가 안 채움=null 전송, NOT NULL 제약/트리거 있으면 upsert 실패 가능→실제 표 스키마 확인 요망).

⚠️ reviewer 참고:
- 봐줬으면 하는 부분: (1) **기존 렌더 감싸기(재대입)** 안전성 — renderPatternGrid/reloadPatterns/renderPatterns/showPanel 원본 본문 무수정, 초기 동기 호출(patterns 593줄=원본, 이후 async=감싼버전) 타이밍. (2) **캡처 정확성** — driveSelectedFolder.path 보존이 트리경로(path없음)·경쟁가드(id비교)에 무영향인지. (3) **RLS 이중방어** — 쓰기 UI가 pmAdmin에게만, upsert는 관리자만 성공, 등록캡처는 from-drive(admin전용)에서만. (4) **degrade 완전성** — 미설정/실패 전 경로에서 목록·선택·작업 무손상. (5) 카테고리 정규화(catOf 우선순위·드라이브캡처 vs 이름파생 일관성).
- **결정한 것(리뷰 판단 요망)**: 카테고리 라벨=`pmCategoryFromPath`가 최상위폴더를 "숫자접두 제거+알려진키워드로 정규화"(예 "0.농구"→"농구"). 기획서 예시 "농구유니폼"과 달리 키워드로 수렴시켜 이름파생("농구_U넥"→"농구")과 **일관성** 확보를 우선함. 관리자가 select→직접입력으로 임의 라벨 교정 가능. PM_KNOWN_CATEGORIES 목록 조정으로 라벨 정밀도 변경 가능.

🧪 developer 자체검증(정적): new Function 파싱 **문법0**(patterns 인라인1742줄·work 1377줄). 신규 pm함수 각 1회 정의·모든 pm참조 정의됨(MISSING=dataset속성/DOM id 오탐). **신규 하드코딩 색상 0건**(추가라인 hex/rgb/named 0, var(--*)·color-mix(var(--paper))만). 사용 CSS변수 11종 존재 확인. diff=추가556/삭제1(삭제1=openDriveScanFolder에 path필드 추가한 그 1줄). **런타임 브라우저/실 Supabase 왕복은 tester 몫**.

### 테스트 결과 (tester) — 즐겨찾기+자동분류 프론트 [2026-07-07]
검증 방식: **jsdom 실DOM 하니스**(patterns/work.html 통째 로드 + 인라인 스크립트 실제 실행, `window.supabase.createClient`·`/api/public-config`·`/api/patterns`·`/patternfiles`·`/from-drive`·`pattern_meta select/upsert` 전부 스텁, 네트워크0) + **정적 diff 회귀검증** + **실서버 스모크**(uvicorn 8231, 로컬 무인증). 6 하니스 = **113 assert**.

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| 1. 인라인 문법0 (patterns/work) | ✅ 통과 | new Function 파싱 OK(1741·1376줄) + jsdom 4경로(degrade/admin/member) 런타임 JS에러0 |
| 2. **degrade(핵심)** | ✅ 통과 | ①auth_required=false ②select 실패 ③CDN(window.supabase) 미로딩 ④빈목록 — 전 경로 목록·필터·선택·작업 정상(안깨짐)·별표없음·이름파생/미분류 카테고리·upsert no-op |
| 3. 카테고리 그룹/필터 | ✅ 통과 | 전체/특정/미분류/빈결과 안내. distinct칩·카운트·override반영(야구_져지=커스텀A). 미분류 항상 마지막. category=metaMap.category ?? 이름파생 ?? 미분류 |
| 4. 별표 읽기(전원) | ✅ 통과 | metaMap.is_favorite 반영(is-fav star). member/degrade도 fav 카드만 별 표시(비-fav readonly 숨김) |
| 5. **별표 쓰기(admin만)** | ✅ 통과 | admin=토글+upsert{is_favorite}·onConflict=pattern_id·낙관적갱신·**실패시 원복+토스트**. **member/degrade=쓰기UI 미노출**(select0·별표 readonly·클릭시 upsert0). 카테고리 select변경·**직접입력(prompt)**·변경실패 원복도 확인 |
| 6. 캡처(scan등록→분류) | ✅ 통과 | openDriveScanFolder path보존→registerFromDrive 성공시 upsertMeta(서버 pattern_id,{category:최상위폴더파생"농구"}). 트리경로(path없음)=upsert 생략 |
| 7. **트리 회귀0(핵심)** | ✅ 통과 | 정적diff **삭제=patterns 1줄뿐**(openDriveScanFolder path필드 추가, work 삭제0). renderPatternGrid/reloadPatterns/renderDrivePreview/트리함수 **본문 0줄 변경**(hunk 미접촉)=감싸기(재대입)만. 등록카드 수정/삭제버튼·별표 stopPropagation·본문클릭→work네비 기존동작 유지 |
| 8. **work 선택흐름 무변경(핵심)** | ✅ 통과 | 카드클릭→patternId 선택이동(is-selected/체크아이콘)·네비없음·stepper(goTo step1↔0 패널토글)·필터바 step0에서만·sessionStorage 프리셀렉트 1회성 소비·자동첫선택. 재렌더 후 별표/배지 데코 유지(중복0) |
| 9. 하드코딩 색상0 | ✅ 통과 | 추가라인 hex/rgb/hsl/named 0건·var(--*)/color-mix만 |
| E. XSS 이스케이프 | ✅ 통과 | 카테고리에 `"><img onerror>` 주입→img/onerror 요소0(select value·칩·배지 driveEsc/esc/textContent). 리터럴 보존 |
| E. 실서버 스모크 | ✅ 통과 | health200·patterns200(125KB)·work200(90KB)·public-config auth_required:false·**서빙본==소스본 동일**·PM 식별자 서빙. 종료=포트8231 PID로만(node 미영향) |

📊 **종합: 113 assert 전통과 / 0 실패** (문법6+patterns42+work24+색/esc/파생19+엣지18+카테고리원복4) + 정적diff회귀 + 서버스모크. **치명결함0·회귀0 → 커밋 가능.**

🔒 특히 **degrade**(미설정/select실패/CDN미로딩/빈목록 전부 목록·선택·작업 무손상), **트리 회귀0**(삭제 1줄=path추가뿐·기존 렌더/트리 함수 본문 무수정=순수 감싸기), **work 선택흐름 무변경**(patternId·stepper·프리셀렉트·자동첫선택 그대로, 즐겨찾기 상단/카테고리 필터는 표시 껍데기만) 확실히 검증.

🟡 관찰(차단 아님·라이브 전용 확인 요망):
- **updated_by 컬럼**: pmUpsertMeta row=`{pattern_id,updated_at,...patch}`만 전송(updated_by 미포함=NULL). 아키텍트 스키마 nullable이라 정상 예상이나, 실배포 표 생성 후 **첫 별표/카테고리 저장 1회로 실확인 권장**(NOT NULL·트리거 있으면 실패 가능·dev도 플래그).
- **RLS 실거부**는 표+정책 생성 후 라이브에서만 확정. 로컬은 UI 게이트+호출로직만 검증(task 명시).
- (참고, 회귀 아님) "auth_required=true인데 supabase-js CDN 미로딩" 병리 조합에서 **기존 initAccount(diff 밖)**가 `window.supabase.createClient` 참조로 예외 — PM 무관(pmGetSb는 `!window.supabase` 가드로 정상 degrade). login/계정메뉴도 불가한 상태라 실사용 시나리오 아님.

### 리뷰 결과 (reviewer) — 즐겨찾기+자동분류 프론트 [2026-07-07]
📊 **종합 판정: 통과** (치명 0 · 회귀 0 · 제약위반 0). diff +556/−1(patterns 377/1·work 180/0). 정적 정독 검증(코드/식별자/DOM구조/호이스팅/이스케이프/CSS변수). **커밋 가능.** 런타임 실Supabase 왕복은 tester 몫.

✅ 잘된 점:
- **보안 이중게이트 정합**: 프론트는 `cfg.supabase_publishable_key`만 사용(SECRET/service_role 참조 0, grep 확인). isAdmin=`sb.auth.getUser()`의 app_metadata.role(서버만 쓰는 영역·JWT 위조는 Supabase 서명키 없이는 불가) → **UI 게이트는 UX용**, 실제 강제는 RLS. 비관리자는 pmAdmin=false→읽기전용 별표(쓰기 리스너 없음)·배지(select 없음). 콘솔로 upsert 시도해도 RLS 거부 + 낙관적 원복이 안전 처리. upsert는 supabase-js가 세션 JWT 자동첨부→RLS(admin) 통과/거부 구조 정합. work.html은 SELECT만(upsert 없음) 확인.
- **트리/기존 회귀 0**: 삭제 1줄=`driveSelectedFolder={id,name}`→`{id,name,path}`(path 추가뿐). id 비교 경쟁가드·renderDrivePreview(id/name만 읽음)에 무영향, 트리 경로(selectDriveFolder)는 path 미설정→pmCapturedPath=null→카테고리 upsert 생략(이름파생 폴백)=설계대로. renderPatternGrid/reloadPatterns/renderPatterns/showPanel 전부 함수선언(재대입 합법)을 원본캡처 후 감싸기, 원본 본문 무수정. `.pm-added`는 매 후처리 시 remove 후 재부착→리스너/노드 누수·중복 0. 카드 기본 클릭리스너는 render 시 1회만 부착(pm은 안 건드림). work 선택흐름(patternId·update·stepper·프리셀렉트) 무변경(읽기전용 덧댐만).
- **초기화 타이밍 안전**: 감싸기(patterns 2254·work 1510)는 동기 실행, 이후 모든 렌더 호출부(patterns 645/1187·초기 630은 원본으로 빈그리드, work 1341/1522/1527/1533 loadPatterns)는 전역 이름참조라 콜백(async) 시점엔 감싼 버전 해석. 메타/패턴 로드 순서 무관하게 최종 pmAfterRender 수렴. registerFromDrive(1647)가 뒤에 정의된 pmCategoryFromPath/pmUpsertMeta 호출=둘 다 함수선언(호이스팅)+런타임(클릭) 호출이라 TDZ/순서문제 없음.
- **degrade 완비**: pmGetSb=미설정/실패/로컬(auth_required=false)→null→pmLoadMeta={}, pmIsAdmin=false. 별표 없음·카테고리는 이름파생/미분류·필터칩은 파생값 구성. 목록·필터·선택·작업 전부 생존. upsert=미설정 시 {ok:false} no-op.
- **카테고리 로직 일관**: catOf=저장값 ?? pmMatchKnownCategory(이름) ?? 미분류. 캡처(scan path 최상위)·이름파생 **둘 다 pmMatchKnownCategory로 수렴**("0.농구"→접두제거→"농구", "농구_U넥"→"농구") = 라벨 일관. 관리자 select→직접입력으로 override(prompt 취소 시 재렌더 원복). 미분류 항상 맨 뒤·사라진 필터값은 전체로 리셋.
- **이스케이프/제약**: patterns=driveEsc(&<>"' 전부), work=esc(&<>" — 작은따옴표 미포함이나 사용처가 전부 쌍따옴표 속성/textContent라 XSS 무해). 배지=textContent(자동), select 옵션 value/text·칩 data속성=esc 후 getAttribute 디코딩 왕복 정확. 하드코딩 색상 0(추가라인 grep 0, 전부 var(--*)/color-mix(var(--paper))). 사용 CSS변수(--brand=--stiz-red·--paper·--surface-active·--surface-card·--border-strong 등) 전부 tokens/colors.css 존재. Material Symbols(star/star_border). 빌드0·webapp/static 2파일·백엔드/엔진/기존기능 무변경. 낙관적 갱신=실패 시 원복+토스트 확인. 별표 카드 앵커=이미지영역(children[0]) `position:relative` 존재→absolute 별표 정위치.

🔴 필수 수정: **없음**

🟡 권장(선택, 차단 아님):
- (updated_by 스키마) upsert row에 updated_by 미포함(null). planner 설계=nullable이라 정합이나, 사용자가 실행하는 SQL 표가 updated_by NOT NULL이면 쓰기 실패(단 원복+토스트로 안전 degrade, 데이터 손상 아님). SQL 문서와 nullable 일치 1회 확인 권장.
- (이중클릭/경쟁) 별표·카테고리 낙관갱신에 처리중 disabled/debounce 없음. 빠른 연속 클릭 시 마지막 upsert 승리(idempotent)하나 응답 순서 역전 시 UI-DB 순간 불일치 가능(저위험). 여력 시 처리중 별표 disabled 가드.
- (후처리 try/catch) 렌더 감싸기가 pmAfterRender를 try/catch 없이 이어붙임. 현 후처리는 방어적(grid/children/nameBlock 전부 존재가드)이라 예외경로 없음(무해). 완전 degrade를 원하면 후처리 try/catch로 감싸면 원본 render 성공을 pm 예외로부터 절연.
- (work esc 작은따옴표) 현재 안전. 향후 작은따옴표 속성에 재사용 시 위험 — 지금은 무해(인지만).

### 기획설계 — 패턴 폴더 자동 스캔(카드 그리드) [2026-07-07 planner-architect]

🎯 목표: 깊은 트리를 일일이 안 펼쳐도 "등록 가능한 패턴 폴더"를 자동 발견해 카드 그리드로 노출, [등록]→기존 미리보기/등록 재사용.

📍 만들 위치와 구조:
| 파일 | 역할 | 신규/수정 |
|------|------|----------|
| webapp/gdrive.py | list_all_folders / list_all_pattern_files 2헬퍼(벌크·페이지네이션·기존 재시도패턴) | 수정(추가만) |
| webapp/api.py | GET /api/drive/scan(admin) + 스캔빌더(폴더맵·부모그룹핑·경로·루트스코프) + 메모리 TTL캐시+Lock | 수정(추가만) |
| webapp/static/screens/patterns.html | driveMode 세그먼트토글[자동찾기|트리] + 카드그리드 + 카드→미리보기 배선 + renderDrivePreview(panel) 파라미터화 | 수정 |

🔗 기존 연결: 카드[등록]→기존 renderDrivePreview({id,name})→/patternfiles(정확)→registerFromDrive→/from-drive(정확 재스캔). **벌크 스캔=발견 전용, 등록은 기존 정확경로가 결정**(근사 오차 무영향).

📋 실행 계획(4단계·각 독립 커밋):
| 순서 | 작업 | 담당 | 선행 |
|------|------|------|------|
| 1 | gdrive.py 헬퍼 2개(list_all_folders/list_all_pattern_files) | developer | 없음 |
| 2 | api.py GET /api/drive/scan + 스캔빌더 + TTL캐시 | developer | 1 |
| 3 | 프론트 세그먼트토글+카드그리드(fetchDriveScan·로딩/빈/오류·새로고침) | developer | 2 |
| 4 | 카드→미리보기→등록 배선(renderDrivePreview(panel) 파라미터화) | developer | 3 |
| 각 단계 후 | tester + reviewer 병렬 | tester/reviewer | 해당 단계 |

⚠️ developer 주의:
- 파일쿼리는 `name contains '.ai'` **금지**(Drive는 토큰 prefix매칭이라 누락위험)→전 비폴더 파일 fetch 후 `_PATTERN_FILE_EXTS` endswith 서버필터.
- 벌크스캔에서 폴더당 list_children 재호출 금지(그게 느림의 원인)→부모별 그룹핑으로 처리.
- 루트스코프: GDRIVE_ROOT_FOLDER_ID 자손만(조상추적), 체인 끊긴 폴더 제외.
- 사이즈판정=기존 `_parse_size_from_filename`·`_is_temp_or_aux_file`·`_SIZE_RANK` 재사용(복제 금지).
- renderDrivePreview/registerFromDrive는 patternel 파라미터화로 트리 #drivePanel과 ID충돌 방지(최소·하위호환).
- 미설정/403/오류/빈결과=classifyDriveRes+driveEmptyHtml 재사용. var(--*)·Material Symbols·admin전용·Drive읽기전용·--workers1·비밀키0.

## 구현 기록 (developer) — 패턴 폴더 자동 스캔 백엔드 (계획 1·2단계) [2026-07-07]

📝 구현한 기능: 드라이브를 재귀 없이 **벌크 2쿼리**로 훑어 '등록 가능한 패턴 폴더'를 찾아주는 `GET /api/drive/scan`(발견 전용·admin). 화면 변화 없음(서버만). 등록은 기존 정확 경로(/patternfiles→/from-drive)가 그대로 결정.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| webapp/gdrive.py | 대량조회 헬퍼 2개 추가(list_children 뒤·download_file 앞) | 수정(추가만) |
| webapp/api.py | `import time` 1줄 + drive 섹션 끝(from-drive 뒤)에 캐시상수·`_scope_path`·`_build_drive_scan`·`GET /drive/scan` | 수정(추가만) |

**gdrive.py 추가 함수**(둘 다 list_children와 동일 안전패턴: get_service→try밖 / _call_with_retry 페이지단위 재시도·items유지 / supportsAllDrives·includeItemsFromAllDrives·corpora=allDrives·pageSize=1000·nextPageToken 전수 / 실패=DriveError):
- `list_all_folders()` q=`mimeType='폴더' and trashed=false`, fields=`id,name,parents` → `[{id,name,parents(없으면[])}]`
- `list_all_pattern_files()` q=`mimeType!='폴더' and trashed=false`(**폴더만 제외, name contains 안 씀**), fields=`id,name,parents,mimeType` → `[{id,name,parents,mimeType}]`

**api.py 추가**(전부 drive 섹션 끝, 라인 ~1663 이후):
- 캐시: `_SCAN_CACHE`(root_folder_id별 `{result,ts}`) + `_SCAN_CACHE_LOCK`(threading.Lock) + `_SCAN_CACHE_TTL=300.0` + `_SCAN_MAX_DEPTH=30`. 락 안에서 캐시확인·재스캔 한 덩어리 → **동시 중복 스캔 방지**. refresh=True거나 TTL만료면 재스캔.
- `_scope_path(pid,fmap,root)` → `(in_scope, path_names)`: pid→부모→…→root까지 올라가 자손판정+경로. visited집합+MAX_DEPTH로 사이클/과깊이 방어. 사슬 끊김/루트 못만남=제외.
- `_build_drive_scan()`: ①folders→`fmap{id:{name,parent}}` ②files→임시(`_is_temp_or_aux_file`)·확장자(`_PATTERN_FILE_EXTS` splitext) 필터 후 `by_parent{pid:[names]}` ③부모별 `_parse_size_from_filename`으로 사이즈집합(None제외)→**1개이상이면 채택** ④루트스코프+경로 ⑤이름없으면 제외 ⑥sizes `_SIZE_RANK`로 작은→큰 정렬 ⑦path→name 정렬. **기존 헬퍼 전부 재사용(복제0)**.
- `GET /drive/scan?refresh:bool=False` (admin): 미설정=200 `{configured:false,message}` / DriveConfigError=500 / DriveError=502 (tree와 동일 규약).

📦 응답 shape: `{configured:true, cached:bool, scanned_at:epoch초, count:int, folders:[{id,name,path("A › B › C"),size_count,sizes:["XL","2XL",...]}]}`

💡 tester 참고:
- **테스트 방법**: 네트워크 없이 `webapp.api`/`webapp.gdrive` import 후 `gdrive.list_all_folders/list_all_pattern_files/root_folder_id/is_configured`를 가짜로 몽키패치 → `api.drive_scan(refresh=...)` 직접 호출(JSONResponse.body를 json.loads). (developer가 이 방식으로 자체검증 통과.)
- **정상 동작**: 사이즈파일 든 루트-자손 폴더만 folders에 뜸. path=루트 바로 아래부터 폴더까지 breadcrumb(" › "). sizes는 작은→큰. cached: 1차 False→2차 True(scanned_at 동일)→refresh=True면 False로 재스캔.
- **주의 검증 포인트**: ①폴더맵 경로조립(깊은 사슬) ②확장자 필터(.txt/이미지 제외, .ai/.pdf/.svg만) ③사이즈판정(사이즈0인 폴더 미채택·임시 ~/.tmp 제외·사이즈 미상 파일은 집합 기여X) ④루트스코프(부모 사슬 끊긴 폴더·**사이클 폴더** 제외) ⑤캐시(TTL·refresh·root별 분리·동시성 Lock) ⑥미설정 configured:false / DriveError 502 / DriveConfigError 500.
- developer 자체검증: 가짜 트리(root>0.농구>단면>U넥>스탠다드-A + 떠돌이/사이클/빈/잡폴더)로 count=1·path·sizes[XL,2XL,3XL]·cached 전이·502/500·configured:false 전부 단언 통과. py_compile 통과.

⚠️ reviewer 참고:
- 봐줬으면 하는 부분: (1) `_scope_path` 사이클/과깊이 방어와 루트 도달 판정(root가 fmap에 있든 없든 안전한지). (2) 캐시 락 범위 — 느린 벌크 스캔을 락 안에서 돌려 동시요청을 직렬화(의도=중복 스캔 방지)한 트레이드오프. (3) 벌크 pageSize=1000·corpora=allDrives 조합이 공유드라이브 전 폴더/파일 커버하는지(list_children는 200이었음). (4) DriveConfigError/DriveError를 `with _SCAN_CACHE_LOCK` 밖 except로 잡아 락이 확실히 풀리는지.

## 구현 기록 (developer) — 패턴 폴더 자동 스캔 프론트 (계획 3·4단계) [2026-07-07]

📝 구현한 기능: `#driveMode` 안에 **[자동 찾기 | 폴더 트리] 탭**을 넣고, 기본 탭 **자동 찾기**에서 `GET /api/drive/scan` 결과를 **카드 그리드**로 노출. 카드/[등록] 클릭 → 미리보기 서브뷰(2단계 마법사) → **기존 renderDrivePreview/registerFromDrive 그대로 재사용**. 트리 탭은 기존 마크업·동작 무변경(감싸기만). 파일 1개(patterns.html) 수정. 빌드0·var(--*)만·Material Symbols.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| webapp/static/screens/patterns.html | 탭+자동찾기 카드그리드+카드→미리보기 배선 + renderDrivePreview panel 인자화 + registerFromDrive 활성패널 스코프 + 소량 CSS | 수정 |

🔧 변경 상세(위치·방식):
- **CSS(<style> 끝, ~170줄)**: `#driveTabs{align-self:flex-start}`(세로 flex서 .seg 가로 안 늘어나게)+탭 아이콘 정렬 + `@media(max-width:720px){#driveScanGrid.grid-3{1fr}}`(좁은 화면 1열). 신규 클래스 없이 기존 `.seg`/`.grid-3`/`.card`/`.badge`/`.empty`/`.spinner` 재사용.
- **마크업(#driveMode, ~352줄)**: 상단 `.seg#driveTabs`(auto_awesome 자동 찾기·account_tree 폴더 트리, 활성=is-active). `#driveScanView`={카드목록 `#driveScanList`(툴바 `#driveScanMeta`+`#btnDriveScanRefresh` / 격자 `#driveScanGrid`) + 미리보기 `#driveScanPreviewWrap`(뒤로 `#btnDriveScanBackToList` + `.drivewrap__panel>#driveScanPreview`)}. **기존 트리 `.drivewrap`(좌 #driveTree+우 #drivePanel)는 한 글자도 안 바꾸고 `#driveTreeView`로 감싸기만**.
- **탭 전환 `showDriveTab(which)`**: 두 뷰 상호배타 토글+탭 is-active. **전환 시 공유전역 driveSelectedFolder=null + 트리 하이라이트 해제 + `driveScanShowList()`(=미리보기 닫고 #driveScanPreview 비움) + 상대 패널 비우기**(스캔탭→ #drivePanel.innerHTML=""; 트리탭→ loadDriveRoot 가 renderDrivePreview(null) 로 #drivePanel 안내만). 스캔탭은 `driveScanLoaded` false일 때만 loadDriveScan(재전환 시 재요청 안 함).
- **진입 `showDriveMode`**: 기존 `loadDriveRoot()` 직접호출 제거 → `driveScanLoaded=false; showDriveTab("scan")`(기본=자동찾기). 트리 루트로드는 트리탭 눌렀을 때만.
- **`fetchDriveScan(refresh)`**: `apiFetch('/api/drive/scan'+(refresh?'?refresh=1':''))` → `{ok,status,body}` 정규화(fetchDriveTree 동일 패턴).
- **`loadDriveScan(refresh)`**: (A)로딩 `.spinner`+"드라이브를 스캔하는 중…(수 초)" → classifyDriveRes 4갈래(미설정 cloud_off/403 lock/500·502 error+다시시도 `#driveScanRetry`)→정상 renderDriveScanCards. grid.className 을 로딩/빈/오류=""·카드=grid-3 로 토글. 성공 시 driveScanLoaded=true.
- **`renderDriveScanCards(body)`**: 툴바 `driveScanMetaHtml(count,body)`(방금/ N분 전/ N시간 전 + cached면 "(캐시)", scanned_at·Date.now()로 계산·외부문자열 없음). folders 0개=driveEmptyHtml("search_off",…파일명 사이즈/공유 확인). 있으면 `driveScanCardHtml` map→grid-3. 카드 클릭 위임(data-scan-idx→openDriveScanFolder).
- **`driveScanCardHtml(f,i)`**: `.card.card--interactive`=①folder아이콘+폴더명(driveEsc·말줄임) ②`badge badge--info badge--sm` "N 사이즈"(size_count) ③경로 캡션(path driveEsc·word-break) ④`btn btn--primary btn--sm` [등록](버튼 클릭도 카드로 버블 → 한 번만 호출).
- **카드→미리보기 `openDriveScanFolder`**: driveSelectedFolder={id,name} → driveScanShowPreview() → **`renderDrivePreview(driveSelectedFolder, $("#driveScanPreview"))`**.
- **`renderDrivePreview(folder, panelEl)` 파라미터화**: `const panel = panelEl || $("#drivePanel")`(기본=기존 트리패널=회귀0). 내부 재시도 콜백 2곳 `renderDrivePreview(folder)`→`(folder, panel)`. renderDrivePreviewBody(panel,…)는 이미 panel 인자+버튼 panel.querySelector 라 무수정.
- **`registerFromDrive` 활성패널 스코프**: 신규 `activeDrivePanel()`(scanPreviewWrap 보이면 #driveScanPreview, 아니면 #drivePanel) 도입 → #driveName/#driveBaseSize/#btnDriveRegister 를 `document.getElementById`→`panel.querySelector`로. **트리 경로선 activeDrivePanel=#drivePanel 반환 → 결과 동일(회귀0)**.

💡 tester 참고:
- **테스트 방법**: 배포/로컬 로그인(admin)→패턴 관리→[드라이브에서 등록] 진입.
- **정상 동작**: 진입 시 **자동 찾기 탭 활성 + 카드 그리드**(툴바 "N개 패턴 폴더 · 방금 스캔"). 카드 [등록]/본문 클릭 → 미리보기 서브뷰(사이즈칩·이름·기준사이즈·[이 폴더로 패턴 등록]) → 등록 성공 시 토스트+목록복귀. [폴더 트리] 탭 → 기존 트리 탐색 100% 동일. [새로고침]=재스캔(refresh=1). "← 패턴 폴더 목록"=카드목록 복귀.
- **꼭 볼 검증 포인트**: ①탭 상호배타(한쪽만 보임) ②카드 렌더/개수/최신성 ③[새로고침] 재요청 ④카드→미리보기→등록 왕복(스캔 경로) ⑤**트리 회귀0**(트리 폴더선택→미리보기→등록 그대로) ⑥**입력칸 중복 없음**(탭·서브뷰 오가도 등록이 항상 현재 보이는 폴더 기준. 스캔서 폴더A 열고→트리 탭→트리서 폴더B 등록 시 B로 등록되는지) ⑦빈결과(folders 0)·미설정(configured:false cloud_off)·403 lock·500/502 error+다시시도.
- **주의 입력**: 폴더명/경로에 `<>&"'` 포함(driveEsc 확인). count 0 vs 없음. scanned_at 오래된 값(“N시간 전”).

⚠️ reviewer 참고:
- 봐줬으면 하는 부분: (1) **#driveName ID 중복 안전성** — 탭 전환 시 상대 패널 비우기 + registerFromDrive 의 activeDrivePanel 스코프 이중방어. 실제 동시 존재 가능성/사각지대. (2) **트리 회귀0** — renderDrivePreview 기본값·selectDriveFolder(무인자 호출)·loadDriveRoot(renderDrivePreview(null)) 경로가 이전과 동일한지. (3) 카드 [등록] 버튼 클릭이 카드로 버블→openDriveScanFolder 1회만 호출(중복X). (4) driveScanLoaded 캐시 전이(진입=false 재로드, 탭 재전환=유지, refresh=강제).

🧪 developer 자체검증(정적): vm.Script 파싱 **문법오류 0**(인라인 스크립트 1404줄). 신규 함수 10개 각 def=1·참조≥2. 신규 컨테이너 id 전부 x1(중복0). renderDrivePreview 호출부 4곳 인자 의도 일치(트리=기본#drivePanel/스캔=#driveScanPreview/재시도=panel). tnum·text-body-strong·grid-3·seg·empty·spinner 전부 기존 정의 재사용 확인. **런타임 브라우저 왕복은 tester 몫**(자체검증은 정적 한계).

## 테스트 결과 (tester) — 패턴 폴더 자동 스캔 프론트 (2026-07-07)
검증 방식: **jsdom 실 DOM 하니스**(patterns.html 통째 로드+실 스크립트 실행, fetch/supabase 스텁·네트워크0) + **실서버 스모크**(로컬 uvicorn 8199, GDRIVE 미설정). 실브라우저(claude-in-chrome)는 확장연결 불확실+비결정적이라, 더 결정론적인 jsdom 실행으로 대체(실 DOM·실 이벤트·실 fetch흐름). 총 4개 하니스(문법/메인54/이스케이프5/엣지10) + 색상 grep + 실서버.

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| 1. 인라인 스크립트 문법오류 0 | ✅ 통과 | new Function 파싱 OK(1404줄) + jsdom 로드/전시나리오 후 런타임 JS에러 0 |
| 2. 탭 상호배타·진입기본=자동찾기 | ✅ 통과 | 진입 #driveScanView 보임/#driveTreeView 숨김·탭 is-active 정확. scan↔tree 전환 시 한 뷰만 표시(XOR). 재전환 시 미리보기 닫힘 |
| 2b. 탭전환 상대뷰 입력칸 비움 | ✅ 통과 | scan→tree: #driveScanPreview innerHTML="" / tree→scan: #drivePanel innerHTML="". 문서 내 #driveName 항상 ≤1 |
| 3. 카드 렌더(grid-3) | ✅ 통과 | folders3→카드3·folder아이콘·badge--info "N 사이즈"·경로캡션·[등록]btn--primary·grid-3 토글 |
| 3b. count·최신성 | ✅ 통과 | "3개 패턴 폴더 · 방금 스캔" / cached+scanned_at−300 → "5분 전 스캔 (캐시)" |
| 3c. 이스케이프(driveEsc) | ✅ 통과 | & < > " ' 5종 엔티티(raw문자열 직접확인). <img> 태그 미주입. **속성value XSS방어**(x" onload= 주입요소0·value리터럴보존) |
| 4. [새로고침] refresh=1 | ✅ 통과 | 클릭→/api/drive/scan?refresh=1 재호출 |
| 5. 카드→미리보기→등록 왕복(스캔) | ✅ 통과 | 카드클릭→서브뷰+renderDrivePreview(#driveScanPreview)렌더(칩·이름·기준XL·등록btn)→등록클릭 POST from-drive {folderId:fA,name:폴더명유래,base_size:XL}. "←목록"복귀+미리보기비움 |
| 6. **트리 회귀 0(핵심)** | ✅ 통과 | 트리탭 루트로드·#drivePanel "폴더선택"안내(renderDrivePreview(null))·selectDriveFolder→#drivePanel 미리보기(무인자 기본패널)·activeDrivePanel=#drivePanel·트리등록 folderId=t1. 기존 경로 100% 동일 |
| 7. **입력칸 중복 없음(핵심)** | ✅ 통과 | 스캔서 폴더A 미리보기(name="AAA")→트리탭 전환(스캔미리보기 비워짐)→트리서 폴더B선택·name="BBB"→등록. 결과 **folderId=t2(B)·name="BBB_트리폴더"**(A혼선0). activeDrivePanel 스코프 정확 |
| 8a. 미설정 configured:false | ✅ 통과 | cloud_off 빈상태·grid className=""·**실서버도 configured:false 확인**(로컬 GDRIVE 미설정) |
| 8b. 403 | ✅ 통과 | lock "관리자 권한"·재시도버튼 없음 |
| 8c. 500·502 | ✅ 통과 | error+다시시도버튼. 재시도 클릭→재호출+grid-3 카드복구 |
| 8d. 빈 folders | ✅ 통과 | search_off "찾지 못" 안내·grid className=""·툴바 "0개" |
| 9. 하드코딩 색상 0 | ✅ 통과 | diff 추가라인 hex/rgb/named 색 0건·var(--accent/text-*)만 사용 |
| E1. driveScanLoaded 캐시전이 | ✅ 통과 | 진입=1회로드/탭재전환(scan→tree→scan)=재요청0/재진입=재요청1 |
| E2. 카드 [등록] 버튼 버블 단일호출 | ✅ 통과 | 버튼클릭→카드로 버블→openDriveScanFolder 1회만(patternfiles 1회·중복0) |
| E3. 실서버 스모크 | ✅ 통과 | uvicorn 8199 health200·/drive/scan configured:false·patterns.html 200(신규식별자16건 서빙) |

📊 **종합: 69개 통과 / 0 실패** (문법1+메인53+이스케이프5+엣지10 = 실측 assert. 메인하니스 1건 "FAIL"은 **테스트 아티팩트**로 확인·기각: 텍스트노드에 들어간 "/'는 jsdom innerHTML 재직렬화 시 리터럴로 환원되어 &quot;/&#39; 문자열 매칭 실패—실제 driveEsc는 raw문자열·속성컨텍스트에서 정확 이스케이프됨을 esc.js가 별도 입증). **치명결함 0·회귀 0 → 커밋 가능.**

🔒 특히 **트리 회귀 0**(renderDrivePreview 무인자=기본#drivePanel·loadDriveRoot renderDrivePreview(null)·selectDriveFolder 무인자·activeDrivePanel=#drivePanel 전부 기존동일)과 **입력칸 중복 없음**(탭전환 시 상대패널 innerHTML="" 비움 + activeDrivePanel 스코프 이중방어로 스캔A→트리B 등록 시 B로 정확 등록·#driveName 항상 ≤1) 확실히 검증됨.

## 리뷰 결과 (reviewer) — 패턴 폴더 자동 스캔 프론트 (2026-07-07)
📊 **종합 판정: 통과** (치명 0 · 회귀 0 · 제약위반 0). diff +264/-20, patterns.html 1파일. new Function 파싱 문법오류 0. **커밋 가능.**

✅ 잘된 점:
- **트리 회귀 0(최우선) 확인**: `renderDrivePreview(folder, panelEl)` 기본값 `panelEl || $("#drivePanel")` → 트리 호출부 3곳(selectDriveFolder 무패널·loadDriveRoot renderDrivePreview(null)·내부 재시도 콜백 `(folder, panel)`서 panel=#drivePanel) 전부 이전과 동일 타깃. renderDrivePreviewBody(panel,…)는 원래 panel 인자라 무수정. **삭제된 20줄=기존 `.drivewrap` 블록이 `#driveTreeView`로 감싸져 재생성된 것뿐**(#driveTree/#drivePanel id 각 1개·`.drivewrap*` 클래스 선택자는 id 래퍼 무영향). loadDriveRoot/makeDriveNode/selectDriveFolder/renderDrivePreviewBody 로직 무변경.
- **입력칸 중복 이중방어 실제 유효**: 어느 순간에도 #driveName 은 한 곳만 존재 — 탭 전환 시 showDriveTab 이 상대 패널을 비운다(스캔탭→ #drivePanel.innerHTML=""; 트리탭→ driveScanShowList 가 #driveScanPreview.innerHTML=""). 스캔 흐름은 #drivePanel 에 절대 안 쓰고, 트리 흐름은 #driveScanPreview 에 절대 안 씀. 그 위에 `activeDrivePanel()`(scanPreviewWrap 보이면 #driveScanPreview, 아니면 #drivePanel)이 wrap 가시성=활성탭과 1:1로 매핑돼 registerFromDrive 가 항상 보이는 패널의 #driveName/#driveBaseSize/#btnDriveRegister 를 읽음. document.getElementById 오집음 경로 없음. (tester 관점⑥ "스캔서 A 열고→트리서 B 등록=B" 정합 확인.)
- **탭 전환 견고·리스너 누수 0**: #driveTabScan/#driveTabTree 리스너는 최상위 1회 부착(재부착 없음). 카드 리스너는 renderDriveScanCards 가 grid.innerHTML 전체 교체(구 카드+리스너 GC)→새 카드에만 부착. #btnDriveRegister 는 innerHTML 재생성마다 새 버튼에 매번 부착(누수 없음, 기존 관례). driveSelectedFolder 공유상태는 showDriveTab 에서 null 리셋+하이라이트 해제→stale 잔류 없음. 진입=driveScanLoaded false 재로드/탭 재전환=유지/refresh=강제, 전이 정확.
- **카드 [등록] 버블 1회**: 카드 내부 `<button>`은 자체 리스너 없음·파일에 `<form>` 전무(grep 0)→type 미지정이라도 submit/리로드 없음, 카드 클릭으로 버블→openDriveScanFolder 딱 1회.
- **fetch/분류/최신성**: fetchDriveScan=fetchDriveTree 동일 정규화·classifyDriveRes 4갈래 재사용·refresh=1·retry 시 원 refresh 플래그 보존. driveScanMetaHtml 은 count(숫자)+내부문구만(외부문자열 0=innerHTML 안전), 시계 역전(scanned_at 미래)도 `ageMin<=0→"방금 스캔"` 방어.
- **제약 준수**: 빌드0·하드코딩 hex 0(신규 전부 var(--*))·Material Symbols only·기존 API/인증/엔진/로컬등록/카드 무변경(추가+panel 파라미터화만)·webapp/static 1파일. 외부값(name/path/warnings) driveEsc 일관. 재사용 클래스(seg/is-active/grid-3/card--interactive/badge--info·sm/tnum/stack-4·5/row-between) 전부 기존 정의 존재.
- **엣지**: folders 0=search_off 빈상태·path 김=word-break·size_count 0(숫자)면 "0 사이즈"(백엔드 미발생·방어)·등록 성공→reloadPatterns+backToList, 재진입 시 showDriveMode 가 driveScanLoaded=false 리셋해 상태 잔류 없음.

🔴 필수 수정: **없음**

🟡 권장(선택, 차단 아님):
- (트리탭 매전환 재로드) showDriveTab("tree")는 driveScanLoaded 같은 가드 없이 매번 loadDriveRoot() 호출 → 스캔↔트리 왕복 시 루트 재fetch+펼침상태 소실. **기존 "진입마다 재로드" 동작과 동일·안전**하나, 여력 시 driveTreeLoaded 가드로 스캔탭과 대칭 맞추면 API 1회+상태 보존. (무해)
- (경로 중복 표시) 카드가 폴더명(folder 아이콘)과 path 캡션을 함께 보여주는데 path 마지막 crumb == 폴더명이라 살짝 중복(백엔드 리뷰 권고와 동일). 순수 시각, 무해.
- (a11y) role="tablist"/"tab"만 있고 aria-selected 토글·tabpanel 연결 없음. 키보드/스크린리더 나이스투해브(선택).

## 테스트 결과 (tester) — 패턴 폴더 자동 스캔 백엔드 (2026-07-07)
독립 모킹 단위검증(네트워크 0). gdrive.list_all_folders/list_all_pattern_files/root_folder_id/is_configured 를 가짜 드라이브 트리(root>0.농구>단면>U넥>스탠다드>스탠다드-A 깊이5 + 떠돌이/사이클/자기참조/과깊이60/빈폴더/루트직속/다중확장자 라운드)로 몽키패치→api.drive_scan 직접 호출. 벌크헬퍼는 가짜 Drive 서비스로 페이지네이션 직접 검증.

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| py_compile (gdrive.py·api.py) | ✅ 통과 | 둘 다 OK |
| 경로조립 깊은폴더 breadcrumb | ✅ 통과 | "0.농구 › 단면 › U넥 › 스탠다드 › 스탠다드-A"(루트 바로 아래부터·" › ") |
| 루트 포함/제외 일관성 | ✅ 통과 | path에 루트명 미포함, root가 fmap에 있든 없든 자식경로 일관 |
| 확장자 필터 .ai/.pdf/.svg만 | ✅ 통과 | .txt/.png 제외(무영향)·splitext 필터·`name contains` 미사용(전파일 fetch) |
| 사이즈 판정·정렬 | ✅ 통과 | E=[XL,2XL,3XL]·라운드=[S,M,L,XL,2XL] 작은→큰·다중확장자 혼합집계 |
| 임시/보조 제외 | ✅ 통과 | ~접두 .ai→5XL·.tmp→4XL 집계 기여0 |
| 사이즈0 폴더 미채택 | ✅ 통과 | 잡폴더(설명.pdf 토큰없음) 미채택 |
| 토큰 정확일치(오인방지) | ✅ 통과 | U넥→U, 암홀X→X 오인 없음 |
| 스코프: 떠돌이/사슬끊김 제외 | ✅ 통과 | 부모 fmap없음·부모없음 제외 |
| 사이클/자기참조/과깊이 방어 | ✅ 통과 | CYC1↔CYC2·X→X False 반환(무한루프X)·60>MAX30 크래시X |
| 캐시 1차 False→2차 True | ✅ 통과 | 2차 list_all 호출 0회 증가·scanned_at 동일 |
| refresh=true 재스캔 | ✅ 통과 | cached=False·재호출·scanned_at 갱신 |
| TTL 만료 재스캔 | ✅ 통과 | ts를 TTL+100 과거로→재스캔 |
| root별 캐시 분리 | ✅ 통과 | 다른 root 별도키·원래 root 캐시 보존 |
| 동시성(Lock) 중복방지 | ✅ 통과 | 4스레드 Barrier(벌크 sleep0.25)→벌크스캔 딱1회·1개만 cached=False |
| 미설정→200 configured:false | ✅ 통과 | message 포함 |
| DriveConfigError→500 / DriveError→502 | ✅ 통과 | tree/patternfiles 동일 규약 |
| 예외 후 Lock 해제(데드락X) | ✅ 통과 | 다음 호출 성공·non-block acquire 성공 |
| 응답 shape | ✅ 통과 | {configured,cached,scanned_at,count,folders[{id,name,path,size_count,sizes}]} |
| 벌크헬퍼 안전패턴 | ✅ 통과 | 2페이지 전수·pageSize1000·corpora=allDrives·supportsAllDrives·q(폴더만/폴더제외)·parents[] 정규화·전송에러 1회재시도 items유지 |
| 회귀 0 | ✅ 통과 | git diff 삭제 0줄(gdrive +102/-0·api +169/-0=271 전부 추가)·기존 함수 시그니처/존재 무변경 |

📊 종합: **68개 통과 / 0 실패** (drive_scan 모킹 52 + 벌크헬퍼 16). developer 자체검증 독립 재현 + 놓친케이스(다중확장자·과깊이·자기참조·root별분리·동시성) 추가검증 통과. **치명결함 없음 → 커밋 가능.**

🟡 관찰(차단 아님·저위험): root 폴더 자신이 list_all_folders에 폴더로 포함 + 루트직속에 사이즈파일이 있으면 `_scope_path(root,root)=(True,[])`라 path=""·name=루트명 카드 1장이 뜸. 실배포는 GDRIVE_ROOT_FOLDER_ID가 최상위=list_all_folders 결과에 root 자신 미포함→folder_name=""으로 조용히 제외→무해. 후속 여력 시 path=="" 카드 스킵 가드 고려 가능(reviewer 권장과 무관·별건).

## 리뷰 결과 (reviewer) — 패턴 폴더 자동 스캔 백엔드 (2026-07-07)
📊 **종합 판정: 통과** (치명 0 · 회귀 0 · 제약위반 0). diff 271줄 전부 추가(169/0·102/0)·py_compile OK. 커밋 가능.

✅ 잘된 점:
- 제약 준수: 기존 엔드포인트/엔진/인증 무변경(추가만). `/drive/scan` admin전용(Depends(admin_required))·Drive readonly(.list만)·비밀키 노출0(에러=예외문자열만)·--workers1 무영향. 신규 `import time`=stdlib 부작용0, threading은 기존 존재.
- 벌크 헬퍼 안전패턴 완전 일치: get_service() try밖 선호출→DriveConfigError↔DriveError 계층 보존. `_call_with_retry`+`pt=page_token` 기본인자 바인딩→재시도 시 같은 페이지·이미 모은 items 유지·중복0. supportsAllDrives/includeItemsFromAllDrives/corpora=allDrives 유지, nextPageToken 종료조건. pageSize=1000은 Drive API v3 상한 내. orderBy는 생략(allDrives 충돌 회피)+메모리 정렬=오히려 안전.
- 캐시 정합(핵심): `with _SCAN_CACHE_LOCK` 안에서 캐시확인+재스캔 원자적→동시요청 시 벌크스캔 1회 보장. TTL/refresh/root별 키 정확, cached 플래그가 조건·응답 일관. **실패 미캐시 확인**: `_build_drive_scan()` 성공 후에만 `_SCAN_CACHE[root]` 대입, 예외는 `with` 밖 except가 잡아(락 정상 해제) 500/502 반환→오염 없음.
- `_scope_path` 견고: 사이클(A→B→A)·자기참조·부모None(사슬끊김)·루트미도달·과깊이(30) 전부 visited집합+range 이중방어로 무한루프/크래시 없이 (False,[]) 반환. 루트가 fmap에 있든/없든 안전(루트-자기자신은 folder_name 없으면 제외로 일관).
- 필터/사이즈 정확: 확장자는 `os.path.splitext(...).lower()`(기존 _scan_folder_pattern_files와 동일·endswith보다 정확). _is_temp_or_aux_file·_parse_size_from_filename·_SIZE_RANK 전부 재사용(복제0). set 중복제거·사이즈0 폴더 미채택·미상토큰 맨뒤·정렬 stable.
- 엣지: 폴더0/파일0/parents빈배열 전부 안전(count=0, 크래시 없음).

🔴 필수 수정: **없음**

🟡 권장(선택, 차단 아님):
- (락+네트워크 트레이드오프) 벌크 스캔(수초 I/O)을 락 안에서 실행→동시 스캔요청 직렬화(스레드풀 스레드 블록). admin·저빈도 discovery라 허용, 문서화됨. 스캔이 수십초로 길고 요청이 쌓이면 스레드풀 고갈로 타 엔드포인트 영향 가능성(현 검증 깊이5·소규모라 무관). 후속 부담 시 "락 안=in-progress 신호만 공유, 실제 스캔은 락 밖" 패턴 고려 가능(현재 불필요).
- (과깊이 30) `_SCAN_MAX_DEPTH=30` 넘는 정상 폴더는 스코프 밖 오인 제외. 의류 구조상 30 충분·상수라 조정 용이.
- (path 중복) path 마지막 crumb == name(폴더 자기이름). breadcrumb에 self 포함이라 프론트에서 중복표시 가능(무해·설계선택).
- (parents[0]) 다중부모(My Drive 레거시)면 첫 부모만 사용→공유드라이브는 항상 1개라 무영향(주석 인지됨).

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
| 2026-07-07 | tester | 즐겨찾기+자동분류 프론트 검증 — jsdom 실DOM 하니스(patterns/work)+정적diff+서버스모크 | **113 assert 전통과·치명0·회귀0**. 문법0·**degrade4경로**(auth false/select실패/CDN미로딩/빈목록 무손상)·카테고리 그룹/필터/빈결과·별표읽기(전원)·**별표쓰기 admin만**(낙관적+실패원복+토스트, member/degrade 쓰기UI미노출·upsert0)·캡처(scan등록→category=최상위폴더파생, 트리 path없음=생략)·**트리회귀0**(삭제1줄=path추가·렌더/트리함수 본문0변경=감싸기만)·**work선택흐름 무변경**(patternId/stepper/프리셀렉트/자동첫선택)·XSS이스케이프·색상0·서빙본==소스본. 관찰3(updated_by nullable 라이브확인·RLS 라이브전용·기존 initAccount CDN미로딩 예외=PM무관). 커밋 가능 |
| 2026-07-07 | reviewer | 즐겨찾기+자동분류 프론트 리뷰(patterns +377/−1·work +180) | **통과**·치명0·회귀0·제약위반0. 보안 이중게이트(publishable만·SECRET0·isAdmin=app_metadata.role·RLS강제·work SELECT전용) 정합·삭제1줄=path추가 회귀0·감싸기(함수선언 재대입·원본무수정·.pm-added 누수0)·초기화 호이스팅 안전·degrade완비·카테고리 pmMatchKnownCategory 수렴 일관·이스케이프/색상0/CSS변수 존재. 권고4(updated_by 스키마 nullable 확인·이중클릭 debounce·후처리 try/catch·work esc 작은따옴표) 전부 차단아님 |
| 2026-07-07 | developer | 즐겨찾기+자동분류 프론트(patterns.html·work.html) — Supabase pattern_meta 직접 read/write | 계정메뉴 방식 재사용(public-config→createClient publishable·세션JWT·role=app_metadata.role) 공용유틸(getSb/loadMeta/isAdmin/upsertMeta/catOf) · 카테고리=드라이브 최상위폴더 캡처(registerFromDrive 성공 시 upsert)+이름파생 폴백 · 기존 렌더 '감싸기'(교체0·본문무수정) · patterns=별표토글/카테고리select/필터칩(admin쓰기+RLS이중) · work=즐겨찾기상단+카테고리칩(읽기전용·선택흐름무변경) · degrade완비 · 문법0·하드코딩색0·추가556/삭제1(트리회귀0). 커밋 대기(PM) |
| 2026-07-07 | planner-architect | 신규기능 즐겨찾기+자동분류+메타저장 기획설계 | 프론트 직접 Supabase(publishable+세션 JWT)·RLS(SELECT 전체/쓰기 admin `auth.jwt()->app_metadata->>role`)·단일표 pattern_meta(pattern_id PK)·자동분류=키워드파생(override??파생, 기존2개 마이그0)·**등록파일 영속화는 별도 Phase B**(메타만 우선, preset 20~88KB 소형)·5단계 독립커밋·decisions 기록. 승인대기 |
| 2026-07-07 | tester | 자동스캔 프론트 검증 — patterns.html jsdom 실DOM 하니스+실서버 스모크 | **69/69 통과**·치명0·회귀0. 문법0·탭상호배타·카드렌더(grid-3/배지/경로/이스케이프)·refresh1·카드→미리보기→등록왕복(folderId/name정확)·**트리회귀0**·**입력칸중복0(스캔A→트리B=B등록)**·4갈래(configured:false/403/500·502/빈folders)·색상0·캐시전이·버블단일호출·XSS속성방어. 메인 1건 "FAIL"=jsdom 텍스트노드 재직렬화 아티팩트로 기각(esc.js가 실제 이스케이프 별도입증). 실서버 configured:false 확인. 커밋 가능 |
| 2026-07-07 | developer | 자동스캔 프론트(계획3·4) — patterns.html [자동찾기\|폴더트리] 탭+카드그리드+카드→미리보기 배선 | #driveMode 안 .seg 탭 2뷰 상호배타·자동찾기=GET /api/drive/scan→grid-3 카드(폴더명/N사이즈 배지/경로/[등록])·툴바 개수+최신성+새로고침·2단계 마법사(카드→미리보기). renderDrivePreview panel 인자화(기본#drivePanel=트리회귀0)+registerFromDrive activeDrivePanel 스코프(#driveName ID중복 이중방어). 트리 마크업 무변경(감싸기만). 파일1개. vm.Script 문법0·함수10 def1·신규id 중복0. 커밋 대기(PM) |
| 2026-07-07 | reviewer | 자동스캔 프론트 리뷰(patterns.html +264/-20 탭+카드그리드+미리보기배선) | **통과**·치명0·회귀0·제약위반0. new Function 문법0. 트리회귀0(renderDrivePreview 기본#drivePanel·삭제20줄=트리블록 감싸기 재생성·기존함수 무변경)·입력칸중복 이중방어 유효(탭전환 상대패널 비우기+activeDrivePanel 스코프)·카드[등록] form없음 버블1회·리스너누수0. 권고3(트리탭 매전환 재로드·경로중복표시·a11y) 전부 차단아님 |
| 2026-07-07 | tester | 자동스캔 백엔드 독립 모킹검증(gdrive 벌크헬퍼2 + api drive_scan) | **68/68 통과**·치명0·회귀0. 가짜트리(깊이5+떠돌이/사이클/자기참조/과깊이60/빈/루트직속/다중확장자)로 경로조립·확장자필터·사이즈정렬·임시제외·루트스코프·캐시(TTL/refresh/root별/동시성Lock 4스레드=벌크1회)·미설정/500/502·페이지네이션 전검증. git diff 삭제0줄=회귀0. 관찰1(root자기카드 실배포 무해). 커밋 가능 |
| 2026-07-07 | reviewer | 자동스캔 백엔드 리뷰(gdrive 벌크헬퍼2 + api scan/scope/cache) | **통과**·치명0·회귀0·제약위반0. 추가만271줄·py_compile OK. 캐시 락 원자성+실패 미캐시 확인·_scope_path 사이클/과깊이/부모None 방어·계층보존·필터정확·복제0. 권고4(락+I/O 트레이드오프·과깊이30·path중복·parents[0]) 전부 차단아님 |
| 2026-07-07 | developer | 자동스캔 백엔드(계획1·2) — gdrive 벌크헬퍼2 + api GET /drive/scan+TTL캐시 | list_all_folders/list_all_pattern_files(list_children 안전패턴·pageSize1000) + _scope_path/_build_drive_scan(fmap→부모그룹핑→사이즈판정→루트스코프+경로→정렬) + 캐시Lock TTL300 refresh. 기존헬퍼 재사용(복제0). py_compile OK·몽키패치 자체검증(count/path/sizes/cached/502/500/미설정) 전통과. 커밋 대기(PM) |
| 2026-07-07 | planner-architect | 신규기능 패턴 폴더 자동 스캔(카드 그리드) 기획설계 | 벌크 2쿼리(폴더+파일)→부모그룹핑→카드그리드(발견전용)·등록은 기존 renderDrivePreview/from-drive 정확경로 재사용. name contains 금지→endswith 서버필터. GET /api/drive/scan+TTL캐시. 4단계 독립커밋. decisions 기록. 승인대기 |
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
