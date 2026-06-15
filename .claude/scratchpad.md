# 작업 스크래치패드

## 현재 작업
- **요청**: 코워크 새 의뢰서(A-1 이후 잔여) — 우선순위 재정의. 추천 순서대로 진행 확정.
- **상태**: A-4 구현 중 (설계 승인 완료)
- **현재 담당**: developer
- **A-4 결정 확정(2026-06-15)**: R-A 좌하단 기준 / R-B em중앙 근사 / R-C stroke 1차 제외(fill만) / R-E 검증시 임시검정→흰색복원 / R-F 글리프 누락 시 텍스트 통째 생략+경고 / 결합=Piece.extra_ops 필드 추가(compose 시그니처 불변) / 단독테스트=grade+build_layouts에 number/name 인자 + CLI --number/--name

### 새 우선순위 (의뢰서 2026-06-15, 사용자 "추천순서대로" 승인)
1. **A-4** 배번/이름 렌더 engine/text.py (폰트 확보됨 → 착수) ⬅️ **지금**
2. **A-5** 주문서 파싱 engine/order.py (xlsx→행, 폰트 불필요)
3. **job** 선수별 통합 engine/job.py (주문행×디자인→선수별 출력, A-4·A-5 선행)
4. **A-2** 전 사이즈 (실제 XS~5XL 패턴 파일 사용자 확보 대기 / 설계는 완료됨)
5. **B** 웹앱 FastAPI + web/ 결합

### A-4 재료 (확보 완료)
- 폰트: data/fonts/Pretendard-Black.otf(배번), Pretendard-Bold.otf(이름). 둘 다 한글+숫자+영문, OFL 상업인쇄 가능.
- fontTools 4.63.0 설치 완료(requirements.txt 등재).
- preset number_area(piece_id=back, rel_bbox[0.30,0.35,0.70,0.60], Black, cmyk[0,0,0,0]흰색, center) / name_area(back, rel_bbox[0.25,0.62,0.75,0.74], Bold, 흰색, center) 이미 완비.
- A-4 방식(의뢰서): fontTools 글리프→윤곽→PDF 경로연산자(m/l/c…f) CMYK 단색 fill. 폰트 임베드 X(아웃라인화). verify_output 여전히 PASS(래스터 미추가·CMYK 유지)여야 함.

### A-2 메모 (보류, 설계 완료)
- A-2 코드는 미작성(0%). 설계만 "## 기획설계" 섹션에 보존. R1 piece_id매칭 보류 / R2 종횡비30% / R3 _piece_transform grade.py유지 / R4 바이트동일. 실제 전 사이즈 패턴 파일 확보 시 재개.

### A-2 핵심 변수 (2026-06-15 확인)
- **실데이터에 pattern_XS.svg 1개뿐**. S/M/L/XL/XXL SVG 없음. (config: baseSize=XL디자인 / targetSize=XS패턴)
- → A-2 "전 사이즈 SVG 로딩"은 **구조만 일반화**하고 현재는 XS로 검증, 나머지 사이즈 SVG는 추후 투입 시 동작하도록 설계 필요.

### 로드맵
A-1 preset스키마+좌표정합 ✅ → **A-2 패턴로딩** → A-3 전사이즈 일괄합성 → A-4 text.py 배번/이름 → A-5 order.py 주문서 → A-6 투명도차단 → B 웹앱

### 불변 제약
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) 불변 / device CMYK 무손실(바이트동일) / 빌드0·순수HTML+vanillaJS / 폴더+JSON 저장 / CLI 단독 테스트 가능

### 확정 사실 (방식A 앵커 정합)
- 좌표정합 = 방식A(앵커, bottom-left, 등방 contain) 확정. grade.py `_piece_transform`이 정답 공식.
- 실측 디자인영역(design_XL.ai pt): 앞판 x[468..2098]y[2877..5287]→svg_index1 / 뒤판 x[2310..3997]y[2877..5287]→idx0 / 소매 x[468..2225]y[5301..5562]→idx2. (parse_svg 높이 내림차순 정렬: 0=뒤판,1=앞판,2=소매)
- 출력=다페이지 1PDF / 패턴=전사이즈 SVG 보유 예정

### A-2~ 백로그 (reviewer 지적, 차단 아님)
①verify.py cm 정규식 음수 미허용→방식A 오프셋 음수라 "스케일cm" FAIL(engine 수정 승인 필요) ②shrink 등방한계(가로/세로 다른 수축 미반영) ③preset sizes.scale 미사용(스키마/구현 불일치) ④number/name_area piece_id 유효성 검증 없음 ⑤svg_index 높이정렬 가정 사이즈확장 시 재확인

### 실데이터 경로
../grader/illustrator-scripts/test/ (config.json, design_XL.ai, pattern_XS.svg, result.json, output_XS_ai.eps)
원천 로직: ../grader/illustrator-scripts/grading.jsx (기존 좌표정합)

### git
origin=cobby8/grader-v2, main. 미푸시 0개. 최신 b19c75c(A-1 완료).

## 기획설계 (planner-architect)

### A-2 패턴 로딩 모듈 설계 (2026-06-15)

🎯 목표: preset.sizes[]를 순회하며 사이즈별 패턴 SVG를 탐색·parse_svg 로딩하고, 각 사이즈를 engine의 Piece 리스트로 변환하는 "범용 로딩 계층"을 grade.py에서 분리한다. XS 1개로 검증, 나머지 사이즈 SVG는 코드수정 0으로 추후 합류. 누락 사이즈는 에러 아닌 경고.

#### 1. 책임 범위 — 무엇을 떼고 무엇을 추가하나
현재 grade.py `build_layouts` 한 함수 안에 (A)사이즈 순회+SVG경로조립+parse_svg (B)조각별 transform(방식A) 계산 (C)페이지크기 계산 이 뒤섞여 있다. A-2는 이 중 **(A) "SVG를 찾아 읽어 조각으로 변환"하는 로딩 계층**만 떼어낸다. (B)방식A transform은 A-1 확정 자산이라 손대지 않는다.

