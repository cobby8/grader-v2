# 작업 스크래치패드

## 현재 작업
- **요청**: 디자인→조각 합성 품질 근본수정(자동매핑·cover채움·재단선1줄). 의뢰서: 조각자동매핑-레이어기반.
- **상태**: ✅ **합성1·2·3 전부 완료·커밋** (미푸시 ~11개 — 푸시 예정). 의뢰서 완료기준 4개 달성(앞뒤정합·꽉참·재단선1줄·시각PASS).
- **현재 담당**: pm

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
| 2026-06-20 | dev/test/rev | 출력형식 PDF/EPS/both | tester13/13·EPS305KB벡터 |
| 2026-06-20 | dev/rev | 웹앱1~5(FastAPI 풀스택)+종합리뷰 | E2E 완료기준 달성·치명0 |
| 2026-06-22 | tester | 브라우저 시각검증 E2E | 버그4건 발견(both/EPS·헤더·푸터·3XL표기) |
| 2026-06-22 | dev | 화면버그 5건 수정 | tester9/9·EPS실생성·드롭동작 |
| 2026-06-22 | debugger | 실OS 파일드롭 버그(document가드+좌표) | CDP검증·클릭회귀0 |
| 2026-06-22 | dev/test | 합성1 자동매핑(build-preset+preset교정) | 자동산출=정답값 0pt(front svg1·back svg0) |
| 2026-06-22 | dev/test/rev | 합성2+3 cover/블리드+재단선1줄+OCG제거 | tester12/12·rev통과. 앞뒤정합·꽉참·재단선1줄·빨강1색만제거 |
| 2026-06-22 | pm | 합성1·2·3 커밋 | 푸시 예정 |
