# 작업 스크래치패드

## 현재 작업
- **요청**: 코워크 의뢰서 — Phase A(엔진 그레이딩 완성) + Phase B(웹앱). 오늘은 A-1 착수.
- **상태**: 진행 중 — A-1 좌표정합 방식 시험렌더 (developer: 실데이터로 앵커 vs 전체정렬 비교 미리보기 생성)
- **현재 담당**: developer
- **사용자 결정(2026-06-15)**: ①좌표정합=실파일로 먼저 검증(시험렌더 후 확정) ②출력=다페이지 1PDF ③패턴=전사이즈 SVG 보유
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

## 테스트 결과 (tester)
(아직 없음)

## 리뷰 결과 (reviewer)
(아직 없음)

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| pm/검증 | engine/cli.py (또는 진입점) | 한글 Win cp949 콘솔에서 '—'(U+2014) 등 비-cp949 문자 print 시 UnicodeEncodeError 크래시. stdout/stderr UTF-8 고정 필요 | 완료 |

## 작업 로그 (최근 10건만 유지)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-10 | pm | 지식 시스템 초기화, scratchpad 생성 | 완료 |
| 2026-06-10 | planner-architect | DESIGN.md 타당성 검토 보고서 작성(웹리서치+유사솔루션 비교) | 완료 (조건부 GO) |
| 2026-06-15 | pm | engine 환경세팅(pikepdf/PyMuPDF 설치) + requirements.txt 생성 | 완료 |
| 2026-06-15 | debugger | 한글 Win cp949 콘솔 UnicodeEncodeError 수정(진입점 stdout/stderr UTF-8 고정) | selftest PASS |
| 2026-06-15 | pm | git 초기화 + .gitignore + 첫 커밋(d5af10b) | 완료 (미푸시 1건) |
| 2026-06-15 | planner-architect | A-1 preset.json 스키마 설계(일러 grading.jsx 좌표정합 규명+3옵션+사용자결정 도출) | 완료(설계/분석만) |
| 2026-06-15 | developer | A-1 좌표정합 시험렌더(compare_mapping.py): 방식A(앵커) vs 방식B(전체정렬+클립) 실데이터 합성·미리보기·검증 | 완료(outA/B.pdf+previewA/B PNG 생성) |
