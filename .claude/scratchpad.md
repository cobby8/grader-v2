# 작업 스크래치패드

## 현재 작업
- **상태**: ✅ **즐겨찾기 + 자동분류(폴더 트리 기준) 완성·커밋**(feat 27b96db·docs 685b745, tester 113assert/0·rev 치명0). Supabase pattern_meta에 프론트 직접 read/write(백엔드 키리스). 미푸시 2.
- **현재 담당**: pm → planner-architect (**신규기능: 번호위치 구멍 수정**). ✅즐겨찾기+자동분류 배포·SQL실행·별표저장 확인·별표 골드채움 e27ac16. **발견된 구멍(조사 완료)**: from-drive(스캔) 등록 패턴은 완성본 미지정→preset에 number_area/name_area 없음→주문 시 번호·이름 조용히 미출력(에러없음, 몸판+재단선만). 2차구멍: build_area_preset가 만든 area에 piece_id 없음(_inject가 piece_id로 조각찾기→None이면 건너뜀). 현정상 2개(농구V넥/U넥)는 preset 수작업 piece_id 박힘. 근거: job.py:604-607/763-814/596-601, grade.py:235-240, reference.py:290-306/355-376, api.py:1276-1345/1564-1636. **사용자 선택=제대로 고치기**: (1)스캔등록에 완성본·글리프셋 파일선택 노출(서버 reference_file_id/glyph_file_id 이미지원) (2)piece_id 자동부여(웹계층·엔진무수정) (3)주문화면 번호위치없음 안전경고(has_number_area 플래그). architect 설계중.
- **⏳ 별개 남은것**: 즐겨찾기 라이브 비관리자 쓰기막힘 확인은 사용자 계정 있을때.
- **최근 완료(2026-07-06~07, 상세는 git+아래 작업로그)**: Drive Phase1(백엔드)+Phase2(프론트 트리/미리보기/등록)+배포+admin권한(Supabase role) → SSL동시성수정(스레드로컬) → **패턴폴더 자동스캔**(GET /drive/scan+카드그리드) → **즐겨찾기+자동분류**. 배포 URL grader-v2-47gd.onrender.com. 로컬 127.0.0.1:8000 병행.
- **카테고리 라벨 정책(사용자 확인 여지)**: 최상위폴더/이름을 pmMatchKnownCategory로 "0.농구→농구" 정규화. 원하는 라벨 다르면 PM_KNOWN_CATEGORIES 조정. 관리자 override 가능.

## 기획설계 (planner-architect) — 번호·이름 위치 구멍 수정 [승인 대기]

🎯 목표: 스캔/로컬 등록 패턴에서 번호·이름이 조용히 안 찍히는 구멍을, 엔진 무수정으로 웹계층에서 제대로 고친다.

📍 만들/고칠 위치:
| 파일 | 역할 | 신규/수정 |
|------|------|----------|
| webapp/api.py create_pattern area 후처리(1327-1345, glyph_source 붙이는 그 자리) | piece_id 자동주입(front→pieces[0].id, back번호/이름→pieces[1].id) | 수정(추가 ~8줄) |
| webapp/api.py _scan_one_pattern(137-155) | has_number_area 플래그 반환 | 수정(2줄) |
| webapp/api.py _scan_folder_pattern_files(1489-1507)+patternfiles 응답 | 사이즈없는 .ai/.pdf "기타 파일" 버킷(id 포함) 반환 | 수정(추가 ~10줄) |
| webapp/static/screens/patterns.html renderDrivePreviewBody(1561)+registerFromDrive(1648) | 완성본·글리프셋 드롭다운(기타파일 기반, 선택안함=기존동작)→payload reference_file_id/glyph_file_id | 수정 |
| webapp/static/screens/work.html renderPatterns(542) | has_number_area=false면 "번호·이름 안 찍힘" 경고(허용+경고) | 수정 |

🔗 기존 코드 연결: from-drive는 이미 create_pattern 재사용 → piece_id 고침 1개로 로컬+드라이브 동시 해결. server가 reference_file_id/glyph_file_id 이미 지원(1599-1636), UI만 미노출.

📋 실행 계획(각 독립 커밋, 단계 후 tester+reviewer 병렬):
| 순서 | 작업 | 담당 | 선행 |
|------|------|------|------|
| 1 | piece_id 자동부여(백엔드, create_pattern) — 로컬+드라이브 즉효 | developer | 없음 |
| 2 | has_number_area 플래그 + work 주문경고(사고예방) | developer | 없음(1과 병행가능) |
| 3 | patternfiles 기타파일 버킷(백엔드) | developer | 없음 |
| 4 | 스캔등록 완성본/글리프셋 드롭다운(patterns.html) + payload 연결 | developer | 3 |

⚠️ developer 주의: 엔진(reference.py/job.py) 무수정. piece_id는 기존 있으면 유지(2패턴 회귀0). area 키 있을때만 주입. 완성본 파일이 폴더에 없을 수 있음(드롭다운 "후보없음"+로컬등록 대안). 프론트 사이즈정렬=순서표 인덱스.

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
