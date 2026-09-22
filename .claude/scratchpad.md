# 작업 스크래치패드

## 현재 작업
- **2026-09-22 (Fable 5.1 세션)**: 실사용 개선 TOP7 — **#1·#2·#3(삭제)·#5·#6·#7 완료**, #4 는 정직 안내만(좌표 전송 미구현). + toast XSS·`_find_job_dir` 남의 ZIP 버그 수정. 커밋 0ae5f26·a2f2d08·2f316c8 (**미푸시 3**).
- **🚨 운영 서버 grader-v2-47gd.onrender.com 이 Render 에서 «suspended»(503, x-render-routing: suspend)** — 코드가 아니라 계정/플랜. 사장님이 Render 대시보드에서 확인 필요. 직원은 지금 접속 불가.
- **실사용 e2e(로컬, 실주문서 연세대 38행 + 실디자인 .ai)**: 파싱 38/38 정확 · V넥 12행 생성 14초 · 검사 전부 PASS · EPS 11/11 · 미리보기 육안 정상. **3XL 5명(13%)은 자산 결함으로 생성 불가**(skip 배너로 표시됨).
- **다음**: ① Render 복구 ② 3XL.ai 재확보 ③ ZIP 에 주문요약(수량 포함) 동봉 ④ 이력 화면 재다운로드 ⑤ B/C 좌표 실제 전송. 상세 제안은 PM 보고(2026-09-22).

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

## 구현 기록 (developer · 2026-09-22 제안⑤ B/C 편집기 좌표 실제 저장)
- **api.py**: `create_pattern` 에 `layout: Optional[str] = Form(None)` 추가(from-drive 무수정). 신설 `_apply_layout`·`_layout_page_frame`(design_file MediaBox→완성본→화면 힌트→preset page_size_pt)·`_norm_rect`·`_norm_to_pt`(y 뒤집기)·`_layout_find_piece`(id→index). preset 조립 뒤 «보낸 항목만» `pieces[].design_region_pt`·`back_number_area`·`back_name_area`(·front_number) 덮어쓰기. 전 조각 덮으면 균등분할 경고 제거. 응답 `layout_applied:{pieces,areas}`. 틀린 layout=경고+자동 추정 유지(200).
- **patterns.html**: B/C 영역에 `dataset.touched`(시드 0 · 직접 그림/이동/리사이즈 1). `buildLayoutPayload()` → 손댄 것만 `layout` JSON(정규화 0~1·좌상단, C 는 뒤판 조각 상대 piece_id:"back"). 배너 «여기서 맞춘 위치가 등록 시 저장돼요»(alert--info)·힌트 문구·성공 토스트 «맞춘 위치 N개 저장». `resetRegister` 가 편집기 영역도 비움(지난 등록의 손댄 영역 재전송 방지).
- 검증: py_compile·vm.Script·selftest PASS. TestClient (a) a273ff2 워크트리 vs 현재, layout 없이 등록 → preset·응답 **완전 동일**(layout_applied 만 추가) (b) pieces 1·areas 2 → 해당 키만 변경·수동 계산 일치 (c) JSON 깨짐·범위 밖·없는 piece·비dict → 200+경고+auto 와 동일 (d) from-drive 코드 정독 무영향 (e) 임시 패턴 2개로 run_job 1행 각각 8/8 PASS, 미리보기 PNG 에서 번호·이름이 layout 대로 이동 확인. 브라우저 :8000 — 시드 미전송·드래그 후 등록 → 서버 preset front/band/back_number 정확, back 자동 유지, 토스트 "맞춘 위치 3개 저장". 임시 패턴 8개·job 2개·uploads 15개·워크트리 정리(PM 0125* 보존).
- tester 참고: 화면 3번째 조각 id 는 'sleeve'(서버 'band' 는 index 2 로 매칭). C 캔버스 = 뒤판이라 앞번호는 항상 자동. 브라우저 드래그는 pointer 합성 이벤트로 검증(실 OS 드래그는 tester 확인 권장).

## 구현 기록 (developer · 2026-09-22 ZIP 주문요약 동봉 — 완료·커밋 37498cc)
- api.py `order_rows.json` 저장 · `_build_manifest_rows` · 주문요약.csv/xlsx ZIP 동봉 · `GET /jobs/{id}/manifest` · work.html 안내 1줄. 상세는 커밋 37498cc + 아래 tester 결과. 구 job 제외 행은 배번 빈칸.

