# 작업 스크래치패드

## 현재 작업
- **요청**: 이슈1 번호 글리프셋(디자이너 athletic 블록체) — 추출→렌더→폴백→job 스모크→검증→기록. 끝까지 완료.
- **상태**: ✅ **구현·검증 완료**(developer). number_glyphs.py 신규(추출/렌더)+text place_number glyph_source 분기(기본값 None=폰트폴백)+job 글리프셋 로더+cli number-glyphs+preset glyph_source. 10글리프 추출·잉크중심0.0pt·V넥 job verify2/2·금지연산자0·육안 블록체·U넥회귀0·불변제약 무수정. PM(tester/커밋) 대기.
- **현재 담당**: developer 완료 → pm(tester 검증/커밋) 대기. 변경: engine/{number_glyphs.py 신규, text.py, job.py, cli.py}+preset.json+number_glyphs.json(신규).

## 진행 현황
| 단계 | 내용 | 상태 |
|------|------|------|
| Step1 | 미커밋 정리(text.py TTF폰트 fix 등) | ✅ 푸시 |
| Phase B | text.py place_number/place_name + reference CLI | ✅ (tester 15/15) |
| Phase C | job 통합(빈템플릿 base+flatten+앞/뒤번호·이름 정밀주입) | ✅ (tester 8/8) |
| Phase D | V넥 패턴 13사이즈(svg_normalize) + preset | ✅ (되돌림1로 좌표오염 FAIL 해소, tester 7/7) |
| Phase E | STIZ 신양식 주문서 파서 + 전선수 PDF 38건 | ✅ (tester 7/7, verify 38/38) |

## 백로그 (차단 아님, 후속)
- **번호 가로중심 1~3pt 미세조정**: §4대로 구현했으나 사이드베어링 비대칭. cowork 오버레이 확인 후 preset 값으로 조정(코드 무수정 가능).
- **주문서 자동판별 과적합 가드(reviewer 지적)**: 현 parse_order ①→③→② 순이 "③헤더가 12행 밖"이라 우연히 동작. ③헤더가 12행 이내인 다른 STIZ 주문서면 ①이 선점→qty 깨짐. parse_order에서 ③('순번'컬럼) 먼저 식별 또는 _parse_form1에 가드 1줄 권장.
- **design_region_pt**: V넥이 U넥 값 재사용. cowork 정합 확인 후 빈템플릿/완성본으로 정밀 재추출 여지.
- 하의 사이즈 분리(상하의 별 size) / shrink 등방한계 / preset sizes.scale 미사용 / 이름 세로 descent 받침~3.6pt / svg_index 높이정렬 사이즈확장 시 재확인.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) + build_layouts/grade **시그니처·동작 무수정**(신규 인자 기본값 확장만). device CMYK 무손실. 글자 `k` fill만(RGB/투명도/이미지 금지). 빌드0·순수Python. 폴더+JSON. CLI 단독 검증.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left·등방 contain). grade.py `_piece_transform`이 정답(job.py에 `_job_piece_transform`로 복제 — grade 공식 변경 시 동기화 필요).
- **글자 주입**: place_number/place_name(text.py)이 디자인좌표 ops 생성 → job이 조각 transform(cm)으로 감싸 시트좌표 주입. Piece.extra_ops 경로. 디자인 Form 불변, verify PASS 유지.
- **V넥 완성본 §4 수치**(페이지 4478.74×5669.29): 앞번호 center[1389,4184] cap310 / 뒤번호 [3217,4342] cap539 / 이름 center_x3219.8 baseline4765.7 em136.40 pitch195.4 font HY헤드라인M(=H2hdrM). 앞/뒤분할 x=2239.37.
- **V넥 패턴**: 앞=svg_index0/뒤=idx1(U넥과 역순!), 소매 없음(앞/뒤 2조각). viewBox 마커시트 4478×3401.
- ⚠️ **변환 함정(errors.md)**: 조각수=2+verify PASS여도 viewBox 세로(5669)/음수좌표면 앞판 소실 → **비-XL job 미리보기 육안 필수**. parse_svg는 polyline만 → path SVG는 svg_normalize 전처리 필요.
- ⚠️ pikepdf 출력 비결정적(XObject 이름 랜덤): 회귀는 이름 정규화 후 콘텐츠 비교.
- ⚠️ STIZ 신양식 헤더에 nbsp(\xa0) 섞임 → _norm_header에서 제거.

## 핵심 모듈/산출물
- engine: text.py(place_*), reference.py(build_area_preset), job.py(run_job 정밀배치), svg_normalize.py(path→polyline), order.py(양식①/②/③ STIZ), flatten.py.
- CLI: grade/job/reference/normalize-svg/flatten/order/selftest.
- 보조: scripts/ai_to_path_svg.py(.ai→path SVG), illustrator-scripts/ai_to_svg.jsx(일러스트 배치변환, 곡선패턴용 보관).
- 데이터: data/patterns/농구_U넥_양면/, 농구_V넥_양면/(SVG13+preset). data/jobs/(.gitignore).

## 실데이터 / git
- 빈템플릿/완성본/주문서: `C:/Users/user/Desktop/새 폴더/` (연세대 V넥 템플릿.ai / XL.ai / 260213_추가주문서.xlsx)
- V넥 패턴 원본 .ai: `G:/공유 드라이브/디자인/2026 커스텀용 패턴/.../V넥 양면유니폼 스탠다드/`
- 폰트: data/fonts/HY헤드라인M.ttf(번호·이름 공통), Pretendard-Black/Bold.otf
- 산출(cowork 검증용): data/jobs/260619_연세대V넥/output/{XL_22_김윤서.pdf, 2XL_05_이주영.pdf}
- git: origin=cobby8/grader-v2, main. **미푸시 0개**(c11b4fa까지 푸시).

## 기획설계 (planner-architect)
(완료 — 상세는 git 히스토리 + decisions.md/architecture.md)

## 구현 기록 (developer)
(완료 — Phase B~E, 상세는 git 히스토리)

### 이슈2 — place_number/place_name 잉크 bbox 기준 중앙정렬 (2026-06-19)
📝 구현: place_number 중앙정렬을 advance 박스 기준 → **실제 잉크 bbox 기준**으로 변경. "1"처럼
advance 박스 내 잉크가 좌측 치우친 글자가 ~27pt 밀리던 버그 교정. place_name 도 가로 잉크중심으로 통일.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| engine/text.py | place_number: advance 임시배치(segs) → 배치좌표계 잉크 min/max x·y 측정 → shift_x/baseline_y 로 잉크중심을 center_x/center_y 에 평행이동 | 수정 |
| engine/text.py | place_name: 음절 임시배치(segs) → 가로 잉크 min/max x 측정 → shift_x 로 가로 잉크중심을 center_x 에 정렬(세로 baseline_y 고정 유지) | 수정 |

- 측정은 기존 `_glyph_ink_bounds`(폰트단위 경계) 재사용 + `시트좌표=폰트좌표×s+dx` 환산(transform/scale 반영).
- 시그니처·ASCII ops·k fill·q…Q 래핑 무수정. 하드코딩 0(좌표·크기·색 전부 인자).

💡 tester 참고:
- 회귀: `python -m engine selftest` → PASS(전 항목).
- 번호 잉크중심 오차(cap539, center 1000,2000): **"1"·"11"·"20"·"22" 모두 x오차 +0.000 / y오차 +0.000pt** (이전 "1"/"11" -27.6pt → 교정).
- 이름 가로 잉크중심(center_x 3219.8): 김경원/김윤서/이해솔/박 모두 +0.000pt.
- 금지 op(Do/rg/RG/ca/CA) 전부 없음. 빈/공백/None/누락글리프 안전처리 정상.
- 검증법: ops 문자열의 m/l/c 좌표점을 모아 min/max bbox 중심 계산 → center 와 비교.

⚠️ reviewer 참고:
- place_number 의 scale 결정(rep=대표 잉크높이 최대 글리프)은 그대로 유지. 정렬만 잉크 기준으로 분리.
- place_name 세로는 의뢰서 §4 요구(baseline 고정)대로 baseline_y 유지 — 가로만 잉크 보정.

### 이슈4 — 빨간 재단선(stroke)+너치 보존 (2026-06-19, developer)
📝 구현: 디자인의 빨간 재단선(CMYK 0,0.96,0.95,0)을 추출→조각 매핑→클립 '밖'(extra_ops)에
재주입해 너치까지 잘리지 않고 출력에 보존. job.py + preset(V넥 cutline 키)만 수정(불변 제약 준수).

**🔴 소스 확인(중요)**: 템플릿 .ai PDF 콘텐츠에 재단선 레이어(MC1/MC2/MC3)는 있으나 **내용이 비어 있음**
(`/Layer /MC1 BDC` 바로 뒤 `EMC` — 그림 0개). 실제 재단선 벡터는 일러스트 전용 AIPrivateData(압축
바이너리)에만 존재 → **PDF로 읽히는 빨간 stroke = 0개**(flatten 후에도 0). 즉 현 템플릿은 추출 0이 정상.
→ 코드는 "있으면 보존/없으면 0+경고" 설계. 재단선 보이는 소스로 재내보내면 동일 코드가 자동 보존.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| engine/job.py | `_extract_red_strokes()`: 디자인 1회 훑어 CTM 추적→빨간 stroke(허용오차 tol) 경로를 디자인절대좌표 ops(m/l/c/v/y/h + device K 재지정 + w + S)로 캡처 + bbox 반환 | 수정 |
| engine/job.py | `_map_strokes_to_pieces()`: stroke bbox↔design_region_pt 겹침면적 최대 조각 매핑. 가는 선(폭/높이=0)은 중심점 포함으로 보조 매핑. 겹침 없는 stroke(밴드[0])는 skip+경고 | 수정 |
| engine/job.py | `_build_precise_layout(..., cutline_strokes)`: 매핑 stroke 를 그 조각 transform 으로 _wrap_design_ops 감싸 extra_ops 누적(글자와 동일 경로, 클립 밖) | 수정 |
| engine/job.py | `_count_red_strokes_in_output()` + run_job: 추출 1회(공유 디자인)·summary "재단선 보존" 체크(출력 빨간 stroke ≥ 매핑 기대) + summary.cutline 추적 | 수정 |
| data/patterns/농구_V넥_양면/preset.json | cutline 키 추가{color_cmyk,match_tol,expected_strokes,device_k}(V넥만) | 수정 |

