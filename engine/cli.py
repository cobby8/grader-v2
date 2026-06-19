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

  python -m engine order ORDER.xlsx [--json OUT.json]
      주문서 xlsx 를 파싱해 [{name,number,size,qty}] 행을 추출 → 행수·샘플 출력.
      --json 을 주면 결과를 그 경로에 JSON 으로 저장(job 단계에서 읽을 order.json).

  python -m engine job --preset PRESET.json --design D.ai --order ORDER.xlsx
                       [--out DIR] [--split per_player|single] [--no-preview]
      주문서(선수 명단) × 디자인 → 선수별 배번/이름 갈아끼운 PDF 한 벌 생성 → 검증.
      --out 미지정 시 data/jobs/<날짜_주문서명>/ 자동 생성. 결과는 job.json 에 덤프.
"""
from __future__ import annotations

import argparse
import os
import sys

from . import fixtures, pattern, preview, verify
from .compose import Piece, SizeLayout, compose, grid_layout
from .flatten import flatten_transparency  # 투명도 벡터 평탄화(EPS 벡터 유지용)
from .grade import grade as grade_run  # preset.json 기반 전 사이즈 합성(방식 A)
from .job import run_job  # 주문서 × 디자인 → 선수별 통합 출력 오케스트레이터
from .order import parse_order  # 주문서 xlsx → [{name,number,size,qty}] 파서(코어 독립)
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
    #    --number/--name 을 주면 뒤판에 배번/이름을 벡터 글자로 그린다(없으면 글자 없이 기존과 동일). ──
    warnings = []
    placements = grade_run(args.preset, args.design, out_pdf,
                           number=args.number, name=args.name, warnings=warnings)
    print(f"그레이딩 합성 완료: 배치 {placements}회 -> {out_pdf}")

    # ── 글자 렌더 경고(글리프 누락·칸 오류 등)가 있으면 화면에 안내. ──
    for w in warnings:
        print(w)

    # ── 출력물 검증(무손실/단일임베드/색공간 등). 디자인 원본과 대조한다. ──
    checks = verify.verify_output(out_pdf, args.design, placements)
    print(verify.format_report(checks))

    # ── 검수용 PNG 미리보기(눈으로 확인용, 출력 적합성 판정 아님). ──
    previews = preview.render_previews(out_pdf, out_dir, prefix="grade")
    print(f"미리보기 {len(previews)}장 저장: {out_dir}")
    return 0 if verify.all_passed(checks) else 1


def cmd_order(args) -> int:
    """주문서 xlsx 를 파싱해 행수·샘플을 출력하고(옵션) JSON 으로 덤프한다."""
    # ── 핵심: order.parse_order 가 xlsx 를 표준 행 리스트로 바꾼다(engine 코어 무관). ──
    warnings: list = []
    rows = parse_order(args.xlsx, warnings=warnings)

    # ── 경고(열기 실패·사이즈 누락 등)를 먼저 안내한다. ──
    for w in warnings:
        print(w)

    print(f"파싱된 행 수: {len(rows)}개  (파일: {args.xlsx})")

    # ── 사이즈 분포 요약(어떤 사이즈가 몇 개인지 한눈에). ──
    dist: dict = {}
    for r in rows:
        key = r["size"] if r["size"] else "(빈사이즈)"
        dist[key] = dist.get(key, 0) + 1
    if dist:
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
        print(f"사이즈 분포: {summary}")

    # ── 앞 10행 샘플 출력(사람이 눈으로 검수). ──
    print("샘플(최대 10행):")
    for r in rows[:10]:
        print(f"  이름='{r['name']}' 배번='{r['number']}' "
              f"사이즈='{r['size']}' 수량='{r['qty']}'")

    # ── --json 지정 시 결과를 파일로 저장(job 단계가 읽을 order.json). ──
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장: {args.json}")

    # 행을 하나라도 찾으면 성공으로 본다(빈 결과면 1 — 사용자가 알아채게).
    return 0 if rows else 1


def cmd_job(args) -> int:
    """주문서 × 디자인 → 선수별 통합 출력. xlsx → parse_order → run_job → summary 출력."""
    import datetime

    # ── 1) 주문서 파싱(이름/배번/사이즈/수량). 경고 먼저 안내. ──
    parse_warns: list = []
    order_rows = parse_order(args.order, warnings=parse_warns)
    for w in parse_warns:
        print(w)
    if not order_rows:
        print(f"주문서에서 선수 행을 찾지 못했습니다: {args.order}", file=sys.stderr)
        return 2
    print(f"주문서 파싱: 선수 {len(order_rows)}명  (파일: {args.order})")

    # ── 2) 작업 폴더 결정: --out 없으면 data/jobs/<날짜_주문서명>/ 자동 생성. ──
    if args.out:
        out_dir = args.out
    else:
        today = datetime.date.today().strftime("%y%m%d")
        order_stem = os.path.splitext(os.path.basename(args.order))[0]
        out_dir = os.path.join("data", "jobs", f"{today}_{order_stem}")
    os.makedirs(out_dir, exist_ok=True)

    # ── 3) 핵심: run_job 이 선수마다 사이즈 레이아웃+배번/이름으로 PDF 를 굽고 검증한다. ──
    result = run_job(args.preset, args.design, order_rows, out_dir,
                     font_path=args.font, split=args.split,
                     make_preview=not args.no_preview)

    s = result["summary"]
    # ── 4) 행 경고/스킵 안내(사람 검수용). ──
    for w in s["warnings"]:
        print(w)
    for sk in s["skipped"]:
        print(f"  건너뜀: 행{sk['row']} '{sk.get('name','')}' — {sk['reason']}")
    if s["missing_sizes"]:
        print(f"  ⚠️ preset 에 없는 사이즈(패턴 미확보): {', '.join(s['missing_sizes'])}")

    # ── 5) 종합 요약. ──
    produced = s["produced"]
    vpass = s["verify_pass"]
    vfail = s["verify_fail"]
    nskip = len(s["skipped"])
    split_name = s["split"]
    print("\n생성 %d개 / verify PASS %d · FAIL %d / 건너뜀 %d (split=%s)" % (produced, vpass, vfail, nskip, split_name))
    print("작업 폴더: %s" % s["job_dir"])

    # 하나도 못 만들었거나 verify 실패가 있으면 비정상 종료코드(사용자가 알아채게).
    if s["produced"] == 0 or s["verify_fail"] > 0:
        return 1
    return 0


def cmd_normalize_svg(args) -> int:
    """path SVG(직선 d 명령) → polyline SVG 변환(단일/배치) + 변환 후 조각수 자동 확인.

    두 가지 사용법:
      ① 단일: --in IN.svg --out OUT.svg
      ② 배치: --in-dir DIR --pattern '..._{size}.svg' --out-dir DIR --sizes 5XS,XS,...
              → 각 사이즈마다 IN=in-dir/pattern({size}치환), OUT=out-dir/<size>.svg.

    변환 직후 parse_svg 로 다시 읽어 조각수를 출력한다(2 가 기대값 — 앞/뒤판).
    """
    from .svg_normalize import normalize_svg

    # ── 변환할 (입력, 출력, 라벨) 목록을 만든다(단일 또는 배치). ──
    jobs = []  # (in_path, out_path, label)
    if args.in_path and args.out:
        jobs.append((args.in_path, args.out, os.path.basename(args.out)))
    elif args.in_dir and args.out_dir and args.pattern and args.sizes:
        sizes = [s.strip() for s in args.sizes.split(",") if s.strip()]
        for sz in sizes:
            fname = args.pattern.replace("{size}", sz)
            in_path = os.path.join(args.in_dir, fname)
            out_path = os.path.join(args.out_dir, f"{sz}.svg")
            jobs.append((in_path, out_path, sz))
    else:
        print("사용법: normalize-svg --in IN.svg --out OUT.svg  (단일)\n"
              "    또는 normalize-svg --in-dir DIR --pattern '..._{size}.svg' "
              "--out-dir DIR --sizes 5XS,XS,...  (배치)", file=sys.stderr)
        return 2

    ok_count = 0
    fail_count = 0
    for in_path, out_path, label in jobs:
        # ── 입력 존재 선검증(친절한 한글 안내). 1개 실패해도 나머지는 계속. ──
        if not os.path.exists(in_path):
            print(f"  ❌ [{label}] 입력 없음: {in_path}", file=sys.stderr)
            fail_count += 1
            continue
        try:
            rep = normalize_svg(in_path, out_path)
        except Exception as e:
            print(f"  ❌ [{label}] 변환 실패: {e}", file=sys.stderr)
            fail_count += 1
            continue

        # ── 변환 직후 parse_svg 로 재파싱해 조각수를 확인(2 기대). ──
        polys = pattern.parse_svg(out_path)
        n = len(polys)
        mark = "✅" if n == 2 else "⚠️"
        print(f"  {mark} [{label}] 조각 {n}개 "
              f"(written={rep['pieces_written']} / dropped open={rep['dropped_open']} "
              f"small={rep['dropped_small']} dup={rep['dropped_dup']}) → {out_path}")
        for w in rep["warnings"]:
            print(f"      {w}")
        if rep["has_curves"]:
            print("      🟡 곡선 명령 감지 — 직선 근사됨(형태 확인 필요).")
        ok_count += 1

    print(f"\n변환 완료: 성공 {ok_count} · 실패 {fail_count} (총 {len(jobs)})")
    return 0 if fail_count == 0 else 1


def cmd_flatten(args) -> int:
    """디자인 PDF 의 투명도를 벡터 상태로 평탄화한다(EPS 벡터 유지 선결 작업)."""
    bg = None
    if args.bg:
        try:
            bg = tuple(float(x) for x in args.bg.split(","))
            if len(bg) != 4:
                raise ValueError
        except ValueError:
            print("--bg 는 'C,M,Y,K' 4개 0~1 실수여야 합니다 (예: 0.8,0.5,0,0.1)", file=sys.stderr)
            return 2
    rep = flatten_transparency(args.design, args.out, bg_cmyk=bg)
    print("배경색(CMYK): %s" % (rep["bg"],))
    print("평탄화한 XObject: %s / 색 교체 %d곳 / 알파 ExtGState %d개 → 1.0"
          % (rep["flattened_xobjects"], rep["recolored_fills"], rep["alpha_gstates_fixed"]))
    for w in rep["warnings"]:
        print("  ⚠️ %s" % w)
    if rep["transparency_left"]:
        print("  ❌ 평탄화 후에도 투명도 잔존: %s" % rep["transparency_left"], file=sys.stderr)
        return 1
    print("투명도 없음 ✅ → 저장: %s" % args.out)
    return 0


def cmd_reference(args) -> int:
    """완성본(샘플 번호·이름 박힌 디자인)에서 preset area JSON 초안을 자동 추출한다.

    `engine reference --완성본 R.ai [--템플릿 T.ai] [--json out]`
      · 완성본 단독으로 동작(템플릿은 선택, 1차는 미사용 — 향후 diff 정확도용).
      · 앞/뒤 번호(center·cap_height·color)와 뒤 이름(center_x·baseline·em_pt·pitch)을
        preset 스키마(front_number_area/back_number_area/back_name_area)로 출력.
    """
    from .reference import build_area_preset

    # ── 입력 파일 선검증(친절한 한글 메시지). ──
    if not os.path.exists(args.완성본):
        print(f"완성본 파일을 찾지 못했습니다: {args.완성본}", file=sys.stderr)
        return 2
    if args.템플릿 and not os.path.exists(args.템플릿):
        print(f"템플릿 파일을 찾지 못했습니다: {args.템플릿}", file=sys.stderr)
        return 2
    if args.템플릿:
        # 1차 구현은 완성본 단독 추출이라 템플릿은 받기만 하고 안내만 한다(향후 diff 용).
        print("ℹ️ 템플릿은 받았으나 1차 추출은 완성본 단독으로 수행합니다(diff 정확도 향상은 후속).")

    # ── 핵심: build_area_preset 이 번호(pikepdf)+이름(fitz rawdict)을 묶어 area 초안 산출. ──
    try:
        result = build_area_preset(args.완성본, font=args.font)
    except Exception as e:
        # 크래시 금지 — 사람이 읽을 수 있는 한글 메시지로 안내.
        print(f"완성본 분석 중 문제가 발생했습니다: {e}", file=sys.stderr)
        return 1

    pw, ph = result["page_size"]
    print(f"페이지 크기: {pw} x {ph} pt / 앞·뒤 분할 x={result['split_x']}")

    # ── 추출 경고(부분 실패)를 먼저 안내. ──
    for w in result["warnings"]:
        print(w)

    # ── 추출 결과 요약(사람이 §4 수치와 대조). ──
    areas = result["areas"]
    fa = areas["front_number_area"]
    ba = areas["back_number_area"]
    na = areas["back_name_area"]
    if fa:
        print(f"앞 번호: center={fa['center']} cap_height={fa['cap_height']} color={fa['color_cmyk']}")
    if ba:
        print(f"뒤 번호: center={ba['center']} cap_height={ba['cap_height']} color={ba['color_cmyk']}")
    if na:
        print(f"뒤 이름: center_x={na['center_x']} baseline={na['baseline']} "
              f"em_pt={na['em_pt']} pitch={na['pitch']} color={na['color_cmyk']}")
    nd = result.get("name_detail")
    if nd:
        print(f"  (이름 추출 원문='{nd['text']}' font='{nd['font']}')")

    # ── --json 지정 시 area 초안을 파일로 저장(preset.json 에 붙여넣을 수 있게). ──
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(areas, f, ensure_ascii=False, indent=2)
        print(f"area JSON 저장: {args.json}")

    # 셋 중 하나라도 뽑았으면 성공으로 본다(전부 실패면 1).
    return 0 if (fa or ba or na) else 1


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
    gp.add_argument("--number", default=None, help="(선택) 뒤판에 그릴 배번(예: 7)")
    gp.add_argument("--name", default=None, help="(선택) 뒤판에 그릴 이름(예: 김민수)")
    gp.set_defaults(func=cmd_grade)

    op = sub.add_parser("order", help="주문서 xlsx 파싱(행수·샘플 출력)")
    op.add_argument("xlsx", help="주문서 엑셀 파일 경로(.xlsx)")
    op.add_argument("--json", default=None, help="(선택) 결과를 저장할 JSON 경로")
    op.set_defaults(func=cmd_order)

    jp = sub.add_parser("job", help="주문서×디자인 → 선수별 통합 출력")
    jp.add_argument("--preset", required=True, help="패턴 폴더의 preset.json 경로")
    jp.add_argument("--design", required=True, help="기준 디자인 파일(.ai/.pdf)")
    jp.add_argument("--order", required=True, help="주문서 xlsx 경로")
    jp.add_argument("--out", default=None,
                    help="(선택) 작업 폴더. 미지정 시 data/jobs/<날짜_주문서명>/ 자동")
    jp.add_argument("--font", default=None,
                    help="(선택, 현재 미사용) 폰트 루트 — preset 의 area.font 가 우선")
    jp.add_argument("--split", choices=["per_player", "single"], default="per_player",
                    help="per_player(기본, 선수별 파일) | single(다페이지 1PDF)")
    jp.add_argument("--no-preview", action="store_true", help="검수용 PNG 미리보기 생략")
    jp.set_defaults(func=cmd_job)

    rp = sub.add_parser("reference", help="완성본에서 번호·이름 area JSON 초안 추출")
    rp.add_argument("--완성본", required=True, dest="완성본",
                    help="샘플 번호·이름이 박힌 완성본 디자인(.ai/.pdf)")
    rp.add_argument("--템플릿", default=None, dest="템플릿",
                    help="(선택) 빈 템플릿 — 1차는 미사용, 향후 diff 정확도용")
    rp.add_argument("--json", default=None, help="(선택) area JSON 초안 저장 경로")
    rp.add_argument("--font", default="data/fonts/HY헤드라인M.ttf",
                    help="번호·이름 공통 폰트 경로(기본 HY헤드라인M.ttf)")
    rp.set_defaults(func=cmd_reference)

    np_ = sub.add_parser("normalize-svg",
                         help="path SVG → polyline SVG 변환(단일/배치) + 조각수 확인")
    np_.add_argument("--in", dest="in_path", default=None, help="(단일) 입력 path SVG")
    np_.add_argument("--out", default=None, help="(단일) 출력 polyline SVG")
    np_.add_argument("--in-dir", dest="in_dir", default=None, help="(배치) 입력 폴더")
    np_.add_argument("--out-dir", dest="out_dir", default=None, help="(배치) 출력 폴더")
    np_.add_argument("--pattern", default=None,
                     help="(배치) 파일명 패턴. '{size}' 가 사이즈로 치환됨")
    np_.add_argument("--sizes", default=None,
                     help="(배치) 변환할 사이즈 콤마 구분(예: 5XS,4XS,...,5XL)")
    np_.set_defaults(func=cmd_normalize_svg)

    fp = sub.add_parser("flatten", help="디자인 투명도 벡터 평탄화(EPS 벡터 유지)")
    fp.add_argument("--design", required=True, help="평탄화할 디자인 파일(.ai/.pdf)")
    fp.add_argument("--out", required=True, help="평탄화 결과 저장 경로(.pdf)")
    fp.add_argument("--bg", default=None, help="(선택) 배경 CMYK 'C,M,Y,K' 강제 지정. 미지정 시 자동 감지")
    fp.set_defaults(func=cmd_flatten)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
