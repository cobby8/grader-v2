# -*- coding: utf-8 -*-
"""출력물 검증 — 합성 PDF가 공장 전달 기준을 만족하는지 자동 검사.

PoC의 AC-1/2/3을 '실제 디자인(ICCBased CMYK)'에도 견고하게 동작하도록 일반화했다.
핵심 전략은 **바이트 동일성**: 디자인을 Form XObject로 임베드할 때 콘텐츠 스트림이
원본과 한 바이트도 다르지 않으면, 색공간이 device CMYK든 ICCBased CMYK든 무손실 보존이
증명된다. 그 동일 사본이 정확히 1개면 '단일 임베드'도 동시에 증명된다.

각 검사는 Check(name, ok, detail) — UI 표/리포트에 그대로 쓴다.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pikepdf

CMYK_OP = re.compile(rb"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(k|K)(?![\w])")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


# ── 저수준 추출기 ────────────────────────────────────────────────────────────
def extract_cmyk_ops(stream_bytes: bytes):
    """k/K 연산자의 device CMYK 4값을 등장 순서대로 추출 (device CMYK 디자인용 보조검사)."""
    out = []
    for m in CMYK_OP.finditer(stream_bytes):
        out.append((m.group(5).decode(), tuple(float(m.group(i)) for i in range(1, 5))))
    return out


def find_form_xobjects(pdf: pikepdf.Pdf) -> List[pikepdf.Stream]:
    forms = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == pikepdf.Name("/Form"):
                forms.append(obj)
        except Exception:
            pass
    return forms


def count_images(pdf: pikepdf.Pdf) -> int:
    n = 0
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == pikepdf.Name("/Image"):
                n += 1
        except Exception:
            pass
    return n


def scan_transparency(pdf: pikepdf.Pdf) -> List[str]:
    """투명도 흔적 — ca/CA<1, SMask, BlendMode≠Normal. 발견 시 EPS/출력에서 래스터화 위험."""
    issues = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == pikepdf.Name("/ExtGState"):
                for key in ("/ca", "/CA"):
                    if key in obj and float(obj[key]) < 1.0:
                        issues.append(f"{key}={float(obj[key]):.3g}")
                if "/SMask" in obj and obj["/SMask"] != pikepdf.Name("/None"):
                    issues.append("SMask")
                if "/BM" in obj and obj["/BM"] not in (pikepdf.Name("/Normal"),):
                    issues.append(f"BM={obj['/BM']}")
        except Exception:
            pass
    return issues


def _classify_colorspace(v) -> str:
    """색공간 객체를 계열로 분류: CMYK / RGB / Gray / Lab / Unknown."""
    try:
        if isinstance(v, pikepdf.Name):
            s = str(v)
            if s == "/DeviceCMYK":
                return "CMYK"
            if s == "/DeviceRGB":
                return "RGB"
            if s == "/DeviceGray":
                return "Gray"
            return "Unknown"
        if isinstance(v, pikepdf.Array) and len(v) >= 1:
            head = str(v[0])
            if head == "/ICCBased":
                n = None
                try:
                    n = int(v[1].get("/N"))
                except Exception:
                    pass
                return {4: "CMYK", 3: "RGB", 1: "Gray"}.get(n, "Unknown")
            if head in ("/CalRGB", "/Lab"):
                return "RGB" if head == "/CalRGB" else "Lab"
            if head == "/CalGray":
                return "Gray"
            if head in ("/Separation", "/DeviceN") and len(v) >= 3:
                return _classify_colorspace(v[2])  # alternate space
            if head == "/Indexed" and len(v) >= 2:
                return _classify_colorspace(v[1])  # base space
    except Exception:
        pass
    return "Unknown"


def non_cmyk_colorspaces(pdf: pikepdf.Pdf) -> List[str]:
    """RGB/Lab 색공간이 끼어들었는지 (색 변환 발생 신호). CMYK·Gray는 허용."""
    bad = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                res = obj.get("/Resources")
                if res and "/ColorSpace" in res:
                    for k, v in res["/ColorSpace"].items():
                        fam = _classify_colorspace(v)
                        if fam in ("RGB", "Lab"):
                            bad.append(f"{k}:{fam}")
        except Exception:
            pass
    return bad


# ── Ghostscript inkcov 교차검증 ──────────────────────────────────────────────
def gs_exe() -> Optional[str]:
    for cand in ("gswin64c", "gs"):
        if shutil.which(cand):
            return cand
    return None


def inkcov(pdf_path: str, page: int = 1) -> Optional[Tuple[float, float, float, float]]:
    exe = gs_exe()
    if not exe:
        return None
    args = [exe, "-dNOPAUSE", "-dBATCH", "-dQUIET",
            f"-dFirstPage={page}", f"-dLastPage={page}",
            "-o", "-", "-sDEVICE=inkcov", pdf_path]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    m = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+CMYK OK", r.stdout)
    return tuple(float(m.group(i)) for i in range(1, 5)) if m else None


# ── 종합 검증 ────────────────────────────────────────────────────────────────
def verify_output(out_path: str, design_path: str, expected_placements: int) -> List[Check]:
    """합성 출력물을 디자인 원본과 대조해 전 항목 검사 (device/ICC CMYK 모두 대응)."""
    checks: List[Check] = []
    out = pikepdf.open(out_path)
    src = pikepdf.open(design_path)
    try:
        src_form_bytes = src.pages[0].as_form_xobject().read_bytes()
        forms = find_form_xobjects(out)
        copies = [f for f in forms if f.read_bytes() == src_form_bytes]

        # AC-1: 디자인 무손실 보존 (바이트 동일) — 색공간 종류 무관하게 증명
        checks.append(Check(
            "디자인 무손실 보존(바이트 동일)", len(copies) >= 1,
            f"원본과 바이트 동일한 Form {len(copies)}개 / 전체 Form {len(forms)}개"))

        # AC-2: 단일 임베드 — 동일 사본이 정확히 1개 (배치 수와 무관)
        checks.append(Check(
            "디자인 단일 임베드", len(copies) == 1,
            f"디자인 사본 {len(copies)}개 (배치 {expected_placements}회와 무관하게 1이어야 함)"))

        # 보조: device CMYK 디자인이면 색값 리스트도 직접 대조
        in_ops = extract_cmyk_ops(src.pages[0].obj["/Contents"].read_bytes())
        if in_ops:
            out_ops = extract_cmyk_ops(copies[0].read_bytes()) if copies else []
            checks.append(Check("device CMYK 색값 일치", in_ops == out_ops,
                                f"입력 {len(in_ops)} vs 출력 {len(out_ops)}"))

        # AC-1: 색공간 CMYK 계열 유지 (RGB/Lab 유입 없음)
        bad_cs = non_cmyk_colorspaces(out)
        checks.append(Check("색공간 CMYK 계열 유지", len(bad_cs) == 0,
                            "CMYK 계열만 사용" if not bad_cs else f"RGB/Lab {len(bad_cs)}건: {bad_cs}"))

        # 안전장치: 투명도 (있으면 출력 시 래스터화 → 원본 평탄화 필요). 출력 유효성상 FAIL.
        trans = scan_transparency(out)
        checks.append(Check("투명도 없음", len(trans) == 0,
                            "없음" if not trans
                            else f"{len(trans)}건({'; '.join(trans)}) → 원본에서 평탄화 후 재등록 필요"))

        # AC-3: 합성 정확 — 클립/스케일/배치 횟수/래스터 미추가
        all_content = b"\n".join(p.obj["/Contents"].read_bytes() for p in out.pages)
        checks.append(Check("클리핑(W n) 적용", b"W n" in all_content, ""))
        checks.append(Check("스케일(cm) 적용",
                            re.search(rb"[\d.]+ 0 0 [\d.]+ [\d.]+ [\d.]+ cm", all_content) is not None, ""))
        do_count = all_content.count(b" Do")
        checks.append(Check("배치 횟수 일치", do_count == expected_placements,
                            f"Do {do_count}회 (기대 {expected_placements})"))
        img_added = count_images(out) - count_images(src)
        checks.append(Check("합성이 래스터 미추가", img_added <= 0,
                            "추가 이미지 없음(벡터 유지)" if img_added <= 0
                            else f"합성 중 이미지 {img_added}개 추가됨"))

        return checks
    finally:
        out.close()
        src.close()


def all_passed(checks: List[Check]) -> bool:
    return all(c.ok for c in checks)


def format_report(checks: List[Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name}" + (f" — {c.detail}" if c.detail else ""))
    lines.append(f"  ===== 종합: {'PASS' if all_passed(checks) else 'FAIL'} =====")
    return "\n".join(lines)
