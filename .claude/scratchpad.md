# 작업 스크래치패드

## 현재 작업
- **요청**: 코워크 의뢰서 — Phase A(엔진 그레이딩 완성) + Phase B(웹앱). 오늘은 A-1 착수.
- **상태**: ✅ A-1 완료. preset.json+grade.py+cli grade. tester 6/6 통과·reviewer 치명없음 → PM 커밋/푸시 진행
- **현재 담당**: pm (커밋/푸시 후 다음 A-2/A-4 대기)
- **reviewer 백로그(A-2~ 차단아님)**: ①verify.py cm 정규식 음수 허용(engine수정·승인필요) ②shrink 등방한계 ③preset sizes.scale 미사용 ④number/name_area piece_id 검증 ⑤svg_index 정렬가정 재확인
- **사용자 결정(2026-06-15)**: ①좌표정합=**방식 A(앵커 정합) 확정**(시험렌더 검증) ②출력=다페이지 1PDF ③패턴=전사이즈 SVG 보유
- **git**: GitHub 연결 완료(origin=cobby8/grader-v2, main), 3커밋 푸시 완료(미푸시 0)
- **실측 확정값(방식A)**: 디자인 design_XL.ai 영역 앞판 x[468..2098]y[2877..5287] / 뒤판 x[2310..3997]y[2877..5287] / 소매 x[468..2225]y[5301..5562]. 매칭 앞판→패턴idx1, 뒤판→idx0, 소매→idx2. (compare_mapping.py 방식A 로직이 정답 기준)
- **알려진 이슈**: 앵커정합 시 transform 오프셋 음수 가능 → engine verify.py cm 정규식(음수 미허용)이 스케일항목 오판 FAIL. 합성 자체는 정상. engine 수정은 별도 승인 필요.
- **로드맵**: A-1 preset 스키마(좌표정합 핵심) → A-2 패턴로딩 → A-3 grade.py 일괄합성 → A-4 text.py 배번/이름 → A-5 order.py 주문서 → A-6 투명도차단 → B 웹앱
- **불변 제약**: engine 공개 API 유지 / device CMYK 무손실(바이트동일) / 빌드0·순수HTML+vanillaJS / 폴더+JSON 저장 / CLI 단독 테스트 가능
- **실데이터**: ../grader/illustrator-scripts/test/ (config.json, design_XL.ai, pattern_XS.svg, result.json, output_XS_ai.eps) + ../grader/illustrator-scripts/grading.jsx(기존 좌표정합 로직 원천)
- **최우선 미결정**: 디자인↔패턴 좌표 관계(디자인을 조각별로 자르나 vs 1장을 패턴 전체에 정렬하나) → 기존 grading.jsx에 단서 추정

## 기획설계 (planner-architect) — A-1 preset.json 스키마 설계 (2026-06-15)

🎯 목표: 기준 디자인 1개 → 전 사이즈 자동 합성을 위한 패턴 프리셋(preset.json) 스키마 확정. "디자인↔패턴 좌표 정합"을 데이터로 정의.

🔑 핵심 발견 (기존 일러 grading.jsx 분석 근거):
- 좌표계 3개가 전부 다름: 디자인 AI(XL) MediaBox `4478×5669`(세로, 양면펼침) ≠ 패턴 SVG(XS) viewBox `4337×3401`(가로, 조각나열 마커) ≠ 대지 158×200cm 고정.
- **기존 일러는 절대좌표 매핑이 아니었다.** 디자인을 "몸판/패턴선/요소" 레이어로 분해 → 패턴조각엔 색만 칠하고 → 요소(로고/배번/이름)를 **면적비 √(targetArea/baseArea) 스케일 + 조각별 상대벡터**로 재조립. (grading.jsx STEP 5~7)
- engine은 정반대 철학: 디자인 PDF를 **분해 안 하고 통짜 Form XObject 1개**로 임베드 후 조각 윤곽으로 **클리핑**(무손실 CMYK). → 일러의 "요소 재조립"은 이식 불가. preset.json은 **"디자인 통짜→조각별 클립+cm변환"** 정보만 제공하면 됨(engine Piece.outline + Piece.transform에 1:1 대응).