💡 tester 참고:
- selftest 회귀 PASS(①). V넥 job(템플릿,선수 김윤서XL): produced 2, verify 2/2 PASS, cutline found=0(빈레이어 정상)·"재단선 보존" PASS(0≥0)+경고.
- **합성 증명**(평탄화본에 빨간 stroke 3개 주입한 디자인으로 end-to-end 검증): found 3→**mapped 3→출력 빨간 stroke 3개**, 재단선 보존 PASS, verify PASS. 출력 device CMYK = `0 0.96 0.95 0 K`(무손실), 선폭 보존, 너치(조각경계 밖) 미리보기에 빨강으로 살아있음 확인.
- U넥(cutline 키 없음): cutline summary=None, 재단선 체크 미추가, verify PASS — 회귀 0(④).
- 테스트법: job.json 의 outputs[].checks 에서 "재단선 보존" ok/detail 확인 + summary.cutline{found,expected,mapped}.

⚠️ reviewer 참고:
- verify_output(불변)에는 손대지 않음. "재단선 보존"은 job summary/output checks 의 **별도 표식 체크**(verify_pass 에 미포함 — 빈 소스로 전체 FAIL 안 나게).
- CTM 추적은 flatten 의 _mat_mul/_apply 와 동일 식 복제(좌표 일관성). 색·좌표·허용오차·기대수 전부 preset/소스에서(하드코딩 0).
- 밴드[0] 보류: 현 V넥 pieces 2개(앞/뒤)뿐 → 밴드 영역 재단선은 매핑 안 됨(경고 후 skip). 이슈3 밴드 조각 추가 시 자동 연결.
- cowork용 PDF: data/jobs/260619_이슈4검증/output/{XL_22_김윤서.pdf, 2XL_05_이주영.pdf}(실템플릿·빈레이어). 보존 동작 시각증명: data/jobs/260619_이슈4_합성검증/preview/XL_22_김윤서.png(빨간 재단선·너치).