- **파일 결정: `engine/pattern_loader.py` 신설** (pattern.py에 함수 추가 X).
  - 이유1(공개 API 불변 제약): pattern.py는 `parse_svg/Polyline`을 제공하는 engine 공개 모듈. 거기에 preset 의존 로직(폴더규약·사이즈탐색)을 넣으면 "engine은 preset을 모른다"는 계층 분리가 깨진다. preset을 아는 코드는 grade.py와 같은 "응용 계층"에 둔다.
  - 이유2(비유): pattern.py = "SVG 글자를 읽는 법을 아는 사전". pattern_loader.py = "어느 책(사이즈)의 몇 페이지를 펴서 사전으로 읽을지 아는 사서". 사전에 사서 업무를 섞지 않는다.
- pattern_loader.py가 가지는 공개 함수(제안):
  - `resolve_size_svg(preset, size) -> (경로|None, 출처설명)` : 한 사이즈의 SVG 경로를 규약대로 찾는다(없으면 None).
  - `load_size_pieces(preset, size) -> list[Piece]` : 한 사이즈의 SVG를 parse_svg→piece_id 매칭→Piece 리스트. (방식A transform 계산은 grade.py의 `_piece_transform`를 import해 사용.)
  - `load_all(preset) -> (results, warnings)` : 전 사이즈 순회. results=[(size, list[Piece]) ...], warnings=[안내문자열...]. 누락 사이즈는 results에서 빠지고 warnings에 기록.
- grade.py 변경: `build_layouts`는 로딩을 pattern_loader.load_all에 위임하고, 받은 pieces로 page_size 계산(C)만 수행해 SizeLayout 조립. transform(B)는 그대로 유지.

#### 2. 다중 사이즈 SVG 파일 탐색 규칙
현 preset `sizes[]`에 이미 `pattern_file` 필드 존재(XS는 "XS.svg"). → **새 필드 추가 불필요.** 탐색 규약을 2단계 폴백으로 명문화:
1. `size.pattern_file`이 명시돼 있으면 그 파일(`_dir` 기준 상대) 사용. (현행 유지)
2. `pattern_file`이 없으면 **파일명 컨벤션 `<size.name>.svg`** 로 자동 탐색(예 name="S"→ S.svg). → 추후 사이즈 추가 시 sizes에 `{"name":"S"}` 한 줄만 넣어도 동작(코드수정 0 충족).
- 경로는 항상 `preset["_dir"]` 기준 상대 → 외부 절대경로 의존 0(기존 conventions 준수).

#### 3. svg_index 높이정렬 가정 방어 (백로그⑤)
위험: parse_svg는 조각을 "높이 내림차순"으로 정렬→ preset의 `svg_index`(0=뒤판,1=앞판,2=소매)는 XS에서 실측한 순서. 사이즈가 커지면 조각 높이 대소가 역전돼 index가 엉뚱한 조각을 가리킬 수 있음.
- A-2 방어책(최소·단순):
  - (a) **개수 검증**: parse_svg 결과 조각 수 ≠ preset.pieces 수면 그 사이즈는 경고 후 skip(잘못 매칭하느니 명시적 실패).
  - (b) **종횡비 교차검증(경고)**: 각 piece의 `design_region_pt` 종횡비와 svg_index가 가리킨 조각 bbox 종횡비가 크게 다르면(예 30%+ 차이) "index 매칭 의심" 경고를 띄운다(차단 아님, 사람이 보게).
  - (c) **근본해결은 A-2 범위 밖으로 명시**: piece_id 명시 매칭(SVG 요소 id ↔ preset piece.id)은 SVG에 조각 id가 없어(현 SVG는 무명 polyline 3개) 지금은 불가. → 백로그⑤를 "별도 결정사항"으로 남기고(아래 8번), A-2는 (a)(b) 안전망만 깐다.

#### 4. 누락 사이즈 처리 정책
- **부분 성공 허용**: 한 사이즈 SVG가 없거나 파싱 0조각이어도 전체를 죽이지 않고, 있는 사이즈만 합성. (사용자 결정: 친절한 경고)
- 경고 메시지 형식(한국어, 비개발자용):
  - 누락: `⚠️ [건너뜀] 사이즈 'M' — 패턴 파일을 찾지 못했습니다(찾은 경로: .../M.svg). 이 사이즈는 출력에서 빠집니다.`
  - 개수 불일치: `⚠️ [건너뜀] 사이즈 'L' — SVG 조각 5개 ≠ 정의된 조각 3개. 패턴 파일을 확인하세요.`
  - 종횡비 의심: `🟡 [경고] 사이즈 'XS' 조각 '소매' — svg_index=2 가 가리킨 조각 비율이 예상과 달라요(의심). 결과 미리보기를 꼭 확인하세요.`
- 전부 누락이면(results 0개) → 그때만 에러: `❌ 합성할 사이즈가 하나도 없습니다.`
- 경고는 stdout으로 모아 cmd_grade가 출력. grade()/load_all은 warnings 리스트로 반환(웹앱 B단계에서 재사용 가능하게 텍스트만).

#### 5. preset.json 스키마 변경
- **변경 거의 없음.** `pattern_file`은 이미 있고 그대로 사용. 컨벤션 폴백(`<name>.svg`)은 코드 규약이라 스키마 변경 아님.
- (선택) `pattern_file`을 **필수→선택**으로 문서상 완화(README에 "없으면 <사이즈>.svg 로 자동 탐색" 한 줄 추가). JSON 구조 자체는 before==after.
  - before: `{"name":"XS","pattern_file":"XS.svg","scale":1.0}`
  - after(동일, 단 신규 사이즈는 생략 가능): `{"name":"S"}` ← pattern_file 없이도 S.svg 자동 탐색.

#### 6. A-3 인터페이스 (전 사이즈 일괄합성)
- A-2 `load_all(preset)` 반환: `(results: list[(size_dict, list[Piece])], warnings: list[str])`.
- A-3(build_layouts)는 results를 받아 각 (size, pieces)→ page_size 계산 후 `SizeLayout(name, page_size, pieces)` 생성 → compose에 리스트로 전달. **A-2가 Piece까지 완성해 주므로 A-3는 페이지 포장만 하면 됨.**
- design_pdf_path 존재검증은 grade()에 유지(로딩 계층은 SVG만 책임, 디자인 PDF는 compose 책임).

