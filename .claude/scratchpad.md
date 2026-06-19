# 작업 스크래치패드

## 현재 작업
- **요청**: Phase D 재설계 — 기존 V넥 path SVG(직선 폴리라인) 발견 → path→polyline 전처리 변환기 + V넥 preset 설계(parse_svg 무수정).
- **상태**: **planner-architect 재설계 완료**(2026-06-19) → developer 구현 대기
- **현재 담당**: planner-architect → (다음) developer
- **핵심 결정**: 기존 path SVG 13개 활용 + path→polyline 전처리 변환기 신규 모듈. ⛔ 잔존 차단 2건(소매 조각 부재, 빈템플릿 미확보) — 아래 잔존 리스크 참조.

### 새 우선순위 (의뢰서 2026-06-15, "추천순서대로" 승인)
1. ~~A-4 배번/이름 렌더 text.py~~ ✅완료(c1d0048)
2. ~~A-5 주문서 파싱 order.py~~ ✅완료(927b7b6)
3. **job 선수별 통합 engine/job.py** ⬅️ **다음** (주문행×디자인→선수별 배번/이름 갈아끼워 출력)
4. **A-2** 전 사이즈 (실제 XS~5XL 패턴 파일 사용자 확보 대기 / 설계 완료·코드 0%)
5. **B** 웹앱 FastAPI + web/ 결합 (web/ 시안 커밋됨 c7fc068)

### job 의뢰서 명세 (착수 시 참고)
- 핵심: 현 grade()는 디자인1장→사이즈별 페이지. 실작업 단위는 **선수별**(같은 사이즈라도 이름·배번 다름). 주문 행마다 배번/이름 갈아끼워 출력.
- 인터페이스: `run_job(preset, design_pdf, order_rows, out_dir, font_path, split="per_player") -> dict`. split: per_player(파일별) | single(다페이지 1PDF). 반환 {outputs:[{size,name,number,pdf,preview,checks}], summary}.
- 각 선수 = 해당 사이즈 레이아웃 + 그 선수 배번/이름 텍스트 블록(A-4 text.py 재사용).
- 결과 ZIP 묶기 좋게 폴더구조: `data/jobs/<날짜_주문명>/output/`. 작업폴더 쓰기 원자적(임시→rename).
- 완료기준: 실패턴+디자인+주문서로 전 사이즈×전 선수 PDF 한 벌 생성, 모든 출력 verify PASS(평탄화 디자인 기준). CLI 한 줄 재현.
- ⚠️ 결정 필요: split 기본값(per_player vs single). (과거 "다페이지 1PDF" 결정 있으나 선수별 단위라 재확인 필요)

### 불변 제약
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) 불변(신규 인자는 기본값 확장만) / device CMYK 무손실 / 빌드0·순수HTML+vanillaJS / 폴더+JSON 저장 / CLI 단독 테스트 가능

### 확정 사실 (방식A 앵커 정합)
- 좌표정합 = 방식A(앵커 bottom-left, 등방 contain). grade.py `_piece_transform`이 정답 공식.
- 디자인영역(design_XL.ai pt): 앞판 x[468..2098]y[2877..5287]→svg_idx1 / 뒤판 x[2310..3997]y[2877..5287]→idx0 / 소매 x[468..2225]y[5301..5562]→idx2.
- 출력=다페이지 1PDF(사이즈). A-4 글자: Piece.extra_ops에 CMYK경로 주입(디자인 Form 불변, verify PASS 유지).
- ⚠️ pikepdf 출력 비결정적(XObject 이름 랜덤): 바이트동일 회귀는 "이름 정규화 후 콘텐츠 비교"로.
- ⚠️ 다중시트 주문서: 표식(주문번호/수량)시트 우선 → 첫시트 → 행최다 폴백. (errors.md)

### 백로그 (차단 아님)
①verify.py cm 정규식 음수 미허용→"스케일cm" FAIL(engine 수정 승인 필요) ②shrink 등방한계 ③preset sizes.scale 미사용 ④number/name_area piece_id 유효성 검증 없음 ⑤svg_index 높이정렬 가정 사이즈확장 시 재확인 ⑥A-4 이름 세로정렬 descent 무시로 받침 ~3.6pt 삐짐 ⑦A-5 상하의 사이즈 분리(현 상의만) ⑧A-5 신양식 '작성하기' 단일시트 0행(SCOOP·싸이클론 추가주문서)

### 설계 보존 (상세는 git 히스토리 / decisions.md)
- **A-2 패턴로딩**(보류, 코드0%): pattern_loader.py 신설 / pattern_file→<name>.svg 폴백 / 개수·종횡비30% 안전망 / 누락 부분성공. 실제 전 사이즈 패턴 확보 시 재개.
- **A-4 배번/이름**(완료): text.py 글리프→PDF큐빅경로 + Piece.extra_ops. CLI --number/--name.
- **A-5 주문서 파싱**(완료): order.py 양식①/② 자동판별, 시트 표식우선, 아동호수, 부분실패. CLI order.

### 실데이터 / git
- 디자인 실데이터: ../grader/illustrator-scripts/test/ (design_XL.ai, pattern_XS.svg)
- 주문서 실데이터: `G:/공유 드라이브/CHINA FACTORY/프랭크웨어 주문서/0.중국 프랭크웨어 주문서/` xlsx 86개
- 폰트: data/fonts/Pretendard-Black(배번)/Bold(이름).otf
- git: origin=cobby8/grader-v2, main. **미푸시 0개**(A-4/자료/A-5 푸시 완료). 최신 927b7b6 푸시됨.

## 기획설계 (planner-architect)

### 기획설계 — Phase D 재설계: 기존 path SVG 활용 + path→polyline 전처리 변환기  [2026-06-19]

🎯 목표: 이미 만들어둔 V넥 패턴 SVG 13개(직선 폴리라인 path)를 parse_svg 무수정으로 그레이딩에 쓰기 위해, **path→polyline 전처리 변환기(신규 모듈)** 로 U넥과 같은 형식의 polyline SVG를 생성하고, V넥 preset.json을 작성한다. 13개 일괄 변환·검증까지.

────────────────────────────────────────────────────────
📊 실측 분석 결과 (XL.svg + U넥 XS.svg 직접 파싱·좌표계산으로 확정)
────────────────────────────────────────────────────────
**(가) V넥 XL.svg 구조** (viewBox `0 0 4478.74 3401.57` = 마커시트, 가로 긴):
- `<path>` 8개. **곡선 명령 전무**(M/H/L/V만, C/Q/S/A 0개) → 전부 직선 폴리라인. transform 전부 `matrix(1,0,0,-1,tx,ty)`(y반전+평행이동).
- path별 matrix 적용+flip_y(PDF좌표 y=vbh-y) 후 bbox:

  | path | pts | 형태 | bbox(시트, flip 후) | 판정 |
  |------|-----|------|------|------|
  | [1] | 106 | **닫힘**(V자 넥, 중앙바닥 y2568) | x[391..2160] y[556..2910] w1769 h2354 | **앞판**(왼쪽, 깊은 V넥) |
  | [0] | 114 | **닫힘**(얕은 U자 넥 y2780) | x[2254..4023] y[556..2908] w1769 h2352 | **뒤판**(오른쪽) |
  | [4] | 2 | 세로선 | x3139 y[584..2751] | 보조선(앞중심접는선) 제외 |
  | [7] | 2 | 세로선 | x1275 y[584..2422] | 보조선 제외 |
  | [2][3] | 3 | 수평선(h=0) | x[2283..3995] y≈627/641 | 보조선(밑단표식) 제외 |
  | [5][6] | 3 | 수평선(h=0) | x[419..2131] y≈626/640 | 보조선 제외 |

- **결론1**: 닫힌(면적 있는) 조각은 **앞판·뒤판 2개뿐**. path[2~7]은 폭만 있거나 세로선인 보조선(접는선·밑단표식)이라 제외 대상.
- **결론2 ⛔**: **소매 윤곽 조각이 V넥 SVG에 없다.** U넥은 소매(idx2, x[539..2123] y[2502..2678] h176 띠) polyline이 있지만 V넥엔 소매에 해당하는 닫힌 조각이 0개. (meta.json `pieceCount:1`도 단순화된 값.)
- 앞/뒤 판정 근거: 의뢰서 §4 앞/뒤 분할 x=2239.37 → path[1]=왼쪽(앞), path[0]=오른쪽(뒤)과 일치. 넥라인도 path[1]이 깊은 V(앞판 V넥), path[0]이 얕은 넥(뒤판)으로 디자인 상식 일치.

**(나) parse_svg 호환성 실측**: U넥 XS.svg `parse_svg`→**3조각 정상**. V넥 XL.svg `parse_svg`→**0조각**(polyline/polygon 태그가 없어 path를 못 읽음). 검증 완료.

**(다) parse_svg svg_index(높이 내림차순) 가정**: 변환 후 polyline이 앞·뒤 2개뿐이면 높이정렬 시 앞(h2354)>뒤(h2352)로 **앞=idx0, 뒤=idx1**이 된다(U넥은 뒤>앞>소매라 뒤=idx0, 앞=idx1, 소매=idx2였음 — 순서 다름!). → preset svg_index를 V넥 실제 정렬에 맞춰 지정해야 함(아래 preset 참고). 높이차 2pt로 근소하나 사이즈별로 역전 가능 → **변환기가 조각 순서를 안정적으로 보장**하거나 preset에서 명시 매핑이 필요(주의사항 참조).

**(라) 좌표계 정합(차단이력 핵심) 정리**: 3좌표계 존재 —
  ① 마커시트(패턴 SVG): V넥 XL viewBox 4478.74×**3401.57**, 조각 y[556..2910]. U넥 XS도 4337×3401(둘 다 가로 긴 마커시트). parse_svg가 flip_y로 PDF좌표(y위로) 변환.
  ② design_XL 펼침본(디자인 AI): 4478.74×**5669.29**, content_box[468,2877,3997,5562]. 의뢰서 §4 완성본 좌표(앞번호center[1389,4184]·뒤[3217,4342]·이름 등)·scratchpad 확정좌표(앞판영역[468,2877,2098,5287] 등)는 **전부 이 펼침본 기준**.
  ③ design_region_pt는 ②(펼침본) 좌표로 적고, _piece_transform이 ①(마커시트 조각 bbox)에 앵커정렬+contain으로 얹는다 → **두 좌표계는 _piece_transform이 자동 정합**(스케일·평행이동). 즉 design_region_pt는 ②좌표 그대로 쓰면 되고, 조각 bbox는 변환된 polyline에서 자동으로 ① 좌표가 나온다. **Phase C job의 _job_piece_transform·방식A가 이미 이 정합을 수행** → V넥도 동일 공식으로 동작(코드 무수정).

🎯 핵심 판단: **parse_svg를 고치지 말고, path SVG를 읽어 U넥과 동일한 polyline SVG로 다시 써주는 전처리 변환기를 신규 모듈로 추가**한다(불변 제약 §6 준수). 변환은 1회성(또는 빌드 단계)이고, 산출 polyline SVG를 preset.sizes가 가리키면 이후 엔진은 V넥을 U넥과 똑같이 취급.

📍 만들 위치와 구조 (건물의 층별 안내도):
| 파일 경로 | 역할 | 신규/수정 |
|----------|------|----------|
| engine/svg_normalize.py | **path→polyline 전처리 변환기**(핵심 신규). path d(M/H/L/V 직선) 좌표전개 + matrix(a,b,c,d,e,f) 적용 → polyline points → U넥형 polyline SVG로 출력. 곡선(C/Q/S/A) 폴백은 평탄화 샘플링 인터페이스만 마련(현재 미사용) | 신규 |
| engine/cli.py | `normalize-svg` 서브커맨드 추가(단일/배치 변환 + 변환 후 parse_svg 조각수 자동 확인) | 수정(추가만) |
| data/patterns/농구_V넥_양면/ | V넥 패턴 폴더(신규). 변환된 polyline SVG 13개 + preset.json | 신규 |
| data/patterns/농구_V넥_양면/<size>.svg | 변환 산출 polyline SVG 13개(5XS~5XL) | 신규(변환 생성) |
| data/patterns/농구_V넥_양면/preset.json | V넥 preset(design·sizes·pieces·area·shrink) | 신규 |

🧩 1) path→polyline 전처리 변환기 설계 (engine/svg_normalize.py):
공개 함수(제안):
```
normalize_svg_paths(in_svg_path, out_svg_path, *, min_points=3, drop_open=True,
                    flatten_curves=False, samples=16) -> dict
```
- **읽기**: ElementTree로 `<path>` 순회. 각 path의 `d`와 `transform`(matrix) 추출.
- **d 파서**: 절대/상대 직선 명령 전개 — M/m(시작·이동), L/l(선), H/h(수평), V/v(수직), Z/z(닫기=시작점 복귀). 현재 좌표(cx,cy) 누적. (parse_svg가 쓰는 토큰화와 동형: `[MmLlHhVvZzCcQqSsAa]|숫자` 정규식.)
- **matrix 적용**: `transform="matrix(a,b,c,d,e,f)"` 파싱 → 각 점 `x'=a*x+c*y+e, y'=b*x+d*y+f`. (V넥은 모두 (1,0,0,-1,tx,ty)이나 일반 6요소 행렬 지원.)
- **출력 좌표계**: matrix 적용 결과는 viewBox 좌표(y아래로). polyline SVG도 **viewBox 좌표 그대로** points에 쓴다(parse_svg가 자체적으로 flip_y하므로 변환기는 flip 안 함 — U넥 SVG도 viewBox 좌표로 저장돼 있음. 이중 flip 방지 핵심!).
- **조각 필터**: 닫힌(또는 점≥min_points이고 bbox 폭·높이 둘 다>임계) path만 polyline으로. drop_open=True면 열린 보조선(세로선·수평선)은 제외. (V넥 path[2~7] 자동 제외 → 앞·뒤 2개만 남음.)
- **곡선 폴백(인터페이스만)**: flatten_curves=True일 때 C/Q/S/A를 samples 등분 평탄화 샘플링으로 점 전개(다른 패턴에서 곡선 섞일 때 대비). V넥은 곡선 0이라 현재 미사용. 곡선 만나면 flatten_curves=False면 경고+건너뜀(또는 직선근사).
- **출력 SVG**: U넥과 동일 골격 — `<svg viewBox="0 0 W H"><polyline class="st0" points="x y x y ..."/>...</svg>`. viewBox는 입력 SVG의 viewBox 그대로 복사(W=4478.74 H=3401.57). class/style은 선택(parse_svg는 무시). 조각 순서는 **원본 path 순서 유지**(앞=path1→첫 polyline) — 단 parse_svg가 높이 내림차순 재정렬하므로 preset svg_index는 정렬 후 기준으로 지정.
- **반환 dict**: `{in, out, viewBox, pieces_written:N, dropped_open:M, has_curves:bool, bboxes:[...]}`(검증·디버깅용).
- **불변 제약**: parse_svg/Polyline 등 engine 공개 API 무수정. 이 모듈은 parse_svg와 같은 입력형식(polyline)을 만들어내는 **앞단 도구**일 뿐(engine 코어 미접촉). pattern.py에 함수 추가하지 않음(계층 분리, decisions A-2 패턴로딩 원칙과 동일).

🧩 2) 조각 매핑 (V넥 path 8개 → 3조각? 2조각!):
- **앞판 = path[1]**(닫힘, 깊은 V넥, x[391..2160]), **뒤판 = path[0]**(닫힘, 얕은 넥, x[2254..4023]).
- **소매 = 없음** ⛔ — V넥 SVG에 소매 닫힌 윤곽이 부재(실측). path[2~7]은 전부 보조선.
- 따라서 V넥 preset pieces는 **앞/뒤 2개**가 1차 현실(아래 잔존 리스크 (가) 참조 — 사용자 결정 필요).
- svg_index: 변환 후 polyline 2개 → parse_svg 높이정렬(앞h2354>뒤h2352) → **앞=idx0, 뒤=idx1**(U넥과 반대 순서!). preset에 정확히 매핑.
- U넥 3 polyline vs V넥 8 path 이유: U넥은 일러 "SVG Export Plug-In"이 **닫힌 윤곽만 polyline 3개**(앞·뒤·소매)로 깔끔히 출력. V넥은 PyMuPDF/inkscape류가 **모든 스트로크(보조선 포함)를 path로** 내보냄 → 8개(닫힌 2 + 보조선 6). 변환기가 보조선을 걸러 2개로 정리.

