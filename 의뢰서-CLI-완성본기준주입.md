# 의뢰서 (CLI/Claude Code 용) — 완성본 기준 → 빈 템플릿 선수별 주입 정식 통합

> 작성: 2026-06-18 (cowork 세션에서 설계·검증 완료분 인계)
> 실행 환경: **CLI(Claude Code, 수빈님 Windows PC)**. 이유: cowork 샌드박스 마운트가 새로
> 쓴 파일을 잘린 상태로 읽고 git lock 처리가 안 되며 G드라이브 패턴이 안 보임 → 코드 반영·
> 커밋·실제 패턴 실행은 CLI가 깔끔. (cowork 쪽은 시각 검증·정합 미세조정 담당)

---

## 0. 한 줄 목표
디자이너가 주는 **완성본(샘플 번호·이름 포함)** + **빈 템플릿(번호·이름 없음)** 2개로,
주문서의 선수마다 **앞 번호·뒤 번호·뒤 이름**을 완성본과 **동일한 크기·위치·자간**으로 빈
템플릿에 주입해 전사 출력 PDF를 생성한다. 모든 출력 verify PASS, CLI 한 줄 재현.

핵심 전환: 완성본의 번호 도형을 **지우지 않는다**. 완성본은 "정답지(좌표·크기·색·자간의
기준)"로만 쓰고, 실제 캔버스는 깨끗한 빈 템플릿이다. (상세: `계획서-완성본기준-템플릿주입.md`)

---

## 1. 먼저 — 미커밋 작업 커밋 (안전 반영)
cowork에서 검증했으나 아직 커밋 안 된 것들. **내용 검토 후 커밋**:
- `engine/text.py` — **TTF 폰트 지원 버그 수정**(아래 2번). 가장 중요.
- `engine/reference.py` — 완성본에서 번호/이름 위치 자동 추출기(초안).
- `계획서-완성본기준-템플릿주입.md`, `의뢰서-CLI-완성본기준주입.md`(이 파일)
- `data/fonts/HY헤드라인M.ttf` — 번호·이름 공통 폰트(아래 3번).

이미 커밋됨(`d845072`): `engine/job.py`(선수별 출력), `engine/flatten.py`(투명도 평탄화),
`engine/verify.py`(cm 정규식 음수 허용), `engine/cli.py`(job·flatten 명령). **origin 푸시 필요**.

---

## 2. text.py 폰트 수정 (이미 반영됨 — 검증/유지)
**증상**: HY헤드라인(TTF)으로 한글 이름이 통째 안 나옴(폰트 미적용).
**근본 원인**: 기존 `_glyph_path_ops`가 OTF(CFF) 전용 — ①한글 합성 글리프(addComponent,
자모 조합)를 분해 못 함 ②TTF 2차 베지어(qCurveTo)를 직선 근사.
**해결**(표준 방식, 회귀 없음):
```python
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.qu2cuPen import Qu2CuPen
# _glyph_path_ops 안:
dpen = DecomposingRecordingPen(glyphset); glyphset[glyph_name].draw(dpen)
rec = RecordingPen(); dpen.replay(Qu2CuPen(rec, max_err=1.0, all_cubic=True))
# 이후 rec.value(=cubic only) 를 m/l/c/h 로 변환
```
**검증 완료**: 김경원/이상혁/뷁뎠활(겹받침) + 0~9 모두 정확 벡터화. Pretendard(CFF)도 통과.
→ CLI 할 일: 이 수정이 들어갔는지 확인하고, `python -m engine selftest` 회귀 통과 확인.

---

## 3. 폰트 사실 (확정)
- `data/fonts/HY헤드라인M.ttf` 의 PostScript 이름 = **H2hdrM** = **완성본의 이름 "김경원"이
  실제로 쓴 폰트**. 즉 이 폰트가 이름·번호 공통 기준 폰트다. (번호 자릿폭/피치도 거의 일치 확인)
- 메타: upm=1024. 숫자 ink 높이 ≈903(0/8/9), 870(7); 숫자 advW=597; 한글 advW=1024(=1em).

---

## 4. 정밀 정합 — 검증된 수치/공식 (그대로 구현)
연세대 V넥 완성본(`연세대 레플리카 블루림 V넥 스탠다드 베이직 XL.ai`) 기준 추출값:

| 요소 | 값 (design pt, 페이지 4478.74×5669.29, 좌하단 원점) |
|------|------|
| 이름 | 폰트 H2hdrM, 크기 **136.40**, baseline y≈**4765.7**, 중심 x≈**3219.8**, 음절 피치 **195.4**, bbox x[2956.2..3483.5] y[4744.3..4882.7] |
| 뒤 번호 | 자릿수 높이 **539**, 중심 (**3217, 4342**), 2자리 자릿중심 x=3040/3392(피치 352), 자릿폭≈301 |
| 앞 번호 | 자릿수 높이 **310**, 중심 (**1389, 4184**), 2자리 자릿중심 x=1288/1490(피치 202), 자릿폭≈173 |
| 앞/뒤 분할 | 페이지 폭 절반 x=2239.37 (왼=앞, 오=뒤) |

**정밀 배치 공식** (현재 `render_text_ops` 의 bbox-contain 방식은 부정확 → 아래로 보강):
- **번호**: 대표 자릿 글리프 ink 높이(font units)로 scale `s = 목표높이 / inkH`. 자릿들을
  자연 advance×s 로 좌→우 배치, 전체를 **중심 x 에 가운데정렬**, 세로는 ink 중심이 **중심 y**
  에 오게 baseline = `center_y - ((yMin+yMax)/2)*s`.
