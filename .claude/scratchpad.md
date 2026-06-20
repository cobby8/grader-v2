# 작업 스크래치패드

## 현재 작업
- **요청**: cowork 시각검증 4이슈(정합보정·조각복원·재단선·번호글리프셋) — 의뢰서-CLI-정합보정-조각복원.md
- **상태**: ✅ **이슈2·4·3·1 전부 완료·커밋** (미푸시 5개 — 푸시 확인 대기). cowork 최종 오버레이 검증 대기.
- **현재 담당**: pm

## 진행 현황
| 작업 | 내용 | 상태 |
|------|------|------|
| Phase B~E | 완성본주입 통합(text/job/V넥 패턴/주문서) | ✅ 완료·푸시 |
| 이슈2 | place_number/name 잉크 bbox 중앙정렬 | ✅ ("1" 27pt치우침 교정, 오차 0pt, tester 6/6) |
| 이슈4 | 빨간 재단선·너치 보존 인프라 | ✅ (tester 7/7, 단 실파일에 재단선 PDF 부재→디자이너 재출력 대기) |
| 이슈3 | 암홀X 3조각(앞/뒤/밴드) 복원 + 단조성가드 + 3XL 안전차단 | ✅ (tester 다회+reviewer, 3XL.ai 결함→비활성) |
| 이슈1 | 디자이너 outline 0~9 번호 글리프셋 | ✅ (tester 8/8, reviewer 통과, 잉크중심 0pt) |

## 백로그 (차단 아님, 후속 — 대부분 사용자/디자이너 입력 대기)
- **[이슈4] 재단선 디자이너 재출력**: 실 .ai에 재단선이 PDF 벡터로 없음(일러스트 전용 데이터). 재단선 레이어를 PDF 포함되게 재출력한 .ai 주면 코드가 자동 보존(인프라 완비, 합성검증 완료).
- **[이슈3] 3XL.ai 재확보**: 원본 암홀X_3XL.ai가 5XL과 동일한 자산 결함 → 현재 비활성(disabled_sizes). 올바른 3XL.ai 받으면: ai_to_path_svg→normalize-svg로 3XL.svg 생성 + preset sizes에 3XL 추가 + disabled_sizes에서 제거 → 12→13개 복원.
- **[이슈1/3] cowork 최종 오버레이 검증**: 번호 글리프셋·밴드·재단선을 완성본과 오버레이 확인.
- **band design_region**: 빈템플릿 기준 산출 → cowork 정합 후 완성본으로 정밀 재추출 여지.
- 하의 사이즈 분리 / shrink 등방한계 / preset sizes.scale 미사용 / 이름 세로 descent 받침~3.6pt / 주문서 자동판별 ③ 우선 가드.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) + build_layouts/grade **시그니처·동작 무수정**(신규 인자 기본값 확장만). device CMYK 무손실. 글자 `k` fill만. 빌드0·순수Python. 폴더+JSON. CLI 단독 검증. 하드코딩 금지(좌표·크기·색 preset/소스).

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left·등방 contain). grade.py `_piece_transform` 정답(job.py `_job_piece_transform` 복제).
- **글자 주입**: text.py place_number/place_name(디자인좌표 ops, **잉크 bbox 중앙정렬**) → job이 조각 transform 감싸 시트좌표 주입(extra_ops, 클립 밖). 재단선도 동일 경로(클립 밖이라 너치 보존).
- **번호 렌더**: preset number_area에 glyph_source 있으면 디자이너 글리프셋(number_glyphs.py, number_glyphs.json), 없으면 HY헤드라인 폰트 폴백.
- **V넥 §4 수치**(페이지 4478.74×5669.29): 앞번호 center[1389,4184] cap310 / 뒤번호 [3217,4342] cap539 / 이름 cx3219.8 baseline4765.7 em136.40 pitch195.4. 0~9 글리프 ArtBox=[585,4673,3923,5211](흰색 outline, 순서 1234567890).
- **V넥 패턴**: 암홀X 3조각 front=idx0/back=idx1/band=idx2. viewBox 4337.01×3401.57. **12사이즈(3XL 비활성=disabled_sizes, 원본 결함)**.
- ⚠️ **변환 함정(errors.md)**: 조각수+verify만으론 부족 → viewBox 통일·양수좌표·**비-XL 미리보기 육안** 필수. 인접 사이즈 좌표 동일=자산결함(단조성 가드 check_size_monotonicity가 탐지).
- ⚠️ disabled_sizes는 sizes 밖 별도 섹션(build_layouts가 sizes만 순회 → grade/job 둘 다 안전).
- ⚠️ 재단선=디자인 빨강 stroke(CMYK 0,0.96,0.95,0). pikepdf 출력 비결정적. STIZ 주문서 헤더 nbsp.

## 핵심 모듈
- engine: text.py(place_*+글리프셋분기), number_glyphs.py(0~9 추출/렌더), reference.py, job.py(정밀배치+재단선+disabled_sizes), svg_normalize.py(path→polyline+보조선필터+단조성가드), order.py(양식①②③), flatten.py.
- CLI: grade/job/reference/normalize-svg/number-glyphs/flatten/order/selftest.
- 보조: scripts/ai_to_path_svg.py, illustrator-scripts/ai_to_svg.jsx.
- 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면(SVG12+preset+number_glyphs.json)}. data/jobs/(.gitignore).

