# 작업 스크래치패드

## 현재 작업
- **요청**: 합성 '패턴선 안쪽 흰틈' + '극단소형 흰요소(줄무늬) 재단선 미달' 동시해결. 해법 A(본체색 채움)+B(사이즈별 자동 블리드).
- **상태**: ✅ **완료·커밋**(2023837). 완료기준 4개 달성(전사이즈 흰틈0·번호무왜곡·verify12/12·cowork PNG). 미푸시 1개.
- **현재 담당**: pm

## 진행 현황 (완료 — 상세는 git 히스토리 + knowledge)
| 작업 | 내용 | 결과 |
|------|------|------|
| 출력형식 PDF/EPS/both | flatten Group제거·eps2write·verify_eps·--format | ✅ tester13/13 |
| 웹앱1~5 | FastAPI 풀스택(order/design/jobs비동기/기록/등록/설정)+run.bat | ✅ rev종합 치명0 |
| 화면버그+실OS드롭 | both/EPS·드래그앤드롭·헤더·3XL칩·푸터 / document가드+좌표 | ✅ tester9/9·debugger |
| 합성1·2·3 | 자동매핑·cover+블리드·재단선1줄(svg_polygon)·패턴선 OCG제거 | ✅ tester12/12·rev통과 |
| 배번 글리프셋 | 자간(advance 0.6611)+"1" lsb 보정 | ✅ selftest PASS·verify4/4 |
| **합성 A+B** | 본체색 채움(Piece.bg_cmyk)+사이즈별 자동블리드(auto_bleed) | ✅ tester6/6·rev통과 치명0 |

## 백로그 (차단 아님, 후속)
- **[U넥 자산]** 농구_U넥_양면 design_XL.ai가 .gitignore 자산이라 로컬 부재 → A+B 후 full job 시각회귀 미실시(코드 동등성으로 하위호환 본질만 검증). 자산 확보 시 권장.
- **[합성 일반화]** hide_design_cutline_layer(OCG 콘텐츠삭제)는 V넥 BDC구조·레이어명("패턴선")·page0 한정 → 신규 디자인 온보딩 시 재확인 체크리스트. 재단선 보존체크 n_out>=expected라 '과다(두줄)' 못 거름(시각검증 보완).
- **[웹앱]** 업로드 확장자/용량 검증 + data/uploads·_JOBS·_design_no_cutline TTL 정리(디스크/메모리 누적). progress 콜백.
- **[디자이너 입력 대기]** 재단선 PDF포함 .ai 재출력 / 올바른 3XL.ai 재확보(현 disabled).
- **[job.py:732 주의]** _auto_bleed 직전 `polys[front svg_index]` 범위가드 부재(행 try/except엔 잡힘, 비치명). 자산결함 시 보강 가능.
- cowork 최종 오버레이 검증(번호글리프셋·밴드·재단선·본체·합성). band design_region 정밀재추출.

## 불변 제약 (영구)
engine 공개 API(compose/Piece/SizeLayout/parse_svg/scale_translate/verify_output)+build_layouts/grade/run_job/parse_order/flatten/eps **시그니처·동작 무수정**(신규 인자 기본값만). device CMYK 무손실. 글자 k fill만. 빌드0(웹앱도 정적 그대로). 폴더+JSON(DB없음). CLI/curl 단독검증. GS 미설치 시 PDF fallback. _handoff 원본 무수정(webapp/static 복사본만). 커밋 전 ast.parse/py_compile.

## 확정 사실 (영구 참고)
- 좌표정합=방식A(앵커 bottom-left). grade `_piece_transform`(job `_job_piece_transform` 복제).
- **합성(job)**: contain→**cover**(s=max(pw/dw,ph/dh)*shrink*bleed)+중앙정렬, **cover_bleed preset 키 있을때만**(없으면 contain=U넥 회귀0). clip이 넘침 차단.
- **사이즈별 자동 블리드**: preset cover_bleed가 `{auto:true,k:1.3,min:1.0,max:1.12}` dict면 _build_precise_layout이 앞판 기준 `dev=|(pw/ph)/(dw/dh)-1|`, `bleed=clamp(1+k·dev,lo,hi)` 단일값 산출→전 조각 등방 적용(번호/이름 무왜곡). float이면 기존 단일. None이면 contain. XL=1.0·M=1.021·2XS=1.056·5XS=1.098·5XL=1.036.
- **본체색 채움(흰틈 제거)**: Piece.bg_cmyk(기본 None) 있으면 place_block이 클립(`W n`)직후·`Do`앞 폴리곤 **재경로** 후 device k+f로 채움(⚠️W n이 경로 소비→fill용 재경로 필수, errors.md). run_job이 본체색 1회 결정: preset.body_fill(이번값[0.8,0.5,0,0.1]) > detect_background_cmyk(pikepdf.Pdf객체) > None. 디자인이 위를 덮어 빈 곳만 본체색=등방.
- **재단선**: 조각 SVG poly.points(=clip outline 동일좌표·너치 포함)를 시트좌표 그대로 빨강 1회 stroke(device K 0,0.96,0.95,0, 2.0pt). cutline.draw_from="svg_polygon". transform 안 감쌈.
- **디자인 패턴선 두 줄 방지**: OCG D.OFF는 Form 합성에 무효 → 콘텐츠 /OC /MCx BDC…EMC 구간 삭제(깊이카운트 짝맞춤, 빨강1색만 제거·5색 무손실). hide_design_cutline_layer=true.
- **조각 자동매핑(build-preset)**: 디자인 OCG "패턴선"(/MC3) 닫힌서브패스 bbox=조각 design_region. SVG 넥깊이로 앞(V넥깊은=svg1)/뒤(라운드=svg0)/밴드(높이최소=svg2) 매칭.
- 글자주입: text place_*(잉크 bbox 중앙정렬, 디자인좌표)→조각 transform 감싸 extra_ops(클립 밖, Do 뒤). 번호: glyph_source 있으면 글리프셋(advance 0.6611·글자별 lsb), 없으면 HY헤드라인.
- **디자인 본체**: .ai "PDF 호환 저장" 켜야 본체 PDF 포함(아니면 3.4KB 흰화면). 정상 빈본체=88KB.
- **출력형식**: flatten Form투명도그룹 제거(EPS 래스터화 트리거)·페이지그룹 /CS 보존. eps2write. EPS 305KB 벡터.
- **V넥**: 암홀X 3조각 front=svg1/back=svg0/band=svg2. 12사이즈(3XL disabled, disabled_sizes는 sizes 밖).
- ⚠️ 변환함정(errors.md): 조각수+verify만으론 부족→viewBox통일·양수·미리보기 육안. 인접사이즈 좌표동일=자산결함. 브라우저 드롭은 document가드+좌표판정.

