# 의뢰서 — CLI 다음 단계 (grader-v2, A-1 이후)

> 수신: 구현 담당(CLI)  |  발신: 코워크(허브)  |  작성일: 2026-06-15
> 선행: `의뢰서-CLI-구현.md`(Phase A/B 전체) · `현황-2026-06-15.md`(통합 현황). 이 문서는 **A-1 완료 이후 잔여 작업**만 다룬다.

---

## 0. 지금 상태 (이미 된 것 — 다시 만들지 말 것)

- **engine 출력 코어** 완성: `compose / verify_output / render_previews`.
- **Phase A-1 완료**: 좌표정합 **방식 A(앵커 bottom-left + contain)** 확정. 다음이 존재한다:
  - `engine/grade.py` — `load_preset(path)`, `build_layouts(preset, design_pdf)`, `grade(preset, design, out)`. 앵커 변환 `_piece_transform(design_region, poly, shrink_x, shrink_y)`.
  - `data/patterns/농구_U넥_양면/preset.json` — `design.content_box`, 조각별 `svg_index`+`design_region_pt`, `design_mapping(anchor)`, `number_area`/`name_area(rel_bbox, piece_id)`, `shrink`.
  - CLI: `python -m engine grade --preset … --design … --out …` → 전 사이즈 합성 + verify + 미리보기.
  - 결과 `_grade_out/grade_p01.png` 정상(앞/뒤판 정렬, 투명도 외 verify PASS).
- **UI 디자인** 완성 → `web/`(정적 HTML/CSS/JS, 화면 3개). API mock 형태는 계약과 일치. 출력 카피는 PDF로 정정됨.

> 원칙 유지: engine은 웹 없이 CLI로 항상 단독 테스트. device CMYK 무손실(바이트 동일성) 깨지 말 것. preset 기존 스키마는 **확장**하되 기존 키 의미는 보존.

---

## 1. 이번 의뢰 범위 (우선순위)

| # | 작업 | 트랙 | 선행 |
|---|------|------|------|
| 1 | **A-4 배번·이름 렌더 `text.py`** | 엔진 | 없음(바로) |
| 2 | **A-5 주문서 파싱 `order.py`** | 엔진 | 없음(바로) |
| 3 | **주문 통합 `job`** (주문 행 × 디자인 → 선수별 출력) | 엔진 | 1·2 |
| 4 | **A-2 전 사이즈** (XS~5XL) | 엔진 | 실제 사이즈별 패턴(사용자) |
| 5 | **Phase B 웹앱**(FastAPI + `web/` 결합) | 웹 | 1~3 권장 |

---

## 2. A-4 — 배번·이름 벡터 렌더 (`engine/text.py`)

**목표**: preset의 `number_area`/`name_area`(조각 기준 `rel_bbox`)에 배번(숫자)·이름(한글)을 **벡터 경로**로 렌더. 폰트 임베드 없이 공장 호환.

**방식**: `fontTools`로 글리프 → 윤곽 좌표 → PDF 경로 연산자(`m/l/c … f`), CMYK 단색 fill(+선택 stroke). 아웃라인화와 동일 효과.

**인터페이스 제안**(기존과 결합):
```python
# text.py
def render_text_ops(text, font_path, bbox_pt, color_cmyk, align="center") -> str
    """글자를 bbox 안에 맞춰 PDF 콘텐츠 연산자 문자열로. (compose 콘텐츠에 끼워넣음)"""
```
- `compose.py`는 디자인 Form 배치만 한다 → 텍스트는 **페이지 콘텐츠 스트림에 추가 블록**으로 그리거나, `Piece`에 선택적 `extra_ops` 필드를 더해 합성한다(작은 확장, 무손실 유지).
- `rel_bbox`(0~1) → 해당 조각 `outline` bbox로 환산해 실제 좌표 계산.

**완료 기준**: `grade` 결과에 지정 선수의 배번/이름이 정위치 벡터로 찍히고, `verify_output` **여전히 PASS**(래스터 미추가·CMYK 유지). 한글 이름·숫자 배번 모두. CLI로 단독 확인 가능.

## 3. A-5 — 주문서 파싱 (`engine/order.py`)

**목표**: xlsx → `[{size, qty, name, number}]`. 웹 업로드/CLI 양쪽에서 호출.