#### 7. 구현 단계 쪼개기 (developer용)
1. `engine/pattern_loader.py` 신설 + `resolve_size_svg()` (pattern_file 우선 → <name>.svg 폴백 → 없으면 None).
2. `load_size_pieces()` : parse_svg 호출 + 개수검증(3a) + svg_index 범위검증 + grade._piece_transform로 Piece 생성.
3. 종횡비 교차검증(3b) 경고 함수 추가(차단 아님).
4. `load_all()` : sizes 순회, 성공/누락 분기, warnings 수집, 부분성공.
5. grade.py `build_layouts` 리팩토링: 로딩부 제거→load_all 위임, page_size 계산만 남김. (transform·방식A 로직 그대로 보존, 출력 바이트 동일 회귀 확인 필수).
6. cli.py cmd_grade: load_all warnings를 화면에 출력(있으면).
7. 검증: `python -m engine grade --preset ... --design design_XL.ai` → XS 정상 합성 + previewA와 바이트 동일(A-1 회귀) + (가짜 M 사이즈 한 줄 추가 테스트로 누락경고 동작 확인).

#### 8. 리스크 / 미결정 (PM 결정 필요)
- (R1) **백로그⑤ 근본해결 보류 승인**: A-2는 개수+종횡비 안전망만. piece_id↔SVG 매칭은 SVG에 조각 id가 없어 불가 → 추후 SVG에 id를 넣게 디자이너에게 요청할지, 아니면 종횡비 자동매칭을 도입할지는 별도 결정. (현재는 svg_index 수동 유지)
- (R2) **종횡비 의심 임계값**(30% 제안) 값 확정 필요 — 너무 낮으면 정상도 경고 남발.
- (R3) `_piece_transform`를 grade.py에 둔 채 pattern_loader가 import할지, 아니면 pattern_loader로 이동할지 — 제안: **transform은 grade.py 유지**(방식A 자산 응집), loader는 "어떤 조각을 어떤 윤곽에 얹을지"까지만. PM 확인.
- (R4) 회귀 기준: A-1 previewA/outA.pdf와 **바이트 동일**을 통과 기준으로 삼는다(좌표/로딩만 바뀌므로 출력 불변이어야 함). 확인.

### A-4 배번·이름 벡터 렌더 설계 (engine/text.py 신설) — 2026-06-15

🎯 목표: preset의 number_area/name_area(조각 기준 rel_bbox 0~1)에 배번(숫자)·이름(한글)을
**벡터 경로(아웃라인)**로 그려 넣는다. 폰트 임베드 없이 글리프를 PDF 경로연산자(m/l/c…f)로
펴서 CMYK 단색으로 칠한다(공장 호환). 디자인 Form 자체는 **건드리지 않고**, 글자는 페이지
콘텐츠에 별도 추가 → device CMYK 무손실·verify PASS 유지.

#### 0. 사전 조사로 확정한 사실 (직접 검증함)
- Pretendard-Black/Bold.otf 는 **CFF(큐빅 베지어) 아웃라인**, **glyf 아님**. unitsPerEm=2048.
  - → 펜이 주는 곡선이 **cubic(curveTo, 3점)** 이라 PDF `c`(큐빅) 연산자에 **1:1 대응**(평탄화·근사 불필요). 가장 단순한 경로다.
- getGlyphSet()[glyphname] 은 `.draw(pen)`(윤곽) + `.width`(advance, 폰트단위) 둘 다 제공.
- cmap 에 0~9, 김/이/박, A 모두 존재. 이모지(U+1F600) 같은 건 없음 → 글리프 누락 처리 대상.
- 펜 명령 집합: moveTo / lineTo / curveTo(큐빅) / closePath. (qCurveTo 없음 — TTF였다면 쿼드라틱이라 변환 필요했을 것)
- compose.py: 페이지마다 `page.obj["/Contents"] = out.make_stream(블록.encode("ascii"))` 로
  **페이지 콘텐츠를 통째로 새로 만든다.** 디자인은 Form XObject 1개로 임베드 후 `q…Do…Q` 로 참조.
  → 글자 연산자를 이 콘텐츠 문자열 **뒤에 이어 붙이면** 디자인 위에 글자가 얹힌다. Form 바이트는 불변.
- verify_output 의 PASS 기준(핵심): ①Form 바이트가 원본과 동일(글자는 페이지 콘텐츠라 Form 불변→영향 0)
  ②동일 Form 정확히 1개 ③RGB/Lab 색공간 유입 0(글자는 CMYK `k` 로만 칠함→OK) ④투명도 0(글자에 ca/CA·SMask 안 씀→OK)
  ⑤이미지 추가 0(`count_images` 가 /Subtype /Image 셈 — **글자는 벡터 경로라 이미지 0 추가→OK**)
  ⑥`b" Do"` 카운트 == expected_placements. **여기 함정**: 글자 연산자에 ` Do` 가 들어가면 카운트가 틀어진다.
  → 글자 경로는 `Do` 를 절대 쓰지 않으므로(m/l/c/f/k/q/Q만) 안전. (developer가 글자 ops에 'Do' 문자열 안 넣도록 주의)
  ⑦`b"W n"`(클립)·`cm`(스케일) 존재는 기존 디자인 배치가 이미 충족.

#### 1. text.py 공개 함수 시그니처 (입출력 명확)
```
# 메인 — 글자 1줄을 bbox 안에 맞춘 PDF 콘텐츠 연산자 문자열로 반환
render_text_ops(
    text: str,                 # 그릴 글자("7", "김민수")
    font_path: str,            # otf/ttf 절대경로(없으면 친절 에러)
    bbox_pt: tuple,            # (x0,y0,x1,y1) 시트(PDF) 절대좌표 — 글자가 들어갈 칸
    color_cmyk: tuple,         # (c,m,y,k) 0~1 또는 0~100 → 내부서 0~1 정규화
    align: str = "center",     # "left"|"center"|"right" 가로정렬(세로는 항상 중앙)
) -> str
# 반환: "q … k  <경로 m/l/c h> f … Q" 형태 PDF 연산자(ascii). 빈 문자열이면 그릴 것 없음.
# 글리프 누락/빈 텍스트면 "" 반환 + 경고는 호출측이 수집(아래 7번).

# 보조(내부, 필요 최소)
_load_glyphset(font_path) -> (glyphset, cmap, units_per_em)   # 폰트 1회 로드(캐시 가능)
_glyph_path_ops(glyphset, glyph_name, scale, dx, dy) -> str   # 글리프1개 → m/l/c h (스케일·이동 적용)
_text_metrics(text, glyphset, cmap, units_per_em) -> (advances, missing)
                                                   # 글자별 advance 폭 합 + 누락 글자 목록
```
- **반환을 "문자열"로** 둔 이유: compose 가 이미 "콘텐츠=문자열 join" 구조라 그대로 이어붙이면 됨(추상화 최소).

