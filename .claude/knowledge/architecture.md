# 프로젝트 구조 지식
<!-- 담당: planner-architect, developer | 최대 30항목 -->
<!-- 프로젝트의 폴더 구조, 파일 역할, 핵심 패턴을 기록 -->

### [2026-06-20] 출력형식(PDF/EPS/both) 경로 + EPS 벡터화의 핵심 함정(Form그룹 vs 페이지그룹)
- **분류**: architecture
- **발견자**: developer
- **내용**: PDF→EPS 변환은 **engine/eps.py**(신규)가 담당. `pdf_to_eps(pdf,eps,ghostscript_path,page,strip_groups=True)`(GS eps2write+EPSCrop, graceful fallback) + `verify_eps(eps,sheet_size,...)`(벡터·CMYK·BBox 검사) + `find_ghostscript(settings_path)`(탐색순서: settings → 절대경로후보 → PATH). **★EPS 벡터화의 결정적 함정★**: eps2write가 페이지를 통째 래스터화(20MB+)하는 트리거는 **Form XObject의 `/Group(/Transparency)`** 다. 이것만 제거하면 EPS가 벡터(~270~305KB)로 나오고 PDF 렌더 픽셀도 그대로(delta>10 픽셀 0개). 반대로 **페이지의 `/Group`은 `/CS`(ICCBased CMYK 블렌딩 색공간)를 갖고 있어 통째 지우면 본판 색이 미세 시프트**(렌더 27% 픽셀 변화)되고 EPS 벡터화엔 기여도 안 함. → flatten._strip_transparency_groups는 **Form group은 항상 제거, 페이지 group은 /CS 있으면 보존**(실측 확정). **두 번 strip 필요**: flatten이 디자인 원본의 Form group을 지워도, compose의 `as_form_xobject()`가 디자인을 재임베드할 때 원본 페이지 /Group이 새 Form으로 옮겨붙어 **합성 출력 PDF에 투명도 그룹이 되살아남** → pdf_to_eps(strip_groups=True)가 변환 직전 임시 사본에서 Form group을 다시 제거(compose 무수정 제약 회피). **run_job 흐름**: out_format(pdf|eps|both, run_job인자>preset.output.format>"pdf") → PDF 항상 생성(EPS도 이 PDF에서 변환) → output/pdf·output/eps 분리(eps단독은 중간PDF를 _epstmp에 두고 정리) → job.json summary에 format·ghostscript·format_summary{pdf/eps produced·verify_pass·skipped}, outputs[].eps·checks_eps. CLI `--format`. **verify_eps 판정**: 래스터/벡터 구분은 image 토큰 수가 아니라(eps2write가 `{imagemask}{image}ifelse` 정의 2개를 늘 넣음) **파일크기(2MB임계)+실제 이미지페인트 호출 `Id` 개수(래스터546개·벡터0개)+벡터연산자 존재**. BBox는 EPSCrop이 콘텐츠로 자르므로 MediaBox 정확일치 불가 → "원점0근처+시트이내+시트절반이상" 완화판정.
- **참조횟수**: 0

### [2026-06-15] 3개 좌표계 분리 + preset.json → engine 매핑 경로
- **분류**: architecture
- **발견자**: planner-architect
- **내용**: 시스템엔 서로 다른 좌표계 3개가 존재한다. ①디자인 AI(기준 XL) MediaBox `4478×5669pt`(세로 긴 양면펼침 페이지) ②패턴 SVG(예 XS) viewBox `4337×3401`(가로 긴 조각나열 마커시트, y아래로 증가) ③출력 대지 158×200cm 고정(일러 기준). engine은 ①을 통짜 Form XObject 1개로 임베드하고 ②의 조각 윤곽으로 클리핑(W n)+cm 변환해 무손실 합성. preset.json은 이 셋을 잇는 변환정보를 담는다. **매핑 경로**: preset의 조각 outline → parse_svg()→Polyline.points → `Piece.outline`(PDF좌표, y뒤집음) / preset의 design_mapping(조각별 fit·anchor·scale) → `Piece.transform`(=scale_translate cm행렬) / page_size → `SizeLayout.page_size` / number_area·name_area(조각 상대비율) → A-4 text.py가 절대좌표 환산. engine 공개 API는 불변(주어진 것).
- **참조횟수**: 0

