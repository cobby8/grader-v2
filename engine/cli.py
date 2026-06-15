# -*- coding: utf-8 -*-
"""engine 커맨드라인 — 웹 없이 엔진을 단독 검증/실행.

  python -m engine selftest [--out DIR]
      합성 픽스처로 PoC(AC-1/2/3)를 재현하고 PASS/FAIL을 출력. 외부 파일 불필요.

  python -m engine build --design D.pdf --pattern P.svg [--out DIR] [--scale 1.0]
      실제 디자인 PDF + 패턴 SVG로 1개 사이즈 합성 → 검증 → 미리보기 PNG.
      (전 사이즈 그레이딩은 사이즈별 패턴/그레이딩 로직 확장 단계에서.)

  python -m engine parse --pattern P.svg
      패턴 SVG 파싱 결과(조각 수/크기) 요약 출력.

  python -m engine grade --preset PRESET.json --design D.ai [--out DIR]
      preset.json + 디자인으로 전 사이즈를 자동 합성(방식 A: 앵커 정합) → 검증 → 미리보기.
"""
from __future__ import annotations

import argparse
import os
import sys

from . import fixtures, pattern, preview, verify
from .compose import Piece, SizeLayout, compose, grid_layout
from .grade import grade as grade_run  # preset.json 기반 전 사이즈 합성(방식 A)
from .pdfutil import scale_translate


def cmd_selftest(args) -> int:
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    design = os.path.join(out_dir, "selftest_design.pdf")
    out_pdf = os.path.join(out_dir, "selftest_composed.pdf")

    fixtures.make_known_cmyk_design(design)
    layouts = [
        grid_layout(name, fixtures.BASE_PIECES, (fixtures.DESIGN_W, fixtures.DESIGN_H), scale)
        for name, scale in fixtures.SIZE_SCALES
    ]
    placements = compose(design, layouts, out_pdf)
    print(f"합성: {len(layouts)}개 사이즈 / {placements}회 배치 -> {out_pdf}")

    checks = verify.verify_output(out_pdf, design, placements)
    print(verify.format_report(checks))

    # inkcov 교차검증 (gs 있을 때만): 1:1 단독 배치로 색 보존 수치 확인
    one = os.path.join(out_dir, "selftest_1to1.pdf")
    full = Piece(
        outline=[(0, 0), (fixtures.DESIGN_W, 0), (fixtures.DESIGN_W, fixtures.DESIGN_H), (0, fixtures.DESIGN_H)],
        transform=scale_translate(1.0, 0, 0), name="full")
    compose(design, [SizeLayout("1to1", (fixtures.DESIGN_W, fixtures.DESIGN_H), [full])], one)
    ic_in, ic_out = verify.inkcov(design), verify.inkcov(one)
    if ic_in and ic_out:
        diff = max(abs(a - b) for a, b in zip(ic_in, ic_out))
        print(f"  [inkcov] 입력 {ic_in} vs 1:1 {ic_out} -> 최대편차 {diff:.6f} "
              f"({'PASS' if diff <= 0.0005 else 'FAIL'})")
    else:
        print("  [inkcov] Ghostscript 미설치 - 생략")

    previews = preview.render_previews(out_pdf, out_dir, prefix="selftest")
    print(f"미리보기 {len(previews)}장 저장: {out_dir}")

    ok = verify.all_passed(checks)
    print(f"\n========== selftest 종합: {'PASS' if ok else 'FAIL'} ==========")
    return 0 if ok else 1


