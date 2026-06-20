# -*- coding: utf-8 -*-
"""flatten — 디자인 PDF의 투명도를 '벡터 상태 그대로' 평탄화한다.

왜 필요한가:
  PostScript/EPS 는 투명도를 표현하지 못한다. 그래서 투명도가 남아 있는 디자인을
  Ghostscript 로 EPS 변환하면 페이지 전체가 래스터화(이미지)되어 벡터가 깨진다.
  (verify_output 의 "투명도 없음" 검사가 이것을 FAIL 로 막는다.)

이 모듈이 하는 일(식당 비유 — 미리 색을 섞어두기):
  반투명 요소(예: 20% 흰색 엠블럼)는 "흰색 + 알파"로 그려져 있다. 이걸 인쇄 직전에
  섞는 대신, **미리 배경색과 섞은 불투명 단색**으로 바꿔 둔다.
      합성색 c' = α·전경색 + (1-α)·배경색   (채널별, Normal 블렌드 가정)
  이렇게 하면 화면 결과는 똑같으면서 투명도(α<1)가 사라져 EPS 가 벡터로 유지된다.

적용 범위(1차):
  "반투명 XObject 1~수 개가 단색 배경(유니폼 본판) 위에 Normal 블렌드로 얹힌" 흔한 구조.
  배경색은 페이지에서 면적이 가장 큰 불투명 채움(=본판)을 자동 감지하거나 인자로 받는다.
  ⚠️ 한계: 반투명 요소가 여러 다른 색 위에 걸쳐 있으면 단일 배경 가정이 어긋날 수 있다
     (그 경우 경고를 남긴다). SMask(소프트 마스크)·非Normal 블렌드는 1차 범위 밖(경고).
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import pikepdf
from pikepdf import parse_content_stream

CMYK = Tuple[float, float, float, float]


# ── 행렬(CTM) 유틸 ───────────────────────────────────────────────────────────
def _mat_mul(m1, m2):
    """PDF 행렬 곱: cm 연산자는 현재 CTM 왼쪽에 곱해진다(new = m1 × m2)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _nums(operands):
    out = []
    for o in operands:
        try:
            out.append(float(o))
        except Exception:
            return None
    return out


# ── 배경색 자동 감지 ─────────────────────────────────────────────────────────
def detect_background_cmyk(pdf: pikepdf.Pdf, page_index: int = 0) -> Optional[CMYK]:
    """페이지에서 '면적이 가장 큰 불투명 4채널(CMYK) 채움'의 색을 배경으로 본다.

    유니폼 본판이 보통 가장 큰 단색 면적이므로 이 휴리스틱이 잘 맞는다.
    CTM 를 추적해 page 좌표계 bbox 면적으로 비교한다. 못 찾으면 None.
    """
    page = pdf.pages[page_index]
    areas: dict = {}  # color(tuple) -> 누적 면적
    ctm_stack: List[tuple] = []
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    fill_color: Optional[CMYK] = None
    pts: List[Tuple[float, float]] = []

    def add_pt(x, y):
        pts.append(_apply(ctm, x, y))

    for operands, op in parse_content_stream(page):
        o = str(op)
        n = _nums(operands)
        if o == "q":
            ctm_stack.append(ctm)
        elif o == "Q":
            ctm = ctm_stack.pop() if ctm_stack else ctm
        elif o == "cm" and n and len(n) >= 6:
            ctm = _mat_mul(tuple(n[:6]), ctm)
        elif o == "scn" and n and len(n) == 4:
            fill_color = tuple(round(v, 4) for v in n)
        elif o in ("k",) and n and len(n) == 4:
            fill_color = tuple(round(v, 4) for v in n)
        elif o == "m" and n and len(n) >= 2:
            add_pt(n[0], n[1])
        elif o == "l" and n and len(n) >= 2:
            add_pt(n[0], n[1])
        elif o == "c" and n and len(n) >= 6:
            add_pt(n[4], n[5])
        elif o in ("v", "y") and n and len(n) >= 4:
            add_pt(n[2], n[3])
        elif o == "re" and n and len(n) >= 4:
            x, y, w, h = n[:4]
            add_pt(x, y); add_pt(x + w, y + h)
        elif o in ("f", "F", "f*", "b", "b*", "B", "B*"):
            if pts and fill_color is not None:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                areas[fill_color] = areas.get(fill_color, 0.0) + area
            pts = []
        elif o in ("n", "S", "s", "W", "W*"):
            pts = []
    if not areas:
        return None
    return max(areas.items(), key=lambda kv: kv[1])[0]