### 이슈3 — 암홀X 전면 교체(밴드 조각 추가, 3조각) (2026-06-19, developer)
📝 구현: V넥 패턴을 '양면 스탠다드'(앞/뒤 2조각) → **'단면 V넥 스탠다드-A(암홀X)' 13개로 정식 교체**.
넥'밴드' 조각이 누락되던 필터 버그를 고쳐 front/back/**band 3조각**으로 완성. 엔진 공개 API 무수정.

**🔴 근본원인(조사기록)**: 밴드 조각은 폭은 충분(1380~1992)한데 **높이만 176pt**로 얇은 가로 띠.
종전 필터 `w<5% or h<5%`(217pt)가 "한 축이라도 작으면 버림" → 밴드(h176<217)를 매번 폐기.
진짜 보조선은 추출 데이터에 0개(접는선/표식은 PDF벡터로 안 잡힘). 실측: 밴드 면적 24만~35만pt².

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| engine/svg_normalize.py | 필터 정정: "한 축이라도 작으면 버림(OR)" → **"양 축 둘 다 작을 때만 버림(AND)" + "면적<min_area_ratio면 버림"**. min_area_ratio=0.002(page_dim²대비) 인자 추가(기본값 확장만). 밴드 보존·0면적 보조선만 제거 | 수정 |
| engine/cli.py | normalize-svg 조각수 표시 기대값 2 → **2 또는 3 둘 다 ✅**(밴드 포함 3조각 정상). 동작 무관, 표시만 | 수정 |
| data/patterns/농구_V넥_양면/*.svg (13개) | 암홀X 13개 .ai → ai_to_path_svg → normalize-svg(수정필터) 재변환 전면 덮어쓰기. 전수 3조각·viewBox 통일 | 수정 |
| data/patterns/농구_V넥_양면/preset.json | pieces에 **band(svg_index:2, design_region_pt:[468,5287,3997,5562])** 추가. front=idx0/back=idx1/band=idx2(높이 내림차순) | 수정 |

**3조각 idx 확정(parse_svg 높이 내림차순)**: front(idx0,h~2419)·back(idx1,h~2311)·band(idx2,h~176).
**밴드 design_region**: 디자인 목둘레 전체 띠 = content_box 가로 전체[468,3997] × front/back 상단~content상단[5287,5562]. contain이 종횡비차 흡수(front/back도 region≠조각 종횡비로 정상동작 중).
**밴드-재단선 연계**: 이슈4 `_map_strokes_to_pieces`가 밴드영역 stroke를 자동으로 band(idx2)에 매핑(면적+중심점 보조). expected_strokes=3 유지(front/back/band 3영역 각1 기대와 정합). preset 조정 불필요.

💡 tester 참고:
- 회귀: `python -m engine selftest` → PASS(필터·cli 수정 후에도).
- 13개 전수: 조각수=3·viewBox 통일(`0 0 4337.01 3401.57` 1종)·양수좌표·높이내림차순·종횡비(front/back~0.7,band~7-11) 모두 PASS.
- 육안(윤곽 시각화 PNG, data/jobs/260619_이슈3검증/outline_check/outline_{5XS,M,L,XL,5XL}.png): 앞(라운드넥)·뒤(V넥)·밴드(좌상단 가로띠+너치) 3조각, 좌우대칭, **앞판 소실 없음**, 밴드 정위치. 빈템플릿이라 색렌더 PNG는 흰색(이슈4와 동일 특성) → 윤곽 PNG로 검증.
- V넥 job per_player(실주문서 38명): 생성 38 / **verify 38/38 PASS**. 출력 글자 k fill `0 0 0 0 k`만, 글자 금지연산자(rg/RG/sc/scn/g/G/ca/CA/gs) 0(scn1·gs1은 디자인임베드 원본 특성, 평탄화본에도 존재).
- 주의입력: 극단 5XS·5XL은 grade로 미리보기 생성(grade_5XS/grade_5XL). 5XL/4XL/3XL은 원본 path 중복 6개→dedup으로 3개(검증됨).

⚠️ reviewer 참고:
- 면적 임계 0.002는 page_dim²대비(하드코딩 아님, 인자). 실측 밴드 최소면적 24만 ≫ 임계(4337²×0.002≈3.8만)라 안전. 진짜 0면적 보조선만 제거.
- 불변 제약: compose/verify/pattern/grade/job/text/flatten 전부 git diff 무수정 확인. 변경=svg_normalize(필터)·cli(표시)·preset·SVG13.
- 밴드 design_region은 빈템플릿 기준 산출 — cowork 정합 확인 후 완성본으로 정밀 재추출 여지(백로그 design_region_pt 항목과 동일 성격).

### 이슈3 마무리 — 단조성 가드 + 3XL 안전 비활성(5XL 오출고 차단) (2026-06-20, developer)
📝 구현: reviewer/tester가 잡은 치명1(3XL.svg=5XL 동일 자산결함)을 **코드로 안전 차단**.
(1)자산결함 자동탐지 가드 신설, (2)3XL을 삭제 아닌 disabled '표식'으로 봉인(복원 쉬움),
(3)job이 disabled 사이즈를 5XL 대체 없이 안전 skip, (4)결함 3XL.svg 삭제. 엔진 코어 무수정.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| engine/svg_normalize.py | **신규 헬퍼 `check_size_monotonicity()`** 추가(기존 함수 무수정·순수 추가). 여러 사이즈 SVG를 parse_svg(읽기전용)로 읽어 (A)서로 다른 사이즈인데 조각좌표 100% 동일(md5 해시)→duplicates 검출+passed=False, (B)size_order 순 조각높이 단조증가 위반(동일/감소)→경고. 보조 `_piece_coord_hash()`도 추가 | 수정(추가만) |
| engine/cli.py | normalize-svg **배치 모드 끝에서 가드 호출**: 성공한 (사이즈명→출력경로) converted_map 누적 → 2개↑면 check_size_monotonicity 실행, 결과 출력. 좌표동일(자산결함) 발견 시 **return 1(출고 차단)** | 수정 |
| data/patterns/농구_V넥_양면/preset.json | 3XL sizes 항목에 `"disabled": true` + `"disabled_reason"` 표식(삭제 아님→복원 쉬움). pattern_file은 그대로 둠(미참조) | 수정 |
| engine/job.py | size_map 구성 시 **disabled 사이즈 제외** + disabled_map 별도 보관. 주문 루프에 disabled 전용 분기 추가→3XL 주문 오면 크래시 없이 **명확 사유로 skip + 경고**(5XL 등 대체 원천차단). summary에 disabled_sizes 추가 | 수정 |
| data/patterns/농구_V넥_양면/3XL.svg | **결함 파일 삭제**(git rm). preset disabled로 미참조라 안전. 올바른 3XL.ai 받으면 normalize-svg로 재생성 | 삭제 |

**3XL 복원법(올바른 .ai 재확보 시)**: ①올바른 농구유니폼_V넥_스탠다드_암홀X_3XL.ai 확보 →
②`scripts/ai_to_path_svg.py`로 path SVG화 →③`python -m engine normalize-svg`로 3XL.svg 재생성
(배치로 돌리면 단조성 가드가 자동으로 5XL과 다른지 검증) →④preset.json 3XL에서 `"disabled"`·
`"disabled_reason"` 두 키만 삭제. 그러면 즉시 12개→13개 복원.

💡 tester 참고:
- ①selftest: `python -m engine selftest` → **PASS**(멱등 재실행도 PASS).
- ②단조성 가드: 정상12개(5XS~5XL, 3XL제외) check_size_monotonicity → **passed=True·duplicates0·
  non_monotonic0**(높이 1966.7→2644.7 단조증가, 해시 전부 상이). 5XL을 3XL로 복제한 결함 재현 시
  → **passed=False·duplicates[('3XL','5XL')]·4XL 단조감소 경고**(검출 성공). CLI 배치 통합도 동일:
  결함포함 return 1, 정상12개 return 0.
- ③V넥 job(3XL 2명+XL/M/5XL/4XL 합성주문, 템플릿.ai): produced 4 / **verify 4/4 PASS·fail0**.
  **3XL 2건 모두 skip(사유 명시)·3XL 출고 0건·5XL은 주문분 1건만(3XL대체 0)**. disabled_sizes
  summary 추적됨. 12개 전수 parse_svg: 3조각·양수·높이내림차순 PASS(밴드 175.7 일정·앞판 소실0).
  산출물: data/jobs/_qa_이슈3마무리/output(4 PDF).
- ④U넥 회귀: U넥 preset disabled키 없음→disabled_map 빈dict(영향0), size_map 정상, XS.svg 3조각.
  `s.get("disabled",False)` 기본 False라 disabled 없는 preset은 기존과 100% 동일 동작.
- ⑤3XL.svg 삭제 확인(파일 없음)·preset 3XL disabled=true+사유 확인(활성 12/총 13).
- 주의입력: disabled 사이즈 주문(3XL)·빈사이즈·없는사이즈 모두 크래시0 skip. 가드는 사이즈 1개일 땐 미실행(비교 대상 없음).

⚠️ reviewer 참고:
- **불변 제약 100% 준수**: HEAD 대비 diff stat — compose/verify/grade/pattern/text/flatten/reference/
  order/preview/pdfutil **전부 무수정(diff 0)**. 변경 engine=cli·job·svg_normalize 3개뿐.
  check_size_monotonicity는 순수 추가(기존 normalize_svg 시그니처·동작 불변), run_job/cmd_normalize_svg
  시그니처 불변(내부 구현만 disabled필터·가드블록 추가).
- 가드는 parse_svg를 '지연 import + 읽기전용'으로 호출 → engine 코어 무수정. 해시는 좌표 반올림(2자리)
  후 md5(부동소수 미세오차 오판 방지). piece_index=0(앞판) 기준 비교가 기본.
- disabled는 '대체'가 아니라 '차단': size 정확일치만 매칭되므로 3XL→5XL 대체 경로 자체가 없음(이중 안전).

### 이슈3 grade회귀 수정 — disabled를 sizes표식→disabled_sizes 섹션으로 일원화 (2026-06-20, developer)
📝 구현: V넥 grade 크래시(FileNotFoundError: 3XL.svg) 회귀를 근본 해소. 결함 3XL을 sizes
'내부 표식(disabled:true)' → preset **최상위 `disabled_sizes` 섹션으로 이동**. build_layouts는
sizes만 순회하므로 3XL이 sizes에 없으면 3XL.svg를 안 읽어 크래시 사라짐(grade.py 무수정).

**🔴 근본원인**: sizes에 disabled:true로 남겨두면 build_layouts(`for size in preset["sizes"]`)가
표식을 모른 채 3XL.svg를 parse_svg로 읽다 크래시. build_layouts/grade는 불변제약→손댈 수 없음.
→ 데이터를 순회 대상(sizes)에서 빼는 게 정답. job은 별도 섹션에서 disabled를 읽어 처리.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| data/patterns/농구_V넥_양면/preset.json | sizes에서 3XL 항목 **제거**(13→12개) + 최상위 `disabled_sizes:[{name:"3XL",reason:...}]` 섹션 추가 | 수정 |
| engine/job.py | size_map은 sizes 전체(출고가능만 들어있음). disabled_map을 **`preset.disabled_sizes`(={이름→사유})에서** 읽도록 변경. 3XL 주문 행→"비활성(자산 결함): 사유" 명확경고+skip(일반 missing과 구분). summary.disabled_sizes=dict(disabled_map). 기존 `s.get("disabled")` 표식 로직 전부 disabled_sizes 방식으로 일원화 | 수정 |

**검증 결과(전 항목 통과)**:
- ① selftest: PASS(디자인무손실·CMYK·투명도없음·Do24·inkcov편차0).
- ② **V넥 grade 크래시 해소**: 템플릿.ai로 grade → 배치 **36회=12사이즈×3조각** PASS·**FileNotFoundError 없음**·미리보기 12장. 3XL 미포함 12개 정상생성.
- ③ V넥 job(3XL 2명+XL/2XL/M/4XL/5XL): produced 5·verify 5/5·fail0. **3XL 2건 모두 skip(결함 사유 명시)·3XL 출고 0·5XL 출고 1(주문분만, 3XL 대체 0)**. summary.disabled_sizes{3XL:사유} 기록.
- ④ U넥 회귀: disabled_sizes 키 없음→`get("disabled_sizes",[])`=[]→disabled_map 빈dict→기존 동작 100%. U넥 grade 배치3회 PASS.
- ⑤ 단조성 가드: 정상12개 passed=True·dup0·non_mono0. 결함재현(5XL=FAKE3XL)→passed=False·duplicates[('FAKE3XL','5XL')]·4XL 단조감소 검출.
- 불변제약: engine 변경=cli/job/svg_normalize 3개뿐. grade/compose/verify/pattern/text/flatten **무수정**(git diff 미포함). 이번 작업 실제 수정=preset.json+job.py.

💡 tester 참고:
- 재현 산출물: data/jobs/_qa_이슈3_grade회귀/{grade_out.pdf(12사이즈), uneck_out.pdf, job/job.json(3XL skip 증거)}.
- grade 명령이 더는 3XL.svg를 찾지 않음(sizes 12개만 순회). job.json의 skipped/disabled_sizes에서 3XL 결함 사유 확인.
- 주의입력: 3XL 주문(결함skip)·없는사이즈(missing)·빈사이즈 모두 크래시0. disabled_sizes 없는 preset은 기존과 동일.

⚠️ reviewer 참고:
- disabled_map 구조가 dict→`{이름:사유}`(문자열)로 단순화됨. 이를 쓰는 3곳(시작안내·주문분기·summary) 모두 맞춰 수정함.
- '대체'가 아니라 '차단': size_map에 3XL 자체가 없으므로 3XL→5XL 대체 경로가 원천 부재(이중 안전).

### 이슈1 — 번호 글리프셋(디자이너 athletic 블록체) 추출·렌더 (2026-06-20, developer)
📝 구현: 번호를 폰트(HY헤드라인M) 대신 **디자이너가 .ai 에 직접 그린 0~9 번호 도형(글리프셋)**으로
렌더. .ai ArtBox 안 단색 fill 10개를 추출→JSON 저장→번호 렌더 시 조립. 글리프셋 없으면 폰트 폴백(출고안전).

**🔴 소스 확정**: 템플릿.ai ArtBox[585,4673,3923,5211] 안 fill 경로 정확히 10개. x오름차순=order"1234567890"
(맨왼쪽 좁은 글리프 폭156=‘1’). cap_height≈538.6. 색은 cs/scn 1회로 10개 공유. 구멍은 다중 subpath+non-zero f.

| 파일 | 변경 내용 | 신규/수정 |
|------|----------|----------|
| engine/number_glyphs.py | **신규**: extract_number_glyphs(CTM추적→artbox내 fill 캡처→x정렬→order매핑→베이스라인원점 정규화 subpath[m/l/c/re/h/v/y 보존]+width+cap_height) / save·load_glyphset_json / render_glyph_number_ops(이슈2 잉크중심 정렬·CMYK k fill·q…Q·구멍 f) | 신규 |
| engine/text.py | place_number 에 **glyph_source=None 인자 추가**(기본값 확장만). None 아니면 render_glyph_number_ops 위임(지연 import), None이면 기존 폰트 폴백 100% 유지 | 수정 |
| engine/job.py | **_load_glyph_source 신규**(preset._dir 기준 JSON 로드+캐시, 실패시 경고+None=폰트폴백). _inject 의 number 분기가 area.glyph_source 읽어 place_number 에 전달 | 수정 |
| engine/cli.py | **number-glyphs 서브커맨드 신규**(--src/--out/--artbox/--order, 추출→저장→글리프별 폭·cap·subpath 출력). 기존 명령 무수정·추가만 | 수정 |
| data/patterns/농구_V넥_양면/preset.json | front/back_number_area 에 "glyph_source":"number_glyphs.json" 추가 | 수정 |
| data/patterns/농구_V넥_양면/number_glyphs.json | **신규**(추출 결과 10글리프). 소스: 템플릿.ai | 신규 |

**검증 결과(전 항목 통과)**:
- ① selftest 회귀 PASS(멱등 재실행도 PASS).
- ② number-glyphs CLI: 0~9 10개 추출→JSON. 폭 ‘1’=156·나머지 297~334·cap_height≈538.6·order 정합·구멍 subpath(4=2/6·9·0=3/8=5, 나머지1). ※스펙의 ‘4/6/9/0=2,8=3’은 추정치, 실소스는 위 값(각 구멍=별 subpath라 8은 구멍2+detail). non-zero f로 구멍 정상.
- ③ 글리프셋 "1"/"11"/"20"/"7" 렌더: **잉크중심 x·y 오차 전부 +0.0000pt**(±2pt 충족, 이슈2). 잉크높이=539=cap. 폰트와 모양 다름(‘7’ 글리프폭307.4 vs 폰트304.2·세그17 vs 11, ‘22’ 글리프602.5 vs 폰트664.0).
- ④ glyph_source=None(또는 미지정)→폰트 폴백. 명시 None==기본값 동일 출력 확인.
- ⑤ V넥 job(템플릿.ai, 김윤서22/XL·이주영7/2XL, glyph_source preset) per_player: produced2·verify 2/2 PASS. 출력 글자 3그룹=앞번호center(1389,4184)·뒤번호(3217,4342)·이름cx3220 정합. 뒤번호 출력폭=글리프602(≠폰트664)로 **글리프셋 출처 확정**. 페이지 글자색 k만, rg/RG/g/G/sc/scn/ca/CA/gs 0(scn/gs/Do는 디자인 임베드 원본). **육안(검정 임시색 렌더): "11" 디자이너 athletic 블록체(밑단 플레어·각진 상단)·앞/뒤 위치 정상·이름 정합**.
- ⑥ U넥: preset 에 glyph_source 키 없음→_load_glyph_source=None→place_number 폰트 폴백(④와 동일 경로). place_number 새 분기는 glyph_source 부재 시 기존과 byte 동일(회귀0).
- 불변제약: git diff — compose/Piece/parse_svg/verify_output/build_layouts/grade **무수정**. 변경=text(인자+분기)·job(헬퍼+전달)·cli(서브커맨드)·preset. 신규=number_glyphs.py·json. device CMYK 무손실·글자 k fill만·빌드0·좌표/색 preset·소스출처(하드코딩0).

💡 tester 참고:
- 재현: `python -m engine number-glyphs --src "(템플릿.ai)" --out data/patterns/농구_V넥_양면/number_glyphs.json`.
- cowork PDF(글리프셋 번호 포함): data/jobs/_qa_이슈1_글리프셋/output/{XL_22_김윤서.pdf, 2XL_07_이주영.pdf}(preset 흰색). 육안색 버전: data/jobs/_qa_이슈1_육안/preview/{XL_11_김윤서.png, 2XL_20_이주영.png}.
- 검증법: render_glyph_number_ops ops 의 m/l/c 좌표 bbox중심 vs center 비교(±2pt). 폰트 출력과 폭·세그수 차이로 출처 구분.
- 주의입력: 글리프셋에 없는 문자(영문·특수기호)→통째 미출력+경고. 빈/None→빈ops. glyph_source 경로 오타→경고+폰트 폴백(크래시0).

⚠️ reviewer 참고:
- 추출 CTM 추적은 job._extract_red_strokes / flatten._mat_mul 과 동일 식 복제(좌표 일관). artbox/order 는 인자(하드코딩 아님, CLI 기본값만).
- 글리프셋 개수≠order 길이면 ValueError(추출 bbox 표시)로 조기 차단 — artbox 오설정 안전망.
- place_number 분기는 glyph_source!=None 일 때만 위임(지연 import). 폰트 폴백 경로·시그니처(기본값 추가만)·ASCII ops·k fill·q…Q 규약 전부 유지.
- subpath 정규화는 베이스라인 잉크 좌하단 원점 → 렌더 시 자유 배치(이슈2 잉크중심과 독립).

## 테스트 결과 (tester)
(완료 — B 15/15, C 8/8, D 7/7(되돌림1), E 7/7)

### 이슈2 독립검증 (2026-06-19, tester) — place_number/place_name 잉크 bbox 중앙정렬
폰트 data/fonts/HY헤드라인M.ttf. ops의 m/l/c 좌표를 직접 추출 + fontTools BoundsPen으로
베지어 곡선 실제 극값 잉크 bbox까지 2중 측정해 교차 검증(코드 무수정, 검증만).

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ PASS | 전 항목 PASS, 멱등 재실행도 PASS |
| 2) place_number 잉크중심(±2pt) | ✅ PASS | 아래 번호별 수치 참조, 전부 0.0000pt |
| 3) place_name 가로잉크중심+baseline고정 | ✅ PASS | 김경원/김윤서/이해솔/박 가로오차 0.0000pt, y범위에 baseline 포함(고정 유지) |
| 4) ops 무결성(q…Q+k fill만) | ✅ PASS | q시작/Q끝/f/단일 k라인(`0 0 0 1 k`), Do·rg·RG·sc·scn·ca·CA·gs 0 |
| 5) 엣지(빈·None·공백·누락·자릿수) | ✅ PASS | 빈''/None/공백/😀·€(진짜 누락)/cap0/em0/pitch0 → 빈 ops+경고, 1~3자리 정상, 크래시 0 |
| 6) 회귀 V넥 job 스모크 | ✅ PASS | 38명 생성·verify 38/38 PASS, 01/11번 산출물 잉크 정상, page Do는 디자인임베드(정상) |

📊 종합: 6/6 PASS, 실패 0

**2) 번호별 잉크중심 오차(cap_h=539, center=(1000,2000)) — BoundsPen 곡선극값 기준:**
| 번호 | 잉크폭(pt) | 잉크높이(pt) | x중심오차 | y중심오차 |
|------|-----------|-------------|----------|----------|
| 1    | 180.91 | 539.00 | 0.0000 | 0.0000 |
| 11   | 550.77 | 539.00 | 0.0000 | 0.0000 |
| 20   | 647.04 | 540.19 | 0.0000 | 0.0000 |
| 22   | 664.04 | 539.00 | 0.0000 | 0.0000 |
| 7    | 304.19 | 539.00 | 0.0000 | 0.0000 |
| 100  | 969.36 | 539.00 | 0.0000 | 0.0000 |

- "1"은 잉크폭 180.91로 좁지만 중심오차 0.0 → 이슈2 핵심(좁은 "1"/"11"이 -27.6pt 밀리던 버그) 완전 교정 확인.
- 잉크높이 모두 ~539(목표 cap_h) 일치 → scale 결정도 정상.
- 완료기준 §2(±2pt 이내) 충족. 명세서 이슈2 요구(advance→잉크 bbox 평행이동) 정확 구현.
- 참고: 'A'는 HY헤드라인 폰트에 실재(라틴 포함)하므로 ops 생성이 정상 — 누락처리는 😀/€ 등 진짜 미보유 글자에서 검증.
- 수정 요청 없음(전 항목 PASS).

### 이슈4 독립검증 (2026-06-19, tester) — 빨간 재단선(stroke)+너치 보존
실데이터엔 재단선 PDF벡터 0개(PM확인)이므로, 합성(synthetic) 입력으로 "있으면 보존하는가"를
end-to-end 검증. 평탄화본에 빨강 stroke(0,0.96,0.95,0) 주입 → V넥 job per_player 실행 →
출력 PDF 콘텐츠 직접 파싱 + 미리보기 PNG 육안. 코드 무수정(검증만).

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ PASS | 전 항목 PASS, 멱등 재실행도 PASS |
| 2) 합성 재단선 보존+너치 클립 미절단 | ✅ PASS | found3→mapped3→출력 stroke3, 너치(가로선·면적0)도 중심점 보조매핑으로 back 보존. 미리보기 PNG에 빨강선 3개(앞/뒤 세로+너치 가로) 육안 확인 |
| 3) 색 무손실(device CMYK) | ✅ PASS | 출력 stroke 3개 전부 `0 0.96 0.95 0 K`. rg/RG/sc/scn/g/G 0개. 글자 k fill 유지 |
| 4) 매핑 정확성 | ✅ PASS | 앞판영역 stroke→front, 뒤판영역+너치→back. region 밖 stroke→보류+경고(bbox 명시) |
| 5) 실데이터 동작 | ✅ PASS | 실템플릿(재단선 0): found0, 재단선보존 0≥0 통과, 크래시0, verify PASS, 적절 경고 |
| 6) 하위호환 | ✅ PASS | U넥(cutline키 없음): cutline summary=None, 재단선체크 미추가, verify PASS. V넥 grade 회귀 26/26 PASS |
| 7) 불변제약 | ✅ PASS | compose/verify/pattern/grade/pdfutil 무수정(git 확인). job.py만 변경(+357/-4, 삭제4줄=인자추가·변수교체) |

📊 종합: 7/7 PASS, 실패 0

**핵심 증명(너치 클립 미절단) — 결정적:**
- back 조각 클립 우측경계 = 시트 x=4023.3 (디자인 x=4122.4). region 우측=3997.
- 너치를 디자인 x[3700,4200](중심3950<region3997→매핑, 끝4200>클립4122→클립밖)으로 합성.
- 출력 너치 시트 x범위=[2821.1, **4099.2**] → 클립경계 4023.3을 **+75.9pt 넘어 온전 보존**.
  → 클립으로 잘렸다면 4023.3에서 끊겼어야 함. extra_ops(클립 밖 렌더)가 너치를 살림을 입증.
- 미리보기 PNG에서도 너치 가로선이 우측에 끊김 없이 한 줄로 육안 확인.

**관찰(차단 아님, 설계 특성):**
- 너치 bbox '중심'이 design_region_pt 밖이면 면적0+중심점매핑 모두 실패→보류+경고(정상 동작).
  실무 너치는 경계를 '약간' 넘으므로 중심은 region 안이 정상. 다만 region을 크게 벗어나는
  비정상/대형 너치는 보류됨 — 이슈3 밴드 조각 추가 또는 region 여유 확장으로 자동 연결 가능.
- preset 글자 color_cmyk=[0,0,0,0](흰색)이라 미리보기에 디자인 본체·글자가 흰배경에 안 보임
  (재단선만 빨강으로 보임). 색값 자체는 preset 설정값이며 k fill 연산자 정상 — 이슈4 무관.

### 이슈3 독립검증 (2026-06-19, tester) — 암홀X 전면교체(밴드 3조각)
빈템플릿 base. parse_svg 13전수 + 필터 변경 부작용 형식증명+실데이터 비교 + 조각 윤곽 PNG 5사이즈
육안(Phase D 함정 재점검) + job 38명 출력 PDF 콘텐츠 직접 파싱(Do수·k fill·page rect) +
밴드-재단선 매핑 단위검증 + 사이즈 단조성/좌표 hash. 코드 무수정(검증만).

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ PASS | 종합 PASS, 멱등 재실행도 PASS |
| 2) V넥 13개 전수 parse_svg | ⚠️ 부분FAIL | 조각=3·viewBox `0 0 4337.01 3401.57` 1종·양수·내림차순·종횡비 전부 정상. **단 3XL.svg 치수 오염(아래 🔴)** — 구조는 통과, 치수만 틀림 |
| 3) ★미리보기 육안(Phase D 함정)★ | ✅ PASS | 5XS·M·L·XL·5XL 윤곽 PNG: 앞(라운드넥)·뒤(V넥)·밴드(좌상단 너치띠) 3조각 모두 존재·좌우대칭·**앞판 소실 없음**·밴드 정위치. 비-XL도 전부 가로(D 함정 해소). 글자 위치도 정합(아래) |
| 4) preset 3조각 유효성 | ✅ PASS | pieces front/back/band, svg_index 0/1/2 정합, 글자영역 piece_id(front/back) 유효, band region=content가로[468,3997]×띠[5287,5562] |
| 5) verify + 금지연산자 | ✅ PASS | job 38명 생성38/verify38 PASS·FAIL0. 전수 Do=3(밴드포함 3조각 임베드)·k fill 전부 `0 0 0 0 k`·rg/RG/sc/scn/Image 0. grade 전사이즈 배치39(13×3) PASS |
| 6) U넥 회귀(필터 부작용) | ✅ PASS | 형식증명(min_dim²0.0025>min_area0.002 → OLD보존조각 NEW 100%보존) + 실데이터 비교(OLD조각⊆NEW조각, NEW가 버린 OLD조각=0, 추가보존=밴드만) + U넥 parse 3조각 유지 + U넥 grade 배치3 PASS |
| 7) 밴드-재단선 연계(이슈4) | ✅ PASS | 합성 재단선 밴드영역 가로띠+너치(높이≈0) 2개 모두 band(idx2) 매핑, front/back도 각 매핑, 보류경고0 |
| 8) 불변제약 git diff | ✅ PASS | compose/verify/pattern/grade/text/flatten/job 무수정(parse_svg/build_layouts/Piece 포함). 변경=svg_normalize(필터)·cli(표시2or3)·preset(band)·V넥SVG13 |

📊 종합: 7/8 PASS, 1 부분FAIL(3XL 치수). **밴드 복원·필터·불변제약·육안은 전부 PASS이나 3XL.svg 자산 오염으로 출고 차단.**

🔴 **재현 확정(reviewer 치명1과 일치)**: 3XL.svg front 좌표 hash(b4d45aff)가 5XL과 100% 동일.
사이즈 단조(인접 +56.5pt) 깨짐: 2XL2475.1 → 3XL **2644.7(=5XL값)** → 4XL2588.2(진짜) → 5XL2644.7.
정상이라면 3XL≈2531.6. → 3XL 주문 선수에게 5XL 크기 출고 불량. errors.md "초록불이어도 치수만 틀림"
함정의 변종(조각수3·viewBox·OOB·정렬·verify·selftest 6신호 통과). **단조성/좌표hash 점검이 유일 탐지법.**
원인=원본 3XL.ai 자산결함(developer 코드결함 아님). 수정요청 등록 — cowork 3XL.ai 재확보 후 3XL.svg만 재변환.

**핵심 증명:**
- 글자 정합(XL_22): 출력 글자 ops 3그룹 = 앞번호 cx1370/y4029~4258(front center[1389,4184]✓)·뒤번호 cx3185/y4072~4471(back[3217,4342]✓)·뒤이름 cx3207/baseline~4766(center_x3219.8/baseline4765.7✓). SVG 좌우(왼=back)와 무관하게 contain이 front왼쪽/back오른쪽 region에 올바르게 재배치.
- page rect: 38개 전수 가로(비율1.43~1.45 일관). Phase D 세로길쭉+앞판소실 완전 해소.
- 검증 산출물(cowork 참고용): data/jobs/_qa_이슈3/qa_outline/qa_{5XS,M,L,XL,5XL}.png, _qa_이슈3/output(38PDF), _qa_이슈3_grade(13사이즈).
- 빈템플릿이라 색렌더 PNG는 흰색(본체·글자 흰색) → 윤곽 PNG로 육안검증(developer 노트와 동일).

### 이슈3 마무리 재검증 (2026-06-20, tester) — 단조성 가드 + 3XL 안전 비활성(5XL 오출고 차단)
이전 🔴치명(3XL=5XL 동일)이 안전 처리됐는지 확정 목적. 코드 무수정(검증만). parse_svg(읽기전용)+
check_size_monotonicity 직접 호출 + cli.cmd_normalize_svg(path SVG 합성입력)로 return code 실측 +
run_job(템플릿.ai, 3XL포함 합성주문) end-to-end + 출력 PDF/사이즈 카운트 + 윤곽 PNG(M/5XL) 육안 + git diff.

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ PASS | 종합 PASS(디자인무손실·CMYK·투명도없음·클립·스케일·Do24·inkcov 편차0) |
| 2) 단조성 가드(함수+CLI) | ✅ PASS | 정상12개 passed=True·dup0·non_mono0(front높이 1966.7→2644.7 단조증가). 동일2개합성→passed=False·duplicates[(FAKE3XL,5XL)] 검출. **CLI 배치(path SVG): 정상→return 0, 결함(좌표동일)→return 1** 실측 |
| 3) ★3XL 안전(핵심)★ | ✅ PASS | V넥 job(3XL 2명+XL/M/5XL/4XL): produced 4·verify 4/4·fail0. **3XL 2건 모두 skip+사유명시·3XL 출고 0건·5XL 출고 1건(주문분만, 3XL대체 0)**. summary.disabled_sizes{3XL:사유}·skipped 사유기록·크래시0 |
| 4) 12개 정상(조각3·verify·육안) | ✅ PASS | 12전수 조각=3·양수좌표·높이내림차순·밴드175.7일정·앞판 모두존재. verify는 job 4/4로 입증. 윤곽 PNG(M/5XL): 앞(라운드넥)·뒤(V넥)·밴드(좌하단 너치띠) 3조각·좌우대칭·앞판 소실0·밴드 정위치 육안확인 |
| 5) 3XL.svg 삭제+preset disabled | ✅ PASS | 3XL.svg 파일 없음(git rm staged)·SVG 12개·preset 3XL disabled=true+사유키 확인. 활성 12/총 13 |
| 6) U넥 회귀(가드 부작용0) | ✅ PASS | disabled키 없는 preset→size_map 100%보존·disabled_map 빈dict·disabled분기 미진입. U넥 XS.svg 3조각 정상. s.get('disabled',False) 기본False라 기존 100% 동일동작 |
| 7) 불변제약 git diff | ✅ PASS | HEAD대비 compose/verify/grade/pattern/text/flatten/reference/order/preview/pdfutil **전부 diff 0**. 변경=cli(+42)/job(+33)/svg_normalize(+190) 3개+preset+SVG데이터만 |
| 8) grade 명령 회귀 | ⚠️ 부분FAIL | **V넥 grade(전사이즈 합성) 실행 시 FileNotFoundError: 3XL.svg 크래시**(build_layouts가 disabled 무시·전 sizes의 pattern_file 읽음, 3XL.svg는 삭제됨). 단 grade는 검수용 전사이즈 합성 경로(주문 출고 아님)이고 크래시=PDF미생성=오출고 0이라 **5XL 오출고 위험 없음**. 출고경로(job)는 안전 |

📊 종합: 7/8 PASS, 1 부분FAIL(grade 명령 회귀 — 출고 안전엔 무관). **★핵심(항목3) 5XL 오출고 0건 확정·3XL 출고 0건 확정★**

**🟢 3XL 출고차단 안전 확정**: 이전 🔴치명(3XL=5XL 동일)은 코드로 안전 차단됨.
- 출고 경로(job/run_job): disabled 사이즈 정확일치만 매칭→대체 경로 자체 없음(이중안전). 3XL 주문 2건 모두 skip+사유, 5XL 오출고 0, 크래시 0, verify 4/4.
- 재발 방지: 단조성 가드가 좌표동일 자산결함을 CLI return 1로 차단(정상 return 0). 복원 시 normalize-svg 배치가 자동 재검증.
- 정상 12개(5XS~5XL, 3XL제외) 정상 동작: 조각3·단조증가·육안 밴드/대칭/앞판소실0.

**⚠️ 부분FAIL(항목8) 상세 — grade 명령 회귀(차단 아님, 출고무관)**:
- 재현법: `python -m engine grade --preset data/patterns/농구_V넥_양면/preset.json --design "(V넥 템플릿.ai)" --out (임의)` → `FileNotFoundError: 3XL.svg`.
- 원인: grade→build_layouts가 `preset["sizes"]` 전체를 순회하며 `pattern_file` 읽음. disabled 키 미인지 + 3XL.svg 삭제됨. (build_layouts/grade는 불변제약 대상이라 developer 미수정 — 설계 정합).
- 영향: grade는 '전 사이즈 한방 합성(검수/미리보기용)'이지 주문 출고 경로 아님. 크래시=PDF 미생성이라 잘못된 출력물 0(오출고 유발 안 함). 다만 V넥 grade 미리보기 워크플로우는 막힘(이전엔 동작, 회귀).
- 판단: 핵심 목표(5XL 오출고 차단)엔 무관. 후속 개선 권장(아래 수정요청).

### 이슈3 grade회귀 재검증 (2026-06-20, tester) — 3XL을 sizes→disabled_sizes 이동
이전 grade 크래시(FileNotFoundError 3XL.svg) 해소 + 3XL 출고차단 유지 재확정. 코드 무수정(검증만).
실제 grade/job 명령 end-to-end 실행 + 출력 파일/사이즈 직접 카운트 + 단조성 가드 함수 직접 호출 +
3XL 포함 합성 주문서(3XL 2명+XL/2XL/M/4XL/5XL) job 실행 + git diff 불변제약.

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ PASS | 종합 PASS(디자인무손실·CMYK·투명도없음·클립·스케일·Do24·inkcov편차0). 멱등 재실행도 PASS |
| 2) ★grade 크래시 해소(핵심)★ | ✅ PASS | 템플릿.ai grade → **배치 36회=12사이즈×3조각·종합 PASS·FileNotFoundError 0·EXIT 0**. 미리보기 12장(3XL 미포함 확인). sizes 12개만 순회→3XL.svg 안 읽음 |
| 3) ★3XL 출고차단(5XL 오출고0)★ | ✅ PASS | V넥 job(3XL 2명+XL/2XL/M/4XL/5XL): produced 5·verify 5/5·fail0. **3XL 2건 모두 skip+결함 사유 경고·출력 3XL 0건·5XL 정확히 1건(주문분만, 3XL 대체 0)**. job.json summary.disabled_sizes{3XL}·skipped 2건 모두 3XL 사유 |
| 4) preset 구조 | ✅ PASS | sizes 12개(3XL 없음)·disabled_sizes에 3XL+사유. pieces front/back/band(svg_index 0/1/2) |
| 5) U넥 회귀 | ✅ PASS | U넥 preset disabled_sizes 키 없음→`get([])`=[]→기존 동작 100%. U넥 grade 배치3 PASS·크래시0 |
| 6) 단조성 가드 | ✅ PASS | 정상12개 passed=True·dup0·non_mono0(높이 1966.7→2644.7 단조증가). 결함재현(FAKE3XL=5XL)→passed=False·duplicates[(FAKE3XL,5XL)]·4XL 단조감소 검출 |
| 7) 불변제약 git diff | ✅ PASS | grade(build_layouts/_piece_transform)·compose(Piece)·verify·pattern(parse_svg)·flatten·text·reference·order·preview·pdfutil **전부 diff 0**. engine 변경=cli/job/svg_normalize 3개뿐. 이번 grade회귀 수정 실질 변경=preset.json+job.py |

📊 종합: **7/7 PASS, 실패 0**. **★grade 회귀 해소·3XL 안전 유지·이슈3 완료★**

**핵심 확정:**
- grade 크래시 완전 해소: 이전 `FileNotFoundError: 3XL.svg`가 사라짐. 메커니즘 확인 — build_layouts(grade.py:213 `for size in preset["sizes"]`)는 sizes만 순회하는데 3XL이 sizes에서 빠지고 disabled_sizes로 이동→3XL.svg를 안 읽음. grade.py 무수정(불변제약 준수).
- 5XL 오출고 0 확정: job size_map에 3XL 자체가 없어 대체 경로 원천 부재(이중안전). 3XL 주문 2건 모두 정확일치 실패→disabled 분기에서 결함 사유로 skip. 출력 5XL은 주문분 1건뿐.
- 산출물: data/jobs/_qa_재검증_grade(grade 12사이즈), data/jobs/_qa_재검증_job(output 5 PDF+job.json), data/jobs/_qa_재검증_uneck(U넥 grade).

### 이슈1 독립검증 (2026-06-20, tester) — 번호 글리프셋(디자이너 athletic 블록체)
코드 무수정(검증만). number_glyphs.json byte동일 비교 + CLI 추출 실측 + ops 좌표 bbox중심 직접계산
(±2pt) + 글리프폭 vs 폰트폭 대조(출처 확정) + V넥 job per_player(출력 PDF 콘텐츠 직접 파싱) +
검정 임시색 미리보기 PNG 2장 육안 + git diff 불변제약 + 엣지(없는문자/빈값/구멍글자).

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| 1) selftest 회귀 | ✅ PASS | 종합 PASS, 멱등 재실행도 PASS(작업 중 손상0) |
| 2) 글리프셋 추출(CLI) | ✅ PASS | 0~9 10개·x순 order"1234567890"·"1"폭156.3/나머지297~334·cap≈538.6·EXIT0. 구멍글자 다중subpath(0/6/9=3,4=2,8=5), 1/7=단일. 커밋본 number_glyphs.json==재추출본 byte동일 |
| 3) 글리프셋 렌더(1/11/20/7/100) | ✅ PASS | 잉크중심 x·y오차 전부 **+0.0000pt**(±2pt충족, 이슈2)·높이=539=cap. 폰트와 폭 명확히 다름(11:312.9 vs 550.8 등=글리프셋 출처). ops=q시작/Q끝/단일f/k fill만·rg/RG/sc/scn/g/G/Do/ca/CA/gs 0 |
| 4) 폴백(None/없는경로/빈값) | ✅ PASS | glyph_source=None(또는 미지정)→폰트폴백, **명시 None==기본값 byte동일**. 빈값→경고0+None, 없는경로/공백→경고1+None. 전부 크래시0. 없는경로→폰트폴백 결과==None과 동일 |
| 5) V넥 job per_player(1~2명) | ✅ PASS | produced2·verify 2/2·fail0. 앞/뒤 번호 잉크중심 오차 **+0.00pt**(앞center1389,4184/뒤3217,4342)·글리프폭≠폰트폭(출처확정). 출력PDF k fill `0 0 0 0`만·Do3(3조각)·rg/RG/sc/scn/g/G/ca/CA/gs 0. **★육안(검정임시색 PNG): "11"/"20" 디자이너 athletic 블록체(밑단 플레어·각진상단, "0"구멍 정확)·이름은 폰트체로 별개·앞/뒤 위치 정상★** |
| 6) U넥/기존 회귀 | ✅ PASS | U넥 preset glyph_source 없음→_load_glyph_source=None→폰트폴백. None==기본값 byte동일(len155). 번호 폰트 그대로(회귀0) |
| 7) 불변제약 git diff | ✅ PASS | compose(Piece)/pattern(parse_svg)/verify(verify_output)/grade(build_layouts/grade)/flatten/reference/svg_normalize/preview/pdfutil/order **전부 diff 0**. 변경=text(시그니처 glyph_source=None 기본값+분기블록만)·job(헬퍼+전달)·cli(서브커맨드). 신규=number_glyphs.py·json |
| 8) 엣지 | ✅ PASS | 없는문자(영문A/x/특수#/전각２)→통째 미출력+경고1. 빈''/None/공백→빈ops 경고0. 구멍글자 0/8/6/9/4 모두 잉크중심0·높이539·단일f(non-zero winding 구멍처리). 크래시0 |

📊 종합: **8/8 PASS, 실패 0**. **★이슈1 번호 글리프셋 완료 — 디자이너 블록체 모양·폭 일치·폴백 안전·불변제약 무수정★**

**핵심 확정:**
- 글리프셋 출처 확정: 렌더 폭이 폰트와 명확히 다름(예 "11" 글리프 312.9 vs 폰트 550.8, "20" 글리프 606.6 vs 폰트 647.0). 육안으로도 athletic 블록체(플레어 세리프) 확인 — 이름 폰트체와 구분됨.
- 잉크중심(이슈2 연계): 1/11/20/7/100 및 앞/뒤 area 전부 x·y오차 0.0000pt(±2pt 완료기준4 충족).
- 폴백 안전: glyph_source 부재/로드실패 시 무조건 폰트폴백(크래시0, U넥 회귀0).
- 산출물: data/jobs/_qa_tester_이슈1(추출 json), _qa_tester_이슈1_job(preset흰색 PDF+preview), _qa_tester_이슈1_육안/preview/{XL_11_김윤서.png, 2XL_20_이주영.png}(검정 육안).

## 리뷰 결과 (reviewer)
(완료 — 전 Phase 통과, 치명0. 주의는 백로그 반영)

### 이슈1 리뷰 (2026-06-20, reviewer) — 번호 글리프셋(디자이너 athletic 블록체)

📊 종합 판정: **통과 (치명 0 · 주의 0 · 후순위 2)**

✅ 잘된 점:
- **불변 제약 §6 완벽 준수**: git diff 직접 확인 — compose/pattern/verify/grade 전부 무수정(diff stat 0). parse_svg·class Piece·build_layouts 정의 파일도 무수정. place_number는 시그니처에 `glyph_source=None` 기본값 인자만 추가(시그니처 호환·폴백 보장) + glyph_source!=None 일 때만 지연 import 위임, None이면 기존 폰트 경로 100% 그대로. job/cli는 순수 추가(헬퍼·서브커맨드)뿐. 글자 device CMYK k fill만(`0 0 0 1 k` 단일 라인), q…Q 래핑, ASCII ops.
- **잉크중심 정렬(이슈2 일관 적용) 직접 검증**: 글리프셋 렌더 "1/11/20/7/22/100" 전부 cx·cy 오차 **+0.0000pt**, 잉크높이 정확히 539(cap_h)=scale 정상. render_glyph_number_ops가 text.place_number와 동일 규약(임시배치→잉크 bbox 중심 평행이동)으로 구현 — "1"처럼 좁은 글리프도 정확 중앙. cap_h 스케일 s=cap_h_pt/rep_cap(최대 잉크높이 글리프 기준 한 줄 동일 배율) 타당.
- **폴백 안전성 견고(크래시 0 확인)**: (a)glyph_source 빈값/None→None 반환→폰트 폴백, byte 동일 검증(`place_number(...)` == `place_number(..., glyph_source=None)` True). (b)오타 경로→"찾지 못해 폰트로 폴백" 경고+None. (c)실재하는 깨진 JSON→try/except "로드 실패(폰트로 폴백): {파싱에러}" 경고+None, 크래시 0. (d)글리프셋에 없는 문자('A' 등)→통째 미출력+경고(번호 깨짐 방지). 빈/None/공백→빈 ops. 모든 실패가 출고 안전(폰트 폴백)으로 수렴.
- **추출 견고성**: CTM 추적(q/Q/cm)이 flatten._mat_mul·job._extract_red_strokes와 동일 식 복제(좌표 일관). m/l/c/v/y/re/h 전 연산자 보존(re는 m/l/h로 전개), fill 연산자(f/F/f*/b/B 계열)로 끝나는 경로만 캡처, stroke/clip/n은 버림(글리프만 선별). x오름차순 정렬→order 1:1 매핑. **개수≠order 길이면 ValueError+추출 bbox 표시**로 artbox 오설정 조기 차단(안전망).
- **구멍 fill rule 보존**: 구멍 있는 글리프 0/6/9=subpath3, 4=2, 8=5(detail 포함)로 다중 subpath 보존, 단일 `f`(non-zero winding)로 채워 구멍 자동 처리(even-odd 안 씀). 명세 §1 요구 충족.
- **베이스라인 원점 정규화 정확**: 추출 직후 각 글리프 잉크 좌하단을 (0,0)으로 평행이동 → _glyph_ink_bounds 측정 결과 1/8/0 모두 ink_min=(0.000,0.000)·ink_max=(width,538.583). 렌더 시 자유 배치 가능(이슈2 잉크중심과 독립).
- **출처 확정(글리프셋≠폰트)**: '22' 글리프셋 출력 폭 602.5 vs 폰트 664.0으로 분명히 다름 → 디자이너 도형 사용 입증. order/cap_height 정합(10글리프, cap≈538.6).
- 코드 품질: 하드코딩 0(artbox/order는 CLI 기본값 인자, 색·좌표는 preset). 네이밍·주석 컨벤션(한글 비유 주석) 일관. JSON 스키마 합리적(units/source/artbox/order/cap_height/glyphs{width,cap_height,subpaths}). 재현 CLI(number-glyphs --src/--out/--artbox/--order) 제공. _GLYPH_CACHE(경로 단위 읽기전용 캐시)로 선수마다 재로드 방지. selftest 회귀 PASS.

