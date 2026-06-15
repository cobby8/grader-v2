# engine — grader-v2 출력 엔진 (Phase 1 코어)

웹과 완전히 분리된 순수 Python 모듈. **웹 없이 커맨드라인으로 항상 테스트 가능**하게 유지한다.
PoC(`../poc/poc_cmyk_compose.py`)에서 증명된 가설을 재사용 가능한 모듈로 일반화한 것.

## 설치

```
pip install -r ../requirements.txt
# (선택) Ghostscript 설치 시 inkcov 색 교차검증 활성화: Windows=gswin64c, 리눅스/맥=gs
```

## 빠른 검증 (외부 파일 불필요)

```
python -m engine selftest
```

합성 device-CMYK 디자인을 만들어 6사이즈×4조각=24회 배치한 뒤 AC-1/2/3을 자동 검사한다.
종합 PASS면 코어가 정상. 결과 PDF·미리보기 PNG는 `_selftest_out/`에 생성.

## 실제 파일로 합성

```
python -m engine build --design 디자인.pdf --pattern 패턴.svg --out 출력폴더 --scale 0.15
python -m engine parse --pattern 패턴.svg     # 패턴 조각 파싱 결과만 확인
```

`build`는 실제 디자인(PDF호환 AI/PDF) + 패턴 SVG로 1개 사이즈를 합성→검증→미리보기한다.

## 모듈

| 파일 | 역할 |
|------|------|
| `pdfutil.py` | PDF 콘텐츠 스트림 저수준 헬퍼 (숫자 표기, 클립 `W n`, 배치 `cm`/`Do`) |
| `compose.py` | **코어**: 디자인 단일 임베드(Form XObject) + 조각별 클립·스케일·배치 → CMYK PDF |
| `pattern.py` | SVG `<polyline>` 파싱 → 조각 윤곽(PDF 좌표, y 뒤집음). DXF는 Phase 4 |
| `verify.py` | 검증: 바이트 동일성(무손실 보존)·단일 임베드·CMYK 계열·투명도·합성 정확 |
| `preview.py` | PyMuPDF로 검수용 PNG 렌더 |
| `fixtures.py` | selftest용 합성 CMYK 샘플 + PoC 기하 |
| `cli.py` | `selftest` / `build` / `parse` 커맨드 |

## 핵심 보장 (검증 항목)

- **무손실 보존**: 임베드된 디자인 Form 콘텐츠가 원본과 **바이트 동일**. device CMYK든
  ICCBased CMYK든 색공간 종류와 무관하게 무손실 증명. (selftest는 inkcov 편차 0.000000)
- **단일 임베드**: 디자인은 배치 횟수와 무관하게 정확히 1번만 들어가고 나머지는 참조(`Do`).
- **벡터·CMYK 유지**: RGB/Lab 색공간 유입 0건, 합성 중 래스터 미추가.
- **투명도 안전장치**: `ca/CA<1`·`SMask`·블렌드모드 발견 시 **검증 FAIL** → 원본 평탄화 후 재등록.
  (출력 단계 래스터화를 사전 차단. DESIGN.md 7번 안전장치.)

## 알려진 한계 / 다음 단계

- **디자인↔패턴 좌표 정합(진짜 그레이딩)**: 디자인 페이지 좌표계와 패턴 viewBox 좌표계는
  서로 다르다. "디자인의 어느 영역이 어느 조각에 얹히는가"는 패턴 프리셋(`preset.json`)에
  정의해야 할 그레이딩 정보다. 현재 `build`는 데모로 전체 디자인을 각 조각 bbox에 맞춰 넣는다.
  → 다음: 사이즈별 패턴 + 조각별 디자인 매핑을 프리셋으로 정의.
- **전 사이즈 그레이딩**: 현재 `build`는 1개 사이즈. selftest는 6사이즈 일괄(합성 픽스처)을 증명.
- **공장 시험인쇄**: 미리보기 PNG 통과 ≠ RIP 통과. Phase 1 완료엔 공장 시험인쇄 승인 필수.