# ── 투명 ExtGState / XObject 식별 ────────────────────────────────────────────
def _alpha_gstates(pdf: pikepdf.Pdf) -> dict:
    """ca 또는 CA 가 1 미만인 ExtGState 의 (이름 무관) 알파값을 모은다.
    반환: {ExtGState객체 id: alpha} 가 아니라, 페이지 리소스 이름→alpha 로 따로 푼다.
    """
    return {}  # (실제 매핑은 페이지 리소스에서 이름으로 찾으므로 여기선 미사용 — 자리표시)


def _transparent_xobjects(pdf: pikepdf.Pdf, page_index: int = 0) -> Tuple[dict, List[str]]:
    """페이지 콘텐츠를 훑어 'ca<1 상태에서 Do 된 XObject 이름 → 알파'를 찾는다.

    반환: ({xobject이름: alpha}, [경고 목록])
    """
    page = pdf.pages[page_index]
    res = page.obj.get("/Resources", {})
    egs = res.get("/ExtGState", {})

    # 이름 → alpha(min(ca,CA)) 매핑
    name_alpha = {}
    for name, g in egs.items():
        a = 1.0
        for key in ("/ca", "/CA"):
            if key in g:
                try:
                    a = min(a, float(g[key]))
                except Exception:
                    pass
        if a < 1.0:
            name_alpha[str(name)] = a

    warnings: List[str] = []
    cur_alpha = 1.0
    alpha_stack: List[float] = []
    found: dict = {}
    for operands, op in parse_content_stream(page):
        o = str(op)
        if o == "q":
            alpha_stack.append(cur_alpha)
        elif o == "Q":
            cur_alpha = alpha_stack.pop() if alpha_stack else 1.0
        elif o == "gs" and operands:
            nm = str(operands[0])
            cur_alpha = name_alpha.get(nm, 1.0)
        elif o == "Do" and operands:
            if cur_alpha < 1.0:
                found[str(operands[0])] = cur_alpha

    # SMask / 비-Normal 블렌드는 1차 범위 밖 — 있으면 경고만.
    for name, g in egs.items():
        if "/SMask" in g and g["/SMask"] != pikepdf.Name("/None"):
            warnings.append(f"SMask 있음({name}) — 1차 평탄화 범위 밖, 수동 확인 필요")
        if "/BM" in g and g["/BM"] not in (pikepdf.Name("/Normal"),):
            warnings.append(f"블렌드모드 {g['/BM']}({name}) — Normal 아님, 결과 색 다를 수 있음")
    return found, warnings


def _composite(fg: CMYK, bg: CMYK, alpha: float) -> CMYK:
    """Normal 블렌드 사전합성: c' = α·fg + (1-α)·bg (채널별)."""
    return tuple(round(alpha * f + (1.0 - alpha) * b, 4) for f, b in zip(fg, bg))


def _recolor_xobject_fills(pdf: pikepdf.Pdf, xobj, bg: CMYK, alpha: float) -> int:
    """XObject 내부의 모든 4채널 채움색(scn/k)을 배경에 합성한 불투명색으로 교체.
    반환: 교체한 색 지정 횟수.
    """
    ops = list(parse_content_stream(xobj))
    changed = 0
    new_ops = []
    for operands, op in ops:
        o = str(op)
        n = _nums(operands)
        if o in ("scn", "k") and n and len(n) == 4:
            c2 = _composite(tuple(n), bg, alpha)
            new_operands = [pikepdf.Object.parse(repr(v).encode()) for v in c2]
            new_ops.append((new_operands, op))
            changed += 1
        else:
            new_ops.append((operands, op))
    if changed:
        xobj.write(pikepdf.unparse_content_stream(new_ops))
    return changed