## 구현 기록 (developer · 2026-09-22 제안④ 이력 화면 재다운로드 + 패턴 표시)
- **api.py**: `create_job_endpoint`(~896) 가 `job_meta.json`{pattern_id,design_name(토큰 `__` 뒤 원본명),out_format,created,total} 저장(임시파일→os.replace·실패 무시) · `_design_display_name()` 신설 · `_job_summary`/`GET /jobs` 에 `format`(meta→summary.format 폴백, 구 job 도 채워짐)·`design`·`skipped`(summary.skipped 길이)·`has_files`(output/ 존재) 추가. 구 job 은 pattern "-" 유지·정렬 그대로.
- **history.html**: esc 헬퍼+toast 이스케이프 · 헤더 형식 칸 · 행마다 `PDF ZIP`·`EPS ZIP`(형식상 없는 쪽 disabled+title, has_files=false 면 둘 다 잠금+"파일 없음(재배포로 삭제됨)")·`요약표`(GET /manifest → 행 아래 접이식 표, 캐시) · 다운로드=apiFetch→blob→a[download](Content-Disposition filename* 존중)·연타 방지·404 토스트. 가짜 재생성/더보기 버튼 제거.
- 검증: py_compile·vm.Script OK · TestClient 새 job(연세대 3행·V넥·both) pattern/format/design/has_files ✓, 구 ffc664 "-"/both/skipped 5 ✓, output 이름변경→has_files false→원복 ✓, zip pdf/eps 200+CD ✓ · 브라우저 :8000 버튼·요약표 38행 펼침·잠금 행 ✓, 콘솔 404 1건은 외부(fonts) 기존 · selftest PASS · 만든 job·업로드 삭제(PM 0125* 2개 보존).
- tester 참고: 주문명 칸은 여전히 폴더명(job.json 에 주문서명이 없고 POST /jobs 도 안 받음) — 이번 범위 밖.

## 테스트 결과 (tester · 2026-09-22 제안⑤ B/C 편집기 좌표 실제 저장)
- **판정: 통과 — 회귀 0 증명·layout 환산·오류 6종+폭탄·엔진 반영·브라우저 실마우스·안전, 실패 0.** ① 회귀: `git worktree add … a273ff2` 로 옛 코드 트리 → 같은 V넥 SVG 12개로 layout 없이 등록(완성본 없음/있음 2벌) → preset.json 키정렬 비교 **완전 동일**, 응답도 `layout_applied` 제외 동일, 폴더 파일 목록 동일. from-drive 정독: layout 인자 자체를 안 넘김(무영향).
- ② 적용: pieces 1 + areas 2(정규화) → MediaBox(4478.74×5669.29, pikepdf 로 실제 읽음) y 뒤집기 손계산과 **소수 1자리까지 일치**(front [447.87,566.93,2239.37,2834.64] · back_number center [2239.4,3259.8] cap 283.5 · back_name baseline 2645.7 em 189.0 pitch 270.8=em×1.4326). 손대지 않은 back/band·나머지 키 = 자동본 그대로(바뀐 키 정확히 3개). 조각 3개 전부(+`sleeve`→index 2 폴백)면 균등분할 경고 제거·실 preset 값 왕복 오차 ≤0.2pt · 완성본 있으면 색/폰트 유지·pitch 비율 유지(346.6) · front_number 자동 그대로. 응답 `layout_applied` 수 일치.
- ③ 오류: JSON 깨짐·범위 밖·x0>x1·없는 piece·문자열 bbox·비dict·NaN → 전부 200 + `[layout]` 경고 + preset = 자동본. 1MB 문자열·`[`×10만·`{"a":`×5만 → 200 경고(서버 생존, health 200). **1MB 초과 JSON 은 starlette 가 400 "Part exceeded maximum size of 1024KB"**(등록 자체 거절, 폴더 없음 — 허용 범위). ④ 엔진: 기준/이동 패턴 각 run_job 1행 XL **8/8 PASS**, 미리보기 PNG 픽셀 측정: 번호 Δ888px(예상 887) · 이름 Δ2449px(예상 2446) · cap 769px(예상 770) — layout 값이 실제 합성에 그대로 먹음.
- ⑤ 브라우저(:8000 내가 띄운 PID→종료, 실마우스 드래그): 소매 영역 그림 + 배번 영역 아래로 끌기 → FormData `layout` = **손댄 2개만**(sleeve index 2 · back_number) · 시드 front/back·name 미전송 · 서버 preset band/back_number 손계산 일치·front/back 균등분할 유지 · 토스트 «맞춘 위치 2개 저장». 새 등록 시작 → 캔버스 0개·pieceRegions 빈·payload null · 소매만 그리고 등록 → `layout` 1개·«맞춘 위치 1개 저장»(지난 등록의 배번 이동 재전송 없음). 콘솔 새 에러 0(기존 8건은 이전 history 탭 zip 404).
- ⑥ 안전: layout id/index 로 경로 접근 0(os.path/open 없음) · `../<script>` id → 경고 문구에만 들어가고 toast 는 driveEsc 이스케이프 · 하드코딩 색 0 · engine/auth/gdrive/storage_backup/main/state/_handoff diff 0 · `_find_piece_index` 는 조회만. 참고(차단 아님): (a) UI 는 소매 매핑이 필수라 **layout 없는 등록(«위치는 자동 추정» 토스트)은 화면에선 도달 불가**(from-drive 전용) (b) 시드 front/back 을 안 옮기면 화면엔 «모든 조각 매핑» 인데 저장은 균등분할 추정 — 직원 안내 필요 (c) `pieces:"front"` 같은 타입 틀린 컬렉션은 경고 없이 무시(무해) (d) `#pname` 은 resetRegister 가 안 비움(기존). 정리: 임시 패턴 22·job 2·uploads 268·워크트리 삭제, 실패턴 2·0125* 보존.

