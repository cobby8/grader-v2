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
from .pdfutil import cm_matrix, scale_translate  # 글자 ops 를 시트좌표로 감쌀 cm 행렬 생성
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


def _job_piece_transform(design_region, poly, shrink_x, shrink_y):
    """grade.py `_piece_transform` 과 '동일한' 방식 A 변환을 계산한다(복제).

    ⚠️ grade.py 의 _piece_transform 은 '_' 접두 내부 함수라 공개 API 가 아니다.
       불변 제약(grade.py 무수정)을 지키기 위해 그 로직을 여기에 그대로 복제한다.
       (수식이 어긋나면 글자가 어긋나므로, grade.py 와 한 글자도 다르지 않게 유지할 것.)

    design_region : (dx0, dy0, dx1, dy1)  디자인에서 이 부위가 차지하는 영역.
    poly          : 이 조각의 패턴 윤곽(parse_svg 결과). poly.bbox 가 시트 위 위치.
    shrink_x/y    : 수축 보정 계수(보통 1.0).
    반환: scale_translate(s, ox, oy)  — (s, 0, 0, s, ox, oy) 행렬 튜플.
    """
    dx0, dy0, dx1, dy1 = design_region
    px0, py0, px1, py1 = poly.bbox  # 조각 윤곽 bbox(시트 좌표)

    dw, dh = (dx1 - dx0), (dy1 - dy0)   # 디자인 영역 크기
    pw, ph = (px1 - px0), (py1 - py0)   # 조각 크기

    # 등방 contain 배율(둘 중 작은 쪽) × shrink 보정 — grade.py 와 완전 동일.
    s = min(pw / dw, ph / dh) * min(shrink_x, shrink_y)

    # 디자인 영역 좌하단 → 조각 좌하단으로 옮기는 오프셋.
    ox = px0 - s * dx0
    oy = py0 - s * dy0
    return scale_translate(s, ox, oy)


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


