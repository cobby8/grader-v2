# -*- coding: utf-8 -*-
"""job — 주문서(선수 명단) × 디자인 → 선수별 통합 출력 오케스트레이터.

배경(왜 grade() 로 부족한가):
  grade() 는 number/name 을 "단일 값"으로 받아 **전 사이즈 1PDF** 를 만든다.
  하지만 실제 작업 단위는 **선수별**이다 — 같은 사이즈라도 선수마다 배번·이름이 다르고,
  한 선수는 자기 사이즈 1페이지만 필요하다. 그래서 주문 행마다 그 선수의 사이즈 레이아웃을
  골라 배번/이름을 갈아끼워 출력하는 응용 계층이 따로 필요하다 — 이게 job.py 다.

설계 비유(식당 주방장):
  주문서(전표)를 한 장씩 보고, 그 선수의 사이즈 '레시피'만 골라 배번·이름을 얹어
  1인분(=PDF 1개/페이지 1장)을 굽는다. 오븐(compose)·레시피해석(build_layouts)·
  검수(verify_output)는 기존 것을 **그대로** 호출한다(불변 제약 준수).

불변 제약(절대 지킴):
  compose / Piece / SizeLayout / parse_svg / scale_translate / verify_output 의
  시그니처·동작을 수정하지 않는다. build_layouts / grade 도 무수정(있는 인자만 사용).
  '사이즈 좁히기'는 preset dict 를 **얕게 복제**해 sizes 만 1개로 교체하는 방식으로
  처리한다(원본 preset 변형 금지 — _dir / number_area 등 보존).
"""
from __future__ import annotations

import json
import copy
import os
import tempfile
from dataclasses import asdict
from typing import List, Optional

import pikepdf
from pikepdf import parse_content_stream

from .compose import Piece, SizeLayout, compose
from .flatten import flatten_transparency  # 디자인 투명도 벡터 평탄화(EPS 벡터 유지·verify PASS)
# grade.py 는 무수정(불변 제약). 공개 build_layouts/load_preset 과 함께, 폰트경로 해석
# 내부 함수 _resolve_font_path 는 '호출만' 한다(복제 대신 재사용 — 동작 일치 보장).
from .grade import _resolve_font_path, build_layouts, load_preset
from .pattern import parse_svg  # 사이즈별 패턴 SVG → 조각 윤곽(정밀배치 경로에서 사용)
from .pdfutil import cm_matrix, scale_translate, fit_matrix, with_mirror  # 글자 ops 를 시트좌표로 감쌀 cm 행렬 생성
from .text import place_name, place_number  # Phase B 정밀 배치기(완성본 실측 수치 재현)
from .verify import all_passed, verify_output

try:
    # 미리보기 PNG 는 선택 기능. PyMuPDF 미설치 환경에서도 job 핵심은 동작해야 하므로
    # import 실패를 치명적으로 보지 않는다(미리보기만 생략).
    from . import preview as _preview
except Exception:  # pragma: no cover - 방어적
    _preview = None


# ── 파일명 안전화 ────────────────────────────────────────────────────────────
_FORBIDDEN = set('/\\:*?"<>|')


def _safe_name(value: str) -> str:
    """파일명에 쓸 수 없는 문자를 _ 로 바꾸고 공백을 정리한다. 빈 이름은 'noname'.

    한글은 그대로 허용한다(Windows/한글 파일명 OK). 경로 구분/금지문자만 치환한다.
    """
    s = "".join("_" if ch in _FORBIDDEN else ch for ch in (value or "")).strip()
    return s or "noname"


def _num_for_filename(number: str) -> str:
    """파일명용 배번. 숫자면 2자리 zero-pad(정렬·식별 편의), 아니면 안전화한 원본.

    ⚠️ 출력 글자(실제 배번)는 원본 그대로 쓴다 — zero-pad 는 **파일명에만** 적용한다.
    """
    n = (number or "").strip()
    if not n:
        return "noNum"
    return n.zfill(2) if n.isdigit() else _safe_name(n)