#### 2. fontTools → PDF 경로연산자 변환 파이프라인 (단계별)
1. `TTFont(font_path)` → `getGlyphSet()`, `getBestCmap()`(코드포인트→glyphname), `head.unitsPerEm`(2048).
2. 글자 1개: `gname = cmap.get(ord(ch))`. 없으면 **누락**(7번). advance = `glyphset[gname].width`.
3. `RecordingPen()` 에 `glyphset[gname].draw(pen)` → 명령 리스트.
4. **폰트단위→pt 스케일** `u = scale / unitsPerEm`(scale=목표 글자높이 pt). 각 좌표에 곱하고 (dx,dy) 더함.
5. 명령 매핑(PDF 연산자):
   - `moveTo (x,y)`            → `x y m`
   - `lineTo (x,y)`            → `x y l`
   - `curveTo (c1,c2,end)`     → `c1x c1y c2x c2y ex ey c`   (큐빅 1:1 — Pretendard는 CFF라 항상 이 형태)
   - `closePath`              → `h`
   - (qCurveTo 나오면 — TTF 폰트 대비 — 쿼드라틱→큐빅 승격 공식 적용: CP1=P0+2/3(QC-P0), CP2=P2+2/3(QC-P2). Pretendard엔 안 나오지만 방어코드로 둠)
6. 글리프 채우기: 한 글자의 모든 서브패스를 모은 뒤, 글자 전체를 1번 `f`(non-zero winding fill)로 칠함.
   - 구멍(예 '0','8','9','이'의 안쪽)은 **even-odd 아닌 non-zero**가 폰트 윤곽 방향과 맞음. CFF/TTF 윤곽은 nonzero 기준 → `f` 사용(=`f*` 아님). 구멍 자동 처리됨.
7. 색: 글자 앞에 `c m y k k`(소문자 k=비획·fill용 CMYK). 예 흰색[0,0,0,0]→`0 0 0 0 k`. stroke 미사용(fill만, 의뢰서 "선택 stroke"는 A-4 범위서 보류).
8. 전체를 `q`…`Q` 로 감싸 그래픽 상태 격리(색·CTM 누수 방지).

#### 3. bbox 맞춤 로직 (rel_bbox → 절대좌표 → 스케일·정렬·세로중앙)
- **(가) rel_bbox(0~1) → 조각 outline bbox 절대좌표 환산**:
  - number_area.piece_id="back" → preset.pieces 에서 id=back 조각을 찾고, 그 조각이 layout 에 만든 Piece.outline 의 bbox 를 구함.
  - Piece.outline 의 bbox = `pdfutil.bbox(piece.outline)` → (px0,py0,px1,py1). (이미 시트 절대좌표·y위로)
  - 절대 칸: `x0 = px0 + rel_x0*(px1-px0)`, `y0 = py0 + rel_y0*(py1-py0)`, x1/y1 동일. (rel 은 좌하단기준 0~1)
  - ⚠️ rel_bbox 가 "좌상단 기준"인지 "좌하단 기준"인지 확정 필요(미결정 R-A). preset 주석상 흰글자/center라 좌우 대칭이지만 **세로 위치**는 기준에 따라 위/아래 뒤집힘. → 방식A 좌표가 y위로(좌하단원점)이므로 **rel 도 좌하단기준 y위로**로 통일 권고. (developer 미리보기로 검증)
- **(나) 텍스트 자연 크기 측정**: unitsPerEm 기준 글자높이=폰트 ascent~descent 대신 **cap/em 기준 단순화**: 글자높이 1em=unitsPerEm 로 보고, 폭=Σadvance.
  - em높이 1.0 환산 시 폭_em = Σadvance/unitsPerEm, 높이_em = 1.0 (보수적). 
- **(다) bbox 맞춤 스케일(contain)**: 칸폭 bw=x1-x0, 칸높이 bh=y1-y0.
  - `scale_by_w = bw / 폭_em`, `scale_by_h = bh / 높이_em`, **scale = min(둘)** (칸 밖으로 안 나가게 contain).
  - 실제 글자높이 pt = scale * 높이_em(=scale), 글자폭 pt = scale*폭_em.
- **(라) 가로정렬**: 남는 가로공간 `gap_x = bw - 글자폭pt`. left→dx=x0 / center→dx=x0+gap_x/2 / right→dx=x0+gap_x.
- **(마) 세로중앙**: `gap_y = bh - 글자높이pt`; baseline_y = y0 + gap_y/2 (+ descent 보정). 폰트 baseline 이 0 이므로 dy=baseline_y.
  - 단순화: descent 무시하고 글자높이=em*scale 로 중앙. 미세 어긋남은 미리보기 보고 preset rel_bbox 로 조정(비개발자가 숫자만 만짐).
- **(바) 글자 누적**: 각 글자 그릴 때 dx 를 advance*u 만큼 전진(글자 사이 간격=폰트 advance 그대로).

#### 4. compose 결합 방식 결정 — (A) vs (B)
- **(A) 페이지 콘텐츠 스트림에 텍스트 블록 추가** (compose 가 글자 ops 를 콘텐츠 끝에 append)
  - 장점: 디자인 Form 완전 불변(바이트동일 보장 자명). 구현 단순(문자열 이어붙이기). verify 영향 분석 쉬움.
  - 단점: compose 시그니처에 "조각별 글자 ops" 를 넘길 통로가 필요.
- **(B) Piece.extra_ops 필드 추가** (Piece 에 글자 ops 를 담아 compose 가 q…Q 뒤에 그림)
  - 장점: "이 조각에 이 글자" 가 데이터로 묶임(자연스러움). compose 루프가 piece 단위라 끼우기 좋음.
  - 단점: dataclass 필드 추가=공개 API 표면 변경(단 **기본값 ""** 면 기존 호출 전부 그대로 동작).
