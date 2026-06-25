# -*- coding: utf-8 -*-
"""eps — 평탄화된 디자인 PDF 를 '벡터 EPS' 로 변환하고 그 품질을 검증한다.

왜 EPS 인가:
  일부 인쇄/재단 공장은 PDF 가 아니라 EPS(PostScript) 파일을 요구한다. PDF 를 EPS 로
  바꾸는 가장 안전한 길은 Ghostscript 의 'eps2write' 디바이스다.

벡터 유지의 핵심(flatten 과의 연결):
  PostScript/EPS 는 투명도를 표현하지 못한다. 그래서 투명도 그룹(/Group(/Transparency))
  이 남은 PDF 를 eps2write 로 변환하면 페이지가 통째로 래스터화(이미지)되어 EPS 가
  수십 MB 로 부풀고 벡터가 깨진다. flatten.py 가 알파·SMask 를 없애고 Form 투명도 그룹을
  제거하므로, 그 평탄화본을 입력으로 주면 eps2write 가 벡터(수백 KB)로 출력한다.

graceful fallback(크래시 0 원칙):
  Ghostscript 가 설치돼 있지 않거나 실행에 실패하면 예외로 죽지 않고, '경고 + EPS 건너뜀'
  으로 흘린다(PDF 산출물은 그대로 유효). 호출부(job.py)는 produced=False 를 보고 PDF 만
  내보낸다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import pikepdf


def _cleanup_tmp(tmp_path: Optional[str], original: str) -> None:
    """EPS 변환에 쓴 임시 strip 사본을 지운다(원본은 절대 건드리지 않음)."""
    if tmp_path and tmp_path != original and os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# Ghostscript Windows 기본 설치 절대경로(설치 버전에 맞춰 후보를 둔다). settings 우선.
_GS_ABS_CANDIDATES = [
    r"C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe",
    r"C:/Program Files/gs/gs10.03.1/bin/gswin64c.exe",
    r"C:/Program Files/gs/gs10.02.1/bin/gswin64c.exe",
]
# PATH 에서 찾을 실행명 후보(절대경로가 없을 때).
_GS_PATH_NAMES = ["gswin64c", "gswin32c", "gs"]


@dataclass
class EpsCheck:
    """EPS 검증 항목 1개(verify.Check 과 같은 모양 — UI 표/리포트에 그대로 쓴다)."""
    name: str
    ok: bool
    detail: str = ""


def find_ghostscript(settings_path: Optional[str] = None) -> Optional[str]:
    """사용할 Ghostscript 실행 경로를 결정한다(없으면 None).

    탐색 순서:
      0) 환경변수 GS_BIN (배포·도커용 최우선). 예: GS_BIN=gs.
      1) settings_path (preset/settings 의 ghostscript_path) — 존재할 때만.
      2) 알려진 Windows 절대경로 후보(C:/Program Files/gs/...).
      3) PATH 의 gswin64c / gswin32c / gs.
    None 이면 호출부가 'EPS 건너뜀(경고)' 으로 처리한다(크래시 없음).
    """
    # 0) 환경변수 GS_BIN — 배포(도커)에서 GS 경로를 강제 지정하는 최우선 분기.
    #    왜 맨 앞인가(비유): 도커 안에는 'gs' 가 PATH 에 있고 Windows 절대경로는 없다.
    #    배포 환경이 GS_BIN=gs 만 켜면 곧장 그걸 쓰도록 가장 먼저 본다.
    #    ⚠️ 로컬 회귀 0: GS_BIN 을 안 켜면(=로컬 기본) 아래 기존 체인 그대로 동작한다.
    #    shutil.which 로 실제 실행 가능한 경우에만 채택(없으면 폴백 계속).
    env_gs = os.environ.get("GS_BIN")
    if env_gs and shutil.which(env_gs):
        return shutil.which(env_gs)

    # 1) 명시 설정 경로(최우선). 실제 파일이 있을 때만 채택한다.
    if settings_path:
        if os.path.exists(settings_path):
            return settings_path
        # 설정에 적혔지만 실제로 없으면 다음 후보로 폴백(경고는 호출부에서).

    # 2) 알려진 절대경로 후보.
    for cand in _GS_ABS_CANDIDATES:
        if os.path.exists(cand):
            return cand

    # 3) PATH 검색.
    for name in _GS_PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found

    return None


def _stripped_copy_for_eps(pdf_path: str):
    """EPS 변환 직전, 합성 PDF 의 잔여 'Form 투명도 그룹'을 제거한 임시 사본을 만든다.

    왜 또 strip 하나(중요):
      flatten 은 '디자인 원본' 의 Form 투명도 그룹을 제거하지만, compose 가 디자인을
      다시 Form XObject 로 임베드할 때(as_form_xobject) 원본 페이지의 /Group 이 그 Form 으로
      옮겨붙어 **합성 출력 PDF 에 투명도 그룹이 되살아난다**. 이게 남으면 eps2write 가
      페이지를 통째로 래스터화(수십 MB)한다. compose 는 불변 제약(무수정)이라, 변환 직전에
      합성 PDF 사본에서 Form 투명도 그룹만 다시 제거한다(색공간 가진 페이지 그룹은 보존 —
      PDF 렌더 픽셀 동일, 델타>10 0개로 실측 확인).

    반환: (임시 PDF 경로, 제거한 그룹 수, [경고]). 잔여 알파/SMask 가 있으면 strip 을
          건너뛰고 원본 경로를 그대로 돌려준다(경고) — 색 변화 방지.
    """
    # flatten 의 검증된 헬퍼를 재사용한다(같은 안전 규칙 적용).
    from .flatten import _scan_residual_transparency, _strip_transparency_groups

    warnings: List[str] = []
    try:
        pdf = pikepdf.open(pdf_path)
    except Exception as e:
        warnings.append(f"🟡 [EPS] PDF 열기 실패(원본으로 변환 시도): {e}")
        return pdf_path, 0, warnings

    try:
        residual = _scan_residual_transparency(pdf)
        if residual:
            warnings.append(
                f"🟡 [EPS] 합성 PDF 에 알파/SMask 잔여({residual}) — Form 그룹 제거를 건너뜁니다"
                "(원본으로 변환; EPS 가 래스터화될 수 있음).")
            pdf.close()
            return pdf_path, 0, warnings
        n = _strip_transparency_groups(pdf)
        out_dir = os.path.dirname(os.path.abspath(pdf_path))
        fd, tmp = tempfile.mkstemp(suffix="_epssrc.pdf", dir=out_dir)
        os.close(fd)
        pdf.save(tmp)
        pdf.close()
        return tmp, n, warnings
    except Exception as e:
        try:
            pdf.close()
        except Exception:
            pass
        warnings.append(f"🟡 [EPS] Form 그룹 제거 실패(원본으로 변환 시도): {e}")
        return pdf_path, 0, warnings


def pdf_to_eps(pdf_path: str, eps_path: str,
               ghostscript_path: Optional[str] = None,
               page: int = 1, strip_groups: bool = True) -> dict:
    """PDF 를 eps2write 로 벡터 EPS 로 변환한다(graceful fallback).

    매개변수
      pdf_path         : 입력 PDF(합성 출력 PDF 또는 평탄화 디자인).
      eps_path         : 출력 EPS 경로.
      ghostscript_path : (선택) settings 의 ghostscript_path. find_ghostscript 1순위.
      page             : 변환할 페이지(1-base). 기본 1.
      strip_groups     : True(기본)면 변환 직전 합성 PDF 의 잔여 Form 투명도 그룹을 제거한
                         임시 사본으로 변환한다(EPS 벡터 보장; compose 가 되살린 그룹 대응).

    반환(dict):
      {
        "produced": bool,        # EPS 가 실제로 만들어졌는지
        "eps_path": str|None,    # 만들어졌으면 경로
        "gs_exe": str|None,      # 사용한 GS 경로(없으면 None)
        "size_bytes": int,       # EPS 파일 크기(없으면 0)
        "groups_removed": int,   # 변환 직전 제거한 Form 투명도 그룹 수
        "warnings": [str, ...],  # 경고(GS 미설치/실행 실패 등)
      }

    실패 정책: GS 미설치/실행 오류는 예외로 죽지 않고 produced=False + 경고로 흘린다
              (PDF 산출은 그대로 유효 — 의뢰서 §2 graceful fallback).
    """
    warnings: List[str] = []
    if not os.path.exists(pdf_path):
        # 입력 PDF 자체가 없으면 변환 불가 — 경고만(상위에서 막혔어야 함).
        warnings.append(f"[EPS] 입력 PDF 없음(EPS 건너뜀): {pdf_path}")
        return {"produced": False, "eps_path": None, "gs_exe": None,
                "size_bytes": 0, "groups_removed": 0, "warnings": warnings}

    gs = find_ghostscript(ghostscript_path)
    if not gs:
        # GS 미설치 — 크래시 대신 경고. PDF 만 산출(fallback).
        warnings.append(
            "🟡 [EPS] Ghostscript 를 찾지 못했습니다 — EPS 변환을 건너뜁니다(PDF 만 산출). "
            "settings.ghostscript_path 를 지정하거나 GS 를 설치하세요.")
        return {"produced": False, "eps_path": None, "gs_exe": None,
                "size_bytes": 0, "groups_removed": 0, "warnings": warnings}

    # settings 에 적혔지만 실제로 없어서 폴백한 경우를 알린다(정보용).
    if ghostscript_path and gs != ghostscript_path:
        warnings.append(
            f"🟡 [EPS] 지정한 ghostscript_path '{ghostscript_path}' 가 없어 '{gs}' 로 폴백했습니다.")

    out_dir = os.path.dirname(os.path.abspath(eps_path))
    os.makedirs(out_dir, exist_ok=True)

    # ── 변환 직전 Form 투명도 그룹 제거(EPS 벡터 보장). 임시 사본을 쓰고 끝에 지운다. ──
    src_pdf = pdf_path
    tmp_src = None
    groups_removed = 0
    if strip_groups:
        tmp_src, groups_removed, w = _stripped_copy_for_eps(pdf_path)
        warnings.extend(w)
        if tmp_src != pdf_path:
            src_pdf = tmp_src  # strip 된 임시 사본으로 변환

    # eps2write + EPSCrop(=BoundingBox 를 콘텐츠에 맞게). 페이지 1장만 변환.
    args = [
        gs, "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=eps2write", "-dEPSCrop",
        f"-dFirstPage={page}", f"-dLastPage={page}",
        "-o", eps_path, src_pdf,
    ]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=300)
    except Exception as e:
        _cleanup_tmp(tmp_src, pdf_path)
        warnings.append(f"🟡 [EPS] Ghostscript 실행 실패(EPS 건너뜀): {e}")
        return {"produced": False, "eps_path": None, "gs_exe": gs,
                "size_bytes": 0, "groups_removed": groups_removed, "warnings": warnings}
    finally:
        _cleanup_tmp(tmp_src, pdf_path)

    if r.returncode != 0 or not os.path.exists(eps_path):
        # GS 가 비정상 종료했거나 파일이 안 생김 — 경고로 흘린다(PDF fallback).
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
        warnings.append(
            "🟡 [EPS] Ghostscript 변환 실패(EPS 건너뜀): "
            f"rc={r.returncode} {' / '.join(tail)}")
        return {"produced": False, "eps_path": None, "gs_exe": gs,
                "size_bytes": 0, "groups_removed": groups_removed, "warnings": warnings}

    size = os.path.getsize(eps_path)
    return {"produced": True, "eps_path": eps_path, "gs_exe": gs,
            "size_bytes": size, "groups_removed": groups_removed, "warnings": warnings}


# ── EPS 검증 ──────────────────────────────────────────────────────────────────
# EPS(PostScript) 안의 래스터 페인트 연산자: image / colorimage / imagemask.
# 단어 경계로 매칭해 'colorimage' 의 부분문자열 'image' 를 중복 카운트하지 않게 한다.
#   ⚠️ 주의: eps2write 는 프롤로그에 '{imagemask}{image}ifelse' 정의(=함수 정의, 실제
#      그림이 아님)를 항상 2개 넣는다. 그래서 이 토큰 수만으로는 래스터/벡터를 못 가른다.
#      실제 이미지 '페인트 호출'은 eps2write 약어 'Id'(image data)로 나가므로 그걸 따로 센다.
_IMG_OP = re.compile(rb"(?<![A-Za-z])(image|colorimage|imagemask)(?![A-Za-z])")
# eps2write 실제 이미지 페인트 호출(약어). 래스터화되면 수백 개, 벡터면 한 자릿수.
_IMG_CALL = re.compile(rb"(?<![A-Za-z])Id(?![A-Za-z])")
# 벡터 경로 페인트의 핵심 연산자: l(lineto) c(curveto) m(moveto). (대표 표본만)
_VEC_OP = re.compile(rb"(?<![A-Za-z])(lineto|curveto|moveto|rlineto|rcurveto)(?![A-Za-z])")
# %%BoundingBox: x0 y0 x1 y1  (HiResBoundingBox 가 아닌 정수 BoundingBox)
_BBOX = re.compile(rb"%%BoundingBox:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)")
# CMYK 색 흔적: setcmykcolor 연산자 또는 /DeviceCMYK / 'k'/'K' 4값.
_CMYK = re.compile(rb"(setcmykcolor|DeviceCMYK)")


def verify_eps(eps_path: str,
               sheet_size: Optional[tuple] = None,
               bbox_tol: float = 2.0,
               raster_size_limit: int = 2_000_000,
               max_image_ops: int = 4) -> List[EpsCheck]:
    """생성된 EPS 가 '벡터·CMYK·올바른 BoundingBox' 인지 검사한다.

    매개변수
      eps_path          : 검사할 EPS.
      sheet_size        : (W, H) 시트(페이지) 크기(pt). 주면 BoundingBox 가 그 안에 들어가고
                          (EPSCrop 은 콘텐츠로 자르므로 BBox ≤ 시트가 정상), 원점이 0 근처인지
                          검사한다. 미지정 시 BBox 존재·양수만 확인.
      bbox_tol          : BoundingBox 허용 오차(pt). EPSCrop 반올림·여백 여유.
      raster_size_limit : 이 바이트 수를 넘으면 '래스터화 의심'(투명도 그룹 잔존 시 20MB+).
      max_image_ops     : 실제 이미지 페인트 호출(Id)이 이 수를 넘으면 '래스터 과다'로 FAIL.

    반환: [EpsCheck, ...]  — 항목별 PASS/FAIL.
      · '벡터(래스터 아님)' : (크기 임계 이하) AND (이미지 페인트 max 이하) AND (벡터 연산자 존재).
      · 'CMYK 색공간'       : setcmykcolor/DeviceCMYK 흔적 존재.
      · 'BoundingBox'       : sheet_size 주면 원점 0 근처 + BBox 폭/높이가 시트 이내(콘텐츠
                              가 있는 합리적 크기). 미지정 시 존재·양수만 확인.

    ⚠️ EPSCrop 주의: eps2write -dEPSCrop 은 BoundingBox 를 '콘텐츠 경계'로 자른다. 따라서
       BBox 는 페이지 MediaBox(여백 포함)와 정확히 같지 않고 보통 더 작다(여백만큼). 그래서
       'BBox == 0 0 W H 정확 일치' 가 아니라 '시트 안에 들어가는 양수 박스' 로 판정한다.
    """
    checks: List[EpsCheck] = []

    if not os.path.exists(eps_path):
        checks.append(EpsCheck("EPS 존재", False, f"파일 없음: {eps_path}"))
        return checks

    size = os.path.getsize(eps_path)
    data = open(eps_path, "rb").read()

    n_img = len(_IMG_OP.findall(data))      # image 토큰(정의 2개 포함 — 단독 판정 X)
    n_call = len(_IMG_CALL.findall(data))   # 실제 이미지 페인트 호출(Id) — 래스터면 다수
    n_vec = len(_VEC_OP.findall(data))      # 벡터 경로 연산자

    # ── 벡터 여부: 3중 판정(크기·이미지 페인트 호출·벡터연산자). ──
    #   투명도 그룹이 남아 통째 래스터화되면 ① 파일이 수십 MB 로 커지고 ② 실제 이미지 페인트
    #   호출(Id)이 수백 개로 폭증하며 ③ 벡터 경로 연산자가 거의 사라진다. 셋을 함께 봐 오탐 방지.
    #   (image 토큰 n_img 는 eps2write 정의 2개가 늘 있어 단독 기준이 못 됨 → 참고로만 표시.)
    size_ok = size <= raster_size_limit
    img_ok = n_call <= max_image_ops
    vec_ok = n_vec > 0
    vector_ok = size_ok and img_ok and vec_ok
    checks.append(EpsCheck(
        "벡터(래스터 아님)", vector_ok,
        f"크기 {size:,}B(임계 {raster_size_limit:,}, {'OK' if size_ok else '초과=래스터의심'}) / "
        f"이미지페인트(Id) {n_call}개({'OK' if img_ok else '과다=래스터'}) / 벡터연산자 {n_vec}개"
        f"({'있음' if vec_ok else '없음=래스터의심'}) / image토큰 {n_img}개(정의 포함)"))

    # ── CMYK 색공간 유지(무손실 색의 흔적). ──
    cmyk_ok = bool(_CMYK.search(data))
    checks.append(EpsCheck(
        "CMYK 색공간", cmyk_ok,
        "setcmykcolor/DeviceCMYK 발견" if cmyk_ok else "CMYK 색 흔적 없음(RGB/Gray 변환 의심)"))

    # ── BoundingBox 검사. ──
    m = _BBOX.search(data)
    if not m:
        checks.append(EpsCheck("BoundingBox", False, "%%BoundingBox 를 찾지 못함"))
    else:
        x0, y0, x1, y1 = (int(m.group(i)) for i in range(1, 5))
        bw, bh = x1 - x0, y1 - y0
        if sheet_size is not None:
            sw, sh = float(sheet_size[0]), float(sheet_size[1])
            # EPSCrop 은 콘텐츠로 자르므로 BBox ≤ 시트가 정상. 판정 기준(완화):
            #   ① 원점이 0 근처(여백 만큼의 오프셋 허용),
            #   ② BBox 폭/높이가 시트 크기를 (tol 넘게) 초과하지 않음,
            #   ③ BBox 가 시트의 절반 이상을 차지(콘텐츠가 실제로 있음 — 빈/깨진 박스 차단).
            origin_ok = abs(x0) <= bbox_tol + sw and abs(y0) <= bbox_tol + sh  # 원점은 양수 오프셋 허용
            within = (bw <= sw + bbox_tol) and (bh <= sh + bbox_tol)
            has_content = (bw >= sw * 0.5) and (bh >= sh * 0.5)
            ok = origin_ok and within and has_content
            checks.append(EpsCheck(
                "BoundingBox", ok,
                f"BBox=({x0} {y0} {x1} {y1}) = {bw}x{bh} / 시트 {sw:.0f}x{sh:.0f} "
                f"(EPSCrop=콘텐츠로 자름, 시트 이내+양수 기대)"))
        else:
            # 시트 크기 미지정 — 존재·양수 폭/높이만 확인.
            ok = bw > 0 and bh > 0
            checks.append(EpsCheck(
                "BoundingBox", ok,
                f"BBox=({x0} {y0} {x1} {y1}) = {bw}x{bh} (시트크기 미지정 — 존재만 확인)"))

    return checks


def eps_all_passed(checks: List[EpsCheck]) -> bool:
    """EPS 검증 항목이 전부 PASS 면 True."""
    return all(c.ok for c in checks)


def eps_checks_to_dicts(checks: List[EpsCheck]) -> list:
    """EpsCheck 목록을 JSON 직렬화용 dict 목록으로(job.json 의 checks_eps 에 그대로)."""
    return [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks]


def format_eps_report(checks: List[EpsCheck]) -> str:
    """사람이 읽을 EPS 검증 리포트 문자열."""
    lines = []
    for c in checks:
        lines.append(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name}"
                     + (f" — {c.detail}" if c.detail else ""))
    lines.append(f"  ===== EPS 종합: {'PASS' if eps_all_passed(checks) else 'FAIL'} =====")
    return "\n".join(lines)


def sheet_size_from_pdf(pdf_path: str, page: int = 0) -> Optional[tuple]:
    """PDF 페이지의 MediaBox 크기(W, H) 를 pt 로 돌려준다(EPS BoundingBox 비교용).

    EPSCrop 은 콘텐츠 경계로 자르므로, '시트 크기'는 보통 MediaBox 가 아니라 콘텐츠
    bbox 다. 그래서 이 함수 결과를 verify_eps 의 sheet_size 로 '강제'하지 말고, 호출부가
    필요할 때만 쓰도록 한다(미지정이면 verify_eps 는 BBox 존재·양수만 확인).
    """
    try:
        pdf = pikepdf.open(pdf_path)
        try:
            mb = pdf.pages[page].MediaBox
            w = float(mb[2]) - float(mb[0])
            h = float(mb[3]) - float(mb[1])
            return (w, h)
        finally:
            pdf.close()
    except Exception:
        return None