**이식할 지식(기존 grader, 코드 아님 규칙만)**: 사이즈 키워드 **긴 것부터** 매칭(5XL→…→XL→…→S), 셀 **전체 스캔**(가로형/세로형/표형 모두), openpyxl **Custom Properties 버그 워크어라운드**. 추출 실패 셀은 빈 값으로 표시(웹에서 붉게 강조 → 사용자 입력).

**인터페이스**:
```python
# order.py
def parse_order(xlsx_path) -> list[dict]   # [{size, qty, name, number}], 실패 셀은 빈 문자열
```
**완료 기준**: 실제 주문서 양식 2~3종으로 행 추출 검증. 누락 셀이 누락으로(크래시 없이) 표시.

## 4. 주문 통합 — 선수별 출력 (`engine/job.py` 또는 grade 확장)

**핵심**: 현재 `grade()`는 디자인 1장 → 사이즈별 페이지다. 실제 작업 단위는 **선수별**(같은 사이즈라도 이름·배번이 다름). 주문 행을 받아 **(사이즈, 이름, 배번)별로 배번/이름을 바꿔** 출력해야 한다.

**인터페이스 제안**:
```python
# job.py
def run_job(preset, design_pdf, order_rows, out_dir,
            font_path, split="per_player") -> dict
    """주문 행마다 배번/이름을 갈아끼워 합성. split: per_player(파일별) | single(다페이지).
       반환: {outputs:[{size,name,number,pdf,preview,checks}], summary}"""
```
- 각 선수 = 해당 사이즈 레이아웃 + 그 선수의 배번/이름 텍스트 블록.
- 결과를 ZIP으로 묶을 수 있게 폴더 구조 정리(`data/jobs/<날짜_주문명>/output/`).

**완료 기준**: 실제 패턴+디자인+주문서로 **전 사이즈 × 전 선수 PDF 한 벌** 생성. 모든 출력 verify PASS(평탄화 디자인 기준). CLI 한 줄 재현.

## 5. A-2 — 전 사이즈 (XS~5XL)

- 현재 `preset.sizes`에 XS 1개뿐. 사이즈별 `pattern_file` + `scale`(또는 사이즈별 윤곽) 추가.
- **사용자 입력 필요**: 실제 XS~5XL 패턴 파일(SVG/DXF). 확보 전까지는 XS로 파이프라인 완성.
- `build_layouts`는 이미 `preset["sizes"]` 순회 구조 → 데이터만 채우면 확장됨(설계 양호).

**완료 기준**: 전 사이즈 패턴 입력 시 사이즈별 페이지가 정위치로. 사이즈 태그/스케일 정확.

## 6. Phase B — 웹앱 (FastAPI + `web/` 결합)

- `engine`을 import하는 얇은 서버. 빌드 0. `web/`를 정적 마운트.
- **API 계약**: `의뢰서-CLI-구현.md` 3-B-2 표 = `web/README.md`의 mock 형태와 동일. 각 화면 `<script>`의 mock 배열을 서버 응답으로 치환하면 결합된다.
  - 핵심 엔드포인트: 패턴목록 / 디자인업로드(투명도·색공간 점검 결과 반환) / 주문업로드(order.py) / 생성(job.run_job, 진행률) / 미리보기+checks / ZIP.
- 데이터: 폴더+JSON(`data/patterns`, `data/jobs`). 작업 폴더 쓰기는 원자적(임시→rename).
- **UX 규칙 유지**(web/README 5항): 점진적 노출 · 투명도 진행 차단 · 추출 실패 셀 강조 · 부분 실패 허용 · 모든 빈/로딩/오류 상태.

**완료 기준**: 직원이 브라우저로 주문 1건 end-to-end(패턴 선택~ZIP). 투명도 디자인 업로드 시 화면 경고+진행 차단.

---

## 7. 사용자(수빈) 준비 필요
- **전 사이즈 패턴**(XS~5XL) — A-2 입력.
- **배번/이름 폰트**(ttf/otf) + 라이선스 확인 — A-4 입력.
- **공장 출력 포맷** 확정(사이즈별 개별 PDF vs 다페이지 1 PDF) — job split 결정.
- **공장 시험인쇄 승인** — Phase A 완료의 절대 조건(미리보기≠RIP).

## 8. 참고
`engine/grade.py`·`preset.json`(현 구조) · `engine/README.md`(API·한계) · `현황-2026-06-15.md` · `web/README.md`(API 결합 지점·UX 규칙) · `의뢰서-CLI-구현.md`(전체 맥락) · 실데이터 `../grader/illustrator-scripts/test/`.
