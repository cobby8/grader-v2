# 에러 및 함정 모음
<!-- 담당: debugger, tester | 최대 30항목 -->
<!-- 이 프로젝트에서 반복되는 에러 패턴, 함정, 주의사항을 기록 -->

### [2026-06-25] PDF 클립 `W n`은 현재 경로를 소비한다 — 클립영역을 fill하려면 폴리곤을 다시 그려야
- **분류**: error
- **발견자**: developer / reviewer
- **내용**: 조각 클립은 `폴리곤(m/l…h) → W n`으로 구성되는데, **`W n`(또는 `W`+path-painting no-op `n`)은 클립 경로로 등록하면서 현재 경로를 비운다**(consume). 그래서 클립영역 안을 본체색으로 채우려고 `W n` 직후 곧바로 `k`(색)+`f`(fill)를 쓰면 **그릴 경로가 없어 아무것도 안 칠해진다**(흰틈 잔존). 반드시 fill용 폴리곤을 `m l…h`로 **다시 그린 뒤 `f`** 해야 한다(clip_path_ops 문자열 재사용 금지 — 그건 `W n`으로 끝남). 올바른 순서: `q / 폴리곤 W n(클립) / k / 폴리곤 재경로 h f(채움) / cm / Do(디자인) / Q`. 단 fill용·clip용 폴리곤은 **동일 좌표(piece.outline=시트좌표)** 여야 어긋남이 없다. 검증: fill이 클립영역 안·Do 앞에 위치 → 디자인 있는 곳은 디자인이 덮고 투명(빈)곳만 본체색. device k(4채널)+f라 투명도0·CMYK·벡터 유지(verify PASS), fill은 Do가 아니라 배치횟수 검증 영향 0.
- **참조횟수**: 0

### [2026-06-15] pikepdf 출력은 비결정적 — "바이트 동일" 회귀는 XObject 이름 통일 후 비교
- **분류**: error
- **발견자**: developer
- **내용**: compose 가 페이지 리소스에 디자인 Form 을 등록할 때 `page.add_resource()` 가 매 실행마다 **랜덤 22자 XObject 이름**(예 `/m7sgcvE74pBb70-IpyYT_A` vs `/uUgSFUmMJ1num_FR8x8Usg`)을 부여한다. 그래서 같은 코드·같은 입력으로 두 번 돌려도 **PDF 바이트가 다르다**(콘텐츠 스트림 안 `/이름 Do` 와 리소스 딕셔너리의 이름이 매번 달라짐, 압축 스트림이라 통째로 바뀜). 파일 크기는 동일·구조도 동일. **함정**: A-2/A-4 회귀 기준 "previewA/출력과 바이트 동일"을 `cmp`/`md5sum` 순수 바이트로 검증하면 코드가 정상이어도 항상 FAIL 처럼 보인다. **올바른 회귀 검증법**: pikepdf 로 양쪽을 열어 `page.obj.Contents.read_bytes()`(압축 해제됨)를 꺼내, 페이지 Resources.XObject 의 이름을 공통 토큰('/X')으로 치환한 뒤 콘텐츠 문자열을 비교한다(A-4 검증에서 길이 4097 100% 일치 확인). 또는 verify_output 의 "디자인 Form 바이트 동일/단일임베드/래스터 미추가" PASS 로 무손실을 간접 증명한다.
- **참조횟수**: 0

