# 프로젝트 지식 목차

## 파일별 요약
| 파일 | 항목 수 | 최종 업데이트 |
|------|--------|------------|
| architecture.md | 6 | 2026-06-19 |
| errors.md | 5 | 2026-06-19 |
| conventions.md | 3 | 2026-06-15 |
| decisions.md | 10 | 2026-06-19 |
| lessons.md | 1 | 2026-06-15 |

## 최근 추가된 지식 (최근 5건)
- [2026-06-19] errors: V넥 패턴 변환 함정 — 조각수=2+verify PASS여도 viewBox 세로(5669)/음수좌표면 비-XL 앞판 소실. verify는 무손실만 보고 위치/캔버스 미검사 → 비-XL job 미리보기 육안 필수. + STIZ 주문서 헤더 nbsp(\xa0)
- [2026-06-19] decisions: 완성본기준 주입 통합 — path SVG는 svg_normalize 전처리(parse_svg 무수정) / V넥 앞=idx0·뒤=idx1·소매없음 2조각 / 글자=디자인좌표 ops를 조각 transform 감싸 주입 / STIZ 신양식 파서(양식③)
- [2026-06-16] errors: 다중 시트 주문서 — 행 최다 시트 채택 시 과거 접수분 오선택. "표식(주문번호/수량) 시트 우선 → 첫 시트 → 행최다 폴백"
- [2026-06-16] decisions: A-5 1차범위(양식① 81개 메인+② best-effort) / 상의기준 / qty=1 / 아동호수 포함 / 시트선택 표식우선
- [2026-06-15] errors: pikepdf 출력 비결정적(XObject 이름 랜덤) → 바이트동일 회귀는 이름통일 후 콘텐츠 비교 + fontTools 글리프 좌표는 폰트단위(u=scale/upm 곱)
- [2026-06-15] decisions: A-4 글자 결합=Piece.extra_ops(기본값"") + 글리프 큐빅경로(Pretendard CFF, upm 2048)
- [2026-06-15] architecture: A-4 배번·이름 벡터 렌더 경로(text.py→Piece.extra_ops→compose, 디자인 Form 불변)
- [2026-06-15] decisions: A-2 패턴로딩 계층 분리(pattern_loader.py) + 사이즈 탐색 폴백·누락 부분성공
- [2026-06-15] decisions: A-1 좌표정합 방식 A(앵커 정합) 확정 — 시험렌더 비교로 검증
- [2026-06-15] architecture: 좌표계 3종(디자인/패턴/대지) + preset→engine 매핑 경로
