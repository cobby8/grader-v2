# 작업 스크래치패드

## 현재 작업
- **요청**: FastAPI 웹 도구 구동(웹앱1~5) + 출력형식 PDF/EPS/both. 의뢰서: FastAPI-구동·출력형식-PDF-EPS·디자인-시안보강.
- **상태**: ✅ **출력형식 + 웹앱1~5 전부 완료·커밋** (미푸시 8개 — 푸시 확인 대기). 직원 E2E 완료기준 달성.
- **현재 담당**: pm

## 진행 현황 (완료)
| 작업 | 내용 | 상태 |
|------|------|------|
| 정합보정 4이슈 | 번호잉크정렬·재단선·암홀X3조각·번호글리프셋 | ✅ 완료·푸시 |
| 빈본체 design_file | 88KB 본체 정식 설정(3.4KB→88KB) | ✅ 커밋 |
| 출력형식 | flatten Group제거(EPS벡터)·eps2write·verify_eps·run_job out_format·--format | ✅ (tester 13/13·rev 통과) |
| 웹앱1 | FastAPI 골격+정적서빙+health/patterns/settings | ✅ |
| 웹앱2 | order/parse + design/check 5케이스 | ✅ |
| 웹앱3 | jobs 비동기+progress/preview/zip | ✅ |
| 웹앱4 | jobs기록+패턴등록+설정저장 | ✅ |
| 웹앱5 | run.bat+직원 E2E(완료기준 달성) | ✅ (rev 종합 통과 치명0) |

## 백로그 (차단 아님, 후속)
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·design_token·_JOBS TTL 정리 루틴(디스크/메모리 누적 방지). progress 진행 콜백.
- **[출력형식]** verify_eps origin_ok 무의미가드, GS 절대경로후보·임계 하드코딩 preset화.
- **[디자이너 입력 대기]** 재단선 PDF 포함 .ai 재출력(이슈4 인프라 완비) / 올바른 3XL.ai 재확보(현 disabled).
- **band design_region** cowork 정밀 재추출. cowork 최종 오버레이 검증(번호글리프셋·밴드·재단선·본체).
- 하의 사이즈 분리 / 주문서 자동판별 ③우선 가드 / shrink 등방 / sizes.scale.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output) + build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로·번들러 없음). 폴더+JSON(DB없음). CLI/curl 단독검증. GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만).

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left·등방 contain). grade `_piece_transform`(job `_job_piece_transform` 복제).
- 글자주입: text place_number/place_name(잉크 bbox 중앙정렬, 디자인좌표 ops) → job이 조각 transform 감싸 extra_ops 주입(클립 밖). 재단선도 동일(클립밖 너치보존).
- 번호: preset glyph_source 있으면 디자이너 글리프셋(number_glyphs.json), 없으면 HY헤드라인 폴백.
- **디자인 본체 핵심**: .ai는 "PDF 호환 저장(Create PDF Compatible File)" 켜야 본체가 PDF 콘텐츠에 들어감. 안 켜면 본체/재단선이 일러스트 전용 데이터에만 → PDF콘텐츠 3.4KB·흰화면. 정상 빈본체=88KB(파란본체+밴드+재단선3, 텍스트0). design_source/README.md에 규칙 명시.
- **출력형식**: flatten은 Form 투명도그룹 제거(EPS 래스터화 트리거)·페이지그룹 /CS 보존(색시프트 방지)·알파잔존시 제거가드. eps2write(GS, output/pdf·eps 분리). compose가 페이지그룹 부활→pdf_to_eps 직전 재제거. EPS 305KB 벡터.
- **V넥 패턴**: 암홀X 3조각 front0/back1/band2. viewBox 4337×3401. 12사이즈(3XL disabled=원본결함). disabled_sizes는 sizes 밖(build_layouts 미순회→grade/job 안전).
- ⚠️ 변환함정(errors.md): 조각수+verify만으론 부족→viewBox통일·양수·비-XL 미리보기 육안. 인접사이즈 좌표동일=자산결함(check_size_monotonicity). STIZ 주문서 헤더 nbsp.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference·job(정밀배치+재단선+disabled+out_format)·svg_normalize(+가드)·order(①②③STIZ)·flatten(+Group제거)·eps(pdf_to_eps·verify_eps)·compose·verify·preview·grade.
- CLI: grade/job/reference/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- **webapp/**: main(FastAPI:/static 마운트+/api+GET/→work)·api(health/patterns/settings GET·PUT, order/parse, design/check 5케이스, jobs 비동기+progress+preview+zip, jobs기록, patterns 등록POST)·state(설정·업로드·job메모리)·run.py·run.bat. webapp/static=_handoff/grader-v2-static 복사본(원본 보존, 디자인 갱신시 재복사).
- 보조: scripts/ai_to_path_svg.py, illustrator-scripts/ai_to_svg.jsx.
- 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면(SVG12+preset+number_glyphs.json)}. data/{jobs,uploads}/(.gitignore). data/settings.json(gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai, README): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base) / _숫자글리프셋_아트보드2.ai(글리프셋) / _완성본_본체포함_XL.ai(참고).
- 빈본체/완성본/주문서(구): C:/Users/user/Desktop/새 폴더/. 암홀X 패턴: Desktop/V넥 스탠다드-A(암홀X)/. 본체 살아있는 라인작업본: G:/공유 드라이브/CHINA FACTORY/order list/...라인작업/.
- 폰트: data/fonts/HY헤드라인M.ttf(이름. 번호는 글리프셋). GS: C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- git: origin=cobby8/grader-v2, main. **미푸시 8개**(design_file·출력형식 docs/feat·웹앱1~5).

## 기획설계/구현/테스트/리뷰
(완료 — 상세 git 히스토리 + knowledge. 출력형식 tester13/13·rev통과, 웹앱 각단계 dev E2E·rev종합 통과 치명0)

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성(disabled_sizes)·재확보 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-19~20 | 팀 | 정합보정 4이슈(번호정렬·재단선·암홀X3조각·글리프셋) | 완료·푸시 |
| 2026-06-20 | dev | 빈본체 design_file 88KB 정식설정 | 33건 verify PASS·겹침0 |
| 2026-06-20 | dev/test/rev | 출력형식 PDF/EPS/both | tester13/13·rev통과, EPS305KB벡터 |
| 2026-06-20 | dev | 웹앱1 FastAPI 골격+API3 | curl/브라우저 PASS |
| 2026-06-20 | dev | 웹앱2 order/parse+design 5케이스 | 38행/11명·5케이스 정확 |
| 2026-06-20 | dev | 웹앱3 jobs비동기+progress/preview/zip | E2E①~⑧ PASS |
| 2026-06-20 | dev | 웹앱4 jobs기록+패턴등록+설정 | 글리프셋10자·완성본추출·5사이즈3조각 |
| 2026-06-20 | dev | 웹앱5 run.bat+직원 E2E | 전체플로우 PASS(완료기준 달성) |
| 2026-06-20 | rev | 웹앱 종합 리뷰(1~5) | 통과 치명0(주의3 백로그) |
| 2026-06-20 | pm | 출력형식·웹앱1~5 커밋(8개) | 미푸시8(푸시대기) |
