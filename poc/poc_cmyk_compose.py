# -*- coding: utf-8 -*-
"""
grader-v2 PoC — CMYK 완전 보존 + 경량 PDF 합성 증명
====================================================
실행 방법:
    pip install pikepdf            (+ Ghostscript 설치: Windows는 gswin64c, 리눅스/맥은 gs)
    python poc_cmyk_compose.py     (이 파일이 있는 폴더에서 실행 — 입출력 파일이 같은 폴더에 생성됨)

산출물:
    sample_design_cmyk.pdf        입력: device CMYK, 투명도 없음, 기지(旣知) 색값 도형 6개+곡선
    sample_design_cmyk_heavy.pdf  입력(보강): 실제 디자인 규모의 무거운 샘플 (AC-2 기준2용)
    output_composed.pdf           4조각 x 6사이즈 = 24회 배치 (디자인은 1회만 임베드)
    output_composed_x2.pdf        48회 배치 (AC-2 크기 증가폭 비교용)
    output_composed_heavy.pdf     무거운 샘플 24회 배치
    output_1to1.pdf               변형 없는 1:1 단독 배치 (AC-1b inkcov 비교용)
    poc_report.txt                AC-1/2/3 PASS/FAIL 수치 로그
"""
import os
import re
import shutil
import subprocess
import sys

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "sample_design_cmyk.pdf")
COMPOSED = os.path.join(HERE, "output_composed.pdf")
COMPOSED_X2 = os.path.join(HERE, "output_composed_x2.pdf")
ONE_TO_ONE = os.path.join(HERE, "output_1to1.pdf")
REPORT = os.path.join(HERE, "poc_report.txt")

DESIGN_W, DESIGN_H = 400.0, 300.0  # pt

# 기지 색값 (C, M, Y, K) — 이 값이 출력에서 한 톨도 변하면 안 됨
KNOWN_FILLS = [
    (1.0, 0.0, 0.0, 0.0),    # C100
    (0.0, 1.0, 0.0, 0.0),    # M100
    (0.0, 0.0, 1.0, 0.0),    # Y100
    (0.0, 0.0, 0.0, 1.0),    # K100
    (0.5, 0.2, 0.0, 0.1),    # 혼합 1
    (0.2, 0.8, 0.9, 0.05),   # 혼합 2
]
KNOWN_STROKE = (0.1, 0.9, 0.3, 0.0)  # 곡선 stroke 색


def fmt(v: float) -> str:
    """PDF 숫자 표기 (불필요한 소수점 제거)"""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


# ---------------------------------------------------------------- 1. 샘플 생성
def make_sample():
    """device CMYK 전용 연산자(k/K)로만 그린 샘플 — ICC/RGB 일절 없음, 투명도 없음"""
    ops = []
    for i, (c, m, y, k) in enumerate(KNOWN_FILLS):
        col, row = i % 3, i // 3
        x, yy = 20 + col * 125, 170 - row * 130
        ops.append(f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k")
        ops.append(f"{x} {yy} 105 100 re f")
    c, m, y, k = KNOWN_STROKE
    ops.append(f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} K")
    ops.append("3 w 30 30 m 130 90 270 -30 370 30 c S")
    content = "\n".join(ops).encode("ascii")

    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(DESIGN_W, DESIGN_H))
    page.obj["/Contents"] = pdf.make_stream(content)
    pdf.save(SAMPLE)


def make_heavy_sample(path, n_paths=20000):
    """실제 디자인 규모(수백 KB~MB)의 무거운 device CMYK 샘플 — AC-2의 '1.5배 이내' 기준용.
    좌표를 의사난수로 흩어 압축이 과하게 되지 않게 한다 (실제 디자인의 복잡도 흉내)."""
    import random
    rnd = random.Random(42)
    ops = []
    for _ in range(n_paths):
        c, m, y, k = (round(rnd.random(), 3) for _ in range(4))
        ops.append(f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k")
        x0, y0 = rnd.uniform(0, DESIGN_W), rnd.uniform(0, DESIGN_H)
        nums = [
            x0 + rnd.uniform(-30, 30), y0 + rnd.uniform(-30, 30),
            x0 + rnd.uniform(-30, 30), y0 + rnd.uniform(-30, 30),
            x0 + rnd.uniform(-30, 30), y0 + rnd.uniform(-30, 30),
        ]
        ops.append(f"{fmt(x0)} {fmt(y0)} m {' '.join(fmt(v) for v in nums)} c f")
    content = "\n".join(ops).encode("ascii")
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(DESIGN_W, DESIGN_H))
    page.obj["/Contents"] = pdf.make_stream(content)
    pdf.save(path, compress_streams=True)