def _build_precise_layout(preset: dict, size_def: dict, *,
                          number=None, name=None, warnings=None,
                          cutline_strokes=None) -> SizeLayout:
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
        transform = _job_piece_transform(pdef["design_region_pt"], poly, shrink_x, shrink_y)
        piece_transforms.append(transform)
        layout_pieces.append(
            Piece(outline=poly.points, transform=transform,
                  name=pdef.get("name", pdef.get("id", ""))))

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
            ops, warns = place_number(
                str(value), font_path,
                cap_h_pt=float(area.get("cap_height", 0)),
                center_x=float(area["center"][0]),
                center_y=float(area["center"][1]),
                color=color)
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
        tp.extra_ops = (tp.extra_ops + "\n" + wrapped) if tp.extra_ops else wrapped

    # 앞·뒤 번호는 '같은 배번'(number) — 앞=front 조각, 뒤=back 조각.
    _inject("front_number_area", "number", number)
    _inject("back_number_area", "number", number)
    _inject("back_name_area", "name", name)

    # ── 4) (이슈4) 빨간 재단선 주입: 디자인좌표 stroke ops 를 매핑 조각 transform 으로
    #       감싸 extra_ops 에 누적한다. 글자와 '같은 경로'라 디자인 위 정위치에 박힌다.
    #       extra_ops 는 q…Do…Q 의 '밖'(클립 외부)이라 너치가 조각 경계를 넘어도 안 잘린다.
    if cutline_strokes:
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
            make_preview: bool = True) -> dict:
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

    output_dir = os.path.join(out_dir, "output")
    preview_dir = os.path.join(out_dir, "preview")
    os.makedirs(output_dir, exist_ok=True)

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

    # 정밀배치 경로 사용 여부(새 area 가 하나라도 있으면 place_*/감싸기 경로). 없으면 폴백.
    use_precise = _has_precise_areas(preset_dict)

    # ── (이슈4) 빨간 재단선 1회 추출 (preset 에 cutline 키가 있을 때만). ──
    #    왜 한 번만: 디자인은 모든 선수가 공유하므로 stroke 추출은 1회로 충분(성능).
    #    cutline 키가 없으면(U넥 등) 추출 자체를 건너뛰어 '기존 동작' 그대로 유지한다.
    cutline_strokes = []          # 매핑 가능한 디자인좌표 stroke 목록
    cutline_cfg = preset_dict.get("cutline")
    cutline_mapped_expected = 0   # '재단선 보존' 체크용 기대 수(조각에 매핑된 stroke 수)
    if cutline_cfg:
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

    # single 모드에서 누적할 (layout, meta) 목록.
    single_layouts: list = []
    single_meta: list = []

    for idx, row in enumerate(order_rows):
        size = (row.get("size") or "").strip()
        name = row.get("name") or ""
        number = row.get("number") or ""

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
        if size not in size_map:
            missing_sizes.add(size)
            skipped.append({"row": idx, "name": name,
                            "reason": f"preset 에 없는 사이즈 '{size}'"})
            continue

        # ── 이 선수의 사이즈만 남긴 preset 으로 레이아웃 1개 생성(배번/이름 주입). ──
        sized = _sized_preset(preset_dict, size_map[size])
        row_warns: list = []
        try:
            if use_precise:
                # 정밀 경로: place_number(앞·뒤)·place_name 으로 글자를 그리고, 각 글자를
                # 그 조각 transform 으로 감싸 디자인 위 정위치(시트좌표)에 박는다.
                layout = _build_precise_layout(
                    preset_dict, size_map[size],
                    number=number, name=name, warnings=row_warns,
                    cutline_strokes=cutline_strokes)
            else:
                # 폴백: 기존 rel_bbox(number_area/name_area) 기반 build_layouts(방식 A).
                layouts = build_layouts(sized, base_design,
                                        number=number, name=name, warnings=row_warns)
                layout = layouts[0]  # 사이즈 1개를 줬으니 layout 도 1개.
        except Exception as e:  # 렌더 단계 행 실패는 흘린다(부분 성공).
            skipped.append({"row": idx, "name": name,
                            "reason": f"레이아웃 생성 실패: {e}"})
            continue

        # 글리프 누락 등 행 경고는 선수 식별과 함께 전체 warnings 에 누적(사람 검수용).
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
        pdf_path = os.path.join(output_dir, f"{ident}.pdf")
        try:
            placements = _atomic_save_compose(base_design, [layout], pdf_path)
        except Exception as e:
            skipped.append({"row": idx, "name": name, "reason": f"합성 실패: {e}"})
            used_filenames.discard(ident)
            continue

        checks = verify_output(pdf_path, base_design, placements)
        verify_pass = all_passed(checks)

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

        outputs.append({
            "size": size, "name": name, "number": number,
            "pdf": os.path.relpath(pdf_path, out_dir).replace("\\", "/"),
            "preview": preview_rel,
            "checks": check_dicts,
            "verify_pass": verify_pass,
        })

    # ── single 모드 마무리: 누적 레이아웃을 1회 compose → 1회 verify ──
    if split == "single" and single_layouts:
        job_name = os.path.basename(os.path.normpath(out_dir)) or "job"
        pdf_path = os.path.join(output_dir, f"{_safe_name(job_name)}_all.pdf")
        placements = _atomic_save_compose(base_design, single_layouts, pdf_path)
        checks = verify_output(pdf_path, base_design, placements)
        verify_pass = all_passed(checks)

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

        # single 은 다페이지 1개라 outputs 도 1개로 묶되, 어떤 선수가 몇 페이지인지 players 로 남긴다.
        outputs.append({
            "size": "(multi)", "name": "(전체)", "number": "",
            "pdf": os.path.relpath(pdf_path, out_dir).replace("\\", "/"),
            "preview": previews_rel,
            "players": [{"page": i + 1, **single_meta[i]} for i in range(len(single_meta))],
            "checks": check_dicts,
            "verify_pass": verify_pass,
        })

    # ── summary 집계 ──
    produced = len(outputs)
    verify_ok = sum(1 for o in outputs if o.get("verify_pass"))
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
            "transparency_left": flatten_info["transparency_left"],
        } if flatten_info else None),
        # 이슈4 추적용: 재단선 추출/매핑 요약(cutline 키 없으면 None).
        "cutline": ({
            "found": len(cutline_strokes),
            "expected": int(cutline_cfg.get("expected_strokes", 0)),
            "mapped": cutline_mapped_expected,
        } if cutline_cfg else None),
    }
    result = {"outputs": outputs, "summary": summary}

    # ── job.json 덤프(폴더+JSON 저장 원칙). 원자적으로 쓴다. ──
    job_json = os.path.join(out_dir, "job.json")
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=out_dir)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, job_json)

    return result