- **✅ 권고: (B) Piece.extra_ops (기본값 "")** — 이유: 글자는 "특정 조각의 특정 칸"에 종속된 정보라
  Piece 에 붙는 게 의미상 맞고, compose 변경이 **루프 안 1줄**로 끝나 가장 작다. 공개 API 는 "기존 인자 불변+신규는 기본값" 원칙을 지킴(호출부 무수정).

  **정확한 변경 지점 (before → after)**:
  - `engine/compose.py` Piece dataclass:
    - before: `outline; transform; name: str = ""`
    - after : `outline; transform; name: str = ""; extra_ops: str = ""`  ← 필드 1개 추가(기본값 빈문자열, 무손실)
  - `engine/compose.py` compose() 내부 루프:
    - before:
      ```
      for piece in layout.pieces:
          blocks.append(place_block(piece.outline, piece.transform, str(name)))
          placements += 1
      ```
    - after (글자 블록을 디자인 배치 **뒤에** 추가 → 디자인 위에 글자):
      ```
      for piece in layout.pieces:
          blocks.append(place_block(piece.outline, piece.transform, str(name)))
          placements += 1
          if piece.extra_ops:           # 글자 등 추가 벡터(있을 때만)
              blocks.append(piece.extra_ops)
      ```
  - **compose() 시그니처는 불변.** placements(=Do 개수)는 글자가 Do 를 안 쓰므로 그대로 디자인 배치수 → verify "배치 횟수 일치" 안 깨짐.
  - 주의: compose 가 콘텐츠를 `.encode("ascii")` 한다 → 글자 ops 도 **ascii(숫자·연산자뿐)**라 OK. (한글은 *글리프 경로 좌표*로 바뀌므로 콘텐츠엔 한글 바이트가 안 들어감 — 핵심 이점)

#### 5. grade.py 연결 (어느 시점에 글자를 그리나 / 값은 어디서)
- 그리는 시점: `build_layouts` 가 각 사이즈의 Piece 들을 만든 **직후**, number_area/name_area 가 가리키는
  piece(back)의 Piece 를 찾아 `extra_ops` 를 채운다.
- 값 출처: **A-4는 job 단계 전**이라 실제 선수 데이터가 없음 → **CLI 플래그 `--number`/`--name` 단독 테스트 경로** 신설.
  - grade(preset_path, design_pdf_path, out, *, number=None, name=None) 로 **키워드 인자 추가(기본 None=안 그림)**.
    기존 호출(grade_run(preset, design, out))은 그대로 동작(API 무손실 확장).
  - build_layouts(preset, design_pdf_path, *, number=None, name=None) 동일하게 키워드 추가.
  - cli grade 에 `--number`(숫자), `--name`(한글) 옵션 추가(기본 None). 둘 다 없으면 글자 없이 기존과 동일 출력(A-1/A-2 회귀 보존).
- 좌표 환산 위치: grade.py 가 piece outline bbox 를 알고 있으므로 grade.py에서 rel_bbox→절대 환산 후 text.render_text_ops 호출이 자연스러움. (text.py 는 "절대 bbox + 글자" 만 받음 = 순수/재사용 쉬움)

#### 6. verify PASS 유지 보장·검증 계획
- 보장 논리: (a)디자인 Form 불변→"바이트동일/단일임베드" 영향0 (b)글자=CMYK `k` fill→"RGB/Lab 유입0" (c)글자에 투명도·SMask 미사용→"투명도0" (d)글자=벡터 경로(이미지 객체 0생성)→"래스터 미추가" (e)글자에 `Do` 미사용→"배치횟수==placements" 유지.
- 검증 절차(developer 자체검증):
  1. `--number 7 --name 김민수` 로 grade → verify_output 전항목 **PASS** 확인(특히 래스터미추가/CMYK유지/배치횟수).
  2. number/name 둘 다 None(글자 없음) 으로 grade → **A-2 직전 출력과 바이트 동일**(회귀: 글자 미지정 시 변화0).
  3. preview PNG 로 back 조각에 "7"·"김민수" 가 number_area/name_area 칸 안 정위치(중앙) 확인.
  4. (선택) inkcov: 글자 흰색[0,0,0,0]은 잉크0이라 inkcov 거의 불변 — 색 보존 깨짐 없음 확인.

#### 7. 엣지 케이스 처리
- **글리프 누락**(폰트에 없는 글자, 예 한자·이모지): 해당 글자만 건너뛰지 말고 **그 텍스트(선수) 전체를 경고+미출력** 권고
  (이름 중 1글자 빠지면 오히려 더 위험). 경고 텍스트로 수집: `🟡 '홍길동' 중 '동' 글자가 폰트에 없어 이름을 그리지 못했습니다(선수 확인).` → render_text_ops 가 missing 있으면 "" 반환 + 사유를 호출측에 전달(반환 튜플 or 예외 대신 경고리스트 콜백). **권고: render_text_ops 는 (ops_str, warnings:list) 튜플 반환**으로 명확화.
- **빈 텍스트**(number/name None 또는 ""): 그냥 "" 반환(아무것도 안 그림). 정상 흐름.
- **bbox 역전/0크기**(rel_x1<=rel_x0 등 preset 오타): bw/bh<=0 이면 경고 후 미출력(0나눗셈 방지).
- **color_cmyk 범위**: 0~1 또는 0~100 입력 모두 수용(>1 값 있으면 /100 정규화) — 비개발자 입력 관대.
- **폰트 파일 없음**: FileNotFoundError 친절 한글 메시지(conventions "입력 선검증" 준수).
- **piece_id 불일치**(number_area.piece_id 가 pieces 에 없음 — 백로그④): 경고 후 글자 미출력(차단 아님).
- **align 오타**: 모르는 값이면 center 로 폴백 + 경고.

#### 8. 구현 단계 쪼개기 (developer용, 작은 스텝)
1. `engine/text.py` 신설: `_load_glyphset` + `_glyph_path_ops`(글리프1개→m/l/c h, 큐빅 매핑) 먼저. 라틴 "7" 한 글자로 ops 문자열 눈 검증.
2. `_text_metrics`(advance 합 + missing) + `render_text_ops`(스케일·정렬·세로중앙·여러글자 누적) 완성. "김민수" 다글자 검증.
3. compose.py: Piece 에 `extra_ops=""` 필드 + 루프에 `if piece.extra_ops: blocks.append(...)` (4번 변경지점 그대로).
4. grade.py: build_layouts/grade 에 `number/name` 키워드 추가, back 조각 bbox→rel_bbox 절대환산→render_text_ops→해당 Piece.extra_ops 세팅. 경고 수집.
5. cli.py cmd_grade: `--number/--name` 옵션 추가, grade 에 전달, 경고 출력.
6. 자체검증: `python -m engine grade --preset data/patterns/농구_U넥_양면/preset.json --design <design.ai|pdf> --number 7 --name 김민수 --out _grade_out`
   → ① verify 전항목 PASS ② preview PNG 에 "7"·"김민수" 정위치 ③ 글자 미지정 시 A-2 출력과 바이트동일.