### [2026-06-15] fontTools 글리프 좌표는 '폰트단위' — em→pt 배율(scale) 말고 폰트단위→pt 배율(u=scale/upm)을 곱해야
- **분류**: error
- **발견자**: developer
- **내용**: text.py 글리프→PDF경로 변환에서 `_glyph_path_ops` 가 글리프 윤곽 좌표에 배율을 곱하는데, 글리프 좌표는 0~unitsPerEm(2048) 범위의 '폰트단위'다. 여기에 em→pt 배율 `scale`(=칸에 맞춘 글자높이) 을 그대로 곱하면 좌표가 **upm(2048)배 폭주**(100pt 칸에 '7' 한 글자가 16000pt 로 나옴). 반드시 폰트단위→pt 배율 `u = scale / upm` 을 곱해야 한다. 구분: scale=em(1글자칸)→pt, u=폰트내부단위→pt. advance(글자 진행폭)도 폰트단위라 `adv * u` 로 전진. 첫 렌더 좌표가 비정상적으로 크면 이 단위 혼동을 의심.
- **참조횟수**: 0

### [2026-06-15] 한글 Windows cp949 콘솔 UnicodeEncodeError
- **분류**: error
- **발견자**: debugger
- **내용**: 한글 Windows 기본 콘솔 인코딩은 cp949. 파이썬 프로그램이 '—'(U+2014), '→'(U+2192) 등 cp949에 없는 유니코드 문자를 print하면 UnicodeEncodeError로 크래시. 엔진 로직과 무관(PYTHONUTF8=1이면 PASS). 해결: 진입점에서 sys.stdout/sys.stderr.reconfigure(encoding="utf-8")로 출력 스트림 UTF-8 고정. 예방규칙: 한글 Win에서 도는 모든 파이썬 CLI는 진입점에서 stdout/stderr UTF-8 고정 + 파일은 open(encoding="utf-8") 명시.
- **참조횟수**: 0

### [2026-06-16] STIZ 주문서 xlsx는 다중 접수분 시트 누적 — "행 최다 시트 채택"은 과거 주문을 잘못 고른다
- **분류**: error
- **발견자**: tester
- **내용**: STIZ 표준 주문서 한 xlsx 파일에는 **여러 접수일 시트가 누적**돼 있다(시트명=날짜 6자리). 이번 주문은 **첫 시트**이며, 첫 시트 상단에 `주문번호: <폴더명과 일치>`와 `수량: 상의 NEA`(N=이번 주문 인원)가 명시된다. 나머지 시트는 같은 양식이지만 **과거의 다른 주문**(연습복/작년 접수분 등)이라 인원이 더 많을 수 있다. A-5 order.py가 시트를 고를 때 `len(parsed) > len(best)`(행 가장 많은 시트 채택) 폴백을 쓰는데, 이 때문에 **과거 대량 접수분 시트를 골라 이번 주문이 아닌 데이터를 반환**한다. 전수 86개 중 13개(15%)가 이 함정에 걸렸다(줄넘기 첫시트49→채택73, 중앙고 1→24, LG 8→16 등). **함정**: 검증을 '대표 5개'로만 하면 통과한다 — 우연히 그 5개는 첫 시트가 행 최다였기 때문. 정적 코드리뷰로도 안 보인다(실데이터 다종 표본 필요). **예방규칙**: 다중 시트 주문서는 (1)첫 시트 우선, 또는 (2)상단 `주문번호:`/`수량:상의 NEA`가 해당 건과 일치하는 시트 우선으로 채택하고, '행 최다'는 최후 폴백으로만 쓴다. 파서 검증 시 반드시 **시트가 2개 이상인 파일**을 표본에 포함하고, 첫시트 r1의 `상의 NEA` 수량과 결과 행수를 대조한다.
- **참조횟수**: 0

