# grader-v2 — 정적 화면 핸드오프 (코워크 전달용)

스티즈 전사유니폼 출력 자동화 웹앱의 **UI 화면 3개 + 문서 2개**를 프레임워크·빌드
없이 동작하는 순수 HTML / CSS / vanilla JS로 만든 패키지입니다. CLI 구현자가
FastAPI 정적 파일로 그대로 마운트해 백엔드에 붙일 수 있습니다.

작성: 디자인 클로드 · 2026-06-15

---

## 폴더 구조

```
grader-v2-static/
├─ README.md                  ← 이 파일
├─ styles.css                 ← 디자인 시스템 토큰 진입점(@import 매니페스트)
├─ tokens/                    ← 색·타이포·간격·반경·그림자·폰트 변수
│  ├─ colors.css  typography.css  spacing.css  base.css  fonts.css
├─ assets/logos/              ← STIZ 로고 · 파비콘
└─ screens/
   ├─ index.html              ← 런처(여기서 시작). 화면 링크 + 결합 안내
   ├─ app.css                 ← 모든 컴포넌트 클래스(버튼·배지·드롭존·표·모달·스위치…)
   ├─ work.html               ← 화면 1 · 작업(메인). 5단계 + 본체검증·대량·검수모달
   ├─ patterns.html           ← 화면 2 · 패턴 관리. 3단계 등록 + 글리프셋·자동추출
   ├─ history.html            ← 화면 3 · 작업 기록. 탭 필터 + 재생성
   ├─ settings.html           ← 화면 4 · 설정. 경로·출력형식·색·서버
   ├─ flow.html               ← UX 플로우 다이어그램(문서)
   ├─ changes.html            ← 2차 변경 요약(문서)
   ├─ navigator.html          ← 전체 화면 탭 네비게이터
   └─ states.html             ← 상태·엣지케이스 명세(문서)
```

> `screens/`의 각 페이지는 `../styles.css` 와 `../assets/logos/` 를 상대경로로
> 참조합니다. **폴더 구조를 그대로 유지**하면 추가 설정 없이 열립니다.

## 외부 의존 (CDN 2개뿐)

- **Pretendard** 가변폰트 — `cdn.jsdelivr.net` (tokens/fonts.css)
- **Material Symbols Outlined** 아이콘 — `fonts.googleapis.com` (각 화면 `<head>`)

사내망이 외부 CDN을 막는다면 두 리소스만 로컬로 받아 경로를 바꾸면 됩니다.
그 외 자바스크립트 의존성은 없습니다.

## FastAPI 마운트 예시

```python
from fastapi.staticfiles import StaticFiles
app.mount("/ui", StaticFiles(directory="grader-v2-static", html=True), name="ui")
# → http://<host>/ui/screens/  에서 런처 확인
```

실제 결합 시에는 `screens/*.html`을 Jinja 템플릿으로 옮기고, 아래 표의
mock 데이터를 서버 응답으로 치환하면 됩니다.

---

## API 결합 지점 (의뢰서 7번 계약과 동일)

각 화면 상단 `<script>`의 mock 배열은 백엔드 응답 모양 그대로입니다.
이 배열만 서버 데이터로 바꾸면 결합됩니다.

| 화면 | mock 변수 (위치) | API 응답(요지) |
|------|------------------|----------------|
| 패턴 선택/목록 | `PATTERNS` (work · patterns) | `[{id, name, sizes[], thumb}]` |
| 디자인 업로드 결과 | work.html `design` 상태 | `{ok, transparency[], colorspace_ok}` |
| 주문 추출 표 | `ORDER` (work) | `{rows:[{size, qty, name, number}]}` |
| 생성 진행률 | `RESULTS` + `tickGenerate()` (work) | `{done, total, state}` |
| 미리보기 그리드 | `RESULTS` (work) | `[{size, name, url, checks:[{name, ok, detail}]}]` |
| 작업 기록 | `JOBS` (history) | `[{id, date, name, pattern, status}]` |