- 자체검증 한 줄: 위 CLI + `python -m engine grade ...(번호/이름 없이)` 두 번 돌려 PASS·회귀 확인.

#### 9. 리스크 / 미결정 (PM 결정 필요)
- (R-A) **rel_bbox 기준축**: 좌하단(y위로) vs 좌상단(y아래로). → **좌하단 y위로 권고**(방식A 좌표계와 일치). preview 로 위/아래 확정. PM 확인.
- (R-B) **세로 정렬 정밀도**: descent/ascent 무시한 em중앙 근사 사용(단순) → 글자가 칸에서 살짝 위/아래로 보일 수 있음. preset rel_bbox 숫자 조정으로 흡수 권고. 정밀 baseline 보정은 후순위. PM 확인.
- (R-C) **stroke(외곽선)**: 의뢰서 "선택 stroke" 는 A-4 1차 범위서 제외(fill만). 유니폼 글자에 테두리 필요 시 후속 작업. 동의 구함.
- (R-D) **design `.ai` 입력**: compose/verify 는 pikepdf.open(design) 으로 .ai 를 PDF로 연다(A-1에서 이미 동작). A-4는 글자만 추가라 .ai 경로 영향 없음 — 확인용 메모.
- (R-E) **글자 색 = 흰색[0,0,0,0]**: 잉크0이라 미리보기 PNG(흰 배경)에서 **안 보일 수** 있음 → 자체검증 때 임시로 검정[0,0,0,1] 로도 1회 렌더해 위치 확인 후, 최종은 preset 흰색 유지 권고. PM 확인.
- (R-F) **글리프 누락 시 텍스트 전체 미출력 vs 가능한 글자만**: 권고=전체 미출력(이름 깨짐 방지). PM이 "있는 글자만이라도" 원하면 변경. 확인.

## 구현 기록 (developer)

### A-4 배번·이름 벡터 렌더 (2026-06-15, 설계대로 구현 완료)

📝 구현한 기능: preset.number_area/name_area 에 배번(숫자)·이름(한글)을 **폰트 임베드 없이
벡터 경로(아웃라인)**로 그려 넣는다. 글자는 디자인 Form 과 분리된 페이지 콘텐츠에 CMYK `k`
fill 로만 얹어 device CMYK 무손실·verify PASS 유지. CLI `--number`/`--name` 으로 단독 테스트.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/text.py | 글리프→PDF큐빅경로(m/l/c h) 변환 + bbox맞춤(contain·정렬·em중앙) + CMYK k fill. render_text_ops(text,font,bbox_pt,color_cmyk,align)→(ops,warnings) | **신규** |
| engine/compose.py | Piece에 `extra_ops: str=""` 필드 추가 + compose 루프에서 디자인 배치 뒤 `if piece.extra_ops: blocks.append(...)` 1줄. compose 시그니처 불변 | 수정 |
| engine/grade.py | build_layouts/grade 에 키워드 `number/name/warnings` 추가. _resolve_font_path(폰트경로 풀기)+_apply_text_area(rel_bbox→절대bbox 환산→render_text_ops→Piece.extra_ops 주입) 헬퍼 신설 | 수정 |
| engine/cli.py | cmd_grade 에 `--number`/`--name` 플래그 + render 경고 화면출력 | 수정 |

💡 핵심 로직:
- **글리프→경로**: TTFont→getGlyphSet/getBestCmap/unitsPerEm(2048). RecordingPen 으로 윤곽 기록.
  Pretendard=CFF(큐빅)라 curveTo→PDF `c` 1:1(평탄화 불필요). closePath→h. 한 글자 모든 서브패스 모아 `f`(non-zero)로 한 번에 채움→구멍(0,8,이 안쪽) 자동.
  ⚠️ **단위 주의**: 글리프 좌표는 '폰트단위'라 `u=scale/upm` 을 곱한다(scale 직접 곱하면 2048배 폭주 — 첫 시도 때 발견·수정). advance 도 `adv*u` 로 전진.
- **bbox 환산**: grade.py 가 대상 piece(back) outline 의 절대 bbox(pdfutil.bbox)를 구해
  rel_bbox(0~1, 좌하단기준 R-A)→절대좌표 환산(y위로, 방식A 일치)→text.render_text_ops 에 절대 bbox 만 넘김(text.py 순수 유지).
  contain 스케일 min(칸폭/글자폭, 칸높이/1em), align 가로정렬, gap_y/2 세로중앙(em근사 R-B).
- **extra_ops 결합**: 글자 ops 를 해당 Piece.extra_ops 에 저장→compose 가 q…Do…Q(디자인) **뒤에** 이어붙여 디자인 위에 글자. 글자는 Do 미사용→placements(=Do개수) 불변.

💡 tester 참고:
- 테스트 방법:
  - 회귀: `python -m engine selftest` → 종합 PASS.
  - 글자없이: `python -m engine grade --preset data/patterns/농구_U넥_양면/preset.json --design "C:/0. Programing/grader/illustrator-scripts/test/design_XL.ai" --out _grade_out` (number/name 미지정).
  - 글자렌더: 위 명령에 `--number 7 --name 김민수 --out _grade_out_text` 추가 → 흰색이라 PNG 안보임(R-E). 보려면 임시 검정 preset 사본 만들어 color_cmyk=[0,0,0,1] 로 렌더(원본 preset은 흰색 유지!).
- 정상 동작:
  - selftest 종합 PASS. grade 는 알려진 FAIL 2건(투명도·스케일cm=백로그①②)만, **새 FAIL 없음**.
  - 검정 미리보기(_grade_out_text/grade_p01.png): 뒤판에 배번 '7'(Black, 기존20영역)+이름 '김민수'(Bold, 위쪽 중앙) 정위치 그려짐 확인 완료.
  - 글자없이 출력 = 글자 그리기 전과 **콘텐츠 동일**(아래 회귀 주의 참고).