## 핵심 모듈 / 웹앱
- engine: text·number_glyphs·reference(+build_pieces_preset/extract_design_pieces)·job(정밀배치+cover/auto_bleed+본체색채움+재단선polygon+OCG제거+disabled+out_format)·svg_normalize·order(①②③STIZ)·flatten(+Group제거+detect_background_cmyk)·eps·compose(+Piece.bg_cmyk)·pdfutil(place_block+bg_cmyk fill)·verify·preview·grade.
- CLI: grade/job/reference/build-preset/normalize-svg/number-glyphs/flatten/order/selftest. --format pdf|eps|both.
- webapp/: main·api(health/patterns/settings·order/parse·design/check5·jobs비동기+progress+preview+zip·기록·등록)·state·run.py·run.bat. webapp/static=_handoff/grader-v2-static 복사본(원본 보존, 갱신시 재복사).
- 데이터: data/patterns/{농구_U넥_양면, 농구_V넥_양면(SVG12+preset+number_glyphs.json)}. data/{jobs,uploads}/·settings.json(.gitignore).

## 실데이터 / git
- design_source/(.gitignore *.ai): 연세대_V넥_빈템플릿_본체포함_XL.ai(88KB base)·_숫자글리프셋_아트보드2.ai·_완성본_본체포함_XL.ai.
- 주문서: C:/Users/user/Desktop/새 폴더/260213_…추가주문서.xlsx. 폰트 data/fonts/HY헤드라인M.ttf. GS C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe.
- 테스트 산출물 `_abtest/`는 .gitignore 대상 아님(커밋 제외 주의). cowork PNG: _abtest/out_allsize/preview/{5XS,XL,M,5XL}_20_*.png.
- git: origin=cobby8/grader-v2, main. **미푸시 1개**(합성 A+B).

## 구현/테스트/리뷰/기획설계
(완료 — 상세 git 히스토리 + knowledge. A+B: tester6/6 PASS·reviewer 통과 치명0, bleed 검산 cowork값 정확일치)

## 수정 요청
| 요청자 | 대상 | 문제 | 상태 |
|--------|------|------|------|
| reviewer/tester | 3XL.ai | 원본이 5XL과 동일(자산결함) | 비활성(disabled_sizes)·재확보 대기 |

## 작업 로그 (최근 10건)
| 날짜 | 에이전트 | 작업 | 결과 |
|------|---------|------|------|
| 2026-06-22 | debugger | 실OS 파일드롭 버그(document가드+좌표) | CDP검증·클릭회귀0 |
| 2026-06-22 | dev/test | 합성1 자동매핑(build-preset+preset교정) | 자동산출=정답값 0pt |
| 2026-06-22 | dev/test/rev | 합성2+3 cover/블리드+재단선1줄+OCG제거 | tester12/12·rev통과 |
| 2026-06-22 | dev | 배번 자간 수정(advance 0.6611 복원) | "20" 2-0분리·selftest PASS·verify2/2 |
| 2026-06-22 | dev | 배번 "1" lsb 보정(글자별 lsb) | 폰트일치·"11"자간차0.0·verify4/4 |
| 2026-06-25 | planner-architect | 합성 A+B 구현설계 | Piece.bg_cmyk fill(compose불변)+앞판dev 단일bleed. 7단계 |
| 2026-06-25 | dev | 합성 A+B 구현(5파일) | bg=None 하위호환·dict cover 3분기·bleed검산 설계일치·ast+pyc+스모크 통과 |
| 2026-06-25 | tester | 합성 A+B 독립검증(전사이즈12) | 6/6 PASS·verify12/12·본체색k×3·bleed정확일치·번호등방·bg=None바이트동등 |
| 2026-06-25 | reviewer | 합성 A+B 코드리뷰 | 통과 치명0(A재경로정확·불변준수·3분기안전). 주의1: job.py:732 svg_index가드 |
| 2026-06-25 | pm | 합성 A+B 커밋(2023837)+knowledge기록(decisions/errors)+scratchpad정리 | 미푸시1 |
