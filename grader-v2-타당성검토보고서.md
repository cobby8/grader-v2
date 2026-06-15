# grader-v2 기술 타당성 검토 보고서

> 검토 대상: `DESIGN.md` — 스티즈 전사유니폼 출력 자동화 (grader-v2)
> 작성: planner-architect | 작성일: 2026-06-10
> 검토 방식: 설계서 정독 + 다중 출처 웹 리서치(일차 문서 우선) + 유사 상용 솔루션 비교

---

## 1. 요약 (Executive Summary)

**종합 판정: "충분히 실현 가능하다. 단, '벡터 CMYK EPS 출력 품질'이 전체 성공의 80%를 좌우하는 단일 핵심 관건이며, 여기서 설계서가 가장 큰 리스크를 과소평가하고 있다."**

쉽게 비유하면, 이 프로젝트는 **"엑셀 명단을 넣으면 자동으로 전 사이즈·전 선수 인쇄판을 찍어내는 자판기"**를 만드는 일입니다. 자판기의 뼈대(웹 서버, 엑셀 읽기, 미리보기, 파일 관리)는 검증된 부품들로 안정적으로 조립됩니다. 문제는 **자판기가 마지막에 뱉어내는 "인쇄판(EPS)"이 공장 기계에서 일러스트레이터로 만든 것과 똑같이 나오느냐**입니다.

- **구현 가능성: 높음 (★★★★☆)** — 제안된 모든 기술(FastAPI, pikepdf, PyMuPDF, fontTools, openpyxl, ezdxf)은 실존하고 문서화가 잘 되어 있으며, 각자 맡은 역할에 적합합니다. 바이브 코더가 다루기에도 무난한 난이도입니다.
- **정상 작동 가능성: 조건부 가능 (★★★☆☆)** — 핵심 변환기인 **Ghostscript eps2write는 "벡터·CMYK 보존"을 공식 목표로 하지만, 결과물의 내부 구조가 원본과 달라질 수 있고("the actual insides may differ"), 투명도가 1%라도 섞이면 페이지 전체를 그림(비트맵)으로 굽어버리는** 명확한 한계가 일차 문서에 적혀 있습니다. 이 한 가지가 통제되느냐가 합격/불합격을 가릅니다.
- **결정적 강점:** 설계서가 가리키는 길은 이미 **VPersonalize**라는 상용 솔루션이 같은 원리(엑셀 로스터 → 단일 디자인 → 사이즈 그레이딩 → 네스팅 → 벡터/CMYK 출력 → RIP 연동)로 상용화에 성공한, **검증된 길**입니다. "되는 일을 작게 만드는 것"이므로 방향 자체는 옳습니다.

핵심 권고: **Phase 1의 "공장 시험 인쇄 1회 승인"을 절대 건너뛰지 말 것.** 설계서는 이를 이미 포함하고 있으며, 이것이 가장 잘한 판단입니다.

---

## 2. 설계 개요 정리

**무엇을 만드는가.** grader-v2는 스티즈가 전사(轉寫, sublimation)로 유니폼을 제작할 때, 디자이너가 만든 **기준 사이즈 디자인 1개**만 가지고 **전 사이즈 × 전 선수**의 공장 출력용 파일(벡터 CMYK EPS)을 자동 생성하는 사내 웹 도구입니다. 핵심 목표는 **"출력 과정에서 일러스트레이터를 완전히 배제"**하는 것입니다 — 디자인은 일러로 하되, 사이즈 늘리기·이름/배번 넣기·출력 파일 만들기는 사람 손을 떼고 자동화합니다.

**어떻게 만드는가.** 형태는 **중앙 서버 웹앱**입니다. 사무실 PC 한 대(또는 클라우드 VM)에 서버를 띄우고, 직원은 브라우저로 접속만 하면 됩니다. Python과 Ghostscript는 그 한 대에만 깔립니다. 기술 스택은 전부 Python 생태계로 통일했고(FastAPI + vanilla JS + pikepdf + Ghostscript + PyMuPDF + fontTools + openpyxl + ezdxf), **빌드 단계가 0이며 데이터베이스 없이 폴더+JSON으로** 저장합니다. 이는 기존 grader가 "Rust+Node+Python 3중 빌드체인, 자동업데이트 시스템"으로 복잡도에 무너진 경험에서 의도적으로 후퇴한, 현명한 단순화입니다.