`checks`(무손실·단일 임베드·CMYK 유지·투명도·합성 정확)는 화면에서
**PASS = "전달 가능" / FAIL = "확인 필요"** 배지로 번역해 보여줍니다.

## 구현 시 유지해야 할 UX 규칙

1. **점진적 노출** — 이전 단계가 끝나야 다음 단계 활성화(work.html `canAdvance()`).
2. **투명도 경고는 진행 차단** — 평탄화 전에는 [다음]·[생성] 비활성. 친절하지만 단호하게.
3. **추출 실패 셀 강조 + 인라인 입력 요구** — 붉은 셀은 값이 채워질 때까지 경고.
4. **부분 실패는 전체를 막지 않음** — "46 / 48 전달 가능"처럼 통과분은 받게.
5. **모든 빈 상태/로딩/오류를 설계** — `states.html`에 specimen 정리됨.

## 한글 카피 톤

- 무엇이 문제인지 **+** 어떻게 푸는지를 한 문장에. (예: "투명도가 있어 출력 시
  래스터화됩니다. 원본에서 평탄화 후 재업로드하세요.")
- 전문용어 최소화. 각 단계 "지금 할 일"을 제목으로.
- 경고는 단호하게, 안내는 차분하게.

---

## 디자인 토큰 요약

- **컬러**: STIZ Black `#111111` + STIZ Red(브랜드) + 중립 잉크 스케일 + 의미색
  (성공=전달가능 / 경고=투명도 / 오류 / 정보). `tokens/colors.css`.
- **타이포**: Pretendard. 위계는 `--text-display … --text-caption`. `tokens/typography.css`.
- **간격·반경·그림자·모션**: `tokens/spacing.css`.
- **컴포넌트**: 전부 `screens/app.css`에 클래스로. 변형/상태는 `states.html` 참조.

---

## 2차 변경 요약 (2026-06-15)

1차 위에 **공백 3건**을 채웠습니다. 토큰·기존 컴포넌트는 그대로 재사용했고, 새 컴포넌트는 `screens/app.css`에 추가했습니다.

| # | 기능 | 변경 파일 | 추가 컴포넌트(app.css) |
|---|------|-----------|------------------------|
| ① | **디자인↔조각 매핑** — 패턴 등록을 3단계로 확장(파일 → 디자인 매핑 → 배번/이름). 조각을 고르고 디자인 위에 드래그로 영역 지정. 좌표는 페이지 pt(좌하단 원점)로 환산해 `design_region_pt`로 저장, `content_box`는 합집합 자동 제안. 미매핑 조각 진행 차단. | `patterns.html` | `.region--piece` · `.region--content` · `.piecerow` · `.coord` · `.substep` |
| ② | **검수 상세(줌) 모달** — 검수 그리드 결과 클릭 → 큰 미리보기 + 배번/이름 영역 오버레이 + 검증 항목 리스트(PASS/FAIL·상세) + 단일 다운로드 + ←/→ 이동·Esc 닫기·배경클릭. | `work.html` · `states.html` | `.lightbox` · `.lb` · `.check` |
| ③ | **대량 주문 UX** — 주문표·검수 그리드에 검색(이름/배번)·필터(확인 필요만/탭)·정렬·페이지네이션·고정 헤더·결과 수 요약. 48행 mock으로 시연. | `work.html` · `states.html` | `.toolbar` · `.search` · `.fchip` · `.select` · `.pager` · `.tablewrap--scroll` |

**좌표 환산 규칙 (①, CLI 필독)**: 화면 캔버스는 좌상단 원점, 출력 pt는 좌하단 원점이라 y축이 뒤집힙니다. `work`/`patterns`의 `toPt()`가 `design.page_size_pt`로 환산합니다 — `design_region_pt = [x0, pageH−yBottomScreen, x1, pageH−yTopScreen]`. 검증값은 `data/patterns/농구_U넥_양면/preset.json`과 일치 확인했습니다(앞판 `[470,2880,2101,5289]` ≈ preset `[468,2877,2098,5287]`).

**검수 모달 데이터(②)**: `RESULTS[].checks:[{name, ok, detail}]`를 그대로 항목 리스트로 렌더. `url`은 큰 미리보기 PNG 자리(현재 placeholder). 배번/이름 오버레이는 preset의 `number_area`/`name_area` 좌표를 얹는 자리입니다.

---

## 3차 변경 요약 — 시안보강 (2026-06-20)

운영에서 터진 이슈 6건을 반영. **새 원자 컴포넌트 없음**(조합/기존 컴포넌트 재사용), 브랜드 유지, `static/` + `ui_kits/grader/` + `data.js` 양쪽 반영. 상세는 `screens/changes.html`.

| # | 항목 | 변경 파일 | 비고 |
|---|------|-----------|------|
| 1 | **디자인 본체 누락 실패 케이스** — PDF는 맞지만 본체가 빈 경우 진행 차단. 통과 파일카드 "본체 포함 ✓". | `work.html` · `WorkScreen.jsx` · `states.html` §11 | `alert--fail`/`filecard--fail` 재사용 |
| 2 | **빈 본체 슬롯 명확화 + 베이크 감지** — 드롭존 "빈 본체 템플릿", 번호/이름 베이크 감지 경고. | `work.html` · `WorkScreen.jsx` · `states.html` §11 | 카피만 |
| 3 | **검수: 재단선·너치 + 건너뜀 N건** — 체크리스트 1줄 추가 + 제외 주문 사유 배너. | `work.html` · `WorkScreen.jsx` · `data.js` · `states.html` §12 | `data.js` `checks`·`skipped` |
| 4 | **패턴 등록: 글리프셋 + 자동추출 탭** — 0~9 아웃라인 업로드 슬롯(폴백) + "완성본 자동 추출(권장)/직접 드래그" 탭. | `patterns.html` · `PatternScreen.jsx` · `data.js` · `states.html` §13 | `.seg` 재사용 |
| 5 | **설정 화면 신설** — 경로·출력형식·선수별/PNG·색·서버. 사이드바 '설정' 추가. | `settings.html` · `SettingsScreen.jsx` | `.switch`(forms/Switch 미러)·`.setrow` |
| 6 | **출력 형식 선택 (PDF/EPS/둘 다)** — 설정 Select에 PDF/EPS/PDF+EPS 추가(벡터 중립=기본값), 생성 단계에 형식 세그먼트(주문마다 변경). 둘 다는 ZIP `pdf/`·`eps/` 분리 안내. | `work.html` · `settings.html` · `WorkScreen.jsx` · `flow.html` · `data.js` | localStorage `stiz-grader-output-format` |

**출력 형식 선택(6)**: 출력은 **PDF·EPS 둘 다 지원**, 필요한 걸 선택(둘 다도 가능). 설정 기본값(`localStorage["stiz-grader-output-format"]` = vector/pdf/eps/both)에 더해 **생성 단계의 세그먼트로 주문마다 변경** 가능. 작업 화면의 생성 라벨·검수 ZIP 버튼·단계 설명이 이 값을 읽어 `{형식}`으로 표기하고, `both`일 때 검수에 ZIP `pdf/`·`eps/` 하위폴더 분리 안내 한 줄이 나옵니다. **결합 시** 이 값을 서버 생성 옵션으로 넘기세요. (EPS 평탄화 선결은 엔진이 자동 처리 — 화면은 형식 선택만 노출.)

**본체 검증(1·2)**: `designChecks`에 `body`(본체 포함)·`baked`(베이크 감지) 필드를 두었습니다. 서버 디자인 업로드 응답에 두 불리언을 추가하면 그대로 매핑됩니다.
