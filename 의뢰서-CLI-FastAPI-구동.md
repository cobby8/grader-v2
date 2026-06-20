# 의뢰서 (CLI/Claude Code 용) — FastAPI 백엔드 + 정적 화면 연결 (실제 구동)

> 작성: 2026-06-20
> 목표: 디자인 클로드의 **정적 핸드오프 화면**(`_handoff/grader-v2-static/`)을 FastAPI로 서빙하고,
> 그 화면의 동작을 **엔진 함수**(run_job/parse_order/flatten/verify/preview)에 연결해 **진짜 동작하는
> 사내 웹 도구**로 만든다. 직원이 브라우저에서 패턴 선택→디자인→주문서→생성→검수→ZIP 까지 끝낸다.
> 선행: `의뢰서-CLI-출력형식-PDF-EPS.md`(EPS·형식선택), `의뢰서-디자인-시안보강.md`(화면 사양).

---

## 0. 원칙
- **엔진 공개 API 무수정**(compose/verify_output/parse_order/run_job/flatten 등 그대로 호출).
- **빌드 0**: 정적 HTML/CSS/JS 그대로 서빙(번들러 없음). FastAPI 는 정적 서빙 + JSON API 만.
- 상태 저장 = **폴더 + JSON**(기존 `data/jobs/<날짜_주문명>/job.json` 규약 유지). DB 없음.
- 각 엔드포인트는 **CLI/HTTP 로 단독 검증** 가능해야 함(curl 한 줄).
- 비개발자 직원 대상: 에러는 한국어로 "원인 + 다음 행동" 친절하게.

## 1. 구조
```
engine/            (기존 — 무수정)
webapp/            (신규)
  main.py          FastAPI 앱: 정적 마운트 + /api 라우터
  api.py           엔드포인트 핸들러(엔진 호출 얇은 래퍼)
  state.py         업로드/작업 임시 저장·세션(파일+JSON)
  static/          ← _handoff/grader-v2-static/ 내용(screens·tokens·assets) 복사/심볼릭
run.bat / run.py   uvicorn 기동(직원용 더블클릭)
```
정적 화면의 목 데이터(`data.js`/localStorage)를 **실제 /api 호출로 교체**. 화면 마크업·토큰은 유지.

## 2. API 엔드포인트 ↔ 엔진 매핑 (핵심)
| 메서드·경로 | 화면 동작 | 엔진/처리 |
|------------|----------|-----------|
| `GET /` , `GET /static/*` | 화면 로드 | 정적 서빙(screens/tokens/assets) |
| `GET /api/patterns` | 패턴 선택·관리 목록 | `data/patterns/*/preset.json` 스캔(이름·사이즈·조각수·glyphset 유무) |
| `POST /api/patterns` | 패턴 등록 | 사이즈별 패턴(.ai/svg) 저장 + AI→SVG 변환 + **글리프셋 추출**(number_glyphs) + **완성본 자동추출**(reference: 배번/이름 area) → preset.json 생성 |
| `POST /api/design/check` | 디자인 업로드 점검(5케이스) | §3 — header/본체/투명도/baked 검증 + 필요시 flatten |
| `POST /api/order/parse` | 주문서 추출 표 | `order.parse_order(xlsx)` → rows[{name,number,size,qty}] + 경고 |
| `POST /api/jobs` | 생성 | `run_job(preset, design, rows, out_dir, out_format)` → job_id, outputs[], summary(skip 포함) |
| `GET /api/jobs/{id}/progress` | 생성 진행바 | 진행률(완료/전체) — 백그라운드 작업 상태 |
| `GET /api/jobs/{id}` | 검수 그리드·검증 | job.json(outputs: 미리보기 경로·checks·verify·skip) |
| `GET /api/jobs/{id}/preview/{file}` | 미리보기 PNG | `preview.render_page` 산출 PNG 서빙 |
| `GET /api/jobs/{id}/zip?format=` | ZIP 다운로드 | 선택 형식 묶기(둘 다면 pdf/·eps/ 하위폴더) |
| `GET /api/jobs` | 작업 기록 | `data/jobs/*/job.json` 목록 |
| `GET/PUT /api/settings` | 설정 | 경로·출력형식·GS경로·색 메모(설정 JSON) |

