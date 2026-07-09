# 작업 스크래치패드

## 현재 작업
- **요청**: **[Phase B] 등록 패턴 파일 영속화** — Render 임시디스크라 재배포 시 등록 preset 소실. Supabase Storage에 백업/복원.
- **상태**: 🟢 1·2단계 완료·커밋(feat 82c3364, tester39/39·rev치명0). 🟡 **3·4단계 구현 완료(미커밋)** — 백업훅(api.py create_pattern)+startup복원훅(main.py 백그라운드). py_compile OK·엔진diff0·스모크 통과. **이중백업 방지=create_pattern 1곳만 백업**(from-drive는 request 전달). tester+reviewer 검증 후 PM 커밋 대기. ⚠️사용자가 Supabase 대시보드에서 가이드대로 버킷+RLS 생성해야 실동작.
- **현재 담당**: developer 3·4단계 완료 → tester+reviewer 검증 대기
- **직전 완료**: 번호·이름 위치 구멍 수정 1~4단계 전부 커밋·푸시 완료(미푸시 0). Drive 트리/자동스캔/즐겨찾기·분류 전부 배포 완료.
- **⏳ 별개 남은것**: 즐겨찾기 라이브 비관리자 쓰기막힘 확인은 사용자 계정 있을때.
- **최근 완료(2026-07-06~07, 상세는 git+아래 작업로그)**: Drive Phase1(백엔드)+Phase2(프론트 트리/미리보기/등록)+배포+admin권한(Supabase role) → SSL동시성수정(스레드로컬) → **패턴폴더 자동스캔**(GET /drive/scan+카드그리드) → **즐겨찾기+자동분류**. 배포 URL grader-v2-47gd.onrender.com. 로컬 127.0.0.1:8000 병행.
- **카테고리 라벨 정책(사용자 확인 여지)**: 최상위폴더/이름을 pmMatchKnownCategory로 "0.농구→농구" 정규화. 원하는 라벨 다르면 PM_KNOWN_CATEGORIES 조정. 관리자 override 가능.

## 기획설계 (planner-architect) — [Phase B] 등록 패턴 파일 영속화 [승인 대기]

🎯 목표: Render 재배포 시 소실되는 등록 패턴 폴더(preset.json+SVG들)를 **Supabase Storage에 zip으로 자동 백업**하고 **앱 시작 시 로컬에 없는 것만 자동 복원**해 등록 패턴이 재배포 후에도 유지되게 한다. 엔진·인증·등록로직·비밀키 규칙 전부 무변경.

📌 핵심 사실(코드 정독으로 확정):
- 패턴은 `data/patterns/{id}/` 폴더에 저장 = `preset.json`(필수) + `{사이즈}.svg`들(~4KB) + `number_glyphs.json`(글리프셋 있으면 ~18KB). 총 20~88KB 소형. **파일은 백엔드 디스크에만 존재**(브라우저는 못 봄).
- 목록/조회 GET /api/patterns → `data/patterns/*/preset.json` 온디맨드 스캔(캐시 없음). 폴더만 있으면 자동 인식.
- 등록 성공부 2곳: `create_pattern`(api.py:1377 return dict) / `create_pattern_from_drive`(1707 return, 내부에서 create_pattern await 재사용). 둘 다 성공 시 `{ok,pattern_id,...}` dict 반환·admin_required.
- **백엔드가 요청자 admin JWT 확보 가능**: auth.py는 `request.headers["Authorization"]`에서 Bearer 토큰을 읽음(admin_required 엔드포인트라 그 토큰=admin). → SERVICE_ROLE 없이도 이 JWT를 Storage REST에 릴레이하면 admin RLS 통과(pattern_meta의 "세션JWT+RLS admin"과 동일 철학).
- 앱 startup 훅: 현재 main.py에 startup 이벤트 없음(신규 추가 자리). --workers 1.
- zip 패턴은 job_zip(api.py:926 `zipfile.ZipFile(io.BytesIO())`) 방식 재사용 가능(폴더→메모리 zip).

📍 만들/고칠 위치:
| 파일 경로 | 역할 | 신규/수정 |
|----------|------|----------|
| Supabase Storage 버킷 `pattern-presets` + storage.objects RLS | 읽기=전원(anon 포함) / 쓰기=admin JWT만. 인프라(SQL) | 신규(설정) |
| `webapp/storage_backup.py` | Storage 백업/복원 헬퍼 모듈: 폴더→zip 업로드(admin JWT 릴레이), Storage 목록·다운로드(publishable), zip 해제. Supabase Storage REST 호출(httpx). | 신규 |
| webapp/api.py `create_pattern` 성공 return 직전(≈1377) | 등록 성공 후 자동 백업 호출(요청 헤더의 JWT 전달, 실패해도 등록 성공 유지=경고만) | 수정(+소량) |
| webapp/api.py `create_pattern_from_drive`(≈1707) | 동일 자동 백업 호출(payload 방식이라 Request 주입 필요) | 수정(+소량) |
| webapp/main.py | `@app.on_event("startup")` 복원 훅(로컬에 없는 패턴만 Storage에서 다운로드·해제, 부팅 막지 않게 방어) | 수정(+소량) |
| (옵션 후속) webapp/api.py + patterns.html | 관리자 수동 "전체 재백업/복원" 버튼·엔드포인트 | 신규(후속) |

🔗 기존 코드 연결:
- create_pattern이 진실의 단일 생성점 → from-drive도 이걸 await(api.py:1684). 백업 훅은 두 엔드포인트 return 직전에 각각(토큰은 각자 헤더에서). from-drive는 payload 방식이라 함수 시그니처에 `request: Request` 추가.
- 복원된 폴더는 GET /api/patterns가 자동 인식(코드 0). pattern_meta(즐겨찾기/분류)는 pattern_id 키라 복원 즉시 재부착(추가 작업 0).
- 로컬 커밋본 2개(농구_U넥/농구_V넥)는 로컬에 이미 존재 → 복원이 건너뜀(회귀 0).

📋 8개 설계 결정 요약:
1. **백업 주체 = 백엔드 경유(사용자 JWT 릴레이).** 파일이 백엔드 디스크에만 있어 프론트 직접 업로드 불가(파일 못 가져옴). 백엔드가 요청자 admin JWT를 Storage REST `POST /storage/v1/object/{bucket}/{path}`에 Authorization으로 릴레이 → SERVICE_ROLE 불필요, RLS가 admin 강제. (pattern_meta=프론트직접이었던 건 데이터가 프론트에서 생성됐기 때문. 파일은 백엔드 생성이라 백엔드 경유가 자연스럽고 일관.)
2. **저장 형식 = zip 1개** (`{pattern_id}.zip`). 개별 파일이면 12+회 호출, zip이면 1회. 소형이라 부담0. job_zip의 io.BytesIO+ZipFile 패턴 재사용.
3. **백업 타이밍 = 등록 성공 직후 자동.** 등록=진실의 순간. 수동버튼은 잊음 위험. 백업 실패는 등록 막지 않음(degrade, 경고만).
4. **복원 타이밍 = startup 자동.** 로컬에 없는 것만 다운로드·해제. --workers 1이라 1회. 콜드스타트 지연 방지 위해 try/except+타임아웃(부팅·헬스체크 안 막음). 20~88KB라 각<1초. (+옵션: 관리자 수동 복원 버튼)
5. **버킷/RLS.** 버킷 `pattern-presets`(private). storage.objects RLS: SELECT `to anon,authenticated using(bucket_id='pattern-presets')`(복원이 startup=JWT없음이라 읽기 개방), INSERT/UPDATE/DELETE `(auth.jwt()->'app_metadata'->>'role')='admin' and bucket_id='pattern-presets'`.
6. **충돌 처리.** 복원은 **로컬에 폴더 없을 때만**(로컬 우선, 커밋본·기존 등록 덮어쓰기 안 함). 재등록은 create_pattern이 이미 409 차단, Storage는 같은 경로 upsert=최신본. 진실 순서: 로컬 디스크 > Storage(공백만 채움).
7. **실행 계획**(아래 표).
8. **주의사항**(아래).

📋 실행 계획(각 독립 커밋, 단계 후 tester+reviewer 병렬):
| 순서 | 작업 | 담당 | 선행 |
|------|------|------|------|
| 1 | Supabase Storage 버킷 `pattern-presets` + RLS 3정책 생성(SQL/대시보드) — 검증: admin 쓰기O·비admin 쓰기X·anon 읽기O | 사용자/developer(MCP) | 없음 |
| 2 | `webapp/storage_backup.py` 신규(업로드=JWT릴레이·목록·다운로드=publishable·zip 묶기/풀기·zip-slip 방어·미설정 skip) | developer | 1 |
| 3 | 등록 직후 자동 백업 훅(create_pattern + from-drive, Request 주입, 실패 degrade) | developer | 2 |
| 4 | startup 자동 복원 훅(main.py, 로컬 없는 것만, 부팅 안막는 방어) | developer | 2 |
| 5 | (후속·옵션) 관리자 수동 백업/복원 버튼 UI | developer | 3,4 |