🟢 후순위(차단 아님, 운영 메모):
- **곡선(c/v/y) 미존재는 현 소스 특성**: 추출된 글리프셋 연산자 분포 = m21·l161·h16 (c/v/y **0개**). 디자이너 .ai가 outline을 직선 세그먼트로 평탄화 내보냈기 때문(명세 "곡선 미존재 가정"과 데이터 일치). **코드는 c/v/y 추출·렌더 모두 지원**하므로 곡선 포함 소스로 바뀌어도 자동 대응 — 결함 아님. 다만 직선 161개로 폭이 충분히 표현돼 육안 품질 영향 없음.
- **글리프셋 1회 추출 운영 의존성**: number_glyphs.json은 특정 소스 .ai(템플릿 XL)에서 1회 추출한 산출물. JSON source 필드에 출처 기록됨. **디자이너 폰트/번호 도형이 바뀌면 `python -m engine number-glyphs`로 재추출 필요**(코드 무수정, 데이터만 갱신). 다른 폰트/숫자세트도 order 인자로 일반화 가능. cowork 오버레이로 글리프셋 번호 모양 최종 육안검증 권장(이슈2 백로그 "가로중심 미세조정"과 함께).

### 이슈3 리뷰 (2026-06-19, reviewer) — 암홀X 전면교체 + 밴드 복원

