# 의뢰서 — CLI 구현 (grader-v2)

> 수신: 구현 담당(클로드 코드/CLI)  |  발신: 코워크(허브)  |  작성일: 2026-06-15
> 협업 구조: **코워크가 조율**하고, **CLI가 구현**, **UI/UX는 디자인 클로드**가 담당.
> 이 의뢰서는 자기완결적이다. 더 깊은 배경은 `DESIGN.md`, `engine/README.md`, `NOTE-PHASE1-2026-06-15.md` 참조.

---

## 0. 한 줄 요약

스티즈 전사유니폼 출력 자동화. 주문이 들어오면 **기준 사이즈 디자인 1개로 전 사이즈·전 선수의 공장 출력용 벡터 CMYK PDF를 자동 생성**한다. Illustrator는 출력 과정에서 완전히 배제(디자인 제작 도구로만 남음). 이미 **출력 엔진 코어(`engine/`)는 완성·검증됨**. 이 의뢰는 그 위에 **(A) 진짜 그레이딩 완성 → (B) 웹앱 골격**을 얹는 것.

## 1. 지금까지 된 것 / 안 된 것 (출발점)

`engine/` 패키지는 웹과 분리된 순수 Python 모듈로 이미 동작한다 (`python -m engine selftest` 종합 PASS, 실제 디자인 end-to-end 렌더 성공).

**완성된 공개 API — 깨지 말고 그대로 사용할 것:**

```python
from engine.compose import Piece, SizeLayout, compose
from engine.pattern import parse_svg, Polyline
from engine.verify import verify_output, format_report, all_passed
from engine.preview import render_previews

# 코어: 디자인을 사이즈별 레이아웃에 단일 임베드 합성 → CMYK PDF
compose(design_pdf: str, layouts: list[SizeLayout], out_path: str) -> int  # 배치 수 반환
# Piece(outline=[(x,y)...], transform=(a,b,c,d,e,f), name)  # PDF 좌표, cm 행렬
# SizeLayout(name, page_size=(w,h), pieces=[Piece,...])      # 한 사이즈 = 1페이지
parse_svg(path, flip_y=True) -> list[Polyline]               # <polyline> → 윤곽(PDF 좌표)
verify_output(out_pdf, design_pdf, expected_placements) -> list[Check]
```

**검증된 보장(verify_output이 자동 검사):** 디자인 무손실 보존(바이트 동일) · 디자인 단일 임베드 · 색공간 CMYK 계열 유지 · **투명도 발견 시 FAIL**(안전장치) · 합성 정확(클립/스케일/배치/벡터 유지).

**아직 안 된 것 (이번 의뢰 범위):**
1. **디자인↔패턴 좌표 정합(진짜 그레이딩).** 디자인 페이지 좌표계 ≠ 패턴 viewBox 좌표계라, "디자인의 어느 영역이 어느 조각에 얹히는가"는 자동추정 불가. 현재 `engine build`는 데모로 전체 디자인을 조각 bbox에 fit할 뿐. → **패턴 프리셋에 매핑을 정의**해야 함.
2. **전 사이즈 그레이딩**(XS~5XL 일괄). 현재 build는 1사이즈.
3. **배번·이름 자동 입력**, **주문서(xlsx) 인식**.
4. **웹앱**(브라우저 UI + 서버).

---

## 2. Phase A — 엔진 그레이딩 완성 (UI 불필요, CLI로 완결)

> 목표: 실제 패턴 + 디자인 + 주문서로 **전 사이즈 × 전 선수 PDF 한 벌**을 CLI 한 번에 생성. 디자인 작업과 독립 병행 가능.

### A-1. 패턴 프리셋 스키마 설계 (`preset.json`) — 가장 먼저
패턴 1종을 정의하는 단일 JSON. 자동 분류에 의존하지 말고 **명시적으로** 정의(DESIGN.md 리스크: V넥 등 양식별 조각 차이).

설계해야 할 항목(초안 — 확정은 구현자 재량):
- `sizes`: 지원 사이즈 목록과 각 사이즈 패턴 파일명 (`{"XS":"XS.svg", ...}`).
- `pieces`: 조각 정의 — 식별자, 패턴 내 어떤 윤곽인지 매칭 규칙(인덱스/높이순/레이어명 등).
- `design_mapping`: **핵심** — 각 조각이 기준 디자인의 어느 영역을 어떤 변환(스케일·이동·회전)으로 가져오는지. 디자인 좌표 → 조각 시트 좌표 매핑. (기존엔 일러 레이어가 담당하던 정보)
- `number_area` / `name_area`: 배번/이름이 들어갈 위치·크기·정렬·색(CMYK)·폰트. 조각 기준 상대 비율로.
- `shrink`(선택, 향후): 원단 수축 보정 계수 자리만 마련.

