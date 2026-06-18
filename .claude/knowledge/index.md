# 프로젝트 지식 목차

## 파일별 요약
| 파일 | 항목 수 | 최종 업데이트 |
|------|--------|------------|
| architecture.md | 4 | 2026-06-16 |
| errors.md | 4 | 2026-06-16 |
| conventions.md | 3 | 2026-06-15 |
| decisions.md | 8 | 2026-06-16 |
| lessons.md | 1 | 2026-06-15 |

## 최근 추가된 지식 (최근 5건)
- [2026-06-16] errors: 다중 시트 주문서 — 행 최다 시트 채택 시 과거 접수분 오선택(15% 오답). "표식(주문번호/수량) 시트 우선 → 첫 시트 → 행최다 폴백"으로 선택. 정적리뷰 미검출, 다중시트 실표본으로만 발견
- [2026-06-16] architecture: A-5 주문서 파싱 경로(order.py 독립 파서, 양식①선수별행/②집계 자동판별 → [{name,number,size,qty}])
- [2026-06-16] decisions: A-5 1차범위(양식① 81개 메인+② best-effort) / 상의기준 / qty=1 / 아동호수 포함 / 시트선택 표식우선
- [2026-06-15] errors: pikepdf 출력 비결정적(XObject 이름 랜덤) → 바이트동일 회귀는 이름통일 후 콘텐츠 비교 + fontTools 글리프 좌표는 폰트단위(u=scale/upm 곱)
- [2026-06-15] decisions: A-4 글자 결합=Piece.extra_ops(기본값"") + 글리프 큐빅경로(Pretendard CFF, upm 2048)
- [2026-06-15] architecture: A-4 배번·이름 벡터 렌더 경로(text.py→Piece.extra_ops→compose, 디자인 Form 불변)
- [2026-06-15] decisions: A-2 패턴로딩 계층 분리(pattern_loader.py) + 사이즈 탐색 폴백·누락 부분성공
- [2026-06-15] decisions: A-1 좌표정합 방식 A(앵커 정합) 확정 — 시험렌더 비교로 검증
- [2026-06-15] architecture: 좌표계 3종(디자인/패턴/대지) + preset→engine 매핑 경로