def _atomic_save_compose(design_pdf: str, layouts, final_path: str) -> int:
    """compose 를 임시 파일에 쓰고 os.replace 로 최종 경로에 원자적 배치한다.

    중간에 죽어도 부분 파일이 최종 경로에 남지 않게 하기 위함(작업폴더 원자적 쓰기 원칙).
    Returns: compose 가 돌려준 배치(Do) 횟수 — verify 의 expected_placements 로 그대로 넘긴다.
    """
    out_dir = os.path.dirname(os.path.abspath(final_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=out_dir)
    os.close(fd)  # compose 가 직접 경로에 쓰므로 핸들은 닫는다.
    try:
        placements = compose(design_pdf, layouts, tmp, design_page=0)
        os.replace(tmp, final_path)  # 원자적 이동(같은 볼륨)
        return placements
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _checks_to_dicts(checks) -> list:
    """verify 의 Check 데이터클래스 목록을 JSON 직렬화 가능한 dict 목록으로 바꾼다."""
    return [asdict(c) for c in checks]


# ════════════════════════════════════════════════════════════════════════════
# Phase C — 정밀 배치 경로 (preset 의 front/back_number_area·back_name_area 사용)
#
#   왜 별도 경로인가:
#     기존 build_layouts 폴백은 number_area/name_area(rel_bbox·contain)로 글자를
#     '칸 안에' 욱여넣는다(미세 부정확). 새 area 는 완성본 실측 수치(잉크높이·중심·자간)를
#     그대로 재현하는 place_number/place_name(Phase B)로 그린다 → 정답지 정합.
#
#   좌표 변환의 핵심(반드시 이해할 것):
#     place_number/place_name 은 '디자인 좌표'(완성본 기준 center 1389,4184 등)로
#     글자 ops 를 만든다. 그런데 compose 의 Piece.extra_ops 는 그 조각의 q…Do…Q '밖'
#     (= 시트 절대좌표)에서 그려진다. 따라서 디자인좌표 글자를 시트좌표로 옮기려면
#     그 조각의 transform(=_piece_transform 이 계산한 s 0 0 s ox oy)으로 직접 감싼다:
#         q
#           s 0 0 s ox oy cm     ← 디자인좌표 → 시트좌표 (그 조각 변환과 동일)
#           <place_* 글자 ops>   ← q…Q 로 자체 래핑된 k fill 경로
#         Q
#     이렇게 하면 grade.py 방식 A 와 '같은 변환'이 글자에 적용돼 디자인 위 정위치에 박힌다.
# ════════════════════════════════════════════════════════════════════════════


def _job_piece_transform(design_region, poly, shrink_x, shrink_y, bleed=None):
    """grade.py `_piece_transform` 과 '동일한' 방식 A 변환을 계산한다(+선택적 cover/블리드).

    ⚠️ grade.py 의 _piece_transform 은 '_' 접두 내부 함수라 공개 API 가 아니다.
       불변 제약(grade.py 무수정)을 지키기 위해 그 로직을 여기에 그대로 복제한다.
       (수식이 어긋나면 글자가 어긋나므로, grade.py 와 한 글자도 다르지 않게 유지할 것.)

    design_region : (dx0, dy0, dx1, dy1)  디자인에서 이 부위가 차지하는 영역.
    poly          : 이 조각의 패턴 윤곽(parse_svg 결과). poly.bbox 가 시트 위 위치.
    shrink_x/y    : 수축 보정 계수(보통 1.0).
    bleed         : 블리드 배수. **기본 None|0 = contain(기존 동작·회귀 보호)**,
                    bleed>0 이면 cover+블리드(작업2). bleed=1.0 은 'cover 만'(추가 확대 없음),
                    1.03 은 cover 후 3% 더 키움(가장자리 흰 줄 방지).
                    호출자(_build_precise_layout)는 preset.cover_bleed 가 있을 때만 그 값을 넘긴다
                    → 키 없으면 None 이 와서 contain(U넥/grade 회귀 0).

    왜 cover/블리드가 필요한가(흰 틈 제거):
      contain(둘 중 작은 배율)은 디자인이 조각 안에 '다 들어오게' 맞춰 어깨/옆선/밴드 양끝에
      디자인이 안 닿는 흰 틈이 생긴다. cover(둘 중 큰 배율)는 조각을 디자인으로 '꽉 채운다'
      (밖으로 삐져나온 부분은 compose 의 clip(조각 윤곽)이 잘라낸다). bleed(>1)는 재단 여유
      만큼 살짝 더 키워 가장자리 흰 줄까지 확실히 덮는다.

    반환: scale_translate(s, ox, oy)  — (s, 0, 0, s, ox, oy) 행렬 튜플.
    """
    dx0, dy0, dx1, dy1 = design_region
    px0, py0, px1, py1 = poly.bbox  # 조각 윤곽 bbox(시트 좌표)

    dw, dh = (dx1 - dx0), (dy1 - dy0)   # 디자인 영역 크기
    pw, ph = (px1 - px0), (py1 - py0)   # 조각 크기

    if bleed is None or bleed <= 0:
        # ── 기존 contain 경로(U넥/grade 회귀 보호): 둘 중 '작은' 배율. ──
        #    grade.py _piece_transform 과 한 글자도 다르지 않게 유지.
        s = min(pw / dw, ph / dh) * min(shrink_x, shrink_y)
        ox = px0 - s * dx0
        oy = py0 - s * dy0
    else:
        # ── cover + 블리드(작업2): 둘 중 '큰' 배율 × 블리드. 조각을 디자인으로 꽉 채움. ──
        #    s = max(조각폭/영역폭, 조각높이/영역높이) × max(shrink) × bleed
        #    오프셋은 '중앙 정렬': 조각 중심에 디자인 영역 중심이 오도록 평행이동.
        #      ox = px0 + (pw - s*dw)/2 - s*dx0   (pw-s*dw 는 음수 → 양쪽으로 균등 오버플로)
        #      oy = py0 + (ph - s*dh)/2 - s*dy0
        s = max(pw / dw, ph / dh) * max(shrink_x, shrink_y) * float(bleed)
        ox = px0 + (pw - s * dw) / 2.0 - s * dx0
        oy = py0 + (ph - s * dh) / 2.0 - s * dy0
    return scale_translate(s, ox, oy)


def _auto_bleed(front_design_region, front_poly, k: float, lo: float, hi: float) -> float:
    """앞판(front) 1개 기준으로 사이즈 대표 블리드를 1회 산출한다(작업 B).

    왜 '앞판 기준 단일 값'인가:
      조각마다 폭/높이 비율이 달라 조각별 bleed 를 따로 쓰면 등방성이 깨질 수 있고 일관성도
      없다. 그래서 앞판 1개의 '디자인영역 대비 조각 윤곽' 가로세로비 어긋남(dev)으로 그 사이즈
      대표 bleed 를 1회 구해 전 조각에 똑같이 적용한다(번호/이름도 같은 단일 bleed → 등방 유지).

    수식:
      dev   = |(조각폭/조각높이) / (영역폭/영역높이) - 1|   (가로세로비 어긋남, 0=완전 일치)
      bleed = clamp(1.0 + k*dev, lo, hi)
    극단소형 사이즈일수록 패턴 윤곽이 디자인영역 비율과 더 어긋나(dev 큼) bleed 가 커져
    흰 줄무늬 같은 요소가 재단선까지 확실히 닿는다. XL(거의 일치)은 dev≈0 → bleed≈1.0.

    front_design_region : 앞판 design_region_pt (dx0,dy0,dx1,dy1).
    front_poly          : 앞판 조각 윤곽(parse_svg 결과, poly.bbox 사용).
    k/lo/hi             : 민감도 계수·하한·상한.
    반환                : 전 조각에 동일 적용할 단일 bleed(float).
    """
    dx0, dy0, dx1, dy1 = front_design_region
    px0, py0, px1, py1 = front_poly.bbox
    dw, dh = (dx1 - dx0), (dy1 - dy0)
    pw, ph = (px1 - px0), (py1 - py0)
    if dw <= 0 or dh <= 0 or pw <= 0 or ph <= 0:
        return float(lo)  # 비정상 입력은 보수적으로 하한(=확대 없음).
    dev = abs((pw / ph) / (dw / dh) - 1.0)
    bleed = 1.0 + float(k) * dev
    # clamp(lo, hi): 너무 작으면 흰틈, 너무 크면 과도 확대(번호 위치 흔들림) 방지.
    return max(float(lo), min(float(hi), bleed))


def _ops_bbox(ops: str, transform) -> Optional[tuple]:
    """글자 ops(m/l/c 좌표, 디자인 좌표) → transform 적용한 시트 bbox. 좌표가 없으면 None."""
    a, b, c, d, e, f = transform
    pts = []
    stack: List[float] = []
    for t in ops.split():
        try:
            stack.append(float(t))
            continue
        except ValueError:
            pass
        if t in ("m", "l") and len(stack) >= 2:
            pts.append((stack[-2], stack[-1]))
        elif t == "c" and len(stack) >= 6:
            pts += [(stack[-6], stack[-5]), (stack[-4], stack[-3]), (stack[-2], stack[-1])]
        stack = []
    if not pts:
        return None
    tx = [a * x + c * y + e for x, y in pts]
    ty = [b * x + d * y + f for x, y in pts]
    return min(tx), min(ty), max(tx), max(ty)


def _wrap_design_ops(transform, ops: str) -> str:
    """디자인좌표로 만든 글자 ops 를 그 조각의 transform(cm)으로 감싸 시트좌표로 옮긴다.

    transform : (a,b,c,d,e,f) = _job_piece_transform 이 돌려준 행렬.
    ops       : place_number/place_name 이 만든 글자 ops(이미 q…k…f…Q 로 자체 래핑됨).
    반환      : "q\\n<cm>\\n<ops>\\nQ"  — extra_ops 에 그대로 누적 가능한 시트좌표 블록.

    바깥 q…Q 로 한 번 더 감싸는 이유: cm 이 이후 페이지 콘텐츠의 CTM 을 오염시키지
    않도록 상태를 격리한다(compose 가 각 piece 를 q…Q 로 닫지만, extra_ops 는 그 밖이라
    여기서 직접 격리해야 안전). place_* 자체도 q…Q 라 색/경로는 이미 격리돼 있다.
    """
    a, b, c, d, e, f = transform
    return "q\n" + cm_matrix(a, b, c, d, e, f) + "\n" + ops + "\nQ"


# ════════════════════════════════════════════════════════════════════════════
# 이슈4 — 빨간 재단선(stroke) + 너치 보존
#
#   왜 필요한가(공장 관점):
#     인쇄·재단 공장은 디자인의 '빨간 재단선'(CMYK 0,0.96,0.95,0 류)과 그 위 너치(재단
#     맞춤 표식)를 보고 천을 자른다. 그런데 compose 는 각 조각을 그 조각 윤곽(clip)으로
#     잘라 디자인을 얹는다 → 재단선/너치는 보통 '조각 경계 밖'이라 클립에 잘려 사라진다.
#     그래서 재단선만 따로 추출해 클립 '밖'(extra_ops)에 다시 그려 살려 둔다.
#
#   접근(소스 확인 결과 반영):
#     디자인 PDF(평탄화본)를 1회 훑어 '빨간 stroke 경로'를 캡처한다. 캡처는 그 시점의
#     CTM(좌표변환)을 적용해 '디자인 절대좌표'로 평탄화한 ops 문자열로 만든다(나중에
#     조각 transform 으로 다시 감싸 시트좌표로 옮기기 위함 — 글자 주입과 같은 경로).
#     ⚠️ 현재 V넥 템플릿은 재단선 레이어(MC1/MC2/MC3)가 PDF 상 '비어' 있어 추출 stroke 가
#        0개일 수 있다. 이때는 경고만 남기고(0개 보존=정상), 재단선이 살아있는 소스가
#        들어오면 동일 코드가 자동으로 보존한다(색·좌표·허용오차는 전부 preset/소스에서).
# ════════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════════
# 작업3② — 디자인 '패턴선' OCG 콘텐츠 제거 (두 줄 방지의 핵심)
#
#   왜 OCG OFF 가 아니라 '콘텐츠 삭제'인가(실증):
#     compose 는 디자인 페이지를 Form XObject(as_form_xobject)로 임베드하면서 Root 의
#     OCProperties 를 복사하지 않는다. 그래서 base 디자인에서 패턴선 OCG 를 D.OFF 로 꺼도
#     출력 PDF 에는 OCProperties 정의 자체가 없어 뷰어/PyMuPDF 가 패턴선을 '그냥 표시'한다
#     (OCG OFF 무효 — 실측 확인). 결과: 디자인 패턴선 + 우리가 그린 재단선 = 두 줄.
#     → 근본 해결: base 디자인의 페이지 콘텐츠에서 '/OC /MCx BDC … EMC'(패턴선 레이어) 구간
#       자체를 잘라낸다. 그러면 Form 안에 패턴선 ops 가 아예 없어 어떤 뷰어에서도 안 보인다.
#
#   안전성(이 템플릿 구조 기준):
#     flatten 후 페이지 콘텐츠의 BDC/EMC 는 톱레벨·비중첩(각 레이어가 BDC…EMC 1구간).
#     그래서 '대상 OCG 를 가리키는 /OC /MCx BDC' 부터 짝 맞는 EMC 까지'만 토큰 단위로 제거하면
#     다른 레이어(몸판/요소/엠블럼)는 그대로 보존된다. 중첩이 있어도 깊이 카운트로 짝을 맞춘다.
# ════════════════════════════════════════════════════════════════════════════


def _ocg_name(ocg) -> str:
    """OCG 의 /Name 을 사람이 읽을 문자열로 디코딩한다(UTF-16-BE BOM/일반 모두 허용)."""
    try:
        raw = bytes(ocg.Name)
    except Exception:
        return ""
    if raw[:2] == b"\xfe\xff":          # UTF-16-BE BOM
        s = raw.decode("utf-16-be", errors="ignore")
    elif raw[:2] == b"\xff\xfe":        # UTF-16-LE BOM
        s = raw.decode("utf-16-le", errors="ignore")
    else:
        s = raw.decode("utf-8", errors="ignore")
    return s.lstrip("﻿")


def hide_design_cutline_layer(design_pdf: str, out_pdf: str,
                              layer_names=("패턴선", "재단선"),
                              page_index: int = 0, target_objgens=None) -> dict:
    """디자인 PDF 의 페이지 콘텐츠에서 '패턴선/재단선' OCG 마킹 구간을 통째로 제거한다.

    절차:
      1) 페이지 Resources/Properties 에서 layer_names 에 해당하는 OCG 의 마킹이름(/MCx) 수집.
      2) 페이지 콘텐츠 토큰을 훑어 '/OC /MCx BDC' 부터 짝 EMC 까지 구간을 건너뛰고 나머지만 보존.
      3) 보존 토큰으로 콘텐츠 스트림을 재작성해 out_pdf 로 저장(다른 색·레이어 무손실).

    반환: {"removed_layers": [...], "removed_spans": n, "found": bool}
    실패/대상없음이면 found=False(호출자가 원본을 그대로 쓰게).
    """
    info = {"removed_layers": [], "removed_spans": 0, "found": False}
    pdf = pikepdf.open(design_pdf)
    try:
        page = pdf.pages[page_index]
        res = page.get("/Resources")
        props = res.get("/Properties") if res is not None else None
        if not props:
            pdf.save(out_pdf)
            return info
        # 1) 대상 OCG 의 마킹이름(/MCx) 집합 구성.
        target_mc = set()
        for mc_name in list(props.keys()):
            ocg = props[mc_name]
            nm = _ocg_name(ocg)
            hit = (ocg.objgen in target_objgens) if target_objgens is not None else (nm in layer_names)
            if hit:
                target_mc.add(str(mc_name))   # 예: "/MC3"
                if nm not in info["removed_layers"]:
                    info["removed_layers"].append(nm)
        if not target_mc:
            pdf.save(out_pdf)
            return info

        # 2) 콘텐츠 토큰을 훑어 대상 BDC…EMC 구간을 제거.
        from pikepdf import ContentStreamInstruction, unparse_content_stream
        instrs = list(parse_content_stream(page))
        kept = []
        skip_depth = 0           # >0 이면 현재 대상 OCG 구간 안(제거 중)
        marker_depth = 0         # 대상 구간 안에서의 중첩 BDC/EMC 카운트
        spans = 0
        for operands, op in instrs:
            o = str(op)
            if skip_depth == 0:
                # 대상 BDC(/OC /MCx) 진입 판정.
                if o == "BDC" and len(operands) >= 2 and str(operands[0]) == "/OC" \
                        and str(operands[1]) in target_mc:
                    skip_depth = 1
                    marker_depth = 1
                    spans += 1
                    continue   # 이 BDC 토큰 자체도 버린다.
                kept.append((operands, op))
            else:
                # 제거 구간 내부: 중첩 BDC/BMC 는 깊이+1, EMC 는 -1. 0 되면 구간 종료.
                if o in ("BDC", "BMC"):
                    marker_depth += 1
                elif o == "EMC":
                    marker_depth -= 1
                    if marker_depth == 0:
                        skip_depth = 0   # 짝 EMC 까지 모두 버리고 구간 종료.
                # 구간 안 토큰은 전부 버린다(보존 안 함).

        if spans == 0:
            pdf.save(out_pdf)
            return info

        # 3) 보존 토큰으로 콘텐츠 재작성.
        new_instrs = [ContentStreamInstruction(ops, pikepdf.Operator(str(op)))
                      for ops, op in kept]
        new_data = unparse_content_stream(new_instrs)
        page.Contents = pdf.make_stream(new_data)
        info["removed_spans"] = spans
        info["found"] = True
        pdf.save(out_pdf)
        return info
    finally:
        pdf.close()


def _off_layer_names(pdf) -> set:
    """문서 기본 보기(/OCProperties /D)에서 «꺼진» 레이어 이름들."""
    names = set()
    try:
        ocp = pdf.Root.get("/OCProperties")
        if ocp is None:
            return names
        d = ocp.get("/D") or {}
        all_ocgs = list(ocp.get("/OCGs") or [])
        if str(d.get("/BaseState", "/ON")) == "/OFF":
            on = {o.objgen for o in (d.get("/ON") or [])}
            off = [o for o in all_ocgs if o.objgen not in on]
        else:
            off = list(d.get("/OFF") or [])
        for o in off:
            nm = _ocg_name(o)
            if nm:
                names.add(nm)
    except Exception:
        pass
    return names


def _off_layer_objgens(pdf):
    """꺼진 레이어 객체 번호 집합. 레이어 정보가 없으면 None."""
    ocp = pdf.Root.get("/OCProperties")
    if ocp is None:
        return None
    d = ocp.get("/D") or {}
    all_ocgs = list(ocp.get("/OCGs") or [])
    if str(d.get("/BaseState", "/ON")) == "/OFF":
        on = {o.objgen for o in (d.get("/ON") or [])}
        return {o.objgen for o in all_ocgs if o.objgen not in on}
    return {o.objgen for o in (d.get("/OFF") or [])}


def _on_layer_names(pdf) -> set:
    try:
        ocp = pdf.Root.get("/OCProperties")
        if ocp is None:
            return set()
        off = _off_layer_objgens(pdf) or set()
        return {_ocg_name(o) for o in (ocp.get("/OCGs") or []) if o.objgen not in off}
    except Exception:
        return set()


def hide_off_layers(state_pdf: str, design_pdf: str, out_pdf: str, page_index: int = 0) -> dict:
    """디자이너가 «꺼 둔» 레이어의 콘텐츠를 지운 사본을 만든다(2026-10-20).

    왜: compose 는 디자인 페이지를 Form 으로 옮기면서 문서의 레이어 켜짐/꺼짐(OCProperties)을 버린다.
        그래서 디자이너가 꺼 둔 «레이어 2»(사이즈 택 아래 초록 상자 등)가 출력에 찍혔다(최근 주문 5건 전부).
        → 꺼진 레이어의 '/OC /MCx BDC … EMC' 구간을 지운다(패턴선 지우기와 같은 방법).
    state_pdf : 꺼짐 정보를 읽을 원본(평탄화본은 OCProperties 가 없을 수 있다)
    design_pdf: 지울 대상(평탄화·패턴선 지운 base)
    반환: {"removed_layers": [...], "removed_spans": n, "found": bool}
    """
    # 이름이 같은 레이어가 둘(켜진 것·꺼진 것)일 수 있어(합친 파일) «이름»이 아니라 레이어 객체로 가린다(리뷰 지적).
    #   대상 파일에 레이어 정보(OCProperties)가 있으면 그 파일의 꺼진 객체로, 없으면 원본 이름으로(켜진 같은 이름은 뺀다).
    with pikepdf.open(design_pdf) as dp:
        off_obj = _off_layer_objgens(dp)
    if off_obj is not None:
        if not off_obj:
            return {"removed_layers": [], "removed_spans": 0, "found": False}
        return hide_design_cutline_layer(design_pdf, out_pdf, page_index=page_index, target_objgens=off_obj)
    with pikepdf.open(state_pdf) as sp:
        off = _off_layer_names(sp) - _on_layer_names(sp)
    if not off:
        return {"removed_layers": [], "removed_spans": 0, "found": False}
    return hide_design_cutline_layer(design_pdf, out_pdf, layer_names=tuple(sorted(off)), page_index=page_index)


def _mat_mul(m1, m2):
    """PDF 행렬 곱(flatten._mat_mul 과 동일): cm 은 현재 CTM 왼쪽에 곱해진다(new = m1 × m2)."""
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
    """점 (x,y) 에 행렬 m 을 적용해 변환된 (x',y') 반환."""
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _to_nums(operands):
    """피연산자들을 float 리스트로. 숫자가 아니면 None(색공간 이름 등)."""
    out = []
    for o in operands:
        try:
            out.append(float(o))
        except Exception:
            return None
    return out


def _color_matches(color, target, tol) -> bool:
    """color(4채널)가 target(4채널)과 채널별 허용오차 tol 이내로 일치하면 True."""
    if color is None or len(color) != 4:
        return False
    return all(abs(c - t) <= tol for c, t in zip(color, target))


def _extract_red_strokes(design_pdf: str, red_cmyk, tol: float,
                         page_index: int = 0):
    """디자인 PDF 를 1회 훑어 '빨간 stroke 경로'를 디자인 절대좌표 ops 로 캡처한다.

    반환: [ {"ops": <str>, "bbox": (x0,y0,x1,y1)}, ... ]  — stroke 1개당 1개 dict.
      ops  : 그 stroke 한 개를 디자인좌표에서 다시 그리는 PDF 연산자 문자열.
             (m/l/c/v/y/h 경로 + device K 색 재지정 + w 선폭 + S 로 stroke)
      bbox : 그 stroke 의 디자인 절대좌표 경계상자(조각 매핑에 사용).

    동작:
      · q/Q/cm 으로 CTM 을 추적해 모든 점을 '디자인 절대좌표'로 환산한다(평탄화).
      · K(또는 4값 SCN)로 stroke 색을 추적하고, 그 색이 red_cmyk 와 tol 이내면
        그 경로를 빨간 재단선으로 보고 캡처한다(stroke 페인트 연산자 S/s/B/b 등에서).
      · 색은 출력에서 device K(`0 0.96 0.95 0 K`)로 '재지정'해 무손실로 보존한다.

    ⚠️ stroke 가 없으면 빈 리스트를 돌려준다(현재 빈-레이어 템플릿의 정상 결과).
    """
    target = [float(v) for v in red_cmyk]

    pdf = pikepdf.open(design_pdf)
    try:
        page = pdf.pages[page_index]

        ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # 현재 변환행렬(디자인 좌표계로의 누적)
        ctm_stack = []
        stroke_color = None   # 현재 stroke 색(K 또는 SCN 4값)
        line_width = 1.0      # 현재 선폭(w). CTM 스케일을 곱해 디자인 절대 선폭으로.
        lw_stack = []
        # 현재 경로의 '디자인 절대좌표' 세그먼트들(연산자, [환산된 점들]) 누적.
        path_segs = []        # [(op_char, [(x,y), ...]), ...]

        strokes = []

        def _emit(op_char, *pts):
            """원본 점들을 CTM 으로 디자인 절대좌표로 환산해 경로 세그먼트에 누적."""
            mapped = [_apply(ctm, px, py) for (px, py) in pts]
            path_segs.append((op_char, mapped))

        def _capture():
            """누적된 경로가 빨간 stroke 면 디자인좌표 ops + bbox 로 캡처한다."""
            if not path_segs:
                return
            if not _color_matches(stroke_color, target, tol):
                return
            # 경로의 모든 점으로 ops 문자열과 bbox 를 만든다.
            xs, ys, lines = [], [], []
            for op_char, mapped in path_segs:
                if op_char == "h":
                    lines.append("h")
                    continue
                # m/l = 1점, c = 3점, v/y = 2점. 점들을 'x y' 나열 후 op 붙임.
                coords = " ".join(f"{x:.4f} {y:.4f}" for (x, y) in mapped)
                lines.append(f"{coords} {op_char}")
                for (x, y) in mapped:
                    xs.append(x); ys.append(y)
            if not xs:
                return
            # CTM 의 평균 스케일로 선폭을 디자인 절대값으로 환산(0 이면 hairline 기본 1pt).
            a, b, c, d, _, _ = ctm
            sx = (a * a + b * b) ** 0.5
            sy = (c * c + d * d) ** 0.5
            scale = (sx + sy) / 2.0 or 1.0
            w_abs = (line_width or 0.0) * scale
            if w_abs <= 0:
                w_abs = 1.0
            # device K 로 색 재지정(무손실) + 선폭 + 경로 + S(stroke). q…Q 로 상태 격리.
            kr, kg, kb, kk = target
            body = (
                "q\n"
                f"{kr:.4f} {kg:.4f} {kb:.4f} {kk:.4f} K\n"
                f"{w_abs:.4f} w\n"
                + "\n".join(lines) + "\n"
                "S\n"
                "Q"
            )
            strokes.append({"ops": body,
                            "bbox": (min(xs), min(ys), max(xs), max(ys))})

        for operands, op in parse_content_stream(page):
            o = str(op)
            n = _to_nums(operands)
            if o == "q":
                ctm_stack.append(ctm); lw_stack.append(line_width)
            elif o == "Q":
                ctm = ctm_stack.pop() if ctm_stack else ctm
                line_width = lw_stack.pop() if lw_stack else line_width
            elif o == "cm" and n and len(n) >= 6:
                ctm = _mat_mul(tuple(n[:6]), ctm)
            elif o == "w" and n and len(n) >= 1:
                line_width = n[0]
            elif o == "K" and n and len(n) == 4:
                stroke_color = tuple(n)            # device CMYK stroke 색
            elif o == "SCN" and n and len(n) == 4:
                stroke_color = tuple(n)            # 색공간 기반 4값 stroke 색
            # ── 경로 구성 연산자: 점을 CTM 환산해 누적 ──
            elif o == "m" and n and len(n) >= 2:
                _emit("m", (n[0], n[1]))
            elif o == "l" and n and len(n) >= 2:
                _emit("l", (n[0], n[1]))
            elif o == "c" and n and len(n) >= 6:
                _emit("c", (n[0], n[1]), (n[2], n[3]), (n[4], n[5]))
            elif o == "v" and n and len(n) >= 4:
                _emit("v", (n[0], n[1]), (n[2], n[3]))
            elif o == "y" and n and len(n) >= 4:
                _emit("y", (n[0], n[1]), (n[2], n[3]))
            elif o == "re" and n and len(n) >= 4:
                x, y, w, h = n[:4]
                # re(사각형) → m/l/h 로 풀어서 누적(stroke 가능 경로로).
                _emit("m", (x, y)); _emit("l", (x + w, y))
                _emit("l", (x + w, y + h)); _emit("l", (x, y + h))
                path_segs.append(("h", []))
            elif o == "h":
                path_segs.append(("h", []))
            # ── 페인트 연산자: stroke 면 캡처, 어느 쪽이든 현재 경로 종료 ──
            elif o in ("S", "s", "B", "B*", "b", "b*"):
                _capture()
                path_segs = []
            elif o in ("f", "F", "f*", "n", "W", "W*"):
                # fill/clip/no-op 으로 끝나는 경로는 재단선 아님 → 버린다.
                path_segs = []
        return strokes
    finally:
        pdf.close()


def _count_red_strokes_in_output(pdf_path: str, red_cmyk, tol: float,
                                 page_index: int = 0) -> int:
    """출력 PDF 의 '페이지 콘텐츠'에서 빨간(허용오차 내) stroke 페인트 수를 센다.

    재단선은 compose 가 extra_ops 로 페이지 콘텐츠에 직접 그린다(디자인 Form 안이 아님).
    그래서 페이지 content 스트림만 훑어 K(빨강) 상태에서의 S/s/B/b 횟수를 센다.
    '재단선 보존' 체크(출력 stroke 수 ≥ 매핑 기대 수)에 쓴다.
    """
    target = [float(v) for v in red_cmyk]
    cnt = 0
    pdf = pikepdf.open(pdf_path)
    try:
        page = pdf.pages[page_index]
        stroke_color = None
        color_stack = []
        for operands, op in parse_content_stream(page):
            o = str(op)
            n = _to_nums(operands)
            if o == "q":
                color_stack.append(stroke_color)
            elif o == "Q":
                stroke_color = color_stack.pop() if color_stack else stroke_color
            elif o in ("K", "SCN") and n and len(n) == 4:
                stroke_color = tuple(n)
            elif o in ("S", "s", "B", "B*", "b", "b*"):
                if _color_matches(stroke_color, target, tol):
                    cnt += 1
        return cnt
    finally:
        pdf.close()


def _overlap_area(b1, b2) -> float:
    """두 bbox(x0,y0,x1,y1)의 겹침 면적(겹치지 않으면 0)."""
    ix0 = max(b1[0], b2[0]); iy0 = max(b1[1], b2[1])
    ix1 = min(b1[2], b2[2]); iy1 = min(b1[3], b2[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def _point_in(region, x, y) -> bool:
    """점 (x,y)가 region(x0,y0,x1,y1) 안에 있으면 True(경계 포함)."""
    return region[0] <= x <= region[2] and region[1] <= y <= region[3]


def _map_strokes_to_pieces(strokes, pieces_def, warnings):
    """각 빨간 stroke 를 design_region_pt 와 겹침면적이 최대인 조각에 매핑한다.

    반환: {piece_index: [stroke, ...]}  — 조각 인덱스별 매핑된 stroke 목록.
    겹치는 조각이 없는 stroke(예: 이슈3 미추가 밴드 영역)는 skip + 경고.

    ⚠️ 재단선/너치는 '가는 선'이라 bbox 가 1차원(폭 또는 높이=0)일 수 있다. 이때
       면적 겹침은 0 이 되어 매핑에 실패한다. 그래서 면적 매핑이 0 이면 'stroke bbox
       중심점이 어느 region 안에 드는지'로 보조 매핑한다(선·점 너치도 매핑되게).
    """
    mapping = {}
    for st in strokes:
        best_idx, best_area = None, 0.0
        for i, pdef in enumerate(pieces_def):
            region = pdef.get("design_region_pt")
            if not region:
                continue
            area = _overlap_area(st["bbox"], tuple(region))
            if area > best_area:
                best_area, best_idx = area, i
        # 보조: 면적 겹침이 없으면(가는 선·점) bbox 중심점 포함 여부로 매핑.
        if best_idx is None:
            bx0, by0, bx1, by1 = st["bbox"]
            cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
            for i, pdef in enumerate(pieces_def):
                region = pdef.get("design_region_pt")
                if region and _point_in(tuple(region), cx, cy):
                    best_idx = i
                    break
        if best_idx is None:
            # 겹치는 조각 없음 → 밴드[0] 등 아직 preset 에 없는 부위. 보류(이슈3 후 연결).
            warnings.append(
                "🟡 재단선 1개가 어느 조각에도 겹치지 않아 보류합니다"
                f"(bbox={tuple(round(v,1) for v in st['bbox'])}) — 이슈3 밴드 조각 추가 후 연결.")
            continue
        mapping.setdefault(best_idx, []).append(st)
    return mapping


def _find_piece_index(pieces_def, piece_id):
    """preset['pieces'] 에서 piece_id 에 해당하는 인덱스를 찾는다(없으면 None)."""
    for i, pdef in enumerate(pieces_def):
        if pdef.get("id") == piece_id:
            return i
    return None


def _has_precise_areas(preset: dict) -> bool:
    """preset 에 정밀배치용 새 area 가 하나라도 있으면 True(정밀 경로 사용 신호)."""
    return any(k in preset for k in
               ("front_number_area", "back_number_area", "back_name_area"))


# ── (이슈1) 번호 글리프셋 로드 캐시: 같은 JSON 을 선수마다 다시 읽지 않게 한 번만 읽는다. ──
#    key = JSON 절대경로 → glyphset dict. preset 단위로 안 두고 경로 단위라 안전(읽기 전용).
_GLYPH_CACHE: dict = {}


def _load_glyph_source(preset: dict, glyph_source, warnings) -> Optional[dict]:
    """area.glyph_source(파일명/경로)를 읽어 글리프셋 dict 로 돌려준다.

    · glyph_source 가 없으면(None/빈값) None 반환 → place_number 가 폰트 폴백으로 그린다.
    · 경로는 preset['_dir'](패턴 폴더) 기준 상대경로로 먼저 찾고, 없으면 절대/현재경로로 시도.
    · 로드 실패(파일 없음/JSON 오류)는 치명적이지 않게 경고만 남기고 None 반환(폰트 폴백 보장).
    """
    if not glyph_source:
        return None
    # 패턴 폴더 기준 경로를 우선 사용(번호 글리프셋은 패턴 폴더에 함께 둔다).
    candidates = []
    base_dir = preset.get("_dir")
    if base_dir:
        candidates.append(os.path.join(base_dir, glyph_source))
    candidates.append(glyph_source)  # 절대/현재경로 폴백

    for path in candidates:
        if os.path.exists(path):
            key = os.path.abspath(path)
            if key in _GLYPH_CACHE:
                return _GLYPH_CACHE[key]
            try:
                from .number_glyphs import load_glyphset_json
                gs = load_glyphset_json(path)
                _GLYPH_CACHE[key] = gs
                return gs
            except Exception as e:
                warnings.append(
                    f"🟡 번호 글리프셋 '{glyph_source}' 로드 실패(폰트로 폴백): {e}")
                return None
    # 후보 경로 어디에도 없음 → 폰트 폴백(경고).
    warnings.append(
        f"🟡 번호 글리프셋 '{glyph_source}' 를 찾지 못해 폰트로 폴백합니다.")
    return None


def _polygon_cutline_ops(points, color_cmyk, stroke_width) -> str:
    """조각 윤곽 points(시트 절대좌표, 너치 포함)를 빨강 1줄 stroke ops 로 그린다(작업3①).

    왜 이 방식인가(두 줄 방지):
      디자인 PDF 안의 빨간 패턴선을 '추출'해 다시 그리면, 디자인 자체의 패턴선(OCG)과
      추출본이 겹쳐 '두 줄'이 될 수 있다. 그래서 디자인 패턴선은 OCG 콘텐츠 삭제로 없애고,
      재단선은 우리가 가진 '조각 윤곽(parse_svg 결과 = 너치 포함 폴리곤)'을 직접 1회만 그린다.
      poly.points 는 이미 시트 절대좌표(parse_svg 가 flip_y 로 PDF 좌표화)라 transform 으로
      감쌀 필요 없이 페이지 콘텐츠에 그대로 그리면 된다(클립 밖 = extra_ops → 너치 안 잘림).

    color_cmyk   : device K 4채널(예: [0,0.96,0.95,0]). 무손실로 그대로 K 지정.
    stroke_width : 선폭(pt). preset.cutline.stroke_width(기본 2.0).
    반환         : "q … K … w … m,l … h S Q" 형태의 1줄 stroke 블록(상태 격리).
    """
    if not points or len(points) < 3:
        return ""
    kr, kg, kb, kk = [float(v) for v in color_cmyk]
    parts = [f"{points[0][0]:.4f} {points[0][1]:.4f} m"]
    for (x, y) in points[1:]:
        parts.append(f"{x:.4f} {y:.4f} l")
    # h = 윤곽을 닫는다(시작점으로 복귀) → 닫힌 재단선 1줄.
    body = (
        "q\n"
        f"{kr:.4f} {kg:.4f} {kb:.4f} {kk:.4f} K\n"
        f"{float(stroke_width):.4f} w\n"
        + "\n".join(parts) + "\n"
        "h\n"
        "S\n"
        "Q"
    )
    return body


def _build_precise_layout(preset: dict, size_def: dict, *,
                          number=None, name=None, warnings=None,
                          cutline_strokes=None, cover_bleed=None,
                          bg_cmyk=None) -> SizeLayout:
    """새 area(front/back_number_area·back_name_area)로 정밀배치한 SizeLayout 1개 생성.

    동작은 build_layouts(방식 A)와 같지만, 글자 주입만 place_number/place_name 으로
    바꾼 '정밀 경로'다. compose/Piece/SizeLayout 시그니처는 그대로 사용한다(불변 준수).

    절차:
      1) 사이즈 패턴 SVG 파싱 → 조각 윤곽(parse_svg, build_layouts 와 동일).
      2) 각 조각의 방식 A transform 계산(_job_piece_transform, grade 와 동일 공식).
      3) front_number_area → front 조각, back_number_area/back_name_area → back 조각의
         place_* 글자 ops 를 '그 조각 transform' 으로 감싸 extra_ops 에 누적.
      4) (이슈4) cutline_strokes(빨간 재단선, 디자인좌표 ops)를 겹침 최대 조각에 매핑해
         그 조각 transform 으로 감싸 extra_ops 에 누적(글자와 동일 경로, 클립 '밖'이라
         조각 경계를 넘는 너치까지 안 잘리고 보존됨).

    cover_bleed : float(전 사이즈 단일) | dict({auto:true,k,min,max})(앞판 기준 사이즈별 산출)
                  | None(contain·회귀). dict+auto 면 이 함수에서 _auto_bleed 로 단일값 산출 후
                  전 조각 동일 적용(등방 유지).
    bg_cmyk     : 본체색(device CMYK 4채널) | None(기본·채움 생략). 값이 있으면 각 Piece.bg_cmyk
                  에 셋 → place_block 이 클립 안을 디자인 전에 칠해 흰틈 제거(작업 A).
    """
    if warnings is None:
        warnings = []

    pieces_def = preset["pieces"]
    shrink = preset.get("shrink", {"x": 1.0, "y": 1.0})
    shrink_x = float(shrink.get("x", 1.0))
    shrink_y = float(shrink.get("y", 1.0))

    # ── 1) 사이즈 패턴 SVG 파싱(build_layouts 와 동일 경로 — _dir + pattern_file). ──
    svg_path = os.path.join(preset["_dir"], size_def["pattern_file"])
    polys = parse_svg(svg_path)  # 높이 내림차순 정렬

    # ── (작업 B) cover_bleed 해석: float 이면 그대로, dict({auto:true,...}) 이면 앞판 기준
    #    단일 bleed 를 이 사이즈에 맞춰 1회 산출한다(전 조각·번호/이름 동일값 → 등방 유지).
    #    cover_bleed 가 None 이면 contain(기존/U넥 회귀 0).
    bleed_value = cover_bleed  # 기본: float 또는 None 그대로
    if isinstance(cover_bleed, dict) and cover_bleed.get("auto"):
        k = float(cover_bleed.get("k", 1.3))
        lo = float(cover_bleed.get("min", 1.0))
        hi = float(cover_bleed.get("max", 1.12))
        front_idx = _find_piece_index(pieces_def, "front")
        if front_idx is None:
            front_idx = 0  # front id 없으면 첫 조각으로 폴백
        front_pdef = pieces_def[front_idx]
        front_poly = polys[front_pdef["svg_index"]]
        bleed_value = _auto_bleed(front_pdef["design_region_pt"], front_poly, k, lo, hi)
        warnings.append(
            f"[블리드:auto] 사이즈 {size_def['name']} 앞판 기준 단일 bleed={bleed_value:.4f}"
            f" (k={k}, clamp[{lo},{hi}]).")
    elif isinstance(cover_bleed, dict):
        # auto 가 아닌 dict 는 잘못된 설정 → 안전하게 contain 으로 폴백(경고).
        bleed_value = None
        warnings.append("🟡 [블리드] cover_bleed dict 에 auto:true 가 없어 contain 으로 진행.")

    # ── 2) 조각별 윤곽 + 방식 A transform 으로 Piece 생성(글자 없이 먼저). ──
    layout_pieces: List[Piece] = []
    piece_transforms: List[tuple] = []  # 같은 인덱스로 글자 감싸기에 재사용
    for pdef in pieces_def:
        idx = pdef["svg_index"]
        if idx < 0 or idx >= len(polys):
            raise ValueError(
                f"조각 '{pdef.get('id','?')}' svg_index={idx} 가 SVG 조각 수({len(polys)})를 벗어남"
                f" (사이즈 {size_def['name']}, 파일 {size_def['pattern_file']})")
        poly = polys[idx]
        # cover_bleed 가 지정되면(작업2) cover+블리드, 아니면 기존 contain(bleed=None→contain).
        if pdef.get("fit"):
            # 조각별 «디자이너 방식»(2026-10-20 등록분부터) — 블리드 없이 그 방식대로. 없으면 예전 그대로.
            transform = fit_matrix(pdef["design_region_pt"], poly.bbox, pdef["fit"], min(shrink_x, shrink_y))
        else:
            transform = _job_piece_transform(pdef["design_region_pt"], poly,
                                             shrink_x, shrink_y, bleed=bleed_value)
        if pdef.get("mirror"):
            transform = with_mirror(pdef["design_region_pt"], transform)   # 거울 짝(디자인엔 한 장뿐)
        piece_transforms.append(transform)
        layout_pieces.append(
            # bg_cmyk: 본체색(있으면). place_block 이 클립 안을 디자인 전에 칠해 흰틈 제거.
            Piece(outline=poly.points, transform=transform,
                  name=pdef.get("name", pdef.get("id", "")),
                  bg_cmyk=bg_cmyk))

    # ── 3) 글자 ops 생성 → 그 조각 transform 으로 감싸 extra_ops 에 누적 ──
    def _inject(area_key, kind, value):
        """area_key 의 정의를 읽어 place_*(디자인좌표) ops 를 만들고, 그 조각 transform 으로
        감싸 해당 Piece.extra_ops 에 더한다. kind='number'|'name'. value 빈값이면 건너뜀."""
        area = preset.get(area_key)
        if not area:
            return
        if value is None or str(value).strip() == "":
            return  # 그릴 값 없음(정상)

        piece_id = area.get("piece_id")
        pidx = _find_piece_index(pieces_def, piece_id)
        if pidx is None:
            warnings.append(
                f"🟡 {area_key} 의 piece_id='{piece_id}' 를 조각 목록에서 찾지 못해 '{value}' 를 그리지 않습니다.")
            return

        font_path = _resolve_font_path(preset, area.get("font", ""))
        color = area.get("color_cmyk", [0, 0, 0, 1])

        # ── 디자인좌표 글자 ops 생성(Phase B 정밀 배치기). ──
        if kind == "number":
            # ── 이슈1: area 에 glyph_source 가 있으면 디자이너 번호 글리프셋으로 그린다.
            #    없거나 로드 실패면 glyph_set=None 으로 전달 → place_number 가 폰트 폴백. ──
            glyph_set = _load_glyph_source(preset, area.get("glyph_source"), warnings)
            ops, warns = place_number(
                str(value), font_path,
                cap_h_pt=float(area.get("cap_height", 0)),
                center_x=float(area["center"][0]),
                center_y=float(area["center"][1]),
                color=color,
                glyph_source=glyph_set,
                outline=area.get("outline"))
        else:  # name
            ops, warns = place_name(
                str(value), font_path,
                em_pt=float(area.get("em_pt", 0)),
                pitch_pt=float(area.get("pitch", 0)),
                baseline_y=float(area["baseline"]),
                center_x=float(area["center_x"]),
                color=color)
        warnings.extend(warns)
        if not ops:
            return

        # ── 디자인좌표 → 시트좌표: 그 조각의 transform 으로 감싼다(핵심). ──
        wrapped = _wrap_design_ops(piece_transforms[pidx], ops)
        tp = layout_pieces[pidx]
        if pieces_def[pidx].get("fit"):
            # 글자는 조각 윤곽으로 잘리지 않는다(클립 밖). 예전 방식은 디자인 영역이 늘 조각 안이라 괜찮았지만,
            #   «위 맞춤»은 작은 사이즈에서 영역이 조각보다 넓어질 수 있다 → 조각 밖으로 나가면 알린다(2026-10-20 리뷰).
            gb = _ops_bbox(ops, piece_transforms[pidx])
            if gb:
                xs = [x for x, _ in tp.outline]; ys = [y for _, y in tp.outline]
                if gb[0] < min(xs) - 2 or gb[2] > max(xs) + 2 or gb[1] < min(ys) - 2 or gb[3] > max(ys) + 2:
                    warnings.append(f"🟡 [{size_def['name']}] '{value}' 글자가 {tp.name} 조각 밖으로 나갑니다 — 인쇄물 확인 필요.")
        tp.extra_ops = (tp.extra_ops + "\n" + wrapped) if tp.extra_ops else wrapped

    # 앞·뒤 번호는 '같은 배번'(number) — 앞=front 조각, 뒤=back 조각.
    _inject("front_number_area", "number", number)
    _inject("back_number_area", "number", number)
    _inject("back_name_area", "name", name)

    # ── 4) 빨간 재단선 주입(작업3) ──
    #    방식 선택: cutline.draw_from == "svg_polygon" 이면 '조각 윤곽(poly.points)'을 직접
    #    빨강 1줄로 그린다(두 줄 방지·너치 포함). 그렇지 않으면(=기존 동작) 디자인에서 추출한
    #    빨간 stroke(cutline_strokes)를 조각 transform 으로 감싸 그린다.
    cutline_cfg = preset.get("cutline") or {}
    draw_from = cutline_cfg.get("draw_from")
    if draw_from == "svg_polygon":
        # ── 작업3①: 조각 윤곽 = 재단선. poly.points 는 이미 시트 절대좌표라 transform 불필요.
        #    각 조각의 윤곽을 빨강 1줄로 그린다(너치 포함, 클립 밖이라 너치 안 잘림).
        color = cutline_cfg.get("color_cmyk", [0, 0.96, 0.95, 0])
        sw = float(cutline_cfg.get("stroke_width", 2.0))
        # (2026-10-20 노치) preset.notches 가 있으면 재단선만 «<사이즈>.notched.svg»(노치 든 외곽선)로 그린다.
        #   합성·클립은 위의 깨끗한 polys 그대로. 노치 홈은 안쪽이라 조각 높이가 같아 높이 내림차순 순서도 같다.
        #   preset.notches 가 없으면(기존 프리셋) cut_polys = polys — 한 줄도 바뀌지 않는다.
        cut_polys = polys
        notch_cfg = preset.get("notches") or {}
        if notch_cfg:
            npath = os.path.splitext(svg_path)[0] + notch_cfg.get("notched_suffix", ".notched.svg")
            if os.path.isfile(npath):
                np_polys = parse_svg(npath)
                # 같은 조각인지 상자로 확인(노치 홈은 안쪽이라 상자가 같다) — 하나라도 다르면 노치 없이 그린다
                same = len(np_polys) == len(polys) and all(
                    max(abs(u - v) for u, v in zip(a.bbox, b.bbox)) < 0.5 for a, b in zip(np_polys, polys))   # bbox 는 속성
                if same:
                    cut_polys = np_polys
                else:
                    warnings.append(f"🟡 [노치] {os.path.basename(npath)} 조각이 깨끗한 SVG 와 맞지 않습니다 — 노치 없이 재단선을 그립니다")
            else:
                warnings.append(f"🟡 [노치] {os.path.basename(npath)} 없음 — 노치 없이 재단선을 그립니다")
        for li, pdef in enumerate(pieces_def):
            poly = cut_polys[pdef["svg_index"]]
            ops = _polygon_cutline_ops(poly.points, color, sw)
            if not ops:
                continue
            tp = layout_pieces[li]
            tp.extra_ops = (tp.extra_ops + "\n" + ops) if tp.extra_ops else ops
    elif cutline_strokes:
        # ── 기존(추출) 방식: 디자인좌표 stroke ops 를 매핑 조각 transform 으로 감싸 누적. ──
        #    extra_ops 는 q…Do…Q 의 '밖'(클립 외부)이라 너치가 조각 경계를 넘어도 안 잘린다.
        cut_map = _map_strokes_to_pieces(cutline_strokes, pieces_def, warnings)
        for pidx, sts in cut_map.items():
            tp = layout_pieces[pidx]
            for st in sts:
                wrapped = _wrap_design_ops(piece_transforms[pidx], st["ops"])
                tp.extra_ops = (tp.extra_ops + "\n" + wrapped) if tp.extra_ops else wrapped

    # ── 페이지 크기 = 모든 조각 윤곽 전체 bbox + 여백 50pt(build_layouts 와 동일). ──
    all_x = [x for p in pieces_def for (x, _) in polys[p["svg_index"]].points]
    all_y = [y for p in pieces_def for (_, y) in polys[p["svg_index"]].points]
    page = (max(all_x) + 50.0, max(all_y) + 50.0)

    return SizeLayout(name=size_def["name"], page_size=page, pieces=layout_pieces)


def _auto_regions(pd: dict, design_pdf: str, warnings: list, label: str = "") -> list:
    """(2026-10-20) 디자인 속 재단 윤곽으로 pd 조각 영역을 맞추고(좌우 거울 포함), 양면이면 두 번째 면 이후의
    프리셋 사본 목록을 돌려준다. 실패하면 빈 목록(등록 때 어림값 그대로)."""
    extra_sides: list = []
    try:
        from .region_match import match_regions
        _bs = pd["design"].get("base_size")
        _bsd = next((s for s in pd["sizes"] if s["name"] == _bs), pd["sizes"][0])
        _polys = parse_svg(os.path.join(pd["_dir"], _bsd["pattern_file"]))
        _m = match_regions(design_pdf, _polys)
        _done = []
        for pdef in pd["pieces"]:
            hit = _m.get(pdef.get("svg_index"))
            if not hit:
                continue
            pdef["design_region_pt"] = list(hit["region_pt"])
            if hit["mirrored"]:
                pdef["mirror"] = True
            _done.append(f"{pdef.get('name') or pdef.get('id')}{'(뒤집음)' if hit['mirrored'] else ''}")
        _sides = _m.pop("_sides", [])
        miss = [p.get("name") or p.get("id") for p in pd["pieces"] if p.get("svg_index") not in _m]
        if _done:
            warnings.append(f"[영역] {label}디자인 속 재단 윤곽으로 조각 영역을 맞췄습니다: " + ", ".join(_done))
            big_miss = [p.get("name") or p.get("id") for p in pd["pieces"]
                        if p.get("svg_index") not in _m and p.get("fit") == "top_height"]
            if big_miss:
                # (2026-10-21) 몸판이 빠지면 «노란 참고» 가 아니라 «빨간 확인» — 퍼시픽 S 는 뒤판(이름·번호)이 통째로 빠졌는데
                #   노란 한 줄만 남고 검증은 통과로 나왔다. 디자인의 그 조각에 재단선(회색 윤곽)이 없을 때 생긴다.
                warnings.append(f"🔴 [영역] {label}디자인에서 몸판 «{', '.join(big_miss)}» 의 재단선을 못 찾아 그 조각이 빠졌습니다 — "
                                "디자인 파일의 그 조각에 재단선(패턴선) 윤곽이 있는지 확인해 주세요.")
            small_miss = [m for m in miss if m not in big_miss]
            if small_miss:
                warnings.append(f"🟡 [영역] {label}디자인에서 못 찾은 조각은 빼고 찍습니다: {', '.join(small_miss)} — "
                                "디자인에 있는 조각이면 재단이 빠지니 확인해 주세요.")
            if miss:
                # 이 디자인에 없는 조각(반팔 주문의 긴팔 소매·한 장짜리 하의 디자인의 옆선판 등)은 어림값으로 그리지 않는다
                pd["pieces"] = [p for p in pd["pieces"] if p.get("svg_index") in _m]
                miss = []
        elif miss:
            warnings.append(f"🟡 [영역] {label}디자인에서 재단 윤곽을 찾지 못해 등록 때 어림값을 씁니다 — 그림이 어긋날 수 있습니다.")
            pd["_auto_failed"] = True
        # (2026-10-20) 양면: 모든 조각이 같은 모양 두 벌 이상(위·아래)이면 두 번째 면도 함께 찍는다
        #   (preset.reversible=false 면 끔). 번호·이름 영역은 그 조각이 옮겨간 만큼 같이 옮긴다.
        _all_ok = (not miss) and all(not _m[p["svg_index"]]["mirrored"] for p in pd["pieces"])
        if _all_ok and _sides and pd.get("reversible", True) is not False:
            n_sides = len(_sides) + 1
            for rnd in _sides:
                if not all(p["svg_index"] in rnd for p in pd["pieces"]):
                    continue
                pd2 = copy.deepcopy(pd)
                deltas = {}
                for p2 in pd2["pieces"]:
                    ra = pd["pieces"][[q["svg_index"] for q in pd["pieces"]].index(p2["svg_index"])]["design_region_pt"]
                    rb = rnd[p2["svg_index"]]
                    p2["design_region_pt"] = list(rb)
                    deltas[p2.get("id")] = (rb[0] - ra[0], rb[1] - ra[1])
                for akey in ("front_number_area", "back_number_area", "back_name_area"):
                    area = pd2.get(akey)
                    if not area:
                        continue
                    dx, dy = deltas.get(area.get("piece_id"), (0.0, 0.0))
                    if "center" in area:
                        area["center"] = [area["center"][0] + dx, area["center"][1] + dy]
                    if "center_x" in area:
                        area["center_x"] = area["center_x"] + dx
                    if "baseline" in area:
                        area["baseline"] = area["baseline"] + dy
                    # (2026-10-21) 그 벌의 번호 색(완성본에서 잰 것) — 옮긴 거리가 맞는 것을 쓴다
                    for sc in area.get("side_colors") or []:
                        if abs(float(sc.get("dy", 0)) - dy) <= 60 and sc.get("color_cmyk"):
                            area["color_cmyk"] = list(sc["color_cmyk"])
                            break
                extra_sides.append(pd2)
            if extra_sides:
                warnings.append(f"[양면] {label}디자인에 같은 조각이 {n_sides}벌 — {n_sides}면을 한 장에 위·아래로 함께 찍습니다.")
    except Exception as e:
        warnings.append(f"🟡 [영역] {label}자동 짝짓기 실패(어림값 사용): {e}")
        pd["_auto_failed"] = True
    return extra_sides


def _stack_layouts(name: str, layouts: list, gap: float = 60.0, margin: float = 50.0) -> SizeLayout:
    """여러 레이아웃을 한 장에 위→아래로 쌓는다(2026-10-20 — 양면 두 면·상의+하의).

    각 레이아웃은 먼저 조각들의 왼아래가 (margin, margin) 이 되게 옮긴다 — 축구 마스터처럼 대지가 아주 크면
    조각 좌표가 원점에서 멀어, 그대로 쌓으면 페이지가 PDF 한도(14400pt)를 넘었다(2026-10-21 점검).
    그다음 마지막(아래) 레이아웃부터 위로 올린다(PDF 는 y 가 위로 크다).
    조각 윤곽·transform 은 옮기고, 시트 좌표로 만든 extra_ops(글자·재단선)는 통째로 평행이동해 감싼다.
    덮어 찍기(overlays)는 조각 transform 다음에 적용되므로 따로 옮길 필요가 없다.
    """
    pieces = []
    y = 0.0
    width = 0.0
    for lay in reversed(layouts):
        xs = [px for p in lay.pieces for px, _ in p.outline]
        ys = [py for p in lay.pieces for _, py in p.outline]
        if not xs:
            continue
        dx = margin - min(xs)
        dy = y + margin - min(ys)
        for p in lay.pieces:
            p.outline = [(px + dx, py + dy) for px, py in p.outline]
            a, b, c, d, e, f = p.transform
            p.transform = (a, b, c, d, e + dx, f + dy)
            if p.extra_ops:
                p.extra_ops = "q 1 0 0 1 %.4f %.4f cm\n%s\nQ" % (dx, dy, p.extra_ops)
        pieces.extend(lay.pieces)
        y += (max(ys) - min(ys)) + 2 * margin + gap
        width = max(width, (max(xs) - min(xs)) + 2 * margin)
    return SizeLayout(name=name, page_size=(width, max(y - gap, 3.0)), pieces=pieces)


def _sized_preset(preset: dict, size_def: dict) -> dict:
    """preset 을 얕게 복제하고 sizes 만 [size_def] 1개로 좁힌다(원본 무변형).

    number_area / name_area / pieces / _dir 등 나머지 키는 공유한다(읽기 전용 사용).
    """
    return {**preset, "sizes": [size_def]}


def run_job(preset: str,
            design_pdf: str,
            order_rows: List[dict],
            out_dir: str,
            font_path: Optional[str] = None,
            split: str = "per_player",
            make_preview: bool = True,
            out_format: Optional[str] = None) -> dict:
    """주문 행(선수)마다 그 선수 사이즈 1페이지에 배번/이름을 얹어 PDF 한 벌을 만든다.

    매개변수
      preset      : preset.json 경로(str). 내부에서 load_preset 한다.
      design_pdf  : 기준 디자인(.ai/.pdf) 경로.
      order_rows  : parse_order 결과 [{name, number, size, qty}] 리스트.
      out_dir     : 작업 루트(예: data/jobs/<날짜_주문명>/). 아래 output/·preview/·job.json 생성.
      font_path   : (현재 미사용) 폰트는 preset 의 number_area/name_area.font 에 박혀 있다.
                    인터페이스 안정성을 위해 받되, 추후 area.font 오버라이드 훅으로 활용 예정.
      split       : "per_player"(기본, 선수별 파일) | "single"(다페이지 1PDF).
      make_preview: True 면 출력마다 검수용 PNG 생성(PyMuPDF 있을 때만).
      out_format  : 출력 형식 "pdf" | "eps" | "both". None 이면 preset.output.format,
                    그것도 없으면 "pdf"(기본). **run_job 인자가 최종 우선**(의뢰서 §5).
                    · pdf  : PDF 만 산출(기존 동작).
                    · eps  : 공통 PDF 를 만든 뒤 EPS 로만 변환(중간 PDF 는 임시).
                    · both : PDF + EPS 둘 다(output/pdf, output/eps 로 분리 저장).
                    GS 미설치 시 eps/both 는 PDF 만 산출(graceful fallback, 크래시 0).

    반환(dict): {"outputs": [...], "summary": {...}}  — 자세한 형태는 아래 코드 참조.
    실패 정책: 행 단위 실패(사이즈 없음/미지원/렌더 오류)는 skip + 사유 기록으로 흘리고
              전체를 죽이지 않는다(부분 성공). 디자인/preset 자체 누락은 시작 전 예외 전파.
    """
    if split not in ("per_player", "single"):
        raise ValueError(f"split 은 'per_player' 또는 'single' 이어야 합니다(받은 값: {split!r})")

    # ── 시작 전 차단: preset/디자인은 여기서 한 번 검증한다(없으면 친절한 예외 전파). ──
    preset_dict = load_preset(preset)  # FileNotFoundError/ValueError 친절 메시지
    if not os.path.exists(design_pdf):
        raise FileNotFoundError(f"디자인 파일 없음: {design_pdf}")

    # ── (§5) 출력 형식 결정: run_job 인자 > preset.output.format > 기본 "pdf". ──
    #    왜 이 우선순위: CLI/호출자가 명시한 형식이 preset 기본값을 덮어쓰는 게 직관적.
    out_cfg = preset_dict.get("output", {}) or {}
    fmt = (out_format or out_cfg.get("format") or "pdf").lower()
    if fmt not in ("pdf", "eps", "both"):
        raise ValueError(f"out_format 은 'pdf'|'eps'|'both' 여야 합니다(받은 값: {out_format!r})")
    want_pdf = fmt in ("pdf", "both")   # 최종 산출물에 PDF 를 남기는가
    want_eps = fmt in ("eps", "both")   # EPS 를 만드는가
    # GS 경로: preset.output.ghostscript_path → eps.find_ghostscript 의 1순위로 넘긴다.
    gs_path = out_cfg.get("ghostscript_path")

    # 사용 가능한 사이즈 맵(이름 → 사이즈 정의). 주문 사이즈를 여기에 대조한다.
    #   sizes 에는 '출고 가능한' 사이즈만 들어 있다(예: V넥 12개). 주문 사이즈가
    #   여기 없으면 매칭 실패다 — 사이즈는 정확히 일치해야만 매칭되므로 '대체' 경로가 없다.
    size_map = {s["name"]: s for s in preset_dict["sizes"]}
    # ── (이슈3) 비활성(결함) 사이즈는 preset 최상위 "disabled_sizes" 섹션에서 읽는다. ──
    #   왜 sizes 가 아니라 별도 섹션인가:
    #     grade.py 의 build_layouts 는 preset["sizes"] 전체를 순회하며 각 사이즈의
    #     pattern_file(SVG)을 읽는다. 결함으로 봉인한 3XL 을 sizes 안에 남겨 두면(설령
    #     disabled 표식이 있어도) build_layouts 는 그 표식을 모른 채 3XL.svg 를 읽으려다
    #     FileNotFoundError 로 크래시한다(grade 회귀). build_layouts/grade 는 불변 제약이라
    #     수정할 수 없으므로, 결함 사이즈를 sizes 에서 아예 빼고 disabled_sizes 로 옮긴다.
    #     → build_layouts 는 3XL 을 순회하지 않아 grade 가 크래시하지 않는다.
    #   삭제가 아니라 '이동'이라, 올바른 .ai 재확보 후 disabled_sizes 에서 빼고 sizes 에
    #   다시 넣으면 즉시 복원된다(복원법은 scratchpad 참조).
    #   {이름 → 사유} 형태로 보관해, 그 사이즈 주문이 오면 '왜' skip 됐는지 명확히 안내한다.
    disabled_map = {d["name"]: d.get("reason", "사유 미기재")
                    for d in preset_dict.get("disabled_sizes", [])}

    # ── 출력 폴더 분리(§4): PDF 는 output/pdf, EPS 는 output/eps. ──
    #    'eps' 단독 모드에서도 PDF 는 '중간 산출물'로 반드시 만들어야 한다(EPS 는 PDF 에서
    #    변환되므로). 중간 PDF 는 _epstmp 폴더에 두고 끝에 정리한다(최종엔 EPS 만 남김).
    pdf_dir = os.path.join(out_dir, "output", "pdf")
    eps_dir = os.path.join(out_dir, "output", "eps")
    tmp_pdf_dir = os.path.join(out_dir, "output", "_epstmp")  # eps 단독 모드의 중간 PDF
    preview_dir = os.path.join(out_dir, "preview")
    # 최종 PDF 를 남길 폴더(both/pdf 면 output/pdf, eps 단독이면 임시).
    pdf_out_dir = pdf_dir if want_pdf else tmp_pdf_dir
    os.makedirs(pdf_out_dir, exist_ok=True)
    if want_eps:
        os.makedirs(eps_dir, exist_ok=True)

    # EPS 변환기 import(여기서만 — eps 미사용 시 의존 회피). GS 1회 탐색 결과를 캐시.
    _eps = None
    eps_gs_exe = None
    eps_gs_warned = False
    if want_eps:
        from . import eps as _eps  # noqa: N813  (pdf_to_eps/verify_eps/...)
        eps_gs_exe = _eps.find_ghostscript(gs_path)

    outputs: list = []
    skipped: list = []
    warnings: list = []
    missing_sizes: set = set()
    used_filenames: set = set()  # 파일명 충돌 회피용

    # (이슈3) 비활성 사이즈가 있으면 작업 시작 시 1회 안내(warnings 정의 이후라 안전).
    if disabled_map:
        for nm, reason in disabled_map.items():
            warnings.append(
                f"🟡 [사이즈 {nm}] 비활성(disabled) — 출고 차단됨. 사유: {reason}")

    # ── base 디자인 투명도 선(先)평탄화 (왜: 투명도가 남으면 EPS 변환 때 래스터화되고
    #    verify 의 '투명도 없음' 검사가 FAIL 난다 → 시작 시 한 번 벡터 평탄화해 모든
    #    선수 합성이 같은 '깨끗한' 디자인을 base 로 쓰게 한다). 평탄화 결과는 out_dir 안에
    #    1개만 만들어 재사용한다(선수마다 다시 평탄화하지 않음). ──
    base_design = design_pdf  # 평탄화 실패/불필요 시 원본을 그대로 base 로 폴백
    flatten_info = None
    flat_path = os.path.join(out_dir, "_flattened_design.pdf")
    try:
        flatten_info = flatten_transparency(design_pdf, flat_path)
        base_design = flat_path  # 이후 compose/verify 는 평탄화본을 기준으로 사용
        for w in flatten_info.get("warnings", []):
            warnings.append(f"[평탄화] {w}")
        if flatten_info.get("transparency_left"):
            # 평탄화 후에도 투명도가 남으면 경고만(부분성공). verify 가 최종 판정한다.
            warnings.append(
                f"[평탄화] 투명도 잔존: {flatten_info['transparency_left']} — 수동 확인 필요")
    except Exception as e:
        # 평탄화 자체 실패는 치명적이지 않게 흘린다(원본으로 진행 — verify 가 막아준다).
        warnings.append(f"[평탄화] 실패(원본 디자인으로 진행): {e}")

    # ── (작업3②) 디자인 '패턴선' OCG 콘텐츠 제거 → base 디자인에서 패턴선이 사라진다.
    #    왜 여기서(평탄화본에): 모든 선수가 같은 base 를 공유하므로 1회만 처리하면 된다.
    #    cutline.hide_design_cutline_layer 가 true 일 때만(없으면 U넥 등 기존 동작 보존).
    #    OCG OFF 는 compose 가 OCProperties 를 버려 무효 → 콘텐츠 삭제로 확실히 없앤다.
    _cutline_cfg0 = preset_dict.get("cutline") or {}
    hide_info = None
    if _cutline_cfg0.get("hide_design_cutline_layer"):
        try:
            hidden_path = os.path.join(out_dir, "_design_no_cutline.pdf")
            hide_info = hide_design_cutline_layer(base_design, hidden_path)
            if hide_info.get("found"):
                base_design = hidden_path  # 패턴선 없는 base 로 교체
                warnings.append(
                    f"[패턴선] 디자인 OCG 레이어 제거: {hide_info['removed_layers']} "
                    f"({hide_info['removed_spans']}구간) — 디자인 패턴선 비표시(두 줄 방지).")
            elif _cutline_cfg0.get("hide_design_cutline_layer") != "if_present":
                # (2026-10-21) 새 등록은 «있으면 지운다(if_present)» — 패턴선 레이어가 없는 게 보통이라 알리지 않는다
                warnings.append(
                    "🟡 [패턴선] 디자인에서 '패턴선/재단선' OCG 마킹을 찾지 못해 제거를 건너뜁니다"
                    "(레이어명/구조 확인 필요). 우리 재단선만 1줄로 그려집니다.")
        except Exception as e:
            warnings.append(f"🟡 [패턴선] OCG 레이어 제거 실패(디자인 패턴선 잔존 가능): {e}")

    # ── (2026-10-20) 디자이너가 꺼 둔 레이어는 출력에서도 뺀다(compose 가 켜짐/꺼짐을 버려 찍히던 문제).
    #    preset.hidden_layers.remove=false 면 끈다(예전 동작).
    if (preset_dict.get("hidden_layers") or {}).get("remove", True):
        try:
            off_path = os.path.join(out_dir, "_design_no_hidden.pdf")
            off_info = hide_off_layers(design_pdf, base_design, off_path)
            if off_info.get("found"):
                base_design = off_path
                warnings.append(f"[숨김 레이어] 디자인에서 꺼 둔 레이어 {off_info['removed_layers']} "
                                f"({off_info['removed_spans']}구간)를 출력에서 뺐습니다.")
        except Exception as e:
            warnings.append(f"🟡 [숨김 레이어] 꺼 둔 레이어 빼기 실패(출력에 찍힐 수 있음): {e}")

    # ── (2026-10-20) 디자인 영역 자동 짝짓기: 등록 때 영역을 안 맞춘 패턴(design.auto_regions)은 디자인 속
    #    재단 윤곽을 모양으로 찾아 조각마다 영역을 정한다(좌우 거울까지 가림 — 왼소매 그림이 오른소매에 가지 않게).
    #    못 찾은 조각은 등록 때 어림값 그대로. 화면에서 맞춘 영역(auto_regions 없음)은 건드리지 않는다.
    extra_sides: list = []   # 양면 두 번째 면 이후의 프리셋 사본(영역만 그 면으로)
    if (preset_dict.get("design") or {}).get("auto_regions"):
        extra_sides = _auto_regions(preset_dict, design_pdf, warnings)

    # ── (2026-10-20) 함께 찍을 패턴(상의 + 하의): preset.companion.pattern 이 있으면 같은 디자인에서 그 패턴 조각도
    #    윤곽으로 찾아 같은 장 아래에 찍는다. 사이즈는 행의 bottom_size(없으면 상의 사이즈).
    companion = None
    _ccfg = preset_dict.get("companion") or {}
    if _ccfg.get("pattern"):
        try:
            _cname = str(_ccfg["pattern"])
            if os.path.basename(_cname) != _cname or ":" in _cname or ".." in _cname:
                raise ValueError("패턴 이름에 경로 문자가 있습니다")      # 패턴 폴더 밖을 가리키지 못하게
            _cpath = os.path.join(os.path.dirname(preset_dict["_dir"]), _cname, "preset.json")
            _cp = load_preset(_cpath)
            _csides = _auto_regions(_cp, design_pdf, warnings, label="함께 찍을 패턴 ")
            if _cp.pop("_auto_failed", False) or not _cp["pieces"]:
                # 하의 조각을 이 디자인에서 하나도 못 찾으면, 하의 프리셋의 옛 영역(다른 디자인 좌표)으로 잘라 붙이지 않는다
                raise ValueError("이 디자인에서 하의 조각을 찾지 못했습니다")
            companion = {"preset": _cp, "sides": _csides, "size_key": _ccfg.get("size_key") or "bottom_size",
                         "size_map": {sd["name"]: sd for sd in _cp["sizes"]},
                         "precise": _has_precise_areas(_cp) or (_cp.get("cutline") or {}).get("draw_from") == "svg_polygon"}
            warnings.append(f"[함께 찍기] «{_ccfg['pattern']}» 조각을 같은 장 아래에 함께 찍습니다.")
        except Exception as e:
            warnings.append(f"🟡 [함께 찍기] 함께 찍을 패턴 «{_ccfg.get('pattern')}» 을 못 읽어 건너뜁니다: {e}")

    # ── (작업 A) 본체색 1회 결정: preset.body_fill > 디자인 자동감지 > None(채움 생략). ──
    #    왜 1회만: 모든 선수가 같은 base 디자인을 공유하므로 본체색도 1번만 정하면 된다.
    #    우선순위 이유: preset 에 디자이너가 명시한 값(body_fill)이 가장 정확하다(자동감지는
    #    휴리스틱=면적 최대 단색이라 디자인에 따라 빗나갈 수 있음). 둘 다 없으면 None →
    #    place_block 이 채움을 생략해 '기존과 완전 동일' 동작(하위호환).
    body_fill = None
    pf = preset_dict.get("body_fill")
    if pf and len(pf) == 4:
        body_fill = tuple(float(v) for v in pf)
        warnings.append(f"[본체색] preset.body_fill 사용: {body_fill} — 패턴선 안쪽 흰틈 채움.")
    else:
        # 자동감지: detect_background_cmyk 는 pikepdf.Pdf 객체를 받는다(path 아님).
        try:
            _bg_pdf = pikepdf.open(base_design)
            try:
                from .flatten import detect_background_cmyk
                detected = detect_background_cmyk(_bg_pdf, page_index=0)
            finally:
                _bg_pdf.close()
            if detected:
                body_fill = tuple(float(v) for v in detected)
                warnings.append(f"[본체색] 자동감지: {body_fill} — 패턴선 안쪽 흰틈 채움.")
            else:
                warnings.append("🟡 [본체색] 자동감지 실패(채움 생략). 필요시 preset.body_fill 지정 권장.")
        except Exception as e:
            warnings.append(f"🟡 [본체색] 감지 중 오류(채움 생략): {e}")

    # 정밀배치 경로 사용 여부(새 area 가 하나라도 있으면 place_*/감싸기 경로). 없으면 폴백.
    use_precise = _has_precise_areas(preset_dict)
    # (2026-10-20 노치) 노치 설정이 있는 프리셋은 번호 영역이 없어도(하의 등) 정밀 경로로 — 폴백(build_layouts)은
    #   조각 윤곽 재단선(svg_polygon)을 그리지 않아 노치가 빠진다. 글자 영역이 없으면 _inject 가 건너뛴다.
    #   노치 설정이 없는 프리셋은 이 줄과 무관(기존 판정 그대로).
    #   (2026-10-20) 노치가 없어도 «조각 윤곽 재단선(svg_polygon)» 설정이면 정밀 경로 — 새 등록은 모두 이 설정이다.
    if (preset_dict.get("cutline") or {}).get("draw_from") == "svg_polygon":
        use_precise = True

    # ── (작업2/B) cover/블리드 배수 결정: preset.cutline.bleed 또는 cover_bleed 키가 있을 때만. ──
    #    왜 키가 있을 때만: 없으면(U넥 등) bleed=None → _job_piece_transform 이 기존 contain
    #    경로를 타 회귀가 0 이 된다(U넥 보호). cover/블리드는 '명시적 opt-in'.
    #    cover_bleed 는 두 형태 허용(하위호환):
    #      · float(예: 1.03)  → 전 사이즈 동일 단일 cover(기존 동작).
    #      · dict({auto:true,k,min,max}) → 사이즈별 앞판 기준 자동 산출(_build_precise_layout 에서).
    #    여기서는 '값을 그대로' 보존해 _build_precise_layout 에 넘긴다(해석은 거기서 사이즈별로).
    cover_bleed = preset_dict.get("cover_bleed")
    if cover_bleed is None:
        cover_bleed = _cutline_cfg0.get("bleed")  # cutline.bleed 도 허용(방침 a)
    if isinstance(cover_bleed, dict):
        # dict(auto) — 그대로 통과(사이즈별 산출). auto:true 면 안내만 1회.
        if cover_bleed.get("auto"):
            warnings.append(
                "[블리드] 자동 블리드(auto) — 사이즈별 앞판 기준으로 cover 배수를 산출합니다"
                f" (k={cover_bleed.get('k', 1.3)}, clamp[{cover_bleed.get('min', 1.0)},"
                f"{cover_bleed.get('max', 1.12)}]).")
    else:
        cover_bleed = float(cover_bleed) if cover_bleed else None
        if cover_bleed:
            warnings.append(f"[블리드] cover+블리드 적용(배수 {cover_bleed}) — 디자인으로 조각 꽉 채움.")

    # ── (이슈4) 빨간 재단선 1회 추출 (preset 에 cutline 키가 있을 때만). ──
    #    왜 한 번만: 디자인은 모든 선수가 공유하므로 stroke 추출은 1회로 충분(성능).
    #    cutline 키가 없으면(U넥 등) 추출 자체를 건너뛰어 '기존 동작' 그대로 유지한다.
    cutline_strokes = []          # 매핑 가능한 디자인좌표 stroke 목록(추출 방식에서만 채움)
    cutline_cfg = preset_dict.get("cutline")
    cutline_mapped_expected = 0   # '재단선 보존' 체크용 기대 수
    if cutline_cfg and cutline_cfg.get("draw_from") == "svg_polygon":
        # ── (작업3①) 폴리곤 방식: 디자인에서 추출하지 않고 조각 윤곽을 직접 그린다.
        #    재단선 보존 기대 수 = 조각 개수(조각당 빨강 1줄). 추출(_extract_red_strokes) 미호출.
        cutline_mapped_expected = len(preset_dict.get("pieces", []))
        warnings.append(
            f"[재단선] svg_polygon 방식 — 조각 윤곽 {cutline_mapped_expected}개를 빨강 1줄로 그립니다"
            f"(stroke {cutline_cfg.get('stroke_width', 2.0)}pt, 디자인 추출 생략).")
    elif cutline_cfg:
        red = cutline_cfg.get("color_cmyk", [0, 0.96, 0.95, 0])
        tol = float(cutline_cfg.get("match_tol", 0.05))
        try:
            cutline_strokes = _extract_red_strokes(base_design, red, tol)
        except Exception as e:
            warnings.append(f"[재단선] 추출 실패(재단선 없이 진행): {e}")
            cutline_strokes = []
        # 매핑 기대 수 미리 계산(경고는 레이아웃 생성 시 1회만 나오게 별도 리스트 사용).
        _pre_warn: list = []
        cutline_mapped_expected = sum(
            len(v) for v in _map_strokes_to_pieces(
                cutline_strokes, preset_dict["pieces"], _pre_warn).values())
        n_found = len(cutline_strokes)
        n_exp = int(cutline_cfg.get("expected_strokes", 0))
        if n_found == 0:
            warnings.append(
                "🟡 [재단선] 디자인에서 빨간 stroke 를 찾지 못했습니다(추출 0개). "
                f"기대 {n_exp}개 — 현재 템플릿은 재단선 레이어가 PDF 상 비어 있을 수 있습니다. "
                "재단선이 보이는 소스로 재내보내면 자동 보존됩니다.")
        elif n_found < n_exp:
            warnings.append(
                f"🟡 [재단선] 추출 {n_found}개 < 기대 {n_exp}개 — 일부 재단선이 누락됐을 수 있습니다.")
        else:
            warnings.append(f"[재단선] 추출 {n_found}개 (매핑 {cutline_mapped_expected}개).")

    # ── 형식별 산출 집계(summary.format_summary 용). ──
    fmt_counts = {
        "pdf_produced": 0, "pdf_verify_pass": 0,
        "eps_produced": 0, "eps_verify_pass": 0, "eps_skipped": 0,
    }

    def _make_eps_for(pdf_path: str, ident: str, sheet_size, page: int = 1):
        """공통 PDF 1개를 EPS 로 변환 + verify_eps 한다(want_eps 일 때만 호출).

        반환: (eps_rel|None, checks_eps_list|None). GS 미설치/실패면 (None, None)+경고.
        sheet_size 는 verify_eps 의 BoundingBox 비교용(없으면 존재만 확인).
        """
        nonlocal eps_gs_warned
        eps_out = os.path.join(eps_dir, f"{ident}.eps")
        conv = _eps.pdf_to_eps(pdf_path, eps_out, ghostscript_path=gs_path, page=page)
        for w in conv["warnings"]:
            # GS 미설치 경고는 작업당 1회만(선수마다 반복 안 함).
            if "찾지 못했" in w:
                if not eps_gs_warned:
                    warnings.append(f"[EPS] {w}")
                    eps_gs_warned = True
            else:
                warnings.append(f"[EPS {ident}] {w}")
        if not conv["produced"]:
            fmt_counts["eps_skipped"] += 1
            return None, None
        fmt_counts["eps_produced"] += 1
        checks_eps = _eps.eps_checks_to_dicts(
            _eps.verify_eps(eps_out, sheet_size=sheet_size))
        if all(c["ok"] for c in checks_eps):
            fmt_counts["eps_verify_pass"] += 1
        eps_rel = os.path.relpath(eps_out, out_dir).replace("\\", "/")
        return eps_rel, checks_eps

    # ── (2026-10-20) 사이즈 택: 디자인 속 기준 사이즈 택을 한 번 찾아 두고, 사이즈마다 그 사이즈 택을 덮어 찍는다 ──
    #    preset.size_tag.enabled=false 면 끈다. 못 찾으면(점수 낮음·라이브러리 없음) 아무것도 안 한다(예전 그대로).
    tag_hits = []   # [(조각 번호, hit)]
    _all_tag_hits: list = []

    def _map_tags(pieces_list):
        """찾은 택마다, 그 택을 품은 조각 번호(영역 기준)."""
        res = []
        for h in _all_tag_hits:
            cx = (h["rect_pt"][0] + h["rect_pt"][2]) / 2
            cy = (h["rect_pt"][1] + h["rect_pt"][3]) / 2
            for pi, pdef in enumerate(pieces_list):
                rx0, ry0, rx1, ry1 = pdef["design_region_pt"]
                if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                    res.append((pi, h))
                    break
        return res

    if (preset_dict.get("size_tag") or {}).get("enabled", True):
        try:
            from .size_tag import find_tags, overlay_for, load_library
            _tag_lib = load_library()
            _base_sz = (preset_dict.get("design") or {}).get("base_size") or ""
            _all_tag_hits = find_tags(base_design, _base_sz, _tag_lib)
            tag_hits = _map_tags(preset_dict["pieces"])
            if tag_hits:
                warnings.append("[택] 기준 사이즈 택 " + ", ".join(
                    f"{preset_dict['pieces'][pi].get('name') or preset_dict['pieces'][pi].get('id')}({h['family']} {h['size']}, 일치 {h['score']})"
                    for pi, h in tag_hits) + " — 사이즈마다 그 사이즈 택으로 바꿔 찍습니다.")
        except Exception as e:
            warnings.append(f"🟡 [택] 사이즈 택 찾기를 건너뜀: {e}")

    side_tag_hits = [_map_tags(pd2["pieces"]) for pd2 in extra_sides] if _all_tag_hits else [[] for _ in extra_sides]

    # (2026-10-20) 양면 본체색: 면마다 그 면 조각 자리에서 다시 감지(흰 면 색으로 자주 면 틈을 칠하지 않게).
    #   preset.body_fill 을 디자이너가 적었으면 모든 면에 그 색.
    side_fill: list = []
    # (2026-10-21) 영역을 디자인 윤곽으로 맞춘 작업은 면이 하나여도 «찍는 조각 자리»에서 본체색을 다시 잰다 —
    #   한 대지에 홈·원정 두 벌이 있는데 한 벌만 찍으면, 페이지 전체로 재면 원정 색(노랑)으로 홈 소매 틈을 칠했다(신탄진 점검).
    if extra_sides or (preset_dict.get("design") or {}).get("auto_regions"):
        if preset_dict.get("body_fill") or body_fill is None:
            side_fill = [body_fill for _ in extra_sides]
        else:
            try:
                from .flatten import detect_background_cmyk

                def _union(pieces_list):
                    rs = [p["design_region_pt"] for p in pieces_list]
                    return (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))
                with pikepdf.open(base_design) as _bgp:
                    f1 = detect_background_cmyk(_bgp, 0, region=_union(preset_dict["pieces"]))
                    if f1:
                        body_fill = tuple(float(v) for v in f1)
                    for pd2 in extra_sides:
                        fk = detect_background_cmyk(_bgp, 0, region=_union(pd2["pieces"]))
                        side_fill.append(tuple(float(v) for v in fk) if fk else None)
                warnings.append(f"[본체색] 찍는 조각 자리에서 감지: 1면 {body_fill}" + "".join(
                    f" · {i + 2}면 {c}" for i, c in enumerate(side_fill)))
            except Exception as e:
                side_fill = [None for _ in extra_sides]
                warnings.append(f"🟡 [본체색] 면별 감지 실패(두 번째 면부터 채움 생략): {e}")
    # (2026-10-21) 함께 찍는 하의도 자기 조각 자리에서 본체색을 잰다 — 예전엔 하의 틈을 아예 안 칠해서
    #   갈색 반바지 가장자리에 흰 틈이 생겼다(웹툰 점검). 상의 본체색을 끈 작업(body_fill 없음)은 그대로 둔다.
    if companion is not None and body_fill is not None:
        try:
            from .flatten import detect_background_cmyk
            with pikepdf.open(base_design) as _bgp:
                for cpd in [companion["preset"]] + companion["sides"]:
                    rs = [p.get("design_region_pt") for p in cpd.get("pieces", []) if p.get("design_region_pt")]
                    if cpd.get("body_fill") or not rs:
                        continue
                    fk = detect_background_cmyk(_bgp, 0, region=(min(r[0] for r in rs), min(r[1] for r in rs),
                                                                 max(r[2] for r in rs), max(r[3] for r in rs)))
                    if fk:
                        cpd["body_fill"] = [float(v) for v in fk]
        except Exception as e:
            warnings.append(f"🟡 [본체색] 함께 찍는 패턴 본체색 감지 실패(채움 생략): {e}")
    if companion is not None:
        companion["tags"] = [_map_tags(pdx["pieces"]) if _all_tag_hits else []
                             for pdx in [companion["preset"]] + companion["sides"]]

    def _apply_size_tags(layout, size: str, row_warns: list, hits=None) -> None:
        for pi, h in (tag_hits if hits is None else hits):
            if size == h["size"] or pi >= len(layout.pieces):
                continue          # 기준 사이즈는 디자인 택이 이미 맞다
            ov = overlay_for(h, size, _tag_lib)
            if ov is None:
                row_warns.append(f"🟡 [택] {h['family']} 계열에 «{size}» 택이 없어 기준({h['size']}) 택이 그대로 찍힙니다.")
                continue
            layout.pieces[pi].overlays.append(ov)

    # single 모드에서 누적할 (layout, meta) 목록.
    single_layouts: list = []
    single_meta: list = []

    _NONE = {"-", "없음", "x", "X", "×", "0", "없슴"}
    for idx, row in enumerate(order_rows):
        size = (row.get("size") or "").strip()
        name = row.get("name") or ""
        number = row.get("number") or ""
        # (2026-10-21) 상의만·하의만: 함께 찍을 패턴이 있을 때 주문서 «하의» 칸이 «-/없음» 이면 상의만,
        #   상의 칸이 «-/없음» 이고 하의 사이즈가 있으면 하의만 찍는다(홍해 3XL «상의만»·S «하의만» 실측).
        _bsz = (row.get(companion["size_key"]) or "").strip() if companion is not None else ""
        top_only = companion is not None and _bsz in _NONE and _bsz != ""
        pants_only = companion is not None and size in _NONE and _bsz not in _NONE and _bsz != ""
        if pants_only:
            size = _bsz

        # ── 엣지: 사이즈 빈값 → skip ──
        if not size:
            skipped.append({"row": idx, "name": name, "reason": "사이즈 빈값"})
            continue
        # ── (이슈3) 비활성(결함) 사이즈 주문 → 크래시 없이 명확한 결함 사유로 skip ──
        #    왜 별도 분기(일반 missing 과 구분): 그냥 "없는 사이즈"로 흘리면 사유가 모호하다.
        #    disabled_sizes 에 든 사이즈는 '자산 결함으로 의도적 차단'이므로 결함 사유를
        #    그대로 알려준다. 5XL 등 다른 사이즈로 '대체'되지 않음 — size 가 정확히 일치해야만
        #    매칭되므로(size_map 에 3XL 자체가 없음) 대체 출고 경로가 원천적으로 없다.
        if size in disabled_map:
            reason = disabled_map[size]
            skipped.append({"row": idx, "name": name,
                            "reason": f"사이즈 '{size}' 비활성(자산 결함): {reason}"})
            warnings.append(
                f"🟡 [행{idx} {name or '(무명)'} {size}] 결함 사이즈 주문 → skip "
                f"(5XL 등으로 대체 출고하지 않음, 결함 사유: {reason}).")
            continue
        # ── 엣지: preset 에 없는 사이즈(아직 패턴 미확보 등) → skip + missing 집계 ──
        if size not in size_map and not pants_only:
            missing_sizes.add(size)
            skipped.append({"row": idx, "name": name,
                            "reason": f"preset 에 없는 사이즈 '{size}'"})
            continue

        # ── 이 선수의 사이즈만 남긴 preset 으로 레이아웃 1개 생성(배번/이름 주입). ──
        row_warns: list = []
        layout = None
        try:
            if pants_only:
                pass                                  # 하의만 — 상의는 안 찍는다(아래 함께 찍기만)
            elif use_precise:
                # 정밀 경로: place_number(앞·뒤)·place_name 으로 글자를 그리고, 각 글자를
                # 그 조각 transform 으로 감싸 디자인 위 정위치(시트좌표)에 박는다.
                layout = _build_precise_layout(
                    preset_dict, size_map[size],
                    number=number, name=name, warnings=row_warns,
                    cutline_strokes=cutline_strokes, cover_bleed=cover_bleed,
                    bg_cmyk=body_fill)
            else:
                # 폴백: 기존 rel_bbox(number_area/name_area) 기반 build_layouts(방식 A).
                layouts = build_layouts(_sized_preset(preset_dict, size_map[size]), base_design,
                                        number=number, name=name, warnings=row_warns)
                layout = layouts[0]  # 사이즈 1개를 줬으니 layout 도 1개.
        except Exception as e:  # 렌더 단계 행 실패는 흘린다(부분 성공).
            skipped.append({"row": idx, "name": name,
                            "reason": f"레이아웃 생성 실패: {e}"})
            continue
        if tag_hits and layout is not None:
            _apply_size_tags(layout, size, row_warns)
        if extra_sides and layout is not None:
            stack = [layout]
            try:
                for si, pd2 in enumerate(extra_sides):
                    if use_precise:
                        lay2 = _build_precise_layout(
                            pd2, size_map[size], number=number, name=name, warnings=row_warns,
                            cutline_strokes=cutline_strokes, cover_bleed=cover_bleed,
                            bg_cmyk=side_fill[si] if si < len(side_fill) else None)   # 면마다 본체색(자주 면에 흰 면 색 X)
                    else:
                        lay2 = build_layouts(_sized_preset(pd2, size_map[size]), base_design,
                                             number=number, name=name, warnings=row_warns)[0]
                    if side_tag_hits[si]:
                        _apply_size_tags(lay2, size, row_warns, side_tag_hits[si])
                    stack.append(lay2)
                layout = _stack_layouts(layout.name, stack)
            except Exception as e:
                row_warns.append(f"🟡 [양면] 두 번째 면을 못 만들어 첫 면만 찍습니다: {e}")
        if companion is not None and not top_only:
            if not (row.get(companion["size_key"]) or "").strip():
                companion["no_bottom"] = companion.get("no_bottom", 0) + 1
            csize = (_bsz if pants_only else (row.get(companion["size_key"]) or size or "")).strip()
            if csize not in companion["size_map"]:
                row_warns.append(f"🟡 [함께 찍기] 함께 찍을 패턴에 «{csize}» 사이즈가 없어 빼고 찍습니다.")
            else:
                try:
                    clays = []
                    for ci, cpd in enumerate([companion["preset"]] + companion["sides"]):
                        if companion["precise"]:
                            cl = _build_precise_layout(cpd, companion["size_map"][csize], number=None, name=None,
                                                       warnings=row_warns, cutline_strokes=None, cover_bleed=None,
                                                       bg_cmyk=cpd.get("body_fill"))
                        else:
                            cl = build_layouts(_sized_preset(cpd, companion["size_map"][csize]), base_design,
                                               warnings=row_warns)[0]
                        if companion["tags"][ci]:
                            _apply_size_tags(cl, csize, row_warns, companion["tags"][ci])
                        clays.append(cl)
                    layout = _stack_layouts(layout.name if layout is not None else size,
                                            ([layout] if layout is not None else []) + clays)
                except Exception as e:
                    row_warns.append(f"🟡 [함께 찍기] 함께 찍을 패턴을 못 만들어 빼고 찍습니다: {e}")

        if layout is None:
            skipped.append({"row": idx, "name": name, "reason": "하의만 행인데 하의를 만들지 못함"})
            continue
        if top_only:
            row_warns.append("[함께 찍기] 하의 칸이 비어 있음 표시(-) — 상의만 찍었습니다.")
        if pants_only:
            row_warns.append("[함께 찍기] 상의 칸이 «-» — 하의만 찍었습니다.")
        # 글리프 누락 등 행 경고는 선수 식별과 함께 전체 warnings 에 누적(사람 검수용).
        row_warns = list(dict.fromkeys(row_warns))   # 양면이면 면마다 같은 경고가 두 번 나온다 — 한 번만
        for w in row_warns:
            warnings.append(f"[행{idx} {name or '(무명)'} {size}] {w}")

        # ── 파일/페이지 식별자 ──
        fn_num = _num_for_filename(number)
        base_id = f"{size}_{fn_num}_{_safe_name(name)}"
        # 충돌 회피: 이미 쓴 식별자면 _2, _3 … 접미사.
        ident = base_id
        n = 2
        while ident in used_filenames:
            ident = f"{base_id}_{n}"
            n += 1
        used_filenames.add(ident)

        meta = {"row": idx, "size": size, "name": name, "number": number,
                "qty": row.get("qty", ""), "ident": ident}

        if split == "single":
            # 페이지 식별을 위해 SizeLayout.name 을 선수 식별자로 덮어쓴다(읽기 전용 표식).
            layout.name = ident
            single_layouts.append(layout)
            single_meta.append(meta)
            continue

        # ── per_player: 선수 1명 = PDF 1개(원자적 저장) → verify → (옵션)미리보기 ──
        #    base_design = 평탄화된 디자인(투명도 제거본). compose·verify 모두 같은 base 사용.
        #    PDF 는 형식과 무관하게 항상 만든다(EPS 도 이 PDF 에서 변환). want_pdf 가 아니면
        #    임시 폴더(_epstmp)에 두고 EPS 변환 후 정리한다.
        pdf_path = os.path.join(pdf_out_dir, f"{ident}.pdf")
        try:
            placements = _atomic_save_compose(base_design, [layout], pdf_path)
        except Exception as e:
            skipped.append({"row": idx, "name": name, "reason": f"합성 실패: {e}"})
            used_filenames.discard(ident)
            continue

        checks = verify_output(pdf_path, base_design, placements)
        verify_pass = all_passed(checks)
        fmt_counts["pdf_produced"] += 1
        if verify_pass:
            fmt_counts["pdf_verify_pass"] += 1

        # ── (이슈4) '재단선 보존' 체크: 출력의 빨간 stroke 수 ≥ 매핑 기대 수. ──
        #    verify_pass(불변 검사) 에는 섞지 않는다 — 재단선은 별도 표식 체크로 보고만 한다.
        check_dicts = _checks_to_dicts(checks)
        if cutline_cfg:
            red = cutline_cfg.get("color_cmyk", [0, 0.96, 0.95, 0])
            tol = float(cutline_cfg.get("match_tol", 0.05))
            n_out = _count_red_strokes_in_output(pdf_path, red, tol)
            ok = n_out >= cutline_mapped_expected
            check_dicts.append({
                "name": "재단선 보존",
                "ok": ok,
                "detail": f"출력 빨간 stroke {n_out}개 (매핑 기대 {cutline_mapped_expected}개)",
            })

        preview_rel = None
        if make_preview and _preview is not None:
            try:
                os.makedirs(preview_dir, exist_ok=True)
                png = os.path.join(preview_dir, f"{ident}.png")
                _preview.render_page(pdf_path, png, page=0)
                preview_rel = os.path.relpath(png, out_dir).replace("\\", "/")
            except Exception as e:
                warnings.append(f"[행{idx} {name}] 미리보기 생성 실패(무시): {e}")

        # ── (§4) EPS 변환 + verify_eps (want_eps 일 때만). PDF 시트 크기로 BBox 비교. ──
        eps_rel = None
        checks_eps = None
        if want_eps and _eps is not None:
            sheet = _eps.sheet_size_from_pdf(pdf_path)
            eps_rel, checks_eps = _make_eps_for(pdf_path, ident, sheet)

        # 'eps' 단독 모드면 중간 PDF 는 정리(최종엔 EPS 만 남김). both/pdf 면 유지.
        if not want_pdf and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

        outputs.append({
            "size": size, "name": name, "number": number,
            # want_pdf 가 아니면(eps 단독) PDF 는 임시였으므로 경로를 남기지 않는다.
            "pdf": (os.path.relpath(pdf_path, out_dir).replace("\\", "/") if want_pdf else None),
            "eps": eps_rel,
            "preview": preview_rel,
            "checks": check_dicts,
            "checks_eps": checks_eps,
            "verify_pass": verify_pass,
        })

    # ── single 모드 마무리: 누적 레이아웃을 1회 compose → 1회 verify ──
    if split == "single" and single_layouts:
        job_name = os.path.basename(os.path.normpath(out_dir)) or "job"
        pdf_path = os.path.join(pdf_out_dir, f"{_safe_name(job_name)}_all.pdf")
        placements = _atomic_save_compose(base_design, single_layouts, pdf_path)
        checks = verify_output(pdf_path, base_design, placements)
        verify_pass = all_passed(checks)
        fmt_counts["pdf_produced"] += 1
        if verify_pass:
            fmt_counts["pdf_verify_pass"] += 1

        # ── (이슈4) '재단선 보존' 체크(single): 전 페이지 합산 stroke ≥ 기대×페이지수. ──
        check_dicts = _checks_to_dicts(checks)
        if cutline_cfg:
            red = cutline_cfg.get("color_cmyk", [0, 0.96, 0.95, 0])
            tol = float(cutline_cfg.get("match_tol", 0.05))
            n_pages = len(single_layouts)
            n_out = sum(_count_red_strokes_in_output(pdf_path, red, tol, page_index=pi)
                        for pi in range(n_pages))
            exp = cutline_mapped_expected * n_pages
            check_dicts.append({
                "name": "재단선 보존",
                "ok": n_out >= exp,
                "detail": f"출력 빨간 stroke {n_out}개 (매핑 기대 {exp}개 = {cutline_mapped_expected}×{n_pages}p)",
            })

        previews_rel = []
        if make_preview and _preview is not None:
            try:
                os.makedirs(preview_dir, exist_ok=True)
                pngs = _preview.render_previews(pdf_path, preview_dir, prefix=_safe_name(job_name))
                previews_rel = [os.path.relpath(p, out_dir).replace("\\", "/") for p in pngs]
            except Exception as e:
                warnings.append(f"single 미리보기 생성 실패(무시): {e}")

        # ── (§4) EPS 변환(single): EPS 는 1페이지 포맷이라 페이지별로 1개씩 변환한다. ──
        eps_list = None
        checks_eps_list = None
        if want_eps and _eps is not None:
            eps_list = []
            checks_eps_list = []
            sheet = _eps.sheet_size_from_pdf(pdf_path)
            for pi in range(len(single_layouts)):
                ident = single_meta[pi]["ident"]
                er, ce = _make_eps_for(pdf_path, ident, sheet, page=pi + 1)
                eps_list.append(er)
                checks_eps_list.append(ce)

        # 'eps' 단독 모드면 중간 PDF 정리.
        if not want_pdf and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

        # single 은 다페이지 1개라 outputs 도 1개로 묶되, 어떤 선수가 몇 페이지인지 players 로 남긴다.
        outputs.append({
            "size": "(multi)", "name": "(전체)", "number": "",
            "pdf": (os.path.relpath(pdf_path, out_dir).replace("\\", "/") if want_pdf else None),
            "eps": eps_list,
            "preview": previews_rel,
            "players": [{"page": i + 1, **single_meta[i]} for i in range(len(single_meta))],
            "checks": check_dicts,
            "checks_eps": checks_eps_list,
            "verify_pass": verify_pass,
        })

    # ── summary 집계 ──
    produced = len(outputs)
    verify_ok = sum(1 for o in outputs if o.get("verify_pass"))
    if companion is not None and companion.get("no_bottom"):
        warnings.append(f"🟡 [함께 찍기] 하의 사이즈가 없는 {companion['no_bottom']}행은 상의 사이즈로 하의를 찍었습니다 — "
                        "상·하의 사이즈가 다르면 주문서 «하의» 칸을 채워 다시 만들어 주세요.")
    summary = {
        "job_dir": os.path.abspath(out_dir),
        "split": split,
        "total_players": len(order_rows),
        "produced": produced,
        "verify_pass": verify_ok,
        "verify_fail": produced - verify_ok,
        "skipped": skipped,
        "warnings": warnings,
        "missing_sizes": sorted(missing_sizes),
        # (이슈3) 비활성 사이즈 목록(사유 포함) — 어떤 사이즈가 결함으로 차단됐는지 추적.
        #   disabled_map 은 이미 {이름 → 사유} 형태(preset.disabled_sizes 섹션 출처)다.
        "disabled_sizes": dict(disabled_map),
        # Phase C 배관 추적용: 정밀배치 경로 사용 여부 + 평탄화 결과 요약(있으면).
        "precise_placement": use_precise,
        "flatten": ({
            "bg": list(flatten_info["bg"]),
            "flattened_xobjects": flatten_info["flattened_xobjects"],
            "recolored_fills": flatten_info["recolored_fills"],
            "alpha_gstates_fixed": flatten_info["alpha_gstates_fixed"],
            # 제거한 투명도 그룹 수(EPS 벡터화 트리거 제거 여부 추적). 0 이면 EPS 래스터 위험.
            "groups_removed": flatten_info.get("groups_removed", 0),
            "transparency_left": flatten_info["transparency_left"],
        } if flatten_info else None),
        # 이슈4 추적용: 재단선 추출/매핑 요약(cutline 키 없으면 None).
        "cutline": ({
            "found": len(cutline_strokes),
            "expected": int(cutline_cfg.get("expected_strokes", 0)),
            "mapped": cutline_mapped_expected,
        } if cutline_cfg else None),
        # ── (§4) 출력 형식 + 형식별 산출/검증 집계. ──
        #    format        : 실제 적용된 형식("pdf"|"eps"|"both").
        #    ghostscript   : EPS 변환에 쓴 GS 경로(없으면 None — fallback 으로 PDF 만 산출).
        #    format_summary: 형식별 produced/verify 카운트(PDF·EPS 따로).
        "format": fmt,
        "ghostscript": eps_gs_exe if want_eps else None,
        "format_summary": {
            "pdf": {"produced": fmt_counts["pdf_produced"],
                    "verify_pass": fmt_counts["pdf_verify_pass"]},
            "eps": {"produced": fmt_counts["eps_produced"],
                    "verify_pass": fmt_counts["eps_verify_pass"],
                    "skipped": fmt_counts["eps_skipped"]},
        },
    }
    result = {"outputs": outputs, "summary": summary}

    # ── 'eps' 단독 모드에서 쓴 중간 PDF 임시 폴더 정리(비어 있으면 삭제). ──
    if not want_pdf and os.path.isdir(tmp_pdf_dir):
        try:
            # 남은 파일이 있어도 안전하게 모두 제거(임시 PDF 전용 폴더).
            for f in os.listdir(tmp_pdf_dir):
                try:
                    os.remove(os.path.join(tmp_pdf_dir, f))
                except OSError:
                    pass
            os.rmdir(tmp_pdf_dir)
        except OSError:
            pass

    # ── job.json 덤프(폴더+JSON 저장 원칙). 원자적으로 쓴다. ──
    job_json = os.path.join(out_dir, "job.json")
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=out_dir)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, job_json)

    return result