**처리 흐름(파이프라인).** 웹과 분리된 순수 Python `engine/`이 6단계로 일합니다: ① `pattern.py`(SVG/DXF → 조각 윤곽) → ② `order.py`(엑셀 → 주문 행) → ③ `compose.py`(pikepdf로 빈 CMYK 페이지에 조각별 클리핑·스케일·디자인 합성) → ④ `text.py`(fontTools로 이름·배번을 벡터 경로로) → ⑤ `eps.py`(Ghostscript eps2write 변환 + 자동 검증) → ⑥ `preview.py`(PyMuPDF로 검수용 PNG). 각 모듈은 웹 없이 커맨드라인으로 단독 테스트가 가능하도록 설계되어 있습니다.

**리스크 인식 수준.** 설계서는 "일러 출력물과 미세 차이", "서버 PC 장애", "패턴 양식별 조각 분류 차이", "폰트 라이선스" 4가지를 리스크로 적었고, 특히 **투명도→EPS 래스터화 문제를 인지하고 업로드 시 스캔·경고하는 안전장치**까지 설계에 넣었습니다. 리스크 감수성은 상당히 높은 편입니다. 다만 후술하듯 **eps2write의 구조적 한계와 색 관리(ICC/CMYK 프로파일) 부분은 과소평가**되어 있습니다.

---

## 3. 기술별 타당성 분석

각 핵심 기술을 [근거 사례 / 검증된 점 / 한계·주의점 / 판정] 형식으로 정리합니다. (검증된 사실과 추정을 구분 표기)

### 3-1. Ghostscript eps2write (EPS 변환) — ⚠️ 가장 중요한 모듈

> **비유:** "원고를 다른 출판사 양식으로 다시 조판해주는 번역 식자공"입니다. 글 내용(벡터·색)은 보존하려 하지만, 조판을 처음부터 다시 짜기 때문에 "겉보기는 같아도 속 구조는 다른" 결과가 나옵니다.