🧩 3) 좌표계 정합 (위 (라) 결론 적용):
- design_region_pt는 **design_XL 펼침본(4478×5669) 좌표**로 적는다(scratchpad 확정좌표 재사용). 앞판[468,2877,2098,5287]/뒤판[2310,2877,3997,5287]을 1차 그대로 사용(U넥 값 — V넥도 같은 디자인 펼침 레이아웃이면 동일. 다르면 reference로 재추출).
- 조각 bbox는 변환 polyline에서 자동(마커시트 좌표). _piece_transform/_job_piece_transform이 design_region(펼침)→조각bbox(마커)로 앵커+contain 정합 → **추가 좌표변환 코드 불필요**(Phase C 방식A 그대로). 글자(앞/뒤 번호·이름)도 _wrap_design_ops가 같은 transform으로 감싸므로 자동 정합.
- ⚠️ 단 design_region_pt가 U넥 펼침본 값이라 V넥 펼침 레이아웃이 다르면 위치 어긋남 → **빈템플릿/완성본 확보 후 reference로 V넥 실값 재추출**(잔존 리스크 (나)).

🧩 4) V넥 preset.json 구조 (data/patterns/농구_V넥_양면/preset.json):
```jsonc
{
  "preset_name": "농구_V넥_양면",
  "design": {
    "base_size": "XL",
    "design_file": "template_XL.ai",          // 빈템플릿 placeholder(미확보 시 명시)
    "page_size_pt": [4478.74, 5669.29],
    "content_box": [468.0, 2877.0, 3997.0, 5562.0]
  },
  "sizes": [ {"name":"5XS","pattern_file":"5XS.svg","scale":1.0}, ... 13개 ... {"name":"5XL",...} ],
  "pieces": [
    {"id":"front","name":"앞판","svg_index":0,"design_region_pt":[468.0,2877.0,2098.0,5287.0]},
    {"id":"back", "name":"뒤판","svg_index":1,"design_region_pt":[2310.0,2877.0,3997.0,5287.0]}
    // sleeve: 소매 조각 부재 → 잔존 리스크 (가) 결정 후 추가/생략
  ],
  "design_mapping": {"mode":"anchor","anchor":"bottom-left","fit":"contain","preserve_aspect":true},
  "front_number_area": {"piece_id":"front","center":[1389,4184],"cap_height":310,"color_cmyk":[0,0,0,0],"font":"data/fonts/HY헤드라인M.ttf"},
  "back_number_area":  {"piece_id":"back","center":[3217,4342],"cap_height":539,"color_cmyk":[0,0,0,0],"font":"data/fonts/HY헤드라인M.ttf"},
  "back_name_area":    {"piece_id":"back","center_x":3219.8,"baseline":4765.7,"em_pt":136.40,"pitch":195.4,"color_cmyk":[0,0,0,0],"font":"data/fonts/HY헤드라인M.ttf"},
  "shrink": {"x":1.0,"y":1.0}
}
```
- area 3개는 의뢰서 §4 V넥 완성본 수치(이미 U넥 preset에 들어가 있는 값과 동일 — 원래 V넥 연세대 완성본에서 뽑은 값이라 V넥에 정확). svg_index는 **앞=0/뒤=1**(U넥과 반대) 주의.
- number_area/name_area(구 rel_bbox 폴백)는 넣지 않음 — 새 area 3개만으로 Phase C 정밀경로 사용(use_precise=True).

🧩 5) 13개 일괄 변환 + 검증 워크플로:
- (a) 변환: `python -m engine normalize-svg --in-dir "G:/.../V넥 양면유니폼 스탠다드" --pattern "양면유니폼_V넥_스탠다드_{size}.svg" --out-dir data/patterns/농구_V넥_양면 --sizes 5XS,4XS,3XS,2XS,XS,S,M,L,XL,2XL,3XL,4XL,5XL` → out-dir에 `<size>.svg` 13개(.bak/.meta.json 제외).
- (b) 각 변환본 조각수 자동확인(변환기 반환 pieces_written + parse_svg 재파싱): 13개 전부 **2조각** 기대. 0이나 1이면 실패 표식.
- (c) CLI 한 줄 검증: `python -c "from engine.pattern import parse_svg; print([len(parse_svg(f'data/patterns/농구_V넥_양면/{s}.svg')) for s in '5XS 4XS 3XS 2XS XS S M L XL 2XL 3XL 4XL 5XL'.split()])"` → `[2,2,...,2]` 기대.
- (d) svg_index 안정성: 13개 각각 앞h vs 뒤h 출력해 정렬 역전(앞<뒤) 사이즈 없는지 확인. 역전 있으면 변환기가 **조각에 id/순서 메타를 polyline에 부여**하거나 preset를 사이즈별 분기(드물면 변환기에서 면적·x위치 기준 안정 정렬 권장).

🧩 6) Phase E 연결 (job 실행까지):
- 빈템플릿(template_XL.ai 또는 .pdf) 확보 → preset.design.design_file에 경로.
- 실행: `python -m engine job --preset data/patterns/농구_V넥_양면/preset.json --design <빈템플릿> --order <주문서.xlsx> --out data/jobs/<날짜_주문명>` → 선수별 PDF + verify PASS.
- job 코드는 **무수정**(Phase C가 새 area 3개·precise 경로·flatten·좌표변환 다 처리). preset만 바꾸면 동작.
- cowork에 산출 PDF 1~2개 보내 시각 정합 최종확인(번호·이름 위치).

⛔ 막히는 가정(명시):
- (가) **소매 조각 부재** — V넥 SVG에 소매 닫힌 윤곽 없음. → 사용자 결정: ①V넥은 소매 없는 디자인(앞/뒤만 출력)인가? ②소매가 별 파일/별 폴더에 있나? ③앞/뒤만으로 1차 진행 후 소매 추가? (1차 설계는 앞/뒤 2조각 전제.)
- (나) **design_region_pt 좌표계** — U넥 펼침본 값 재사용. V넥 펼침 레이아웃이 다르면 위치 어긋남 → 빈템플릿/완성본으로 reference 재추출 필요.
- (다) **빈템플릿 미확보** — design_file은 placeholder. 확보 전 Phase E job 실행 불가(스모크는 design_XL.ai로 대체 가능).
- (라) **svg_index 정렬 역전** — 앞·뒤 높이차 2pt로 사이즈별 역전 가능. 변환기 안정정렬 또는 preset 검증으로 방어.

