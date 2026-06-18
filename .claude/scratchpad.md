# 작업 스크래치패드

## 현재 작업
- **요청**: job(선수별 통합 출력) engine/job.py 신설 — 주문서×디자인→선수별 배번/이름 출력.
- **상태**: split 기본값 **per_player 확정**(2026-06-18) → **planner-architect 설계 진행 중**
- **현재 담당**: planner-architect (job 설계)

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

## 구현 기록 (developer)
(job 대기)

## 테스트 결과 (tester)
(job 대기)

## 리뷰 결과 (reviewer)
(job 대기)

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|

## 작업 로그 (최근 10건만 유지)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
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