> 결정 필요 사항을 코워크/사용자에게 질문으로 올릴 것: **기준 디자인과 패턴의 좌표 관계를 어떻게 잡을지**(예: 디자인을 조각별로 잘라 만드는가, 디자인 1장을 패턴 전체에 정렬하는가). 실제 운영 파일 1~2종으로 확정 권장.

### A-2. 패턴 로딩 확장 (`engine/pattern.py`)
- 사이즈별 SVG(XS~5XL) 로딩. `preset.json`의 `pieces` 규칙으로 조각 식별(현재의 높이순 자동분류는 fallback).
- 좌표 정합 유틸: `design_mapping`을 `Piece.transform`(cm 행렬)으로 변환하는 함수.

### A-3. 그레이딩 일괄 합성 (신규 `engine/grade.py` 또는 compose 확장)
- preset + 기준 디자인 → 전 사이즈 `SizeLayout` 목록 생성 → `compose()` 1회 호출로 다페이지 PDF.
- 사이즈별 페이지 또는 사이즈별 개별 PDF(공장 요구에 맞춤 — 사용자 확인).

### A-4. 배번·이름 렌더 (신규 `engine/text.py`)
- `fontTools`로 글리프 → **벡터 경로(아웃라인화)**, 폰트 임베드 없이 공장 호환. CMYK 단색 fill(+선택 stroke).
- preset의 `number_area`/`name_area` 좌표에 배치. 한글 이름·숫자 배번 모두.
- 합성 후에도 `verify_output`이 PASS여야 함(래스터 미추가).

### A-5. 주문서 파싱 (신규 `engine/order.py`)
- `openpyxl`로 xlsx → `[{size, qty, name, number}]`.
- **기존 grader 지식 이식**(코드 아님, 규칙만): 사이즈 키워드 긴 것부터 매칭(5XL→XL), 셀 전체 스캔(가로/세로/표형), openpyxl Custom Properties 버그 워크어라운드.

### A-6. 투명도 정책 강화
- 현재 verify는 투명도를 FAIL로 잡음. 운영 흐름에서는 **업로드 시점에 차단**하고 "원본에서 평탄화 후 재등록" 안내. (경고 후 진행 금지 — 설계 검토 권고사항)

### Phase A 완료 기준 (AC)
1. 실제 패턴(전 사이즈) + 평탄화된 실제 디자인 + 실제 주문서 1종으로 **전 사이즈 × 전 선수 PDF** 생성.
2. 모든 출력에 대해 `verify_output` 전 항목 PASS.
3. 배번·이름이 정위치에 벡터로 렌더(미리보기 확인).
4. CLI 한 줄로 재현 가능(`python -m engine grade --preset ... --design ... --order ...`).
5. **공장 시험인쇄용 1벌** 산출(실제 RIP 승인은 사용자 담당 — 미리보기 PNG 통과 ≠ RIP 통과).

---

## 3. Phase B — 웹앱 골격 (디자인 클로드 산출물과 결합)

> 목표: 직원이 **브라우저만으로** 주문 1건을 처리(패턴 선택 → 업로드 → 생성 → 미리보기 → ZIP). 서버는 사무실 PC 1대 또는 클라우드 VM 1대.

### B-1. 서버 (FastAPI + Uvicorn)
- `engine`을 그대로 import해서 호출(웹은 얇은 껍데기). 빌드 단계 0.
- 정적 파일 서빙(디자인 클로드의 HTML/CSS/JS를 그대로 마운트).
- 데이터 저장: **폴더 + JSON**(DB 없음). DESIGN.md 6번 데이터 모델 따름:
  ```
  data/patterns/<패턴>/preset.json, XS.svg…5XL.svg
  data/fonts/
  data/jobs/<날짜_주문명>/job.json, design.pdf, output/
  ```
- 동시성: 작업 폴더 쓰기는 **원자적**으로(임시 폴더 후 rename). 설계 검토 지적사항.