## 실데이터 / git
- 빈템플릿/완성본/주문서/글리프셋소스: `C:/Users/user/Desktop/새 폴더/` (V넥 템플릿.ai=글리프셋·빈템플릿 / XL.ai=완성본 / 260213_추가주문서.xlsx)
- 암홀X 패턴 원본 .ai: 데스크톱 V넥 스탠다드-A(암홀X) / G드라이브 단면
- 폰트: data/fonts/HY헤드라인M.ttf(이름. 번호는 글리프셋)
- cowork 검증용: data/jobs/_qa_*/ (글리프셋 번호 PDF/PNG — 절대경로는 각 이슈 작업폴더)
- git: origin=cobby8/grader-v2, main. **미푸시 5개**(의뢰서 docs + 이슈2/4/3/1).

## 기획설계/구현/테스트/리뷰
(완료 — 상세 git 히스토리 + knowledge. 이슈2~1 전부 tester+reviewer 통과)

## 테스트 결과 (tester) — 본체92K 풀합성 검증 (2026-06-20)
**대상**: 라인작업 92KB 본체(`data/jobs/_base92k/base_XL.ai`, page0 콘텐츠 91,917 bytes) × preset(농구_V넥_양면, design_file을 본체로 변경) × 선수1명(장혁준/11/XL). engine 코드 무수정, preset design_file 데이터만 변경+실행.
- **design Form 바이트수**: ✅ **이전 3.4KB(3419) → 이번 91,917 bytes**. 평탄화본 page0 콘텐츠 91,917 == 출력 Form 콘텐츠 91,917 (**byte-identical 무손실**). 하위 Image 0개(래스터 미추가).
- **임베드·렌더**: verify_output 9개 전부 PASS — 디자인 단일임베드 Form 1개(배치3·임베드1), CMYK 무손실, 투명도없음, 클립(W n)·변환(cm) 보존, Do 3회=조각3, 래스터미추가, 재단선 빨강 stroke 3개. **Do 3회·k(CMYK fill) 3회·금지연산자 BI 0개·gs 0개**.
- **PNG 렌더(정상)**: 6787×4735, **비흰픽셀 51.19%(흰화면 아님)** — 파란계열 50.57%(본체), 빨강 0.36%(재단선/밴드), 어두운 0.04%(번호 글자). 육안: **파란 본체+밴드+재단선+athletic 번호+YONSEI 로고+이름"장 혁 준" 한 장에 정상 렌더**. 번호 "11"이 본체 기존 번호 "30"과 겹침=예상(보고용). 이전 자산(3.4KB·흰화면) 문제 완전 해소.
- **PNG 절대경로**: `C:\0. Programing\grader-v2\data\jobs\_qa_본체92K_XL11\preview\XL_11_장혁준.png` / 출력PDF: `C:\0. Programing\grader-v2\data\jobs\_qa_본체92K_XL11\output\XL_11_장혁준.pdf`
- **preset design_file 변경**: `"연세대 레플리카 블루림 V넥 스탠다드 베이직 XL - 템플릿.ai"` → `"../../jobs/_base92k/base_XL.ai"` (glyph_source=number_glyphs.json 유지). 크래시 없음.

## 테스트 결과 (tester) — 실템플릿 풀합성 검증 (2026-06-20)
**대상**: 실제 빈템플릿(1.73MB, 요소제거) × preset(농구_V넥_양면) × 선수1명(XL/11/장혁준). 코드·preset 무수정 순수 실행.
- **design Form 바이트수**: ⚠️ **3.4KB (decoded 3419 / 압축 raw 1109 bytes)** — 90KB급 아님.
  - 평탄화본(_flattened_design.pdf) 1.51MB, 출력PDF 1.17MB이나 **as_form_xobject 콘텐츠 스트림 자체가 3.4KB**.
  - Form Resources에 하위 XObject·Image 참조 0개(래스터 미추가). 콘텐츠는 `/MC0` 안 흰색(CS0=ICCBased CMYK, `0 0 0 0 scn`) 글자 outline 몇 개 + **MC1/2/3 레이어 빈 채(BDC/EMC만)**.
  - **빈템플릿·완성본 XL.ai 둘 다 Form 콘텐츠 ≈3.4KB**(3419 vs 3413). 즉 이 .ai들의 PDF 표시 콘텐츠가 원래 작음 — "90KB급 디자인 Form" 가정은 이 자산에 해당 안 됨.
- **임베드·렌더**: verify_output 9개 전부 PASS(디자인 단일임베드 Form 1개, Do 3회=앞/뒤/밴드 3조각, 무손실 바이트동일, CMYK유지, 투명도없음, 래스터미추가, 재단선보존). 글자 k fill, 금지연산자 0.
- **PNG 렌더**: preset 기본(흰색 번호) PNG는 **완전 흰화면(비흰픽셀 0)** — but 합성버그 아님. **원본 .ai 자체가 fitz 렌더 시 흰화면**(빈템플릿·완성본 모두 비흰0). 파란 본체가 .ai PDF 표시스트림에 없음 + 글자색 흰색(CMYK0000)이 원인.
- **합성 정상 증명**: 글자색만 검정으로 바꾼 임시preset(원본 무수정·임시폴더, 검증후 삭제)로 재합성 → **번호11(앞·뒤)+이름"장 혁 준" 정상 렌더**(검정픽셀1.53%, 앞/뒤 위치분리, athletic 글리프셋). 파이프라인(글자주입·배치·글리프셋·합성)은 완전 정상.
- **결론**: 합성·임베드·검증 파이프라인은 정상이나, 이 빈템플릿/완성본 .ai는 **파란 본체가 PDF 벡터 표시콘텐츠로 없음**(Illustrator 전용데이터 추정, 재단선 부재와 동일 양상) → design Form 3.4KB·미리보기 본체 미표시는 **자산 문제**. 90KB급 본체 검증하려면 본체가 PDF 표시콘텐츠로 살아있는 .ai 재출력 필요.
- **PNG 절대경로**(cowork 전달용):
  - 기본(흰번호, 흰화면): `C:\0. Programing\grader-v2\data\jobs\_qa_실템플릿_XL11\preview\XL_11_장혁준.png`
  - 검정번호(육안확인용, 번호11+이름 보임): `C:\0. Programing\grader-v2\data\jobs\_qa_실템플릿_XL11_검정\preview\XL_11_장혁준.png`
  - 출력PDF: `C:\0. Programing\grader-v2\data\jobs\_qa_실템플릿_XL11\output\XL_11_장혁준.pdf`

