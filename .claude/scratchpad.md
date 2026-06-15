# 작업 스크래치패드

## 현재 작업
- **요청**: 코워크가 구현한 engine/ 환경 세팅 + 이 PC(한글 Win, Py3.11)에서 동작 검증
- **상태**: 진행 중 (인코딩 버그 수정 → 재검증 → requirements.txt → git 초기화)
- **현재 담당**: debugger(cli 인코딩 수정) + developer(requirements.txt) 병렬
- **확인된 사실**:
  - PoC(6/10) 통과 완료, engine/ 8개 모듈 구현됨(6/15 코워크, Py3.10 환경)
  - 이 PC엔 pikepdf/PyMuPDF 미설치였음 → PM이 설치(pikepdf 10.8.0, PyMuPDF 1.27.2.3)
  - selftest는 UTF-8 모드(PYTHONUTF8=1)에서 전부 PASS (inkcov 편차 0.000000)
  - 버그: 한글 Win 기본 콘솔(cp949)에서 '—'(U+2014) 출력 시 UnicodeEncodeError로 크래시
  - git 미초기화, requirements.txt 없음

## 기획설계 (planner-architect)
- **산출물**: `C:\0. Programing\grader-v2\grader-v2-타당성검토보고서.md` (8개 섹션, 일차 출처 기반 웹리서치 + 유사 솔루션 비교)
- **종합 판정**: 조건부 GO. "충분히 실현 가능, 단 벡터 CMYK EPS 출력 품질이 성패의 80%를 좌우하는 단일 핵심 관건."
- **구현 가능성 높음**: FastAPI/pikepdf/fontTools/PyMuPDF/openpyxl/ezdxf 모두 실존·적합·바이브코딩 친화. pikepdf 합성(Form XObject)은 무손실 벡터 보존으로 가장 안전.
- **최대 리스크(설계 과소평가)**: Ghostscript eps2write — 투명도 1%라도 있으면 페이지 전체 래스터화(공식문서 확인), ICC 색 보존 불가, "속 구조 재조립". 설계의 투명도 스캔 안전장치는 옳으나 "경고 후 진행"은 약함 → 차단/자동평탄화 권고.
- **설계 누락 리스크**: ① 원단 수축(shrink) 보정 ② 색관리(ICC/PMS) 전략 ③ 폰트 아웃라인 라이선스 ④ EPS RIP 호환성 미검증 ⑤ 동시성 원자적 쓰기.
- **최선 개선안**: "공장이 EPS만 받는가, PDF도 되는가?" 확인 → PDF 허용 시 EPS의 투명도·색 한계 대부분 해소(EPS는 투명도 미지원 구포맷).
- **검증된 방향**: VPersonalize가 동일 원리(엑셀 로스터→단일 디자인→사이즈 그레이딩→네스팅→벡터 CMYK 출력→RIP 연동)로 상용화 성공 → 옳은 길.
- **핵심 성공조건 3**: ①출력포맷 확정 ②Phase1 공장 시험인쇄 승인 절대 생략 금지(미리보기 PNG통과≠RIP통과) ③입력 SOP 표준화(device CMYK 통일+평탄화+라이선스폰트+수축보정).
- **비고**: 본 작업은 분석/문서만 수행, 소스코드 미작성.

### [PDF전환/코워크지시] 2026-06-10
- **결정 변경**: 출력 포맷 EPS→PDF 확정. 설계서 eps.py(Ghostscript eps2write) 폐기. 투명도 래스터화·ICC색 변형 리스크 대부분 해소.
- **절대 조건 2개**: ①CMYK 완전 보존(device CMYK 그대로 통과, RGB/ICC 변환 금지) ②파일 경량(Form XObject로 디자인 1회만 임베드 후 N×M 참조).
- **산출물**: `코워크-전달-PoC지시.md`(프로젝트 루트). 코워크에 그대로 붙여넣는 자기완결 PoC 지시서.
- **PoC 통과기준**: AC-1 CMYK 보존(pikepdf 색값 추출 비교 + gs inkcov 교차검증), AC-2 경량(임베드 횟수=1, 배치 증가에도 선형 소량 증가), AC-3 합성정확(W n 클리핑+cm 스케일+벡터 유지).
- **범위 밖 명시**: 웹UI·주문서·배번·실패턴파싱·수축보정·PMS·EPS 전부 제외. 조각 윤곽은 하드코딩 좌표로 충분.

## 구현 기록 (developer)
- requirements.txt 생성 (pikepdf==10.8.0, PyMuPDF==1.27.2.3) — engine/ 전수조사 결과 실제 import는 pikepdf+fitz(PyMuPDF) 둘뿐, 나머지는 표준 라이브러리. 설치 버전 pip show로 일치 확인. (기존 Phase3/4 예정 패키지 목록은 현 시점 미사용이라 실제 의존성으로 교체)

### 수정 이력
| 회차 | 수정 내용 | 수정 파일 | 비고 |
|------|----------|----------|------|
| 1차 | cp949 콘솔 UnicodeEncodeError 수정. `_force_utf8_console()` 헬퍼 추가(stdout/stderr를 UTF-8로 reconfigure, 미지원 시 안전 무시) + main() 첫 줄에서 호출. `import sys`는 기존 존재(추가 불필요). PDF/색 보존 로직 미변경 | engine/cli.py (헬퍼 121~130줄, main() 호출 132줄) | 원래 요청 / 검증: cp949(chcp 949)·PYTHONUTF8 없이 `python -m engine selftest` 크래시 없이 `selftest 종합: PASS` 확인 |

## 테스트 결과 (tester)
(아직 없음)

## 리뷰 결과 (reviewer)
(아직 없음)

## 수정 요청
| 요청자 | 대상 파일 | 문제 설명 | 상태 |
|--------|----------|----------|------|
| pm/검증 | engine/cli.py (또는 진입점) | 한글 Win cp949 콘솔에서 '—'(U+2014) 등 비-cp949 문자 print 시 UnicodeEncodeError 크래시. stdout/stderr UTF-8 고정 필요 | 완료 |

## 작업 로그 (최근 10건만 유지)
| 날짜 | 에이전트 | 작업 내용 | 결과 |
|------|---------|----------|------|
| 2026-06-10 | pm | 지식 시스템 초기화, scratchpad 생성 | 완료 |
| 2026-06-10 | planner-architect | DESIGN.md 타당성 검토 보고서 작성(웹리서치+유사솔루션 비교) | 완료 (조건부 GO) |