📐 preset.json → engine 매핑 경로 (확정):
- `sizes[].pieces[].outline_svg`(또는 사이즈별 SVG 파일) → parse_svg() → Polyline.points → **Piece.outline**
- `design_mapping`(조각별 fit/anchor/scale 규칙) → 계산 → **Piece.transform = scale_translate(s, ox, oy)** (cm 행렬)
- `sizes[].page_size`(또는 대지 고정) → **SizeLayout.page_size**
- `number_area`/`name_area`(조각 상대 비율) → A-4 text.py가 절대좌표로 환산해 글리프 배치
- `shrink`(가로/세로 수축률) → transform 스케일에 곱하는 보정계수(자리만 확보)

🧭 좌표정합 방식 3옵션 (보고서 본문 참조):
- (가) 조각별 fit-to-bbox(현 build 데모): 단순, but 디자인 왜곡/위치 부정확 → 데모 한정.
- (나) **앵커 기반 정합(추천)**: 디자인에 기준점(몸판 bbox) 정의 + 조각마다 "디자인의 어느 영역을 어떤 앵커로 얹을지" 명시. 일러의 면적비+상대벡터 철학을 좌표화. 무손실 유지.
- (다) 전체정렬 후 클리핑: 디자인 1장을 패턴 전체에 1회 정렬 후 조각 윤곽으로만 분할. 가장 단순·무손실, but 사이즈별 비례·조각 재배치 자유도 낮음.

🔴 사용자 결정 필요 (PM이 질문으로): ①디자인↔패턴 좌표관계 방식(가/나/다) ②사이즈별 개별PDF vs 다페이지 1PDF ③전사이즈 SVG 사전 보유 여부 ④번호/이름 영역 좌표 기준 ⑤shrink 적용 시점. (보고서 4번 섹션에 질문+선택지+추천 정리)

⚠️ 제약 준수: engine 공개 API(compose/Piece/SizeLayout/parse_svg/verify_output) 불변 = 주어진 것. device CMYK 무손실. 과한 추상화 금지. 본 작업 코드 미작성 — 설계/분석만.

### (옛 PoC 기획 — 작업로그로 이관, 상세 생략)
- 타당성검토보고서(조건부 GO) + EPS→PDF 전환결정 + 코워크 PoC지시서. 상세는 decisions.md / 작업로그 참조.

## 구현 기록 (developer)
- requirements.txt 생성 (pikepdf==10.8.0, PyMuPDF==1.27.2.3) — engine/ 전수조사 결과 실제 import는 pikepdf+fitz(PyMuPDF) 둘뿐, 나머지는 표준 라이브러리. 설치 버전 pip show로 일치 확인. (기존 Phase3/4 예정 패키지 목록은 현 시점 미사용이라 실제 의존성으로 교체)

### A-1 좌표정합 시험 렌더 (2026-06-15)
📝 구현한 기능: 디자인↔패턴 좌표정합 두 전략(앵커 vs 전체정렬+클립)을 실데이터로 합성·미리보기·검증하는 일회성 비교 스크립트. engine은 import만(수정 없음).

| 파일/폴더 | 내용 | 신규/수정 |
|----------|------|----------|
| grading_compare/compare_mapping.py | 비교 스크립트(한글 주석+상단 실행법). engine.compose/pattern/pdfutil/preview/verify import만 | 신규 |
| grading_compare/outA.pdf | 방식A(앵커 정합) 결과 PDF (~1.21MB) | 생성물 |
| grading_compare/outB.pdf | 방식B(전체 정렬+클립) 결과 PDF (~1.21MB) | 생성물 |
| grading_compare/previewA/previewA_p01.png | 방식A 미리보기 PNG | 생성물 |
| grading_compare/previewB/previewB_p01.png | 방식B 미리보기 PNG | 생성물 |