## 테스트 결과 (tester · 2026-09-22 ZIP 주문요약 — 커밋 37498cc)
- 통과 70/70·회귀 0. 수정 권장 1(csv/xlsx `=1+1` 인젝션 → 수정 요청표·errors.md).

## 테스트 결과 (tester · 2026-09-22 제안④ 이력 재다운로드 + 패턴 표시)
- **판정: 통과 — TestClient 46 · 인증 ON 4 · 브라우저 DOM · 안전 4, 실패 0.** 정적 3종 OK. 새 job(연세대 3행·V넥·both, 4.5s): `/jobs` 첫 항목 pattern 농구_V넥_양면·both·design 원본명·has_files true·skipped 0·count 3 · `job_meta.json` 5키 정확·.tmp 없음 · zip pdf/eps/both 200 + `filename*=UTF-8''` · 구 ffc664 "-"·both·skipped 5 · output 개명→has_files false·zip 404·manifest 200→원복 ✓ · 깨진 meta 5종(배열·깨진JSON·빈·null·HTML) 폴백 "-"/both/"" 목록 200.
- 회귀: id/date/name/count/status 유지 · mtime 내림차순 · **`/jobs` 34개 45ms**(manifest 재조립 없음). 인증 ON 별도 프로세스: `/api/jobs`·zip·manifest 토큰 없이 **401**(health 200) · apiFetch Bearer 부착·401→login(코드 정독).
- 브라우저(:8000 내가 띄운 PID→종료): 헤더 7칸(형식) · dadbbf "33 · 제외 5"·PDF·EPS ZIP disabled(title) · 요약표 38행 펼침/닫기/재펼침(캐시) ✓ · PDF ZIP→서버 200·토스트 파일명 `web_…_pdf.zip` · PM job PDF ZIP **3연타→서버 요청 1회** · EPS ZIP 200 · 파일 없는 행 잠금+문구 · job_meta `<b>`·`<img onerror>`·사유 `<b>` 전부 글자(b/img 요소 0) · toast 주입도 글자 · 콘솔 앱 에러 0(외부 Pretendard 404·내가 낸 EPS 404 뿐).
- 안전: diff 내 하드코딩 색 0 · _handoff/engine/auth/gdrive/storage_backup diff 0 · `_design_display_name` 은 basename+`__` 뒤만 표시용(`../../x/y__z.ai`→`z.ai`), 파일 접근은 `_resolve_design_path` 별도 ✓. 만든 job·uploads·임시 폴더 삭제, PM 0125* 2개 보존, ffc664 폴더 mtime 을 job.json 시각으로 복원.
- 참고(차단 아님): ① 형식 모르는 구 행의 없는 형식 ZIP 404 토스트가 "재배포로 지워졌을 수…"로 시작(사유는 뒤에 붙음) ② 정렬·날짜=폴더 mtime 이라 폴더를 건드리면 맨 위로 튐(기존) ③ 26MB ZIP 은 버튼만 잠긴 채 ~10초.

