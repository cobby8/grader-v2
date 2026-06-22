# 작업 스크래치패드

## 현재 작업
- **요청**: FastAPI 웹 도구 구동(웹앱1~5) + 출력형식 PDF/EPS/both. 의뢰서: FastAPI-구동·출력형식-PDF-EPS·디자인-시안보강.
- **상태**: ✅ **출력형식 + 웹앱1~5 전부 완료·커밋** (미푸시 8개 — 푸시 확인 대기). 직원 E2E 완료기준 달성.
- **현재 담당**: pm

## 진행 현황 (완료)
| 작업 | 내용 | 상태 |
|------|------|------|
| 정합보정 4이슈 | 번호잉크정렬·재단선·암홀X3조각·번호글리프셋 | ✅ 완료·푸시 |
| 빈본체 design_file | 88KB 본체 정식 설정(3.4KB→88KB) | ✅ 커밋 |
| 출력형식 | flatten Group제거(EPS벡터)·eps2write·verify_eps·run_job out_format·--format | ✅ (tester 13/13·rev 통과) |
| 웹앱1 | FastAPI 골격+정적서빙+health/patterns/settings | ✅ |
| 웹앱2 | order/parse + design/check 5케이스 | ✅ |
| 웹앱3 | jobs 비동기+progress/preview/zip | ✅ |
| 웹앱4 | jobs기록+패턴등록+설정저장 | ✅ |
| 웹앱5 | run.bat+직원 E2E(완료기준 달성) | ✅ (rev 종합 통과 치명0) |