def flatten_transparency(in_path: str, out_path: str,
                         bg_cmyk: Optional[CMYK] = None,
                         page_index: int = 0) -> dict:
    """디자인 PDF 의 투명도를 벡터 상태로 평탄화해 out_path 에 저장한다.

    절차:
      1) 배경색 결정(인자 없으면 면적 최대 불투명 채움 자동 감지).
      2) ca<1 로 그려진 XObject 들을 찾아, 그 내부 채움색을 배경에 사전합성.
      3) 모든 ca/CA<1 ExtGState 를 1.0(불투명)으로 바꿈.
    반환(dict): {bg, flattened_xobjects, recolored_fills, warnings, transparency_left}
    """
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"디자인 파일 없음: {in_path}")
    pdf = pikepdf.open(in_path)

    bg = bg_cmyk or detect_background_cmyk(pdf, page_index)
    warnings: List[str] = []
    if bg is None:
        warnings.append("배경색 자동 감지 실패 — 흰색(0,0,0,0)으로 가정. bg_cmyk 지정 권장.")
        bg = (0.0, 0.0, 0.0, 0.0)

    trans, w2 = _transparent_xobjects(pdf, page_index)
    warnings.extend(w2)

    res = pdf.pages[page_index].obj.get("/Resources", {})
    xobjs = res.get("/XObject", {})
    recolored = 0
    flattened_names = []
    for name, alpha in trans.items():
        key = pikepdf.Name(name if name.startswith("/") else "/" + name)
        if key in xobjs:
            recolored += _recolor_xobject_fills(pdf, xobjs[key], bg, alpha)
            flattened_names.append(name)

    # 모든 알파<1 ExtGState 를 불투명으로(페이지/XObject 리소스 전부 순회)
    fixed = 0
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == pikepdf.Name("/ExtGState"):
                for key in ("/ca", "/CA"):
                    if key in obj and float(obj[key]) < 1.0:
                        obj[key] = pikepdf.Object.parse(b"1.0")
                        fixed += 1
        except Exception:
            pass

    # ── 투명도 그룹(/Group <</S /Transparency>>) 제거 ──────────────────────────
    #   왜 필요한가(EPS 벡터 유지의 마지막 빗장):
    #     알파(ca/CA)·SMask 를 다 없애도, 페이지나 Form XObject 에 '투명도 그룹' 표지판
    #     (/Group <</S /Transparency>>)이 남아 있으면 Ghostscript eps2write 가 "여긴 투명
    #     구역"이라 보고 그 영역을 통째로 래스터화(이미지화)해 벡터가 깨질 수 있다.
    #     알파를 전부 1.0 으로 바꾸고 SMask 가 없으면, 그 그룹은 '아무 합성 효과도 없는'
    #     껍데기다 → 표지판만 떼어내도 화면 결과(색·모양)는 한 픽셀도 변하지 않는다.
    #   ⚠️ 안전장치(의뢰서 요구):
    #     떼기 '직전'에 잔여 알파(ca/CA<1)·SMask 를 다시 한 번 스캔한다. 하나라도 남아
    #     있으면 그룹을 떼면 합성 결과가 달라질 수 있으므로 제거를 건너뛰고 경고만 남긴다.
    groups_removed = 0
    residual = _scan_residual_transparency(pdf)  # (알파/SMask 잔여 목록)
    if residual:
        # 잔여 투명도가 있으면 Group 제거는 위험 → 건너뜀(경고). verify 가 최종 판정.
        warnings.append(
            "🟡 [Group제거 건너뜀] 알파/SMask 잔여 발견 "
            f"({residual}) — 투명도 그룹을 제거하면 색이 달라질 수 있어 보존했습니다.")
    else:
        groups_removed = _strip_transparency_groups(pdf)

    pdf.save(out_path)

    # 검증: 평탄화 후에도 투명도가 남았는지 자체 스캔(verify.scan_transparency 와 동일 기준)
    left = []
    chk = pikepdf.open(out_path)
    try:
        for obj in chk.objects:
            try:
                if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == pikepdf.Name("/ExtGState"):
                    for key in ("/ca", "/CA"):
                        if key in obj and float(obj[key]) < 1.0:
                            left.append(f"{key}={float(obj[key]):.3g}")
                    if "/SMask" in obj and obj["/SMask"] != pikepdf.Name("/None"):
                        left.append("SMask")
            except Exception:
                pass
    finally:
        chk.close()

    return {
        "bg": bg,
        "flattened_xobjects": flattened_names,
        "recolored_fills": recolored,
        "alpha_gstates_fixed": fixed,
        # 페이지 + Form XObject 에서 제거한 투명도 그룹(/Group(/Transparency)) 개수.
        # 0 이면(잔여 투명도로 건너뜀 또는 애초에 그룹 없음) EPS 단계에서 별도 확인 권장.
        "groups_removed": groups_removed,
        "warnings": warnings,
        "transparency_left": left,
    }