⚠️ developer 주의사항(빠지기 쉬운 함정):
- **비밀키**: SERVICE_ROLE·SECRET 절대 사용/로깅 금지. Storage 헤더 `apikey=PUBLISHABLE` + `Authorization=Bearer <요청자 JWT>`만(auth.py introspection과 동일 규칙).
- **토큰 확보 경로**: create_pattern은 FormData 파라미터라 Request가 없음 → 시그니처에 `request: Request` 추가하되 **from-drive가 create_pattern을 직접 await 호출**하므로 request 전달 일관성 주의(각 엔드포인트가 자기 request의 헤더 토큰을 백업 훅에 넘기는 게 단순). 헤더 없거나 로컬 무인증(토큰 없음)이면 백업 skip(로컬은 디스크 영속이라 불필요).
- **degrade 필수**: Storage 미설정(env 없음)·업로드 실패·Supabase 장애 시 등록/부팅은 정상 진행(pattern_meta degrade와 동일). 백업은 "있으면 좋은" 부가기능.
- **startup blocking 금지**: 복원이 Storage 네트워크를 동기 대기하면 첫 헬스체크 지연 → try/except+httpx timeout, 다수면 최악의 경우도 유한. (필요 시 백그라운드 스레드 검토, 단 --workers 1·_JOBS 패턴 참고.)
- **zip-slip**: 해제 시 pattern_id/엔트리 경로 sanitize(../ 차단). preset.json 없는 손상 zip은 skip.
- **회귀0**: 로컬 커밋본 2개는 복원이 건드리지 않음(로컬 존재→skip). 로컬 개발(GRADER_REQUIRE_AUTH off)은 토큰·env 없어 백업/복원 자동 skip=기존 동작 그대로.
- **엔진/인증/등록로직 무수정**: create_pattern 본체 로직 불변(성공 return 직전 훅 호출만 추가). engine/ diff 0.

## 구현 기록 (developer) — [Phase B] 등록 패턴 파일 영속화 [1·2단계]

📝 구현한 기능: (1) Supabase Storage 버킷+RLS **설정 가이드 문서**(사용자가 대시보드에서 직접 실행), (2) `webapp/storage_backup.py` **백업/복원 헬퍼 모듈**. api.py/main.py 무수정(백업·복원 훅은 3·4단계). 엔진 diff 0.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| `Phase-B-Supabase-Storage-설정가이드.md` (프로젝트 루트) | 비개발자용 가이드: 버킷 `pattern-presets`(private) 생성 클릭순서 + storage.objects RLS SQL(읽기=anon+authenticated 개방 / INSERT·UPDATE·DELETE=admin JWT `auth.jwt()->'app_metadata'->>'role'='admin'`) 복붙실행 + 검증법(admin쓰기O·비admin쓰기X·anon읽기O). ⚠️버킷명=코드 상수 정확일치 명시. **작업산출물 아닌 가이드**(PM이 커밋포함 판단) | 신규 |
| `webapp/storage_backup.py` | Storage 백업/복원 헬퍼. `BUCKET="pattern-presets"`, `_config()`(SUPABASE_URL+PUBLISHABLE env→없으면 미설정), `is_enabled()`, `backup_pattern(pattern_id,user_jwt)`(폴더→io.BytesIO+ZipFile zip→REST POST /object/{bucket}/{id}.zip, apikey=PUBLISHABLE+Authorization=Bearer user_jwt+x-upsert:true, **user_jwt없으면 skip**, 실패 삼키고 False), `list_backups()`(POST /object/list/{bucket}, publishable 읽기), `restore_missing()`(목록→로컬 없는 것만 GET 다운로드→`_safe_extract`, 복원개수 반환), `_safe_extract`(**zip-slip 방어**: 절대/`..`경로 차단+commonpath 경계검사, preset.json 없는 손상 zip skip). **키·JWT 로그 금지**. httpx(이미 requirements.txt:18) | 신규 |

🔎 근거(코드 정독): env 변수명=auth.py의 `SUPABASE_URL`·`SUPABASE_PUBLISHABLE_KEY` 동일. 패턴 저장경로=state.get_patterns_dir()=`data/patterns/{id}/`(preset.json+{사이즈}.svg+number_glyphs.json). zip=job_zip(api.py:926) io.BytesIO+ZipFile 재사용. RLS JWT경로=decisions.md pattern_meta 방식과 동일.

💡 tester 참고:
- **미설정 skip(핵심 degrade)**: env 없이 `is_enabled()`=False / `backup_pattern('x',None)`=False / `list_backups()`=[] / `restore_missing()`=0. **예외 안 던짐**(등록·부팅 안 막음). ✅스모크 통과.
- **user_jwt 없을 때 skip**: env 있어도 user_jwt=None이면 backup skip(False). (로컬 무인증=디스크 영속이라 불필요)
- **zip 묶기/풀기 왕복**: `_zip_pattern_folder`(폴더→bytes)→`_safe_extract`(bytes→폴더) 왕복 후 preset.json·XL.svg 그대로 복원. ✅
- **zip-slip 방어**: `../evil.txt` 엔트리 든 zip→`_safe_extract` False 반환+**목표폴더 밖에 파일 안 생김**(escaped? False). 절대경로/`..`/commonpath 경계이탈 전부 차단. ✅
- **손상 zip skip**: preset.json 없는 zip→`_safe_extract` False(복원 안 함). ✅
- **sanitize**: `../../etc/passwd`→`passwd`, `a/b/c`→`c`, `..`→`''`(빈값=skip). 경로조작 무력화. ✅
- **네트워크 검증(tester가 실 Supabase/httpx 모킹 권장)**: 200/201 업로드 성공 True·403(비admin)/기타 status False·타임아웃 예외삼킴 False. list=POST list엔드포인트 200 파싱·.zip만 필터. 아직 실호출 미검증(3·4단계 훅 붙인 뒤 e2e 가능).

⚠️ reviewer 참고:
- **비밀키 규칙**: 쓰기=apikey(PUBLISHABLE)+Authorization(요청자 user_jwt) 릴레이만, SERVICE_ROLE 미사용. 읽기=publishable을 apikey·Authorization 양쪽(anon 역할). **print에 키/JWT 절대 안 남김**(status 코드·pattern_id·예외 타입명만).
- **degrade 완결성**: 모든 공개함수가 예외를 안 던지도록 try/except로 감쌈. restore는 패턴별 개별 try(하나 실패해도 계속). 단 print의 em-dash(—)가 Windows cp949 콘솔에서 인코딩 크래시→**전부 하이픈(-)으로 교체**(배포 Linux UTF-8 무관하나 안전).
- **로컬 우선(회귀0)**: restore_missing은 `os.path.isdir(local_dir)` True면 skip=커밋본 2개·기존등록 덮어쓰기 안 함.
- **미사용 import 제거**: json(httpx의 json= 파라미터는 별개). py_compile OK.
- **한계(3·4단계에서 결선)**: 이 모듈은 아직 어디서도 호출 안 됨(api.py/main.py 무수정). backup 훅(3단계)·startup 복원 훅(4단계) 붙여야 실동작.

## 구현 기록 (developer) — [Phase B] 등록 패턴 파일 영속화 [3·4단계 백업훅+startup복원훅]

📝 구현한 기능: 2단계에서 만든 `storage_backup.py`를 실제로 **결선(호출 연결)**. (3) 등록 성공 직후 자동 백업 훅(api.py) + (4) 앱 startup 자동 복원 훅(main.py, 백그라운드 스레드). 모듈 자체 무수정. 엔진 diff 0.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| webapp/api.py import(≈22·26) | `Request`를 fastapi import에 추가 + `from . import storage_backup` | 수정 |
| webapp/api.py `_extract_bearer_token`(신규, create_pattern 직전) | 요청 헤더 Authorization에서 Bearer 토큰만 추출(auth.py:178-183과 동일 방식, 대소문자 대응, 없으면 None). **토큰 값 로그 금지** | 신규(+18줄) |
| webapp/api.py `create_pattern` 시그니처(≈1074) | `request: Request` 인자 **맨 앞** 추가(Python 문법: 기본값 없는 인자는 Form 기본값들보다 앞). FastAPI가 자동 주입 | 수정(+1줄) |
| webapp/api.py `create_pattern` 성공 return 직전(≈1377) | **5) 자동 백업 훅**: `user_jwt=_extract_bearer_token(request)` → `storage_backup.backup_pattern(pattern_id, user_jwt)`. try/except로 감싸 **어떤 예외도 등록 성공을 안 막음**(degrade). 등록 본체 로직 무변경 | 수정(+13줄) |
| webapp/api.py `create_pattern_from_drive` 시그니처(≈1599)+create_pattern 호출부(≈1684) | `request: Request` 추가 + `await create_pattern(request=request, ...)` 로 자기 request 전달. **from-drive는 별도 백업 안 함**(create_pattern이 백업=이중백업 0) | 수정(+2줄) |
| webapp/main.py import(≈16·20) | `import threading` + `from . import storage_backup` | 수정 |
| webapp/main.py `_restore_patterns_background`+`_on_startup`(신규, 정적마운트 뒤) | `@app.on_event("startup")`가 **daemon 백그라운드 스레드**로 `restore_missing()` 실행. 스레드 시작만 하고 즉시 반환→부팅/헬스체크 지연 0. 전체 try/except(복원·스레드생성 실패해도 부팅 계속). 미설정이면 모듈 no-op | 신규(+45줄) |