📊 종합 판정: **수정 필요(치명 1건)** — 코드/필터/preset 로직은 정상이나 데이터 1개 오염

✅ 잘된 점:
- 불변 제약 완벽 준수: engine 변경 파일은 cli.py·svg_normalize.py 단 2개. compose/pattern/grade/job/text/flatten/verify/pdfutil/reference/order 전부 git diff 무수정 확인(§6 통과).
- 필터 변경(OR→AND + min_area_ratio) 견고: (a)밴드 보존 (b)0면적 보조선 제거 의도 정확. 임계 0.002 합리적 — 실측 밴드면적 24만~35만 ≫ 임계 3.8만(4337²×0.002). page_dim²대비 인자라 하드코딩 아님. min_area_ratio·min_dim_ratio 둘 다 기본값 확장만(시그니처 호환).
- 13개 전수 parse_svg 직접 검증: 조각수=3·viewBox 통일(`0 0 4337.01 3401.57` 1종)·OOB 없음(음수/초과 좌표 0)·높이 내림차순 안정(front>back>band, band176로 충분히 분리돼 정렬 뒤집힘 위험 없음). → errors.md 2026-06-19 "viewBox 섞임/앞판소실" 함정 회피 확인.
- 좌우정합(관점4): front 조각=SVG우측(cx3138)/back=좌측(cx1297)이나, grade `_piece_transform`이 각 조각을 자기 design_region에 독립 contain 배치 → SVG상 좌우위치 무관. developer 주장 타당. 디자인 앞=좌(region[468..2098])/뒤=우([2310..3997]) 매핑도 정합.
- band design_region[468,5287,3997,5562]=content_box 최상단 띠(가로전체)로 목밴드 위치 타당. selftest PASS(회귀0).