### [2026-06-20] preset "disabled" 사이즈 봉인은 한 경로(job)만 막고 다른 경로(grade)는 그대로 통과 — 삭제한 pattern_file을 읽다 크래시 [해결됨]
- **분류**: error
- **발견자**: tester
- **해결(2026-06-20 developer)**: sizes 내부 `"disabled": true` 표식은 build_layouts가 인지 못해 실패했다. **결함 사이즈를 sizes에서 아예 빼고 preset 최상위 `disabled_sizes` 섹션으로 이동**하는 방식으로 일원화해 해결. build_layouts/grade는 `preset["sizes"]`만 순회하므로 3XL이 sizes에 없으면 3XL.svg를 읽지 않아 크래시가 사라진다(grade.py 무수정). job은 `preset.disabled_sizes`(=`{이름→사유}`)에서 disabled_map을 읽어 결함 사이즈 주문을 명확 사유로 skip(5XL 대체 0). 검증: V넥 grade 배치 36회(12사이즈×3조각) PASS·FileNotFoundError 없음, job 3XL 2건 skip·5XL 오출고 0·verify 5/5, U넥(disabled_sizes 키 없음) 회귀 0, 단조성 가드 정상 12개 통과/결함 검출. **남는 교훈**: 사이즈/조각을 "비활성"하는 표식을 도입할 때, **표식을 모르는 경로가 있으면 표식이 아니라 데이터 자체를 그 경로의 순회 대상에서 빼는 것**(섹션 분리)이 더 견고하다. 한 경로만 검증하고 "안전"이라 결론내지 말 것 — disabled/skip 로직은 경로별로 독립이다.
- **참조횟수**: 1

### [2026-06-22] 실제 OS 파일 드롭 실패 — 드롭존 요소에만 리스너를 달면 자식 span/패딩 드롭이 브라우저 기본동작(새 탭)으로 샌다. playwright 합성 drop 은 이 함정을 못 잡는다 [해결됨]
- **분류**: error
- **발견자**: debugger
- **내용**: work.html 드롭존이 `<button class="dropzone">` + 자식 `<span>`(아이콘/제목/힌트) 구조인데, `wireDropzone`이 그 **button 요소에만** dragenter/dragover/dragleave/drop 리스너를 달았다. 실제 마우스로 파일을 끌어 놓으면 커서가 박스 정중앙이 아니라 **자식 span(글씨) 위·패딩·여백**에 떨어지기 쉽다. span 위 drop 이벤트는 button 핸들러로 안 잡히고 **document 까지 버블링**되는데, document/window 레벨에 dragover/drop `preventDefault` 가드가 없으면 브라우저 **기본동작(파일을 새 탭에서 열기/무시)** 으로 빠져 "끌어다 놔도 아무 반응 없음(첨부 안 됨)"이 된다. 클릭 업로드는 별개 경로라 정상. **결정적 함정**: playwright `dispatchEvent`/합성 drop 은 핸들러가 달린 요소에 이벤트를 **직접** 쏘므로(좌표 빗나감·버블링 함정이 없음) 항상 PASS 한다 → **합성이벤트 PASS 만으로 실제 OS 드롭이 된다고 결론내면 안 된다.** 부차로 StaticFiles 는 etag/last-modified 캐시를 줘서 수정한 work.html 이 옛 버전(드롭 핸들러 없는)으로 떠 있을 수 있다.
- **해결(2026-06-22)**: (1) 요소별 리스너를 버리고 **document 레벨 단일 dragover/dragleave/drop 가드**로 전환. dragover 에서 `preventDefault`(이게 있어야 drop 이벤트가 발생) + `dropEffect="copy"`. drop 에서도 `preventDefault` 로 어디에 떨어뜨려도 새 탭 열기를 원천 차단. (2) 드롭 좌표(clientX/clientY)를 각 드롭존의 `getBoundingClientRect()` 박스와 비교해 **영역 판정**으로 라우팅 → 자식 span·패딩 어디에 떨어져도 디자인→uploadDesign(/api/design/check)·주문→uploadOrder(/api/order/parse)로 클릭과 동일 경로로 흐른다. `wireDropzone`은 시그니처 유지하되 id→onFile 등록만 담당(렌더 재생성마다 최신 콜백 갱신). (3) work.html `<head>`에 `Cache-Control: no-cache, no-store, must-revalidate` + Pragma + Expires meta 추가(옛 버전 캐시 방지, 강력새로고침 불필요). **검증**: CDP/좌표 기반 drop 으로 **자식 span 좌표(SPAN.dropzone__title)에 직접** 드롭 → 디자인 /api/design/check 호출+filecard, 주문 /api/order/parse 호출+12행. 드롭존 밖(5,5) 드롭 → URL 변경 0·탭 1개(새 탭 안 열림). 클릭 업로드 회귀 0.
- **예방규칙**: 브라우저 파일 드롭은 (1) **반드시 document/window 레벨에 dragover+drop preventDefault 가드**를 깔고(요소 리스너만으론 자식/패딩 드롭이 샌다), (2) 드롭존 판정은 요소 타겟이 아니라 **좌표 vs getBoundingClientRect**로 하며, (3) 검증은 합성 dispatchEvent 가 아니라 **드롭존 자식 요소 좌표·드롭존 밖 좌표**에 실제 드롭을 흘려 새 탭 미발생·API 호출을 함께 확인한다. 정적 화면 수정이 안 먹는 것 같으면 캐시(etag/304)부터 의심하고 no-cache 헤더/meta 를 확인한다.
- **참조횟수**: 0

