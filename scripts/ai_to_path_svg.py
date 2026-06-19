# -*- coding: utf-8 -*-
"""ai_to_path_svg — Adobe Illustrator(.ai) → path SVG 추출 보조 스크립트.

왜 이 스크립트가 필요한가 (큰 그림):
  엔진의 패턴 변환 파이프라인은 두 단계다.
    ① .ai → path SVG  (이 스크립트)
    ② path SVG → polyline SVG  (engine 의 `normalize-svg` 서브커맨드, 무수정)
  이 스크립트는 ①만 담당한다. PyMuPDF(fitz)로 .ai 1페이지를 열어
  get_svg_image(text_as_path=True) 로 path SVG 를 뽑는다. 글자는 외곽선(path)으로
  떨어뜨려 폰트 의존을 없앤다.

  비유: ②가 '번역기'라면 이 스크립트는 '원문 스캐너'다. 책(.ai)을 펼쳐 깨끗한
       스캔본(path SVG)을 만들어 번역기에 넘긴다. 엔진 코어는 일절 건드리지 않는다.

왜 방식 (A) 인가 (좌표계 오염 해소):
  과거 비-XL 12개 패턴 SVG 는 '다른 출처'(viewBox 세로 5669 + 음수 좌표)에서 변환돼
  앞판이 캔버스 밖으로 소실됐다. 이 스크립트로 '원본 .ai 13개를 같은 출처·같은 방식'으로
  추출하면 PyMuPDF 가 13개 모두 viewBox 가로(4478×3401)·양수 좌표로 통일한다(실측 확인).
  → 그 뒤 기존 normalize-svg 로 polyline 화하면 13개가 동일 좌표계가 된다.

불변 제약(절대 준수):
  engine 공개 API·cli·svg_normalize 코어 전부 무수정. 이 스크립트는 scripts/ 의
  독립 도구로, engine 을 import 하지 않고 fitz 만 쓴다.

사용법:
  ① 단일:
     python scripts/ai_to_path_svg.py --in IN.ai --out OUT.svg
  ② 배치(사이즈 패턴):
     python scripts/ai_to_path_svg.py \
       --in-dir "G:/.../V넥 양면유니폼 스탠다드" \
       --pattern "양면유니폼_V넥_스탠다드_{size}.ai" \
       --out-dir "data/_tmp_path_svg" \
       --sizes 5XS,4XS,3XS,2XS,XS,S,M,L,XL,2XL,3XL,4XL,5XL
     → out-dir 에 <size>.svg 13개(path SVG) 생성.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile


def _force_utf8_console() -> None:
    """한글 콘솔에서 출력이 깨지지 않게 stdout/stderr 를 UTF-8 로 강제한다.

    cmd.exe(cp949) 에서 ✅·한글이 섞이면 UnicodeEncodeError 가 날 수 있어 방어한다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def ai_to_path_svg(in_path: str, out_path: str, *, page_index: int = 0) -> dict:
    """단일 .ai(또는 .pdf) → path SVG 로 추출(원자적 저장).

    매개변수
      in_path    : 입력 .ai/.pdf 경로.
      out_path   : 출력 path SVG 경로(임시파일 → os.replace 로 원자적 저장).
      page_index : 추출할 페이지(0-base). 패턴 파일은 보통 0.

    반환(dict): {"in","out","viewBox","paths","header_ok","header"}
      header_ok=False 면 %!PS- (구형 EPS 헤더) 라 PyMuPDF 가 못 여는 경우 → 보고용.

    좌표 처리:
      get_svg_image 는 .ai 1페이지를 viewBox 좌표(가로 4478×3401)로 떨어뜨린다.
      여기서는 가공하지 않고 '원문 그대로' 저장한다. flip/필터/중복제거는 모두
      다음 단계(normalize-svg)가 한다 — 역할 분리.
    """
    import fitz  # PyMuPDF (지연 import: 미설치 환경에서도 사용법 출력은 되게)

    if not os.path.exists(in_path):
        raise FileNotFoundError(f"입력 파일 없음: {in_path}")

    # ── 헤더 확인: %PDF- 면 PyMuPDF 가 정상 처리, %!PS- 면 구형이라 보고 필요. ──
    with open(in_path, "rb") as fh:
        head = fh.read(5)
    header = head.decode("latin-1", errors="replace")
    header_ok = head.startswith(b"%PDF-")

    doc = fitz.open(in_path)
    try:
        if page_index >= doc.page_count:
            raise ValueError(
                f"페이지 인덱스 {page_index} 가 범위를 벗어남(총 {doc.page_count}쪽): {in_path}")
        page = doc[page_index]
        # text_as_path=True: 글자를 외곽선 path 로 떨어뜨려 폰트 의존 제거.
        svg_text = page.get_svg_image(text_as_path=True)
    finally:
        doc.close()

    # ── viewBox·path 수를 보고용으로 뽑는다(검증 편의). ──
    import re
    m = re.search(r'viewBox="([^"]+)"', svg_text)
    view_box = m.group(1) if m else None
    n_paths = svg_text.count("<path")

    # ── 원자적 저장(임시파일 → os.replace). 중간 실패 시 부분 파일 안 남김. ──
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".svg", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(svg_text)
        os.replace(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    return {
        "in": in_path,
        "out": out_path,
        "viewBox": view_box,
        "paths": n_paths,
        "header_ok": header_ok,
        "header": header,
    }


def _build_jobs(args) -> list:
    """CLI 인자에서 (in_path, out_path, label) 목록을 만든다(단일 또는 배치)."""
    jobs = []
    if args.in_path and args.out:
        jobs.append((args.in_path, args.out, os.path.basename(args.out)))
    elif args.in_dir and args.out_dir and args.pattern and args.sizes:
        sizes = [s.strip() for s in args.sizes.split(",") if s.strip()]
        for sz in sizes:
            fname = args.pattern.replace("{size}", sz)
            in_path = os.path.join(args.in_dir, fname)
            out_path = os.path.join(args.out_dir, f"{sz}.svg")
            jobs.append((in_path, out_path, sz))
    return jobs


def main(argv=None) -> int:
    _force_utf8_console()
    ap = argparse.ArgumentParser(
        prog="ai_to_path_svg",
        description=".ai → path SVG 추출(단일/배치). 다음 단계는 engine normalize-svg.")
    ap.add_argument("--in", dest="in_path", help="입력 .ai/.pdf (단일)")
    ap.add_argument("--out", dest="out", help="출력 .svg (단일)")
    ap.add_argument("--in-dir", dest="in_dir", help="입력 폴더 (배치)")
    ap.add_argument("--pattern", dest="pattern",
                    help="파일명 패턴 (배치). {size} 를 사이즈로 치환. 예: '..._{size}.ai'")
    ap.add_argument("--out-dir", dest="out_dir", help="출력 폴더 (배치)")
    ap.add_argument("--sizes", dest="sizes",
                    help="콤마 구분 사이즈 목록 (배치). 예: 5XS,XS,M,L,XL")
    ap.add_argument("--page", dest="page", type=int, default=0,
                    help="추출 페이지(0-base, 기본 0)")
    args = ap.parse_args(argv)

    jobs = _build_jobs(args)
    if not jobs:
        print("사용법: ai_to_path_svg --in IN.ai --out OUT.svg  (단일)\n"
              "    또는 ai_to_path_svg --in-dir DIR --pattern '..._{size}.ai' "
              "--out-dir DIR --sizes 5XS,XS,...  (배치)", file=sys.stderr)
        return 2

    ok = 0
    fail = 0
    for in_path, out_path, label in jobs:
        if not os.path.exists(in_path):
            print(f"  ❌ [{label}] 입력 없음: {in_path}", file=sys.stderr)
            fail += 1
            continue
        try:
            rep = ai_to_path_svg(in_path, out_path, page_index=args.page)
        except Exception as e:
            print(f"  ❌ [{label}] 추출 실패: {e}", file=sys.stderr)
            fail += 1
            continue
        # %!PS- 등 비-PDF 헤더면 경고(PyMuPDF 가 열긴 했어도 보고).
        warn = "" if rep["header_ok"] else f"  ⚠️ 헤더 비정상('{rep['header']}') — 확인 필요"
        print(f"  ✅ [{label}] viewBox={rep['viewBox']} paths={rep['paths']} "
              f"→ {out_path}{warn}")
        ok += 1

    print(f"\n추출 완료: 성공 {ok} · 실패 {fail} (총 {len(jobs)})")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