## 테스트 결과 (tester) — 빈본체 XL11 검증 (2026-06-20)
**대상**: 깨끗한 빈 본체(`design_source/연세대_V넥_빈템플릿_본체포함_XL.ai`, page0 콘텐츠 88,141 bytes·텍스트0=번호·이름 없음·페이지4478.74×5669.29) × preset(농구_V넥_양면) × 장혁준/11/XL 1명. engine 코드 무수정.
- **preset design_file 변경**: `../../jobs/_base92k/base_XL.ai`(김경원 완성본) → `../../../design_source/연세대_V넥_빈템플릿_본체포함_XL.ai`(빈 본체, 프로젝트루트 design_source 기준 상대경로). glyph_source=number_glyphs.json 유지.
- **글리프셋 일치 확인**: 아트보드2.ai에서 재추출 → 기존 number_glyphs.json과 비교 시 subpath 구조(개수·점수·op) 완전 동일, 좌표 최대편차 0.001pt(부동소수 반올림 수준). **실질 일치 → 기존 JSON 유지(재추출 불필요)**.
- **design Form 바이트수**: ✅ **88,141 bytes** — 빈본체 page0 콘텐츠 88,141 == 출력 Form 콘텐츠 88,141 (**byte-identical 무손실**). 하위 Image 0개, Form 1개(단일임베드).
- **★겹침 없음★**: ✅ 빈템플릿이라 기존 번호·이름 없음 → 번호11(앞·뒤)+이름"장 혁 준" **깨끗하게 단독 렌더**. **이전 김경원 완성본의 "30번 겹침 완전 소멸**(육안 확인).
- **verify**: 9개 전부 PASS — 무손실임베드·단일임베드·CMYK유지·투명도없음·클립(Wn)·변환(cm)·Do3회(조각3)·래스터미추가·재단선빨강stroke3. **Do 3회·k(CMYK fill)3회·K(stroke)3회·금지연산자 BI 0·gs 0**.
- **PNG 렌더(정상)**: 6787×4735, **비흰픽셀 52.64%**(흰화면 아님) — 파란계열52.06%(본체+밴드), 빨강0.34%(재단선), 어두운0.04%(글자). 육안: 파란본체+밴드+흰사이드라인+방패로고(앞)+YONSEI(뒤)+번호11(앞·뒤)+이름"장혁준"+빨강재단선 **한 장 정상 렌더**.
- **PNG 절대경로**: `C:\0. Programing\grader-v2\data\jobs\_qa_빈본체_XL11\preview\XL_11_장혁준.png` / 출력PDF: `C:\0. Programing\grader-v2\data\jobs\_qa_빈본체_XL11\output\XL_11_장혁준.pdf`
- **결론**: ✅ 빈 본체 정식 설정 완료 + XL11 검증 PASS. 정상이면 11명 전체 진행 가능.

## 구현 기록 (developer) — 실주문 빈본체 전체 재출력 (2026-06-20)
📝 구현한 기능: **실주문 11명(선수×사이즈 38행) 빈본체 전체 재출력 + 전수검증**. engine 코드·preset 무수정, job CLI per_player 실행만.
- **명령**: `python -m engine.cli job --preset data/patterns/농구_V넥_양면/preset.json --design design_source/연세대_V넥_빈템플릿_본체포함_XL.ai --order "C:/Users/user/Desktop/새 폴더/260213_연세대학교 레플리카_농구유니폼_추가주문서.xlsx" --out data/jobs/260620_연세대V넥_빈본체 --split per_player`
- **produced/verify/skip**: 주문 38행 → **생성 33개 / verify PASS 33 / FAIL 0 / 건너뜀 5(3XL)**. 사이즈분포 XS4·S2·M7·L9·XL9·2XL2. 3XL 5명(이해솔·이주영·이채형·홍상민·김윤서) disabled_sizes로 skip+사유기록(5XL 등 대체출고 0). missing_sizes 없음.
- **design Form 88KB 무손실**: ✅ 빈본체 평탄화 page0 콘텐츠 **88,141 bytes** == 33개 출력 design Form 콘텐츠 **전부 byte-identical(분포 {88141:33})**. 불일치 0건. Form 1개(단일임베드)·Image 0개(래스터미추가) 전수.
- **★겹침 없음★**: ✅ 빈본체라 기존 번호 없음 → 선수별 번호·이름 깨끗 단독렌더. 전 미리보기33 비흰픽셀<30% **0건**(흰화면 없음, 전부 본체 정상렌더, XS47.9%~2XL56.3%).
- **연산자 전수**: Do 3회(앞/뒤/밴드){3:33}, k(CMYK fill){3:33}, K(재단선 stroke){3:33}, 금지연산자(BI/인라인이미지) **0건**, 래스터 0. cutline found3/expected3/mapped3.
- **대표 육안 6건 PASS**: XS_06김승우·S_05이주영·M_02최영상·L_09이병엽·XL_11장혁준·2XL_13박준성 — 전부 파란본체+밴드+흰사이드라인+방패로고(앞)+YONSEI(뒤)+번호(앞·뒤)+이름+빨강재단선 한장 정상, 앞판소실 없음, 두자리번호(11/13) 깨끗.
- **공식 verify_output**: XL11 표준리포트 종합 PASS(무손실·단일임베드·CMYK·투명도없음·Wn클립·cm·Do3·래스터미추가).