## 백로그 (차단 아님, 후속)
- **[Phase B: 등록패턴 파일 영속화]** Render 임시디스크→재배포 시 등록 preset 소실(현 repo커밋 2개만 잔존). 복구=재스캔등록(같은이름이면 메타 자동재적용). preset 20~88KB 소형→Supabase Storage 백업/복원 별도 승인단위로.
- **[즐겨찾기/분류 후속]** updated_by 프론트 미전송(SQL nullable이라 OK). 별표 이중클릭 debounce 없음(멱등). 카테고리 라벨 정규화 목록(PM_KNOWN_CATEGORIES) 조정 여지.
- **[Drive UI 후속]** DRIVE_SIZE_ORDER=백엔드 _SIZE_TOKENS 프론트복제(동기화 의무). glyph_file_id/reference_file_id 미노출(서버지원). 카드 **수정** 무동작(disabled "준비 중" — 수정 API 없음).
- **[패턴 삭제 후속 · 2026-09-22]** 삭제는 `_trash/` 이동만이라 **Storage 백업 zip 은 남는다** → 재배포 startup `restore_missing`(로컬에 없는 것만 복원)이 지운 패턴을 되살린다. 막으려면 storage_backup 에 삭제(DELETE object) 추가 필요(금지영역이라 미구현, UI·응답에 경고만). `_trash/` 영구 정리(TTL) 없음. pattern_meta(즐겨찾기) 행은 삭제 시 안 지움. B/C 편집기 좌표 실제 전송(create_pattern 인자 확장)은 여전히 미구현.
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
| tester | webapp/static/screens/patterns.html regFailMsg(≈1180) | [TOP7 #6 회귀] 502/503/504 에서 body.error(서버 JSON, 예: from-drive "Drive 접근 실패: …")가 있어도 "서버가 깨어나는 중"으로 덮음 → 드라이브 권한 문제를 콜드스타트로 오안내. 수정안: body.error 있으면 그걸 우선, 없을 때(HTML 게이트웨이 응답)만 깨우는중 문구 | 대기 |
| tester | webapp/api.py `_manifest_table`(≈1290)·`_manifest_xlsx_bytes` | [수정 권장·회귀 아님] 주문요약 인젝션 — `=1+1` 이 CSV 그대로, xlsx 는 openpyxl 수식 셀('f'). 수정안: `=+-@\t\r` 접두 문자열에 `'` 접두 + xlsx `data_type='s'` | 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-09-22 | tester | [제안⑤ 검증] a273ff2 워크트리 회귀 diff 0 · layout 환산 손계산 · 오류 6종+폭탄 · run_job 픽셀 측정 · 브라우저 실마우스 2회 · 안전 | **통과** 실패 0 · 참고 4(UI 는 소매 필수라 layout 없는 등록 불가 등) · 정리 완료 |
| 2026-09-22 | developer | [제안⑤ B/C 좌표 저장] layout 폼 필드(정규화→pt 서버 환산) · touched 만 전송 · 배너/토스트 갱신 | (a)회귀 diff 0 (b)(c)(e) 통과 · 브라우저 확인 · decisions 1건 · 커밋 대기(PM) |
| 2026-09-22 | tester | [제안④ 검증] 정적 3종·TestClient 46·인증 ON 401·브라우저 DOM(연타 1회·HTML 이스케이프·잠금)·안전 4 | **통과** 실패 0 · 참고 3(토스트 문구·mtime 정렬·대용량 대기) · 정리 완료 |
| 2026-09-22 | developer | [제안④ 이력 재다운로드] job_meta.json · /jobs format/design/skipped/has_files · history 버튼 3개+접이식 요약표 | TestClient 15/15 · 브라우저 확인 · selftest PASS · 커밋 대기(PM) |
| 2026-09-22 | tester | [ZIP 주문요약 검증] 정적 3종·e2e 38행 both·csv/xlsx/manifest 대조·회귀·주입·인젝션 | 기능 70/70 통과 · 수정 권장 1(csv/xlsx 인젝션) · errors.md 1건 |
| 2026-09-22 | developer | [ZIP 주문요약] order_rows.json 보존 · 주문요약.csv/xlsx 동봉 · /manifest API · work 안내 1줄 | e2e 38행 수량합 87 일치 · selftest PASS · 커밋 대기(PM) |
| 2026-09-22 | pm | scratchpad 100KB→정리(완료 섹션 삭제, 로그 요약) · 실사용 e2e 검증 · Render suspended 발견 · 개선 제안 | 커밋 docs |
| 2026-09-22 | dev+tester | [TOP7 #3·#4·#7 + toast XSS + _find_job_dir] | 2f316c8 · tester 52/52 · engine diff 0 · errors.md 17항목 |
| 2026-09-22 | dev+tester+pm | [TOP7 #2·#5·#6] 콜드스타트 거짓표시 3종 | a2f2d08 · tester 57/59→PM 수정(502 원문 유지)→통과 |
| 2026-07-16 | developer | [TOP7 #1] 데모 ORDER 48명 제거 + step2 게이트 | 0ae5f26 · tester 5/5 |
| 2026-07-16 | planner-architect | [실사용 전체진단] TOP7 도출(코드정독, 수정 0) | 안전지대: engine/auth/gdrive/비밀키/hex백업 |
| 2026-07-09 | 전원 | [Phase B] 등록패턴 Storage 백업/복원 완료·실서버 e2e | 한글키→hex. 커밋 82c3364~7e47bf1 |