def cmd_build(args) -> int:
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    polys = pattern.parse_svg(args.pattern)
    if not polys:
        print(f"패턴에서 조각을 찾지 못했습니다: {args.pattern}", file=sys.stderr)
        return 2
    print(f"패턴 파싱: 조각 {len(polys)}개 (높이순)")
    for i, pl in enumerate(polys):
        print(f"  조각{i}: 점 {len(pl.points)}개, 크기 {pl.width:.1f} x {pl.height:.1f}")

    # 패턴 윤곽을 시트 좌표로 옮기고, 각 조각 bbox에 디자인을 '맞춰 넣어'(fit) 클립한다.
    # 주의: 디자인 좌표계와 패턴 좌표계는 서로 다르므로(디자인 페이지 ≠ 패턴 viewBox),
    #       '디자인의 어느 영역이 어느 조각에 얹히는가'는 본래 패턴 프리셋(preset.json)에
    #       정의해야 하는 그레이딩 정보다. 여기서는 데모용으로 전체 디자인을 조각 bbox에 맞춘다.
    import pikepdf
    _d = pikepdf.open(args.design)
    dpg = _d.pages[0].MediaBox
    dw = float(dpg[2]) - float(dpg[0])
    dh = float(dpg[3]) - float(dpg[1])
    _d.close()

    minx = min(pl.bbox[0] for pl in polys)
    miny = min(pl.bbox[1] for pl in polys)
    s = args.scale
    pieces = []
    for i, pl in enumerate(polys):
        outline = [((x - minx) * s + 20, (y - miny) * s + 20) for (x, y) in pl.points]
        bx0, by0, bx1, by1 = pl.bbox
        ox = (bx0 - minx) * s + 20
        oy = (by0 - miny) * s + 20
        fit = min((bx1 - bx0) * s / dw, (by1 - by0) * s / dh)  # 디자인 전체를 조각 bbox에 맞춤
        pieces.append(Piece(outline=outline, transform=scale_translate(fit, ox, oy), name=f"piece{i}"))
    w = max(x for pl in polys for x, _ in pl.points) - minx
    h = max(y for pl in polys for _, y in pl.points) - miny
    layout = SizeLayout(args.size, (w * s + 40, h * s + 40), pieces)

    out_pdf = os.path.join(out_dir, "build_composed.pdf")
    placements = compose(args.design, [layout], out_pdf)
    print(f"합성: 1개 사이즈({args.size}) / {placements}회 배치 -> {out_pdf}")

    checks = verify.verify_output(out_pdf, args.design, placements)
    print(verify.format_report(checks))
    previews = preview.render_previews(out_pdf, out_dir, prefix="build")
    print(f"미리보기 저장: {previews}")
    return 0 if verify.all_passed(checks) else 1


def cmd_parse(args) -> int:
    polys = pattern.parse_svg(args.pattern)
    groups = pattern.classify_by_height(polys)
    print(f"조각 {len(polys)}개 / 큰조각 {len(groups['large'])} · 작은조각 {len(groups['small'])}")
    for i, pl in enumerate(polys):
        print(f"  조각{i}: 점 {len(pl.points)}개, bbox {tuple(round(v,1) for v in pl.bbox)}, 높이 {pl.height:.1f}")
    return 0


def cmd_grade(args) -> int:
    """preset.json + 디자인으로 전 사이즈를 자동 합성(방식 A) → 검증 → 미리보기."""
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    out_pdf = os.path.join(out_dir, "grade_composed.pdf")

    # ── 핵심: grade.py 가 preset 을 읽어 방식 A 로 전 사이즈를 합성한다(engine.compose 호출). ──
    placements = grade_run(args.preset, args.design, out_pdf)
    print(f"그레이딩 합성 완료: 배치 {placements}회 -> {out_pdf}")

    # ── 출력물 검증(무손실/단일임베드/색공간 등). 디자인 원본과 대조한다. ──
    checks = verify.verify_output(out_pdf, args.design, placements)
    print(verify.format_report(checks))

    # ── 검수용 PNG 미리보기(눈으로 확인용, 출력 적합성 판정 아님). ──
    previews = preview.render_previews(out_pdf, out_dir, prefix="grade")
    print(f"미리보기 {len(previews)}장 저장: {out_dir}")
    return 0 if verify.all_passed(checks) else 1


def _force_utf8_console() -> None:
    """한글 Win 기본 콘솔(cp949)에서 '—'(U+2014) 등 비-cp949 문자 출력 시
    UnicodeEncodeError 크래시를 막기 위해 stdout/stderr를 UTF-8로 고정한다.
    (리다이렉트된 스트림 등 reconfigure 미지원 시 안전하게 무시)"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None) -> int:
    _force_utf8_console()
    p = argparse.ArgumentParser(prog="engine", description="grader-v2 출력 엔진 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("selftest", help="합성 픽스처로 PoC 재현")
    sp.add_argument("--out", default="_selftest_out")
    sp.set_defaults(func=cmd_selftest)

    bp = sub.add_parser("build", help="실제 디자인+패턴으로 1사이즈 합성")
    bp.add_argument("--design", required=True)
    bp.add_argument("--pattern", required=True)
    bp.add_argument("--out", default="_build_out")
    bp.add_argument("--size", default="XS")
    bp.add_argument("--scale", type=float, default=0.1)
    bp.set_defaults(func=cmd_build)

    pp = sub.add_parser("parse", help="패턴 SVG 파싱 요약")
    pp.add_argument("--pattern", required=True)
    pp.set_defaults(func=cmd_parse)

    gp = sub.add_parser("grade", help="preset.json+디자인으로 전 사이즈 합성(방식 A)")
    gp.add_argument("--preset", required=True, help="패턴 폴더의 preset.json 경로")
    gp.add_argument("--design", required=True, help="기준 디자인 파일(.ai/.pdf)")
    gp.add_argument("--out", default="_grade_out")
    gp.set_defaults(func=cmd_grade)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