# ── 투명도 그룹 제거 헬퍼 ─────────────────────────────────────────────────────
def _scan_residual_transparency(pdf: pikepdf.Pdf) -> List[str]:
    """문서 전체에서 잔여 알파(ca/CA<1)·SMask 흔적을 모은다(Group 제거 전 안전 검사).

    verify.scan_transparency 와 동일 기준(ca/CA<1, SMask≠None)이라, 여기서 빈 리스트면
    '투명 효과가 실제로 없는' 상태가 보장된다 → Group(껍데기)을 떼도 색이 안 변한다.
    """
    found: List[str] = []
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == pikepdf.Name("/ExtGState"):
                for key in ("/ca", "/CA"):
                    if key in obj and float(obj[key]) < 1.0:
                        found.append(f"{key}={float(obj[key]):.3g}")
                if "/SMask" in obj and obj["/SMask"] != pikepdf.Name("/None"):
                    found.append("SMask")
        except Exception:
            pass
    return found


def _strip_transparency_groups(pdf: pikepdf.Pdf) -> int:
    """페이지 + 모든 Form XObject 에서 /Group <</S /Transparency>> 를 제거한다.
    단, **색공간(/CS)을 가진 페이지 그룹은 보존**한다(아래 '왜' 참조).

    반환: 제거한 그룹 수.

    ── 왜 '색공간 가진 페이지 그룹'은 남기는가(실측으로 확정) ──────────────────
      EPS(eps2write)가 페이지를 통째로 래스터화(20MB+)하게 만드는 진짜 트리거는
      **Form XObject 의 투명도 그룹**이다. 이것만 제거하면 EPS 가 벡터(≈270KB)로 나오고
      PDF 렌더 픽셀도 그대로다(델타>10 픽셀 0개 = 시각·색 변화 0).
      반대로 페이지 그룹의 /CS(ICCBased CMYK 등 '블렌딩 색공간')까지 통째로 지우면,
      렌더러가 기본 색공간으로 합성을 다시 해 **본판 색이 미세 시프트**된다(렌더 27% 픽셀
      변화). 게다가 페이지 그룹 제거는 EPS 벡터화에 기여하지도 않는다(제거해도 여전히
      래스터). 즉 '페이지 그룹의 /CS 제거'는 백해무익 → 색공간 가진 페이지 그룹은 보존.

      · Form XObject 의 /Group(/Transparency): **항상 제거**(벡터화 트리거 + 색 무변).
      · 페이지의 /Group(/Transparency) 중 /CS 없는 것: 제거(색 영향 없음).
      · 페이지의 /Group(/Transparency) 중 /CS 있는 것: 보존(색 보존 + 벡터화 무관).
    ⚠️ 이 함수는 알파·SMask 가 '이미 다 제거된' 뒤에만 호출돼야 한다(호출부 안전검사).
    """
    removed = 0

    def _is_transparency_group(grp) -> bool:
        try:
            return isinstance(grp, pikepdf.Dictionary) and \
                grp.get("/S") == pikepdf.Name("/Transparency")
        except Exception:
            return False

    def _has_colorspace(grp) -> bool:
        """그룹에 블렌딩 색공간(/CS)이 정의돼 있으면 True(보존 대상 판단용)."""
        try:
            return isinstance(grp, pikepdf.Dictionary) and "/CS" in grp
        except Exception:
            return False

    # 1) 페이지 딕셔너리의 /Group — /CS 가 없는 경우에만 제거(색 보존).
    for page in pdf.pages:
        pobj = page.obj
        try:
            grp = pobj.get("/Group")
            if "/Group" in pobj and _is_transparency_group(grp) and not _has_colorspace(grp):
                del pobj["/Group"]
                removed += 1
        except Exception:
            pass

    # 2) 모든 Form XObject 의 /Group — 벡터화 트리거이므로 항상 제거(색 무변).
    for obj in pdf.objects:
        try:
            if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == pikepdf.Name("/Form"):
                if "/Group" in obj and _is_transparency_group(obj.get("/Group")):
                    del obj["/Group"]
                    removed += 1
        except Exception:
            pass

    return removed