🔎 근거(코드 흐름 정독 — 이번 핵심 함정):
- **이중백업 방지**: `create_pattern_from_drive`(api.py:1684)가 `await create_pattern(...)`을 호출 = create_pattern이 **유일한 생성점**. 따라서 백업 훅을 create_pattern 한 곳에만 넣으면 from-drive 경로도 자동 1회 백업. from-drive는 자기 request를 넘기기만(추가 백업 호출 없음). → 이중백업 0 / 누락 0.
- **토큰 확보**: admin_required 엔드포인트라 배포에선 헤더 Bearer=admin 토큰. `_extract_bearer_token`이 auth.py require_auth와 동일하게 추출. 로컬 무인증=헤더 없음→None→backup skip(로컬은 디스크 영속이라 불필요). 미설정 env→is_enabled False→skip.
- **Python 문법 주의**: `request: Request`(기본값 없음)를 `name: str = Form(...)` 등 기본값 인자 뒤에 두면 SyntaxError → **맨 앞**에 배치(FastAPI는 Request를 위치 무관 특수 주입).
- **startup 백그라운드(reviewer 권고 반영)**: restore_missing 동기(list 1회+미복원 N회 다운로드, 각 최대 15초)→최악 부팅 수십초 지연 위험. daemon Thread로 분리해 `_on_startup`은 즉시 반환. --workers 1이라 스레드 1개로 충분·중복복원 없음.

💡 tester 참고:
- **테스트 방법**: `python -m py_compile webapp/api.py webapp/main.py` ✅통과. 스모크: `_on_startup()` 직접호출→**0.000s 즉시반환**(부팅 안 막음)·미설정 env에서 restore no-op(예외0)·`_extract_bearer_token`: None/무헤더→None, `Bearer abc123`→abc123, 소문자 `bearer`→OK, `Bearer `(빈값)→None. ✅전부 확인.
- **이중백업 없음(핵심)**: 코드상 backup_pattern 호출은 create_pattern 안 1곳뿐. from-drive는 `grep backup_pattern webapp/api.py`=1매치(create_pattern 내부)로 확인 가능. from-drive 등록해도 백업 1회.
- **등록 실패 안 함**: backup 훅 전체 try/except. Storage 미설정/토큰없음/업로드403/네트워크장애 전부 삼키고 등록 성공 dict 그대로 반환. (backup_pattern 자체도 예외 안 던지지만 이중 방어)
- **startup 부팅 안 막음**: `_on_startup`이 스레드 시작 후 즉시 반환(≈0s). 복원은 백그라운드. Storage 느려도 헬스체크 지연 0.
- **미설정 skip(로컬 회귀0)**: SUPABASE env 없으면 백업·복원 전부 조용히 no-op → 로컬 개발 기존 동작 그대로.
- **정상 동작(배포 e2e, 버킷 생성 후)**: 패턴 등록→Storage에 `{id}.zip` 생김 / 재배포(디스크 초기화)→startup 백그라운드 복원→로컬에 없던 등록패턴 폴더 재생성→GET /api/patterns 자동 인식. 로컬 커밋본 2개는 로컬 존재→복원 skip(회귀0).
- **주의 입력**: from-drive 등록도 request 전달돼 백업됨(단, 로컬 무인증이면 토큰없어 skip). 실 Supabase 버킷+RLS는 사용자가 가이드대로 생성해야 실동작(미생성이면 업로드 403/목록 실패=degrade로 조용히 skip).

⚠️ reviewer 참고:
- **엔진 무수정**: `git diff --stat engine/`=빈 결과. 변경=webapp/api.py(+45)·main.py(+45)뿐.
- **create_pattern 본체 무변경**: 성공 return 직전 훅 호출 1블록(+토큰추출)만 추가. 반환 dict·검증·preset조립 로직 불변. from-drive는 시그니처+호출 keyword arg 1개(request=) 추가만.
- **비밀키 규칙**: backup에 넘기는 건 요청자 JWT(user_jwt)뿐, SERVICE_ROLE 미사용. `_extract_bearer_token`은 토큰 값을 로그에 안 남김(반환만). main/api 새 print는 status·개수·type명·"skip 사유"만(키/JWT 미출력).
- **degrade 완결**: 3단계 훅 try/except + backup_pattern 내부 방어 = 이중. 4단계 _on_startup try/except + _restore_patterns_background try/except + restore_missing 내부 패턴별 try = 삼중. 어느 층에서 터져도 등록/부팅 정상.
- **--workers 1 유지**: startup 스레드 daemon 1개(프로세스당). uvicorn --workers 변경 없음.

## 테스트 결과 (tester) — [Phase B] 등록 패턴 파일 영속화 [3·4단계 백업훅+startup복원훅]

📊 종합: **검증 항목 전부 통과 / 실패 0** · 수정 요청 없음 · **커밋 가능**. (실 네트워크는 Supabase 버킷 미생성이라 미검증 — 이번 검증대상=연결의 정확성·안전성)

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| py_compile(api.py·main.py·storage_backup.py) | ✅ 통과 | 3파일 전부 OK |
| **[2] FastAPI 라우팅 무결성(중요)** | ✅ 통과 | `request:Request`+Form 파라미터 공존해도 **TestClient build 성공**(전 라우트 dependant 분석 OK=시그니처 안 깨짐). api.router.routes에 POST /api/patterns(create_pattern)·POST /api/patterns/from-drive(create_pattern_from_drive) 정상 등록. create_pattern params=[request,name,base_size,...] request 맨앞. from_drive params=[request,payload]. 빈 POST /api/patterns→**422**(FormData name 필수 검증=라우트 도달)·from-drive 빈payload→200(drive미설정 degrade)·health 200 |
| **[3] 이중백업 방지(핵심)** | ✅ 통과 | `grep backup_pattern webapp/` = **실호출 api.py:1410 딱 1곳**(나머지는 주석·정의·모듈내부). from-drive(1724)는 `await create_pattern(request=request,...)`로 request만 전달, 별도 backup 호출 0 → from-drive 경로도 1회만 백업(누락·이중 없음) |
| **[4] 등록 실패 안 함(degrade)** | ✅ 통과 | backup_pattern을 **강제 예외 스텁**으로 교체해도 훅 try/except(api.py:1408-1413)가 삼킴 → 등록 성공 유지. **미설정 실 등록 e2e**: XL/M/S svg 3개 업로드→POST /api/patterns→**200 ok=True** pattern_id 정상, 로그 "skip 백업: 미설정"만 남고 등록 완료 |
| **[5] startup 부팅 안 막음(중요)** | ✅ 통과 | restore_missing을 3초 sleep 스텁으로 교체 후 `_on_startup()` 호출→**0.001s 즉시반환**(복원은 백그라운드 미완=부팅과 분리 확인). restore가 RuntimeError 던지는 스텁→`_on_startup` 예외 전파 0, 백그라운드 스레드가 예외 삼킴(프로세스 생존). daemon Thread 격리 정상 |
| **[6] 미설정 skip** | ✅ 통과 | SUPABASE env 제거 상태: is_enabled()=False·backup_pattern('x',None)=False·list_backups()=[]·restore_missing()=0. **예외 0**(등록·부팅 안 막음) |
| **[7] 토큰 추출(_extract_bearer_token)** | ✅ 통과 | None request→None·무헤더→None·`Bearer abc123`→abc123·소문자 authorization키→OK·소문자 `bearer`스킴→OK·`Bearer `(빈값)→None·스킴없는 생토큰→None (7케이스) |
| **[8] 엔진 무수정** | ✅ 통과 | `git diff --stat -- engine/` = 빈 결과(0). 변경=webapp/api.py·main.py만 |
| **[9] 실 등록 e2e(미설정)** | ✅ 통과 | 위 [4]와 동일 — 미설정 로컬에서 패턴 등록 여전히 정상(백업 조용히 skip), 회귀 0. 서버 기동 없이 TestClient 함수레벨로 수행(포트 종료 불필요) |

🟢 관찰(비차단): (a) 이 FastAPI 버전은 include_router를 `_IncludedRouter`로 지연 마운트해 app.routes에 서브라우트가 즉시 안 펼쳐짐 → 라우트 조사는 api.router.routes 직접 조회 또는 TestClient build로 해야 함(테스트 하니스 참고, 코드 문제 아님). (b) 실 Supabase 버킷+RLS 생성 후 배포 e2e(등록→zip 생성, 재배포→startup 복원)는 사용자가 가이드대로 버킷 만든 뒤 별도 확인 필요 — 현 단계 검증 한계는 여기까지(연결 정확성·안전성은 전부 통과).