# ---------------------------------------------------------------- 2. 합성
PIECES = [
    [(0, 0), (180, 0), (180, 140), (0, 140)],                      # 사각형 A
    [(200, 0), (400, 0), (400, 140), (200, 140)],                  # 사각형 B
    [(0, 160), (180, 160), (180, 300), (0, 300)],                  # 사각형 C
    [(200, 160), (300, 300), (400, 240), (380, 170), (290, 160)],  # 오각형
]
SIZES = [0.5, 0.7, 0.85, 1.0, 1.15, 1.3]  # 6사이즈 스케일


def clip_ops(poly, scale, ox, oy):
    parts = []
    for i, (x, y) in enumerate(poly):
        parts.append(f"{fmt(ox + x * scale)} {fmt(oy + y * scale)} {'m' if i == 0 else 'l'}")
    parts.append("h W n")
    return "\n".join(parts)


def compose(out_path, repeat=1, sample=SAMPLE):
    """디자인을 Form XObject로 '1회만' 임베드하고, 사이즈별 페이지에 조각 배치는 참조(Do)만 반복"""
    src = pikepdf.open(sample)
    out = pikepdf.new()
    xobj = out.copy_foreign(src.pages[0].as_form_xobject())  # ← 임베드는 이 한 번뿐

    placements = 0
    for s in SIZES:
        page_w, page_h = DESIGN_W * s * 2 + 60, DESIGN_H * s * 2 + 60
        page = out.add_blank_page(page_size=(page_w, page_h))
        name = page.add_resource(xobj, pikepdf.Name("/XObject"))  # 같은 객체 참조 등록
        chunks = []
        for r in range(repeat):
            for j, poly in enumerate(PIECES):
                ox = 20 + (j % 2) * (DESIGN_W * s + 10) + r * 3
                oy = 20 + (j // 2) * (DESIGN_H * s + 10) + r * 3
                chunks.append(
                    f"q\n{clip_ops(poly, s, ox, oy)}\n"
                    f"{fmt(s)} 0 0 {fmt(s)} {fmt(ox)} {fmt(oy)} cm\n"
                    f"{name} Do\nQ"
                )
                placements += 1
        page.obj["/Contents"] = out.make_stream("\n".join(chunks).encode("ascii"))
    out.save(out_path, compress_streams=True)  # 무손실 deflate만 — 색/이미지 무변형
    return placements


def make_1to1():
    src = pikepdf.open(SAMPLE)
    out = pikepdf.new()
    xobj = out.copy_foreign(src.pages[0].as_form_xobject())
    page = out.add_blank_page(page_size=(DESIGN_W, DESIGN_H))
    name = page.add_resource(xobj, pikepdf.Name("/XObject"))
    page.obj["/Contents"] = out.make_stream(f"q\n{name} Do\nQ".encode("ascii"))
    out.save(ONE_TO_ONE)


# ---------------------------------------------------------------- 3. 검증
def extract_cmyk_ops(stream_bytes):
    """콘텐츠 스트림에서 k/K 연산자의 CMYK 4값 리스트 추출 (등장 순서 유지)"""
    found = []
    pat = re.compile(rb"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(k|K)(?![\w])")
    for m in pat.finditer(stream_bytes):
        vals = tuple(float(m.group(i)) for i in range(1, 5))
        found.append((m.group(5).decode(), vals))
    return found


def find_design_xobjects(pdf):
    """PDF 전체에서 Form XObject 객체 수집 (중복 임베드 감지)"""
    forms = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == pikepdf.Name("/Form"):
                forms.append(obj)
        except Exception:
            pass
    return forms


def scan_transparency(pdf):
    issues = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == pikepdf.Name("/ExtGState"):
                for key in ("/ca", "/CA"):
                    if key in obj and float(obj[key]) < 1.0:
                        issues.append(f"ExtGState {key}={float(obj[key])}")
                if "/SMask" in obj and obj["/SMask"] != pikepdf.Name("/None"):
                    issues.append("SMask 존재")
                if "/BM" in obj and obj["/BM"] not in (pikepdf.Name("/Normal"),):
                    issues.append(f"BlendMode {obj['/BM']}")
        except Exception:
            pass
    return issues


def gs_exe():
    for cand in ("gswin64c", "gs"):
        if shutil.which(cand):
            return cand
    return None


def inkcov(pdf_path):
    exe = gs_exe()
    if not exe:
        return None
    args = [exe, "-dNOPAUSE", "-dBATCH", "-dQUIET",
            "-dFirstPage=1", "-dLastPage=1",
            "-o", "-", "-sDEVICE=inkcov", pdf_path]
    r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    m = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+CMYK OK", r.stdout)
    return tuple(float(m.group(i)) for i in range(1, 5)) if m else None


def colorspace_check(pdf):
    """페이지/XObject Resources에 RGB·ICC 색공간이 끼어들지 않았는지 (0건이어야 정상)"""
    bad = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                res = obj.get("/Resources")
                if res and "/ColorSpace" in res:
                    for k, v in res["/ColorSpace"].items():
                        bad.append(f"{k}: {str(v)[:60]}")
        except Exception:
            pass
    return bad


def main():
    lines = []
    log = lambda s="": (print(s), lines.append(s))

    make_sample()
    log(f"입력 생성: sample_design_cmyk.pdf ({os.path.getsize(SAMPLE)} bytes, "
        f"도형 {len(KNOWN_FILLS)}개 + 곡선 1개, device CMYK, 투명도 없음)")

    n24 = compose(COMPOSED, repeat=1)
    n48 = compose(COMPOSED_X2, repeat=2)
    make_1to1()
    log(f"합성 완료: {n24}회 배치 / 2배 비교본 {n48}회 배치 / 1:1 검증본")
    log()

    overall = True

    # ---------- AC-1a: 색값 직접 비교 ----------
    src = pikepdf.open(SAMPLE)
    out = pikepdf.open(COMPOSED)
    in_ops = extract_cmyk_ops(src.pages[0].obj["/Contents"].read_bytes())
    forms = find_design_xobjects(out)
    out_ops = extract_cmyk_ops(forms[0].read_bytes()) if forms else []
    match = in_ops == out_ops
    overall &= match
    log("[AC-1a] CMYK 색값 직접 비교 (입력 페이지 vs 출력 내 Form XObject)")
    for (op_i, v_i), (op_o, v_o) in zip(in_ops, out_ops):
        log(f"    입력 {op_i} {v_i}  →  출력 {op_o} {v_o}  {'==' if v_i == v_o else '!!'}")
    log(f"    값 개수: 입력 {len(in_ops)} / 출력 {len(out_ops)}")
    log(f"    → {'PASS' if match else 'FAIL'} (리스트 완전 일치={match})")

    cs_bad = colorspace_check(out)
    cs_ok = len(cs_bad) == 0
    overall &= cs_ok
    log(f"[AC-1a] 색공간 검증: ColorSpace 리소스 {len(cs_bad)}건 "
        f"(k/K=device CMYK 직접 지정이므로 0이어야 함) → {'PASS' if cs_ok else 'FAIL: ' + '; '.join(cs_bad)}")

    trans = scan_transparency(out)
    t_ok = len(trans) == 0
    overall &= t_ok
    log(f"[AC-1a+] 출력 투명도 스캔: {len(trans)}건 → {'PASS' if t_ok else 'FAIL: ' + '; '.join(trans)}")
    log()

    # ---------- AC-1b: inkcov 교차 검증 ----------
    log("[AC-1b] Ghostscript inkcov 교차 검증 (입력 vs 1:1 배치)")
    ic_in = inkcov(SAMPLE)
    ic_out = inkcov(ONE_TO_ONE)
    if ic_in and ic_out:
        diff = max(abs(a - b) for a, b in zip(ic_in, ic_out))
        ic_ok = diff <= 0.0005
        overall &= ic_ok
        log(f"    입력  C/M/Y/K = {ic_in}")
        log(f"    1:1   C/M/Y/K = {ic_out}")
        log(f"    최대 편차 {diff:.6f} (허용 0.0005) → {'PASS' if ic_ok else 'FAIL'}")
    else:
        log("    Ghostscript 미설치 — inkcov 생략 (gswin64c 또는 gs 필요)")
    log()

    # ---------- AC-2: 경량 (1회 임베드) ----------
    s_in = os.path.getsize(SAMPLE)
    s_24 = os.path.getsize(COMPOSED)
    s_48 = os.path.getsize(COMPOSED_X2)
    embed_count = len(forms)
    forms48 = find_design_xobjects(pikepdf.open(COMPOSED_X2))
    per_placement = (s_48 - s_24) / max(n48 - n24, 1)
    # 기준1 (지시서 택1): 임베드 1회 + 배치 2배 시 배치당 소량(<1KB) 선형 증가
    crit1 = (embed_count == 1) and (len(forms48) == 1) and (per_placement < 1024)
    log("[AC-2] 파일 크기 경량 (Form XObject 재사용)")
    log(f"    입력 디자인 크기      : {s_in:,} bytes")
    log(f"    배치 {n24}회 출력 크기 : {s_24:,} bytes")
    log(f"    배치 {n48}회 출력 크기 : {s_48:,} bytes (24→48 증가폭 {s_48 - s_24:,} bytes, "
        f"배치당 약 {per_placement:.0f} bytes)")
    log(f"    디자인 임베드 횟수    : 24회본={embed_count} / 48회본={len(forms48)} (반드시 1)")
    log(f"    기준1: 1회 임베드 + 배치당 <1KB 선형 증가 → {'PASS' if crit1 else 'FAIL'}")
    # 기준2 (출력 < 입력x1.5)는 실제 디자인 규모에서 의미가 있으므로 무거운 샘플로 별도 측정
    # (기지색 샘플은 ~650 bytes라 PDF 고정 오버헤드가 지배 — 비율 비교가 무의미)
    heavy = os.path.join(HERE, "sample_design_cmyk_heavy.pdf")
    heavy_out = os.path.join(HERE, "output_composed_heavy.pdf")
    make_heavy_sample(heavy)
    n_h = compose(heavy_out, repeat=1, sample=heavy)
    s_hin = os.path.getsize(heavy)
    s_hout = os.path.getsize(heavy_out)
    heavy_embeds = len(find_design_xobjects(pikepdf.open(heavy_out)))
    crit2 = (heavy_embeds == 1) and (s_hout < s_hin * 1.5)
    log(f"    [실제 규모 보강] 무거운 샘플 {s_hin:,} bytes → {n_h}회 배치 출력 {s_hout:,} bytes "
        f"(입력 대비 {s_hout / s_hin:.3f}배, 기준 <1.5배, 임베드 {heavy_embeds}회)")
    log(f"    기준2: 출력 < 입력x1.5 → {'PASS' if crit2 else 'FAIL'}")
    size_ok = crit1 and crit2
    overall &= size_ok
    log(f"    → {'PASS' if size_ok else 'FAIL'} (기준1+2 모두 충족)")
    log()

    # ---------- AC-3: 합성 정확성 ----------
    page0 = out.pages[0].obj["/Contents"].read_bytes()
    has_clip = b"W n" in page0
    has_cm = re.search(rb"[\d.]+ 0 0 [\d.]+ [\d.]+ [\d.]+ cm", page0) is not None
    do_count = sum(p.obj["/Contents"].read_bytes().count(b" Do") for p in out.pages)
    no_images = True
    for o in out.objects:
        try:
            if isinstance(o, pikepdf.Stream) and o.get("/Subtype") == pikepdf.Name("/Image"):
                no_images = False
        except Exception:
            pass
    ac3 = has_clip and has_cm and do_count == n24 and no_images
    overall &= ac3
    log("[AC-3] 합성 정확성")
    log(f"    클리핑(W n) 적용: {has_clip} / 스케일(cm) 적용: {has_cm}")
    log(f"    배치 참조(Do) 횟수: {do_count} (기대 {n24}) / 래스터 이미지 0개: {no_images} (벡터 유지)")
    log(f"    → {'PASS' if ac3 else 'FAIL'}")
    log()

    log(f"========== 종합: {'PASS — 가설 증명됨' if overall else 'FAIL — 항목 확인 필요'} ==========")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n로그 저장: {REPORT}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