🔴 필수 수정(치명):
- **[3XL.svg] 사이즈 데이터 오염 — 3XL이 5XL과 100% 동일 조각**. parse_svg 결과 3XL의 앞/뒤/밴드 조각 좌표가 5XL과 완전 일치(좌표 md5 hash 동일: front 06452679, back fb10e3e5, band ab4dbe5c). 높이 단조성 깨짐: 사이즈당 +56.5pt 규칙인데 2XL=2475→3XL=2645(+169.6, =5XL값)→4XL=2588(-56.5, 진짜4XL)→5XL=2645. 즉 정상이라면 3XL=2531.6이어야 함.
  - **근본원인**: developer 코드/변환 결함 아님. **원본 자산 결함** — 데스크톱 `V넥 스탠다드-A(암홀X)/농구유니폼_V넥_스탠다드_암홀X_3XL.ai` 자체가 5XL 도형을 담고 있음(PyMuPDF로 원본 .ai 직접 추출 시 3XL.ai≡5XL.ai 조각 hash 동일, 4XL.ai만 다름). 변환기는 결함 원본을 충실히 반영했을 뿐.
  - **회귀 확인**: 이전 커밋(Phase D, 다른 출처본)에서는 3XL≠5XL로 정상 단조(+28pt: 2382→2410→2438→2466)였음. 이번 "동일 .ai 직변환 통일"로 원본 결함이 유입됨.
  - **영향**: 3XL 주문 선수에게 5XL 크기 출력 → 출고 불량. "조각수3·viewBox·OOB·정렬·verify·selftest" 6개 신호 전부 초록불이나 치수만 틀림(errors.md 2026-06-19 함정의 변종).
  - **조치**: developer 단독 코드수정 불가(자산 문제). cowork에 올바른 3XL.ai 재확보 요청 후 3XL.svg만 재변환 필요. 그 전까지 3XL 사이즈 출고 보류 권장. (developer "5XL/4XL/3XL 중복6→dedup3"은 파일 '내부' 2벌중복 제거를 말한 것 — 파일 '간' 3XL=5XL 동일은 별개 미인지 사안.)