📋 실행 계획 (최대 7단계):
| 순서 | 작업 | 담당 | 선행 조건 |
|------|------|------|----------|
| 1 | engine/svg_normalize.py 신설: normalize_svg_paths(d파서 M/H/L/V·matrix적용·보조선필터·viewBox좌표 polyline출력·곡선폴백 인터페이스) | developer | 없음 |
| 2 | engine/cli.py에 `normalize-svg` 서브커맨드(단일/배치 --in-dir/--pattern/--out-dir/--sizes + 변환후 조각수 자동확인) | developer | 1 |
| 3 | 13개 일괄 변환 실행 → data/patterns/농구_V넥_양면/*.svg 생성 + 전 사이즈 parse_svg 조각수=2 확인(svg_index 역전 점검) | developer | 2 |
| 4 | data/patterns/농구_V넥_양면/preset.json 작성(앞=idx0/뒤=idx1, area 3개, design_file placeholder) | developer | 3 |
| 5 | tester 검증 + reviewer 리뷰 (병렬): 변환정확성(bbox 원본대비)·조각수·selftest회귀·불변제약(parse_svg diff 0)·preset스키마 | tester + reviewer | 1~4 |
| 6 | (필요시) 수정 반영 | developer | 5 |
| 7 | (사용자 결정·빈템플릿 확보 후) Phase E job 스모크 — design_XL.ai 또는 빈템플릿으로 run_job verify PASS 확인 | developer | 5, 사용자입력 |

⚠️ developer 주의사항:
- **불변 제약 절대**: parse_svg/Polyline/compose/Piece/SizeLayout/scale_translate/verify_output·build_layouts/grade **무수정**. svg_normalize.py는 독립 신규 모듈(engine 코어 import 안 함 — ElementTree만). pattern.py에 함수 추가 금지(계층분리).
- **이중 flip 금지(핵심 함정)**: 변환기는 matrix만 적용하고 **flip_y 하지 않는다**. 출력 polyline points는 viewBox 좌표(y아래로) 그대로. parse_svg가 읽을 때 자체 flip_y한다. U넥 SVG도 viewBox좌표 저장이라 동일. 변환기가 flip하면 parse_svg가 또 flip→상하반전.
- **viewBox 그대로 복사**: 출력 SVG viewBox = 입력 viewBox(4478.74 3401.57). 임의 변경 금지(parse_svg가 flip 기준높이로 vb_h 사용).
- **보조선 필터 기준**: 닫힘(시작=끝) OR (점≥3 AND bbox폭>임계 AND bbox높이>임계). V넥은 닫힘 여부로 앞·뒤만 통과. 임계는 페이지 대비 비율(예 폭·높이 각 >5%)로 — 작은 표식 제외, 큰 조각만.
- **svg_index 매핑**: 변환 후 parse_svg는 높이 내림차순. V넥 앞(h2354)>뒤(h2352)라 **앞=0, 뒤=1**. preset에 그대로. (U넥은 뒤=0,앞=1,소매=2였으니 복붙 주의!) 사이즈별 역전 가능성 단계3에서 확인.
- **소매 처리**: 1차는 앞/뒤 2 pieces. 사용자가 소매 별파일 주거나 "소매 없음" 확정 전까지 sleeve 미정의(있으면 svg_index 초과 ValueError로 job이 행 skip하니 안전하나, 의도된 2조각이어야 함).
- **design_region_pt**: U넥 펼침값 재사용(1차). reference로 V넥 재추출은 빈템플릿 확보 후.
- **곡선 폴백**: 현재 V넥 곡선0이라 미발동. 인터페이스(flatten_curves/samples)만 만들고 본구현은 후속(YAGNI — 지금 직선만 정확히).
- CLI 한 줄 재현 완료기준: 위 워크플로 (a)(c). 한글 콘솔은 cli.py _force_utf8_console 흐름 안.

────────────────────────────────────────────────────────
### (요약 보존) 기획설계 — job(선수별 통합 출력) engine/job.py  [2026-06-18] ✅구현완료(Phase C)
run_job(preset, design_pdf, order_rows, out_dir, font_path, split="per_player")→{outputs,summary}. grade()는 단일값·전사이즈1PDF라 못 씀 → preset 얕은복제 후 sizes 1개로 좁혀 build_layouts 호출(공개API무수정). per_player(파일별)/single(다페이지). 재사용: load_preset/build_layouts/compose/parse_order/verify_output/preview. 원자쓰기 tmp→os.replace. Phase C에서 flatten선적용+정밀배치 place_*+좌표변환(_job_piece_transform=_piece_transform복제)·area3개까지 통합 완료. **상세 원문은 git 히스토리 / 아래 구현·테스트·리뷰 기록 참조.**

<details><summary>(접힘) job 설계 원문</summary>

### 기획설계 — job(선수별 통합 출력) engine/job.py 신설  [2026-06-18]

🎯 목표: 주문서 행(선수)마다 그 선수의 사이즈 1페이지에 배번/이름을 갈아끼운 PDF를 per_player(기본) 또는 single로 한 벌 생성. 모든 출력 verify PASS, CLI 한 줄 재현.

📍 만들 위치와 구조 (건물의 층별 안내도):
| 파일 경로 | 역할 | 신규/수정 |
|----------|------|----------|
| engine/job.py | run_job(): 주문행×디자인→선수별 출력 오케스트레이터(응용 계층, grade.py와 동급) | 신규 |
| engine/cli.py | `job` 서브커맨드 추가(--preset/--design/--order/--out/--font/--split) | 수정(추가만) |
| data/jobs/<날짜_주문명>/output/ | 출력 폴더(per_player: 선수별 PDF / single: 1PDF) | 신규(런타임 생성) |
| data/jobs/<날짜_주문명>/job.json | 결과 summary 덤프(폴더+JSON 원칙) | 신규(런타임 생성) |
| data/jobs/<날짜_주문명>/preview/ | 검수용 PNG(옵션) | 신규(런타임 생성) |

💡 핵심 설계 판단 (왜 grade()를 못 쓰고 job.py가 필요한가):
- grade()는 number/name "단일 값"으로 **전 사이즈 1PDF**를 만든다. 실작업 단위는 **선수별**(같은 사이즈도 이름·배번 다름) + 선수는 **자기 사이즈 1페이지만** 필요.
- 불변 제약: build_layouts/grade 공개 시그니처 변경 금지(신규 인자는 기본값만). 사이즈 필터 인자를 새로 넣는 대신 **preset dict를 얕은 복제 후 sizes를 해당 1개로 좁혀** build_layouts에 넘긴다(공개 API 무수정). 이게 job.py가 떠안는 핵심 일.
- 즉 job.py = "식당 주방장": 주문서(주문 전표) 한 장씩 보고, 그 선수의 사이즈 레시피만 골라 배번/이름 얹어 1인분(=1 PDF/1 페이지) 굽는다. 오븐(compose)·레시피해석(build_layouts)·검수(verify)는 기존 것 그대로 호출.

🔗 기존 코드 재사용 지점 (레고 블록 재조립):
- engine/grade.py: load_preset(preset_path)로 preset 로드 → **preset dict 복제 후 sizes를 1개로 좁힘** → build_layouts(sized_preset, design, number=, name=, warnings=)로 SizeLayout 1개 생성. (grade()는 전사이즈+1PDF라 그대로 못 씀 → build_layouts를 직접 호출)
- engine/compose.py: compose(design, [layout], out_pdf, design_page=0) → 무손실 CMYK PDF. per_player=선수마다 [layout1개] 1회 호출, single=[layout들] 모아 1회 호출.
- engine/order.py: parse_order(xlsx, warnings) → [{name,number,size,qty}]. job이 입력 받는 두 경로: (a) xlsx 경로 받아 내부에서 parse_order 호출, (b) order_rows(이미 파싱된 리스트) 직접 받음. **인터페이스는 order_rows를 받되**, CLI는 xlsx→parse_order→run_job.
- engine/verify.py: verify_output(out_pdf, design, placements) → checks. 각 출력 PDF마다 호출, all_passed로 PASS 집계. 반환 dict의 outputs[].checks에 담음.
- engine/preview.py: render_previews / render_page → 검수 PNG(옵션, 기본 생성, --no-preview로 끔).
- engine/text.py: 직접 호출 안 함(build_layouts 내부 _apply_text_area가 이미 호출). number/name만 넘기면 됨.

🧩 인터페이스 (확정 초안 준수):
```
run_job(preset, design_pdf, order_rows, out_dir, font_path, split="per_player") -> dict
```
- preset: preset.json 경로(str). 내부에서 load_preset. (dict도 허용하면 웹앱 편하나 1차는 경로 str로 통일)
- design_pdf: 기준 디자인(.ai/.pdf) 경로.
- order_rows: parse_order 결과 [{name,number,size,qty}] 리스트.
- out_dir: 작업 루트(예: data/jobs/<날짜_주문명>/). 내부에서 output/·preview/ 생성.
- font_path: 폰트 루트 경로(현재 preset의 number_area/name_area에 font가 박혀 있어 사실상 미사용 → **1차는 받되 미사용+주석, 추후 area.font 오버라이드 훅으로 활용**. 인터페이스 안정성 위해 시그니처엔 유지).
- split: "per_player"(기본, 파일별) | "single"(다페이지 1PDF).
- 반환:
```
{
  "outputs": [
    {"size":"L","name":"김민수","number":"7","pdf":"output/L_07_김민수.pdf",
     "preview":"preview/L_07_김민수.png","checks":[{name,ok,detail}...],"verify_pass":true}
  ],
  "summary": {"job_dir":..., "split":"per_player", "total_players":N, "produced":N,
              "verify_pass":N, "verify_fail":N, "skipped":[{row,reason}...],
              "warnings":[...], "missing_sizes":[...]}
}
```

🔄 데이터 흐름 (주문 전표 → 완성품):
1. load_preset(preset) → preset dict. preset["sizes"]에서 사용 가능한 사이즈 집합 S 추출.
2. order_rows 순회. 각 행 r:
   - r.size가 빈값/S에 없음 → skip(summary.skipped에 사유 기록, 크래시 금지).
   - preset 얕은 복제 sized = {**preset, "sizes":[그 사이즈 dict]} (나머지 키·_dir 유지).
   - layouts = build_layouts(sized, design_pdf, number=r.number, name=r.name, warnings=warns) → SizeLayout 1개.
   - per_player: out=output/<size>_<번호zero-pad>_<safe이름>.pdf. compose(design, layouts, tmp, design_page=0)=placements. verify_output(out_pdf, design, placements). (옵션)preview.
   - single 모드: 각 행의 layout(이름=size_number_name 식별자)을 누적 리스트에 모음 → 루프 후 1회 compose로 다페이지 1PDF.
3. single: compose(design, all_layouts, output/<주문명>_all.pdf) 1회 → verify_output(..., total_placements) 1회.
4. 원자적 쓰기: 모든 출력은 임시파일(tmp/ 또는 .part)에 쓰고 os.replace로 최종 경로 rename. 중간 실패 시 부분물 안 남김.
5. summary + outputs를 job.json으로 덤프(폴더+JSON 원칙).

🛡️ 엣지케이스 / 실패 처리 (보안 검색대):
- 빈 사이즈/미인식 사이즈 행: skip + skipped 기록(주문서 86개 중 사이즈 인식 실패 행 존재 — order.py가 이미 빈값 허용).
- preset.sizes에 없는 사이즈(예: 주문은 4XL인데 패턴 폴더에 없음): skip + missing_sizes 집계 + 경고. (백로그 A-2 전사이즈 확보 전까지 흔함 → 부분성공으로 흘림, 전부 실패일 때만 비정상 종료코드)
- 글리프 누락(이름에 폰트 없는 한자/이모지): text.py가 해당 텍스트 통째 미출력+경고 → 그 선수 PDF는 글자 없이라도 생성되되 warnings에 누적(outputs[].checks와 별개로). 사람이 검수.
- 동명이인/같은 번호 파일명 충돌: 파일명에 행 인덱스 접미사(_r03 등) 또는 size_number_name 조합으로 유일화. 충돌 시 _2 접미사.
- 파일명 안전화: 한글 OK, 경로 금지문자(/\:*?"<>|)는 _로 치환, 공백 trim, 빈 이름은 "noname".
- 배번 zero-pad: 정렬·식별 편의로 2자리(07). 단 원본 번호 보존이 우선이면 그대로(결정: 파일명만 zero-pad, 출력 글자는 원본 그대로 — text는 r.number 원본 전달).
- pikepdf 출력 비결정적(XObject 이름 랜덤): 회귀 테스트는 바이트동일 대신 "XObject 이름 정규화 후 콘텐츠 비교"(errors.md). job 자체 동작엔 영향 없음(verify_output은 바이트동일 Form 1개만 확인하므로 PASS).
- 디자인/preset/폰트 누락: load_preset·build_layouts가 친절한 한글 FileNotFoundError → run_job은 그대로 전파(시작 전 차단이 안전).
- out_dir 기존 존재: output/ 안 동명 파일은 덮어씀(재실행 가능). 원자적 rename이라 부분 갱신 안전.

📋 실행 계획 (최대 7단계):
| 순서 | 작업 | 담당 | 선행 조건 |
|------|------|------|----------|
| 1 | engine/job.py 신설: run_job() + 내부 헬퍼(_safe_name, _atomic_save, preset 사이즈 좁히기, per_player/single 분기) | developer | 없음 |
| 2 | engine/cli.py에 `job` 서브커맨드 추가(xlsx→parse_order→run_job, summary 출력) | developer | 1 |
| 3 | tester 검증 + reviewer 리뷰 (병렬) | tester + reviewer | 1,2 |
| 4 | (필요시) 수정 반영 | developer | 3 |

⚠️ developer 주의사항:
- 불변 제약 절대 준수: compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output **시그니처·동작 무수정**. build_layouts/grade도 무수정(있는 인자만 사용). 사이즈 좁히기는 **preset dict 복제**로 처리(원본 preset 변형 금지 — _dir 등 보존).
- preset 복제는 얕은 복제로 충분하나 "sizes"만 새 리스트로 교체({**preset, "sizes":[one]}). number_area/name_area/_dir 등은 공유 OK(읽기만).
- build_layouts는 디자인 존재검사·SVG파싱을 매 호출 반복한다(선수 수만큼). 60명이면 60회 parse_svg. **느리면** preset 사이즈별 layout을 캐시(사이즈→base layout)하고 number/name만 다시 주입하는 최적화 가능하나, **1차는 단순하게 매번 build_layouts 호출**(가장 단순 우선). compose도 디자인을 매번 다시 연다(per_player라 어쩔 수 없음). single은 1회라 빠름.
- 원자적 쓰기: pikepdf compose는 out_path에 직접 저장하므로, tmp 경로로 compose→os.replace(tmp, final). verify는 final 경로로(또는 tmp로 검증 후 rename).
- per_player verify는 selftest처럼 6사이즈가 아니라 **1페이지(placements=조각수, 보통 3)**. verify_output의 "배치 횟수 일치"가 그 placements와 맞아야 함(compose 반환값 그대로 넘기면 자동).
- 폴더명 <날짜_주문명>은 run_job 밖(CLI)에서 정해 out_dir로 넘기는 게 깔끔. run_job은 받은 out_dir 아래 output/preview/job.json만 만든다(역할 분리).
- 한글 콘솔 안전: cli.py에 이미 _force_utf8_console 있음. job summary 출력도 그 흐름 안.
- CLI 한 줄 재현 완료기준 예: `python -m engine job --preset data/patterns/농구_U넥_양면/preset.json --design <design.ai> --order <order.xlsx> --out data/jobs/<날짜_주문명>`

📌 백로그 영향 검토 의견:
- ④ number/name_area piece_id 유효성: grade.py _apply_text_area가 이미 piece_id 못 찾으면 경고+건너뜀 처리됨(코드 확인). job은 이 경고를 warnings로 수집만 하면 됨. **추가 작업 불필요**, 단 job summary에 노출 권장.
- ⑦ 상하의 사이즈 분리: order.py는 현재 상의(C열)만 size로 반환. job도 1차는 그 size로 상의 패턴만 출력. 하의 패턴/사이즈가 별 preset로 분리되면 run_job을 상·하 각각 호출하거나 garment 인자 확장 필요 → **1차 범위 밖, 인터페이스는 단일 garment 전제**. 향후 order_rows에 top_size/bottom_size 분리 + preset에 garment 구분이 들어오면 run_job 루프를 (행×garment)로 확장(기본값 인자로 호환). 지금은 영향 없음(상의만).
- (추가) split=single일 때 페이지 순서: 사이즈→번호 정렬 권장(공장 작업 편의). 1차는 order_rows 입력 순서 유지(단순), 정렬은 옵션 백로그.

</details>

## 구현 기록 (developer)

### Phase E — STIZ 신양식③ 주문서 파서 + 연세대 V넥 38건 선수별 PDF 생성  [2026-06-19] ✅**완료**

📝 구현한 기능: STIZ '작성하기' 신양식③(순번|이니셜|배번|사이즈(상의/하의)|비고 헤더) 파서를 order.py(응용계층)에만 추가하고, 그 주문서로 V넥 양면 38건 선수별 PDF를 job으로 생성·전수 검증. engine 코어 전부 무수정.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/order.py | `_norm_header` nbsp(\xa0) 제거 보강 + `_parse_form_stiz` 신양식③ 파서 추가 + 헤더키워드(_HEADER_SEQ/_HEADER_NOTE)·_QTY_NUM_PATTERN 추가 + parse_order 자동판별에 ①→③→② 순 끼워넣기 | 수정(+114/-4) |

🔧 신양식③ 파서 핵심:
- 헤더 탐색: 한 행에 '순번'+'이니셜'+'사이즈'가 모두 있어야 ③로 식별(양식①은 '순번' 컬럼 없어 충돌 없음).
- 컬럼을 키워드로 동적 매핑(순번/이니셜=이름/배번/사이즈/비고). 이름=B열, 배번=C열(양식①과 위치 다름).
- 부제행("상의/하의") 1행 skip → 상의 사이즈(col_size) 사용.
- 비고 "4장"→4 추출(_QTY_NUM_PATTERN). 없으면 qty="1".
- 핵심 결측행(이름·배번·사이즈 모두 빈 행=순번만 미리 적힌 39~100행) skip.
- `_norm_header`: \xa0(nbsp)도 공백처럼 제거(신양식 헤더 '\xa0이니셜','순\xa0\xa0 번' 매칭 위함). 양식①/② 헤더엔 nbsp 없어 무손상.

📊 파싱 결과(검증 PASS): 260213 연세대 추가주문서 → **유효 38행 / 11명** (이해솔1·최영상2·이주영5·김승우6·이채형7·이병엽9·홍상민10·김상현12·박준성13·김윤서22·장혁준11), 사이즈 XS·S·M·L·XL·2XL·3XL, qty "1"~"6" 정상 추출. warnings 0.

📦 job summary(per_player): **total_players 38 / produced 38 / verify_pass 38 / verify_fail 0 / skipped [] / missing_sizes [] / warnings [] / precise_placement True**. 작업폴더 data/jobs/260619_연세대V넥/ (output 38 PDF + preview 38 PNG + job.json).

🖼️ 미리보기 육안확인(필수, 6건 PASS): XS 김승우6·M 이해솔1·L 이채형7·XL 김윤서22·2XL 이주영5·3XL 김윤서22 — 전부 **앞판(YONSEI+번호)·뒤판(이름+번호) 둘 다 캔버스 안 정위치, 앞판 소실 없음**(Phase D 되돌림 교훈 준수). 모든 page rect 가로(w>h). 흰 글자 정렬 정상.

🔒 금지연산자 전수 0(대표 6건): Do=2(앞/뒤만)·rg/RG=0·scn=0(별색없음)·gs=0(투명도없음)·inline BI=0. k(CMYK fill)=3=앞번호+뒤번호+이름(글자 k fill만). 디자인 device CMYK 무손실(verify PASS).

🤝 cowork 시각검증용 PDF(절대경로):
- XL: `C:\0. Programing\grader-v2\data\jobs\260619_연세대V넥\output\XL_22_김윤서.pdf` (§4 비교용)
- 비-XL: `C:\0. Programing\grader-v2\data\jobs\260619_연세대V넥\output\2XL_05_이주영.pdf`

✅ 회귀: selftest PASS / 양식①(순번 없음·이름 A열) 무손상(stiz파서 0행 반환=충돌없음) / 기존 실주문서 3개(126·32·39행) 정상 파싱.

🧩 불변 제약 준수(§6): git diff = **engine/order.py 1파일만**(+114/-4). engine 공개 API·job·svg_normalize·grade·build_layouts·compose·verify 변경 0줄. data/jobs/는 .gitignore(출력 미커밋). order.py만 커밋 대상.

💡 tester 참고:
- 파싱 재현: `python -c "from engine.order import parse_order; w=[]; print(len(parse_order(r'C:/Users/user/Desktop/새 폴더/260213_연세대학교 레플리카_농구유니폼_추가주문서.xlsx', w)), w)"` → (38, [])
- job 재현: 상단 CLI 한 줄(--split per_player). 정상이면 produced 38/verify_pass 38.
- 주의 입력: 신양식 헤더 nbsp(\xa0)·"순번만 적힌 빈 행"·비고 "N장" → 전부 처리됨. 양식①/② 무손상 확인 필수.

⚠️ reviewer 참고:
- `_parse_form_stiz` 헤더 식별 조건(순번+이니셜+사이즈 동시)이 양식①과 충돌 안 하는지(①은 순번 없음).
- `_norm_header` nbsp 보강이 양식①/② 헤더 매칭에 영향 없는지(nbsp 미포함이라 무손상).
- 자동판별 순서 ①→③→② — ①이 0행이어야 ③ 진입. 신양식은 ①에서 헤더('이니셜' 있으나 컬럼 배치 달라) 부분 매칭 가능성? → 실측상 ①은 0행(데이터 시작행 판정에서 막힘), ③에서 38행. 확인 권장.

### Phase D 되돌림1 — 방식(A) 실행: 원본 .ai 13개 동일출처 재변환(좌표계 오염 해소)  [2026-06-19] ✅**완료**

📝 구현한 기능: tester 수정요청(비-XL 12개 SVG 좌표계 오염 → 앞판 소실)을 **승인된 방식(A)** 로 해소. `.ai → path SVG` 추출을 **별도 보조 스크립트**(scripts/ai_to_path_svg.py)로 신설하고, 그 뒤 **기존 normalize-svg CLI 그대로** 사용해 원본 .ai 13개(XL 포함 전부)를 **동일 출처·동일 viewBox(가로 4478×3401)** 로 재변환·덮어쓰기. engine 공개 API·cli·svg_normalize 코어 **전부 무수정**(scripts/ 신규 + 데이터 재생성만).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| scripts/ai_to_path_svg.py | .ai→path SVG 추출 보조 스크립트(fitz.get_svg_image(text_as_path=True), 단일/배치, %!PS-헤더 보고, 원자쓰기). engine 미import, fitz만 | 신규(폴더 생성) |
| data/patterns/농구_V넥_양면/{5XS~5XL}.svg | 원본 .ai 13개 재변환 polyline SVG로 덮어쓰기(viewBox 가로 3401·양수 좌표·앞=idx0/뒤=idx1) | 재생성(덮어쓰기) |

🔧 파이프라인(2단계, engine 무수정):
1. `python scripts/ai_to_path_svg.py --in-dir "G:/…/V넥 양면유니폼 스탠다드" --pattern "양면유니폼_V넥_스탠다드_{size}.ai" --out-dir "data/_tmp_path_svg" --sizes 5XS,…,5XL` → path SVG 13개(임시). 13개 전부 viewBox `0 0 4478.74 3401.57`·path 8·헤더 %PDF- 확인.
2. `python -m engine normalize-svg --in-dir "data/_tmp_path_svg" --pattern "{size}.svg" --out-dir "data/patterns/농구_V넥_양면" --sizes 5XS,…,5XL` → polyline SVG 13개 덮어쓰기. 13개 전부 written=2 / dropped(open=0 small=6 dup=0) **일관**(이전 비-XL은 dup 발생했으나 정상출처라 dup=0).
3. 검증 후 임시 폴더 data/_tmp_path_svg/ 및 검증 job 출력 정리.

🩺 근본원인 해소: 이전 커밋된 비-XL 12개는 다른 출처(viewBox 세로 5669 + 음수 좌표)에서 변환돼 앞판이 캔버스 밖으로 소실. **원본 .ai를 PyMuPDF로 추출하면 13개 전부 viewBox 가로 3401·양수**(실측)라 동일 좌표계로 통일됨.

✅ 검증 결과(전수 PASS — 표는 tester 재검증 참고):
- **13개 viewBox 전부 `0 0 4478.74 3401.57`(가로)** — 교체 전 12개 세로 5669 → 전부 가로로 통일.
- **13개 조각수=2** + **앞=idx0(왼쪽 cx≈1100~1376)/뒤=idx1(오른쪽 cx≈3076~3349)** 13개 일관(앞h≥뒤h, 역전 0).
- **13개 전 조각 좌표 양수**(min x,y ≥ 0, 음수 0건 — 소실 원인 제거).
- **selftest 회귀 PASS**(코어 무수정, U넥 영향 0).
- **preset.json 유효**(load_preset OK, sizes 13, pieces front:0/back:1, area 3개 전부 존재 — SVG만 교체, preset 무변경).
- **비-XL 육안확인(필수) 완료**: 빈템플릿(연세대 V넥 XL 템플릿.ai) base로 5XS·M·L·XL·5XL per_player 실행 → 미리보기 PNG 5장 모두 **앞판·뒤판 둘 다 캔버스 안 정위치, 앞판 소실 없음**. (5XS 오민기/5, M 문대성/23, L 이정후/51, XL 김경원/20, 5XL 강백호/10 — 앞 YONSEI+번호 / 뒤 이름+번호, 흰색 정위치).
- **page rect 정상**: 5개 PDF 전부 가로(w>h). 이전 비-XL 세로 길쭉(M 2811×5351) → 해소(M 4165.5×2785.9 등).
- **verify_output PASS**: 5개 전부 모든 체크 PASS(디자인 무손실·CMYK 계열·투명도 없음·Do 2회(앞/뒤)·래스터 미추가).
- **금지연산자 0**: 페이지 스트림 scn(별색)=0, rg/RG=0, ca/CA≠1=0, inline image=0, k(CMYK fill)=3(앞번호+뒤번호+이름). produced 5/verify_pass 5/verify_fail 0/skipped 0/missing 0, precise_placement=True, flatten transparency_left=[].

📌 별색 오인 주의(검증 메모): 디자인 Form **내부** scn 카운트가 보이지만, 해당 컬러스페이스 /CS0는 별색(Separation/DeviceN)이 아니라 **/ICCBased /N 4 (ICC 기반 CMYK 4채널)**. 빈템플릿 .ai 자체 색이며 verify가 "CMYK 계열 유지 PASS"로 인정. 페이지 스트림 scn=0이라 금지연산자 기준 충족.

