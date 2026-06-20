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

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성 처리·재확보 대기 |
| (해결됨) | grade | 3XL.svg 삭제로 크래시 | disabled_sizes 이동으로 해결 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-19 | pm/팀 | Phase B~E 완성본주입 통합 | 완료·푸시 |
| 2026-06-19 | dev/test | 이슈2 번호 잉크중앙정렬 | 오차0pt, 6/6 |
| 2026-06-19 | dev/test | 이슈4 재단선 보존 인프라 | 7/7(실파일 재단선 부재→디자이너 재출력 대기) |
| 2026-06-20 | dev/test/rev | 이슈3 암홀X 3조각 복원+단조성가드 | 12개 PASS, 3XL 결함 발견 |
| 2026-06-20 | dev/test | 이슈3 3XL 안전차단+grade회귀 수정 | 5XL오출고0·grade정상 7/7 |
| 2026-06-20 | dev/test/rev | 이슈1 번호 글리프셋(0~9 outline) | 8/8, 잉크중심0pt, athletic 블록체 |
| 2026-06-20 | pm | 이슈2/4/3/1 커밋(5개) | 미푸시5(푸시대기) |
| 2026-06-20 | tester | 본체92K 풀합성 검증(preset design_file→본체) | design Form 3.4KB→91,917B, verify 9/9 PASS, PNG 비흰51%·본체+밴드+번호 정상 |
| 2026-06-20 | tester | 빈본체 XL11 검증(preset design_file→빈본체 정식설정) | design Form 88,141B 무손실, **겹침없음(30 소멸)**, verify 9/9, PNG 비흰52.6%·번호11/이름 깨끗, 글리프셋 일치확인 |
| 2026-06-20 | dev | 실주문 11명 빈본체 전체 재출력(job per_player 38행) | **생성33/verify PASS33/FAIL0/skip5(3XL)**, design Form 88,141B 전수 byte-identical, 겹침없음·Do3·k/K3·금지0, 대표6건 육안PASS, cowork PDF/PNG 경로명시 |