## 테스트 결과 (tester) — [Phase B] 등록 패턴 파일 영속화 [2단계 storage_backup.py]

📊 종합: **39개 검증 전부 통과 / 실패 0** · 수정 요청 없음 · **커밋 가능**(단위·스모크 수준, 실 네트워크는 3·4단계 결선 후 e2e)

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| py_compile(storage_backup.py) | ✅ 통과 | OK |
| **[2] 미설정 degrade(핵심)** | ✅ 통과 | env 없을 때 is_enabled()=False·backup(,None)=False·backup(,jwt)=False(네트워크 도달 전 skip)·list_backups()=[]·restore_missing()=0. **예외 0**(등록·부팅 안 막음) |
| **[3] user_jwt 없을 때 skip** | ✅ 통과 | env 있어도 jwt=None/''(빈값)이면 backup skip=False. 네트워크 도달 전 차단(is_enabled=True 확인 후) |
| **[4] zip 묶기/풀기 왕복** | ✅ 통과 | preset.json+XL.svg+하위폴더(sub/number_glyphs.json) → _zip_pattern_folder → _safe_extract 후 내용 완전 보존. 빈/없는 폴더→None |
| **[5] zip-slip 방어(보안)** | ✅ 통과 | (5a)../evil.txt (5b)/tmp 절대경로 (5c)../../etc/passwd 전부 _safe_extract False + **목표 폴더 밖에 파일 안 생김**. sanitize: ../../etc/passwd→'passwd'·a/b/c→'c'·'..'→''(skip)·백슬래시 ..\\..\\x→'x'·한글 정상유지 |
| **[6] 손상 zip skip** | ✅ 통과 | preset.json 없는 zip→False+아무것도 안 풂. 잘못된 바이트(BadZipFile)→False(예외 삼킴) |
| **[7] restore_missing 로컬 우선(회귀0)** | ✅ 통과 | 모킹: 창고에 [이미있음.zip,새패턴.zip]→로컬 존재 '이미있음' **안 덮어씀**(original 보존)·'새패턴'만 복원=1. 커밋본 2개 안전 |
| **[부가] backup 네트워크 경로(httpx 모킹)** | ✅ 통과 | 200→True·403→False(예외0)·타임아웃 예외→False(삼킴). **헤더 규칙 검증: apikey=publishable(공개키)·Authorization=Bearer user_jwt(릴레이)·x-upsert=true·URL에 버킷 pattern-presets 포함** |
| **[7] 비밀키 안전** | ✅ 통과 | 소스에 SERVICE_ROLE/SECRET 하드코딩·실제 키값(eyJ) 0(주석/문서 언급만). **로그 출력에 JWT/키 문자열 미노출**(status·pattern_id·type명만) 실행 로그로 확인 |
| **[8] env 변수명 auth.py 일치** | ✅ 통과 | storage_backup `SUPABASE_URL`·`SUPABASE_PUBLISHABLE_KEY` = auth.py:106-107 동일. SECRET 미사용(auth.py도 introspection에 SECRET 안 씀) |

🟢 관찰(비차단): _safe_extract는 `..` split 검사 + `os.path.commonpath` 경계검사 이중 방어라 형제폴더 접두어 우회(slip_target vs slip_target_evil)도 컴포넌트 단위로 안전. 3·4단계(api.py 백업 훅·main.py startup 복원 훅)에서 실 Supabase 버킷 연결 후 실호출 e2e 필요(현재 버킷 미생성이라 단위/모킹까지가 검증 한계).

## 리뷰 결과 (reviewer) — [Phase B] 등록 패턴 파일 영속화 [1·2단계]

📊 종합 판정: ✅ **통과** (🔴치명 0 · 커밋 가능). storage_backup.py 신규 + 설정가이드 md. api.py/main.py/engine diff 0(git 확인), py_compile OK.