💡 tester 참고:
- 테스트 방법: `cd "C:/0. Programing/grader-v2"` 후 `python grading_compare/compare_mapping.py`
- 정상 동작: outA/outB.pdf + previewA/·previewB/ PNG 생성, 두 방식 모두 배치 3개.
- 매칭 확정: 앞판→조각idx1(1542×2085), 뒤판→조각idx0(1542×2193), 소매→조각idx2(1584×176). (parse_svg는 높이 내림차순 정렬이라 인덱스 주의)
- verify 결과: 방식A는 "스케일(cm) 적용" 항목이 FAIL로 뜨는데, 이는 앵커 정합에서 오프셋(e/f)이 음수가 되어 verify.py의 정규식(`[\d.]+ ... cm`, 음수 미허용)에 안 걸리는 것뿐. 실제 스케일/배치는 정상(미리보기로 확인됨). engine 수정 금지라 회피 안 함.
- "투명도 없음" FAIL은 양쪽 공통 — 디자인 워터마크 ca/CA=0.2 탓. 운영 시 평탄화 필요, 이번 비교 관심사 아님.
- 색공간 CMYK 계열 유지 / 디자인 무손실(바이트동일) / 단일 임베드 / 래스터 미추가는 양쪽 PASS.

⚠️ reviewer 참고:
- 앵커 정합 build_layout_A의 등방 스케일은 contain(가로/세로 중 작은 배율) 채택 — engine scale_translate가 등방만 지원하기 때문(비율 보존 우선).
- 미리보기 관찰: 방식A는 앞판/뒤판/소매가 각 패턴 조각 크기에 꽉 맞게 들어가 옷 형태로 정상 보임. 방식B는 디자인 1장을 시트 전체에 한 번 정렬 후 조각 모양으로 오려내, 부위가 어긋나고 잘림(전체정렬 방식의 한계 시각화). 최종 선택은 사용자 몫.

### 수정 이력
| 회차 | 수정 내용 | 수정 파일 | 비고 |
|------|----------|----------|------|
| 1차 | cp949 콘솔 UnicodeEncodeError 수정. `_force_utf8_console()` 헬퍼 추가(stdout/stderr를 UTF-8로 reconfigure, 미지원 시 안전 무시) + main() 첫 줄에서 호출. `import sys`는 기존 존재(추가 불필요). PDF/색 보존 로직 미변경 | engine/cli.py (헬퍼 121~130줄, main() 호출 132줄) | 원래 요청 / 검증: cp949(chcp 949)·PYTHONUTF8 없이 `python -m engine selftest` 크래시 없이 `selftest 종합: PASS` 확인 |

### A-1 마무리 — preset.json + engine/grade.py 일반화 (2026-06-15)
📝 구현한 기능: 방식A(앵커 정합)를 하드코딩 시험스크립트(compare_mapping.py)에서 **preset.json 데이터 + 재사용 모듈(grade.py)**로 일반화. 디자인 1장 → 전 사이즈 자동 합성의 토대(A-2/A-3) 완성. engine 코어(compose/pattern/pdfutil/preview/verify)는 import만, 무수정.

| 파일/폴더 | 내용 | 신규/수정 |
|----------|------|----------|
| data/patterns/농구_U넥_양면/preset.json | 방식A 스키마를 실측값으로 채움. pieces 3개(앞판svg_index1/뒤판0/소매2 + design_region_pt) + design_mapping(anchor,bottom-left,contain) + sizes(XS 1개) + number_area/name_area(뒤판 상대비율, 좌표만) + shrink(1.0 자리) | 신규 |
| data/patterns/농구_U넥_양면/README.md | preset.json 각 필드 한글 설명(JSON은 주석 불가라 별도). 비유 포함 | 신규 |
| data/patterns/농구_U넥_양면/XS.svg | 실데이터 pattern_XS.svg를 폴더로 **복사**(상대경로 참조, 외부 절대경로 의존 제거) | 신규(복사) |
| engine/grade.py | load_preset(검증)/build_layouts(방식A 일반화)/grade(compose 호출). 단독 실행부 포함. 한글 docstring+주석 | 신규 |
| engine/cli.py | `grade` 서브커맨드 최소 추가(import 1줄+cmd_grade+서브파서+docstring). 기존 selftest/build/parse 무변경 | 수정(최소) |
| _grade_out/grade_composed.pdf, grade_p01.png | 합성 결과물(배치3·1.21MB) + 미리보기 | 생성물 |

핵심 로직: `_piece_transform()` = compare_mapping.build_layout_A와 **동일 공식**. 등방 contain 배율 s=min(조각폭/영역폭,조각높이/영역높이)*min(shrink_x,shrink_y), 디자인영역 좌하단→조각 좌하단 앵커정렬 → scale_translate(s, px0-s*dx0, py0-s*dy0). build_layouts는 사이즈마다 그 사이즈 SVG를 parse_svg→svg_index로 조각 매칭→transform 계산→SizeLayout. page_size=조각 전체 bbox+50pt 여백.