- **근거 사례 (검증됨):** Ghostscript 공식 문서가 "high level devices는 그림으로 굽지 않고 원시 명령을 다시 고수준 페이지 기술로 재조립한다(reassemble the primitives back into high level page description)"고 명시 — **벡터 보존이 설계 목표임은 사실.** Separation/DeviceN 색공간도 "가능하면 보존"합니다. ([Ghostscript High Level Devices](https://ghostscript.readthedocs.io/en/latest/VectorDevices.html))
- **검증된 점:** CMYK device color는 표현 가능하고, EPS는 단일 페이지·DSC 준수 형태로 출력됩니다. 설계서의 "PoC에서 벡터·CMYK 보존 검증 완료"는 단순한 디자인에서는 사실일 가능성이 높습니다.
- **한계·주의점 (검증됨 — 설계서가 과소평가):**
  1. **투명도 = 즉시 래스터화.** 문서 원문: *"If the input contains PDF-compatible transparency... the transparency cannot be preserved. In this case the entire page is rendered to a bitmap"* — 투명도가 있으면 **그 페이지 전체가 벡터가 아닌 그림으로 변환**됩니다. (설계서의 투명도 스캔 안전장치는 이 때문에 **반드시 필요**하며, 옳은 판단입니다.)
  2. **"속 구조가 달라진다."** 문서 원문: 결과물은 "visually the same"을 목표로 하나 *"the actual insides may differ"* — 즉 시각적으로 같아 보여도 곡선·폰트·패스가 재조립되어 미세 차이가 생길 수 있음.
  3. **ICC 기반 색 보존 불가.** *"ICCbased colors cannot be represented in PostScript"* — 일러스트레이터가 ICC 프로파일로 관리하던 색은 EPS에서 device CMYK로 변환되며, **색 수치가 미묘하게 바뀔 수 있음.** (설계서에 색 관리 언급 없음 → 누락 리스크)
  4. **호환성/압축 이슈.** 일부 EPS 소비 프로그램이 eps2write의 압축 출력을 못 읽는 사례, 과거 유니코드 폰트 처리 버그 등 현장 잡음이 보고됨. ([gs-bugs Bug 695503](https://gs-bugs.ghostscript.narkive.com/sWERfogq/bug-695503-new-problem-with-using-eps-files-generated-with-eps2write-in-latex), [Ghostscript bug 690012](https://bugs.ghostscript.com/show_bug.cgi?id=690012))
- **판정:** **구현 가능, 그러나 "품질 보증"은 공장 실측으로만 확정 가능.** 이 모듈이 전체의 성패를 쥐고 있습니다. 단순·평탄화된 디자인이라면 합격 가능성이 높지만, 그라데이션·투명·복잡 효과가 들어간 디자인은 래스터화/색변동 위험이 큽니다.

### 3-2. pikepdf (PDF 합성·클리핑·스케일) — ✅ 적합

> **비유:** "큰 도화지(CMYK 빈 페이지) 위에 디자인 그림을 정확한 자리에 오려 붙이는 풀과 가위." 그림 자체를 다시 그리지 않고 **원본을 그대로 얹기** 때문에 손실이 없습니다.

- **근거 사례 (검증됨):** pikepdf 공식 문서가 `add_overlay()`, `as_form_xobject()`, `calc_form_xobject_placement()`로 페이지를 다른 페이지 위에 합성하는 표준 방법을 제공. 합성은 **Form XObject** 방식으로 이뤄져 벡터 내용이 유지됩니다. ([pikepdf Overlays](https://pikepdf.readthedocs.io/en/latest/topics/overlays.html))
- **검증된 점:** 위치·스케일·종횡비 제어가 명시적으로 지원되고, `push_stack` 옵션으로 변환 행렬 초기화도 통제 가능. 설계서의 "클리핑 W n → 스케일 cm → 디자인 인라인"은 PDF 연산자 수준의 정공법으로, pikepdf로 충분히 구현 가능.
- **한계·주의점:** pikepdf는 **벡터 "추출"은 못 합니다.** 그러나 이 설계는 추출이 아니라 **원본 디자인을 통째로 얹는(합성)** 방식이므로 해당 한계에 걸리지 않습니다 — 오히려 가장 안전한 사용법입니다. 다만 "기본 PDF 소프트웨어가 Form XObject 내부 이미지를 못 볼 수 있다"는 경고가 있어, **최종 EPS는 반드시 공장과 같은 RIP에서 확인** 필요. ([pikepdf content streams](https://pikepdf.readthedocs.io/en/latest/api/filters.html))
- **판정:** **적합·저위험.** 이 모듈은 가장 안정적인 부분입니다.

### 3-3. fontTools (이름·배번 → 벡터 아웃라인) — ✅ 적합

> **비유:** "글자를 폰트가 아니라 '그림(도형)'으로 바꿔 박는 것." 공장에 폰트 파일을 안 보내도 글자가 깨지지 않습니다(아웃라인화).

- **근거 사례 (검증됨):** fontTools `pens`(특히 `SVGPathPen`)가 글리프 윤곽을 베지어 세그먼트 단위로 정확히 추출해 벡터 경로(SVG path `d` 명령)로 변환. 글리프 데이터의 저장 형식과 1:1 대응. ([fontTools pens](https://fonttools.readthedocs.io/en/latest/pens/index.html), [svgPathPen](https://fonttools.readthedocs.io/en/latest/pens/svgPathPen.html))
- **검증된 점:** 폰트 임베드 불필요 → 공장 호환 안전. 설계서의 "글리프→벡터 경로 후 CMYK fill" 접근은 표준적·정확.
- **한계·주의점 (추정 포함):** ① 합자(ligature)·커닝·복합 스크립트는 직접 처리해야 함(한글 이름이면 자모 결합·고급 OpenType 기능 주의). ② glyph 좌표는 폰트의 unitsPerEm 기준이므로 **mm 단위 배치로 변환하는 스케일 계산을 정확히** 해야 함(치수 정확도 직결). 단순 영문/숫자 배번이라면 위험 낮음.
- **판정:** **적합.** 영문 이름·숫자 배번 중심이면 저위험. 한글·특수 글리프가 들어가면 테스트 케이스를 늘릴 것.

### 3-4. PyMuPDF (미리보기 PNG 렌더) — ✅ 적합

- **근거 사례 (검증됨):** `page.get_pixmap(dpi=300)` 또는 `Matrix(dpi/72, dpi/72)`로 임의 해상도 PNG 렌더 가능. 기본 96dpi, 고해상도 지원. ([PyMuPDF Images](https://pymupdf.readthedocs.io/en/latest/recipes-images.html))
- **한계·주의점:** **미리보기는 검수용일 뿐, 공장 출력물의 색을 보장하지 않습니다.** PyMuPDF는 화면용 RGB 렌더이므로 **CMYK 색감과 다를 수 있음** — 직원이 "화면에서 예뻐 보였는데 공장 색이 다르다"고 오해할 여지. 미리보기 화면에 "색은 참고용, 실제 출력색은 공장 기준" 안내 권장.
- **판정:** **적합.** 단, 색 검수 용도로 과신하지 말 것.

### 3-5. xml(SVG) + ezdxf(DXF) (패턴 파싱) — ✅ 적합, 일부 주의

> **비유:** "재단 본(패턴)의 외곽선 좌표를 읽어들이는 스캐너." 본의 종류(SVG/DXF)에 따라 읽는 방식만 다릅니다.

- **근거 사례 (검증됨):** ezdxf가 LWPOLYLINE/POLYLINE 정점, bulge(호) 처리, 가상 DXF 프리미티브 변환까지 지원 — 의류 CAD 패턴 외곽 추출에 표준적. SVG는 표준 XML 파싱으로 path/polygon 좌표 추출 가능. ([ezdxf LWPolyline](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html))
- **한계·주의점 (검증됨):** DXF의 **SPLINE/ARC/BULGE를 점 목록으로 평탄화(flatten)할 때 곡선 근사 정밀도** 문제 — 너무 거칠면 곡선이 각져 보이고, 너무 촘촘하면 파일이 무거워짐. SVG는 `transform`/`viewBox`/단위(px vs mm) 해석을 정확히 해야 치수가 맞음. 설계서가 "preset.json에 조각 정의를 명시(자동 분류 의존 최소화)"한 것은 이 변동성을 줄이는 좋은 대응.
- **판정:** **적합.** 곡선 평탄화 정밀도와 단위 변환을 초기에 못 박을 것.

### 3-6. openpyxl (주문서 인식) — ✅ 적합, 검증된 경험 보유

- **근거 사례:** 설계서가 기존 `order_parser.py`에서 "셀 전체 스캔(가로형/세로형/표형)", "사이즈 키워드 긴 것부터 매칭", "Custom Properties 버그 워크어라운드"를 이미 실전 검증. openpyxl은 .xlsx 표준 라이브러리.
- **한계·주의점 (추정):** **병합 셀, .xls(구형), 수식 결과값, 빈 행/머리글 변형**이 현장 주문서마다 제각각 — Phase 3의 "실제 주문서 3종 검증"으로 커버해야 함. 자동 추출 후 **반드시 표로 확인/수정** 단계를 둔 설계는 옳음.
- **판정:** **적합·저위험** (이식할 실전 지식 보유가 강점).

### 3-7. FastAPI + vanilla JS + 폴더/JSON(무DB) — ✅ 적합

- **근거 사례 (검증됨):** FastAPI+Uvicorn은 소규모 사내 도구·단일 서버·JSON 응답에 적합하다는 것이 일반적 합의. 페이지 3개·동시 사용자 소수 규모에서 DB 없이 폴더+JSON으로 충분. ([FastAPI](https://github.com/fastapi/fastapi), [FastAPI 배포 가이드](https://www.zestminds.com/blog/fastapi-deployment-guide/))
- **한계·주의점:** ① **동시 쓰기 충돌** — 두 직원이 동시에 같은 job.json을 수정하면 깨질 수 있음(소수 사용자라 위험 낮으나 파일 잠금/원자적 쓰기 권장). ② EPS 생성은 CPU 무거운 작업 → **동기 처리로 막으면 서버가 멈춘 듯 보임.** 백그라운드 작업(BackgroundTasks/별도 워커)으로 빼고 진행률 표시 필요. ③ 백업=폴더 복사는 단순하나 **자동 백업 스케줄**은 별도로 챙길 것.
- **판정:** **적합.** 규모에 맞는 합리적 선택. 무DB는 이 단계에선 단점보다 장점이 큼.

---

## 4. 유사 프로그램·사례 비교

설계의 접근법이 "발명"이 아니라 **이미 상용화된 검증된 패턴**임을 보여주는 사례들입니다.

| 솔루션 | 접근법 | grader-v2와의 공통점 | grader-v2가 다른/단순화한 점 | 출처 |
|--------|--------|------------------|------------------------|------|
| **VPersonalize** (자동 패턴 생성) | 엑셀 로스터 업로드 → 디자인 → **사이즈 그레이딩 → 네스팅 → 벡터 PDF/AI(CMYK·PMS) 출력 → RIP(Ergosoft/Caldera/Onyx) 연동** | **거의 동일한 철학.** 단일 디자인→전 사이즈, 엑셀 명단 자동화, 이름/배번 그레이딩, CMYK 벡터 출력 | grader-v2는 네스팅·다중 그레이딩 방법론·클라우드 SaaS 없이 **사내 필요분만** 구현(의도적 단순화). 출력은 EPS 단일 | [vPersonalize 자동 패턴 생성](https://www.vpersonalize.com/automated-pattern-generation.html), [vPersonalize 메인](https://www.vpersonalize.com/) |
| **LiveArt Uniform Design Tool** | 웹 디자이너 + Names & Numbers 툴(승화/스크린/DTG/자수 호환) | 이름·배번 자동 배치 개념 | 디자인 *제작* 툴 중심(스티즈는 디자인을 일러로 끝내고 *출력만* 자동화) | [LiveArt](https://www.liveartdesigner.com/uniform-design-tool) |
| **ImprintNext / Goal Sublimation SW** | 고객 셀프 디자인 + 이름/번호 커스터마이즈 | 변수 데이터(이름·번호) | B2C 셀프 디자인 지향, 공장 출력 자동화는 약함 | [ImprintNext](https://imprintnext.com/sublimation-jersey-software) |
| **ErgoSoft / Wasatch SoftRIP / CADLink Digital Factory** (RIP) | 색관리(ICC)·네스팅·step&repeat·**variable data·hot folder 자동화** | 변수 데이터·자동화 워크플로우 개념 | grader-v2는 RIP 자리를 대체하지 않고 **그 앞단(출력 파일 생성)만** 담당 → RIP과 공존 | [ErgoSoft Roland Edition](https://global.rolanddg.com/products/software/ergosoft-roland-edition-rip-software), [Wasatch](https://wasatch.com/), [CADLink Digital Factory](https://www.graphicsone.com/product/cadlink-digital-factory-rip-software-dye-sublimation-edition/) |

**핵심 시사점 3가지:**
1. **방향이 옳다.** VPersonalize가 똑같은 원리로 상용화에 성공 → grader-v2는 "되는 것을 작게 만드는" 프로젝트이지, 검증 안 된 모험이 아닙니다.
2. **상용 솔루션은 출력을 "벡터 PDF/AI 또는 래스터 TIFF"로 내고, 색은 ICC/PMS로 관리합니다.** grader-v2가 **EPS 단일·ICC 미언급**인 점은 잠재적 약점 — VPersonalize조차 CMYK뿐 아니라 PMS/PANTONE·ICC를 챙깁니다. (4-색 관리 보강 필요 신호)
3. **상용은 RIP에 의존합니다.** grader-v2의 EPS가 결국 들어갈 곳도 공장 RIP이므로, **"우리 EPS가 공장 RIP에서 어떻게 해석되는가"가 진짜 합격 기준** — 화면 미리보기가 아니라.

---

## 5. 구현 가능성 종합 평가

### 모듈별

| 모듈 | 구현 난이도 | 리스크 | 평가 |
|------|-----------|--------|------|
| `order.py` (엑셀) | 낮음 | 낮음 | 실전 지식 이식 → 가장 쉬움 |
| `preview.py` (PNG) | 낮음 | 낮음 | API 호출 수준 |
| `compose.py` (pikepdf 합성) | 중간 | 낮음 | 정공법, 문서 풍부. 좌표·스케일 계산이 일거리 |
| `pattern.py` (SVG/DXF) | 중간 | 중간 | 곡선 평탄화·단위 변환 정밀도 필요 |
| `text.py` (fontTools) | 중간 | 중간 | 영문/숫자면 쉬움, 한글이면 케이스↑ |
| `eps.py` (Ghostscript) | 중간 | **높음** | **구현은 호출 수준이나 "품질"이 외부 요인(공장)에 달림** |
| 웹 UI(FastAPI+JS) | 중간 | 중간 | 비동기·진행률·동시성 처리가 변수 |

### Phase별

- **Phase 0~1 (engine + EPS + 공장 시험인쇄):** 여기가 **진짜 분수령.** Phase 1의 "공장 시험 인쇄 승인"을 통과하면 나머지는 사실상 "껍데기 씌우기"입니다. **자원의 60%를 여기 쏟을 것.**
- **Phase 2~3 (웹 UI + 주문서/배번):** 검증된 부품 조립. 동시성·진행률·UX가 관건이나 난이도는 중하.
- **Phase 4 (패턴 관리 UI):** 드래그로 배번/이름 영역 지정하는 UI가 가장 손이 많이 가는 프론트엔드 작업. 기능적 위험은 낮음.
- **Phase 5 (클라우드):** 설계대로 "코드 동일, 인프라만 변경"이 무DB·정적 자산 구조 덕에 실제로 수월. 단 동시 사용자↑ 시 파일잠금→DB 전환 필요 가능.

**종합: 구현 가능성 높음.** 단계 독립성·engine 분리·CLI 테스트 원칙이 잘 잡혀 있어 바이브 코딩으로 점진 진행하기에 이상적인 구조입니다.

---

## 6. 정상 작동 가능성 종합 평가 (출력 품질 관점)

"일러스트레이터 출력물 수준으로 안정적으로 나오는가?"를 3축으로 봅니다.

### (A) 벡터 보존 — 조건부 ★★★☆☆
- pikepdf 합성 단계까지는 **완전 벡터 보존**(원본을 통째로 얹으므로 무손실).
- **eps2write 변환 단계에서 위험.** 벡터 보존이 목표지만 "속 구조 재조립", 그리고 **투명도 1%라도 있으면 페이지 전체 래스터화.** → **디자인 평탄화(flatten)를 강제하는 워크플로우가 사실상 필수.** 설계의 투명도 스캔·경고는 옳으나, "경고 후 진행 여부 선택"은 약함 → **투명도 발견 시 진행 차단(또는 자동 평탄화)을 기본값으로 권장.**

### (B) 색 정확도 (CMYK) — 미흡 ★★☆☆☆ (설계 보강 필요)
- device CMYK는 보존되나 **ICC 기반 색은 보존 불가** → 일러에서 ICC로 보던 색과 EPS 색이 어긋날 수 있음.
- 설계서에 **색 관리(ICC 프로파일, PMS/별색) 전략이 전혀 없음.** 상용 솔루션(VPersonalize, ErgoSoft 등)은 모두 ICC/PMS를 챙깁니다.
- **권고:** ① 디자인 입력을 처음부터 **device CMYK로 통일**(ICC 의존 제거), ② 별색(PMS)이 필요한 종목 유니폼이 있는지 확인, ③ Phase 1 시험인쇄에서 **색 표(컬러 차트) 동봉 비교.**

### (C) 치수 정확도 — 양호 ★★★★☆
- 설계의 "단순 비례 스케일 + 클리핑이 업계 허용 오차 내"(decisions 2026-04-08)는 검증된 전제. pikepdf의 cm(행렬) 연산은 수학적으로 정확.
- 변수: **패턴 곡선 평탄화 거칠기, fontTools 글리프→mm 스케일, SVG 단위 해석.** 이들만 못 박으면 치수는 안정적. **전사는 원단 수축(shrink)이 있는데 설계에 수축 보정 언급 없음** — VPersonalize는 "fabric shrink management"를 핵심 기능으로 둠. (누락 리스크, 7장 참조)

**종합 판정:** **"단순·평탄화된 device-CMYK 디자인"이라면 일러 수준 출력이 안정적으로 가능. 그러나 투명도·ICC색·원단수축 3가지가 통제되지 않으면 품질이 흔들린다.** 합격 여부는 **Phase 1 공장 시험 인쇄로만 최종 확정** 가능하며, 설계가 이를 포함한 것이 가장 큰 안전판입니다.

---

## 7. 추가 리스크 및 권고사항 (설계서가 놓쳤거나 과소평가한 부분)

1. **🔴 원단 수축(shrink) 보정 누락.** 전사는 열압착 시 원단이 수축합니다. 상용 솔루션은 이를 핵심 기능으로 둠. → **사이즈별/원단별 수축률 보정 계수를 preset.json에 추가** 권고. (없으면 큰 사이즈에서 치수 오차 누적)
2. **🔴 색 관리(ICC/PMS) 전략 부재.** 6-(B) 참조. → **device CMYK 통일 + 별색 필요성 확인 + 컬러차트 시험인쇄.**
3. **🟡 투명도 경고가 약함.** "진행 여부 선택"보다 **차단/자동 평탄화 기본값**으로. 평탄화 자동화는 Ghostscript `pdfwrite`로도 일부 가능하나 품질 보장은 어려움 → 디자이너 단계 평탄화 규칙(SOP) 병행.
4. **🟡 EPS RIP 호환성 미검증.** eps2write의 압축·encapsulation 호환 잡음 보고됨 → **공장 RIP에서 직접 import 테스트**를 Phase 1 체크리스트에 명시(미리보기 PNG 통과 ≠ RIP 통과).
5. **🟡 폰트 라이선스 — 아웃라인화도 100% 면제 아님.** 설계는 "부담 적음"이라 했으나, 일부 상용 폰트는 **아웃라인(임베드 변환)도 라이선스로 제한**합니다. → 배번/이름용 폰트는 **임베드+에디터블 라이선스가 명확한 폰트(또는 OFL 폰트)**로 한정 권고.
6. **🟡 동시성/원자적 쓰기.** 다중 직원 동시 작업 시 JSON 깨짐 가능 → **임시파일 쓰고 rename(원자적 교체)** 패턴, 작업 잠금.
7. **🟡 긴 작업 UX.** EPS 일괄 생성은 수십 초~분 → **백그라운드 작업 + 실시간 진행률 + 부분 실패 처리**(한 선수 실패가 전체를 막지 않게).
8. **🟢 한글 글리프 테스트.** 선수 이름이 한글이면 fontTools 글리프 결합·세로/긴 이름 레이아웃 케이스 확대.

### 더 나은 대안 기술 검토
- **eps2write 대안:** 공장이 **PDF/X 또는 AI 호환 PDF**를 받을 수 있다면, **EPS 대신 PDF로 출력**하면 투명도·색 관리가 훨씬 안정적입니다(EPS는 1990년대 포맷, 투명도 미지원이 근본 한계). → **"공장이 정말 EPS만 받는가?"를 먼저 확인**하고, PDF 허용 시 `pdfwrite`/직접 PDF 출력으로 전환하면 6장의 위험 다수가 해소됩니다. **이것이 가장 큰 단일 개선 제안입니다.**
- 그 외 스택은 현 선택이 규모·난이도에 잘 맞아 교체 권고 없음.

---

## 8. 최종 결론

**진행 권고: 예 (조건부 GO).** 설계 방향은 상용 사례(VPersonalize)로 검증된 옳은 길이고, 기술 스택은 전부 실존·적합·바이브 코딩 친화적이며, 단계 독립성과 engine 분리 설계가 견고합니다. "기존 grader의 복잡도를 버리고 핵심만 단순화"한 판단도 정확합니다.

다만 **출력 품질(특히 EPS 변환)이 외부 요인(공장)에 달린 단일 고위험 지점**이므로, 무작정 전체를 만들기 전에 **Phase 0~1의 품질 검증부터 끝내는 순서**를 반드시 지켜야 합니다.

### 핵심 성공 조건 3가지
1. **출력 포맷을 먼저 확정하라 — "공장이 EPS만 받는가, PDF도 되는가?"** PDF가 가능하면 EPS의 투명도·색 한계 대부분이 사라집니다. (가장 먼저 확인할 것)
2. **Phase 1 "공장 시험 인쇄 승인"을 절대 생략하지 말고, 색 차트·투명/그라데이션 디자인·전 사이즈를 포함한 까다로운 케이스로 테스트하라.** 미리보기 PNG 통과는 합격이 아니다 — **공장 RIP 통과가 합격이다.**
3. **입력 규칙(SOP)을 못 박아라:** device CMYK 통일 + 투명도 평탄화 필수 + 라이선스 명확한 폰트 + 원단 수축 보정 계수. 출력 자동화의 품질은 **입력 표준화**에서 나온다.

---

### 출처 (Sources)
- [Ghostscript High Level Devices (eps2write/ps2write 공식 문서)](https://ghostscript.readthedocs.io/en/latest/VectorDevices.html)
- [Ghostscript bug 690012 — ps2write 유니코드 폰트 오류](https://bugs.ghostscript.com/show_bug.cgi?id=690012)
- [gs-bugs Bug 695503 — eps2write EPS 호환 문제](https://gs-bugs.ghostscript.narkive.com/sWERfogq/bug-695503-new-problem-with-using-eps-files-generated-with-eps2write-in-latex)
- [pikepdf Overlays/Form XObject 문서](https://pikepdf.readthedocs.io/en/latest/topics/overlays.html)
- [pikepdf Content streams 문서](https://pikepdf.readthedocs.io/en/latest/api/filters.html)
- [fontTools pens 문서](https://fonttools.readthedocs.io/en/latest/pens/index.html)
- [fontTools svgPathPen](https://fonttools.readthedocs.io/en/latest/pens/svgPathPen.html)
- [PyMuPDF Images/렌더 문서](https://pymupdf.readthedocs.io/en/latest/recipes-images.html)
- [ezdxf LWPolyline 문서](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html)
- [FastAPI (공식 GitHub)](https://github.com/fastapi/fastapi)
- [FastAPI 배포 가이드 2026](https://www.zestminds.com/blog/fastapi-deployment-guide/)
- [vPersonalize 자동 패턴 생성](https://www.vpersonalize.com/automated-pattern-generation.html)
- [vPersonalize 메인](https://www.vpersonalize.com/)
- [LiveArt Uniform Design Tool](https://www.liveartdesigner.com/uniform-design-tool)
- [ImprintNext Sublimation Jersey Software](https://imprintnext.com/sublimation-jersey-software)
- [ErgoSoft Roland DG Edition RIP](https://global.rolanddg.com/products/software/ergosoft-roland-edition-rip-software)
- [Wasatch SoftRIP](https://wasatch.com/)
- [CADLink Digital Factory RIP](https://www.graphicsone.com/product/cadlink-digital-factory-rip-software-dye-sublimation-edition/)
- [Adobe — Transparency flattening](https://helpx.adobe.com/acrobat/using/transparency-flattening-acrobat-pro.html)
- [PDF Association — 20 years of transparency in PDF](https://pdfa.org/20-years-of-transparency-in-pdf/)

> 검증 구분 안내: 본문에서 "(검증됨)"은 일차 문서·공식 출처로 확인한 사실, "(추정)"은 일반적 기술 지식에 근거한 합리적 추론입니다. 출력 품질의 최종 합격 여부는 **실제 공장 시험 인쇄로만** 확정 가능합니다.