## 3. 디자인 업로드 점검 — 5케이스 (시안 §1·2 대응)
`POST /api/design/check` 가 업로드 파일을 받아 아래로 분기(엔진 로직 재사용):
1. **PostScript(거부)**: 헤더 첫 바이트가 `%!PS-Adobe` → fail "PDF 호환 형식 아님"(기존 헤더검사 규약).
2. **본체 누락(차단)**: `%PDF` 인데 **페이지 콘텐츠/디자인 콘텐츠 바이트가 임계 미만**(예: <10KB,
   실측 정상 88KB·결함 3.4KB) → fail "본체가 PDF에 안 들어감 — PDF 호환 저장". (pikepdf 로 콘텐츠 크기 측정)
3. **투명도**: `verify.scan_transparency` 로 ca<1/SMask 발견 → **자동 flatten 시도**(`flatten_transparency`).
   평탄화 성공 시 pass(+"평탄화 적용됨"), SMask/비-Normal 등 불가 시 fail "원본 평탄화 필요".
4. **베이크(경고)**: 번호/이름 area 에 live text(Tj) 또는 큰 흰색 채움 감지 → warn "빈 본체를 올려주세요"
   (완성본은 패턴 등록 기준용). 진행은 허용/차단은 정책 선택(시안은 경고).
5. **정상(pass)**: 위 모두 통과 → "본체 포함 · 투명도 없음 · 빈 본체 확인" + 다음 단계 허용.
반환: `{status: pass|warn|fail, checks:[{name,ok,detail}], message, flattened: bool}`.

## 4. 생성(run_job) — 비동기 + 형식
- 큰 주문은 시간이 걸리므로 **백그라운드 실행**(BackgroundTasks 또는 thread) + `/progress` 폴링.
- `out_format` = pdf|eps|both (화면 세그먼트/설정값). EPS 는 `의뢰서-CLI-출력형식-PDF-EPS.md` 구현 선행.
- 결과·검증·skip 은 job.json 그대로 사용(화면이 그걸 읽음). 미리보기 PNG 는 검수 그리드에 서빙.

## 5. 패키징·배포(직원 PC)
- **uvicorn** 단일 기동: `run.bat`(파이썬 venv 활성→`uvicorn webapp.main:app --port 8000`). 더블클릭 실행.
- 브라우저 `localhost:8000` 자동 오픈(webbrowser.open).
- 의존성: 기존 requirements + `fastapi`,`uvicorn`,`python-multipart`(업로드). GS 는 EPS용(동봉/경로설정).
- (후순위) 단일 exe(pyinstaller) 또는 구버전 grader 식 자동업데이트 — 1차는 폴더 배포로 충분.
- 사이드바 "서버 연결됨 :8000" 표시는 실제 헬스체크(`GET /api/health`)로.

## 6. 단계별 진행(권장 순서)
1. FastAPI 뼈대 + 정적 서빙 + `/api/health`·`/api/patterns`·`/api/settings`(읽기) — 화면 뜨고 패턴 목록 실연결.
2. `/api/order/parse` + `/api/design/check`(5케이스) — 작업 1~3단계 실동작.
3. `/api/jobs`(run_job, 비동기) + `/progress` + `/preview` + `/zip` — 생성·검수·다운로드.
4. `/api/jobs`(기록) + 패턴 등록(`POST /api/patterns`) + 설정 저장(PUT).
5. 패키징(run.bat) + 직원 E2E 1회.

## 7. 불변 제약 / 완료 기준
- 제약: 엔진 공개 API 무수정, 빌드0, 폴더+JSON 저장, CMYK 무손실, 각 API curl 단독검증.
- 완료: 브라우저에서 **패턴 선택→빈본체 업로드(5케이스 점검)→주문서 추출→생성(형식 선택)→검수(검증·
  미리보기·skip)→ZIP** 까지 실데이터로 끝까지 동작. 산출물 1건 cowork 최종 시각검증.

## 8. 참고 파일
- 정적 화면: `_handoff/grader-v2-static/`(screens·tokens·assets)
- 엔진: engine/(job·order·flatten·verify·preview·reference·number_glyphs·text·grade)
- 연계 의뢰서: 출력형식-PDF-EPS, 디자인-시안보강
