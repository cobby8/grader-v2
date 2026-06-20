# 의뢰서 (CLI/Claude Code 용) — 출력 형식 선택 (PDF / EPS / 둘 다)

> 작성: 2026-06-20 (cowork 실증 결과 인계)
> 대상: `C:\0. Programing\grader-v2` engine. 현재 산출물은 PDF(+미리보기 PNG).
> 목표: 사용자가 **PDF / EPS / 둘 다** 중 필요한 형식으로 출력하도록 한다.
> 핵심: EPS 변환 시 **투명도 그룹 잔여로 통째 래스터화되는 버그**가 있다 — 아래 1번이 그 해결.

---

## 0. cowork 실증 요약 (그대로 신뢰)
실주문 산출 PDF(`260620_연세대V넥_빈본체/output/XL_11_장혁준.pdf`)를 Ghostscript eps2write 로
변환해 본 결과:
- **그냥 변환 → EPS 14.98MB, 벡터 경로 0개, 이미지화(래스터)** ← 깨짐.
- 원인: 출력 PDF에 알파(ca/CA)는 평탄화됐으나 **페이지+디자인 Form 에 `/Group /Transparency`
  (투명도 그룹) 속성이 남아** 있어 GS가 페이지 전체를 래스터화함.
- **`/Group` 제거 후 변환 → EPS 306KB, 벡터 경로 5,108개, CMYK 유지** ← 정상 벡터.
- GS 버전 9.55 동작 확인. 클립·아웃라인 글자·번호 글리프셋·재단선·CMYK 전부 벡터 보존.

---

## 1. flatten 보강 — 투명도 그룹(`/Group`) 제거 (EPS 벡터화의 핵심)
**왜**: 알파만 1.0으로 바꿔도 `/Group /Transparency` 가 남으면 EPS가 래스터화된다. 실제 투명도가
없으므로(=ca/CA 전부 1.0) 이 그룹 속성은 제거해도 시각·색 변화가 없다(PDF 렌더 동일).
**요청**: `engine/flatten.py` 의 평탄화 마지막에 **페이지 + 모든 Form XObject 의 `/Group` 제거**.
```python
# flatten_transparency() 안, 알파를 1.0으로 바꾸고 엠블럼 합성한 '뒤':
for page in pdf.pages:
    if "/Group" in page.obj:
        del page.obj["/Group"]
for obj in pdf.objects:
    try:
        if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == pikepdf.Name("/Form") \
           and "/Group" in obj:
            del obj["/Group"]
    except Exception:
        pass
```
**주의**: SMask/실제 알파가 남아있는데 Group만 지우면 결과가 달라질 수 있으니, **모든 ca/CA=1·
SMask 없음을 먼저 보장한 뒤**에만 Group 제거(이미 flatten 이 그 일을 함). flatten 리포트에
`groups_removed` 카운트 추가.
**검증**: flatten 후 PDF 렌더(픽셀 동일) + 그 PDF를 eps2write 변환 → 벡터(이미지 0·크기 급감)인지
자동 확인. (verify 에 항목 추가는 3번.)

## 2. EPS 출력 단계 — Ghostscript eps2write
**요청**: `engine/eps.py`(신규) 또는 compose 옆에 EPS 변환 함수 추가.
```
gs -dNOPAUSE -dBATCH -dSAFER -sDEVICE=eps2write -dEPSCrop -o <out.eps> <flattened.pdf>
```
- 입력은 **flatten + Group제거된 PDF**(=현재 job 이 compose 하는 그 PDF). 그걸 eps2write 로 변환.
- **GS 탐색**: Windows `gswin64c`(설치/동봉) → 없으면 `gs`. 둘 다 없으면 **EPS 건너뛰고 경고 +
  PDF 만 산출**(graceful fallback). GS 경로는 설정(settings)에서 지정 가능하게.
- 배포: GS 동봉 또는 설치 가이드(AGPL, 사내용 OK). 버전 권장 9.55+.

## 3. EPS 검증 — verify_output 은 PDF 전용이라 별도 체크
**왜**: `verify_output` 은 "디자인 Form 바이트 동일" 등 PDF 구조 기준이라 EPS(평탄 합성)엔 못 씀.
**요청**: `verify_eps(eps_path)`(신규) — PoC 방식 재사용:
- **벡터 여부**: 파일 크기 임계(예: 페이지당 수 MB↑면 래스터 의심) + `/Image`/`colorimage`/`/ImageType`
  과다 여부 + 벡터 연산자(`l`/`c`/`m`) 존재. 래스터화 감지 시 FAIL(=Group제거 누락 신호).
- **CMYK**: `setcmykcolor`/`DeviceCMYK`/`k` 존재(색공간 보존).
- **BoundingBox**: `%%BoundingBox` 가 시트 크기와 일치(0 0 W H).
- 결과를 job.json outputs[].checks_eps 에 담음.

## 4. 형식 선택 — PDF / EPS / 둘 다 (사용자 선택)
**요청**: `run_job(..., out_format="pdf")` 인자 추가(기본 "pdf"). 값: `"pdf" | "eps" | "both"`.
- per_player/single 양쪽에서 동작. compose 로 PDF 생성(공통) → 형식에 따라:
  - `pdf`: PDF 만.
  - `eps`: PDF(중간) → eps2write → EPS 만 최종(중간 PDF 는 임시/삭제 선택).
  - `both`: PDF + EPS 둘 다.
- **폴더 구조**: `out_dir/output/pdf/…pdf`, `out_dir/output/eps/…eps`(둘 다일 때 분리). 한 형식만이면
  `output/` 바로 아래도 무방(일관성 위해 하위폴더 권장).
- CLI: `python -m engine job … --format pdf|eps|both`. 미지정 시 preset/settings 기본값.
- 검수/요약: job.json summary 에 `format`, 형식별 produced/verify 집계.
- ZIP(앱 단): 선택 형식만 묶기(둘 다면 pdf/·eps/ 하위폴더 포함).

## 5. preset / settings 연동
- settings(또는 preset)에 `output.format` 기본값(pdf|eps|both) + `ghostscript_path`.
- 작업 흐름에서 주문별로 형식 덮어쓰기 가능(run_job 인자가 최종 우선).

---

## 6. 불변 제약 (유지)
engine 공개 API(compose/verify_output 등) 무수정. flatten 의 Group 제거는 **알파=1 보장 후에만**.
device CMYK 무손실. GS 미설치 시 PDF fallback(앱이 죽지 않게). 좌표·색·경로 preset/설정값.

## 7. 완료 기준
1) flatten 후 PDF→eps2write 가 **벡터 EPS**(이미지 없음·크기 정상·CMYK 유지). (XL_11 기준 ~300KB대)
2) `python -m engine job … --format both` → output/pdf, output/eps 양쪽 생성, 각각 검증 PASS.
3) GS 없는 환경에서 `--format eps`/`both` → 경고 + PDF 산출(앱 정상).
4) 산출 PDF·EPS 1쌍을 cowork 로 보내 시각/벡터 최종 확인.

## 8. 참고
- 실증 명령·수치는 §0. GS 9.55 사용. flatten Group 제거 전/후 = 14.98MB(래스터) → 306KB(벡터).
- 디자인 시안 쪽 형식 선택 UI 는 `의뢰서-디자인-시안보강.md` §6 에 반영됨(PDF/EPS/둘 다 + 주문별 선택).
