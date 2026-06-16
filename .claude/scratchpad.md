# 작업 스크래치패드

## 현재 작업
- **요청**: 코워크 새 의뢰서(A-1 이후 잔여) — 우선순위 재정의. 추천 순서대로 진행 중.
- **상태**: A-5 ✅완료·커밋(927b7b6) → **job(선수별 통합 출력) 착수 예정**
- **현재 담당**: pm (job 설계 위임 준비, split 결정 대기)

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
(job 대기. A-2/A-4/A-5 설계는 "설계 보존" + git 참조)

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