💡 cowork 전달용 대표 경로:
- PNG(앞뒤 미리보기): `C:\0. Programing\grader-v2\data\jobs\260620_연세대V넥_빈본체\preview\XL_11_장혁준.png` / `...\preview\M_02_최영상.png` / `...\preview\2XL_13_박준성.png`
- PDF(출고용): `C:\0. Programing\grader-v2\data\jobs\260620_연세대V넥_빈본체\output\XL_11_장혁준.pdf` / `...\output\L_09_이병엽.pdf`
- 작업폴더 루트: `C:\0. Programing\grader-v2\data\jobs\260620_연세대V넥_빈본체\` (output/ PDF33, preview/ PNG33, job.json)

## 구현 기록 (developer) — 웹앱1 (FastAPI 뼈대 + 정적서빙 + health/patterns/settings) (2026-06-20)
📝 구현한 기능: **웹앱 1단계** — FastAPI 백엔드 뼈대로 디자인 핸드오프 정적화면을 서빙하고, 화면 패턴목록·server-pill을 실 API에 연결. 엔진은 `load_preset` 호출만(무수정). 빌드0·폴더+JSON.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| webapp/__init__.py | 패키지 설명(설계원칙) | 신규 |
| webapp/state.py | 경로헬퍼(PROJECT_ROOT/STATIC/PATTERNS/JOBS) + read_settings(설정JSON 없으면 DEFAULT_SETTINGS 머지) + DEFAULT_PORT | 신규 |
| webapp/api.py | APIRouter(/api): GET /health{status,port} · /patterns(data/patterns/*/preset.json 스캔→[{id,name,sizes[],pieces,icon,glyph_source(bool),disabled_sizes[]}]) · /settings | 신규 |
| webapp/main.py | FastAPI: /api 라우터 + /static 마운트(StaticFiles html=True) + GET / → **RedirectResponse(/static/screens/work.html)** | 신규 |
| webapp/run.py | uvicorn 기동(127.0.0.1:8000) + 1.2s 뒤 브라우저 자동오픈 | 신규 |
| webapp/static/ | _handoff/grader-v2-static/ **복사본**(22파일). README에 "복사본·재복사" note 1줄 | 신규(복사) |
| webapp/static/screens/work.html | PATTERNS 목배열→`let PATTERNS=[]` + loadPatterns()/refreshServerPill() fetch 추가, patternId=null→첫패턴. 마크업·토큰·mock 나머지 유지 | 수정(복사본만) |
| webapp/static/screens/patterns.html | PATTERNS→[] + renderPatternGrid()/fetch(/api/patterns) + server-pill fetch(/api/health). 나머지 유지 | 수정(복사본만) |
| requirements.txt | fastapi==0.138.0 · uvicorn==0.49.0 · python-multipart==0.0.32 추가 | 수정 |

**핵심 판단(★)**: GET / 를 work.html 직접반환 대신 **/static/screens/work.html 로 307 리다이렉트**. 이유 = work.html 자산이 `../styles.css` 등 screens/ 기준 상대경로라 루트반환 시 `/styles.css` 404로 스타일 깨짐. 리다이렉트하면 브라우저 base가 /static/screens/ 가 되어 자산이 /static/styles.css 로 정확히 풀림(원본 마크업 무수정).

✅ 검증(완료기준 ①~⑤ 전부 PASS):
- **①기동**: `uvicorn webapp.main:app --port 8000` 크래시0, /api/health 200 UP.
- **②curl**: health=`{"status":"ok","port":8000}` / patterns=실목록(농구_U넥_양면 sizes1·pieces3 / **농구_V넥_양면 sizes12·pieces3·glyph_source true·disabled[3XL]**) / settings=`{output_format:pdf, ghostscript_path, preview_enabled:true, color_note}`. (콘솔 surrogate표시뿐, UTF-8 파일덤프로 한글 정상 확인)
- **③브라우저**(playwright chromium headless): 루트→work.html 리다이렉트, **패턴카드 2개 실데이터**(V넥 12사이즈 칩 전부 렌더), server-pill="서버 연결됨 · :8000"(실 health), patterns.html 그리드도 실데이터·pill 연결. 스크린샷 정상(STIZ 브랜딩·스테퍼·사이드바). 콘솔에러는 외부 CDN Pretendard 404뿐(오프라인 환경, 코드무관·시스템폰트 폴백).
- **④git diff**: **engine/ 0변경**(diff 없음) + _handoff/grader-v2-static **원본 무수정**(diff -rq: webapp/static 복사본의 work/patterns/README 3개만 다름, 나머지19 byte-identical / _handoff README는 note없는 원본).
- **⑤종료**: 포트8000 PID로만 taskkill(전역 node/python kill 안 함).

💡 tester 참고:
- 기동: `python -m uvicorn webapp.main:app --port 8000` (또는 직원용 `python -m webapp.run` = 브라우저 자동오픈).
- curl 단독검증: `curl localhost:8000/api/health` · `/api/patterns` · `/api/settings`.
- 정상: health ok·port8000 / patterns에 V넥 sizes12·glyph_source true·disabled[3XL] / 브라우저 localhost:8000 작업화면 뜨고 패턴 실데이터·server-pill 초록.
- 주의입력: 한글 폴더명 → 콘솔 stdout이 cp949면 깨져 보임(데이터는 정상, UTF-8로 확인). 외부CDN 폰트404는 정상(오프라인). 설정JSON 없으면 기본값 응답.
- 종료: 포트8000 PID로만(`netstat -ano|findstr :8000`→`taskkill /f /pid`).

⚠️ reviewer 참고:
- GET / 리다이렉트 결정(자산 상대경로 보존 위함) 타당성.
- api._scan_one_pattern: 패턴1개 깨져도 try/except로 그것만 skip(목록 안 죽음). glyph_source=앞/뒤 number_area 중 하나라도 glyph_source 키 있으면 true.
- state.read_settings: 설정파일 없음=정상(에러아님), 깨짐도 기본값 폴백.

## 구현 기록 (developer) — 출력형식 PDF/EPS/both (2026-06-20)
📝 구현한 기능: **출력형식 선택(PDF/EPS/둘다)** — flatten Group제거 + engine/eps.py 신설 + run_job 형식분기 + preset settings + CLI --format. 의뢰서 §1~5 전부 구현·검증 완료.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| engine/flatten.py | flatten_transparency 끝(save직전) Form투명도그룹 제거 + 잔여알파/SMask 재스캔 안전가드 + groups_removed 카운트. `_scan_residual_transparency`/`_strip_transparency_groups` 추가 | 수정 |
| engine/eps.py | **신설**: pdf_to_eps(eps2write+EPSCrop, GS탐색 settings→절대→PATH, graceful fallback, 변환직전 Form그룹 strip) + verify_eps(벡터/CMYK/BBox) + find_ghostscript | 신규 |
| engine/job.py | run_job out_format(pdf\|eps\|both) 인자 + output/pdf·output/eps 분리 + EPS변환·verify_eps + summary format/ghostscript/format_summary + outputs[].eps·checks_eps + flatten groups_removed | 수정 |
| engine/cli.py | cmd_job --format 추가 + run_job 전달 + 형식별 요약 출력 | 수정 |
| data/patterns/농구_V넥_양면/preset.json | output{format:"pdf", ghostscript_path} 추가 | 수정 |

**핵심 발견(★)**: EPS 래스터화 트리거는 **Form XObject의 /Group(/Transparency)** 뿐. 페이지 /Group은 /CS(ICC CMYK 블렌딩색공간) 보유→통째 제거 시 본판색 미세시프트(렌더 27%변화)+벡터화 기여0 → **Form그룹만 제거, 페이지그룹(/CS有) 보존**. compose의 as_form_xobject가 디자인 재임베드 시 페이지 /Group을 새 Form으로 옮겨 합성PDF에 투명그룹 부활 → pdf_to_eps가 변환직전 임시사본에서 Form그룹 재제거(compose 무수정).

✅ 검증 결과(완료기준 ①~⑤ 전부 PASS):
- **①회귀0**: selftest PASS(inkcov편차0) / flatten후 PDF렌더 **delta>10 픽셀 0개**(변화0.006%=AA노이즈, 시각·색변화0) / 기존V넥 job verify PASS(9/9). flatten groups_removed=1(Form그룹, 페이지그룹 보존).
- **②EPS벡터(XL_11)**: 305,898B(~300KB대) · 실이미지페인트 Id **0개**(래스터 아님, 대조군 래스터EPS=20MB·Id546개) · CMYK유지 · verify_eps 3/3 PASS. EPSCrop 렌더 비흰54.9%(파랑54.2%본판+빨강0.5%재단선+번호) = 시각 정상.
- **③both(선수2명)**: output/pdf+output/eps 양쪽 생성 / PDF verify 2/2 PASS · EPS verify 6/6 PASS(벡터·CMYK·BBox) / format_summary{pdf:2/2, eps:2/2/0}. 38행 전체도 생성33/verifyPASS33/skip5(3XL).
- **④GS fallback**: (a)잘못된 ghostscript_path→PATH폴백 경고+EPS생성 (b)GS완전부재→EPS skip2·**PDF만 산출**·경고1회·**크래시0**.
- **⑤summary집계**: format/ghostscript/format_summary(pdf·eps produced·verify_pass·skipped) + outputs[].checks_eps 정상 기록. eps단독모드=EPS만 남기고 중간PDF(_epstmp) 정리.

✅ 불변제약 준수: compose.py/verify.py/pattern.py/grade.py **git diff 무수정 확정**. verify_output/Piece/parse_svg/build_layouts/grade 시그니처 그대로. device CMYK 무손실. 빌드0(py_compile OK).

💡 tester 참고:
- 테스트: `python -m engine.cli job --preset data/patterns/농구_V넥_양면/preset.json --design design_source/연세대_V넥_빈템플릿_본체포함_XL.ai --order <xlsx> --out <dir> --split per_player --format both --no-preview`
- 정상: output/pdf·output/eps 양쪽 생성, EPS ~300KB, "EPS: 생성N·verify PASS N" 출력, job.json에 checks_eps.
- 주의입력: --format eps(중간PDF 정리되어 EPS만), GS없는 환경(EPS skip+PDF산출), single split(페이지별 EPS).
- GS: C:/Program Files/gs/gs10.04.0 설치됨 + PATH에 gswin64c.

⚠️ reviewer 참고:
- flatten 페이지그룹 보존(/CS 有) 판단 로직 — 색보존 핵심. Form그룹은 항상제거.
- pdf_to_eps의 strip_groups 임시사본 처리(tempfile→변환→cleanup, 원본 무수정).
- verify_eps BBox 완화판정(EPSCrop=콘텐츠로 자름 → MediaBox 정확일치 불가).

## 테스트 결과 (tester) — 출력형식 PDF/EPS/both 독립검증 (2026-06-20)
**대상**: 출력형식 구현(eps.py 신설·flatten Group제거·job out_format·cli --format·preset output) 독립 재검증. 코드 무수정, 검증만. 환경: Python 3.11.9, pikepdf 10.8.0, PyMuPDF 1.27.2, GS 10.04.0(절대경로+PATH 둘 다). 빈본체 preset(design_file=빈본체) × 실주문서 38행.

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ 통과 | 종합 PASS, inkcov 최대편차 **0.000000** |
| 2-a) Form그룹 제거 회귀(색·시각 변화) | ✅ 통과 | 제거본 vs 살림본 렌더 **delta>10 픽셀 0/6,350,400 (0.0000%)**, 최대delta=2(AA). 시각·색 변화 0 |
| 2-b) 페이지그룹 /CS 보존 입증 | ✅ 통과 | flatten후 페이지 /Group·/CS **둘 다 보존(True)**, 잔존 Form투명도그룹 0, groups_removed=1. /CS 통째제거 대조군은 색시프트 0.233%(maxΔ37) → 보존이 색보존 핵심임 입증 |
| 2-c) 기존 V넥 job verify | ✅ 통과 | CLI 38행 both → 생성33/verify PASS33/FAIL0/skip5(3XL) |
| 3) EPS 벡터화(XL_11) | ✅ 통과 | 305,898B(~300KB대) · **이미지페인트 Id 0개** · CMYK유지 · 벡터연산자21 · BBox 시트이내. verify_eps 3/3 PASS |
| 3-대조) Form그룹 잔존 래스터 | ✅ 통과 | strip=False → **14.98MB·Id 443개**(의뢰서 §0 14.98MB와 일치), 정식대비 **49배**. 합성PDF에 compose 부활 Form그룹 1개 실재 확인 |
| 4) --format both | ✅ 통과 | output/pdf+output/eps 양쪽 생성. PDF verify·EPS verify 양쪽 PASS. format_summary 형식별 집계·outputs[].checks_eps 기록. 38행 전체 checks_eps 33/33 보유·전부 PASS |
| 5) --format eps | ✅ 통과 | EPS만 남음(output/eps), output/pdf·_epstmp 정리됨(존재안함), outputs[].pdf=None |
| 5) --format pdf | ✅ 통과 | PDF만 남음(output/pdf), output/eps 없음, eps produced=0, outputs[].eps=None |
| 6-a) 잘못된 ghostscript_path 폴백 | ✅ 통과 | PATH GS로 폴백 경고+EPS 정상생성, 크래시 0 |
| 6-b) GS 완전부재 시뮬 | ✅ 통과 | EPS skip(skipped:1)·**PDF만 산출(파일 실존)**·GS미설치 경고1회·**크래시 0**, ghostscript=None |
| 7) 불변제약 git diff | ✅ 통과 | compose/verify/pattern/grade/pdfutil/text/order **diff 0건**(무수정 확정) |
| 8) PDF 경로 변경 영향 | ✅ 통과 | job.json outputs[].pdf=output/pdf/…, eps=output/eps/… **실제 파일과 전부 일치**. preview는 별도 preview/ 폴더라 무영향. 깨지는 곳 0 |

📊 종합: **13개 항목 전부 통과 / 0개 실패** — 출력형식 PDF/EPS/both 구현 독립검증 **PASS**.
- EPS 33개 크기 분포: 최소304,401B·최대306,182B·평균305,468B·**2MB초과(래스터의심) 0개**(전부 벡터).
- 핵심 3대 확정: ②색시프트 0(Form그룹 제거 무영향+페이지그룹/CS 보존) · ③EPS 이미지0(벡터, 대조군 래스터 49배) · ⑥fallback 크래시0(폴백·부재 양쪽).
- 검증 산출물 경로(참고): `C:\0. Programing\grader-v2\_qa_eps\job_cli_both\` (PDF33·EPS33·job.json), `_qa_eps\job_both\`(both 2명), `_qa_eps\contrast_raster.eps`(래스터 대조군 14.98MB).

## 리뷰 결과 (reviewer) — 출력형식 PDF/EPS/both (2026-06-20)

📊 종합 판정: **통과** (치명 0건). 후속 1건은 의뢰서 설계에 이미 반영됨.

✅ 잘된 점:
- **불변제약 완벽 준수**: git diff 확인 — compose.py/verify.py/pattern.py/grade.py **무수정 확정**. eps.py 신규, flatten/job/cli + preset만 변경. verify_output/Piece/parse_svg/build_layouts/grade 시그니처 그대로. run_job은 out_format 인자를 **기본값 None**으로 추가(기존 호출부 무영향).
- **flatten Group제거 안전가드 우수(핵심)**: `_strip_transparency_groups` 호출 직전 `_scan_residual_transparency`로 알파(ca/CA<1)·SMask 재스캔 → 잔여 있으면 제거 건너뛰고 경고만(flatten.py 256~263, eps.py 113~119 이중 적용). Form그룹은 항상 제거(벡터화 트리거), 페이지그룹은 /CS(블렌딩 색공간) 있으면 보존(색시프트 방지) — 의뢰서 §1·§6 device CMYK 무손실 요구에 정확히 부합. "표지판만 떼되 색 효과 남았으면 보존" 판단 타당.
- **graceful fallback 견고**: GS 탐색 settings→절대경로→PATH 순서 정확(eps.py 59~85). subprocess timeout=300·capture_output·try/except, GS 미설치/실행실패/rc≠0/파일미생성 전부 produced=False+경고로 흘림(크래시0). 임시 strip 사본은 finally + _cleanup_tmp로 원본 무손상 정리. GS미설치 경고는 작업당 1회(eps_gs_warned 플래그).
- **EPS 단독 모드 순서 안전**: verify→preview→EPS변환→PDF삭제 순. 미리보기가 PDF 삭제 전 생성되어 eps 단독에서도 preview 정상(job.py 912~934).
- **verify_eps 벡터판정 정교**: image토큰(eps2write 정의 2개 상존)을 단독기준에서 배제하고 실제 페인트호출 `Id`로 래스터/벡터 판별 + 크기임계 + 벡터연산자 3중 AND. 오탐 방지 설계 우수.
- **에러 한국어·네이밍 양호**, 주석으로 "왜"를 충실히 설명.

🟡 권장 수정(후순위, 차단 아님):
- [eps.py:316 verify_eps origin_ok] `abs(x0) <= bbox_tol + sw` 는 x0가 시트폭(sw)만큼 떨어져도 통과 → 사실상 항상 참인 무의미 가드. EPSCrop BBox 원점은 0 근처여야 정상이므로 `abs(x0) <= bbox_tol`(또는 작은 여백)이 의도에 맞음. **단 과대허용=거짓양성 아님(검증 느슨해질 뿐)**이라 치명 아님. 현 동작(within·has_content가 실질 판정)으로 EPS 품질검증은 유효.
- [eps.py:42 _GS_ABS_CANDIDATES / verify_eps 임계값들] GS 절대경로 후보·raster_size_limit(2MB)·max_image_ops(4)가 소스 하드코딩. preset.output.ghostscript_path로 1순위 오버라이드는 되므로 실사용 무지장이나, GS 버전 올라가면 후보 목록 갱신 필요. 임계값도 향후 preset화 여지(현재는 합리적 기본값).
- [flatten.py:117 _alpha_gstates] 빈 dict 반환 자리표시 함수 — 미사용이면 후속 정리 시 제거 검토(현재 무해).

🔶 후속 리스크(치명 아님 — 의뢰서에 이미 반영 확인):
- **PDF 경로 변경(output/ → output/pdf/)**: 기존 job.json을 읽는 코드는 engine 내 없음(grep 확인). outputs[].pdf는 out_dir 기준 상대경로로 기록되어 경로 변경이 JSON에 자동 반영됨. **후속 FastAPI 웹앱**(의뢰서-CLI-FastAPI §2 `/zip?format=` "둘 다면 pdf/·eps/ 하위폴더")이 신 구조를 전제로 설계되어 있어 **정합**. 단, 260620_연세대V넥_빈본체 등 **이미 생성된 기존 job 폴더는 output/ 직하에 PDF**가 있으므로, 웹앱 기록조회(`GET /api/jobs`)가 구·신 두 구조를 모두 읽도록 해야 함(웹앱 구현 시 처리 권장).
- eps 단독 모드: outputs[].pdf=null로 기록 → 웹앱/소비자가 null 처리 가정 필요(의뢰서에 형식분기 명시되어 정상).

(이전 검증 기록은 위 "구현 기록 (developer) — 출력형식" 및 "테스트 결과" 섹션 보존)

## 구현 기록 (developer) — 웹앱2 (주문서 파싱 API + 디자인 점검 5케이스 + 화면 fetch 연결) (2026-06-20)
📝 구현한 기능: **웹앱 2단계** — ① 주문서 xlsx 파싱 API, ② 디자인 점검 5케이스 API(우선순위 판정), ③ work.html 드롭존을 실 파일 업로드+fetch로 연결. 엔진 공개 API는 호출만(무수정), _handoff 원본 무수정(webapp/static 복사본만).

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| webapp/state.py | save_upload(upload): data/uploads/ 에 '시각_랜덤8__원본명' 으로 저장→절대경로 반환. UPLOADS_DIR 상수 추가. | 수정 |
| webapp/api.py | POST /api/order/parse(xlsx→parse_order→{rows,warnings,total,empty_size}) + POST /api/design/check(5케이스 우선순위) + 베이크 헬퍼(_number_areas preset에서 좌표읽기·_count_white_glyphs_in_number_area) + 임계상수 | 수정 |
| webapp/static/screens/work.html | pickFile/uploadDesign/uploadOrder fetch 헬퍼 + renderDesign(서버 status→톤/체크리스트)·renderOrder(서버 rows→ORDER) JS만 교체. 마크업·토큰·DESIGN_CASES 무수정 | 수정(복사본만) |
| .gitignore | data/uploads/ 추가(업로드 임시저장소) | 수정 |

**5케이스 우선순위 판정 로직(★)**: ① 첫바이트 %!PS-Adobe → fail(PDF호환 아님) → ② %PDF인데 page0 콘텐츠<10KB → fail(본체누락) → ④ 베이크(Tj 라이브텍스트>0 OR 번호area 흰글리프>임계14) → warn(빈본체 권장, 진행허용) → ③ 투명도(scan_transparency) → flatten_transparency 성공·잔여0 pass(+flattened)/SMask등 잔여 fail(원본평탄화) → ⑤ 정상 pass.

**베이크 area 판정(★ 오판 방지)**: preset front/back_number_area의 center/cap_height를 단일출처로 읽어 번호중심±(cap*2.0가로,1.2세로)로 area를 좁혀 흰색(0,0,0,0) 채움만 카운트. 실측: **정상 빈템플릿 Tj0·흰글리프12 / 완성본 Tj1·흰글리프16** → 임계14로 빈템플릿 pass·완성본 warn 정확히 갈림. 1차 신호 Tj(0 vs 1)만으로도 갈리며 흰글리프는 OR 보조. _collect_fills(reference.py) 재사용.

✅ 검증 결과(①~④ 전부 PASS):
- **①주문서 curl+직접호출**: parse_order → **total 38 / 고유이름 11명 / empty_size 0 / warnings 0**. 의뢰 "11명·유효38행" 일치.
- **②design 5케이스(curl HTTP + 직접호출)**: ⑤빈템플릿=pass+flattened(Tj0/흰12, 투명도ca·CA=0.2→평탄화) · ④완성본=warn(Tj1/흰16) · ②본체누락3.4K=fail(3,419<10K) · ①합성%!PS=fail · ③합성SMask=fail(평탄화후 SMask잔여). **정상pass↔완성본warn 또렷이 구분**.
- **③브라우저(playwright)**: 패턴카드2개 실데이터 / 빈템플릿업로드→filecard pass톤·본체88,141B·평탄화표시 / 완성본업로드→filecard warn톤+alert--warn "빈본체올려주세요" / 주문서업로드→**38행**·첫행"이해솔". 콘솔에러는 외부CDN 폰트404뿐(오프라인·코드무관).
- **④불변제약 git diff**: **engine/ 0변경 + _handoff/ 0변경**(둘 다 빈 diff). webapp/static은 복사본 work.html만 수정(원본 무수정). 빌드0(py_compile OK). 변경파일 4개(.gitignore·api·state·work.html).

💡 tester 참고:
- 기동: `python -m uvicorn webapp.main:app --port 8000` (종료는 포트8000 PID로만, taskkill //f //im node 금지).
- 주문서 테스트: `curl -X POST localhost:8000/api/order/parse -F "file=@<xlsx>"` → total38/이름11.
- 디자인 테스트: `curl -X POST localhost:8000/api/design/check -F "file=@<ai>"` → status(pass|warn|fail)+checks+message+flattened.
- 정상 동작: 빈템플릿=pass(flattened true) / 완성본=warn / 3.4K템플릿=fail(본체누락) / %!PS=fail / SMask=fail.
- 주의입력: SMask 든 PDF=평탄화불가 fail(합성으로만 재현 가능). 한글 콘솔 stdout cp949 깨짐은 표시뿐(UTF-8 덤프로 확인). data/uploads/ 는 gitignore(임시).

⚠️ reviewer 참고:
- design/check 5케이스 우선순위 순서(① %!PS → ② 본체<10K → ④ 베이크 → ③ 투명도 평탄화 → ⑤ pass) — 베이크가 투명도보다 먼저라 빈템플릿(베이크아님)만 ③평탄화 단계로 진입.
- 베이크 임계 _BAKED_WHITE_GLYPH_MAX=14, _BODY_MIN_BYTES=10000 소스상수(실측 기반, 디자인 바뀌면 여기만). 번호area는 preset center/cap_height에서 읽음(하드코딩 좌표 없음).
- save_upload 충돌접두어(시각_랜덤8) + upload.file.seek(0) 후 복사. 평탄화 임시파일 tempfile→점검후 finally cleanup(원본 무손상).

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성 처리·재확보 대기 |
| (해결됨) | grade | 3XL.svg 삭제로 크래시 | disabled_sizes 이동으로 해결 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-20 | dev/test | 이슈3 3XL 안전차단+grade회귀 수정 | 5XL오출고0·grade정상 7/7 |
| 2026-06-20 | dev/test/rev | 이슈1 번호 글리프셋(0~9 outline) | 8/8, 잉크중심0pt, athletic 블록체 |
| 2026-06-20 | pm | 이슈2/4/3/1 커밋(5개) | 미푸시5(푸시대기) |
| 2026-06-20 | tester | 본체92K 풀합성 검증(preset design_file→본체) | design Form 3.4KB→91,917B, verify 9/9 PASS, PNG 비흰51%·본체+밴드+번호 정상 |
| 2026-06-20 | tester | 빈본체 XL11 검증(preset design_file→빈본체 정식설정) | design Form 88,141B 무손실, **겹침없음(30 소멸)**, verify 9/9, PNG 비흰52.6%·번호11/이름 깨끗, 글리프셋 일치확인 |
| 2026-06-20 | dev | 실주문 11명 빈본체 전체 재출력(job per_player 38행) | **생성33/verify PASS33/FAIL0/skip5(3XL)**, design Form 88,141B 전수 byte-identical, 겹침없음·Do3·k/K3·금지0, 대표6건 육안PASS, cowork PDF/PNG 경로명시 |
| 2026-06-20 | dev | 출력형식 PDF/EPS/both(flatten Group제거+eps.py+run_job형식+CLI --format) | 완료기준①~⑤ 전부PASS: 회귀0(픽셀delta>10=0·selftest·job verify)/EPS 305KB벡터·Id0·CMYK/both양쪽생성·verify PASS/GS fallback크래시0/summary집계·checks_eps. 불변제약 무수정. 빌드0 |
| 2026-06-20 | reviewer | 출력형식 코드리뷰(eps.py/flatten/job/cli/preset) | **통과(치명0)**: 불변제약 무수정확정·flatten Group제거 알파/SMask 이중가드·페이지그룹/CS보존 타당·GS fallback크래시0·verify_eps Id벡터판정 정교. 권장3(origin_ok무의미가드·GS경로/임계 하드코딩·미사용 _alpha_gstates). 후속: PDF경로 output/pdf 이전→기존job 구구조 웹앱 양쪽읽기 권장(의뢰서 §2 정합) |
| 2026-06-20 | dev | 웹앱1 FastAPI 뼈대(정적서빙+health/patterns/settings) | 완료기준①~⑤ PASS: uvicorn기동크래시0·curl 3종(V넥 sizes12·glyph_source true·disabled[3XL])·브라우저 패턴실데이터+server-pill연결·engine0변경+_handoff원본무수정(복사본 3파일만)·포트PID종료. fastapi/uvicorn requirements추가. 빌드0 |
| 2026-06-20 | dev | 웹앱2(주문서parse API+디자인점검5케이스+work.html fetch연결) | ①~④ PASS: 주문서 total38/이름11/empty0 · 5케이스 정확(빈템플릿pass+flattened·완성본warn·본체누락fail·%!PS fail·SMask fail, **정상↔완성본 또렷구분** Tj0/1·흰글리프12/16임계14) · 브라우저 업로드→표/점검 정상 · engine0+_handoff0 무수정. 빌드0. data/uploads gitignore |