🧩 불변 제약 준수(git diff): engine 코어(pattern/compose/verify/job/grade/text/svg_normalize/preview/flatten/pdfutil) 변경 **0줄**. 이번 작업 변경 = scripts/ai_to_path_svg.py 신규 + 데이터 SVG 13개 재생성뿐. (cli.py 73+/0-은 이전 Phase D 미커밋분이며 이번에 무수정.)

💡 tester 재검증 참고:
- 재현: 위 2단계 파이프라인(임시 폴더는 정리됨 — 재실행 시 --out-dir 임시로 다시 추출 후 normalize-svg).
- 조각수+viewBox 한줄검증: `python -c "import re; from engine.pattern import parse_svg; [print(s, re.search('viewBox=\"([^\"]+)\"', open(f'data/patterns/농구_V넥_양면/{s}.svg',encoding='utf-8').read()).group(1), len(parse_svg(f'data/patterns/농구_V넥_양면/{s}.svg'))) for s in '5XS 4XS 3XS 2XS XS S M L XL 2XL 3XL 4XL 5XL'.split()]"` → 13개 전부 viewBox 3401 / 조각 2.
- **핵심 재검증**: 비-XL 미리보기 육안으로 앞판 존재 + page rect 가로(w>h) 확인(tester가 지적한 "초록불 4개 켜져도 깨질 수 있음"의 진짜 판정 기준).
- 주의: 좌표 미세 정합은 cowork 오버레이 권장(의뢰서 §7-4). 곡선 섞인 SVG는 변환기가 끝점 직선근사+경고(현 데이터엔 곡선 0).

### Phase D-1 (ai_to_svg.jsx) — 일러스트레이터 SVG 직접 내보내기 스크립트 신설  [2026-06-19]

📝 구현한 기능: Phase D 차단의 **해결책 (A)** 자동화 — .ai 사이즈 원본을 일러스트레이터 "SVG Export Plug-In"으로 직접 내보내 polyline 3조각·소매 보존 SVG를 **배치로** 생성하는 ExtendScript. (PyMuPDF 변환은 path라 parse_svg 0개 + 소매 소실 → 이 경로로 우회)

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| illustrator-scripts/ai_to_svg.jsx | .ai→.svg 배치 변환 JSX(폴더 신규 생성) | 신규 |

🔧 설계 핵심:
- 골격: grader(v1)/illustrator-scripts/ai_to_pdf.jsx 그대로(IIFE / 같은폴더 input.json 읽기→result.json 쓰기 / 최상위 try-catch로 result 보장 / app.open→처리→doc.close(DONOTSAVECHANGES)).
- 차이: saveAs(PDF) 대신 doc.exportFile(outFile, ExportType.SVG, svgOpts). 단일 아니라 **jobs 배열 순회**(배치). job마다 try/catch+finally close라 1개 실패해도 나머지 계속.
- input.json **두 스키마**: ①{"jobs":[{input_path,output_path}...]} ②{"input_dir","output_dir","sizes":[...],"name_pattern":"..._{size}.ai"}→내부 jobs 전개({size} 치환, 출력=사이즈명.svg). 둘 다 공통 jobs로 정규화.
- SVGExportOptions: cssProperties=ENTITIES(U넥처럼 <style>+class), coordinatePrecision=2, fontType=OUTLINEFONT, embedRasterImages=false, documentEncoding=UTF8.
- 출력 폴더 없으면 parent.create(). result.json: job별 success/output_path/output_size + summary{total,ok,fail}.
- 파일 상단 한글 주석: 방식①/② 작성 예, File→Scripts→Other Script 실행법, result 확인법, **polyline 보존 리스크 경고**(직선→polyline✅ / 곡선섞임→path❌ → parse_svg 0조각, 1개 먼저 시험변환 권장), 변환검증 한 줄(`python -c "from engine.pattern import parse_svg; print(len(parse_svg('...XL.svg')))"` → 조각수, 0이면 path로 떨어진 것).

⚠️ ExtendScript 문법 self-review 완료: var만(let/const 없음), JSON.parse/stringify(CC2014+), File/Folder 객체·parent.create(), for 루프만(forEach/화살표/템플릿리터럴 미사용), 정규식 replace(/g). engine 코드 무수정(JSX 독립 산출물, 파이썬 미접촉).

💡 tester 참고:
- 이 스크립트는 **일러스트레이터 GUI에서 사용자 수동 실행**(Python/CLI 자동 테스트 불가). tester는 (a)JSX 문법 정적 검토 (b)입력 정규화 로직(방식①②→jobs)의 의도 일치 정도만 검토 가능.
- 실동작 검증은 사용자가 1개 사이즈 시험 변환 후 위 "변환검증 한 줄"로 조각수 확인(3 나오면 정상, 0이면 path 떨어짐). 이건 사용자 단계.

⚠️ reviewer 참고:
- SVGExportOptions 옵션명/Enum(SVGCSSPropertyLocation.ENTITIES, SVGFontType.OUTLINEFONT, ExportType.SVG)이 실제 일러스트 ExtendScript DOM과 일치하는지(버전별 차이) 확인 권장. documentEncoding은 try로 감쌈(미지원 버전 안전).
- 곡선 패스가 polyline으로 안 떨어지는 건 export 옵션으로 100% 보장 못 함(일러스트가 곡선이면 path 출력) → 주석 경고가 사용자 검증을 유도하는 게 핵심.

### Phase D 구현 — V넥 preset+패턴 변환  [2026-06-19]  ⛔ **차단(사용자 확인 필요)**

📌 진행: 사전 조사·진단까지 완료. 코드 작성 전 단계에서 **본질적 차단 2건** 발견 → 추측 진행 중단·보고.

✅ 확인된 사실(긍정):
- V넥 스탠다드 패턴 .ai **13개 전부 존재**(5XS~5XL, 소매 별도파일 없음).
- 13개 전부 헤더 `%PDF-1.6` → PyMuPDF `get_svg_image(text_as_path=True)` 변환 가능(%!PS- 없음).
- 페이지 4478.74×3401.57(가로 긴 마커시트). 의뢰서 §4 완성본은 4478.74×**5669.29**(세로 긴 펼침). 다른 좌표계(architecture.md 3좌표계 지식과 일치 — 패턴 SVG ≠ 디자인 AI).

⛔ 차단 1 — **변환 산출 SVG가 parse_svg와 비호환**(조각 0개로 읽힘):
- 기존 U넥 패턴 SVG는 일러스트레이터 "SVG Export Plug-In"이 만든 `<polyline>` 3개 → parse_svg 정상.
- 그러나 의뢰서가 지정한 PyMuPDF 변환은 `<path>` + path별 개별 `matrix(1,0,0,-1,tx,ty)` 출력. parse_svg는 polyline/polygon만 읽음 → **PyMuPDF V넥XL.svg를 parse_svg로 파싱 시 조각 0개**(실측 확인). 그대로는 그레이딩 불가.
- 해결안은 있음(엔진 무수정): PyMuPDF `get_drawings()`로 윤곽 점 추출 후 polyline SVG로 **재생성**하는 변환 헬퍼. 큰 조각(앞226점/뒤210점)은 추출 성공 확인.

