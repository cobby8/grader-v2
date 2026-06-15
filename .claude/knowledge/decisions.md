# 기술 결정 이력
<!-- 담당: planner-architect | 최대 30항목 -->
<!-- "왜 A 대신 B를 선택했는지" 기술 결정의 배경과 이유를 기록 -->

### [2026-06-10] 공장 출력 포맷: EPS → PDF 전환
- **분류**: decision
- **발견자**: pm / planner-architect
- **내용**: 설계서(DESIGN.md)는 Ghostscript eps2write로 EPS 출력 예정이었으나, 공장이 PDF 수용 가능 확인 → PDF로 확정. eps.py 단계 폐기. 이유: EPS는 투명도 미지원 구포맷이라 투명도 1%만 있어도 페이지 전체 래스터화 + ICC 색 변형 위험(공식문서 확인). PDF는 device CMYK·벡터·투명도 그대로 보존 가능.
- **절대 조건**: ① CMYK 완전 보존(device CMYK 그대로 통과, RGB/ICC 변환 금지) ② 파일 경량(Form XObject로 디자인 1회 임베드 후 N×M 참조).
- **참조횟수**: 0

### [2026-06-15] A-1 좌표정합 방식: ✅ "앵커 기반 정합"(방식 A) 확정 (시험렌더 검증)
- **분류**: decision
- **발견자**: planner-architect 제안 → developer 시험렌더 → 사용자 확정
- **내용**: 디자인↔패턴 좌표 관계 3안 중 **방식 A(앵커 기반 정합) 최종 확정**. 사용자가 "실파일로 먼저 검증" 후 결정하기로 하여, 실데이터(design_XL.ai + pattern_XS.svg)로 방식A(조각별 design_region을 조각 윤곽 bbox에 앵커정렬+등방스케일) vs 방식B(디자인 전체를 패턴시트에 1회 정렬 후 조각 윤곽 클리핑)를 grading_compare/compare_mapping.py로 실제 합성·미리보기 비교. **결과: 방식A=앞/뒤/소매가 옷 형태 그대로 완벽 배치, 방식B=디자인이 조각 경계서 잘리고 어긋남(YONSE/김ㅎ 등 일부만)→사용불가.** 방식A는 일러 면적비+상대벡터 철학과 일치, engine Piece.transform(cm)에 1:1 대응, device CMYK 무손실 유지. 실측 매칭: 디자인 앞판→패턴조각idx1, 뒤판→idx0, 소매→idx2(종횡비 일치). → preset.json은 방식A 기준(조각별 design_region_pt + 앵커정렬)으로 확정.
- **주의(다음 구현 반영)**: 앵커 정합 시 transform 오프셋(e/f)이 음수가 될 수 있어 engine verify.py의 cm 검증 정규식(음수 미허용)이 "스케일 적용"을 FAIL로 오판 → A-3 구현 시 verify 정규식 보강 또는 좌표 오프셋 양수화 검토 필요(engine 수정은 별도 승인). 합성 자체는 정상.
- **참조횟수**: 0

### [2026-06-15] 출력 PDF 단위: ✅ 다페이지 1PDF(사이즈=페이지) 확정 (사용자) — 단 공장 RIP 수용성 추후 확인
- **분류**: decision
- **발견자**: planner-architect
- **내용**: engine.compose는 SizeLayout 리스트를 받아 "한 사이즈=한 페이지"인 다페이지 PDF 1개를 만든다(이미 구현됨, selftest 6사이즈 1PDF 검증). 일러 구버전은 사이즈별 개별 EPS였다. 다페이지 1PDF는 디자인 임베드 1회·관리 단순 장점. 단 공장 RIP/작업자가 "사이즈별 개별 파일"을 요구하면 페이지 분할 출력 옵션 필요 → 사용자 결정사항. preset.json 스키마는 두 경우 모두 수용(레이아웃 생성은 동일, 저장 단위만 분기)하도록 설계.
- **참조횟수**: 0

### [2026-06-10] 합성 엔진: pikepdf 중심, PyMuPDF는 미리보기 전용
- **분류**: decision
- **발견자**: planner-architect
- **내용**: PDF 합성은 pikepdf(Form XObject 재사용 + W n 클리핑 + cm 스케일)로 무손실 벡터·CMYK 보존. PyMuPDF는 PNG 렌더 시 RGB 변환되므로 검수 미리보기에만 쓰고 출력 경로엔 절대 사용 금지.
- **참조횟수**: 0
