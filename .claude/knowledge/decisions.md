# 기술 결정 이력
<!-- 담당: planner-architect | 최대 30항목 -->
<!-- "왜 A 대신 B를 선택했는지" 기술 결정의 배경과 이유를 기록 -->

### [2026-06-10] 공장 출력 포맷: EPS → PDF 전환
- **분류**: decision
- **발견자**: pm / planner-architect
- **내용**: 설계서(DESIGN.md)는 Ghostscript eps2write로 EPS 출력 예정이었으나, 공장이 PDF 수용 가능 확인 → PDF로 확정. eps.py 단계 폐기. 이유: EPS는 투명도 미지원 구포맷이라 투명도 1%만 있어도 페이지 전체 래스터화 + ICC 색 변형 위험(공식문서 확인). PDF는 device CMYK·벡터·투명도 그대로 보존 가능.
- **절대 조건**: ① CMYK 완전 보존(device CMYK 그대로 통과, RGB/ICC 변환 금지) ② 파일 경량(Form XObject로 디자인 1회 임베드 후 N×M 참조).
- **참조횟수**: 0

### [2026-06-10] 합성 엔진: pikepdf 중심, PyMuPDF는 미리보기 전용
- **분류**: decision
- **발견자**: planner-architect
- **내용**: PDF 합성은 pikepdf(Form XObject 재사용 + W n 클리핑 + cm 스케일)로 무손실 벡터·CMYK 보존. PyMuPDF는 PNG 렌더 시 RGB 변환되므로 검수 미리보기에만 쓰고 출력 경로엔 절대 사용 금지.
- **참조횟수**: 0