### B-2. API 계약 (초안 — 디자인 의뢰서와 공유) 
아래 형태로 맞추면 디자인 클로드의 화면과 무리 없이 결합된다. 응답은 JSON.

| 메서드 | 경로 | 용도 | 응답(요지) |
|--------|------|------|-----------|
| GET | `/api/patterns` | 등록된 패턴 목록 | `[{id,name,sizes:[...],thumb}]` |
| POST | `/api/patterns` | 패턴 신규 등록(사이즈별 파일+영역) | `{id}` |
| POST | `/api/jobs` | 작업 생성(패턴 선택) | `{job_id}` |
| POST | `/api/jobs/{id}/design` | 디자인 업로드 | `{ok, transparency:[...], colorspace_ok}` ← **투명도 경고용** |
| POST | `/api/jobs/{id}/order` | 주문서 업로드 → 자동 추출 | `{rows:[{size,qty,name,number}]}` |
| PUT | `/api/jobs/{id}/order` | 추출표 수정 저장 | `{ok}` |
| POST | `/api/jobs/{id}/generate` | 전 사이즈×선수 생성 | `{task_id}` (진행률 폴링/SSE) |
| GET | `/api/jobs/{id}/status` | 진행률 | `{done,total,state}` |
| GET | `/api/jobs/{id}/previews` | 미리보기 PNG 목록 | `[{size,name,url,checks:[{name,ok}]}]` |
| GET | `/api/jobs/{id}/download` | 결과 ZIP | (파일) |
| GET | `/api/jobs` | 작업 기록 | `[{id,date,name,pattern,status}]` |

> 검증 결과(`verify_output`)를 `previews` 응답의 `checks`로 그대로 노출 → 화면에서 "공장 전달 가능/불가"를 명확히 표시.

### B-3. UI 결합
- 디자인 클로드가 `의뢰서-디자인-UIUX.md` 기준으로 정적 HTML/CSS(필요시 vanilla JS) 산출.
- CLI는 그 마크업에 위 API를 fetch로 연결. 프레임워크/빌드체인 없음(React 금지 — DESIGN.md 결정).

### Phase B 완료 기준 (AC)
- 직원이 브라우저로 주문 1건을 처음부터 끝까지(패턴 선택~ZIP 다운로드) 처리.
- 투명도 있는 디자인 업로드 시 경고가 화면에 표시되고 진행이 막힘.
- 생성 결과 미리보기 그리드 + 검증 결과 배지 표시.

---

## 4. 비범위 (이번에 하지 말 것 — DESIGN.md 의도적 제외)
G드라이브 자동 동기화 · AI→SVG 일괄 변환 · 자동 업데이트 시스템 · Supabase 인증 · 데스크톱 앱/Tauri/Rust. 이것들은 기능이 아니라 복잡도의 근원이었다. (외부 확장 시점에 인증만 별도 검토)

## 5. 기술 제약 / 원칙
- **Python 단일 스택, 빌드 단계 0.** 화면은 순수 HTML+vanilla JS.
- **device CMYK 무손실**: 색공간 변환 금지. engine이 보장하는 바이트 동일성 깨지 말 것.
- **engine은 웹 없이 항상 CLI로 테스트 가능**하게 유지. 새 모듈도 `python -m engine ...`로 단독 검증.
- **바이브 코딩 친화**: 모듈 경계 명확, 한글 주석, 과한 추상화 지양. 한 파일 한 책임.
- 폴더+JSON 저장(DB 없음). 백업 = 폴더 복사.

## 6. 리스크 / 먼저 물어볼 것
- **(최우선) 디자인↔패턴 좌표 관계 확정** — 실제 운영 파일로. 이게 A-1의 핵심이자 전체 성패.
- 공장이 **사이즈별 개별 PDF**를 원하는가, **다페이지 1 PDF**인가.
- 폰트 라이선스(아웃라인화라 부담 적지만 상용폰트 확인).
- 원단 수축 보정·PMS 별색은 향후 — preset에 자리만.

## 7. 참고 파일
`DESIGN.md`(전체 설계) · `engine/README.md`(API·한계) · `NOTE-PHASE1-2026-06-15.md`(현재 상태·발견) · `poc/poc_cmyk_compose.py`(원리 증명) · `grader-v2-타당성검토보고서.md`(리스크 분석) · 실데이터 `../grader/illustrator-scripts/test/`.
