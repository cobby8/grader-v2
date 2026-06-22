# 프로젝트 지식 목차

## 파일별 요약
| 파일 | 항목 수 | 최종 업데이트 |
|------|--------|------------|
| architecture.md | 7 | 2026-06-22 |
| errors.md | 7 | 2026-06-22 |
| conventions.md | 3 | 2026-06-15 |
| decisions.md | 10 | 2026-06-20 |
| lessons.md | 1 | 2026-06-15 |

## 최근 추가된 지식 (최근 5건)
- [2026-06-22] decisions/errors: 합성 품질 근본수정 — 조각 자동매핑(디자인 OCG "패턴선" bbox=design_region, SVG 넥깊이로 앞/뒤 식별) / cover+블리드(흰틈 제거, preset 키 있을때만) / 재단선=SVG 폴리곤 1줄 / 디자인 패턴선 두줄방지는 OCG OFF 무효→콘텐츠 BDC…EMC 삭제(빨강1색만, 무손실)
- [2026-06-22] errors: 브라우저 파일 드롭은 document 레벨 가드+좌표(getBoundingClientRect) 판정 필수. <button>+자식 요소에만 리스너 달면 자식/패딩 드롭이 새 탭으로 샘. playwright 합성 dispatchEvent는 타겟 직접이라 PASS여도 실 OS 드롭 보장 못 함
- [2026-06-20] architecture: 웹 도구 — webapp/ FastAPI(정적 _handoff 복사본 서빙 + /api: patterns·order/parse·design/check 5케이스·jobs 비동기·preview·zip·patterns등록·settings). 엔진 호출만, 빌드0, 폴더+JSON. 출력형식 PDF/EPS/both(flatten Form그룹제거→eps2write, 페이지 /CS 보존, GS 없으면 PDF fallback). 디자인 본체는 "PDF 호환 저장" 필수(아니면 3.4KB 흰화면)
- [2026-06-20] errors: 자산 결함(원본 .ai 사이즈 중복: 3XL≡5XL) — 6신호 초록불인데 치수만 틀림. 인접 사이즈 좌표 동일 검사(단조성 가드)만 탐지. + disabled는 sizes 밖 disabled_sizes로(grade/job 양쪽 안전)
- [2026-06-20] decisions: 정합보정 4이슈 — 번호 잉크bbox 중앙정렬 / 재단선 extra_ops 클립밖 / 암홀X 3조각+보조선필터 AND / 번호 글리프셋(폰트 폴백)
- [2026-06-20] decisions: 정합보정 4이슈 — 번호 잉크bbox 중앙정렬(advance 아님) / 재단선=디자인 빨강stroke를 extra_ops 클립밖 드로잉 / 암홀X 3조각(앞·뒤·밴드) + 보조선필터 OR→AND+최소면적 / 번호=디자이너 outline 0~9 글리프셋(없으면 폰트 폴백)
- [2026-06-19] errors: V넥 변환 함정 — viewBox 세로/음수좌표면 비-XL 앞판 소실, 비-XL 미리보기 육안 필수. + STIZ 헤더 nbsp
- [2026-06-19] decisions: 완성본기준 주입 통합 — path SVG svg_normalize 전처리 / 글자=디자인좌표 ops를 조각 transform 감싸 주입 / STIZ 신양식 파서
- [2026-06-16] errors: 다중 시트 주문서 — 행 최다 시트 채택 시 과거 접수분 오선택. "표식(주문번호/수량) 시트 우선 → 첫 시트 → 행최다 폴백"
- [2026-06-16] decisions: A-5 1차범위(양식① 81개 메인+② best-effort) / 상의기준 / qty=1 / 아동호수 포함 / 시트선택 표식우선
- [2026-06-15] errors: pikepdf 출력 비결정적(XObject 이름 랜덤) → 바이트동일 회귀는 이름통일 후 콘텐츠 비교 + fontTools 글리프 좌표는 폰트단위(u=scale/upm 곱)
- [2026-06-15] decisions: A-4 글자 결합=Piece.extra_ops(기본값"") + 글리프 큐빅경로(Pretendard CFF, upm 2048)
- [2026-06-15] architecture: A-4 배번·이름 벡터 렌더 경로(text.py→Piece.extra_ops→compose, 디자인 Form 불변)
- [2026-06-15] decisions: A-2 패턴로딩 계층 분리(pattern_loader.py) + 사이즈 탐색 폴백·누락 부분성공
- [2026-06-15] decisions: A-1 좌표정합 방식 A(앵커 정합) 확정 — 시험렌더 비교로 검증
- [2026-06-15] architecture: 좌표계 3종(디자인/패턴/대지) + preset→engine 매핑 경로
