# 작업 스크래치패드

## 현재 작업
- **요청**: "완성본 기준 → 빈 템플릿 선수별 주입" 정식 통합 (의뢰서-CLI-완성본기준주입.md)
- **상태**: ✅ **Phase B~E 전부 완료·커밋·푸시** (미푸시 0). 완료기준 §7 달성.
- **현재 담당**: pm (cowork 시각검증 대기 — 사용자가 오버레이로 번호·이름 정합 최종확인 예정)

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

## 리뷰 결과 (reviewer)
(완료 — 전 Phase 통과, 치명0. 주의는 백로그 반영)

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| (없음) | | Phase D 좌표오염은 되돌림1로 해소 | 완료 |

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
