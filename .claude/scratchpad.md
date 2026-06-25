# 작업 스크래치패드

## 현재 작업
- **요청**: 합성 '패턴선 안쪽 흰틈' + '극단소형 흰요소(줄무늬) 재단선 미달' 동시해결. 해법 A(본체색 배경채움)+B(사이즈별 자동 블리드). cowork 검증완료.
- **상태**: 🔵 진행중 — tester+reviewer 병렬 검증 단계 (구현 완료)
- **현재 담당**: tester+reviewer

### 의뢰서 핵심 (A+B 둘 다 적용, 등방 유지)
- **A) 본체색 배경채움**: flatten.detect_background_cmyk(design)로 본체색 1회 감지(이번값 (0.8,0.5,0,0.1)) → run_job 시작 시 감지·compose 전달(또는 preset 'body_fill' 캐시). pdfutil.place_block에 bg_cmyk 인자 추가: 클립 직후·Do 전 폴리곤을 본체색 fill (q/폴리곤 W n/k/h f/cm/Do/Q). 인자없으면 생략(하위호환).
- **B) 사이즈별 자동 블리드**: dev=|(앞판폴리곤 w/h)/(디자인영역 w/h)-1|; bleed=clamp(1.0+1.3*dev,1.0,1.12). XL=1.0·5XS≈1.10·2XS≈1.056·M≈1.02·5XL≈1.036. _build_precise_layout에서 사이즈별 산출→_job_piece_transform 전달(단일 cover_bleed 대신). preset 'auto_bleed':true로 켜고 K·clamp 옵션화.
- **불변**: compose/verify 시그니처 외 동작유지. CMYK·투명도없음·벡터유지(verify PASS). 번호/이름 등방(비등방 금지).
- **완료기준**: ①전사이즈(5XS~5XL) 본체·흰요소 재단선까지 채움(흰틈0) ②번호/이름 무왜곡·재단선1줄 ③verify 전사이즈 PASS ④cowork 최종 시각검증.

## 진행 현황 (완료 — 상세는 git 히스토리)
| 작업 | 내용 | 결과 |
|------|------|------|
| 정합보정 4이슈 | 번호잉크정렬·재단선·암홀X3조각·번호글리프셋 | ✅ 푸시 |
| 빈본체 design_file | 88KB 본체 정식설정 | ✅ |
| 출력형식 PDF/EPS/both | flatten Group제거·eps2write·verify_eps·--format | ✅ tester13/13 |
| 웹앱1~5 | FastAPI 골격·order/design5케이스·jobs비동기·기록/등록/설정·run.bat+E2E | ✅ rev종합 치명0 |
| 화면버그 5건 | both/EPS실효·드래그앤드롭·패턴헤더·3XL칩·설정푸터 | ✅ tester9/9 |
| 실OS드롭 버그 | document가드+좌표판정 | ✅ debugger |
| 합성1 자동매핑 | reference build-preset·preset 앞뒤/y하한 교정 | ✅ 정답값 0pt일치 |
| 합성2+3 | cover+블리드·재단선1줄(svg_polygon)·패턴선 OCG제거 | ✅ tester12/12·rev통과 |

## 백로그 (차단 아님, 후속)
- **[합성 일반화]** hide_design_cutline_layer(OCG 콘텐츠삭제)는 V넥 템플릿 BDC구조·레이어명("패턴선")·page0 한정 → 신규 디자인 온보딩 시 BDC구조·레이어명 재확인 체크리스트. 재단선 보존체크가 n_out>=expected라 '과다(두줄)' 못 거름(시각검증 보완).
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·design_token·_JOBS·_design_no_cutline/_flattened_design TTL 정리 루틴(디스크/메모리 누적). progress 진행 콜백.
- **[디자이너 입력 대기]** 재단선 PDF포함 .ai 재출력(인프라 완비) / 올바른 3XL.ai 재확보(현 disabled).
- cowork 최종 오버레이 검증(번호글리프셋·밴드·재단선·본체·합성). band design_region 정밀재추출.
- [출력형식] verify_eps origin_ok 무의미가드·GS경로/임계 일부 하드코딩. 하의 사이즈분리 / 주문서판별③가드 / shrink등방 / sizes.scale.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). CLI/curl 단독검증. GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만). 커밋 전 ast.parse/py_compile.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→**cover**(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, **cover_bleed preset 키 있을때만**(없으면 contain=U넥 회귀0). 블리드 1.03으로 안쪽 흰틈 제거, clip이 넘침 차단.
- **재단선**: 조각 SVG poly.points(=clip outline 동일좌표·너치 포함)를 시트좌표 그대로 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). cutline.draw_from="svg_polygon". transform 안 감쌈(이미 시트좌표).
- **디자인 패턴선 두 줄 방지**: OCG D.OFF는 Form 합성에 무효(compose가 OCProperties copy 안 함) → **콘텐츠 /OC /MCx BDC…EMC 구간 삭제**(깊이카운트 짝맞춤, 빨강1색만 제거·5색 무손실). hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=조각 design_region(CTM적용·Form Fm0 재귀). SVG 넥깊이(상단35%·중앙±15%)로 앞(V넥 깊이큰=svg1)/뒤(라운드=svg0)/밴드(높이최소=svg2) 매칭. parse_svg 높이정렬 인덱스=svg_index.
- 글자주입: text place_*(잉크 bbox 중앙정렬, 디자인좌표) → job 조각 transform 감싸 extra_ops(클립 밖). 번호: preset glyph_source 있으면 글리프셋, 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체 PDF에 들어감(안 켜면 3.4KB 흰화면). 정상 빈본체=88KB(본체+밴드+재단선3, 텍스트0).
- **출력형식**: flatten Form투명도그룹 제거(EPS 래스터화 트리거)·페이지그룹 /CS 보존(색시프트 방지). eps2write(output/pdf·eps 분리). EPS 305KB 벡터.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2(교정완료). 12사이즈(3XL disabled). disabled_sizes는 sizes 밖.
- ⚠️ 변환함정(errors.md): 조각수+verify만으론 부족→viewBox통일·양수·미리보기 육안. 인접사이즈 좌표동일=자산결함. STIZ 헤더 nbsp. 브라우저 드롭은 document가드+좌표판정(합성이벤트 검증 금물).

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference(+build_pieces_preset/extract_design_pieces)·job(정밀배치+cover/블리드+재단선polygon+OCG제거+disabled+out_format)·svg_normalize(+가드)·order(①②③STIZ)·flatten(+Group제거)·eps·compose·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main·api(health/patterns/settings·order/parse·design/check5·jobs비동기+progress+preview+zip·jobs기록·patterns등록)·state·run.py·run.bat. webapp/static=_handoff/grader-v2-static 복사본(원본 보존, 갱신시 재복사).
- 보조: scripts/ai_to_path_svg.py, illustrator-scripts/ai_to_svg.jsx.
- 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면(SVG12+preset+number_glyphs.json)}. data/{jobs,uploads}/·settings.json(.gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai, README): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋_아트보드2.ai·_완성본_본체포함_XL.ai.
- 주문서: C:/Users/user/Desktop/새 폴더/260213_…추가주문서.xlsx. 암홀X 패턴: Desktop/V넥 스탠다드-A(암홀X)/. 폰트 data/fonts/HY헤드라인M.ttf. GS C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- git: origin=cobby8/grader-v2, main. **미푸시 ~11개**(웹앱/출력형식/화면버그/드롭/합성1·2·3).