✅ 검증 결과:
- **transform 완전 일치**: grade.py build_layouts 3조각 transform+page_size가 compare_mapping 방식A(정답기준)와 숫자까지 100% 동일(코드로 대조 확인).
- **미리보기 픽셀 동일**: grade_p01.png(434302B) == previewA_p01.png(434302B) 바이트 동일. 앞판(YONSEI20+로고)/뒤판(김경원+20+엠블럼)/소매(상단띠) 제자리 합성, 옷 형태 정상.
- **verify_output**: 무손실(바이트동일)·단일임베드·색공간CMYK유지·클리핑·배치횟수(3)·래스터미추가 = PASS. 종합은 FAIL이나 사유는 알려진 2건뿐.
- **selftest 회귀 PASS**(cli 최소수정이 기존 기능 안 깸 확인). grade 서브커맨드 도움말 정상 노출.

💡 tester 참고:
- 테스트 방법: `cd "C:/0. Programing/grader-v2"` 후 `python -m engine grade --preset "data/patterns/농구_U넥_양면/preset.json" --design "C:/0. Programing/grader/illustrator-scripts/test/design_XL.ai" --out "_grade_out"`
- 정상 동작: 배치 3회 + _grade_out/grade_composed.pdf + grade_p01.png 생성. 미리보기에 앞/뒤/소매 옷형태로 보이면 정상.
- 회귀 확인 필수: `python -m engine selftest` → 종합 PASS 유지여야 함(cli.py 수정 영향 없음 확인용).
- 단독 실행도 가능: `python -m engine.grade <preset.json> <design.ai> <out.pdf>`

⚠️ 주의점(tester/reviewer):
- **종합 verify FAIL 2건은 정상(예상됨)**: ①"투명도 없음" FAIL=디자인 워터마크 ca/CA=0.2 탓(운영 시 평탄화, A-6 안건). ②"스케일(cm) 적용" FAIL=앵커정합 오프셋 f가 음수(-2159 등)라 verify.py cm 정규식(음수 미허용)이 못 잡는 **알려진 한계**. 합성/스케일 자체는 정상(미리보기·transform 대조로 입증). **engine verify.py 수정은 별도 승인 사안 — 이번에 안 건드림.**
- pieces 매칭은 parse_svg가 높이 내림차순 정렬이라 svg_index 0=뒤판,1=앞판,2=소매. 사이즈 추가 시 이 정렬 가정 유지되는지 확인 필요.
- number_area/name_area는 좌표(비율)만 정의. 실제 글자 렌더는 A-4(text.py). 비율값은 합리적 초기값이라 실측 후 조정 가능.

## 테스트 결과 (tester)

### A-1 마무리(preset.json + grade.py + cli grade) 검증 (2026-06-15)

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| 1. grade 명령 실행 | ✅ 통과 | "배치 3회" + _grade_out/grade_composed.pdf(1,210,269B) + grade_p01.png 생성. 한글 로그 정상 출력(인코딩 크래시 없음) |
| 2. selftest 회귀 | ✅ 통과 | "selftest 종합: PASS", exit 0. 6사이즈/24배치, inkcov 편차 0.000000. cli.py 수정이 기존 기능 안 깸 |
| 3. 미리보기 시각 확인 | ✅ 통과 | 앞판(YONSEI 20+엠블럼)/뒤판(김경원+20+1885엠블럼+STIZ)/소매(상단 띠) 옷 형태로 제자리 합성 |
| 3b. 정답(previewA) 대조 | ✅ 통과 | grade_p01.png == previewA_p01.png **raw 바이트 완전 동일**(434,302B, 픽셀 동일) |
| 4. verify FAIL 해석 | ✅ 통과 | FAIL 2건뿐 = 둘 다 "알려진 정상"("투명도 없음"=워터마크 ca/CA0.2, "스케일cm"=음수오프셋+정규식한계). **예상 밖 FAIL 0건**. 나머지 6항목 PASS |
| 5. preset.json 유효성 | ✅ 통과 | 정상 JSON 로드, 필수키(design/sizes/pieces/design_mapping) 전부 존재, sizes1·pieces3. grade --help 정상 노출 |

