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

## 테스트 결과 (tester)
(완료 — B 15/15, C 8/8, D 7/7(되돌림1), E 7/7)

## 리뷰 결과 (reviewer)
(완료 — 전 Phase 통과, 치명0. 주의는 백로그 반영)

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| (없음) | | Phase D 좌표오염은 되돌림1로 해소 | 완료 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-19 | pm | Step1 미커밋 정리(text.py TTF fix + reference/폰트/명세) 커밋·푸시 | 완료 |
| 2026-06-19 | dev/test/rev | Phase B 정밀배치+reference CLI | 통과(15/15) |
| 2026-06-19 | dev/test/rev | Phase C job 통합(flatten+앞뒤번호·이름 주입) | 통과(8/8) |
| 2026-06-19 | dev | Phase D-1 ai_to_svg.jsx(일러스트 배치변환) | 작성·커밋 |
| 2026-06-19 | dev/test/rev | Phase D V넥 패턴(svg_normalize)+preset 13사이즈 | 통과(7/7) |
| 2026-06-19 | dev/test | Phase D 되돌림1: 원본.ai 동일출처 재변환(좌표오염 해소) | FAIL 해소 |
| 2026-06-19 | dev/test/rev | Phase E STIZ신양식 파서+전선수 PDF 38건 | 통과(verify38/38) |
| 2026-06-19 | pm | Phase B/C/D/E 커밋 5개 origin 푸시 | 완료(미푸시0) |