🟡 권장 수정(주의):
- **변환 검증에 사이즈 단조성 가드 추가**: errors.md 2026-06-19 예방규칙에 "조각 height가 사이즈 오름차순으로 단조 증가(인접 사이즈와 동일 좌표면 경고/실패)"를 1줄 추가 권장. 이번 3XL=5XL는 viewBox/OOB/정렬 검증을 전부 통과해 잡히지 않았음 — 단조성 점검이 유일한 탐지법.

🟢 후순위(차단 아님, 백로그 일치):
- band design_region 빈템플릿 기준 산출 → cowork 정합 확인 후 완성본으로 정밀 재추출 여지(기존 백로그 design_region_pt 항목과 동일 성격).
- band 종횡비(폭1992×h176, AR~10) vs region(가로3529×275, AR~12.8): contain으로 region내 좌측정렬+여백 발생(front/back도 동일 특성이라 일관). cowork 오버레이로 밴드 위치 육안확인 권장.
- cli 표시변경(2 또는 3 ✅)은 동작 무관·정상. flatten_curves 곡선폴백은 현 데이터 곡선0이라 미사용(향후 곡선패턴 도입 시 재검토).

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| (없음) | | Phase D 좌표오염은 되돌림1로 해소 | 완료 |
| reviewer | data/patterns/농구_V넥_양면/3XL.svg (+원본 3XL.ai) | 🔴치명: 3XL이 5XL과 100% 동일 조각(좌표 hash 일치, 높이 단조성 깨짐 2645=5XL). 원인=원본 V넥 암홀X 3XL.ai 자체가 5XL 도형(원본 .ai hash 동일). developer 코드결함 아님→자산결함. cowork에 올바른 3XL.ai 재확보 후 3XL.svg만 재변환 필요. 그 전 3XL 출고 보류. | **3XL.ai 재확보 대기(비활성 처리)** — 결함 3XL.svg 삭제·preset 3XL disabled 표식·job이 3XL주문 안전skip(5XL대체0)·단조성 가드 신설로 재발 자동차단 완료(2026-06-20 developer). 올바른 .ai 받으면 normalize-svg 재변환+preset disabled 2키 삭제로 복원 |
| reviewer | (권장) 변환 검증 단조성 가드 | 🟡 권장: "조각 height 사이즈 오름차순 단조증가, 인접 동일좌표면 경고/실패" 가드 추가 | **완료**(svg_normalize.check_size_monotonicity + cli 배치 호출, 2026-06-20 developer). 재검증 PASS(정상 return0/결함 return1) |
| tester | engine/grade.py(build_layouts) + data/patterns/농구_V넥_양면/3XL.svg | 🟡 grade 명령 회귀: V넥 grade(전사이즈 합성) 실행 시 `FileNotFoundError: 3XL.svg`. build_layouts가 preset의 disabled 키를 무시하고 전 sizes의 pattern_file을 읽는데 3XL.svg는 삭제됨. | **수정완료**(2026-06-20 developer). 옵션 외 더 깔끔한 방식 채택: 결함 3XL을 **sizes에서 제거하고 preset 최상위 `disabled_sizes` 섹션으로 이동**. build_layouts/grade 무수정(불변제약 준수)으로 sizes에 3XL이 없어 3XL.svg를 안 읽음→크래시 해소. job은 disabled_sizes 섹션에서 결함 사유 읽어 skip. 검증: grade 배치36(12×3) PASS·크래시0, job 3XL skip·5XL오출고0, U넥 회귀0, 단조성 가드 정상12통과/결함검출 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-19 | dev/test/rev | Phase B 정밀배치+reference CLI | 통과(15/15) |
| 2026-06-19 | dev/test/rev | Phase C job 통합(flatten+앞뒤번호·이름 주입) | 통과(8/8) |
| 2026-06-19 | dev | Phase D-1 ai_to_svg.jsx(일러스트 배치변환) | 작성·커밋 |
| 2026-06-19 | dev/test/rev | Phase D V넥 패턴(svg_normalize)+preset 13사이즈 | 통과(7/7) |
| 2026-06-19 | dev/test | Phase D 되돌림1: 원본.ai 동일출처 재변환(좌표오염 해소) | FAIL 해소 |
| 2026-06-19 | dev/test/rev | Phase E STIZ신양식 파서+전선수 PDF 38건 | 통과(verify38/38) |
| 2026-06-19 | pm | Phase B/C/D/E 커밋 5개 origin 푸시 | 완료(미푸시0) |
| 2026-06-19 | dev | 이슈2 place_number/place_name 잉크 bbox 기준 중앙정렬 | "1/11/20/22" 오차±0.000pt, selftest PASS |
| 2026-06-19 | tester | 이슈2 독립검증(BoundsPen 곡선극값 2중측정+V넥 job 스모크) | 6/6 PASS, 1/11/20/22/7/100 오차 0.0000pt, verify 38/38 |
| 2026-06-19 | dev | 이슈4 재단선(빨간 stroke)+너치 보존(job.py+V넥 cutline preset) | selftest PASS·U넥회귀0·합성검증 found3→mapped3→출력3 device CMYK 무손실. 소스: 템플릿 재단선레이어 PDF상 비어있음(추출0 정상) |
| 2026-06-19 | tester | 이슈4 독립검증(합성 stroke end-to-end+너치 클립경계 좌표증명+미리보기 육안) | 7/7 PASS. 너치 시트x 4099.2>클립4023.3(+75.9pt 보존), CMYK무손실, U넥/grade 회귀0, 불변파일 무수정 |
| 2026-06-19 | dev | 이슈3 암홀X 전면교체(svg_normalize 밴드보존필터+13개재변환+preset band조각) | selftest PASS·V넥 13개 전수3조각·viewBox통일·양수·육안(앞/뒤/밴드·대칭·앞판소실0)·job verify38/38·k fill·밴드재단선연계 PASS·U넥회귀0·불변제약 무수정 |
| 2026-06-19 | reviewer | 이슈3 코드리뷰 | 수정필요(치명1): 3XL.svg=5XL 동일(원본 3XL.ai 자산결함). 필터/preset/불변제약/좌우정합/viewBox 전부 정상. 권장: 단조성 가드 추가 |
| 2026-06-19 | tester | 이슈3 독립검증(13전수+필터부작용 형식증명+윤곽5사이즈 육안+job38 콘텐츠파싱+밴드재단선매핑) | 7/8 PASS, 부분FAIL1: 3XL.svg front좌표 hash=5XL 동일(단조 깨짐 2645=5XL값) 재현확정→출고차단(reviewer 치명1과 일치). 밴드복원·필터·불변·육안·verify38/38·U넥회귀 전부 PASS |
| 2026-06-20 | tester | 이슈3 마무리 재검증(단조성 가드+3XL 안전비활성) | 7/8 PASS. ★3XL 출고0·5XL 오출고0 확정★(job 3XL 2건 skip+사유, verify4/4). 가드 정상return0/결함return1·선택12개 조각3/단조/육안·불변diff0·U넥회귀0. 부분FAIL1: V넥 grade(전사이즈) 3XL.svg 누락 크래시(출고무관·미리보기 회귀, 수정요청 등록) |
| 2026-06-20 | dev | 이슈3 grade회귀 수정(3XL을 sizes→disabled_sizes 섹션 이동, job이 disabled_sizes서 읽기) | ✅ 전항목 통과: grade 배치36(12×3) 크래시0·FileNotFound0, job 3XL 2건skip·5XL오출고0·verify5/5, U넥회귀0, 단조성가드 정상12통과/결함검출, grade.py등 불변제약 무수정 |
| 2026-06-20 | tester | 이슈3 grade회귀 재검증(코드 무수정, end-to-end 실행 검증) | ✅ **7/7 PASS**. grade 배치36 크래시0·FileNotFound0(핵심), job 3XL 2건skip·출력 3XL 0·5XL 1건(오출고0), selftest PASS, U넥회귀0, 단조성가드 정상12 passed=True/결함 FAKE3XL=5XL 검출, 불변제약 grade/compose/verify/pattern diff0 |
| 2026-06-20 | dev | 이슈1 번호 글리프셋(디자이너 athletic 블록체) 추출·렌더 — number_glyphs.py 신규+text glyph_source 분기+job 로더+cli number-glyphs+preset | ✅ 전항목: selftest PASS·CLI 10글리프 추출(폭/cap/구멍)·"1/11/20/7" 잉크중심0.0pt·폴백·V넥 job verify2/2·글자 k fill만·금지연산자0·육안 블록체 확인·U넥회귀0·불변제약 무수정 |
| 2026-06-20 | tester | 이슈1 독립검증(코드무수정, 추출 byte동일+ops 좌표 bbox중심+글리프vs폰트폭+job 콘텐츠파싱+육안PNG2장+엣지) | ✅ **8/8 PASS**. 추출10개 order/폭/cap/구멍정합·렌더 잉크중심0.0pt(±2pt)·글리프폭≠폰트폭(출처확정)·폴백None==기본값byte동일·job verify2/2 금지연산자0·육안 athletic블록체("0"구멍)·U넥회귀0·불변제약 compose/pattern/grade/verify diff0·엣지(없는문자/빈값/구멍0689 4) 크래시0 |
| 2026-06-20 | reviewer | 이슈1 코드리뷰(불변diff+잉크중심+폴백3종+구멍fill+정규화+출처) | ✅ **통과(치명0·주의0)**. 불변제약 compose/pattern/verify/grade·parse_svg·Piece·build_layouts diff0·place_number 기본값인자만. 잉크중심 6종 0.0000pt·k fill만·금지연산자0. 폴백: None=폰트byte동일/오타/깨진json 전부 None+경고 크래시0. 구멍 다중subpath+non-zero f. 후순위2: 곡선 미존재(소스특성·코드는지원)·1회추출 운영의존 |