⛔ 차단 2 — **소매 조각이 PyMuPDF 변환에서 사라짐**(앞/뒤 2개만):
- U넥 검증본 SVG는 조각 **3개**(뒤 h2192/앞 h2084/**소매 h175 띠**). 그런데 동일 U넥 .ai를 PyMuPDF로 변환하면 닫힌 조각 **2개**(앞/뒤)만, 소매 자리엔 폭1485 수평선 4개(열린 선분)만 남음.
- V넥도 동일: PyMuPDF get_drawings 큰조각 2개(앞 x[2254..4023]/뒤 x[390..2159], 각 w≈1769 h≈2352)뿐, 소매에 해당하는 닫힌 윤곽 없음(보조선만 #2~#7).
- 즉 PyMuPDF 경로로는 **소매 design_region_pt를 산출할 조각이 없음**. U넥 preset처럼 sleeve(svg_idx2) 매핑 불가.

🔻 그 결과 막힌 후속:
- design_region_pt(앞/뒤/소매)를 V넥 기준으로 산출 못 함(소매 없음 + 좌표계가 완성본과 달라 scratchpad 확정 좌표 그대로 못 씀 — 그건 design_XL 펼침본 기준).
- design_file(빈 템플릿) 미확보(의뢰서도 §5 "미확보" 명시) → preset design_file은 placeholder.

❓ 사용자 결정 필요(택1 이상):
- (A) 패턴 변환을 **일러스트레이터 SVG Export Plug-In**으로(U넥처럼) 직접 내보낸 .svg를 받기 → polyline·소매 3조각 보장, parse_svg 즉시 호환. **가장 깔끔**(권장).
- (B) PyMuPDF 변환을 쓰되, **get_drawings→polyline 재생성 헬퍼**를 신설(엔진 무수정). 단 소매는 분리선분 재구성 로직이 추가로 필요(추측 영역) → 정합 위험.
- (C) V넥에 **소매 조각이 실제로 없는 디자인**인지 확인(앞/뒤만 출력?) → 그렇다면 preset pieces를 앞/뒤 2개로.
- 공통: **빈 템플릿(design_file) 확보 시점** 확인 필요.

#### 수정 이력
| 회차 | 날짜 | 수정 내용 | 수정 파일 | 사유 |
|------|------|----------|----------|------|
| 1차 | 2026-06-19 | 차단 전면 해소 → Phase D 구현 완료(아래 별도 기록) | svg_normalize.py(신규)·cli.py·V넥 폴더 | 사용자가 결정·자료(기존 V넥 path SVG 13개+빈템플릿+완성본) 확보 후 재착수 |

### Phase D 구현 — V넥 변환기(svg_normalize.py)+preset+패턴+스모크  [2026-06-19] ✅**완료**

📝 구현한 기능: 기존 V넥 path SVG 13개(직선 d 명령)를 parse_svg 무수정으로 쓰기 위해 **path→polyline 전처리 변환기**(신규 모듈)를 만들어 U넥형 polyline SVG로 변환하고, V넥 preset.json 작성 + job 스모크(빈템플릿)로 verify PASS 확인. **불변 제약 전부 준수**(parse_svg/compose/Piece/SizeLayout/scale_translate/verify_output/build_layouts/grade/job/text/flatten 무수정 — 신규 모듈 + cli 서브커맨드 추가 + preset/SVG 데이터만).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/svg_normalize.py | path SVG→polyline SVG 변환기(d파서 M/H/L/V·matrix적용·보조선/중복필터·원자쓰기). engine 코어 미접촉(stdlib만) | 신규 |
| engine/cli.py | `normalize-svg` 서브커맨드(단일/배치 + 변환후 parse_svg 조각수 자동확인). 기존 명령 무수정 | 수정(추가만) |
| data/patterns/농구_V넥_양면/{5XS~5XL}.svg | 변환 산출 polyline SVG 13개 | 신규(변환생성) |
| data/patterns/농구_V넥_양면/preset.json | V넥 preset(앞=idx0/뒤=idx1, area 3개, design_file=빈템플릿명) | 신규 |
| .gitignore | `data/jobs/` 추가(스모크 산출 PDF/PNG 제외 — 큰 .ai도 미커밋) | 수정 |

🔬 설계 실측과 다른 점(전수 분석 후 변환기가 흡수):
- **곡선 전무**(M/H/L/V만) — 설계대로 확인. 직선 전개로 정확 변환.
- **Z(닫기) 명령 없음** — 면적 조각도 시작점=끝점(gap≈0)으로만 닫힘 → 변환기 닫힘판정=시작≈끝(1pt 이내).
- **XL만 특수**: viewBox 가로(4478×3401)·큰조각 2개. **나머지 12개**: viewBox 세로(4478×5669)에 앞·뒤판이 위·아래 2벌씩 중복 → 큰조각 4개. → 변환기가 bbox(폭·높이·중심) 근사동일 **중복 제거**로 전부 앞/뒤 2조각으로 통일.
- 보조선(세로 접는선·수평 밑단선)은 폭/높이 한쪽 0 또는 점<3 → 필터 제외.

✅ 검증 결과(전부 통과):
- **13개 변환 조각수=2 전수**: `[2,2,2,2,2,2,2,2,2,2,2,2,2]` (parse_svg 재파싱 확인).
- **selftest 회귀 PASS**(기존 기능 무손상).
- **preset 유효 JSON + load_preset OK**(sizes 13, pieces front/back).
- **job 스모크 PASS**: 빈템플릿(연세대 V넥 XL 템플릿.ai)으로 김경원/20(XL)·이순신/7(M) per_player → produced 2 / verify_pass 2 / verify_fail 0 / skipped 0. precise_placement=True, flatten 적용(transparency_left=[]).
- **금지연산자 0**: 출력 PDF에 RGB(rg/RG) 0·별색(scn) 0·Image XObject 0·ExtGState ca/CA 전부 1.0. 글자 k(CMYK) fill 3회(앞번호+뒤번호+이름)=정확 주입. Do 2회=앞/뒤 디자인 Form(정상).
- **미리보기 시각확인**: 앞판 YONSEI+앞번호20, 뒤판 김경원+뒤번호20 모두 정위치·흰색(0,0,0,0). 의뢰서 §4 완성본 재현 일치.

🧭 svg_index 매핑 근거: 변환 후 parse_svg 높이정렬에서 **13개 전 사이즈 모두 앞(왼쪽,약간 높음)=idx0 / 뒤(오른쪽,약간 낮음)=idx1**로 일관(앞h>뒤h, 차이 ~2pt). 앞/뒤 판정은 원본 path 왼쪽=앞(깊은 V넥, 의뢰서 §4 분할 x=2239.37 왼=앞)으로 확정. → preset svg_index front:0/back:1.

📐 design_region_pt 산출근거/리스크:
- 앞 [468,2877,2098,5287] / 뒤 [2310,2877,3997,5287] — **U넥 값 재사용**. 이 값은 연세대 V넥 완성본에서 도출·검증된 펼침본(4478×5669) 좌표라 V넥에 그대로 유효. area center(앞x1389/뒤x3217)와도 정합(분할 x2239.37 기준 좌/우 안에 위치).
- 교차확인: 빈템플릿 콘텐츠 bbox 앞x[452.6..2260.8]y[2605.9..5513.8]/뒤x[2332.7..4101.3]y[2605.9..5357.0] — design_region과 근사(콘텐츠 bbox엔 작은 표식 포함되어 약간 넓음). 스모크 시각결과가 정합 양호.
- ⚠️ 리스크: design_region은 디자인 부위를 조각 bbox에 contain하므로 미세 위치차 가능. cowork 오버레이로 최종 정밀확인 권장(의뢰서 §7-4).

⛔ 잔여(차단 아님):
- **소매 조각 없음**: V넥 SVG에 소매 닫힌 윤곽 부재(실측) → 앞/뒤 2 pieces로 진행. 사용자 "앞/뒤 2조각" 확정과 일치.
- **주문서 신양식 미파싱**: 의뢰서 지정 추가주문서(260213…xlsx)는 단일시트 '작성하기' 신양식(백로그⑧)이라 order.py가 0행 반환 → 스모크는 §4 김경원/20을 order_rows로 직접 주입. 실주문 파싱은 A-5 후속 범위.
- **svg_index 정렬 역전 가능성**: 앞·뒤 높이차 ~2pt로 작음. 현재 13개 전수 앞=idx0 일관 확인했으나, 향후 다른 V넥 계열(슬림 등) 추가 시 재점검 필요(백로그⑤와 동일 성격).

💡 tester 참고:
- 회귀: `python -m engine selftest` → PASS.
- 변환 재현: `python -m engine normalize-svg --in-dir "<G드라이브 V넥폴더>" --pattern "양면유니폼_V넥_스탠다드_{size}.svg" --out-dir "data/patterns/농구_V넥_양면" --sizes 5XS,4XS,3XS,2XS,XS,S,M,L,XL,2XL,3XL,4XL,5XL` → 13개 모두 ✅ 조각 2개.
- 조각수 한줄검증: `python -c "from engine.pattern import parse_svg; print([len(parse_svg(f'data/patterns/농구_V넥_양면/{s}.svg')) for s in '5XS 4XS 3XS 2XS XS S M L XL 2XL 3XL 4XL 5XL'.split()])"` → 전부 2.
- job 스모크(빈템플릿 경로는 사용자 Desktop): `engine.job.run_job(PRESET, 빈템플릿.ai, [{name,number,size,qty}], OUT)` → verify_pass=produced, verify_fail=0.
- 정상 동작: 미리보기 PNG에서 앞=번호(작게)·뒤=이름+번호(크게) 흰색 정위치. 출력 PDF에 RGB/별색/이미지/투명도 0.
- 주의할 입력: design_region 미세 위치차(cowork 오버레이 권장) / 다른 V넥 계열은 svg_index 재점검 / 곡선 섞인 SVG는 변환기가 끝점 직선근사+경고(현재 데이터엔 없음).

⚠️ reviewer 참고:
- 봐줬으면 하는 부분: ①svg_normalize 닫힘판정(시작≈끝 1pt 임계)·중복제거(bbox tol=페이지×1%)·보조선필터(min_dim_ratio 5%) 임계가 13개 모두 안정적인가(다른 패턴 일반화 시 견고성). ②이중flip 방지(변환기 flip 안 함, parse_svg가 flip) 정확성. ③cli normalize-svg 단일/배치 인자분기·에러처리. ④preset svg_index 앞0/뒤1이 U넥(뒤0/앞1)과 반대인 점이 의도대로인지.

### Phase B 구현 — 정밀 배치 함수 + reference 모듈/CLI  [2026-06-19]

📝 구현한 기능: 완성본 실측 수치(높이·중심·자간)를 그대로 재현하는 정밀 배치 함수 2개(text.py) + 완성본에서 preset area JSON 초안을 자동 추출하는 reference 보강 + `engine reference` CLI.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/text.py | place_number/place_name + 헬퍼 _glyph_ink_bounds 추가(기존 render_text_ops/_glyph_path_ops/_load_glyphset 무수정), ControlBoundsPen import | 수정(추가만) |
| engine/reference.py | build_area_preset/_name_from_rawdict/_number_area_from_cluster 추가(기존 extract_reference 무수정) | 수정(추가만) |
| engine/cli.py | cmd_reference + `reference` 서브커맨드 추가(기존 명령 무수정) | 수정(추가만) |

추가 함수 시그니처:
- `place_number(text, font, cap_h_pt, center_x, center_y, color) -> (ops, warnings)` — 대표 자릿 잉크높이로 scale, advance×s 배치 후 center_x 가운데정렬, baseline=center_y-((yMin+yMax)/2)*s.
- `place_name(text, font, em_pt, pitch_pt, baseline_y, center_x, color) -> (ops, warnings)` — scale=em_pt/upm, 음절을 pitch 간격 고정·center_x 가운데정렬·baseline 고정, 공백 음절은 피치 한 칸.
- `build_area_preset(design_path, page_index=0, page_width=None, font=...) -> {page_size, split_x, areas{front_number_area, back_number_area, back_name_area}, name_detail, warnings}` — 번호=pikepdf(extract_reference 재사용), 이름=fitz rawdict.
- CLI: `python -m engine reference --완성본 R.ai [--템플릿 T.ai] [--json out] [--font ...]`

💡 tester 참고:
- 검증 방법: `python -m engine selftest`(회귀) + place_number/place_name 좌표 bbox 계산 + `python -m engine reference --완성본 ../grader/illustrator-scripts/test/design_XL.ai`.
- 정상 동작: ops가 q…Q 래핑·CMYK `k` fill·m/l/c 경로만(Do/RGB/ca/CA 금지), 빈값=무출력, 잘못된 cap/em/pitch=경고+건너뜀, 누락 글리프=통째 미출력+경고.
- 검증 결과(design_XL.ai = 의뢰서 §4 완성본):
  · selftest 종합 PASS(회귀 0).
  · place_number 앞(cap310/c1389,4184): 잉크높이 310.0/세로중심 4184.0 정확, 가로중심 1387.6~1387.9(목표1389, 사이드베어링 비대칭 ~1.4pt). 뒤(cap539/c3217,4342): 잉크높이 539.0/세로중심 4342.0 정확, 가로중심 ~3215(목표3217 ~2.4pt). 한자리/두자리 모두 가운데정렬.
  · place_name(em136.4/pitch195.4/cx3219.8/bl4765.7): bbox x[2965.7..3468.3] vs 완성본 x[2956.2..3483.5], y[4747.2..4879.5] vs 완성본 y[4744.3..4882.7] 거의 일치.
  · reference: 페이지 4478.74x5669.29, 앞 center[1389.2,4184.4] cap309.8, 뒤 center[3217.1,4342.4] cap538.6, 이름 center_x3219.8 baseline4765.7 em136.4 pitch195.5 font H2hdrM — 전부 §4 일치.

⚠️ reviewer 참고:
- 번호 가로중심 ~1-3pt 오차는 글리프 좌우 사이드베어링 비대칭(advance 중앙≠잉크 중앙). 의뢰서 §4가 "번호 세로중심·폭 미세 조정 여지 — cowork 오버레이 재검증" 명시한 정상 범위. 필요 시 advance중심 대신 '전체 잉크 bbox 중심'을 center_x에 맞추는 보정 가능(후속 판단).
- 이름 pitch는 비공백 음절 origin 간격 중앙값으로 계산(완성본 '김 경 원' 공백+Tc 자간 → 공백 char 제외해야 195.4 나옴).
- 불변 제약 준수: 공개 API/build_layouts/grade 무수정, device CMYK·`k` fill만, 빌드0.

### Phase C 구현 — 통합 배관(flatten + 정밀배치 place_* + 좌표변환 감싸기)  [2026-06-19]

📝 구현한 기능: job 파이프라인에 (1)디자인 투명도 선평탄화 (2)preset 새 area 3개(front/back_number_area·back_name_area) 기반 place_number/place_name 정밀배치 (3)디자인좌표 글자 ops를 그 조각 transform(cm)으로 감싸 시트좌표에 박는 좌표변환을 연결. Phase B 부품들을 하나의 흐름으로 묶는 "배관 검증" 완료.

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| data/patterns/농구_U넥_양면/preset.json | front_number_area/back_number_area/back_name_area 3개 추가(기존 number_area/name_area 유지). 각 area에 piece_id 부여(감쌀 조각 결정용) | 수정(추가만) |
| engine/job.py | flatten 선적용 + 정밀배치 경로(_build_precise_layout/_job_piece_transform/_wrap_design_ops/_has_precise_areas) + base_design(평탄화본) 사용 + summary에 flatten/precise 노출 | 수정 |

🔧 job 동작 흐름(Phase C):
1. run_job 시작 시 base 디자인 1회 flatten_transparency → out_dir/_flattened_design.pdf. 이후 모든 compose/verify가 이 평탄화본(base_design)을 기준으로 사용. 실패해도 원본 폴백(verify가 최종 판정).
2. preset에 새 area 있으면(use_precise=True) 정밀 경로: 사이즈별 parse_svg → 조각 윤곽 + _job_piece_transform(grade.py _piece_transform 동일공식 복제, grade.py 무수정).
3. place_number(앞·뒤)·place_name(이름)으로 디자인좌표 글자 ops 생성 → _wrap_design_ops로 그 조각 transform(cm)으로 감싸 Piece.extra_ops에 누적. 앞=front 조각, 뒤번호·이름=back 조각. 앞·뒤 번호는 같은 배번.
4. 새 area 없으면 기존 build_layouts(rel_bbox) 폴백 — 완전 호환.
5. split per_player/single 기존 분기 그대로.

🔑 좌표변환 핵심: place_*는 '디자인좌표'(완성본 center 등)로 ops 생성. compose의 extra_ops는 piece q…Do…Q '밖'(시트좌표)에서 그려짐 → `q [s 0 0 s ox oy cm] [글자ops] Q`로 직접 감싸 디자인배치와 동일 변환을 글자에 적용. (grade.py 방식A와 같은 s/ox/oy)

✅ 검증 결과(전부 PASS):
- ① selftest 종합 PASS, inkcov 편차 0.000000(회귀 0).
- ② per_player(7번 홍길동, 20번 김경원, XS): produced 2/verify_pass 2/fail 0. precise_placement=True. flatten 적용 확인(bg CMYK[0.8,0.5,0,0.1] 자동감지, /Fm0 평탄화, recolored 1, alpha gstate 2→1.0, transparency_left=[]).
- PDF 콘텐츠 검증: Do 3회(조각3), k fill 3개(앞·뒤번호+이름, `0 0 0 0 k`), f 3회, c(큐빅)47/89개(글자윤곽 실주입), cm 6개(디자인배치3+글자감싸기3). 골격구조 확인: 글자감싸기 cm = 같은조각 디자인배치 cm와 동일행렬(front 0.8651.., back 0.9098..).
- ③ single: produced 1/verify_pass 1, 2페이지(page1 홍길동/page2 김경원), 각 page Do=3 k=3 RGB=0 caCA=0.
- ④ 금지연산자 전무: RGB(rg/RG)=0, ca/CA=0, gs=0, 인라인이미지=0. (한/두자리 번호 모두 처리)

💡 tester 참고:
- 검증 재현: `python -m engine selftest`(회귀) + 스모크는 run_job(preset, '../grader/illustrator-scripts/test/design_XL.ai', [{name,number,size:'XS',qty}], out, split=...) 직접 호출(또는 cli job --order xlsx).
- 정상 동작: produced=선수수, verify_pass=produced, precise_placement=True, flatten.transparency_left=[]. PDF 콘텐츠에 Do=조각수, k fill=주입글자수(앞번호+뒤번호+이름=최대3), cm=Do수×2, RGB/ca/CA/gs/이미지=0.
- 주의 입력: 빈 number/name → 그 글자만 미주입(k fill 개수 감소, 정상). 누락 글리프 이름 → 통째 미출력+warnings. 사이즈 빈값/preset에 없는 사이즈 → skip+missing_sizes(부분성공).
- ⚠️ 좌표 정합 자체는 V넥 완성본 수치라 U넥에선 위치가 안 맞을 수 있음(스모크 목적이라 OK). 실제 V넥 정합은 Phase D/E. Phase C 검증 포인트는 "배관이 흐르는가"(글자 주입·좌표변환·평탄화·verify PASS)지 "위치가 정확한가"가 아님.

⚠️ reviewer 참고:
- 좌표변환 감싸기 검증 포인트(핵심): _wrap_design_ops가 만든 글자 블록의 cm 행렬이 _build_precise_layout에서 그 조각에 계산한 transform과 100% 동일해야 함(앞번호=front transform, 뒤번호/이름=back transform). 위 골격구조 출력으로 육안 확인됨(front 0.8651/184.84, back 0.9098/213.49).
- _job_piece_transform은 grade.py _piece_transform의 '복제'(grade.py가 _접두 내부함수라 무수정 원칙). 두 함수 수식이 어긋나면 글자가 디자인과 어긋남 → 향후 grade._piece_transform 변경 시 job쪽도 동기화 필요(주석에 명시함).
- _resolve_font_path는 복제 대신 grade.py에서 import(호출만) — 동작 일치 보장, grade.py 무수정.
- 불변 제약 준수: grade/compose/verify/text/pdfutil/flatten/pattern 전부 git diff 0(무수정). 변경 코드파일은 job.py 1개 + preset.json. device CMYK k fill만, 빌드0.
- flatten은 행 루프 밖 1회만(선수마다 재평탄화 안 함). 평탄화본은 out_dir/_flattened_design.pdf로 남음(검수/디버깅용, 정리 필요시 후속).

## 테스트 결과 (tester)

### Phase E 독립 검증 [2026-06-19] — ✅ 종합 PASS (7/7) → **완료기준 §7 전 항목 달성**

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ 통과 | 6사이즈 24배치 9개 PASS, inkcov 편차 0.000000, 종합 PASS. order.py 변경이 코어/job/grade 영향 0(git status: order.py 1파일만 M) |
| 2) 신양식③ 파싱 | ✅ 통과 | **유효 38행/11명** 전수 일치(이해솔1·최영상2·이주영5·김승우6·이채형7·이병엽9·홍상민10·김상현12·박준성13·김윤서22·장혁준11). 사이즈 XS·S·M·L·XL·2XL·3XL, qty "N장"→숫자 정확(이주영 XL=6장 등). nbsp 헤더 인식·warnings 0 |
| 3) ★기존 양식 회귀★ | ✅ 통과 | 실주문서 3개(호바스 32행·ATLAS 39행·신도고 12행) 정상 파싱. **stiz파서가 기존 양식 시트에서 잡은 수=0**(신양식③ 분기가 양식①/② 무손상, 충돌 0). 양식①(이름 A열·순번 없음) 정상 |
| 4) job 완료기준 CLI 재현 | ✅ 통과 | `job --preset 농구_V넥_양면 --design 빈템플릿.ai --order 추가주문서.xlsx --out _etest` → **produced 38/verify_pass 38/fail 0/skipped[]/missing[]/warnings[]/precise=True** 재현. summary 11키 전부 존재 |
| 5) ★미리보기 육안(필수)★ | ✅ 통과 | 대표 6건(XS 김승우6·M 이해솔1·L 이채형7·XL 김윤서22·2XL 이주영5·3XL 홍상민10) PNG **전부 앞판(YONSEI+번호)·뒤판(이름+번호) 둘 다 캔버스 안 정위치, 앞판 소실 없음**. **page rect 6개 전수 가로**(XS 3897×2748~3XL 4283×2863). Phase D FAIL(세로 길쭉·앞판소실) 재발 없음. 1자리·2자리 번호 모두 정상 |
| 6) verify 38 + 금지연산자 | ✅ 통과 | verify 38/38 PASS. **38건 전수 Do=2(앞/뒤)·k=3(앞·뒤번호+이름 CMYK fill) 균일**, rg/RG·scn·gs·BI(inline)·ca/CA=0건(전수). 글자 k fill만 |
| 7) 엣지(다중사이즈·빈/결측행) | ✅ 통과 | 이주영(배번5) 6벌이 S/M/L/XL/2XL/3XL 파일명 충돌 없이 구분(38개 PDF 경로 전수 unique). 실시트 100행 중 순번만 적힌 빈행 62개 skip→38행. 합성엣지(부제행/순번만/전부빈) 정확 skip, qty없음→"1" 폴백 |

📊 종합: 7개 전부 통과 / 0개 실패 → **종합 PASS** (수정 요청 없음)

🎯 **완료기준 §7 달성 판정**: §7-1(selftest PASS) ✅ / §7-3(job 선수별 PDF 38건 전부 verify PASS, CLI 한 줄 재현) ✅ / §7-4(번호·이름 위치 — 미리보기 육안 정위치 확인, cowork 오버레이 정밀재검증은 잔여) → **§7 핵심 완료기준 달성**. (Phase D 데이터결함은 되돌림1로 해소, 본 Phase E에서 재발 0 재확인)

⚠️ Phase D 함정 재점검(errors.md [2026-06-19]): 13개 패턴 SVG viewBox **전수 동일(0 0 4478.74 3401.57 가로)**·조각 bbox **음수/초과 0건**·조각수=2·앞=idx0(왼)/뒤=idx1(오) 13개 일관. "조각수2+verify PASS" 초록불에 더해 (a)viewBox전수동일 (b)좌표 viewBox내 (c)page rect 가로 (d)미리보기 육안 4중 점검 전부 통과.

검증 환경: Python 3.11.9 / fitz 1.27.2.3 / pikepdf 10.8.0 / openpyxl. 빈템플릿=C:/Users/user/Desktop/새 폴더/…V넥…XL - 템플릿.ai. 주문서=동 폴더 260213…추가주문서.xlsx. 임시출력 data/jobs/_etest 정리 완료. order.py는 아직 미커밋(작업트리 M) — Phase E 커밋 대상.

### Phase B 독립 검증 [2026-06-19] — 종합 PASS (15/15)

| 테스트 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ 통과 | 6사이즈 24배치, 9개 PASS + inkcov 편차 0.000000, 종합 PASS |
| 2) place_number 잉크높이 | ✅ 통과 | 한자리 정확(오차0), 두자리 +0.7~1.2(대표글리프 기준 정상) |
| 2) place_number 세로중심 | ✅ 통과 | 한자리 오차0, 두자리 +0.34~0.60 |
| 2) place_number 가로중심 | ✅ 통과 | 앞-1.07/-1.37, 뒤-1.86/-2.39 모두 ±3pt 이내(§4 사이드베어링 인정범위) |
| 3) place_name 김경원 bbox | ✅ 통과 | x[2965.7..3468.3] y[4747.2..4879.5], 완성본 실측 대비 최대 -15.1pt(폭) 근접 |
| 4) ops 무결성 | ✅ 통과 | 연산자 집합={q,Q,k,f,h,m,l,c}만. Do/RGB/ca/CA/gs/sc 전무(§6 준수) |
| 5) 엣지: 빈값/None | ✅ 통과 | 빈ops 반환, 크래시 없음 |
| 5) 엣지: cap_h 0/음수 | ✅ 통과 | 경고+빈결과 |
| 5) 엣지: em_pt 0/pitch 음수 | ✅ 통과 | 경고+빈결과 |
| 5) 엣지: 누락글리프(漢/🎉) | ✅ 통과 | 통째 미출력+경고 |
| 6) reference 완성본 추출 | ✅ 통과 | 페이지·분할·앞뒤center·cap·이름cx/bl/em/pitch/font 전부 §4 일치 |
| 6) reference --help | ✅ 통과 | usage 정상 출력 |
| 6) reference --json 저장 | ✅ 통과 | preset 스키마(front/back_number_area·back_name_area) 일치 |
| 7) 템플릿 생략(완성본 단독) | ✅ 통과 | 정상 동작. 템플릿 명시 시 안내메시지 후 동일 결과 |
| (부가) 없는 완성본 에러처리 | ✅ 통과 | "찾지 못했습니다" + exit2 |

📊 종합: 15개 중 15개 통과 / 0개 실패 → **종합 PASS** (수정 요청 없음)

검증 환경: Python 3.11.9 / fitz 1.27.2.3 / fontTools 4.63.0 / pikepdf 10.8.0 / 폰트 HY헤드라인M.ttf(H2hdrM) / 완성본 ../grader/illustrator-scripts/test/design_XL.ai

reference 실측(§4 대조): 페이지 4478.74×5669.29(일치) / 분할 x=2239.37(일치) / 앞 center[1389.2,4184.4] cap309.8 / 뒤 center[3217.1,4342.4] cap538.6 / 이름 cx3219.8 bl4765.7 em136.4 pitch195.5 font H2hdrM — 모든 수치 §4 ±0.4 이내.

참고: place_number 가로중심 1~3pt 오차는 advance중심≠잉크중심(좌우 사이드베어링 비대칭)으로 §4가 명시한 정상 범위(cowork 오버레이 재검증 항목). 코드 결함 아님.

### Phase C 독립 검증 [2026-06-19] — 종합 PASS (8/8)

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ 통과 | 6사이즈 24배치 9개 PASS, inkcov 편차 0.000000, 종합 PASS. 불변제약: git diff 변경파일=job.py+preset.json만(grade/compose/verify/text/pdfutil/flatten/pattern 무수정) |
| 2) per_player 스모크 | ✅ 통과 | 7번 홍길동/20번 김경원 XS → produced 2/verify_pass 2/fail 0, precise_placement=True, PDF 2개 생성+각 verify PASS, skipped/missing 없음 |
| 3) 콘텐츠 주입 | ✅ 통과 | 앞·뒤번호+이름 ops 실주입: Do=3 k(fill)=3 f=3 c(큐빅)47~89 l283~290 m14~19. flatten: bg CMYK[0.8,0.5,0,0.1]자동감지, /Fm0평탄화, recolored 1, alpha gstate 2수정, transparency_left=[], _flattened_design.pdf 생성 |
| 4) 좌표변환 동일행렬 | ✅ 통과 | 글자감싸기 cm = 그 조각 디자인배치 cm과 100%동일. 앞번호→front(0.8651,184.84,-2159.87) / 뒤번호·이름→back(0.9098,213.49,-2288.51) 2개. sleeve(0.6734)엔 글자없음. developer 주장 재현 |
| 5) split single | ✅ 통과 | produced 1/verify_pass 1, 다페이지 1PDF 2페이지(page1 홍길동/page2 김경원), 각 page Do=3 k=3 RGB/ca/CA=0 |
| 6) 금지연산자 전무 | ✅ 통과 | 전 PDF에서 rg/RG/sc/scn/ca/CA/gs/BI(인라인이미지)=0. 1자리·2자리 번호 모두 |
| 7) 하위호환 폴백 | ✅ 통과 | 새 area 제거 레거시 preset → precise_placement=False(폴백), build_layouts 경로 동작, Do=3 k=2(back번호+이름), verify PASS. 회귀 없음 |
| 8) 엣지케이스 | ✅ 통과 | 1자리(5)/2자리(99) OK, 누락글리프(漢字🎉) 통째미출력+친절경고, 빈이름/빈번호 정상(k fill 개수 글자내용 따라 1~3 정확), 빈사이즈·없는사이즈(4XL) skip+사유+missing집계, 크래시 0. produced 5/verify_pass 5 |

📊 종합: 8개 중 8개 통과 / 0개 실패 → **종합 PASS** (수정 요청 없음)

검증 환경: 위 Phase B와 동일(Python 3.11.9 / pikepdf 10.8.0 등). preset=data/patterns/농구_U넥_양면/preset.json(새 area 3개 포함), design=../grader/illustrator-scripts/test/design_XL.ai.
job.json summary 키 11개 전부 존재(job_dir/split/total_players/produced/verify_pass/verify_fail/skipped/warnings/missing_sizes/precise_placement/flatten).
참고: 좌표 정합(위치 정확도)은 U넥에서 V넥 완성본 수치라 어긋날 수 있음 — Phase C 검증 포인트는 "배관이 흐르는가"(글자주입·좌표변환·평탄화·verify PASS)이며 전부 통과. 위치 정합은 Phase D/E 범위.

### Phase D 되돌림1 재검증 [2026-06-19] — ✅ 종합 PASS (7/7) → **되돌림1로 FAIL 해소 확정**

| 재검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ 통과 | 6사이즈 24배치 9개 PASS, inkcov 편차 0.000000, 종합 PASS. 코어 무수정·U넥 영향 0 |
| 2) 13개 viewBox 가로·전좌표 양수·조각/svg_index | ✅ 통과 | **13개 전부 viewBox `0 0 4478.74 3401.57`(가로)** + **조각 bbox 전수 양수**(min x,y≥0, max≤W/H, 음수 0건). 조각수=2 전수, 앞=idx0(왼쪽 cx 1103~1376)/뒤=idx1(오른쪽 cx 3076~3349) 13개 일관, 앞h≥뒤h 역전0. 이전 비-XL 세로5669+음수 → 전부 해소 |
| 3) ★핵심★ 비-XL 앞판 소실 해소 (미리보기 육안) | ✅ 통과 | 5XS·M·L·5XL(비-XL 4개)+XL per_player → **미리보기 PNG 5장 전부 앞판(YONSEI+번호)·뒤판(이름+번호) 둘 다 캔버스 안 정위치, 앞판 소실 없음**(직접 육안 확인). **page rect 5개 전부 가로**(5XS 3953×2689, M 4165.5×2785.9, L 4213×2745, XL 4073×2960, 5XL 4287×3001). 이전 M 세로 2811×5351·뒤판만 → **증상 완전 소멸** |
| 4) verify_output + 금지연산자 | ✅ 통과 | produced 5/verify_pass 5/fail 0/skipped 0/missing 0, precise=True, transparency_left=[]. job.json checks 전수 ok. 페이지스트림 **scn=0 rg=0 RG=0 gs=0 BI(inline)=0**, Do=2(앞/뒤판) k=3(앞·뒤번호+이름 CMYK fill) — 5개 PDF 전부 동일 |
| 5) ai_to_path_svg.py 동작 | ✅ 통과 | 인자없음 사용법+exit0, 단일변환 정상(viewBox·path 추출 성공 1/실패 0), 크래시 없음. 배치는 되돌림1 산출물(13개 재변환)로 입증 |
| 6) preset.json 유효 | ✅ 통과 | load_preset OK, sizes 13, pieces front:0/back:1, area 3개(front/back_number·back_name) 전부 존재. SVG만 교체·preset 무변경 |
| 7) U넥 회귀 | ✅ 통과 | U넥 폴더(농구_U넥_양면) 무변경(XS.svg 1개·preset 그대로), parse_svg=3조각, job 스모크(홍길동7/XS) produced 1/pass 1/fail 0. V넥 SVG 교체는 별 폴더라 U넥 무영향 |

📊 종합: 7개 항목 전부 통과 / 0개 실패 → **종합 PASS** → **되돌림1로 이전 🔴 FAIL(비-XL 앞판 소실) 해소 확정** (수정 요청 없음)

⚠️ 이전 FAIL 대조: 이전엔 비-XL 12개가 viewBox 세로5669+음수좌표 → 앞판 캔버스 밖 소실(M 뒤판만, page rect 세로 2811×5351). 되돌림1(원본 .ai 13개 동일 파이프라인 재변환)로 **13개 viewBox 가로3401·전좌표 양수 통일** → 비-XL 미리보기 육안에서 앞판 정상 복귀·page rect 가로 확인. errors.md [2026-06-19] "조각수=2+verify PASS만으론 부족, 비-XL 육안 필수" 함정의 진짜 판정기준(미리보기 육안)으로 재검증 완료.

검증 환경: Python 3.11.9 / fitz 1.27.2.3 / pikepdf 10.8.0. 빈템플릿=C:/Users/user/Desktop/새 폴더/연세대…V넥…XL - 템플릿.ai. 임시 검증출력(data/jobs/_retest_*) 정리 완료. git: engine 변경=cli.py 73+/0-(이전 Phase D분)·svg_normalize 신규뿐, 코어 무수정 / scripts/ai_to_path_svg.py 신규.

### Phase D 독립 검증 [2026-06-19] — 🔴 종합 FAIL (코드 OK / 데이터 결함)

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ 통과 | 6사이즈 24배치 9개 PASS, inkcov 편차 0.000000, 종합 PASS. U넥 영향 없음 |
| 2) 13개 조각수=2 + svg_index | ✅ 통과 | 13개 전부 parse_svg=2, front=idx0/back=idx1 일관(역전 0). **단 좌표는 별개 문제(항목3 FAIL 참조)** |
| 3a) 변환기 d파서·matrix 정확성 | ✅ 통과 | XL path[0] 수동검산: M/H/L/V 전개+matrix(1,0,0,-1,e,f) 적용 4점 모두 ±0.01 일치. 닫힘판정(시작≈끝 gap≈0)·보조선필터(small 6개 제외)·중복제거 정상 동작 |
| 3b) **커밋된 12개 SVG 좌표계 오염** | ❌ **실패** | **XL만 viewBox 가로(3401)·양수 좌표 정상. 나머지 12개(5XS~L,2XL~5XL)는 viewBox 세로(5669)+조각 x좌표 음수**(M앞판 x[-1341..313]). 원본 .ai 13개를 변환하면 전부 viewBox 가로(3401)·양수가 나옴(변환기는 정확, XL은 .ai변환=커밋본 완전일치). 커밋된 12개는 XL과 다른 출처 SVG에서 변환돼 좌표 오염 |
| 4) normalize-svg CLI | ✅ 통과 | --help OK, 단일변환 OK(조각2✅), 배치 누락파일 친절처리(크래시X), 인자부족 사용법+exit2. 기존 명령(grade/job/reference/flatten/order/selftest) help 전부 회귀 없음 |
| 5) preset.json | ✅ 통과 | 유효JSON, load_preset OK, sizes13, pieces front:0/back:1, design_mapping 존재. area 수치 §4 완전일치(앞 c1389,4184 cap310 / 뒤 c3217,4342 cap539 / 이름 cx3219.8 bl4765.7 em136.4 pitch195.4) |
| 6a) job 스모크(XL) | ✅ 통과 | 김경원/20 XL → verify_pass, 미리보기 앞YONSEI+20·뒤김경원+20 정위치 흰색. precise_placement=True, flatten 적용(transparency_left=[]). 금지연산자0(Do2·k fill3·rg/RG0·scn0·gs0·BI0·Image0·ca/CA없음) |
| 6b) **job 스모크(M·L 등 비-XL)** | ❌ **실패** | 이순신/7 M·홍길동/10 L → verify_pass=True·skipped0으로 **카운트는 통과하나 실제 출력 깨짐**. page rect 세로 길쭉(M 2811×5351, L 2811×5379), **앞판 소실(미리보기에 뒤판만)**. cm translate -1788pt까지 밀림(음수좌표 정합 부작용). ✅대조: 같은 M을 올바른 .ai 변환본으로 교체하면 앞·뒤 정상 |
| 7) 엣지케이스 | ✅ 통과 | 빈SVG=0조각(크래시X), 보조선만=0조각, 깨진XML=ParseError(차단), 없는입력=친절FileNotFoundError, 극단 5XS/5XL 조각수=2. .ai변환은 5XS/5XL도 viewBox3401 정상 |

📊 종합: 13항목 중 11 통과 / **2 실패(3b·6b — 동일 근본원인: 커밋된 12개 SVG 좌표 오염)** → **종합 FAIL**

⚠️ 핵심 진단: **svg_normalize.py·cli·preset·변환기 로직은 전부 정상**(불변제약 준수, selftest 회귀 0, XL 완벽). 결함은 **커밋된 13개 패턴 SVG 중 비-XL 12개의 입력 출처**다. XL은 원본 .ai PyMuPDF 변환본과 1:1 일치하나, 나머지 12개는 viewBox 세로(5669)+조각 음수좌표인 다른 출처 SVG에서 변환됐다. 그 결과 앞판이 캔버스 밖으로 나가 출력에서 소실된다.

🩸 함정(scratchpad가 PASS로 오인한 이유): ①조각수 2 ②svg_index 앞0/뒤1 일관 ③verify PASS ④job produced/verify_pass 정상 — **이 4개 초록불이 전부 켜져도 출력은 깨진다.** verify_output은 디자인 Form 무손실만 보지 위치/캔버스를 안 본다. 스모크를 XL 1개만 보면(developer 스모크는 김경원20 XL·이순신7 M였으나 M 미리보기 육안을 안 한 듯) 통과처럼 보인다. **반드시 비-XL 사이즈 미리보기 육안이 필요.**

✅ 재발 검증법(수정 후 필수): (a)13개 viewBox 전수 동일 + 조각 bbox가 viewBox[0..W] 안(음수/초과 0) (b)출력 page rect 사이즈 무관 동일 비율(가로) (c)**전 사이즈는 아니어도 최소 비-XL 2~3개 미리보기 육안으로 앞판 존재 확인**.

검증 환경: Python 3.11.9 / fitz 1.27.2.3 / pikepdf 10.8.0. 빈템플릿=C:/Users/user/Desktop/새 폴더/연세대…V넥…XL - 템플릿.ai. 원본 .ai=G:/공유 드라이브/디자인/2026 커스텀용 패턴/0. 농구유니폼 확정 정리본/2. 양면 유니폼상의 패턴/V넥/V넥 양면유니폼 스탠다드/.

## 리뷰 결과 (reviewer)

### Phase E 리뷰 결과 [2026-06-19] — STIZ 신양식③ 파서(order.py)

📊 종합 판정: **통과** (치명 0 / 주의 2 / 후순위 3)

✅ 잘된 점:
- **불변 제약 완벽 준수**(§6): `git diff HEAD --name-only` = `engine/order.py`·`.claude/scratchpad.md` **딱 둘뿐**. engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)·job·svg_normalize·grade·build_layouts·verify **변경 0줄**. order.py는 원래 engine 코어를 import 안 하는 독립 입력 파서라 코어 무손상. `selftest 종합 PASS`(바이트동일·CMYK·inkcov 편차 0) 회귀 0 직접 확인.
- **컬럼 위치 키워드 동적 매핑**(과적합 방지 핵심): 고정 오프셋 아님. 순번/이니셜/배번/사이즈/비고를 헤더 키워드로 각각 col 인덱스 탐색 → 양식①(이름 A열)과 양식③(이름 B열) 컬럼 배치 차이를 정확히 흡수. 배번 헤더 누락 시 `col_name+1` 폴백도 합리적.
- **결측행 skip 견고**: 이름·배번·사이즈 3개 모두 빈 행("순번만 미리 적힌 39~100행")을 정확히 건너뜀. 실데이터에서 100행 중 유효 38행만 추출, 빈 62행 무오염 확인.
- **부제행(상의/하의) skip 정확**: 헤더 바로 아래 `상의`/`하의` 텍스트 감지 시 1행 skip → 상의 col_size 그대로 사용. 실데이터 19행(상의/하의 부제) 정확히 건너뜀.
- **qty 숫자추출 안전**: `_QTY_NUM_PATTERN=(\d+)` 가 "4장"·"1장"에서 앞 숫자 추출, col_note 없거나 비숫자/결측이면 qty="1" 폴백. `_to_str` 거쳐 None/float 방어.
- **nbsp 보강 정확·무손상**: `_norm_header`가 `\xa0`→공백→제거. 실데이터 헤더 `\xa0이니셜`·`순\xa0\xa0 번` 매칭 위함. 양식①/② 헤더엔 nbsp 없어 영향 0 — `_parse_form1`은 `_HEADER_INITIAL` 매칭만 쓰고 정상 작동(실데이터 form1=0 확인). selftest·기존 파서 경로 무변동.
- **실데이터 전수 정상**: 260213 연세대 추가주문서 → form1=0 / stiz=38 / warnings 0. 사이즈 XS~3XL·qty "1"~"4" 정상.

🔴 필수 수정: 없음.

🟡 주의(권장, 차단 아님):
- **[과적합 위험 — 자동판별 순서 ①→③→②의 취약점] (가장 중요)** developer 설명("①이 0행이라 ③ 진입")의 *메커니즘이 실제와 다름*. ①이 0행인 진짜 이유는 **`_parse_form1`의 헤더 탐색 범위가 `min(12, len)` 즉 0~11행뿐인데 실데이터 양식③ 헤더가 18행**에 있어 ①이 헤더를 아예 못 찾기 때문(우연한 안전). 직접 재현 검증 결과: **양식③ 헤더를 0~11행 안으로 옮기면 `_parse_form1`이 '이니셜' 헤더(B열)를 잡아 양식③ 데이터를 2행으로 파싱해버리고, 그 결과 비고("4장")가 무시되어 qty가 전부 "1"로 깨진다**(stiz 파서에 도달조차 못 함). 즉 현 통과는 "헤더가 12행 밖"이라는 *이 파일 1개의 우연*에 의존. 다른 STIZ 양식③ 주문서(헤더 위치 다름)에서 qty 손실 가능. → 근본 방어: parse_order에서 ③ 식별(순번+이니셜+사이즈)을 ①보다 **먼저** 시도하거나, `_parse_form1`이 헤더행에 '순번' 컬럼이 보이면 양식③에 양보(빈 리스트 반환)하도록 가드 1줄 추가 권장. (현 데이터 무해 → 차단 아님, 단 일반화 시 1순위 개선)
- **[하의 사이즈 미지원 = 백로그⑦]** col_size는 상의 열만 사용, 하의 열(부제행 '하의'가 가리키는 col)은 무시. V넥 상의 출력엔 정상이나, 상·하의 사이즈가 다른 주문(농구는 보통 세트)에서 하의 정보 소실. 백로그⑦에 이미 등재됨 — 1차 범위 밖, 인지 확인.

🟢 후순위(개선 제안):
1. **[헤더 탐색 범위 비일관]** stiz는 헤더 20행/컬럼 10열, form1은 12행/7열로 범위가 제각각. 실데이터 헤더 18행이 form1 범위(12) 밖이라 우연히 충돌 안 나지만, 두 파서 범위를 같은 상수로 통일하면 의도가 명확해지고 위 🟡 취약점도 부분 완화.
2. **[col_seq 미사용]** 헤더에서 col_seq를 잡아두지만 데이터 추출엔 안 씀(파일명/정렬에 활용 여지). 현재 무해, 식별용으로만 쓰임.
3. **[qty 정수성 미검증]** "0장"·"00장"이 와도 qty="0"으로 통과(양식②는 0 제외 처리). job이 qty=0을 어떻게 다루는지(0벌 출력?) 확인 권장 — 현 실데이터엔 0 없음.

검증 방법: git diff HEAD --name-only(2파일 한정) + order.py diff·전문 정독(_parse_form_stiz/_norm_header/parse_order 분기) + 실데이터 260213 시트별 form1/stiz 결과(0/38) + 헤더행 위치 실측(18행) + **합성 양식③(헤더 5행) 재현으로 form1 선점·qty 손실 위험 입증** + nbsp/결측행/부제행/qty추출 단위 확인 + selftest PASS + 의뢰서 §6 대조.

---

### Phase D 리뷰 결과 [2026-06-19]

📊 종합 판정: **통과** (치명 0 / 주의 2 / 후순위 4)

✅ 잘된 점:
- **불변 제약 완벽 준수**(§6): `git diff HEAD` 결과 engine 추적파일 변경은 **cli.py 단 1개(73줄 추가/0줄 삭제)**, svg_normalize.py는 신규. parse_svg/compose/Piece/SizeLayout/scale_translate/verify_output/build_layouts/grade/text/flatten **전부 무수정(diff 0)**. svg_normalize.py는 stdlib(re/xml/math/os/tempfile)만 쓰고 engine 코어 import 안 함(계층 분리). preset/SVG는 데이터. selftest 종합 PASS·inkcov 편차 0.000000(회귀 0).
- **13개 변환 조각수=2 전수 재확인**(직접 parse_svg 재파싱): 5XS~5XL 모두 2조각. svg_index 앞=idx0/뒤=idx1이 **13개 전부 안정**(앞h가 뒤h보다 일관되게 큼). preset svg_index front:0/back:1 정확.
- **d 파서 견고**: M/m·L/l·H/h·V/v 절대·상대 정확 처리, M 다음 암묵 L 처리(SVG 규약), 다중 좌표쌍 반복, 음수·지수 표기 정규식(_NUM) 커버. 닫힘판정=Z OR 시작≈끝(1pt) — 실측 gap≈0에 맞음. 곡선(C/Q/S/A)은 끝점 직선근사+has_curves 경고(현재 데이터 0개, YAGNI 인터페이스만).
- **matrix 합성 정확**: x'=a*x+c*y+e, y'=b*x+d*y+f 표준 affine. matrix 없으면 항등행렬 폴백. nums<6도 항등 폴백(방어).
- **이중 flip 방지 정확**(핵심 함정): 변환기는 matrix만 적용하고 flip 안 함, parse_svg가 자체 flip_y. 스모크 미리보기에서 상하 정위치 확인됨 → 정확.
- **보조선/중복 필터 임계 안전**: min_dim 5%=283.5pt(세로 viewBox) ≪ 실조각 폭 ~1542pt라 실조각은 확실히 통과, 보조선(폭/높이 한쪽 0)은 확실히 탈락. dedup tol 1%=56.7pt — 앞/뒤는 가로중심 차이 ~2447pt ≫ tol이라 **서로 중복 오판 불가**(다른 조각 누락 위험 낮음). 위/아래 2벌 복제만 제거.
- **원자적 쓰기**: tempfile.mkstemp→fdopen 기록→os.replace. finally에서 잔류 tmp 정리. conventions(친절한 한글 에러)도 준수(입력 없음 FileNotFoundError, cli 입력 선검증).
- **수치/경로 하드코딩 없음**: 임계는 전부 매개변수(min_points/min_dim_ratio/dedup_tol_ratio), 사이즈/경로는 cli 인자({size} 치환). preset 폰트(HY헤드라인M.ttf) 실존 확인.
- **Phase E 연결성 OK**: V넥 preset는 Phase C job이 처리하는 스키마(pieces[].id/design_region_pt + front/back_number_area·back_name_area, use_precise=True)와 동일 → **job 코드 무수정으로 동작**. 스모크(김경원20/이순신7 per_player) verify_pass=produced·금지연산자 0·글자 k fill 정주입 입증.

🔴 필수 수정: 없음.

🟡 주의(권장, 차단 아님):
- [좌표계 — 음수 bbox] 변환본 12개(XL 제외)의 앞판 polyline bbox가 **viewBox 밖 음수 x 영역**(예: XS 앞 x[-1228.5..313.6])에 위치. 원본 세로 viewBox에 앞·뒤판이 위·아래 2벌 중복→dedup 후 남은 벌이 matrix(…,-1,…) 적용으로 음수로 떨어진 것. **동작 무해**: _piece_transform이 조각 bbox(px0,py0)를 절대기준으로 ox/oy를 자기완결 계산 → 음수여도 design_region 정합 보존(스모크 verify PASS·시각 정합이 입증). 단 음수 좌표는 직관에 반하므로 향후 다른 패턴에서 dedup이 "엉뚱한 벌(잘린 쪽)"을 남길 경우 위치 어긋남 가능 → cowork 오버레이 최종 정밀확인(의뢰서 §7-4) 권장. 변환기가 "viewBox 안쪽 벌 우선 유지" 규칙이면 더 견고(후속 개선 여지).
- [svg_index 역전 근소] 앞·뒤 높이차가 **5XS에서 0.72pt**로 매우 근소(5XL에서도 2.16pt). 현재 13개 전수 앞=idx0 안정이나, 향후 다른 V넥 계열(슬림/롱 등) 추가 시 정렬 역전으로 앞/뒤 글자가 뒤바뀔 위험(백로그⑤와 동일 성격). 근본 방어책: dedup 후 조각을 **가로중심 x 기준 안정 정렬**(왼쪽=앞)로 변환기가 순서 보장하거나, parse_svg 정렬에 의존 말고 preset가 면적·위치로 매핑하는 검증 단계 추가. 현재는 cli가 변환 후 조각수 2를 확인하나 앞/뒤 역전은 점검 안 함 → 변환/검증 시 앞h vs 뒤h 출력 1줄 추가 권장.

🟢 후순위(개선 제안):
1. [dedup cy 미비교] 중복 판정이 폭·높이·가로중심(cx)만 보고 세로중심(cy)은 안 봄. V넥은 앞/뒤 cx가 멀어 오판 없으나, 폭·높이·cx 같고 cy만 다른 정당한 별개 조각이 있는 패턴에선 1개가 누락될 수 있음 → cy도 비교 추가하면 일반화 견고(현 데이터 무해).
2. [곡선 폴백 미구현] flatten_curves=True여도 끝점 직선근사뿐(평탄화 샘플링 미구현). 곡선 섞인 SVG는 형태 왜곡+경고만. 현재 V넥 곡선 0이라 무발동(YAGNI 타당). 다른 패턴 확장 시 본구현 필요.
3. [cli 조각수 기대값 하드코딩 2] `mark = "✅" if n == 2 else "⚠️"` — V넥 전제(앞/뒤 2). 소매 포함 패턴(3조각)이나 단면(1)에선 항상 ⚠️ 표시 → 기대 조각수를 인자/preset에서 받거나 메시지를 "확인 필요"로 완화 여지(동작 무해, 표시만).
4. [소매 부재] V넥 SVG에 소매 닫힌 윤곽 없음 → 앞/뒤 2 pieces로 진행(사용자 "앞/뒤 2조각" 확정과 일치). design_region_pt는 U넥 펼침값 재사용 — V넥 펼침 레이아웃 차이 시 위치 어긋남 가능, cowork 오버레이 재확인(이미 잔여리스크로 명시됨).

검증 방법: git diff HEAD(engine 변경=cli.py 73+/0- + svg_normalize 신규만 확인) + svg_normalize 전 함수 정독(d파서/matrix/필터/dedup/원자쓰기) + 13개 변환본 parse_svg 재파싱(조각수=2·앞뒤높이·bbox 실측) + _piece_transform 음수좌표 무해성 확인 + cli 인자분기/에러처리 정독 + preset JSON·폰트 실존 + selftest PASS + 의뢰서 §6 대조.

---

### Phase C 리뷰 결과 [2026-06-19]

📊 종합 판정: **통과** (치명 0 / 주의 2 / 후순위 4)

✅ 잘된 점:
- 불변 제약 완벽 준수: `git diff HEAD` 결과 변경 파일 = job.py + preset.json(+scratchpad) **딱 그것뿐**. compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output/build_layouts/grade/text.py/flatten.py **전부 working tree diff 0(무수정)**. preset 새 area는 기존 number_area/name_area 옆에 "추가만". §6 준수.
- 좌표변환 정확(핵심): `_job_piece_transform` 의 s/ox/oy 공식이 grade.py `_piece_transform` 과 **한 글자도 다르지 않게 동일**(s=min(pw/dw,ph/dh)*min(shrink_x,shrink_y), ox=px0-s*dx0, oy=py0-s*dy0). 방식A 앵커 bottom-left·등방 contain 그대로.
- 글자 감싸기 행렬 정합 검증됨: compose는 `place_block`(q…clip…cm…Do…Q)을 **닫은 뒤** extra_ops를 별도 블록으로 추가 → extra_ops는 시트 절대좌표 컨텍스트에서 그려진다(compose.py L79~82 확인). 따라서 디자인좌표 글자 ops를 `_wrap_design_ops`가 그 조각 transform(cm)으로 다시 감싸는 것이 정확 = Do에 적용된 변환과 동일 행렬 재현. 앞=front 조각/뒤번호·이름=back 조각 매핑 맞음(piece_id "front"/"back"이 pieces[].id와 일치).
- device CMYK k fill만: place_number/place_name ops = `q\n c m y k k\n <m/l/c/h>\n f\n Q`. Do/rg/RG/ca/CA/gs/인라인이미지 0건(text.py L316~470 확인). 앞·뒤 같은 배번 주입.
- _resolve_font_path는 복제 안 하고 grade.py에서 import(호출만) → 동작 일치 보장, grade.py 무수정.
- flatten은 행 루프 **밖 1회만** 실행(선수마다 재평탄화 안 함, L333). 실패해도 base_design=원본 폴백 후 진행, verify가 최종 판정(안전). flat 실패 시 깨진 _flattened_design.pdf가 생겨도 base_design이 원본으로 폴백돼 참조 안 됨.
- 엣지 견고: piece_id 못 찾으면 경고+건너뜀(_inject), svg_index 범위초과는 ValueError→행 skip(부분성공), 빈 number/name=무출력, 사이즈 빈값/미존재=skip+missing_sizes. 파일명 충돌 _2 접미사. 수치 전부 preset에서 읽음(하드코딩 없음).
- Phase D 연결성 OK: V넥 preset도 같은 스키마(pieces[].id/design_region_pt + front/back_number_area·back_name_area)면 job 코드 무수정으로 동작. _has_precise_areas 분기라 새 area 없는 기존 preset은 build_layouts 폴백(완전 호환).

🔴 필수 수정: 없음.

🟡 주의(권장, 차단 아님):
- [후속 리스크] _job_piece_transform이 grade.py _piece_transform의 **복제**라 향후 grade 공식이 바뀌면 job이 따로 논다(글자가 디자인과 어긋남). 현재 두 함수는 100% 동일하고 주석에도 명시돼 있으나, 근본 해소책은 grade.py가 _piece_transform을 **공개 함수(piece_transform)로 승격**해 job이 import하게 하는 것(_resolve_font_path를 import한 것과 같은 방식). 단 grade.py 무수정 제약 하에선 불가 → 제약 완화 가능한 Phase D/E 시점에 "공개 승격 후 복제 제거" 검토 권장. 회귀 방어로 두 함수 동일성 확인 단위테스트 1개 추가도 저비용 보험.
- [job.py L370] use_precise=True여도 매 선수마다 `sized = _sized_preset(...)`를 계산하는데 정밀 경로에선 sized를 안 쓴다(불필요 dict 복제). polys 캐시 없이 선수마다 parse_svg+compose 반복도 그대로(60명이면 60회 — 설계서가 1차 단순 우선으로 허용한 범위). 성능 문제 시 use_precise 분기 안으로 sized 계산 이동 + 사이즈별 base layout 캐시(글자만 재주입)로 최적화 가능. 동작엔 영향 없음.

🟢 후순위(개선 제안):
1. [job.py _inject color 기본값] `area.get("color_cmyk",[0,0,0,1])`(검정)로 폴백하나 preset 새 area는 모두 [0,0,0,0](흰색) 명시 → 현재 무해. 폴백 기본값을 흰색 area 용도에 맞춰 두거나 색 누락 시 경고 추가 여지.
2. [_flattened_design.pdf 정리] out_dir에 평탄화본이 영구히 남음(검수/디버깅엔 유용). 산출물 ZIP 시 제외 또는 작업 종료 후 옵션 정리 검토(설계서도 "정리 필요시 후속" 명시).
3. [single 모드 페이지 순서] order_rows 입력 순서 유지(설계 의도). 공장 작업 편의상 사이즈→번호 정렬은 옵션 백로그.
4. [좌표 정합 자체] U넥 preset에 V넥 완성본 수치(center 1389,4184 등)가 들어가 U넥에선 글자 위치가 안 맞을 수 있음 — Phase C는 "배관이 흐르는가" 검증이라 OK. 실제 정합은 Phase D/E(V넥 preset).

검증 방법: git diff HEAD(변경 3파일 한정 확인) + _job_piece_transform↔grade._piece_transform 수식 대조(동일) + compose extra_ops 위치 확인(place_block 밖=시트좌표) + _wrap_design_ops cm 재현 검증 + text.py place_* 연산자 규약 확인(k fill만) + preset piece_id↔pieces.id 매핑 + 엣지/분기 정독.

---

### Phase B 리뷰 결과 [2026-06-19]

📊 종합 판정: **통과** (치명 0 / 주의 2 / 후순위 4)

✅ 잘된 점:
- 불변 제약 완벽 준수: git diff 확인 결과 변경 파일은 cli.py/reference.py/text.py 3개뿐. 코어(compose/pattern/pdfutil/preview/verify)·build_layouts·grade·기존 render_text_ops/extract_reference **무수정, 전부 "추가만"**. selftest 회귀 0 PASS.
- device CMYK `k` fill만 사용: place_number/place_name ops 검증 → Do/ca/CA/rg/RG/scn 등 금지 연산자 0건, q…Q 래핑 정상. (실측 확인)
- reference CLI가 §4 수치와 정밀 일치: 앞 cap309.8/center[1389,4184], 뒤 cap538.6/[3217,4342], 이름 em136.4·pitch195.5·baseline4765.7·font H2hdrM. 모두 §4 목표 일치.
- **Phase C 연결성 OK**: --json 출력 키(front_number_area{center,cap_height,color_cmyk,font} / back_number_area / back_name_area{center_x,baseline,em_pt,pitch,color_cmyk,font})가 §4 Phase C preset 예시와 100% 일치 → 바로 붙음.
- 엣지케이스 견고: 빈값=무출력, cap/em/pitch 0·음수=경고+건너뜀, 누락글리프=통째 미출력+경고, 한자리/두자리/3자리 번호 모두 center_x 가운데정렬. 수치 전부 인자(하드코딩 없음). 친절한 한글 경고.
- upm 폰트메타에서 읽음(1024 확인) → 명세 §3 upm=1024와 정합. text.py 상단 옛 주석(upm=2048)과 무관하게 실폰트값 사용해 정확.

🔴 필수 수정: 없음.

🟡 주의(권장):
- [text.py place_number ~L172] 번호 가로중심 사이드베어링 보정 누락 → 잉크 가로중심이 목표 대비 ~1.4~2.4pt 좌측 치우침(실측: 7→3215.1, 20→3214.6 vs 목표3217). 명세 §4가 "번호 세로중심·폭 미세 조정 여지 / cowork 오버레이 재검증" 명시한 정상 범위라 **차단 아님**. Phase E cowork 오버레이에서 육안 확인 후, 필요시 'advance중심' 대신 '대표글리프 잉크 bbox 중심'을 center_x에 맞추는 보정 1줄로 해소 가능.
- [text.py place_name 누락처리 L256~] missing 글자 있어도 이미 glyph_blocks를 다 만든 뒤 버림(통째 미출력 의도는 정확·동작 무해, 단 불필요 연산). cmap에 없는 글자만 가려내는 1차 스캔을 루프 앞으로 빼면 깔끔. 우선순위 낮음.

🟢 후순위(개선 제안, 차단 아님):
1. [reference CLI] --템플릿 받기만 하고 1차 미사용(명세 §5 "1차는 완성본 단독 OK" 허용 범위). 향후 템플릿 diff로 휴리스틱 의존 제거 시 정확도↑.
2. [reference._number_area_from_cluster] cap_height=번호 합친 bbox 세로높이라 한 자리 번호 완성본일 때 자릿높이=잉크높이로 정확하나, 두 자리에서 위첨자/하강 글리프 섞이면 오차 가능. 현 완성본(0/8 계열)은 OK. 사이즈/폰트 확장 시 재확인.
3. [reference.build_area_preset] name color_cmyk를 back_number 색에서 차용(이름=살아있는 텍스트라 자체 fill색 미추출). 현재 둘 다 흰색이라 무해. fitz span color 직접 읽기로 개선 여지.
4. [text.py 직접 import 사용 시] 경고 문자열의 🟡 이모지가 cp949 콘솔 직출력 시 크래시 가능(CLI는 _force_utf8_console로 안전). job.py가 place_*를 직접 호출해 warnings를 그냥 print하면 환경따라 위험 → job 단계에서 cli의 utf8 강제 흐름 안에서만 출력하면 OK.

검증 방법: git diff(추가만 확인) + selftest PASS + place_number/name 엣지·ops규약 실측 + reference CLI 실행(§4 대조) + --json 키 대조.

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| tester | data/patterns/농구_V넥_양면/{5XS,4XS,3XS,2XS,XS,S,M,L,2XL,3XL,4XL,5XL}.svg (XL 제외 12개) | **좌표계 오염**: 12개가 viewBox 세로(5669)+조각 x좌표 음수에서 변환됨. XL만 정상(viewBox 가로 3401, 양수). 그 결과 비-XL job 출력에서 **앞판이 캔버스 밖으로 소실**(미리보기에 뒤판만, page rect 세로 길쭉). 재현: `run_job(preset, 빈템플릿.ai, [{name:'이순신',number:'7',size:'M',qty:1}], OUT)` → 미리보기 PNG 보면 앞판 없음. 해소: 원본 .ai 13개(G:/…/V넥 양면유니폼 스탠다드/양면유니폼_V넥_스탠다드_{size}.ai)를 PyMuPDF get_svg_image로 .svg 추출 후 normalize-svg로 13개 **동일 출처·동일 viewBox(3401)**로 재변환. (변환기 svg_normalize.py·cli·preset은 무결 — XL .ai변환=커밋본 1:1 일치 확인) | **수정완료** (2026-06-19 방식A: scripts/ai_to_path_svg.py 신설→원본 .ai 13개 재추출→normalize-svg 재변환. 13개 viewBox 가로3401·양수·조각2·앞0뒤1 통일. 비-XL 5사이즈 육안 앞판 정상·page rect 가로·verify PASS·금지연산자0. engine/cli/코어 무수정) |

## 작업 로그 (최근 10건만 유지)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-19 | reviewer | Phase E 리뷰: order.py 신양식③ 파서·nbsp·자동판별 | 통과(치명0/주의2/후순위3). 불변제약·selftest OK. 🟡 자동판별 ①→③ 순서가 헤더 12행밖 우연에 의존(헤더 앞쪽이면 form1이 선점→qty손실) — 일반화 시 가드 권장 |
| 2026-06-15 | developer | A-4 구현: text.py 신설+compose/grade/cli 확장 | 글자없이 콘텐츠100%동일·verify PASS유지 |
| 2026-06-15 | tester/reviewer | A-4 검증·리뷰 | 통과(6/6, 치명0, 🟡후순위) |
| 2026-06-15 | pm | A-4 커밋(c1d0048)+자료 커밋(c7fc068)+fontTools | 완료 |
| 2026-06-16 | planner-architect | A-5 주문서 파싱 설계(양식2종 분석, 실데이터 86개) | 완료(설계만) |
| 2026-06-16 | developer | A-5 구현: order.py 신설+cli order(양식①/②·아동호수·부분실패) | 자체검증 대표5개 일치 |
| 2026-06-16 | reviewer | A-5 코드리뷰 | 통과(치명0, 🟡4건) |
| 2026-06-16 | tester | A-5 검증 | 🔴시트선택 버그 발견(13/86 오답) |
| 2026-06-16 | developer | A-5 되돌림1: 시트선택 표식우선 수정 | 13개 교정·전수86 오선택0 |
| 2026-06-16 | tester | A-5 재검증(되돌림1) | 통과(13/13 FIX, 회귀0) |
| 2026-06-16 | pm | A-5 커밋(927b7b6)+index 갱신+scratchpad 정리 | 완료(미푸시3) |
| 2026-06-18 | planner-architect | job 설계: engine/job.py run_job() per_player/single·preset사이즈좁히기·원자쓰기·엣지 | 완료(설계만) |
| 2026-06-19 | developer | Phase B: text.py place_number/place_name(정밀배치)+reference build_area_preset+cli reference | selftest PASS·§4 수치 재현 일치 |
| 2026-06-19 | reviewer | Phase B 코드리뷰(불변제약·ops규약·§4정합·Phase C키·엣지) | 통과(치명0, 🟡2, 🟢4) |
| 2026-06-19 | developer | Phase C: job 통합배관(flatten선적용+정밀배치 place_*+좌표변환 감싸기), preset area3개 | selftest PASS·per/single verify PASS·글자ops주입확인·금지연산자0·grade무수정 |
| 2026-06-19 | tester | Phase C 독립검증(8항목: selftest회귀·per_player·콘텐츠주입·좌표변환동일행렬·single·금지연산자·하위호환폴백·엣지) | 종합 PASS(8/8, 수정요청0) |
| 2026-06-19 | reviewer | Phase C 코드리뷰(불변제약·좌표변환정합·flatten·piece매핑·Phase D연결) | 통과(치명0, 🟡2, 🟢4) — transform복제 동기화 후속리스크 명시 |
| 2026-06-19 | developer | Phase D 사전조사: V넥 .ai 13개 확인·PyMuPDF변환 검증 | ⛔차단2건(PyMuPDF=path라 parse_svg 0개·소매조각 소실) — 사용자 확인 대기 |
| 2026-06-19 | developer | Phase E: order.py 신양식③ 파서(_parse_form_stiz)+_norm_header nbsp보강 / V넥 38건 job | 파싱38행11명·produced38/verify_pass38·육안6건PASS·금지연산0·order.py만수정 |
| 2026-06-19 | developer | Phase D-1: ai_to_svg.jsx 신설(일러스트 SVG직접내보내기 배치·해결책A 자동화, 두스키마·ENTITIES·polyline리스크주석) | 작성완료(사용자 GUI 실행 산출물, engine 무수정) |
| 2026-06-19 | planner-architect | Phase D 재설계(기존 path SVG 13개 발견): path→polyline 전처리 변환기 svg_normalize.py + V넥 preset 설계. XL.svg 실측(닫힘조각 앞/뒤 2개·곡선0·소매부재 확인) | 완료(설계만). ⛔잔존:소매부재·빈템플릿미확보 |
| 2026-06-19 | developer | Phase D 구현 완료: svg_normalize.py(path→polyline 변환기·중복제거·닫힘=시작≈끝)+cli normalize-svg+V넥 13개 변환+preset+빈템플릿 job 스모크 | selftest PASS·13개 조각수=2 전수·preset유효·스모크 verify PASS(김경원20/이순신7)·금지연산자0·불변제약준수 |
| 2026-06-19 | reviewer | Phase D 코드리뷰(불변제약 git diff·svg_normalize 정확성/견고성·임계·이중flip·preset svg_index·음수좌표 무해성·Phase E연결) | 통과(치명0, 🟡2[음수bbox·svg_index역전근소], 🟢4). cli.py 73+/0-·코어 전부 무수정 확인 |
| 2026-06-19 | tester | Phase D 독립검증(13항목: selftest회귀·조각수·변환정확성수동검산·CLI·preset·job스모크XL/M/L·엣지) | 🔴종합 FAIL(11/13). 코드/변환기/preset 정상이나 **커밋된 비-XL 12개 SVG 좌표 오염→비-XL 출력 앞판 소실**. reviewer가 🟡로만 본 음수bbox가 실제로 출력 깨뜨림 확인. 수정요청1·errors.md기록 |
| 2026-06-19 | developer | Phase D 되돌림1(방식A): scripts/ai_to_path_svg.py 신설→원본 .ai 13개 재추출→기존 normalize-svg 재변환·덮어쓰기(engine/cli/코어 무수정) | ✅13개 viewBox 가로3401·양수·조각2·앞0뒤1 통일. 비-XL(5XS/M/L)+XL+5XL 육안 앞판 정상·page rect 가로·verify PASS·금지연산자0·selftest회귀 PASS |
| 2026-06-19 | tester | Phase D 되돌림1 재검증(7항목: selftest·viewBox/양수전수·★비-XL앞판육안★·verify/금지연산자·스크립트·preset·U넥회귀) | ✅종합 PASS(7/7). 비-XL 5XS/M/L/5XL+XL 미리보기 육안 앞판소실 해소·page rect 가로 확정 → **되돌림1로 이전🔴FAIL 해소 확정**. 수정요청0 |