### [2026-06-19] path SVG → polyline SVG 전처리 경로 (engine/svg_normalize.py, parse_svg 앞단 도구)
- **분류**: architecture
- **발견자**: planner-architect
- **내용**: 운영 패턴 SVG가 두 형식으로 들어온다 — ①일러 "SVG Export Plug-In" = `<polyline>`(닫힌 윤곽만, parse_svg 직접호환, U넥) ②inkscape/PyMuPDF류 = `<path d="M/H/L/V...">`+개별 `matrix(a,b,c,d,e,f)`(보조선 포함, parse_svg 0조각, V넥). parse_svg는 polyline/polygon만 읽으므로(불변), ②를 ①로 바꾸는 **전처리 변환기 `engine/svg_normalize.py`**를 parse_svg **앞단**에 둔다(engine 코어 미접촉, ElementTree만 import, pattern.py에 함수추가 안 함=계층분리). 공개함수 `normalize_svg_paths(in,out,*,min_points,drop_open,flatten_curves,samples)->dict`. 흐름: path d 직선전개(M/H/L/V 절대·상대)+matrix적용(x'=ax+cy+e,y'=bx+dy+f)→**viewBox좌표 그대로**(flip_y 안 함, parse_svg가 flip→이중flip방지)→보조선(열린·세로·수평선) 필터→U넥형 polyline SVG. 곡선(C/Q/S/A) 폴백은 평탄화샘플링 인터페이스만 마련(V넥 곡선0이라 미사용). **변환은 1회성**(빌드단계), 산출 polyline SVG를 preset.sizes가 가리키면 이후 엔진은 V넥을 U넥과 동일취급. **V넥 실측**: 닫힌조각=앞·뒤 2개(소매부재), 변환후 높이정렬 앞=idx0/뒤=idx1. 좌표정합은 design_region_pt(펼침본4478×5669)→조각bbox(마커시트4478×3401)를 _piece_transform이 앵커+contain 자동수행(Phase C 방식A). data/patterns/농구_V넥_양면/ 폴더에 변환SVG13개+preset.json.
- **참조횟수**: 0

### [2026-06-18] job 선수별 통합 출력 경로 (engine/job.py, 응용 오케스트레이터 — grade.py와 동급)
- **분류**: architecture
- **발견자**: planner-architect
- **내용**: job.py는 "주문서 행(선수) × 디자인 → 선수별 배번/이름 출력"을 묶는 **응용 계층 오케스트레이터**다(engine 코어 무수정, grade.py와 같은 층). 공개 함수 `run_job(preset, design_pdf, order_rows, out_dir, font_path, split="per_player") -> {outputs, summary}`. **핵심 구조 사실**: grade()는 number/name 단일값으로 **전 사이즈 1PDF**를 만들지만 실작업 단위는 **선수별 + 자기 사이즈 1페이지**라 grade()를 직접 못 쓴다. build_layouts/grade의 공개 시그니처는 불변이어야 하므로(신규 인자 금지), job은 **preset dict를 얕은 복제 후 sizes를 해당 1개로 좁혀**(`{**preset, "sizes":[one]}`, _dir·area 등 공유) build_layouts(sized, design, number=r.number, name=r.name, warnings=)를 호출 → SizeLayout 1개를 얻는다(공개 API 무수정으로 사이즈 필터 구현). **흐름**: load_preset → 사용가능 사이즈집합 S 추출 → order_rows 순회(빈/미존재 사이즈는 skip+사유기록) → 행마다 사이즈 좁힌 preset으로 build_layouts → compose(design,[layout],tmp,design_page=0)=placements → verify_output(final, design, placements) → (옵션)preview. split=per_player는 행마다 compose 1회(파일별 PDF), split=single은 layout을 모아 루프 후 compose 1회(다페이지 1PDF). **재사용 지점**: grade.load_preset/build_layouts, compose.compose, order.parse_order(CLI에서 xlsx→rows), verify.verify_output/all_passed, preview.render_previews. text.py는 직접 안 부르고 build_layouts 내부 _apply_text_area가 number/name으로 호출. **저장 규약**: out_dir(=data/jobs/<날짜_주문명>/) 아래 output/(선수별 또는 1PDF)·preview/·job.json(summary 덤프). 원자적 쓰기=tmp에 compose 후 os.replace로 final rename(부분물 방지). 파일명=<size>_<번호zeropad>_<safe이름>.pdf(경로 금지문자 _치환, 충돌 시 접미사). pikepdf 비결정 출력은 verify_output엔 무영향(바이트동일 Form 1개만 확인). 폴더명 결정은 CLI 책임(run_job은 받은 out_dir만 채움 — 역할 분리).
- **참조횟수**: 0

