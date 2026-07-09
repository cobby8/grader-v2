# 프로젝트 지식 목차

## 파일별 요약
| 파일 | 항목 수 | 최종 업데이트 |
|------|--------|------------|
| architecture.md | 9 | 2026-07-09 |
| errors.md | 15 | 2026-07-07 |
| conventions.md | 5 | 2026-07-06 |
| decisions.md | 17 | 2026-07-09 |
| lessons.md | 1 | 2026-06-15 |

## 최근 추가된 지식 (최근 5건)
- [2026-07-09] decisions+architecture: [Phase B] 등록패턴 파일 영속화 — Render 임시디스크 재배포 시 소실되는 data/patterns/{id}/를 Supabase Storage에 zip 백업/복원. 핵심=SERVICE_ROLE 없이 **요청자 admin JWT를 백엔드가 Storage REST에 릴레이**(등록=admin_required라 헤더에 admin 토큰). 등록직후 자동백업+startup 자동복원(로컬없는것만, zip-slip 방어). 버킷 pattern-presets(private)+RLS(읽기 anon개방·쓰기 admin). 1·2단계 구현·커밋(storage_backup.py 모듈+SQL가이드), 3·4단계(api/main 결선) 대기
- [2026-07-07] decisions: 패턴 폴더 자동 스캔 — 재귀 대신 전폴더+전파일 각 1쿼리로 훑어 폴더맵 조립·부모별 그룹핑·사이즈파서로 패턴폴더 선별. GET /drive/scan(TTL캐시·루트스코프·경로 breadcrumb). 스캔=발견전용, 등록은 기존 정확경로(/patternfiles·/from-drive) 재사용→근사오차 무오염. 프론트 [자동찾기|트리] 탭+카드그리드, renderDrivePreview panel 인자화+activeDrivePanel로 입력칸 중복방어. Drive `name contains`는 prefix매칭이라 누락위험→전파일 fetch+endswith
- [2026-07-06] errors: Drive 동시호출 SSL record layer failure — google-api-python-client httplib2는 스레드 비세이프. 전역 service를 FastAPI 스레드풀이 공유→동시 execute 충돌. 해결=스레드로컬 service + 전송에러 리셋 재시도(HttpError 제외). 재시도 래퍼로 감쌀 함수는 config검증(DriveConfigError)을 try 밖 선호출로 분리해 에러계층 보존
- [2026-07-06] architecture+convention: Drive 연동 완결(백엔드 gdrive.py+api.py 3엔드포인트+patterns.html #driveMode). 등록은 _DriveUpload 어댑터로 기존 create_pattern 재사용(중복구현 금지). 사이즈파서 _SIZE_TOKENS 정확토큰일치. **프론트 사이즈 정렬은 문자열 정렬 금지→순서표 인덱스**(2XL/XL 오탐). _handoff 비대칭에 drive JS 추가(재복사 시 소실 주의, 참조+1)
- [2026-07-06] decisions: Drive연동 Phase2(프론트) — 독립 #driveMode 채택(from-drive 원샷 서버호출·현 savePattern이 subB/C 매핑 미전송=자동매핑이라 폴더선택+이름만으로 완결). 카드 glyphset배지는 GET /api/patterns의 glyph_source(bool)로 프론트만. 카드클릭→sessionStorage `grader_selected_pattern`+work.html 프리셀렉트. admin 403/미설정 configured:false는 동일 빈상태 톤. 엔진/인증/등록흐름 무수정
- [2026-06-29] errors: 배포본 404 디버깅 — 404 본문이 "Cannot GET"(Express)이면 우리 FastAPI 앱 아님(이름선점 타인 앱). 코드 의심 전 ①응답 서버시그니처 ②대시보드 실제 URL(해시 suffix) ③서비스 존재여부 확인. health 200 하나로 단정 금지
- [2026-06-26] decisions/errors: 배포 Phase1 갱신 — 인증을 JWT secret 로컬검증→Supabase 토큰 introspection(httpx GET /auth/v1/user, apikey=PUBLISHABLE, timeout5, 60초캐시)으로 교체. admin_required(role!=admin→403)는 POST patterns·PUT settings에만. env PUBLISHABLE/SECRET. 프런트 함정: 루트가 앱화면 직행하면 미인증 우회→루트는 login으로+클라 세션판정+apiFetch 401가드(토큰clear). login 404는 StaticFiles 마운트/복사부터
- [2026-06-25] decisions: 배포 Phase1 설계 — Docker+Render+Supabase Auth. GS_BIN env를 eps.find_ghostscript 1순위(로컬 폴백 보존), 인증 Dependency는 /api/health만 제외, 공통 apiFetch 래퍼로 Authorization 부착+401 리다이렉트, _handoff 원본→webapp/static 복사. 엔진/run.bat 무수정·비밀키 레포금지·--workers 1 유지
- [2026-06-25] decisions/errors: 합성 흰틈/극소형미달 해소 — A 본체색 채움(Piece.bg_cmyk, run_job이 preset.body_fill>detect_background_cmyk>None 1회 결정, place_block이 클립 W n직후·Do앞 fill) + B 사이즈별 자동블리드(cover_bleed dict면 앞판 dev로 clamp(1+1.3dev,1.0,1.12) 단일값 등방). 함정: PDF `W n`은 경로 소비→클립영역 fill하려면 폴리곤 재경로 필수
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