✅ 잘된 점:
- **불변 제약 준수**: `git status/diff --stat -- engine/ webapp/api.py webapp/main.py` = 전부 빈 결과. 이번 단계는 신규 모듈 1개 + 가이드 md뿐(어디서도 import 안 됨=3·4단계 결선 예정). 빌드0.
- **비밀키 규칙 완벽(치명 후보 클리어)**: 쓰기(backup)=`apikey=PUBLISHABLE`+`Authorization=Bearer {user_jwt}` 릴레이만. 읽기(list/download)=publishable을 apikey·Authorization 양쪽(anon 역할)=supabase-js 무세션 기본동작과 동일. SERVICE_ROLE·SECRET 미사용. auth.py `_introspect`(apikey=PUBLISHABLE+Bearer user token)와 동일 철학. **로그에 키/JWT 절대 안 남김**: 모든 print가 status_code·pattern_id·byte수·`type(e).__name__`만(resp.text/헤더/토큰 미출력).
- **env 변수명 정합(치명 후보 클리어)**: `_config()`가 `SUPABASE_URL`·`SUPABASE_PUBLISHABLE_KEY`—auth.py:106-107·api.py:108-109·render.yaml:18/21·.env.example:21-22와 **글자단위 일치**. 오타로 항상 미설정死 되는 버그 없음.
- **zip-slip 방어 견고(보안 치명 후보 클리어)**: `_safe_extract` 3중 방어—①preset.json 없으면 통째 skip ②엔트리별 절대경로(`/`·`\` 시작)+`..` 컴포넌트(`split('/')` 후 멤버검사, `foo/../../bar`도 차단) 선차단 ③`os.path.commonpath([dest_abs, target]) != dest_abs` 경계검사. **전부 통과해야 실제 해제(all-or-nothing)**. 윈도 드라이브문자(`C:\evil`)는 Linux(배포)선 단일 파일명이라 dest 안쪽, 로컬 윈도선 commonpath가 다른드라이브→ValueError→outer except→False(안전死). 우회경로 못 찾음.
- **degrade 완결(부팅·등록 안 막음)**: 모든 공개함수(backup_pattern/list_backups/restore_missing)가 예외를 밖으로 안 던짐. httpx 전 호출 `timeout=15.0` 명시. backup=httpx try/except+status분기, list/download=try/except+status!=200 방어, restore=**패턴별 개별 try**(하나 실패해도 continue). 미설정/no-jwt/폴더없음/손상zip 전부 조용히 skip.
- **폴더명 정합(silent-skip 없음)**: 등록 `_safe_pattern_dirname`(api.py:1021, 금지문자·공백→`_`치환, 양끝 점제거, 선행`_`보존)이 만든 dirname에 `_sanitize_pattern_id`를 적용하면 **idempotent**(제거할 위험문자 이미 없음, `_`·한글·선행`_` 보존). backup 폴더조회·restore pid복원이 왕복 일치→유효 등록패턴을 조용히 놓치지 않음. object명=`{safe_id}.zip` 왕복 대칭.
- **RLS SQL 정확**: SELECT `to anon,authenticated using(bucket_id='pattern-presets')`=startup(JWT없는 anon) 복원 읽기와 정합. INSERT/UPDATE/DELETE `auth.jwt()->'app_metadata'->>'role'='admin'`=pattern_meta·decisions.md 방식과 동일. upsert(x-upsert:true)에 INSERT+UPDATE 둘 다 제공(신규=INSERT/덮어쓰기=UPDATE). 버킷명 `pattern-presets`=코드 `BUCKET` 상수 일치, 가이드가 오타주의 명시. drop-if-exists로 재실행 안전.
- **zip 패턴 일관성**: `_zip_pattern_folder`=job_zip(api.py:926) `io.BytesIO`+`ZipFile(...,ZIP_DEFLATED)`+arcname 상대경로(`\`→`/`) 동일 관례. state.get_patterns_dir()(state.py:56) 정확 사용.

🔴 필수 수정: **없음.**

🟡 권장(비차단, 대부분 3·4단계 결선 시 반영):
- **[4단계 결선 주의·중요] startup blocking**: `restore_missing`은 동기(list 1회 + 미복원 패턴 N회 다운로드, 각 최대 15초). Storage 느림/장애 시 최악 `15*(1+N)`초 부팅 지연→첫 헬스체크 위협. 4단계 main.py 훅에서 **백그라운드 스레드**(또는 총 예산 타임아웃)로 감싸 부팅·헬스체크를 안 막게 할 것(설계 §4·주의사항과 동일 취지). 이 모듈 자체는 함수로선 정상.
- **list_backups limit=1000 고정**(offset 페이지네이션 없음): 현재 패턴 수십개라 무해. 1000개 초과 시 초과분 복원 누락. 지금은 비차단.
- **[3단계 결선 시 확인]** backup_pattern에 넘길 `pattern_id`는 create_pattern 반환값(=dirname)이어야 폴더조회 성공. from-drive도 동일 dirname 반환 확인 후 연결.
- (신규 convention 후보, PM 승격 판단) "Supabase Storage 접근=쓰기는 apikey(PUBLISHABLE)+Authorization(요청자 admin JWT) 릴레이, 읽기는 publishable 양쪽(anon)—SERVICE_ROLE 금지. auth.py introspection·pattern_meta와 동일 규칙."

## 리뷰 결과 (reviewer) — [Phase B] 등록 패턴 파일 영속화 [3·4단계 백업훅+startup복원훅]

📊 종합 판정: ✅ **통과** (🔴치명 0 · 커밋 가능). 변경=webapp/api.py(+45)·main.py(+45)뿐(git diff --stat). engine/ diff 0. FastAPI 0.138.0.

✅ 잘된 점:
- **불변 제약 준수(치명 후보 클리어)**: `git diff --stat` = api.py(+45)·main.py(+45)·scratchpad뿐, **engine/ 무변경**. create_pattern 본체 로직 무변경—성공 return dict 직전에 백업 훅 1블록(+토큰추출 헬퍼)만 추가, 반환 dict·검증·preset 조립 불변. from-drive는 시그니처에 `request: Request` + 호출부 `request=request` 1개만 추가. 빌드0. --workers 1 유지(startup daemon 스레드 1개는 프로세스당 1개, uvicorn workers 변경 없음).
- **이중백업 방지 견고(치명 후보 클리어)**: `grep backup_pattern webapp/` = 호출 **1곳뿐**(api.py:1410, create_pattern 내부). create_pattern 호출자 확인=from-drive(:1724, `request=request`)와 라우트 데코레이터뿐, **다른 Python 호출자 없음**. from-drive 성공 경로는 반드시 create_pattern을 경유(중복 구현 없음)하므로 create_pattern 1곳 백업=from-drive도 자동 정확히 1회. from-drive는 별도 backup 호출 안 함 → 이중백업 0.
- **백업 위치가 성공 보장점(누락·오백업 0)**: 훅이 `_cleanup_dir(tmp_path_dir)` 직후·`return {ok:True,...}` 직전에 위치. create_pattern의 모든 실패/조기 return(409 등 JSONResponse)은 이 지점보다 **앞**에서 반환됨 → 백업은 등록이 실제 성공한 경우에만 실행(실패 시 미백업). 정확.
- **degrade 견고(치명 후보 클리어)**: 3단계 훅 `try/except`는 **오직 2줄**(토큰추출+backup_pattern 호출)만 감쌈—등록 본체 완료 뒤라 등록 성공을 절대 못 막고, 광범위하게 다른 오류를 삼키지도 않음(스코프 최소). backup_pattern 자체도 모든 예외 내부 처리(예외 안 던짐)=이중 방어. except가 `type(e).__name__`을 로그로 남겨 디버깅 단서 보존(무음 삼킴 아님). 토큰/키 값은 로그에 없음.
- **startup 부팅 안 막음(치명 후보 클리어·이전 4단계 권고 반영 확인)**: 내 [1·2단계] 리뷰 🟡 "restore_missing 동기(최악 15×(1+N)초)→백그라운드/타임아웃 필수" 권고가 **정확히 반영됨**. `_on_startup`은 daemon Thread를 start만 하고 즉시 반환(스모크 0.000s)=헬스체크/요청 지연 0. 복원은 백그라운드에서 진행. 3중 방어: `_on_startup` try/except(스레드 생성 실패해도 부팅 계속) + `_restore_patterns_background` try/except + restore_missing 내부 패턴별 try. --workers 1이라 스레드 1개=중복 복원 없음. httpx 전 호출 timeout=15.0.
- **토큰 릴레이 보안·일관성(치명 후보 클리어)**: `_extract_bearer_token`이 auth.py:178-183 require_auth와 **동일 로직**(`headers.get("Authorization") or headers.get("authorization")` → `.lower().startswith("bearer ")` 검사 → `split(" ",1)[1].strip()` → 빈값 None). request=None·헤더없음·빈토큰 전부 None 안전. 토큰 값 로그 미출력(반환만). backup에 넘기는 건 요청자 JWT뿐, SERVICE_ROLE 미사용.
- **Request 주입 정합(라우팅 안전)**: create_pattern은 `request: Request`(기본값 없음)를 **맨 앞**, Form(...) 기본값 인자들 뒤—Python 문법 정상(no-default 먼저). from-drive는 `request: Request, payload=Body(...)`. FastAPI는 Request를 위치 무관 특수 주입이라 두 라우트 정상 동작. py_compile OK(스크래치패드 기록·재확인).

🔴 필수 수정: **없음.**

🟡 권장(비차단, 참고만):
- **`@app.on_event("startup")` deprecated(FastAPI 0.138)**: 현재 버전에서 **정상 동작**하나 FastAPI 공식은 lifespan(`@asynccontextmanager` + `app = FastAPI(lifespan=...)`)을 권장하며 on_event는 향후 제거 예정 경고 대상. 지금 기능·부팅에 영향 0(기존 코드에 startup 이벤트가 없던 신규 추가라 on_event가 가장 단순한 선택). 차후 FastAPI 메이저 업 시 lifespan 전환 여지—현 단계 비차단.
- **list_backups limit=1000 고정**([1·2단계]에서도 지적, 미해결·비차단): offset 페이지네이션 없음. 패턴 수십 개라 무해, 1000개 초과 시 초과분 복원 누락. 지금 비차단.
- **실 e2e 미검증(구조상 불가피)**: Supabase 버킷+RLS를 **사용자가 가이드대로 생성해야** 실 백업/복원 동작. 미생성 시 업로드 403·목록 실패=degrade로 조용히 skip(부팅·등록 정상). 코드 경로는 단위/스모크/모킹까지 검증됨, 실 네트워크 왕복은 버킷 생성 후 배포 e2e 필요.

## 구현 기록 (developer) — 번호·이름 위치 구멍 수정 [1·2단계]

📝 구현한 기능: (1) 패턴 등록 시 번호/이름 area에 **piece_id 자동부여**(엔진이 조각을 찾아 번호·이름을 실제로 그리도록) + (2) 번호위치 미등록 패턴 **주문 경고**(has_number_area 플래그+work 배너). **엔진 무수정**(webapp/api.py·work.html만).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| webapp/api.py `create_pattern` area 후처리(≈1332~1360, glyph_source 붙이던 자리) | 완성본 추출 area에 piece_id `setdefault` 자동부여(앞번호→pieces[0].id, 뒤번호·이름→pieces[1].id, 1조각뿐이면 폴백). 하드코딩 아니라 `_build_pieces`가 만든 실제 조각 id 사용(=job._find_piece_index 매칭키 pdef["id"]와 일치) | 수정(+23줄) |
| webapp/api.py `_scan_one_pattern`(≈137~) | `has_number_area` = front/back number 또는 back name area 중 하나라도 유효하면 True. /api/patterns 응답에 포함 | 수정(+6줄) |
| webapp/static/screens/work.html `renderPatterns`(≈542) | `p.has_number_area===false`면 카드 하단 warn 배너(var(--status-warn-*)·--amber-600/700·Material Symbols `warning`). 진행 차단 아님, 경고만. `.pm-added` 아니라 즐겨찾기 코드와 충돌0 | 수정(+9줄) |

🔎 근거(코드 정독): job.py:772-777 `_inject`가 `area.piece_id`→`_find_piece_index`(job.py:596 `pdef["id"]==piece_id`)로 조각탐색→없으면 경고+건너뜀. reference.py:366 `build_area_preset` 반환 area엔 **piece_id 키 없음(=구멍)**. 정상 preset(농구V넥)은 area에 piece_id 수작업. from-drive는 create_pattern 재사용→로컬·드라이브 동시 해결.

💡 tester 참고:
- **piece_id 자동부여(단위)**: `python scratchpad/verify_piece_id.py` 류 — build_area_preset은 piece_id 미포함 확인 / 자동부여 후 front·back·back, 기존값 setdefault 유지 확인. ✅통과.
- **end-to-end(run_job)**: 정상 폴더 복사→area piece_id 제거(구멍 재현) vs 내 로직 적용, run_job 비교. **BROKEN=번호미출력 경고 3건(번호·이름 안 그림), FIXED=경고 0건(정상 주입). 판정 PASS.** ✅
- 실등록 검증 권장: 완성본(design_source/연세대_V넥_완성본_본체포함_XL.ai)으로 로컬/from-drive 등록→preset.json의 front/back_number_area·back_name_area에 piece_id 박혔는지 확인→run_job으로 실제 번호 출력.
- has_number_area: 실제 2패턴 모두 True 확인. 완성본 미등록(area 없음) 패턴은 False.
- 정상 동작: (a)등록 preset area에 piece_id 자동 존재 (b)기존 2패턴 preset 무변경(회귀0, create_pattern 미경유) (c)work 목록에서 area없는 패턴에 노란 경고배너, 선택·진행은 그대로 가능.
- 주의 입력: 조각 1개뿐 패턴(뒤판 없음)→뒤번호/이름 piece_id가 첫 조각으로 폴백. area 키 없는 완성본 미등록 패턴→piece_id 부여 안 함(2단계 경고가 담당).

⚠️ reviewer 참고:
- setdefault로 기존 piece_id 유지(2패턴 회귀0 핵심). piece_id는 `pieces`(_build_pieces)의 실제 id를 써서 _inject 매칭키와 정확히 일치.
- work 경고는 `p.has_number_area===false`(strict)만—undefined 구버전 응답 오경보 방지. pm 즐겨찾기 `.pm-added`/`card.children[0]` 로직과 충돌 없음(배너는 card.children[1]).
- 엔진 diff 0(engine/ 무변경, git diff --stat 확인).

## 구현 기록 (developer) — 번호·이름 위치 구멍 수정 [3·4단계]

📝 구현한 기능: 스캔/트리로 드라이브 폴더를 등록할 때, 그 폴더 안의 **완성본·글리프셋 파일을 드롭다운에서 골라** 함께 등록 → 번호·이름 위치가 등록 즉시 채워지게. (서버 from-drive는 reference_file_id/glyph_file_id 이미 지원, UI만 미노출이던 것을 노출.) **엔진 무수정**(webapp/api.py·patterns.html만). 1·2단계(piece_id 자동부여·주문경고)와 결합하면: 완성본 선택→area 추출→piece_id 자동부여→주문 시 번호·이름 실제 출력.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| webapp/api.py `_EXTRA_FILE_EXTS` 상수(≈1471) | 완성본/글리프셋 후보 확장자 `{.ai,.pdf}` 신규(사이즈파일 `_PATTERN_FILE_EXTS` 와 별개, .svg 제외) | 수정(+7줄) |
| webapp/api.py `_scan_folder_pattern_files`(≈1503) | 반환을 `(files,warnings)`→`(files,warnings,others)` **3-tuple**. 사이즈 토큰 없는 .ai/.pdf(임시/보조 제외)를 `others=[{id,name,mimeType}]`로 **추가** 수집. **files/warnings/사이즈인식 로직 무변경**(그 파일은 여전히 warnings에도 남음=회귀0). id 포함(화면 드롭다운 선택용) | 수정(3단계) |
| webapp/api.py patternfiles 응답(≈1570)·from-drive 호출부(≈1629) | patternfiles 응답에 `"others":others` 추가. from-drive는 `files,scan_warnings,_others=`로 언패킹(others 미사용—payload로 직접 받음) | 수정 |
| webapp/static/screens/patterns.html `drivePickRecommend`(신규, ≈driveUniqueSizes 아래) | others 중 파일명 키워드 매칭 첫 파일 id 반환(대소문자무시), 없으면 ""(선택안함). 자동추천 헬퍼 | 신규(+13줄) |
| webapp/static/screens/patterns.html `renderDrivePreviewBody`(≈1561) | others 읽기 + `driveSelectedFolder.others` 보관(안전망). 기준사이즈 아래(섹션5-2)에 **완성본 드롭다운(#driveReference)+글리프셋 드롭다운(#driveGlyph)** 추가. 옵션=`others`, 첫 옵션 "선택 안 함"(value=""), 자동추천(완성/샘플/final/본체포함→완성본, 글리프/glyph/번호/숫자→글리프셋) selected. **후보없음(others 비어있고 sizes>0)**=드롭다운 대신 alert--warn 안내("완성본 후보 없음→로컬 등록 권장", 등록은 계속 가능) | 수정(4단계) |
| webapp/static/screens/patterns.html `registerFromDrive`(≈1648) | 활성패널에서 #driveReference/#driveGlyph 값 읽어 값 있으면 `payload.reference_file_id`/`glyph_file_id` 포함. **선택 안 함(value="")=미포함=기존 동작** | 수정(+11줄) |

🔎 근거(코드 정독): 완성본/글리프셋 파일은 파일명에 사이즈 토큰 없음(예 `..._완성본_본체포함.ai`)→기존 `_scan_folder_pattern_files`에서 warnings("사이즈 인식 못함")로만 빠져 **id가 안 실려 화면에서 선택 불가**. 서버 from-drive(api.py:1650-1659)는 이미 reference_file_id/glyph_file_id→get_file_meta→다운로드→create_pattern(reference=/glyphset=) 완비. 드롭다운 option value=파일 id라 baseSize와 동일 방식으로 활성패널에서 `.value` 읽어 그대로 payload. 옵션 value/name은 driveEsc 이스케이프.

💡 tester 참고:
- **테스트 방법(3단계 백엔드)**: `/api/drive/folder/{id}/patternfiles` 응답에 `others` 키 존재·사이즈없는 .ai/.pdf가 `{id,name,mimeType}`로 담김·.svg는 others 제외(warnings만). 시뮬 검증 PASS(스크래치패드 스크립트): files=[XL,2XL]·others={R1완성본,G1글리프,P1pdf}·warnings 무변경.
- **테스트 방법(4단계 프론트)**: 드라이브 모드→폴더/카드 선택→미리보기에서 (a)완성본·글리프셋 드롭다운 렌더 (b)완성본명에 "완성/본체포함" 있으면 자동선택·글리프명에 "글리프/숫자" 있으면 자동선택 (c)완성본 후보 없는 폴더면 드롭다운 대신 노란 안내(등록 버튼은 여전히 enabled).
- **정상 동작**: 완성본 선택 후 등록→서버 payload에 reference_file_id 포함→preset의 number_area/name_area 생성(+1단계 piece_id 자동부여)→run_job 시 번호·이름 출력. "선택 안 함"이면 reference_file_id 미포함=기존과 동일(번호 없는 등록).
- **주의 입력**: (1)completion 후보 다수인 폴더=자동추천은 첫 매칭만, 사용자가 바꿀 수 있음 (2)완성본이 사이즈있는 파일명이면(예 `완성본_XL.ai`) files로 분류돼 others에 안 뜸=드롭다운 후보 안 됨(현 설계 한계, 후보없음 안내로 로컬등록 유도) (3)같은 파일이 완성본·글리프셋 둘 다로 선택 가능(방어 안 함—서버가 각각 처리).
- **회귀 확인**: 기존 스캔/트리/미리보기/등록·1·2단계 무변경(추가만). others 미지원 구버전 응답에도 `(body.others)||[]`로 안전(드롭다운 안 뜸=기존 동작). from-drive 3-tuple 언패킹으로 등록 정상.

⚠️ reviewer 참고:
- 3-tuple 반환 변경=내부 헬퍼 시그니처. 호출부 2곳(patternfiles·from-drive) 모두 갱신 확인(grep 3매치=정의1+호출2). 외부 API 응답은 키 추가만(others).
- others는 warnings와 **중복 보유**(같은 파일이 양쪽에)=의도적("추가만"으로 warnings 무변경 회귀0 확보). warnings=사람이 보는 제외사유(id없음), others=선택용(id있음).
- 드롭다운 value=파일 id, driveEsc 이스케이프. registerFromDrive는 activeDrivePanel 스코프로 읽어(baseSize와 동일) 자동찾기/트리 탭 id 충돌 방어. driveSelectedFolder.others 보관은 안전망(실제 선택은 dropdown value에서 직접).
- 후보없음 안내는 sizes.length>0(등록가능)일 때만—사이즈파일도 없으면 기존 disabled+안내가 담당(중복 안내 방지).
- 엔진 diff 0(git diff --stat engine/ = 빈 결과). py_compile OK. inline JS vm.Script 파싱 OK(81,970자).

## 테스트 결과 (tester) — 번호·이름 위치 구멍 수정 [3·4단계]

📊 종합: **43개 검증 전부 통과 / 실패 0** · 수정 요청 없음 · 커밋 가능

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| py_compile(api.py) | ✅ 통과 | OK |
| patterns.html inline JS 문법(vm.Script) | ✅ 통과 | 81,970자 컴파일 성공. 변경 조각 13/13 존재 |
| **others 분류(핵심, 실함수 27검증)** | ✅ 통과 | 사이즈파일=files(정렬 M/XL/2XL 무변경)·사이즈없는 .ai/.pdf(비임시)=others(id 포함)·**.svg others 제외**·**임시(~)/.tmp others 제외**·.png 무시 |
| files/warnings 회귀0 | ✅ 통과 | files 키={id,name,size,mimeType}·정렬 무변경. warnings 6건(임시2+사이즈미상4) 구조·reason 문구 무변경. 완성본은 others+warnings 중복보유(의도) |
| patternfiles 응답 others 키 | ✅ 통과 | diff 확인: 응답에 `"others":others` 추가 |
| **from-drive 3-tuple 언패킹** | ✅ 통과 | grep=정의1(1503)+호출2. patternfiles(1570 `files,warnings,others`)·from-drive(1629 `files,scan_warnings,_others`) 둘 다 3-tuple. **2-tuple 잔존 0(크래시 위험 0)** |
| **드롭다운 렌더+drivePickRecommend(14검증)** | ✅ 통과 | "선택 안 함"(value="") 첫 옵션·완성/본체포함→완성본·글리프/숫자→글리프셋 자동추천·매칭없음/빈배열/undefined→""(구버전 `||[]` 방어)·대소문자 무시·첫매칭만·driveEsc 이스케이프 |
| 후보없음 안내 | ✅ 통과 | sizes>0 && others 빈 → alert--warn 안내(등록 계속 가능). others 있으면 드롭다운 |
| **payload(선택안함=기존동작)** | ✅ 통과 | refId/glyphId 있으면 `reference_file_id`/`glyph_file_id` 포함. value=""→미포함=서버 `if reference_file_id:` false→ref_upload None=기존 등록. panel(activeDrivePanel) 스코프로 읽음 |
| CSS/클래스 | ✅ 통과 | select·field__hint·alert--warn 전부 기존 클래스 재사용(발명0). 하드코딩 색상 없음 |
| **연결 완결성(코드 흐름)** | ✅ 통과 | 완성본선택→payload.reference_file_id→서버 다운로드→create_pattern(reference=)→build_area_preset(area추출)→**piece_id 자동부여(1349-64)**→run_job 번호·이름 출력. 이론상 경로 완결(1단계와 결합) |
| 엔진 무수정 | ✅ 통과 | git diff engine/ = 0(api.py/patterns.html/scratchpad만) |

🟡 비차단 관찰(주석 뉘앙스, 동작 문제 0): registerFromDrive 라인 ≈1736 주석 "선택 필드(glyph_file_id·reference_file_id 등)는 이번 UI 에선 생략"이 **바로 아래 3-2 블록이 실제로 추가**하므로 stale(주석-코드 불일치). 기능 영향 없음, 다음 손질 시 주석만 정리 권장.

## 리뷰 결과 (reviewer) — 번호·이름 위치 구멍 수정 [3·4단계]

📊 종합 판정: ✅ **통과** (치명 0 · 커밋 가능)

✅ 잘된 점:
- **3-tuple 호출부 전부 갱신(크래시 위험 0)**: grep `_scan_folder_pattern_files` = 정의1(api.py:1503)+호출2. patternfiles(:1570 `files,warnings,others`)·from-drive(:1629 `files,scan_warnings,_others`) **둘 다 3-tuple 언패킹**. 2-tuple 잔존 0. files/warnings/사이즈 정렬 로직 무변경(others는 `if not size` 블록 내 append만 추가).
- **엔진 무수정**: `git diff --stat -- engine/` = 빈 결과. 변경=api.py(+30)·patterns.html(+71)·scratchpad뿐.
- **others 분류 정확(선행 필터 순서 완벽)**: 폴더 skip → `_is_temp_or_aux_file` warnings+continue(others 제외) → `ext not in _PATTERN_FILE_EXTS` continue → `if not size`에서 `if ext in _EXTRA_FILE_EXTS(.ai/.pdf)`만 others. ⇒ (a)사이즈 있는 파일은 others로 **못 샘**(others가 `if not size` 안에만 존재) (b)사이즈 없는 파일은 files로 **못 감**(files.append 앞 continue) (c).svg 사이즈없음=warnings만·others 제외(_EXTRA_FILE_EXTS에 .svg 없음) — 스펙과 정확히 일치.
- **payload/하위호환**: refSel/glyphSel을 `activeDrivePanel()` 스코프(:1720, baseSize·name과 동일 패턴)로 읽어 `.value` 있으면 payload.reference_file_id/glyph_file_id 포함. 선택안함(value="")=미포함=기존 동작(번호없는 등록). 서버(:1644·1674)는 `str(...or"").strip()`으로 빈값 방어, 완성본만 있으면 다운로드→create_pattern(reference=ref_upload, :1690).
- **잘못된 id 안전**: 서버가 존재하지 않는 reference/glyph id 받으면 get_file_meta/download_file→`gdrive.DriveError`→502 한글 에러(finally에서 임시파일·핸들 정리). 크래시 없음.
- **드롭다운 견고**: `(body.others)||[]`·`drivePickRecommend` 내 `others||[]`로 구버전/빈배열 방어. 자동추천은 첫 매칭만이고 첫 옵션 "선택 안 함"(value="")—미매칭 시 브라우저가 첫 옵션 선택=기존 동작. 옵션 value=파일 id·name 모두 `driveEsc` 이스케이프. 재렌더 시 `driveSelectedFolder.others` 보관(안전망, 실선택은 dropdown value 직접).
- **UX/제약**: 후보없음 안내는 `sizes.length>0`(등록가능)에서만·등록 버튼 별도 enabled(등록 안 막음). CSS 전부 정의(app.css `.field__hint`:357·`.alert--warn`:382·`.alert__title/body`—var(--status-warn-*)/--amber-600·700)·Material Symbols·.select/.field 재사용. py_compile OK.
- **연결 완결성**: 완성본 선택→reference_file_id→create_pattern reference→build_area_preset area 추출→(1단계 piece_id 자동부여)→번호·이름 출력. 이 경로는 1·2단계 run_job e2e(BROKEN 경고3→FIXED 앞"7"·뒤"홍길동+7" 실출력)로 이미 검증됨.

🔴 필수 수정: 없음.

🟡 권장(비차단, 참고만):
- **중복 노출 UX**: 완성본/글리프셋 파일은 warnings("사이즈 인식 못함")와 완성본 드롭다운에 **동시** 노출. 사용자가 미리보기에서 같은 파일을 "제외 사유" 경고로 보면서 드롭다운 후보로도 봄=약간 혼란스러울 수 있으나 무해(회귀0 확보용 의도적 트레이드오프). 여유되면 others에 담긴 파일은 warnings 문구를 "완성본/글리프셋 후보(사이즈 없음)"처럼 톤 조정 여지.
- **자동추천 키워드 중첩**: 완성본 추천에 "본체포함", 글리프셋 추천에 "번호/숫자". 완성본 파일명에 "번호"가 들어가면 글리프셋으로 오추천 가능(예 "…번호위치_완성본.ai"→ref와 glyph 둘 다 추천될 수 있음). **사용자가 드롭다운에서 변경 가능**하므로 비차단. 같은 파일이 ref·glyph 둘 다로 선택돼도 서버가 각각 처리(무해).

## 리뷰 결과 (reviewer) — 번호·이름 위치 구멍 수정 [1·2단계]

📊 종합 판정: ✅ **통과** (치명 0 · 커밋 가능)

✅ 잘된 점:
- **엔진 무수정 확인**: git diff --stat = api.py/work.html/scratchpad 3개만. engine/(reference·job·grade) 무변경. 불변제약 준수.
- **piece_id 매칭 정확**: `_build_pieces`가 pieces[0].id="front"·[1].id="back"·[2].id="band"로 부여 → 부여한 id가 엔진 `_find_piece_index`(job.py:599 `pdef["id"]==piece_id`) 매칭키와 정확히 일치. front→앞판·뒤번호/이름→뒤판이 엔진 관례(job.py:811-814 `_inject("front_number_area"…)/("back_number_area"…)`)와 일치. 하드코딩 문자열 아닌 실제 조각 id 사용.
- **회귀 0**: setdefault라 기존 piece_id 유지. create_pattern은 build_area_preset(piece_id 없는 area) 신규조립 경로라 항상 채움. 기존 2패턴(V넥/U넥)은 create_pattern 미경유 preset.json → 무변경. area 없으면(fa/ba/na=None) if 블록 건너뜀 = no-op.
- **폴백 안전**: pieces는 항상 ≥1(size_files 필수·`n=max(1,…)`)→pieces[0] 실제 id 보장. 1조각뿐이면 back_pid→front_pid 폴백. 3조각(band)도 뒤번호=back(pieces[1]) 정확, band는 번호/이름 대상 아님.
- **has_number_area 정합**: `bool(front or back or name_area)`(각 `get(...,{}) or {}`로 None/빈dict 방어). /api/patterns 신규 필드 추가만 → patterns.html·work.html 기존 소비자 무파괴.
- **work 경고 안전**: `p.has_number_area===false` strict(구버전 undefined 오경보 방지). 진행 차단 안 함(경고 배너만). 배너는 card.children[1]로 분리 → 즐겨찾기 `pmDecorateCardWork`(children[0] 내부 nameBlock에 `.pm-added` 부착, 재렌더 시 remove 후 재부착)와 충돌 0. 배너 텍스트=정적(사용자입력 없음→이스케이프 불필요). 색상 전부 var(--status-warn-*/--amber-6·700/--text-caption) 존재 확인.
- **제약 충족**: py_compile OK · work.html inline JS `new vm.Script` OK · webapp/api·work.html만 · 비밀키 0.

🔴 필수 수정: 없음.

🟡 권장(비차단, 참고만):
- api.py:143 주석 "엔진 `_has_precise_areas`와 같은 기준"은 엄밀히는 다름(_has_precise_areas=키 존재만 검사 / has_number_area=키+비어있지않음). 실데이터에선 area가 항상 비어있지 않아 결과 동일하고, 빈dict를 "없음"으로 보는 게 경고 목적상 오히려 안전. **동작 문제 없음, 주석 뉘앙스만**.
- (신규 convention 후보, PM 승격 판단) "웹계층 piece_id 자동부여는 하드코딩 아닌 `_build_pieces` 산출 id를 써서 엔진 `_find_piece_index` 매칭키와 일치시킨다".

## 테스트 결과 (tester) — 번호·이름 위치 구멍 수정 [1·2단계]

📊 종합: **8개 항목 전부 통과 / 실패 0** · 수정 요청 없음 · 커밋 가능

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| py_compile(api.py) | ✅ 통과 | OK |
| work.html inline JS 문법(vm.Script) | ✅ 통과 | script 1블록 63,789자 파싱 OK, 변경 3조각 반영 확인 |
| **piece_id 자동부여(핵심)** | ✅ 통과 | 실제 완성본 build_area_preset 반환 area 3종 모두 **piece_id 없음(구멍 확인)** → 부여 후 front→'front'·back→'back'·back_name→'back' |
| **piece_id ↔ 엔진 매칭** | ✅ 통과 | `_find_piece_index`로 front→idx0(앞판)·back번호→idx1(뒤판)·back이름→idx1. 앞=앞판/뒤=뒤판 방향 정확. 기존 정상 preset(V넥)의 수작업 piece_id와 값 완전 일치 |
| **기존값 유지(setdefault, 회귀0)** | ✅ 통과 | 기존 piece_id 있으면 미덮음(CUSTOM 유지). 1조각뿐→첫조각 폴백. None area 스킵·pieces빈배열 방어. 기존 2패턴 preset.json git 무변경 |
| **run_job 엔드투엔드(GS 실행)** | ✅ 통과 | BROKEN(piece_id제거=구멍): 경고3건 "조각 못찾아 '7'/'홍길동' 안그림"·preview에 번호/이름 없음. FIXED(수정): 경고0·**preview에 앞 "7"·뒤 "홍길동"+"7" 실제 출력**·fill연산 3→6 |
| has_number_area 정확 | ✅ 통과 | 실2패턴=True, area없는/빈dict 구멍=False. glyph_source와 동일 방식 |
| work 경고 배너 | ✅ 통과 | ===false strict(undefined 오경보X)·진행 허용(click핸들러 유지)·pm 즐겨찾기(.pm-added=children[0]내부 vs 배너=children[1]) 무충돌·CSS변수 전부 정의 |
| 엔진 무수정(핵심) | ✅ 통과 | git diff engine/ = 0줄 |
| 회귀0(추가만) | ✅ 통과 | from-drive가 create_pattern 재사용(api.py:1662, reference 전달)→로컬·드라이브 둘 다 수정 적용 |

🟡 비차단 참고(reviewer와 동일 관찰): api.py:143 주석 "_has_precise_areas와 같은 기준"은 엄밀히 다름(엔진=키존재 / has_number_area=키+비어있지않음). 실데이터 동일결과·경고목적상 오히려 안전. **주석 뉘앙스만, 동작 문제 0**.

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
| 2026-07-09 | tester | [Phase B] 3·4단계 백업훅+startup복원훅 검증 | **전항목 통과·실패0·수정요청0·커밋가능**. py_compile3파일OK·**라우팅무결성(TestClient build OK=시그니처안깨짐, POST patterns/from-drive 등록, 빈POST 422)**·**이중백업방지(backup_pattern 실호출 1곳뿐)**·degrade(예외스텁 삼킴+미설정 실등록e2e 200)·**startup 0.001s즉시반환+복원예외 스레드격리**·미설정skip(예외0)·토큰추출7케이스·엔진diff0. 실네트워크는 버킷생성 후 배포e2e |
| 2026-07-09 | developer | [Phase B] 3·4단계 백업훅(api.py)+startup복원훅(main.py) 결선 | 3단계: create_pattern 성공 return 직전 backup_pattern 호출(request 주입+_extract_bearer_token JWT릴레이·try/except degrade). **이중백업 방지=from-drive가 create_pattern 재사용→백업은 create_pattern 1곳뿐**(from-drive는 request만 전달). 4단계: main.py @on_event startup→daemon 백그라운드 스레드로 restore_missing(즉시반환=부팅안막음). **py_compile OK·엔진diff0·스모크(startup 0.000s즉시반환·미설정no-op·토큰추출 5케이스) 통과**. 미커밋(tester+reviewer 후 PM 커밋) |
| 2026-07-09 | tester | [Phase B] 2단계 storage_backup.py 검증 | **39/39 통과·실패0·수정요청0·커밋가능**. 미설정degrade(예외0)·jwt없음skip·zip왕복내용보존·zip-slip 3종 방어(밖에파일0)·손상zip skip·restore 로컬우선(회귀0)·httpx모킹 200/403/타임아웃·헤더규칙(apikey=publishable+Bearer user_jwt+x-upsert)·비밀키하드코딩0/로그노출0·env변수명 auth.py일치. 실호출 e2e는 3·4단계 결선 후 |
| 2026-07-09 | developer | [Phase B] 등록패턴 파일영속화 1·2단계(Storage 설정가이드 md + storage_backup.py) | 가이드 md(버킷 pattern-presets+RLS 3정책 SQL 복붙) / storage_backup.py(backup_pattern JWT릴레이·list_backups·restore_missing·zip-slip방어·미설정/no-jwt skip degrade). **api.py/main.py 무수정(훅은 3·4단계)**. py_compile OK·엔진diff0·스모크(미설정skip/zip왕복/zip-slip차단/손상skip) 통과. httpx 기존존재 |
| 2026-07-07 | tester | 번호·이름 위치 구멍 수정 3·4단계 검증 | **43검증 전부 통과·실패0·수정요청0**. others 분류 실함수 27검증(사이즈파일=files 정렬무변경·사이즈없는.ai/.pdf=others id포함·**.svg/임시/.tmp others제외**·회귀0)·from-drive 3-tuple 언패킹 2-tuple잔존0·drivePickRecommend+드롭다운 14검증(선택안함 첫옵션·자동추천·구버전 방어)·**선택안함=기존동작**·연결완결성 코드흐름(완성본선택→reference_file_id→area추출→piece_id자동부여) 확인·엔진diff0 |
| 2026-07-07 | developer | 번호·이름 위치 구멍 수정 3·4단계(스캔등록 완성본·글리프셋 파일선택) | api.py `_scan_folder_pattern_files` others 버킷(사이즈없는 .ai/.pdf, id포함) 추가·patternfiles 응답+others / patterns.html 완성본·글리프셋 드롭다운(자동추천 완성/글리프·후보없음 안내)+payload reference_file_id/glyph_file_id. **선택안함=기존동작·warnings 무변경(회귀0)·엔진 diff 0·py_compile OK·inline JS 파싱 OK**. 시뮬검증(백엔드 분류·JS 추천) PASS |
| 2026-07-07 | tester | 번호·이름 위치 구멍 수정 1·2단계 검증 | **8/8 통과·실패0·수정요청0**. 완성본 build_area_preset area=piece_id 없음(구멍확인)→부여 front/back/back가 엔진 _find_piece_index 매칭. **run_job GS실행 e2e: BROKEN preview 번호·이름 없음(경고3) vs FIXED preview 앞"7"·뒤"홍길동+7" 실출력(경고0)**. setdefault 회귀0·기존2패턴 무변경·엔진diff0·work배너 strict/즐겨찾기무충돌 |
| 2026-07-07 | developer | 번호·이름 위치 구멍 수정 1·2단계(piece_id 자동부여 + 주문경고) | api.py create_pattern area에 piece_id setdefault 자동부여(pieces 실제 id, 앞→front·뒤번호/이름→back)+_scan has_number_area / work renderPatterns warn배너. **엔진 무수정**. py_compile OK. e2e run_job: BROKEN 경고3건→FIXED 0건 PASS. **reviewer 통과(치명0): 엔진무수정·piece_id 매칭정확·회귀0·제약충족)** |
| 2026-07-07 | developer | 즐겨찾기 별 스타일: 빨강 아웃라인→골드 채움 | patterns/work.html 별 색 var(--brand)→var(--star-fav)+FILL 1(속채움). colors.css에 --star-fav(=amber-500 재사용) alias 1개 추가. 동작 무수정·OFF 회색빈별 유지 |
| 2026-07-07 | dev/tester/rev | 즐겨찾기+자동분류 프론트(patterns/work, Supabase pattern_meta 직접) | feat 27b96db·tester113assert/0·rev치명0. degrade·트리회귀0·work선택흐름무변경·별표 admin쓰기/전원읽기·카테고리=폴더트리최상위 |
| 2026-07-07 | planner-architect | 즐겨찾기+자동분류 설계 | 프론트direct Supabase+RLS·단일표 pattern_meta·카테고리 폴더트리·파일영속화 Phase B 분리 |
| 2026-07-07 | dev/tester/rev | 패턴폴더 자동스캔 프론트([자동찾기]탭+카드그리드) | 25f490c·tester69/69·트리회귀0·입력칸중복0. 배포 실서버 74폴더 카드 확인 |
| 2026-07-07 | dev/tester/rev | 패턴폴더 자동스캔 백엔드(GET /drive/scan 벌크2쿼리+캐시) | f3b3257·tester68/68·회귀0·추가만271 |
| 2026-07-07 | planner-architect | 자동스캔 설계 | 벌크2쿼리 발견전용·등록은 기존 정확경로·name contains 금지 |