📊 종합: 6개 중 6개 통과 / 0개 실패 → **통과**

판정 근거(객관 수치):
- grade 합성 성공: 배치 3회, PDF 1.21MB, verify 8항목 중 6 PASS·FAIL 2건은 모두 알려진 정상.
- 미리보기 정답 일치: previewA와 **바이트 단위 동일**(시각적 동일 입증, 단순 유사 아님).
- 회귀 무손상: selftest 종합 PASS·exit0, device CMYK 색값 입출력 7=7 일치, inkcov 최대편차 0.
- 예상 밖 FAIL: **없음**. → 수정 요청 추가 없음.
- engine 코드 무수정(검증만 수행).

## 리뷰 결과 (reviewer)

### 리뷰 결과 (A-1 마무리: grade.py + cli grade + preset.json) — 2026-06-15

📊 종합 판정: **통과(조건부)** — 치명 이슈 없음. A-1 목표(방식A 일반화) 달성. 아래 🟡은 A-2~에서 보강 권장.

✅ 잘된 점:
- engine 공개 API 불변 완벽 준수: grade.py는 compose/Piece/SizeLayout/parse_svg/scale_translate를 **import만** 함(수정 0). cli.py는 import 1줄+cmd_grade+서브파서만 최소 추가, 기존 selftest/build/parse 무변경(tester selftest 회귀 PASS).
- 방식A 로직 정확성: _piece_transform 공식이 compare_mapping.build_layout_A와 동일(등방 contain s=min(pw/dw,ph/dh), 앵커 bottom-left ox=px0-s*dx0). 실제 출력 cm값 대조로 transform 일치 확인.
- preset 검증 견고: load_preset이 파일존재/JSON/필수키/sizes·pieces 빈값/조각별 svg_index·design_region_pt(길이4)까지 친절한 한글 에러로 선검증. 바이브코더 친화적.
- 무손실/색보존 원칙 무위반: grade.py는 좌표(transform)만 계산, 색공간·이미지·재압축 일절 손대지 않음. compose가 Form XObject 단일임베드로 device CMYK 그대로 통과.
- README.md가 preset.json 각 필드를 비유+한글로 충실히 설명(JSON 주석 불가 보완). XS.svg 폴더복사로 외부 절대경로 의존 제거 — 이식성 좋음.

🔴 필수 수정: **없음** (이번 단계 기준)

🟡 권장 수정 (A-2~에서):
- [verify.py:197 / grade] "스케일(cm) 적용" FAIL = 알려진 이슈. 실측 확인: 출력 cm의 f값이 3조각 모두 음수(-2159/-2288/-1067)라 정규식 `[\d.]+ ... cm`(음수 미허용)에 0건 매칭→FAIL. **합성은 정상**(transform·미리보기 일치). 의견은 아래 '결정사안'. 결정 전까지 cmd_grade 종료코드(verify FAIL→exit1)가 CI/자동화에서 실패로 잡힐 수 있음 주의.
- [grade.py:102 _piece_transform] shrink를 `* min(shrink_x, shrink_y)`로 등방 적용. 현재 1.0이라 무해하나, 실제 수축은 가로·세로 비율이 다른 게 정상(예 x0.98/y0.97)인데 등방 한계로 더 작은 쪽만 반영됨. shrink 실값 투입 시 한 축 보정 부정확 → A-2에서 shrink 의미/적용지점 재설계(지금은 자리만 잡은 상태라 OK).
- [grade.py:110 build_layouts] design_pdf_path를 존재검사만 하고 미사용(주석에 명시). compose가 같은 파일을 다시 여므로 중복이나, 조기 에러 이점 있어 유지 무방.
- [preset.json sizes.scale] scale 필드가 정의돼 있으나 build_layouts에서 **미사용**. README엔 "보조 배율"로 설명 → 스키마/구현 불일치. 사용(transform에 곱)할지 제거할지 A-2 정리.
- [preset.json svg_index] parse_svg 높이 내림차순 정렬 가정이라 S/M/L 추가 시 사이즈별 조각 높이순서가 바뀌면 깨질 위험 → per-size svg_index 재확인 필요(README에 경고는 있음).
- [preset.json number_area/name_area] piece_id가 pieces[].id에 실제 존재하는지 load_preset에 검증 없음. A-4 text.py 전 piece_id 유효성 검증 추가 권장. rel_bbox(0~1) 형태는 A-4 절대좌표 환산에 적합 — 방향 OK.
- [grade.py:147-149 page_size] 좌하단 원점 고정(여백 0). 현재 조각이 양수라 안전하나 사이즈 확장 시 minx/miny 음수 가능성 점검 권장(compare_mapping과 동일 가정).