## 백로그 (차단 아님, 후속)
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·design_token·_JOBS TTL 정리 루틴(디스크/메모리 누적 방지). progress 진행 콜백.
- **[출력형식]** verify_eps origin_ok 무의미가드, GS 절대경로후보·임계 하드코딩 preset화.
- **[디자이너 입력 대기]** 재단선 PDF 포함 .ai 재출력(이슈4 인프라 완비) / 올바른 3XL.ai 재확보(현 disabled).
- **band design_region** cowork 정밀 재추출. cowork 최종 오버레이 검증(번호글리프셋·밴드·재단선·본체).
- 하의 사이즈 분리 / 주문서 자동판별 ③우선 가드 / shrink 등방 / sizes.scale.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) + build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로·번들러 없음). 폴더+JSON(DB없음). CLI/curl 단독검증. GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만).

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left·등방 contain). grade `_piece_transform`(job `_job_piece_transform` 복제).
- 글자주입: text place_number/place_name(잉크 bbox 중앙정렬, 디자인좌표 ops) → job이 조각 transform 감싸 extra_ops 주입(클립 밖). 재단선도 동일(클립밖 너치보존).
- 번호: preset glyph_source 있으면 디자이너 글리프셋(number_glyphs.json), 없으면 HY헤드라인 폴백.
- **디자인 본체 핵심**: .ai는 "PDF 호환 저장(Create PDF Compatible File)" 켜야 본체가 PDF 콘텐츠에 들어감. 안 켜면 본체/재단선이 일러스트 전용 데이터에만 → PDF콘텐츠 3.4KB·흰화면. 정상 빈본체=88KB(파란본체+밴드+재단선3, 텍스트0). design_source/README.md에 규칙 명시.
- **출력형식**: flatten은 Form 투명도그룹 제거(EPS 래스터화 트리거)·페이지그룹 /CS 보존(색시프트 방지)·알파잔존시 제거가드. eps2write(GS, output/pdf·eps 분리). compose가 페이지그룹 부활→pdf_to_eps 직전 재제거. EPS 305KB 벡터.
- **V넥 패턴**: 암홀X 3조각 front0/back1/band2. viewBox 4337×3401. 12사이즈(3XL disabled=원본결함). disabled_sizes는 sizes 밖(build_layouts 미순회→grade/job 안전).
- ⚠️ 변환함정(errors.md): 조각수+verify만으론 부족→viewBox통일·양수·비-XL 미리보기 육안. 인접사이즈 좌표동일=자산결함(check_size_monotonicity). STIZ 주문서 헤더 nbsp.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job(정밀배치+재단선+disabled+out_format)·svg_normalize(+가드)·order(①②③STIZ)·flatten(+Group제거)·eps(pdf_to_eps·verify_eps)·compose·verify·preview·grade.
- CLI: grade/job/reference/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- **webapp/**: main(FastAPI:/static 마운트+/api+GET/→work)·api(health/patterns/settings GET·PUT, order/parse, design/check 5케이스, jobs 비동기+progress+preview+zip, jobs기록, patterns 등록POST)·state(설정·업로드·job메모리)·run.py·run.bat. webapp/static=_handoff/grader-v2-static 복사본(원본 보존, 디자인 갱신시 재복사).
- 보조: scripts/ai_to_path_svg.py, illustrator-scripts/ai_to_svg.jsx.
- 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면(SVG12+preset+number_glyphs.json)}. data/{jobs,uploads}/(.gitignore). data/settings.json(gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai, README): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base) / _숫자글리프셋_아트보드2.ai(글리프셋) / _완성본_본체포함_XL.ai(참고).
- 빈본체/완성본/주문서(구): C:/Users/user/Desktop/새 폴더/. 암홀X 패턴: Desktop/V넥 스탠다드-A(암홀X)/. 본체 살아있는 라인작업본: G:/공유 드라이브/CHINA FACTORY/order list/...라인작업/.
- 폰트: data/fonts/HY헤드라인M.ttf(이름. 번호는 글리프셋). GS: C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- git: origin=cobby8/grader-v2, main. **미푸시 8개**(design_file·출력형식 docs/feat·웹앱1~5).

## 기획설계/구현/테스트/리뷰
(완료 — 상세 git 히스토리 + knowledge. 출력형식 tester13/13·rev통과, 웹앱 각단계 dev E2E·rev종합 통과 치명0)

## 구현 기록 (developer)
🐞 실제 OS 파일 드롭 버그 수정 (2026-06-22, debugger · webapp/static/screens/work.html만 · engine/api.py/main.py/_handoff 무수정)

| 회차 | 수정 내용 | 수정 파일 | 비고 |
|------|----------|----------|------|
| 1차 | wireDropzone 재설계: 요소별 리스너 → **document 레벨 dragover/dragleave/drop 가드 + 좌표(getBoundingClientRect) 영역판정 라우팅**. dragover preventDefault(drop 발생 조건)+dropEffect copy, drop preventDefault(새 탭 차단). wireDropzone은 id→onFile 등록만(렌더마다 최신 갱신). `<head>` no-cache meta 3종 추가 | screens/work.html | 원래 요청(실 OS 드롭 무동작) |

- **근본 원인**: 옛 코드는 `<button class="dropzone">`(자식 span 다수) **요소에만** 드롭 리스너 부착. 실제 마우스 드롭은 자식 span/패딩에 떨어져 → button 미처리 → document 버블링 → **document 가드 부재**로 브라우저 기본동작(새 탭/무시)으로 샘. playwright 합성 drop 은 타겟에 직접 쏴서 이 함정을 못 잡음(합성 PASS=실동작 보장 아님). 부차: StaticFiles etag/304 캐시로 옛 버전 가능성.
- **검증(실 OS 드롭 근사·CDP 좌표기반)**: data/jobs/_qa_realdrop/. **자식 span(SPAN.dropzone__title) 좌표에 직접 drop** → 디자인 /api/design/check 호출+filecard, 주문 /api/order/parse 호출+12행. 드롭존 밖(5,5) drop → URL 불변·탭 1개(새 탭 미발생). 클릭 업로드 회귀 0(filechooser /api/design/check+filecard). 01_design_drop·02_order_drop·03_click_regression.png + results.json/results_click.json.
- **불변제약 준수**: engine·api.py·main.py·_handoff 무수정. webapp/static/screens/work.html만 수정. 신규 토큰 없음(.dropzone.is-drag 기존 재사용). 빌드0. 서버 포트8000 그대로(PID만, taskkill //im 미사용).

📝 화면버그 5건 수정 (2026-06-22, webapp/static만 · engine/api.py/_handoff 무수정)

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| screens/work.html | #1 goTo 자동 startGenerate 제거→prepGenerate(형식만 노출·진행바 숨김)+명시 '생성 시작' 버튼(genStarted). renderFmtSeg vector시 서버기본값 활성+'기본'표식. #3 패턴카드 disabled_sizes 취소선'비활성'칩+title. #5 wireDropzone(dragover→is-drag, drop→uploadDesign/uploadOrder) 디자인·주문 드롭존 배선 | 수정 |
| screens/patterns.html | #2 헤더 "4개"하드코딩→#patternCount, renderPatternGrid서 PATTERNS.length 동적 | 수정 |
| screens/settings.html | #4 main.content padding-bottom:80px(저장푸터 겹침 해소) | 수정 |
| screens/app.css | 전역 .seg(형식칩 강조 is-active 검정칩·is-default '기본'표식) 추가. (.dropzone.is-drag 기존 토큰 재사용) | 수정 |

💡 tester 참고:
- **★#1 EPS 실생성 검증(API 직접)**: V넥 both 작업 → output/eps/L_10·M_07.eps **305KB·304KB 실파일 생성**(헤더 %!PS-Adobe-3.0 EPSF-3.0 벡터). pdf도 819·818KB. ZIP both=pdf/2+eps/2. eps만→eps1·pdf0, pdf만→pdf1·eps0 정확.
- **★#1 UI 검증(playwright)**: 생성단계 진입 즉시 자동생성 안함(job_post=None) → '둘 다' 클릭(is-active) → '이 형식으로 생성 시작' 클릭 → **전송 out_format="both" 확인**. vector시 PDF(서버기본)칩 활성표시 스샷 확인.
- **#5 드롭 검증(playwright)**: 디자인/주문서 dragover→is-drag 하이라이트 True. 실파일 drop→ /api/design/check·/api/order/parse 요청 발생 + filecard·dtable 렌더 True. **클릭 업로드 회귀**: filechooser로 .ai 선택→점검완료 OK(드롭·클릭 둘다 동작).
- #2 patterns 헤더 "2개 패턴 프리셋". #3 V넥카드 '3XL·비활성' 취소선칩(스샷). #4 설정 하단 서버카드 안 가림(스샷).
- 회귀: 패턴→디자인→주문→생성(both)→검수 풀플로우 정상. 서버 포트8000 기동·종료(PID) 완료.

⚠️ reviewer 참고:
- #1 버튼 상태머신: step3에서 genStarted=false면 '생성시작'(클릭→startGenerate), true면 '검수로 이동'(canAdvance). 생성취소→goTo(2)→prepGenerate가 genStarted 리셋. 이 흐름 봐주면 좋음.
- .seg 전역 승격: 기존 patterns.html 인라인 .seg와 중복 정의 가능성(인라인이 우선). work/settings엔 인라인 없어 전역만 적용 — 충돌 없음 확인했으나 검토 권장.

## 테스트 결과 (tester · 2026-06-22 화면버그 5건 재검증 · 실브라우저 playwright)
스크린샷: data/jobs/_qa_재검증_화면/ (01~07, results.json·results_drop.json)
서버: 포트8000 기동·헬스ok → 검증 후 **PID 111388 종료 확인(LISTENING 없음)**. taskkill //im 미사용.

| 화면버그 | 결과 | 비고(증거) |
|---------|------|-----------|
| ★#1 출력형식 both/EPS — UI | ✅ PASS | 생성단계 진입 시 자동생성 안함(progress hidden). 형식 세그(PDF/EPS/둘다) 노출+"이 형식으로 생성 시작" 버튼. '둘 다' is-active. 06a·06b.png |
| ★#1 EPS 실생성(전송·디스크) | ✅ PASS | UI 전송 out_format="both". 디스크 output/eps/*.eps **33개·305KB·`%!PS-Adobe-3.0 EPSF-3.0` 벡터**. pdf 33개. job.json outputs[].eps + checks_eps(벡터/CMYK/BBox) 통과 |
| ★#1 ZIP EPS 포함 | ✅ PASS | UI는 ?format=both 호출(zipBtn=downloadZip(apiFmt())). both ZIP=66(pdf/33+eps/33 하위폴더). eps ZIP=eps33/pdf0. pdf ZIP=pdf33/eps0. ※format 파라미터 없이 호출하면 서버 기본 pdf만(정상 동작) |
| #2 패턴관리 헤더 "2개" | ✅ PASS | #patternCount="2개 패턴 프리셋". "4개" 없음. 02.png |
| #3 V넥 "3XL·비활성" 취소선칩+툴팁 | ✅ PASS | line-through "3XL · 비활성" 칩(5XL 뒤). title="원본 암홀X_3XL.ai가 5XL과 동일한 자산 결함..." 03.png |
| #4 설정 하단 '서버' 카드 푸터 안가림 | ✅ PASS | overlap=false(serverCardBottom732<footerTop851), content padding-bottom 80px. 04.png |
| ★#5 드래그 하이라이트 | ✅ PASS | 디자인·주문 드롭존 dragover→is-drag=true. 05a·05c.png |
| ★#5 실제 드롭 첨부 | ✅ PASS | File 담은 drop 디스패치 → 디자인 /api/design/check 1건+결과카드+파일명, 주문 /api/order/parse 1건+38행 테이블. 07a·07b.png |
| #5 클릭 업로드 회귀 | ✅ PASS | filechooser로 디자인·주문 업로드 정상(req fired·테이블 렌더) |

📊 종합: 5건 전부 ✅ PASS (세부 9항목 9/9). 6/22 dev 수정사항 전부 재현 확인.
- pageerror 0건. console error는 CDN 폰트(Pretendard woff2) 404 **1종뿐 → 검증 무관**(명세 예외).
- ⚠️ ZIP은 ?format 미지정 시 서버 기본값 pdf로 응답하나, **웹UI는 항상 apiFmt()(=선택형식 both/eps/pdf)로 호출**하므로 직원 플로우에선 EPS 정상 포함. 결함 아님.

## 테스트 결과 (tester · 2026-06-22 브라우저 시각검증 E2E)
스크린샷: data/jobs/_qa_화면검증/ (01_work_main ~ 14_settings_tall, _downloaded.zip)

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| ①메인 work(사이드바·서버연결초록불·5스테퍼·STIZ) | ✅ 통과 | 01_work_main.png |
| ②패턴카드 실데이터(U넥·V넥) | ✅ 통과 | 02_patterns_cards.png |
| ②V넥 12사이즈·3XL disabled 표기 | ⚠️ 부분 | 칩에 3XL 자체가 없음(목록서 제외). disabled(취소선) 칩 표기는 없음 — 명세기대와 다름 |
| ③디자인 빈템플릿 5케이스 pass | ✅ 통과 | 03_design_empty_pass.png (88,141B·평탄화·흰글리프12<14) |
| ③완성본 "빈 본체 올려주세요" warn | ✅ 통과 | 03b_design_full_warn.png (Tj1·글리프16>14) |
| ④주문서 38행 표 렌더·모두입력됨 | ✅ 통과 | 04_order_table.png |
| ⑤생성 형식선택·진행바·완료 | ✅ 통과 | 05~05c, 11. 완료38/38 |
| ⑥검수 타일·PASS배지·건너뜀5건(3XL) | ✅ 통과 | 12_review_full.png. verdict "33/33 verified" |
| ⑦ZIP 다운로드 동작 | ✅ 통과(동작)/❌(내용) | _downloaded.zip 27MB·33파일 — **pdf/ 33개만, eps/ 0개** |
| ⑧패턴관리·작업기록·설정 렌더 | ✅ 통과 | 08~10,14 |
| **출력형식 "둘 다(both)/EPS" 실효** | ❌ **실패** | 아래 수정요청 #2. EPS 절대 안 만들어짐 |
| 패턴관리 헤더 "4개 패턴 프리셋" | ❌ 실패 | 수정요청 #3. 실제 2개(API/카드)인데 헤더 4 하드코딩/오계산 |
| 설정 하단 카드 vs 저장푸터 겹침 | ⚠️ 경미 | 14_settings_tall.png. 마지막 '서버' 카드 일부를 고정푸터가 가림(하단패딩 부족) |

📊 종합: 11개 중 8개 통과 / 2개 실패 / 1부분·1경미. **E2E 플로우(①~⑧) 자체는 완주 가능**(PDF 기준). 단 EPS 출력은 현재 웹UI로 절대 불가.

### 🔴 핵심버그 근본원인(격리검증 완료) — 출력형식 both/eps 무효
- 엔진 run_job(both): EPS 정상생성 ✅ (CLI 직접호출 output/eps/*.eps 생성 확인)
- 서버 API: payload.out_format 그대로 run_job 전달·응답 echo 정확 ✅ (pdf 보내면 pdf만)
- **UI 버그**: work.html L979 `if(step===3) startGenerate();` — **생성단계 진입 즉시 자동 생성 시작**. 형식버튼(PDF/EPS/둘다)은 그 *뒤*에 노출 → 직원이 "둘 다" 눌러도 이미 시작/종료된 PDF-only 작업엔 미반영. 재생성 트리거 없음. 결과: GS 설치·apiFmt()=both·버튼활성이어도 전송 out_format=pdf → EPS 0개. (job.json out_format='' , output/eps 폴더 없음으로 확인)
- 부가: outFmtKey() 기본 'vector'→serverFmtDefault 'pdf'. 첫 진입 시 형식 미선택이라 무조건 pdf로 시작됨.

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성(disabled_sizes)·재확보 대기 |
| tester | webapp/static/screens/work.html (goTo L979) | 출력형식 both/eps 무효: 생성단계 진입 즉시 자동 startGenerate→형식선택 전에 PDF-only로 시작됨. EPS 절대 생성 안 됨. 형식 선택 후 생성 시작하도록(또는 형식 변경 시 재생성) 수정 필요 | ✅ 완료(자동생성제거+명시버튼, UI out_format=both 확인) |
| tester | webapp/static/screens/patterns.html | 헤더 "4개 패턴 프리셋"인데 실제 패턴 2개(API/카드 일치). 카운트 하드코딩/오계산 → 실제 개수로 | ✅ 완료(PATTERNS.length 동적, "2개" 확인) |
| tester | webapp/static/screens/work.html (V넥 패턴카드) | 3XL "disabled 표기"가 시각적으로 없음(칩 목록서 제외만). 직원이 3XL 비활성을 카드에서 인지 못함 — disabled 칩(취소선) 표기 검토 | ✅ 완료(취소선 '3XL·비활성' 칩+title툴팁) |
| tester | webapp/static/screens/settings.html | 페이지 하단 '서버' 카드 일부를 고정 '저장' 푸터가 가림(하단 패딩 부족). 경미 | ✅ 완료(content padding-bottom:80px) |
| user | webapp/static/screens/work.html (드롭존) | 드래그앤드롭 미구현 — 파일 끌어다놔도 첨부 안 됨(클릭만 동작) | ✅ 완료(wireDropzone: 디자인·주문서 drop→기존 업로드경로) |
| user | webapp/static/screens/work.html (드롭존) | **실제 OS 파일 드롭 무동작**(합성이벤트만 PASS, 실 브라우저 실패). 자식 span/패딩 드롭이 document 가드 부재로 새 탭/무시로 샘 | ✅ 완료(debugger: document 레벨 가드+좌표 영역판정+no-cache meta. CDP 좌표드롭 검증·클릭회귀0) |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-20 | dev/test/rev | 출력형식 PDF/EPS/both | tester13/13·rev통과, EPS305KB벡터 |
| 2026-06-20 | dev | 웹앱1 FastAPI 골격+API3 | curl/브라우저 PASS |
| 2026-06-20 | dev | 웹앱2 order/parse+design 5케이스 | 38행/11명·5케이스 정확 |
| 2026-06-20 | dev | 웹앱3 jobs비동기+progress/preview/zip | E2E①~⑧ PASS |
| 2026-06-20 | dev | 웹앱4 jobs기록+패턴등록+설정 | 글리프셋10자·완성본추출·5사이즈3조각 |
| 2026-06-20 | dev | 웹앱5 run.bat+직원 E2E | 전체플로우 PASS(완료기준 달성) |
| 2026-06-20 | rev | 웹앱 종합 리뷰(1~5) | 통과 치명0(주의3 백로그) |
| 2026-06-20 | pm | 출력형식·웹앱1~5 커밋(8개) | 미푸시8(푸시대기) |
| 2026-06-22 | tester | 브라우저 시각검증 E2E(①~⑧ 스샷) | 8/11통과. 🔴 출력형식both/eps 무효(work.html L979 자동생성), 패턴헤더4개오표기, 설정푸터겹침 — 수정요청4건 |
| 2026-06-22 | dev | 화면버그 5건 수정(work·patterns·settings·app.css) | ✅ 전건완료. #1 EPS 실생성(eps305KB·ZIP both pdf2/eps2)·UI out_format=both(playwright). #5 드롭 디자인·주문 동작+클릭회귀. #2 헤더2개 #3 비활성칩 #4 푸터해소. engine/api.py/_handoff 무수정 |
| 2026-06-22 | debugger | 실제 OS 파일 드롭 버그 수정(work.html) | ✅ 근본원인=요소리스너만+document가드부재→자식span/패딩드롭 새탭으로샘(합성PASS속임). document레벨 가드+좌표 영역판정+no-cache meta로 수정. CDP 좌표드롭 검증(디자인/주문 API호출·밖드롭 새탭0·클릭회귀0). engine/api.py/main.py/_handoff 무수정 |