### [2026-06-15] A-5 주문서 파싱 경로 (engine/order.py, 입력 파서·코어 독립) + STIZ 표준 주문서 양식 2종
- **분류**: architecture
- **발견자**: planner-architect
- **내용**: order.py는 xlsx→`[{name,number,size,qty}]`로 변환하는 **순수 입력 파서**로, engine 코어(compose/Piece/parse_svg)와 완전 독립(conventions "import만/코어 불건드림" 준수). 흐름: parse_order(xlsx)→[행dict] → (차기)job.py가 사이즈로 레이아웃 선택 + name/number를 A-4 text.py extra_ops로 연결. 폴더+JSON 원칙상 결과를 작업폴더 order.json으로 덤프 권장(검수·수정). **실데이터 86개 전수 분석 결과 STIZ 표준 템플릿 2종 확정**: ①「선수별 행」(81/86, 메인) — A=이니셜(이름) B=배번 C=상의사이즈 D=하의사이즈, 1선수=1행, 헤더 텍스트 '이니셜/배 번/사이즈'가 **2행 또는 3행**(신구 버전, 행 고정 금지·키워드 탐색), 헤더 아래 부제행(상의/하의) 건너뛰고 +2행부터 빈행까지가 데이터. ②「사이즈 집계」(5/86, 연습복·슈팅저지·추가주문) — '이니셜' 헤더 없이 A=사이즈 세로나열 B=수량, 이름·배번 없음(기존 grader order_parser.py 규칙으로 처리). 종목(농구/배구/축구/피구/줄넘기) 차이는 거의 없고 차이는 양식 버전에서 옴. 첫 시트=최신 접수일(시트명=날짜6자리), 과거 시트 다수 → 첫시트+사이즈최다시트 폴백. data_only=True 필수(배번이 수식/숫자). H~N열=시안이미지(무시). 사이즈 토큰에 **아동 호수 8/10/12/14호**(피구·줄넘기 76건) 포함, "○○호"는 이름끝 '호' 오탐 차단(^\d{1,2}호$). openpyxl Custom Properties 버그는 현 86개 전부 미발생(custom.xml 0개)이나 기존 grader StringProperty name=None→"" 몽키패치는 외부 xlsx 대비 방어 이식 권장.
- **참조횟수**: 0

### [2026-06-15] A-4 배번·이름 벡터 렌더 경로 (engine/text.py → Piece.extra_ops → compose 콘텐츠)
- **분류**: architecture
- **발견자**: planner-architect
- **내용**: 글자(배번 숫자/이름 한글)는 디자인 Form과 **완전히 분리된 별도 벡터 레이어**로 그린다. 흐름: preset.number_area/name_area(piece_id+rel_bbox 0~1 조각상대) → grade.py가 해당 piece(back)의 Piece.outline bbox(시트 절대좌표)를 구해 rel→절대 환산 → engine/text.render_text_ops(text, font_path, abs_bbox_pt, color_cmyk, align)이 fontTools로 글리프→큐빅 PDF경로(m/l/c h)+CMYK k fill 문자열 생성 → 그 문자열을 해당 Piece.extra_ops에 저장 → compose가 디자인 배치(q…Do…Q) 뒤에 extra_ops를 이어붙여 디자인 위에 글자를 얹음. **좌표계**: 글자는 시트(PDF) 절대좌표 y위로(방식A와 동일). rel_bbox는 좌하단기준 0~1 권고. **무손실 보장축**: 디자인 Form 바이트 불변(글자는 페이지 콘텐츠라 Form XObject 미변경) → device CMYK·단일임베드·verify PASS 유지. text.py는 "절대 bbox + 글자"만 받는 순수 함수라 job/웹앱에서 재사용. unitsPerEm→pt 스케일=목표높이/2048(Pretendard).
- **참조횟수**: 0

### [2026-06-15] 기존 일러 grading.jsx 좌표정합 방식 = "분해 후 요소 재조립"(engine과 철학 반대)
- **분류**: architecture
- **발견자**: planner-architect
- **내용**: 기존 일러는 디자인을 통짜로 얹지 않았다. 디자인 AI를 레이어로 분해('몸판'=배경색, '패턴선'=기준면적 측정용, '요소'/'요소_표_앞'=로고·배번·이름)하고, ①몸판색만 추출해 패턴 SVG 조각에 칠하고 ②요소를 면적비 스케일 `linearScale=√(targetArea/baseArea)`(보정지수 0.95 적용)로 키우고 ③각 요소를 소속 조각(body) 기준 상대벡터(X=중심기준, Y=하단기준)로 개별 재배치했다. 좌→우 cx 정렬 idx로 디자인body↔SVGbody 매칭, 양면은 4분면(좌우×상하) 매칭. 즉 **절대좌표 정합이 아니라 의미기반 재조립**. grader-v2 engine은 정반대로 디자인 PDF를 분해 없이 무손실 통짜 임베드+클리핑하므로, 일러의 요소 재조립 로직은 직접 이식 불가 → preset.json이 "통짜→조각 클립+cm변환" 정보만 제공하는 더 단순한 구조로 대체한다.
- **참조횟수**: 0