🧭 결정사안(verify FAIL 처리) — 리뷰어 의견(결정은 PM/사용자):
- **권장: grade 쪽 좌표 양수화 하지 말 것. verify.py cm 정규식만 음수 허용(`[\d.]+`→`[-\d.]+`)으로 보강**(별도 승인 후).
- 근거: ①앵커정합의 음수 오프셋은 수학적으로 올바른 정상 결과(디자인영역 좌하단을 조각으로 끌어내리는 평행이동). 인위 양수화하면 page_size·클립윤곽·디자인배치를 함께 평행이동해야 해 로직 복잡↑·버그표면적↑. ②무손실/색보존 무영향(좌표변환은 색·바이트 불변). ③verify 목적은 "스케일 cm 존재 여부" 검출인데 현 정규식이 e/f 부호까지 강제 → 과검증(정규식 자체가 버그에 가까움). **단 engine 수정은 별도 승인 필요** — A-3 verify 보강 안건.

📌 결론: A-1 산출물 **머지/커밋 가능**. verify "스케일 FAIL"·"투명도 FAIL" 2건은 알려진 사유(코드결함 아님)로 확정. 위 🟡은 차단요소 아님(A-2~ 백로그). conventions.md 비어있음 → PM이 본 리뷰에서 검출된 패턴(engine import만/무손실 좌표분리/preset 선검증) 승격 검토 권장.

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| pm/검증 | engine/cli.py (또는 진입점) | 한글 Win cp949 콘솔에서 '—'(U+2014) 등 비-cp949 문자 print 시 UnicodeEncodeError 크래시. stdout/stderr UTF-8 고정 필요 | 완료 |

## 작업 로그 (최근 10건만 유지)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-10 | planner-architect | DESIGN.md 타당성 검토 보고서 작성(웹리서치+유사솔루션 비교) | 완료 (조건부 GO) |
| 2026-06-15 | pm | engine 환경세팅(pikepdf/PyMuPDF 설치) + requirements.txt 생성 | 완료 |
| 2026-06-15 | debugger | 한글 Win cp949 콘솔 UnicodeEncodeError 수정(진입점 stdout/stderr UTF-8 고정) | selftest PASS |
| 2026-06-15 | pm | git 초기화 + .gitignore + 첫 커밋(d5af10b) | 완료 (미푸시 1건) |
| 2026-06-15 | planner-architect | A-1 preset.json 스키마 설계(일러 grading.jsx 좌표정합 규명+3옵션+사용자결정 도출) | 완료(설계/분석만) |
| 2026-06-15 | developer | A-1 좌표정합 시험렌더(compare_mapping.py): 방식A(앵커) vs 방식B(전체정렬+클립) 실데이터 합성·미리보기·검증 | 완료(outA/B.pdf+previewA/B PNG 생성) |
| 2026-06-15 | developer | A-1 마무리: preset.json+README+grade.py(방식A 일반화)+cli grade서브커맨드. XS 합성 검증 | 완료(transform·미리보기 previewA와 100%동일, selftest 회귀 PASS) |
| 2026-06-15 | tester | A-1 마무리 검증: grade실행·selftest회귀·미리보기 정답대조·verify해석·preset유효성 | 통과(6/6, previewA 바이트동일, 회귀PASS, 예상밖FAIL 0) |
| 2026-06-15 | reviewer | A-1 마무리 코드리뷰: engine API불변·방식A로직·preset견고성 | 통과(치명0, 커밋가능, 🟡5건 A-2백로그) |
| 2026-06-15 | pm | conventions 3패턴 승격 + A-1 완료 커밋/푸시 | 완료 |
