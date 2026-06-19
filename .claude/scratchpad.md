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