## 구현 기록 (developer)

### 합성 품질 A(본체색 채움)+B(자동 블리드) (2026-06-25)
📝 구현한 기능: (A) 패턴선 안쪽 본체 흰틈을 본체색으로 채움 + (B) 사이즈별 자동 블리드로 극단소형 흰요소(줄무늬)가 재단선까지 닿게 함. 둘 다 등방 유지 → 번호/이름 무왜곡.

- **A 핵심**: 본체 fill은 클립(`W n`) 직후·`Do` 앞이어야 디자인이 그 위를 덮음(디자인 있는 곳=디자인색, 빈 곳만 본체색). 호출자 compose는 불변이므로 Piece에 `bg_cmyk` 필드 추가→place_block이 fill 주입. ⚠️`W n`이 경로를 소비하므로 fill용 폴리곤을 `m/l…h f`로 **재경로**(clip_path_ops 재사용 X).
- **B 핵심**: 앞판(front) 1개 기준 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1.0+k·dev, lo, hi)` 1회 산출→전 조각 동일 적용(등방). cover_bleed가 dict({auto,k,min,max})면 자동, float이면 기존 단일, None이면 contain(U넥 회귀0).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/pdfutil.py | `_fill_polygon_ops()` 신규(폴리곤 재경로+device k+f) / `place_block`에 `bg_cmyk=None` 인자 추가(W n 직후·Do 앞 fill) | 수정 |
| engine/compose.py | `Piece.bg_cmyk: Optional=None` 필드(extra_ops 선례) / 루프서 `place_block(..., bg_cmyk=piece.bg_cmyk)` 1줄 | 수정 |
| engine/job.py | `_auto_bleed()` 신규 / `_build_precise_layout`에 `bg_cmyk` 인자+cover_bleed dict 해석(앞판 단일 bleed)+Piece.bg_cmyk 셋 / run_job 본체색 1회 감지(preset.body_fill>detect_background_cmyk>None)+cover_bleed dict 보존 | 수정 |
| data/patterns/농구_V넥_양면/preset.json | `body_fill:[0.8,0.5,0,0.1]` 추가, `cover_bleed`를 `{auto,k:1.3,min:1.0,max:1.12}`로 | 수정 |

💡 tester 참고:
- 테스트 명령: `python -m engine job --preset data/patterns/농구_V넥_양면/preset.json --design design_source/연세대_V넥_빈템플릿_본체포함_XL.ai --order <주문서> --out <out> --split per_player --format pdf` → 전사이즈(5XS~5XL) preview PNG.
- 정상 기준: ①job verify_pass=True(투명도없음·CMYK·배치횟수) ②페이지콘텐츠에 본체색 `0.8 0.5 0 0.1 k`+`f`가 조각수만큼(클립 안, 금지연산자 rg/g/RG 0) ③패턴선 안쪽 흰틈0(어깨/옆선/밴드끝) ④번호/이름 등방·중앙정렬 회귀0·재단선 1줄.
- **사이즈별 기대 bleed(검산 일치)**: 5XS=1.0983, 4XS=1.0835, 3XS=1.0695, **2XS=1.0563**, XS=1.0438, S=1.0319, **M=1.0207**, L=1.0101, **XL=1.0000**, 2XL=1.0097, 4XL=1.0276, **5XL=1.0360**. (설계 XL=1.0/M≈1.02/2XS≈1.056/5XS≈1.10/5XL≈1.036 전부 일치)
- 주의 입력: body_fill 없는 preset→자동감지(detect_background_cmyk)→실패시 None(채움생략, 기존동일). cover_bleed가 float인 U넥→기존 단일 cover 그대로.

⚠️ reviewer 참고:
- **불변제약 준수**: compose/verify/parse_svg/_job_piece_transform/grade 시그니처·동작 무수정. Piece 신규필드는 기본값(extra_ops 선례). place_block은 `bg_cmyk=None` 기본값만(bg=None ⇔ 인자생략 출력 완전동일=검증함). _build_precise_layout은 keyword 기본값만 추가. CMYK·불투명·벡터(device k+f). Do개수 불변(fill은 Do 아님)→배치횟수 PASS.
- 봐줬으면: ①place_block fill 순서(W n < fill < Do, 검증완료) ②cover_bleed dict↔float↔None 3분기 하위호환 ③본체색 우선순위(preset.body_fill > 자동감지 > None) ④_auto_bleed clamp 경계(XL=1.0 하한 닿음).
- **ast.parse + py_compile**: pdfutil/compose/job.py 3파일 전부 통과. preset.json JSON 파싱 통과. place_block/Piece/_auto_bleed 런타임 스모크 전부 통과.

### 배번 "1" lsb 보정 (2026-06-22)
📝 구현한 기능: 번호 글리프셋에 글자별 **lsb(left side bearing, 칸 왼쪽 여백)** 추가 — 특히 "1"이 칸 왼쪽 끝에 붙어 치우치던 문제 해소. 자간(advance)은 균일(597)이지만 lsb는 글자마다 다른데('1'=108, '0'=56 폰트단위) 잉크 좌하단 정규화로 그 정보가 사라졌던 게 원인.

- **원인**: extract 가 잉크 좌하단(x0)을 (0,0)으로 정규화 → 모든 글자가 칸 왼쪽 끝(lsb=0)에 붙음. '1'(원래 lsb 큼)은 본래 칸 안쪽에 좁게 그려져야 하나 왼쪽 치우침 + 다음 글자와 너무 붙음.
- **해결(lsb식)**: 폰트 hmtx에서 글자별 lsb(폰트단위) 읽어 `lsb_pt = lsb_units × (그 글자 advance_pt / 597)` 로 advance 와 같은 글리프 pt 단위 환산. 렌더는 `gx = dx0 + lsb*s + shift_x`(잉크 bbox 측정도 동일 +lsb*s → 중앙정렬 보존). lsb 없으면 0 폴백.
- **검증값(폰트 일치)**: '1'→64.4152, '0'→33.4005, '2'→30.4183 (계획 기대값 정확 일치).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/number_glyphs.py | `_font_glyph_lsbs()` 헬퍼 추가(hmtx 글자별 lsb) / extract 에 glyph별 lsb 저장(rep_advance 597 분모) / render gx·잉크bbox 둘 다 +lsb*s | 수정 |
| engine/cli.py | number-glyphs 출력에 lsb 표시 | 수정 |
| data/patterns/농구_V넥_양면/number_glyphs.json | --font 재추출(subpath/width/advance 동일, lsb만 추가) | 재생성 |

💡 tester 참고:
- 테스트 방법: `python -m engine job --preset data/patterns/농구_V넥_양면/preset.json --design design_source/연세대_V넥_빈템플릿_본체포함_XL.ai --order _glyphtest/order_lsb.xlsx --out _glyphtest/out_lsb --split per_player --format pdf` → preview PNG.
- 정상 동작: "1" 잉크가 lsb만큼 우측 이동(치우침 해소), 다음 글자 간격 정상. 한자리/세자리 중앙정렬 유지.
- **폰트 대비 자간 수치(cap200, pitch=글자중심간격, 우리/폰트 비율)**: "11" pitch 132.23=132.23 차이 **0.0**(비율 1.0). "10" 148.3 vs 141.8 차이 6.6(비율 1.047). "123" [146.5,130.3] vs [142.3,131.8] 차이 [4.2,-1.5](비율 0.99~1.03). "20" 134.1 vs 131.7 차이 2.4(비율 1.018). 모두 ±소오차 일치(advance 균일356 vs 폰트597 차이서 미세편차, 정상).
- "1" 잉크 시작 xmin = lsb*s(=23.92pt @cap200) 정확히 우측 이동.
- 회귀: selftest 종합 PASS(합성24회 무손실·inkcov편차0). job verify_pass 4/4. 구버전(lsb없음) 폴백 크래시0(0 폴백, "10"/"123" lsb효과 반영, "11"은 양쪽 동일lsb라 shift_x 상쇄=구버전과 동일).
- 번호 글자: 페이지레벨 device CMYK `k` fill 3회·`f` 3회, **금지연산자 0**. (PDF 전체 16개 금지연산자는 디자인 본체 Form XObject 내부 색=원본 무손실 보존분, 주입글자 아님.)
- PNG 경로(11·123 포함): `_glyphtest/out_lsb/preview/XL_11_KIM.png`, `XL_123_LEE.png`, `XL_20_PARK.png`, `XL_07_CHOI.png`. cowork 모음: `_glyphtest/cowork_lsb/`.
- 주의 입력: 폰트 미지정 추출 시 lsb 키 없음(0 폴백). 단자리("7")는 lsb가 shift_x로 상쇄돼 중앙정렬 그대로.

⚠️ reviewer 참고:
- 불변 제약 준수: place_number/place_name/compose/Piece/parse_svg/verify_output 시그니처 무수정(extract/cli만 기존 인자 재사용, 신규 인자 추가 없음). CMYK 무손실. shift_x 중앙정렬 유지(잉크bbox에도 동일 lsb 반영). preset 얕은복제 무영향. ast.parse/py_compile 통과.
- 봐줬으면: render 의 `g.get("lsb",0.0)*s` 폴백 분기(잉크bbox·gx 두 곳 동일 적용 일치성), extract 의 lsb 저장 가드(glyph_lsbs/adv_ratio/rep_advance 전부 있을 때만).

### 배번 자간 수정 (2026-06-22)
📝 구현한 기능: 번호 글리프셋의 글자 자간(advance) 복원 — 기존엔 잉크폭(width)만큼만 전진해 "20"의 2와 0이 다닥다닥 붙었음. 폰트(HY헤드라인M)는 글자칸(advance)에 좌우 여백을 포함하는데 글리프셋엔 그 정보가 없던 게 원인.

- **원인**: render_glyph_number_ops 가 `pen_x += width*s` 로 잉크폭만큼만 전진 → 폰트가 본래 두던 글자칸 여백이 사라져 붙음.
- **해결(방식 A)**: HY헤드라인M 숫자 advance(597, monospace 균일) ÷ 대표 잉크높이(903) = **0.6611** 비율을 구해, 각 글리프 cap_height × 0.6611 = advance(pt) 저장. cap_height 538.583 × 0.6611 ≈ **356pt 균일**. 렌더는 `pen_x += advance*s`(advance 없으면 width 폴백=구버전 JSON 호환).

| 파일 경로 | 변경 내용 | 신규/수정 |
|----------|----------|----------|
| engine/number_glyphs.py | `_font_advance_ratio()` 추가(fontTools로 advance÷잉크높이 비율) / extract 에 `font` 인자→glyph별 advance 저장+메타(advance_font/ratio) / render pen_x 전진을 advance(폴백 width)로 | 수정 |
| engine/cli.py | number-glyphs 에 `--font` 옵션 + 선검증 + advance 출력 | 수정 |
| data/patterns/농구_V넥_양면/number_glyphs.json | --font 로 재추출(width/subpath 동일, advance만 추가, ratio 0.66113) | 재생성 |

💡 tester 참고:
- 테스트 방법: `python -m engine job --preset data/patterns/농구_V넥_양면/preset.json --design design_source/연세대_V넥_빈템플릿_본체포함_XL.ai --order _glyphtest/order_20_7.xlsx --out _glyphtest/out --split per_player --format pdf` → preview PNG 확인.
- 정상 동작: 앞/뒤 "20"의 2와 0 분리(gap 양수), 한자리 "7"·세자리 "123" 중앙정렬 유지.
- 검증 수치(좌표계산): 앞·뒤 "20" pitch/잉크폭 ≈ **1.174~1.190**(완성본 1.16 ±0.03=1.13~1.19 내), 2-0 gap=36.4pt(분리). "7" 잉크중심=(center)정확, "123" 각 글자 분리·중앙정렬.
- 회귀: selftest **종합 PASS**, job verify_pass 2/2(번호 ops `0 0 0 1 k`+f, 금지/외부연산자 0, 경고 0).
- PNG 경로(번호 20 포함): `_glyphtest/out/preview/XL_20_KIM.png`, `XL_07_LEE.png`.
- 주의 입력: cap_height 다른 글자('5'는 537.889)도 자기 cap_height×0.6611로 계산되나 차이 미미. 구버전 JSON(advance 키 없음)은 자동 width 폴백.

⚠️ reviewer 참고:
- 불변 제약 준수: place_number/place_name/compose/Piece/parse_svg/verify_output 시그니처 무수정(extract/cli만 신규 인자 기본값 추가). CMYK 무손실. 한자리/세자리 중앙정렬 유지(잉크 bbox는 width 기반 그대로). preset 얕은복제 영향 없음. ast.parse/py_compile 통과.
- 봐줬으면: render 의 advance 폴백 분기(advance None/0 → width), _font_advance_ratio 폰트 미존재/실패 시 None 반환→advance 키 미저장 경로.

## 리뷰 결과 (reviewer)

### 합성 품질 A(본체색 채움)+B(자동 블리드) 리뷰 (2026-06-25, 코드 무수정)

📊 종합 판정: **통과 (치명 0)**

검토 파일: pdfutil.py(_fill_polygon_ops/place_block) · compose.py(Piece.bg_cmyk·호출1줄) · job.py(_auto_bleed/_build_precise_layout/run_job 본체색) · preset.json.

✅ 잘된 점:
- **A 재경로 정확**: place_block 의 polygon 인자가 클립(clip_path_ops)과 fill(_fill_polygon_ops)에 **동일 변수로 전달**됨. 둘 다 piece.outline(=poly.points, 시트좌표) 동일 좌표 → "W n 후 경로소비→재경로" 우려한 좌표어긋남/clip_path_ops 재사용 버그 **없음**. 연산자 순서 `q→W n→k+m/l h f→cm→Do→Q` 정확(fill 이 클립 안·Do 앞).
- **CMYK·불투명·벡터**: _fill_polygon_ops 는 device `k`(4채널)+`f` 만. rg/g/RG/투명도 연산자 0 → verify '투명도없음·CMYK유지' 충족. fill 은 Do 아님 → 배치횟수(Do개수) 검증 영향 0.
- **불변제약 준수 확인**: place_block(bg_cmyk=None)·Piece.bg_cmyk(=None)·_build_precise_layout(bg_cmyk/cover_bleed) 전부 **기본값 키워드 인자**만 추가. compose 시그니처 무수정(루프 1줄 인자전달만). bg_cmyk=None ⇔ 인자생략 시 출력 문자열 완전 동일(fill="") → U넥/grade 하위호환 0회귀. _job_piece_transform 무수정(bleed 인자 기존 존재, 호출자서 값만 산출).
- **B 식 정확**: _auto_bleed dev=|(pw/ph)/(dw/dh)-1|, bleed=clamp(1+k·dev,lo,hi) 설계와 일치. dw/dh/pw/ph≤0 **0나눗셈 방어**(하한 폴백) 있음. front 단일 bleed 산출→전 조각·번호/이름 동일 적용=등방 유지.
- **3분기 안전**: cover_bleed dict(auto:true)→자동, dict(auto없음)→contain 폴백+경고, float→기존 단일, None→contain. KeyError 없음(전부 .get 기본값). float 음수/0 은 _job_piece_transform 의 `bleed<=0` 가드로 contain 폴백.
- **본체색 우선순위 안전**: preset.body_fill(len==4 가드) > detect_background_cmyk > None. detect_background_cmyk 에 **pikepdf.Pdf 객체**(path 아님) 정확히 전달, try/finally 로 close. 감지 전체 try/except→실패해도 None(채움생략)로 안전 폴백.

🟡 주의(차단 아님):
- **[job.py:732] _auto_bleed 직전 `polys[front_pdef["svg_index"]]` 범위가드 부재**: 본 조각루프(747~750줄)엔 svg_index 범위검사가 있으나 이 줄엔 없음. 자산 결함 등으로 svg_index 가 SVG 조각수 초과 시 IndexError. 단, 행 단위 try/except(1177줄)에 잡혀 **해당 선수 행만 skip**(부분성공)되므로 치명 아님. front_idx 폴백(0)은 잘 처리됨.

🟢 제안(선택):
- **[pdfutil.py:56] _fill_polygon_ops 의 `k0,k1,k2,k3 = [float(v) for v in cmyk]`**: cmyk 길이 4 가정. body_fill 은 run_job(1009줄)서 len==4 가드, 자동감지값도 CMYK 4채널 타입이라 현재 안전. 방어적으로 길이체크 한 줄 추가 가능(필수 아님).
- 빈 폴리곤/None: bg_cmyk=None 분기로 fill 미생성, polygon 자체는 기존 clip 과 동일 소스라 추가 위험 없음.

📌 검증결론: 의뢰 5개 중점포인트(불변제약·A순서/재경로·B식/3분기·본체색우선순위·엣지) **전부 이상 없음**. 시각/사이즈별 흰틈0·블리드값 실측은 tester 영역. **리뷰 통과**, 수정 요청 등록 없음.

## 테스트 결과 (tester)

### 합성 품질 A(본체색채움)+B(자동블리드) 검증 (2026-06-25, 독립검증 — 코드 무수정)
검증 방법: 전사이즈(5XS~5XL 12개) per_player PDF job → ①summary/job.json verify ②출력 PDF 콘텐츠 스트림 연산자·색·순서 분석 ③미리보기 PNG 육안(5XS·M·XL·5XL) ④selftest 회귀 ⑤place_block/Piece/compose 시그니처·하위호환 동등성 코드테스트 ⑥float cover_bleed·자동감지 경로 실행.

| # | 검증 항목 | 결과 | 근거(수치·경로) |
|---|----------|------|----------------|
| 1 | **전사이즈 12개 verify_pass=True** | ✅ PASS | summary produced 12/verify_pass 12/fail 0/skip 0. 각 출력 checks: 투명도없음·CMYK유지·Do 3회(기대3)·무손실·래스터미추가 전부 ok. 금지연산자(rg/g/RG/G)=0 (12개 전수). |
| 2 | **A 본체색 채움** | ✅ PASS | 12개 전수 본체색 `0.8 0.5 0 0.1 k`+`f` ×3(조각수). 순서 `W n(클립)→k→폴리곤재경로 h f→cm→Do` 검증(클립 안, Do 앞). 육안: 5XS/M/XL/5XL 어깨·옆선·밴드끝 흰틈 0. flatten.bg=[0.8,0.5,0,0.1]. |
| 3 | **B 사이즈별 bleed 검산** | ✅ PASS | 산출값=기대값 정확 일치: 5XS=1.0983, 2XS=1.0563, M=1.0207, **XL=1.0000(하한 닿음)**, 5XL=1.0360. 전 12개 ±0.00. clamp[1.0,1.12] 이내. 육안: 5XS 옆선 흰줄무늬 재단선까지 닿음(극소형 미달 해소). |
| 4 | **번호/이름 무왜곡** | ✅ PASS | "20" 전사이즈 등방·중앙정렬 유지(scale 무관 자간 동일). 번호 흰글자 `0 0 0 0 k`+f ×3. 깨짐/비등방 0. 재단선 `0 0.96 0.95 0 K`+S, 2.0pt ×3 (cutline found0/expected3/mapped3=svg_polygon 1줄). |
| 5 | **하위호환 회귀** | ✅ PASS | place_block: bg_cmyk **생략 == None명시 출력 바이트 완전동일**(코드테스트 True). Piece.bg_cmyk 기본값=None(extra_ops 선례). cover_bleed **float(1.03) 경로** 정상(배수1.03 단일·verify PASS·크래시0). body_fill 제거 시 **자동감지=(0.8,0.5,0,0.1)** 동작(preset>자동>None 우선순위). compose 시그니처 무수정. ※U넥 design_XL.ai 자산부재로 full job 불가 → 코드 동등성으로 본질 검증. |
| 6 | **selftest 종합 PASS** | ✅ PASS | 합성 24회 무손실·inkcov 최대편차 0.000000·Do 24회(기대24)·투명도없음. 종합 PASS. 회귀 0. |

📊 종합: 6개 항목 전부 ✅ PASS. **판정: 합격(A 본체색 채움·B 자동블리드 정상, 등방 유지, 하위호환·회귀 0).**

미리보기 PNG(cowork 검증용): `_abtest/out_allsize/preview/5XS_20_5XS.png`(극소형 본체채움·흰줄무늬 재단선 닿음), `XL_20_XL.png`(블리드1.0 기준·번호등방), `M_20_M.png`, `5XL_20_5XL.png`. 12개 전사이즈 동 폴더.

⚠️ 참고(차단 아님):
- U넥(농구_U넥_양면)은 design_XL.ai가 .gitignore 자산이라 **로컬에 없음** → full job 회귀는 불가했음. 대신 place_block bg_cmyk=None 생략 동등성(바이트 일치)·cover_bleed float/None 3분기·Piece 기본값으로 하위호환의 본질을 코드레벨 검증함(의뢰서 5번 "bg=None ⇔ 인자생략" 충족). 추후 U넥 자산 확보 시 full job 시각회귀 권장.
- 3XL은 자산결함(disabled_sizes)로 정상 skip(설계대로), 5XL 오출고 0.
- preset.json diff(+12/-1)는 developer 구현분(body_fill·cover_bleed dict)이며 tester는 소스 무수정(임시 _test_floatcover.json은 테스트 후 삭제 완료).

### 배번 자간 검증 (2026-06-22, 독립검증 — 코드 무수정)
검증 방법: selftest 회귀 + 좌표 정밀계산(render_glyph_number_ops 재현) + 실제 V넥 job(빈본체 디자인, L/XL) per_player PDF·preview + 출력 PDF 콘텐츠 스트림 색/연산자 분석 + 미리보기 육안.

| # | 검증 항목 | 결과 | 비고 |
|---|----------|------|------|
| 1 | selftest 회귀 | ✅ PASS | 종합 PASS, 합성 24회 무손실·inkcov 편차 0 |
| 2 | **앞 "20" pitch/잉크폭** | ✅ PASS(빠듯) | **1.1898** (기준 1.16±0.03=1.13~1.19 상한에 근접). gap=20.45pt 양수(2·0 분리) |
| 3 | 뒤 "20" 동일 비율(scale무관) | ✅ PASS | cap_h 200/400 모두 pitch/잉크폭=**1.1898** 동일. XL/L 시각도 분리 |
| 4 | 한자리 "7"·세자리 "123" | ✅ PASS | "7" 잉크중심=center 정확. "123" 각 글자 분리(gap 74.18·20.45 양수), 중앙정렬 유지, 깨짐 없음 |
| 5 | verify_output·번호 device CMYK k·금지연산자 | ✅ PASS | job verify 3/3 True. 번호 글자=`0 0 0 0 k`+`f`(preset 번호색 [0,0,0,0]=흰글자, device CMYK k fill). rg/g/RG/G/scn=0 |
| 6 | 미리보기 PNG 시각(자간 분리) | ✅ PASS | 앞·뒤 번호 붙음 없음. 경로 아래 |
| 7 | 구버전 호환(advance 없는 글리프셋 폴백) | ✅ PASS | advance 제거 시 크래시 0, width 폴백(pitch 132.99→112.54로 좁아짐). 분기 `adv None/0→width` 정상 |
| 8 | 불변 제약(시그니처 무수정) | ✅ PASS | git diff=number_glyphs.py·cli.py·json만. place_number/place_name/compose/parse_svg/verify_output 시그니처 변경 0. extract/cli만 키워드 인자 기본값 추가 |

📊 종합: 8개 항목 전부 ✅ PASS. **판정: 합격(자간 복원 정상, 회귀 0).**

스크린샷: `_glyphtest/out_L/preview/L_20_KIM.png`(앞/뒤 20), `L_07_LEE.png`(7), `L_123_PARK.png`(123), `_glyphtest/out/preview/XL_20_KIM.png`(XL 20·scale무관).

⚠️ 참고(차단 아님):
- **항목2 비율 1.1898은 허용 상한 1.19에 매우 근접**(여유 0.0002). 완성본 목표 1.16 대비 약간 넓은 쪽이며 현재 통과. 향후 advance_ratio(0.66113)를 미세 낮추면 1.16 중앙값에 더 가까워짐 — 필수 아님, 시각상 자연스러움.
- dev 보고의 번호 ops 색 "0 0 0 1 k"는 실제 출력상 "0 0 0 0 k"(preset 번호색 [0,0,0,0]=흰글자)였음(기능엔 무관, device CMYK k fill 조건 충족). 보고 표기만 정정 참고.
- "123"에서 1(잉크폭 58, 좁음)과 2 사이 간격이 advance 균일(356) 탓에 다소 넓어 보이나 분리·중앙정렬 정상.

## 기획설계 (planner-architect)

### 합성 품질 A(본체색 채움)+B(사이즈별 자동블리드) 구현 설계 (2026-06-25)

🎯 목표: 패턴선 안쪽 본체 흰틈 제거(A) + 극단소형 흰요소 재단선 미달 제거(B). 둘 다 등방→번호/이름 무왜곡.

📍 현재 함수 시그니처·흐름(실측):
- pdfutil.place_block(polygon, matrix, xobject_name)→str. 블록=`q / 폴리곤 W n / cm / Xn Do / Q`. (clip_path_ops가 폴리곤 h W n 생성)
- compose.compose(design_pdf, layouts, out_path, design_page=0, compress=True)→int. 루프: place_block→blocks, **Do 뒤 piece.extra_ops 추가**. ⚠️불변.
- Piece(outline, transform, name="", extra_ops=""). dataclass. **신규 필드는 기본값으로 추가 가능**(extra_ops 선례).
- flatten.detect_background_cmyk(pdf:pikepdf.Pdf, page_index=0)→Optional[CMYK]. **이미 존재**(면적최대 불투명 k/scn 4채널). 인자가 path 아닌 pikepdf.Pdf 객체임 주의.
- job._job_piece_transform(design_region, poly, shrink_x, shrink_y, bleed=None)→(s,0,0,s,ox,oy). bleed None/<=0=contain, >0=cover×bleed(중앙정렬). **앞판폴리곤 비율 pw/ph, 디자인영역 dw/dh 모두 이 함수 안에 있음**(B의 dev 산출 최적위치).
- job._build_precise_layout(preset, size_def, *, number,name,warnings,cutline_strokes,cover_bleed)→SizeLayout. 조각루프서 _job_piece_transform(bleed=cover_bleed) 호출, Piece 생성.
- job.run_job: flatten_transparency 1회→base_design. cover_bleed=preset.cover_bleed or cutline.bleed(단일값). 행루프서 _build_precise_layout(cover_bleed=cover_bleed).

🔗 A 해법(본체색 채움) — 연산자 주입 위치 핵심:
- **구조충돌**: 본체 fill은 클립직후·Do**앞**이어야 함. 그런데 extra_ops는 Do**뒤**라 부적합. place_block이 fill을 넣어야 하나 호출자=compose(불변).
- **회피책(채택)**: Piece에 `bg_cmyk: Optional[tuple]=None` 필드 추가(extra_ops 선례=무손실 확장, compose 시그니처 불변). place_block에 `bg_cmyk=None` 인자 추가(기본값→하위호환). compose 루프 1줄만 `place_block(..., bg_cmyk=piece.bg_cmyk)`로 전달(시그니처 불변, 동작 동일·인자만 추가=불변 위반 아님. extra_ops 추가 때와 동일 수준 변경).
- place_block 새 연산자 순서: `q / 폴리곤 W n / [bg_cmyk면: k0 k1 k2 k3 k → 폴리곤 재경로 h f] / cm / Xn Do / Q`. ⚠️클립 경로(W n)는 경로를 소비하므로 fill용 폴리곤 경로를 **다시 그려야**(W n 후 경로 비워짐) `m..l..h f`. clip은 그대로 유효(W n이 클립영역 설정).
- 본체색 감지: run_job 시작부 flatten 직후 `bg=detect_background_cmyk(pikepdf.open(base_design))` 1회(또는 preset 'body_fill' 캐시값 우선). _build_precise_layout에 bg 인자 전달→각 Piece.bg_cmyk에 셋. preset에 `body_fill:[...]` 있으면 그 값 우선(이번 디자인 0.8,0.5,0,0.1), 없으면 자동감지, 자동도 실패면 None(채움생략).
- **등방성**: fill은 클립영역=조각윤곽 안만 칠함. 디자인 Do가 그 위에 덮음→디자인 있는 곳은 디자인색, 투명(빈)영역만 본체색. 번호/이름 extra_ops는 Do 뒤라 영향 0.

🔗 B 해법(사이즈별 자동블리드) — 산출위치:
- dev·bleed 산출은 **_job_piece_transform 안**이 최적(pw/ph/dw/dh 모두 거기 있음). 단 '앞판 기준' 통일 필요(조각마다 비율 다름)→앞판 1개로 사이즈 대표 bleed 산출 후 전 조각 동일 적용.
- **채택 흐름**: _build_precise_layout서 (a)auto_bleed 켜졌으면 앞판(front) pdef의 design_region+해당 poly로 dev=|(pw/ph)/(dw/dh)-1| 계산→bleed=clamp(1.0+K*dev, lo, hi) 1회 산출 (b)그 단일 bleed를 전 조각 _job_piece_transform(bleed=)에 전달. auto_bleed 꺼졌으면 기존 cover_bleed 단일값.
- preset.cover_bleed에 `auto_bleed`옵션: `"cover_bleed":{"auto":true,"k":1.3,"min":1.0,"max":1.12}` 또는 기존 float(1.03) 둘 다 허용. run_job서 dict면 auto경로, float면 기존경로. 검증값 XL=1.0·5XS≈1.10·2XS≈1.056·M≈1.02·5XL≈1.036.
- 신규 헬퍼 `_auto_bleed(front_pdef, poly, k, lo, hi)→float` (job 내부 _ 함수, 공개API 아님).

⚠️ 불변제약 위반 가능지점·회피:
1. compose 시그니처: 무수정(루프 1줄 place_block 인자만 추가). Piece 신규필드는 기본값(extra_ops 선례 OK).
2. place_block 시그니처: 신규 bg_cmyk=None 기본값만(하위호환). 다른 호출처(grid_layout는 place_block 직접 안 부름, compose만)→영향 1곳.
3. _job_piece_transform: bleed 인자 이미 있음(추가0). auto는 호출자(_build_precise_layout)서 값만 계산해 넘김→이 함수 무수정.
4. CMYK/투명도/벡터: fill은 device k(4채널)·불투명·벡터 m/l/f→verify '투명도없음·CMYK유지' PASS. Do개수 불변(fill은 Do 아님)→배치횟수 검증 PASS.
5. 번호/이름 등방: bleed 전조각 동일 단일값·등방 s. extra_ops는 Do 뒤·조각 transform 감쌈→fill 무관.

📋 실행계획(최대7):
| 순서 | 작업 | 담당 | 선행 |
|------|------|------|------|
| 1 | pdfutil.place_block에 bg_cmyk=None 인자+fill 연산자 주입(W n 후 폴리곤 재경로 h f) | developer | 없음 |
| 2 | compose.Piece에 bg_cmyk 필드 추가 + compose 루프서 place_block에 전달 | developer | 1 |
| 3 | job.run_job서 본체색 1회 결정(preset.body_fill>자동감지>None)→_build_precise_layout에 bg 전달→Piece.bg_cmyk 셋 | developer | 2 |
| 4 | job._auto_bleed 헬퍼 + _build_precise_layout서 앞판기준 단일 bleed 산출, cover_bleed dict(auto) 파싱 | developer | 없음(3과 병렬가능) |
| 5 | preset.json: body_fill 추가, cover_bleed를 {auto,k,min,max}로 | developer | 1-4 |
| 6 | 전사이즈 verify PASS + 흰틈0 + 번호무왜곡 검증 | tester | 5 |
| 7 | 코드리뷰(불변제약·시그니처) | reviewer (6과 병렬) | 5 |

⚠️ developer 주의:
- place_block fill: W n은 경로 소비→fill용 폴리곤 `m l...h` **다시 생성** 필수. clip_path_ops 재사용 시 끝의 `W n` 대신 `h f`로 끝나는 별도 함수/문자열 만들어야.
- detect_background_cmyk 인자는 pikepdf.Pdf 객체(path 아님). run_job서 base_design을 pikepdf.open 해서 넘기고 close.
- auto_bleed dict와 기존 float 양쪽 파싱 분기(하위호환). float이면 기존 단일 cover, dict+auto:true면 앞판 dev산출.
- 앞판 dev: front pdef는 id=="front"로 찾기(_find_piece_index). poly=polys[front svg_index]. pw/ph=poly.bbox폭/높이, dw/dh=design_region폭/높이.
- 커밋 전 ast.parse/py_compile(pdfutil/compose/job.py).

📋 tester 검증항목:
- 전사이즈(5XS~5XL 12개) job verify_pass=True(투명도없음·CMYK·배치횟수).
- 본체색 fill 연산자: 출력 페이지콘텐츠에 device k(0.8 0.5 0 0.1)+f가 조각수만큼, 클립 안. 금지연산자(rg/g/RG)0.
- 흰틈0: 미리보기 PNG서 패턴선 안쪽 파란본체 빈틈 없음(특히 어깨/옆선/밴드끝).
- B 블리드값 검증: XL≈1.0, 5XS≈1.10, 2XS≈1.056, M≈1.02, 5XL≈1.036 (±0.01). 극소형 흰줄무늬가 재단선까지 닿음.
- 번호/이름 무왜곡: 등방 유지, "20"자간·중앙정렬 회귀0, 재단선 1줄.
- 하위호환: bg_cmyk 없는 Piece(U넥)·float cover_bleed 회귀0.

## 기획설계/구현/테스트/리뷰
(완료 — 상세 git 히스토리 + knowledge. 합성1 자동산출 0pt일치, 합성2+3 tester12/12·reviewer 통과 치명0)

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성(disabled_sizes)·재확보 대기 |
| (그 외 화면/드롭 6건) | — | — | ✅ 전건 완료(git 반영) |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-20 | dev/rev | 웹앱1~5(FastAPI 풀스택)+종합리뷰 | E2E 완료기준 달성·치명0 |
| 2026-06-22 | tester | 브라우저 시각검증 E2E | 버그4건 발견(both/EPS·헤더·푸터·3XL표기) |
| 2026-06-22 | dev | 화면버그 5건 수정 | tester9/9·EPS실생성·드롭동작 |
| 2026-06-22 | debugger | 실OS 파일드롭 버그(document가드+좌표) | CDP검증·클릭회귀0 |
| 2026-06-22 | dev/test | 합성1 자동매핑(build-preset+preset교정) | 자동산출=정답값 0pt(front svg1·back svg0) |
| 2026-06-22 | dev/test/rev | 합성2+3 cover/블리드+재단선1줄+OCG제거 | tester12/12·rev통과. 앞뒤정합·꽉참·재단선1줄·빨강1색만제거 |
| 2026-06-22 | pm | 합성1·2·3 커밋 | 푸시 예정 |
| 2026-06-22 | dev | 배번 자간 수정(advance 복원, 폰트비율 0.6611) | "20" pitch/잉크폭 1.17~1.19·2-0분리·selftest PASS·verify 2/2 |
| 2026-06-22 | dev | 배번 "1" lsb 보정(글자별 lsb=units×advpt/597) | '1'→64.4·'0'→33.4·'2'→30.4 폰트일치, "11"자간차0.0·"20/7"회귀0, selftest PASS·verify 4/4 |
| 2026-06-25 | planner-architect | 합성 A(본체색채움)+B(자동블리드) 구현설계 | Piece.bg_cmyk 신규필드로 place_block fill 주입(compose 불변), B는 _build_precise_layout서 앞판dev 단일bleed. 7단계 계획 |
| 2026-06-25 | dev | 합성 A(본체색채움)+B(자동블리드) 구현 | 5파일 수정(pdfutil/compose/job/preset). bg=None 하위호환·dict cover_bleed 3분기. bleed검산 XL1.0/M1.021/2XS1.056/5XS1.098/5XL1.036 설계일치. ast+pyc+스모크 통과 |
| 2026-06-25 | tester | 합성 A+B 독립검증(전사이즈12개) | 6/6 PASS 합격. verify12/12·본체색k×3·bleed기대값정확일치·번호등방·재단선1줄·selftest PASS·bg=None생략동등(바이트)·float cover회귀0. 소스무수정 |