- ⚠️ **바이트동일 회귀 주의(중요)**: pikepdf 가 XObject 리소스 이름을 매 실행 랜덤 22자로 부여→순수 `cmp`/`md5sum` 은 코드 정상이어도 항상 다름. **올바른 검증**: pikepdf 로 열어 page.obj.Contents.read_bytes() 를 꺼내 Resources.XObject 이름을 '/X'로 통일 후 비교(A-4 검증서 콘텐츠 길이 4097 100% 일치 확인). 또는 verify 의 "Form 바이트동일/단일임베드/래스터미추가" PASS 로 무손실 간접증명. (errors.md 기록함)
- 주의할 입력:
  - 폰트에 없는 글자(이모지·한자): `--name 홍길😀` → 이름 통째 미출력 + 🟡경고, 크래시 없음(검증완료).
  - 빈/None: 글자 안 그림(정상). CMYK 0~100 입력도 /100 정규화 수용.

⚠️ reviewer 참고:
- 봐줬으면: ①scale vs u 단위 분리(_glyph_path_ops 에 u 전달) ②extra_ops 결합이 compose 시그니처/공개API 불변 지켰는지(Piece 신규 필드 기본값 "") ③글자 ops 에 Do/ca/CA/rg 없음(verify 무영향) — 검증 결과 콘텐츠에 Do=3(디자인만)·RGB 없음·글자투명도 없음 확인.
- preset.json 의 number_area/name_area 에 font/color/align 필드는 **이전 폰트확보 단계에서 추가된 미커밋 변경**(내가 만든 것 아님). A-4가 사용하는 정당한 필드라 유지. 원본 color_cmyk 는 흰색[0,0,0,0] 그대로(R-E 원복, 검정은 임시사본으로만 검증).
- qCurveTo 분기는 Pretendard(CFF)엔 안 쓰이는 TTF 대비 방어코드(직선 근사). 정밀필요 시 OTF 권장.

## 테스트 결과 (tester)

### A-4 배번·이름 벡터 렌더 검증 (2026-06-15, tester)

| 검증 항목 | 결과 | 객관 수치 / 근거 |
|----------|------|----------------|
| 1. selftest 회귀 | ✅ 통과 | `selftest` 종합 **PASS**, **exit 0**. 9개 항목 전부 PASS, inkcov 최대편차 0.000000 |
| 2. 글자없이 회귀(핵심) | ✅ 통과 | XObject 이름 정규화 후 콘텐츠 **100% 동일**. `_grade_out_reg` ↔ `_grade_out`(A-1) raw길이 4160=4160, ↔ `grading_compare/outA.pdf` 도 4160=4160 동일 |
| 3. 글자 렌더 | ✅ 통과 | 크래시 없음. 배번'7' 좌표 X[2941~3227]Y[1096~1484] ⊂ number_area칸 X[2778~3394]Y[1096~1644]. 이름'김민수' X[2753~3420]Y[1665~1898] ⊂ name_area칸 X[2701~3471]Y[1688~1951]. 검정/흰색 미리보기 모두 뒤판 정위치 렌더 시각확인 |
| 4. verify PASS 유지 | ✅ 통과 | 글자없음/글자있음/이모지누락 **3케이스 verify 항목 100% 동일**. **새 FAIL 0건**. FAIL은 알려진 백로그 2건(투명도없음·스케일cm)뿐 |
| 5. 글리프 누락 부분실패 | ✅ 통과 | `--name 홍길😀` → 이름 통째 미출력 + 🟡경고("'😀' 글자가 폰트에 없어...") + 크래시 없음. k연산자 1개(배번만)=이름 정확히 생략 |
| 6. CMYK 무손실 | ✅ 통과 | 글자 ops에 `k`만(글자있음 k=2, 누락 k=1), **rg/RG/sc/scn=0**(RGB없음). **Do=3 전 케이스 불변**(글자가 Form/Do 미사용→디자인 Form개수 안늘음). ca/CA/SMask/Image=0 |

**추가 확인 사항**:
- 글자 ops 연산자: m/l/c h f + k 만 사용(이미지·투명도·RGB 0). 글자 추가 바이트 1668(4160→5828). 디자인 배치 뒤 q…Q 블록으로 정상 결합.
- cp949 콘솔 크래시 **없음**(🟡·— 등 유니코드 정상 출력).
- 미세 메모(차단 아님): 이름 Y실측 1665가 칸하단 1688보다 23pt 아래 — R-B(em중앙근사·descent무시) 알려진 흡수범위. reviewer도 동일 한계 지적(🟡). 정상.

📊 **종합: 6개 항목 전부 통과 (6/6) — A-4 검증 PASS**
- 회귀 무손실(글자없이 콘텐츠 바이트동일), 글자 정위치 렌더, verify 새 FAIL 0, CMYK 무손실, 글리프누락 안전처리 모두 확인.
- 수정 요청 **없음**.

## 리뷰 결과 (reviewer)

### A-4 배번·이름 벡터 렌더 리뷰 (2026-06-15)

📊 종합 판정: **통과** (치명 이슈 0건). 설계(R-A~R-F)·불변제약 정확히 반영. 🔴 0건 / 🟡 3건(전부 차단 아님).

✅ 잘된 점:
- **단위변환 정확**: `u=scale/upm`(폰트단위→pt) 분리가 정확. `_glyph_path_ops`에 u를 넘기고 advance도 `adv*u`로 전진. (실측: '7'→칸 0~100,0~50 안에 정확히 contain. 좌표 max 62.84로 칸 안.)
- **큐빅 1:1 매핑**: CFF curveTo→PDF `c`(제어점2+끝점) 정확. closePath→h. qCurveTo는 TTF 대비 방어코드로 명시(직선 근사, 한계 주석 솔직).
- **무손실/색보존 완벽**: 글자 ops 정적검증 결과 Do/rg/RG/ca/CA/gs/sh/BI/scn **전부 없음**, `k`(CMYK fill)+`f`(non-zero)+`q…Q`만 사용 → verify 전항목(래스터미추가·RGB유입0·투명도0·배치횟수==placements) 유지 보장. 디자인 Form 안 건드리고 페이지 콘텐츠에만 덧그림.
- **공개 API 불변 준수**: Piece에 `extra_ops:str=""` 기본값만 추가(기존 호출 무수정 동작). compose 시그니처 불변, 루프 삽입 1줄(`if piece.extra_ops`). grade/build_layouts는 `number/name/warnings` 전부 키워드+기본 None → 글자 미지정 시 출력 불변(회귀 보존).
- **엣지케이스 견고**(전부 실측 검증): 빈/None→""·크래시0 / bbox역전→경고+미출력(0나눗셈 방지) / 글리프누락→텍스트 통째 생략+🟡경고(R-F 정확) / align오타→center 폴백+경고 / 폰트없음→친절 한글 FileNotFoundError / CMYK 0~100·0~1 모두 정규화+clamp.
- **지수표기 회피**: 아주 작은 칸(0.001pt)에서도 `fmt`(%.4f)라 `e-` 표기 안 나옴 → ascii 콘텐츠 안전.
- **가독성**: 한글 주석·비유 풍부, 비개발자 친화, 과한 추상화 없음. text.py가 "절대 bbox+글자"만 받는 순수 함수라 grade.py와 책임 분리 깔끔.
- **좌표기준 일치**: rel_bbox(좌하단 0~1)→절대 환산이 방식A(y위로)와 일치(R-A). bbox_of(outline)로 시트 절대좌표 사용.