### [2026-06-19] 패턴 SVG 변환은 "조각수=2 + verify PASS"만으로 정상이 아니다 — viewBox/좌표계가 사이즈별로 섞이면 그레이딩이 깨진다
- **분류**: error
- **발견자**: tester
- **내용**: V넥 13개 패턴 SVG 중 **XL만 viewBox 가로(4478x3401)·양수 좌표**이고, 나머지 12개(5XS~L, 2XL~5XL)는 **viewBox 세로(4478x5669) + 조각 x좌표가 음수**(예 M 앞판 x[-1341..313])다. 원본 .ai 13개를 PyMuPDF로 변환하면 **전부 viewBox 가로(3401)·양수**가 나오는데(변환기 svg_normalize.py 자체는 정확 — d파서 M/H/L/V 전개·matrix 적용 수동검산 일치, XL은 .ai 변환과 커밋본이 완전 일치), 커밋된 12개는 **XL과 다른 출처 SVG**(위·아래 2벌 중복된 세로 5669본)에서 변환돼 좌표계가 어긋났다. **함정**: (1)parse_svg 조각수는 13개 모두 정상 2개로 나온다(중복제거가 잘 돼서). (2)svg_index 앞=0/뒤=1 일관성도 13개 전수 OK로 나온다. (3)verify_output도 PASS한다(verify는 "디자인 Form 무손실 임베드"만 보지 위치/캔버스 크기를 안 봄). (4)job도 produced/verify_pass가 정상 카운트된다. -> 이 4개 신호가 전부 초록불이어도 실제 출력은 깨진다. 음수좌표 조각을 contain 정합하느라 cm translate가 -1788pt까지 밀리고, 출력 페이지가 세로 길쭉(2811x5351)이 되며 앞판이 캔버스 밖으로 나가 소실(미리보기에 뒤판만 보임). XL(올바른 좌표)만 앞·뒤 정상. **유일하게 잡아낸 검증**: 사이즈별로 (a)변환본 viewBox가 동일한지 + 조각 x좌표가 viewBox[0..W] 안에 드는지(음수/초과 금지) 점검, (b)출력 PDF page rect가 사이즈 무관 동일 비율(가로)인지, (c)미리보기 PNG 육안(앞판 존재 여부). **예방규칙**: 패턴 변환 검증은 "조각수=2 + verify PASS"로 끝내지 말고 (1)13개 viewBox 전수 동일 (2)조각 bbox가 viewBox 안(min>=0, max<=W/H) (3)모든 사이즈 미리보기 육안(스모크를 XL 1개만 보면 통과해버림 — 깨진 건 비-XL 12개라서)을 필수로 한다. 변환 입력 원본의 출처(.ai 직변환본인지)를 사이즈마다 통일해야 한다.
- **참조횟수**: 0