- **이름**: scale `= em_pt/upm`(em_pt=136.40). 음절을 **피치 195.4** 간격으로, baseline 고정,
  **중심 x 가운데정렬**. (원본은 음절 사이 공백+Tc로 자간을 줌 → 피치로 재현)
- cowork 검증: 동일 값(20/김경원)으로 렌더 후 완성본에 오버레이 → 이름 거의 정확 일치,
  번호는 높이·중심 일치하나 미세 오프셋(아웃라인 원본과 폰트 미세차). **번호 세로중심·폭 미세
  조정 여지 있음** — CLI 구현 후 cowork에서 오버레이 재검증 권장.

---

## 5. 구현 작업 (Phase B~E)

### Phase B — 정밀 배치 + reference 모듈/CLI
- `engine/text.py` 에 **정밀 배치 함수 추가**(기존 `render_text_ops` 는 유지):
  `place_number(text, font, cap_h_pt, center_x, center_y, color)` /
  `place_name(text, font, em_pt, pitch_pt, baseline_y, center_x, color)` → (ops, warnings).
  4번 공식 그대로. ascii ops, CMYK `k` fill, q…Q 래핑(기존 규약).
- `engine/reference.py` 보강 + `engine reference --완성본 R.ai --템플릿 T.ai [--json out]`:
  완성본에서 앞/뒤 번호(흰색 채움, w 100~700·h 250~900, CTM 추적, 페이지 절반으로 앞/뒤
  분할)와 이름(fitz rawdict: size·font·bbox·중심·baseline·음절피치) 추출 →
  preset area JSON 초안 출력. (가능하면 템플릿과 diff 로 정확도↑, 1차는 완성본 단독 추출 OK)

### Phase C — preset 스키마 확장 + job 통합
- preset.json 에 영역 추가(예):
```json
"front_number_area": {"center":[1389,4184], "cap_height":310, "color_cmyk":[0,0,0,0], "font":"data/fonts/HY헤드라인M.ttf"},
"back_number_area":  {"center":[3217,4342], "cap_height":539, "color_cmyk":[0,0,0,0], "font":"data/fonts/HY헤드라인M.ttf"},
"back_name_area":    {"center_x":3219.8, "baseline":4765.7, "em_pt":136.40, "pitch":195.4, "color_cmyk":[0,0,0,0], "font":"data/fonts/HY헤드라인M.ttf"}
```
- `engine/job.py` 확장(불변 제약 지키며): **base 디자인 = 빈 템플릿**, 시작 시 **flatten 선적용**
  (`flatten_transparency`), 각 선수마다 place_number(앞)·place_number(뒤)·place_name → 페이지
  콘텐츠에 주입(=compose 의 extra_ops 경로 재사용 또는 동급) → verify_output → 선수별 PDF.
  앞·뒤 번호는 같은 배번. split per_player/single 기존대로.
- 투명도 평탄화 파라미터(검증값): GS ca/CA 0.2→1.0, 엠블럼 Fm0 흰색(0,0,0,0)→배경합성
  (bg=CMYK 0.8,0.5,0,0.1, α=0.2 → `0.64 0.4 0 0.08`). `flatten.py` 가 배경 자동감지(면적최대
  불투명 채움)하므로 보통 인자 불필요.

### Phase D — V넥 preset + 패턴
- 패턴 원본: `G:\공유 드라이브\디자인\2026 커스텀용 패턴\0. 농구유니폼 확정 정리본`
  (단면/양면·U넥/V넥·스탠다드/슬림·암홀O/X, 사이즈별 .ai). 이 완성본은 **V넥 스탠다드 계열**.
- 사이즈별 .ai → SVG 변환(기존 grader 의 AI→SVG 헤더검사 로직 참고: `%PDF-` 는 PyMuPDF
  `get_svg_image(text_as_path=True)`, `%!PS-` 는 제외/별도) → preset.sizes 매핑.
- design_region_pt(앞판/뒤판/소매 영역)은 V넥 완성본 좌표로 산출(U넥 preset 구조 참고).

### Phase E — 전체 검증
- 실패턴 + 빈 템플릿 + 주문서로 전 사이즈×전 선수 PDF 생성, 모든 출력 verify PASS,
  CLI 한 줄 재현. 결과 PDF 1~2개를 cowork로 보내 시각 정합 최종확인.

---

## 6. 불변 제약 (반드시 준수)
- engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) **시그니처·
  동작 무수정**(신규 인자는 기본값 확장만). build_layouts/grade 도 무수정.
- device CMYK 무손실, 글자에 이미지(Do)·투명도(ca/CA)·RGB 금지(`k` fill만).
- 빌드0(순수 Python), 폴더+JSON 저장, 각 단계 **CLI 한 줄 단독 검증** 가능.

## 7. 완료 기준
1) `python -m engine selftest` PASS(회귀 0).
2) `python -m engine reference --완성본 … --템플릿 …` 가 4번 수치에 근접한 area JSON 출력.
3) `python -m engine job --preset V넥preset --design 빈템플릿 --order 주문서.xlsx --out …`
   가 선수별 PDF 생성 + 전부 verify PASS.
4) 산출 PDF의 번호·이름이 완성본과 크기·위치·자간 일치(cowork 오버레이 재검증).

## 8. 참고 파일 (저장소 내)
- `계획서-완성본기준-템플릿주입.md` (설계 전반)
- `engine/reference.py`, `engine/text.py`(수정본), `engine/flatten.py`, `engine/job.py`
- 테스트 입력(예): 완성본/빈템플릿 .ai, `data/fonts/HY헤드라인M.ttf`