🟡 권장 수정 (차단 아님, 후순위):
- [text.py 세로정렬, R-B 한계] descent 무시한 em중앙 근사 → 받침/디센더가 칸 **아래로 삐져나감**. 실측: '김민수'를 칸 y[0~40]에 넣으면 글자 y범위가 **-3.59 ~ 31.91**(아래로 3.6pt 초과). 설계상 인지된 한계(preset rel_bbox 숫자로 흡수)지만, 흰글자라 눈에 잘 안 띄어 칸 경계 넘는 게 늦게 발견될 수 있음. 향후 정밀화 시 글자높이를 1.0em 대신 실제 (ascent-descent)/upm 또는 글리프 yMax/yMin 기준으로 바꾸면 칸 안에 정확히 contain. (지금은 미리보기로 조정 권고 — 동작엔 문제 없음)
- [text.py `_FONT_CACHE`] 폰트 캐시가 경로 key만 보고 파일 mtime을 안 봐서, 같은 세션에서 폰트 파일을 교체하면 옛 글리프가 남음. 실사용(폰트 고정)엔 무해하나, 개발 중 폰트 바꿔 테스트할 때 헷갈릴 수 있음. (사소)
- [grade.py `_apply_text_area` color 기본값] `area.get("color_cmyk", [0,0,0,1])`는 검정 기본인데 render_text_ops 호출 시 area에 color_cmyk 없으면 검정. preset엔 항상 흰색[0,0,0,0] 명시돼 있어 실무영향 0. 일관성 메모만.

🔎 확인했고 문제 없음:
- `_apply_text_area`가 `layout_pieces[target_idx]`로 대상 Piece를 찾음 — layout_pieces가 pieces_def와 동일 순서로 build되므로 인덱스 일치 정확(코드상 같은 루프). piece_id 불일치 시 🟡경고+미출력(백로그④ 방어됨).
- build_layouts 루프 안에서 _apply_text_area 호출 위치(transform 계산 후, page_size 계산 전) 무손실 — extra_ops는 compose가 Do 뒤에 붙이므로 디자인 위에 올바르게 얹힘.
- CLI `--number/--name` 기본 None → 기존 grade/selftest/build/parse 서브커맨드 영향 0.

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| reviewer | (없음) | A-4 필수 수정 0건. 🟡 권장 3건은 후순위(세로 em중앙 descent 한계·폰트캐시 mtime·color 기본값)로 리뷰 섹션에만 기록 | 차단 아님 |

## 작업 로그 (최근 10건만 유지)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-15 | pm | engine 환경세팅(pikepdf/PyMuPDF) + git 초기화/첫커밋(d5af10b) | 완료 |
| 2026-06-15 | debugger | 한글 Win cp949 콘솔 UnicodeEncodeError 수정(stdout/stderr UTF-8 고정) | selftest PASS |
| 2026-06-15 | planner-architect | A-1 preset.json 스키마 설계(일러 grading.jsx 좌표정합 규명+3옵션) | 완료(설계만) |
| 2026-06-15 | developer | A-1 시험렌더(compare_mapping.py): 방식A(앵커) vs B(전체정렬+클립) 비교 | outA/B.pdf+previewA/B 생성, 방식A 확정 |
| 2026-06-15 | developer | A-1 마무리: preset.json+README+grade.py(방식A 일반화)+cli grade서브커맨드 | transform·미리보기 previewA와 바이트동일, selftest 회귀PASS |
| 2026-06-15 | tester | A-1 마무리 검증(6항목) | 통과 6/6, previewA 바이트동일, 예상밖FAIL 0 |
| 2026-06-15 | reviewer | A-1 마무리 코드리뷰 | 통과(치명0), 🟡5건 A-2백로그 |
| 2026-06-15 | pm | conventions 3패턴 승격 + A-1 커밋/푸시(b19c75c) | 완료(미푸시0) |
| 2026-06-15 | planner-architect | A-2 패턴로딩 설계(pattern_loader.py 신설+<name>.svg 폴백+누락경고+높이정렬방어) | 완료(설계만) |
| 2026-06-15 | planner-architect | A-4 text.py 설계(글리프→큐빅 PDF경로/Piece.extra_ops 결합/rel_bbox환산/CLI --number·--name/verify PASS유지) | 완료(설계만) |
| 2026-06-15 | developer | A-4 구현(engine/text.py 신설 + compose extra_ops + grade/cli --number/--name). 글리프→큐빅경로·CMYK k fill·rel_bbox환산 | selftest PASS·글자없이 콘텐츠동일·검정미리보기 정위치·verify 새FAIL 0·글리프누락 경고OK |
| 2026-06-15 | tester | A-4 검증(6항목: selftest회귀·글자없이 바이트동일·글자정위치·verify새FAIL0·글리프누락·CMYK무손실) | 통과 6/6, 콘텐츠 4160 100%동일, 새FAIL 0, 수정요청 없음 |
| 2026-06-15 | reviewer | A-4 코드리뷰(text/compose/grade/cli). 단위변환·큐빅매핑·무손실(Do/rg/ca 없음)·공개API불변·엣지케이스 실측검증 | 통과(치명0), 🟡3건 후순위(세로 descent한계·폰트캐시·color기본값) |
