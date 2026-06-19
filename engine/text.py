# -*- coding: utf-8 -*-
"""배번·이름 벡터 렌더 — 글자를 폰트 임베드 없이 'PDF 경로(아웃라인)'로 펴서 그린다.

────────────────────────────────────────────────────────────────────────────
큰 그림 (비유)
  · 보통 PDF에 글자를 넣으면 "폰트 파일"을 같이 끼워 넣어야 한다(임베드).
  · 공장 출력에서는 폰트가 빠지거나 다른 글꼴로 바뀌는 사고가 잦다.
  · 그래서 여기서는 글자를 '그림(선과 곡선)'으로 바꿔 버린다.
    → "김"이라는 글자를 더 이상 글자가 아니라, 선분과 곡선의 모음(벡터 도형)으로 그린다.
    → 폰트가 필요 없어지고, 어떤 공장 RIP에서도 똑같이 나온다.
────────────────────────────────────────────────────────────────────────────

핵심 사실(사전 조사로 확정):
  · Pretendard-Black/Bold.otf 는 CFF(큐빅 베지어) 아웃라인이라, 폰트 펜이 주는 곡선이
    PDF `c`(큐빅) 연산자에 그대로 1:1 대응한다 → 곡선을 직선으로 쪼개는 근사가 필요 없다.
  · unitsPerEm=2048 (폰트 내부 좌표 단위). pt 로 바꾸려면 (목표높이 / 2048) 을 곱한다.
  · 글자 색은 CMYK `k`(소문자=fill) 로만 칠한다 → device CMYK 무손실, verify PASS 유지.
  · 글자에는 이미지(Do)·투명도(ca/CA)·색공간(RGB) 연산자를 절대 쓰지 않는다.

공개 함수:
  render_text_ops(text, font_path, bbox_pt, color_cmyk, align="center")
      → (ops_str, warnings)  글자를 칸에 맞춘 PDF 연산자 문자열 + 경고 목록
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.boundsPen import ControlBoundsPen  # 글리프 '잉크 경계' 측정용(번호 높이 기준)
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.ttLib import TTFont

from .pdfutil import fmt

# ── 폰트 1회 로드 결과를 캐시(같은 폰트를 글자마다 다시 열면 느림) ──
#    key=폰트 절대경로 → (glyphset, cmap, units_per_em)
_FONT_CACHE: Dict[str, tuple] = {}


def _load_glyphset(font_path: str):
    """폰트를 열어 글리프셋·cmap·unitsPerEm 을 돌려준다(캐시).

    glyphset : 글리프이름 → 글리프(.draw(pen) 으로 윤곽, .width 로 advance)
    cmap     : 유니코드 코드포인트 → 글리프이름
    upm      : unitsPerEm (Pretendard=2048). 폰트단위→pt 환산의 분모.
    """
    if not os.path.exists(font_path):
        # 비개발자가 바로 알아챌 친절한 한글 메시지(conventions: 입력 선검증).
        raise FileNotFoundError(f"폰트 파일을 찾지 못했습니다: {font_path}")

    key = os.path.abspath(font_path)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    font = TTFont(font_path)
    glyphset = font.getGlyphSet()
    cmap = font.getBestCmap()              # 코드포인트→글리프이름 (가장 알맞은 cmap 자동 선택)
    upm = font["head"].unitsPerEm          # Pretendard=2048
    result = (glyphset, cmap, upm)
    _FONT_CACHE[key] = result
    return result


def _normalize_cmyk(color_cmyk) -> Tuple[float, float, float, float]:
    """CMYK 값을 0~1 범위로 정규화한다.

    비개발자가 [0,0,0,100] 처럼 0~100 으로 적을 수도 있어, 하나라도 1 보다 크면
    전체를 /100 한다(관대한 입력 허용). 값이 모자라면 0 으로 채운다.
    """
    vals = list(color_cmyk) + [0, 0, 0, 0]
    c, m, y, k = (float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]))
    if max(c, m, y, k) > 1.0:              # 0~100 스케일로 들어온 경우
        c, m, y, k = c / 100.0, m / 100.0, y / 100.0, k / 100.0
    # 0~1 밖으로 나가지 않게 잘라낸다(안전).
    clamp = lambda v: max(0.0, min(1.0, v))
    return clamp(c), clamp(m), clamp(y), clamp(k)


def _glyph_path_ops(glyphset, glyph_name: str, scale: float, dx: float, dy: float) -> str:
    """글리프 1개의 윤곽을 PDF 경로연산자(m/l/c/h)로 만든다.

    scale : 폰트단위 → pt 환산 배율 (= u = 목표스케일 / unitsPerEm).
            ⚠️ 글리프 좌표는 '폰트단위'라 이 값은 반드시 u(폰트단위→pt)여야 한다.
    dx,dy : 이 글자를 놓을 시작 위치(시트 절대좌표, pt). 폰트의 (0,0)=baseline 원점이 여기로 간다.

    좌표 변환 공식: 시트좌표 = 폰트좌표*scale + (dx,dy).
      moveTo(x,y)        → 'X Y m'   (서브패스 시작점)
      lineTo(x,y)        → 'X Y l'   (직선)
      curveTo(c1,c2,e)   → 'C1 C2 E c' (큐빅 베지어 — CFF라 항상 이 형태)
      closePath          → 'h'       (서브패스 닫기)
    """
    # ── 1) 합성 글리프(한글 등 addComponent) 분해 + 2) 쿼드라틱(TTF)→큐빅 변환 ──
    #   · DecomposingRecordingPen: 컴포넌트로 만든 글리프(한글 음절=자모 조합)를 실제 윤곽으로 편다.
    #     (이게 없으면 합성 글리프는 addComponent 만 남아 경로가 0개가 된다 — 한글 누락 버그)
    #   · Qu2CuPen(all_cubic=True): TTF 의 2차 베지어(qCurveTo)를 PDF c(3차)로 정확 변환.
    #     CFF(Pretendard)는 이미 3차라 그대로 통과(회귀 없음).
    dpen = DecomposingRecordingPen(glyphset)
    glyphset[glyph_name].draw(dpen)
    rec = RecordingPen()
    try:
        q2c = Qu2CuPen(rec, max_err=1.0, all_cubic=True)
        dpen.replay(q2c)
        commands = rec.value
    except Exception:
        commands = dpen.value  # 변환 실패 시 분해본이라도 사용(아래 qCurveTo 폴백 처리)

    # 폰트좌표 1점을 시트좌표 pt 로 옮기는 작은 도우미.
    tx = lambda x, y: (x * scale + dx, y * scale + dy)

    parts: List[str] = []
    for cmd, pts in commands:
        if cmd == "moveTo":
            (x, y) = pts[0]
            X, Y = tx(x, y)
            parts.append(f"{fmt(X)} {fmt(Y)} m")
        elif cmd == "lineTo":
            (x, y) = pts[0]
            X, Y = tx(x, y)
            parts.append(f"{fmt(X)} {fmt(Y)} l")
        elif cmd == "curveTo":
            # CFF 큐빅: (제어점1, 제어점2, 끝점) 3개 → PDF c 에 1:1.
            (c1, c2, e) = pts
            c1x, c1y = tx(*c1)
            c2x, c2y = tx(*c2)
            ex, ey = tx(*e)
            parts.append(
                f"{fmt(c1x)} {fmt(c1y)} {fmt(c2x)} {fmt(c2y)} {fmt(ex)} {fmt(ey)} c")
        elif cmd == "qCurveTo":
            # 방어코드: TTF(쿼드라틱) 폰트를 끼웠을 때 쿼드라틱→큐빅 승격.
            #   쿼드라틱 제어점 Q, 시작 P0, 끝 P2 → 큐빅 CP1=P0+2/3(Q-P0), CP2=P2+2/3(Q-P2).
            #   (Pretendard는 CFF라 여기 안 들어옴. 폰트 교체 대비 안전망.)
            # qCurveTo 는 여러 점이 이어질 수 있어 마지막 점이 끝점, 그 앞이 제어점이다.
            # 단순화를 위해 (제어점, 끝점) 2점 형태만 정확 처리하고, 그 외는 직선 근사.
            if len(pts) == 2:
                (q, p2) = pts
                # 시작점(P0)은 직전 명령의 끝점 — parts에서 추적하기 번거로우니
                # 폰트가 CFF가 아닐 때만 쓰이는 경로이므로, 제어점→끝점 직선으로 근사.
                # (정밀 변환이 필요하면 폰트를 CFF(OTF)로 쓰는 것이 원칙.)
                X, Y = tx(*p2)
                parts.append(f"{fmt(X)} {fmt(Y)} l")
            else:
                for p in pts:
                    X, Y = tx(*p)
                    parts.append(f"{fmt(X)} {fmt(Y)} l")
        elif cmd == "closePath":
            parts.append("h")
        # endPath(닫지 않는 경로)는 폰트 윤곽엔 거의 없으므로 무시.
    return "\n".join(parts)


def _text_metrics(text: str, glyphset, cmap, upm: int):
    """글자열의 advance(가로 진행폭) 목록과 폰트에 없는 글자 목록을 구한다.

    반환: (entries, missing)
      entries : [(글리프이름, advance_폰트단위), ...]  실제 그릴 글자만(공백 포함).
      missing : 폰트에 없는 문자 리스트(예: 이모지·한자).
    """
    entries: List[Tuple[str, float]] = []
    missing: List[str] = []
    for ch in text:
        gname = cmap.get(ord(ch))
        if gname is None:
            missing.append(ch)
            continue
        adv = glyphset[gname].width        # advance(다음 글자까지 진행폭, 폰트단위)
        entries.append((gname, adv))
    return entries, missing


def render_text_ops(
    text: str,
    font_path: str,
    bbox_pt: Tuple[float, float, float, float],
    color_cmyk,
    align: str = "center",
):
    """글자를 bbox_pt(시트 절대좌표) 칸 안에 맞춰 PDF 연산자 문자열로 반환한다.

    text       : 그릴 글자("7", "김민수"). 빈값/None 이면 아무것도 안 그림.
    font_path  : otf/ttf 절대경로(없으면 친절 에러).
    bbox_pt    : (x0,y0,x1,y1) 글자가 들어갈 칸. 좌하단(x0,y0)~우상단(x1,y1), y는 위로 증가.
    color_cmyk : (c,m,y,k). 0~1 또는 0~100 모두 허용.
    align      : "left"|"center"|"right" 가로정렬. 세로는 항상 칸 중앙(em중앙 근사).

    반환: (ops_str, warnings)
      ops_str  : "q  c m y k k  <경로 m/l/c h> f  Q" 형태 PDF 연산자(ascii). 없으면 "".
      warnings : 비개발자용 한국어 경고 문자열 목록(글리프 누락·칸 오류 등).

    설계 R-A: 좌표는 좌하단 기준 y위로(방식A와 동일). R-B: 세로는 em중앙 근사.
    R-C: stroke 없이 fill(`f`)만. R-F: 글리프 누락 시 텍스트 통째 생략+경고.
    """
    warnings: List[str] = []

    # ── 빈 텍스트: 그릴 것 없음(정상 흐름). 글자 미지정 시 출력 불변 보장. ──
    if text is None or str(text).strip() == "":
        return "", warnings
    text = str(text)

    # ── 칸 크기 검증(0/역전 방지 — preset 오타 대비) ──
    x0, y0, x1, y1 = (float(bbox_pt[0]), float(bbox_pt[1]),
                      float(bbox_pt[2]), float(bbox_pt[3]))
    bw, bh = (x1 - x0), (y1 - y0)
    if bw <= 0 or bh <= 0:
        warnings.append(
            f"🟡 글자 '{text}' 를 그릴 칸 크기가 잘못됐습니다(가로 {bw:.1f} 세로 {bh:.1f}). 건너뜁니다.")
        return "", warnings

    # ── align 오타 방어 ──
    if align not in ("left", "center", "right"):
        warnings.append(f"🟡 정렬값 '{align}' 을 몰라 가운데(center)로 그립니다.")
        align = "center"

    # ── 폰트 로드 + 글자 측정 ──
    glyphset, cmap, upm = _load_glyphset(font_path)
    entries, missing = _text_metrics(text, glyphset, cmap, upm)

    # ── R-F: 폰트에 없는 글자가 하나라도 있으면 텍스트 전체 미출력(이름 깨짐 방지) ──
    if missing:
        miss_str = "".join(missing)
        warnings.append(
            f"🟡 '{text}' 중 '{miss_str}' 글자가 폰트에 없어 전체를 그리지 않습니다(입력값 확인 필요).")
        return "", warnings

    if not entries:                        # 측정 결과가 비면(이론상 위에서 걸러짐) 안전 종료
        return "", warnings

    # ── 글자열 자연 크기(em 기준): 폭=Σadvance/upm, 높이=1.0em(보수적 근사) ──
    total_adv = sum(adv for _, adv in entries)     # 폰트단위 폭 합
    width_em = total_adv / upm if upm else 0.0     # em(1em=글자 한 칸 높이) 단위 폭
    height_em = 1.0                                 # 높이는 1em 으로 본다(설계 R-B 근사)
    if width_em <= 0:
        warnings.append(f"🟡 글자 '{text}' 의 폭을 계산하지 못해 건너뜁니다.")
        return "", warnings

    # ── contain 스케일: 칸 밖으로 안 나가게 가로/세로 배율 중 작은 쪽 ──
    scale_by_w = bw / width_em
    scale_by_h = bh / height_em
    scale = min(scale_by_w, scale_by_h)            # em → pt 환산 + 칸 맞춤을 한 번에

    text_w_pt = width_em * scale                   # 실제 글자열 가로 크기(pt)
    text_h_pt = height_em * scale                  # 실제 글자열 세로 크기(pt)

    # ── 가로 정렬: 남는 가로공간을 정렬값대로 배분 ──
    gap_x = bw - text_w_pt
    if align == "left":
        start_x = x0
    elif align == "right":
        start_x = x0 + gap_x
    else:                                          # center
        start_x = x0 + gap_x / 2.0

    # ── 세로 중앙(em중앙 근사): baseline 을 칸 중앙에 오게 둔다 ──
    #    글리프 윤곽의 y=0 이 baseline. 글자 높이를 1em 으로 보고 중앙 배치.
    gap_y = bh - text_h_pt
    baseline_y = y0 + gap_y / 2.0                  # 칸 아래에서 (남는높이/2) 만큼 올린 곳이 baseline

    # ── 폰트단위 → pt 배율(글리프 좌표에 곱할 값) ──
    u = scale / upm if upm else 0.0

    # ── 글자를 하나씩 오른쪽으로 advance 만큼 전진시키며 경로 누적 ──
    pen_x = start_x                                # 현재 글자의 가로 시작점(시트 절대좌표)
    glyph_blocks: List[str] = []
    for gname, adv in entries:
        # 글리프 윤곽 좌표는 '폰트단위'(0~upm)이므로 폰트단위→pt 배율 u 를 곱한다.
        # (scale 은 em→pt 배율이라 글리프 좌표에 직접 곱하면 upm 배 커진다 — u 를 써야 함.)
        ops = _glyph_path_ops(glyphset, gname, u, pen_x, baseline_y)
        if ops:                                    # 공백 글리프는 윤곽이 없어 ops 가 빈 문자열
            glyph_blocks.append(ops)
        pen_x += adv * u                           # 다음 글자 위치로 진행(폰트 advance를 pt로)

    if not glyph_blocks:                           # 그릴 윤곽이 없으면(전부 공백 등) 미출력
        return "", warnings

    # ── 색: CMYK fill(소문자 k). 모든 글리프를 한 번에 non-zero winding fill ──
    c, m, y, k = _normalize_cmyk(color_cmyk)
    color_op = f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k"   # fill 색 설정(예: 0 0 0 0 k = 흰색)

    # ── 최종 조립: q(상태저장) → 색 → 모든 글자경로 → f(채우기) → Q(상태복원) ──
    #    q…Q 로 감싸 색/CTM 누수 방지. 'f'(non-zero) 라 글자 구멍(0,8,이 안쪽)도 자동 처리.
    body = "\n".join(glyph_blocks)
    ops_str = f"q\n{color_op}\n{body}\nf\nQ"
    return ops_str, warnings


# ════════════════════════════════════════════════════════════════════════════
# Phase B — 정밀 배치 함수 (의뢰서 §4 공식 그대로 구현)
#
#   기존 render_text_ops 는 'bbox 안에 contain' 방식이라 미세하게 부정확하다.
#   완성본(정답지)에서 실측한 "높이·중심·자간" 수치를 그대로 재현하려면, 칸이 아니라
#   숫자=잉크높이 기준 scale, 이름=em 기준 scale + 음절 피치 로 배치해야 한다.
#   → 아래 place_number / place_name 이 그 정밀 배치기다. (수치는 전부 인자, 하드코딩 없음)
# ════════════════════════════════════════════════════════════════════════════


def _glyph_ink_bounds(glyphset, glyph_name: str):
    """글리프 1개의 '잉크 경계'(xMin,yMin,xMax,yMax, 폰트단위)를 구한다.

    왜 필요한가: 번호의 '자릿수 높이'(목표값 cap_h)는 글자 칸(em)이 아니라 숫자가
    실제로 차지하는 세로 잉크 높이(yMax-yMin)다. 완성본 실측이 잉크 높이라 여기에 맞춘다.

    합성 글리프(한글 음절 등)도 정확히 재기 위해 DecomposingRecordingPen 으로 윤곽을
    먼저 편 뒤 ControlBoundsPen 으로 경계를 잰다. 윤곽이 없는 글리프(공백)는 None.
    반환: (xMin, yMin, xMax, yMax) | None
    """
    # 1) 합성 글리프 분해(컴포넌트를 실제 윤곽으로) → 경계 측정.
    dpen = DecomposingRecordingPen(glyphset)
    glyphset[glyph_name].draw(dpen)
    bpen = ControlBoundsPen(glyphset)
    dpen.replay(bpen)
    if bpen.bounds is None:                 # 공백 등 윤곽 없는 글리프
        return None
    return bpen.bounds                       # (xMin, yMin, xMax, yMax) 폰트단위


def place_number(text, font, cap_h_pt: float, center_x: float, center_y: float, color,
                 glyph_source=None):
    """번호('7','20' 등)를 '자릿수 높이=cap_h_pt' 로 (center_x, center_y) 잉크중심에 배치.

    ── 이슈1(번호 글리프셋) 분기 ──
      glyph_source 가 주어지면(디자이너가 .ai 에 직접 그린 번호 글리프셋 dict),
      폰트 대신 그 글리프셋으로 번호를 그린다. 잉크중심 정렬(이슈2)은 동일하게 적용된다.
      glyph_source 가 None(기본값)이면 기존처럼 font(HY헤드라인M) 아웃라인으로 폴백한다.
      → 글리프셋이 없거나 깨지면 무조건 폰트 폴백이 보장된다(출고 안전).

    의뢰서 §4 + 이슈2(잉크 기준 중앙정렬):
      · 대표 자릿 글리프의 잉크 높이 inkH(폰트단위)로 scale s = cap_h_pt / inkH.
      · 자릿들을 자연 advance×s 로 좌→우 '임시배치'한 뒤, 배치된 전체 글리프의 실제
        잉크 bbox(min/max x·y)를 재서 그 한가운데를 (center_x, center_y) 에 평행이동한다.
      · 왜 advance 기준이 아니라 잉크 기준인가: "1"처럼 advance 박스 안에서 잉크가 한쪽으로
        치우친 글자는 advance 중앙정렬 시 보이는 획이 ~27pt 밀린다(이슈2). 잉크 기준이면
        "1","11","20","22" 모두 보이는 잉크 중심이 center_x 에 정확히 온다.

    인자:
      text       : 번호 문자열("7","20"). 빈값/None 이면 아무것도 안 그림.
      font       : 폰트 절대경로(.ttf/.otf). 없으면 친절 에러.
      cap_h_pt   : 목표 자릿수(잉크) 높이(pt). 예: 앞 310, 뒤 539.
      center_x   : 번호 가로 중심(시트 절대좌표 pt).
      center_y   : 번호 잉크 세로 중심(시트 절대좌표 pt).
      color      : CMYK (c,m,y,k). 0~1 또는 0~100 모두 허용.
    반환: (ops_str, warnings) — render_text_ops 와 동일 규약(ascii ops, k fill, q…Q).
    """
    warnings: List[str] = []

    # ── 빈 텍스트: 그릴 것 없음(정상). 번호 미지정 시 출력 불변 보장. ──
    if text is None or str(text).strip() == "":
        return "", warnings
    text = str(text).strip()

    # ── 목표 높이 검증(0/음수 방지 — preset 오타 대비) ──
    if cap_h_pt <= 0:
        warnings.append(f"🟡 번호 '{text}' 의 높이값이 잘못됐습니다(cap_height {cap_h_pt}). 건너뜁니다.")
        return "", warnings

    # ── 이슈1: 글리프셋이 주어지면 디자이너 번호 도형으로 그린다(폰트 대신). ──
    #    폰트 로드보다 먼저 분기한다. glyph_source 가 None 이면 그대로 아래 폰트 폴백으로 진행.
    #    (모듈 지연 import: 글리프셋을 안 쓰는 경로/환경에 영향 주지 않기 위함.)
    if glyph_source is not None:
        from .number_glyphs import render_glyph_number_ops
        return render_glyph_number_ops(
            glyph_source, text, cap_h_pt=cap_h_pt,
            center_x=center_x, center_y=center_y, color=color)

    # ── 폰트 로드 + 글자 측정(advance, 누락 글리프) ──
    glyphset, cmap, upm = _load_glyphset(font)
    entries, missing = _text_metrics(text, glyphset, cmap, upm)

    # ── R-F: 폰트에 없는 글자가 있으면 통째 미출력(번호 깨짐 방지) ──
    if missing:
        miss_str = "".join(missing)
        warnings.append(
            f"🟡 번호 '{text}' 중 '{miss_str}' 글자가 폰트에 없어 전체를 그리지 않습니다(입력값 확인).")
        return "", warnings
    if not entries:
        return "", warnings

    # ── 대표 자릿 글리프의 잉크 높이로 scale 결정 ──
    #    '대표'는 가장 키 큰 자릿(보통 잉크높이 최대)으로 잡아, 모든 자리를 같은 s 로 배치한다.
    #    (각 자리 높이가 미세히 달라도 한 줄 번호는 동일 배율이어야 자연스럽다.)
    ink_list = []
    for gname, _ in entries:
        b = _glyph_ink_bounds(glyphset, gname)
        if b is not None:
            ink_list.append(b)
    if not ink_list:                         # 전부 공백 등 — 그릴 잉크 없음
        warnings.append(f"🟡 번호 '{text}' 에 그릴 윤곽이 없어 건너뜁니다.")
        return "", warnings

    # 대표 잉크 높이 = 후보 중 최대(가장 큰 자릿). 이 높이를 cap_h_pt 에 맞춘다.
    rep = max(ink_list, key=lambda bb: bb[3] - bb[1])
    ink_h = rep[3] - rep[1]                   # yMax - yMin (폰트단위)
    if ink_h <= 0:
        warnings.append(f"🟡 번호 '{text}' 의 잉크 높이를 계산하지 못해 건너뜁니다.")
        return "", warnings
    s = cap_h_pt / ink_h                      # 폰트단위 → pt 배율(이 번호 전용)

    # ── 1차 임시배치: 자릿들을 advance×s 로 좌→우 이어붙인다(가로 시작점 0 기준 상대배치) ──
    #    왜 임시배치부터 하나: "1"처럼 잉크가 advance 박스 안에서 한쪽으로 치우친 글자가 있어,
    #    advance 기준으로 곧장 중앙정렬하면 보이는 잉크가 밀린다(이슈2). 그래서 일단 배치만 해
    #    놓고, 아래에서 '실제 잉크 bbox'를 재서 그 중심을 center_x/center_y 에 맞춰 평행이동한다.
    #    seg = (글리프이름, 이 글자의 가로 시작점 dx0)  ← dx0 는 아직 center 보정 전 상대좌표.
    segs: List[Tuple[str, float]] = []
    pen_x = 0.0
    for gname, adv in entries:
        segs.append((gname, pen_x))
        pen_x += adv * s                      # 다음 글자 위치로 advance 만큼 전진(pt)

    # ── 배치된 전체 글리프의 '실제 잉크 bbox'(시트좌표계) 측정 ──
    #    각 글리프의 잉크 경계(폰트단위) b=(xMin,yMin,xMax,yMax) 를 배치 좌표계로 변환:
    #      시트x = 폰트x*s + dx0,  시트y = 폰트y*s + (baseline 0 가정).
    #    세로는 baseline 을 일단 0 으로 두고 잰 뒤(아래서 shift_y 로 한 번에 올림).
    ink_min_x = ink_min_y = float("inf")
    ink_max_x = ink_max_y = float("-inf")
    for gname, dx0 in segs:
        b = _glyph_ink_bounds(glyphset, gname)   # (xMin,yMin,xMax,yMax) 폰트단위 | None(공백)
        if b is None:
            continue
        # 폰트단위 경계 → 배치 좌표계(pt)로 환산. dx0 는 글자별 가로 시작점.
        gx0 = b[0] * s + dx0
        gx1 = b[2] * s + dx0
        gy0 = b[1] * s                          # baseline=0 가정 좌표
        gy1 = b[3] * s
        ink_min_x = min(ink_min_x, gx0)
        ink_max_x = max(ink_max_x, gx1)
        ink_min_y = min(ink_min_y, gy0)
        ink_max_y = max(ink_max_y, gy1)

    if ink_min_x == float("inf"):              # 측정된 잉크가 없으면(전부 공백) 종료
        warnings.append(f"🟡 번호 '{text}' 에 그릴 잉크가 없어 건너뜁니다.")
        return "", warnings

    # ── 잉크 중심을 center_x / center_y 에 맞추는 평행이동량 계산 ──
    #    가로: 보이는 잉크의 한가운데가 center_x 에 오도록 shift_x.
    #    세로: baseline=0 으로 잰 잉크 세로중심이 center_y 에 오도록 baseline_y(=shift_y) 결정.
    shift_x = center_x - (ink_min_x + ink_max_x) / 2.0
    baseline_y = center_y - (ink_min_y + ink_max_y) / 2.0

    # ── 자릿별 경로 누적(상대 dx0 + shift_x = 최종 시트 x, baseline_y = 최종 시트 y) ──
    glyph_blocks: List[str] = []
    for gname, dx0 in segs:
        ops = _glyph_path_ops(glyphset, gname, s, dx0 + shift_x, baseline_y)  # s=폰트단위→pt
        if ops:                               # 공백은 윤곽 없어 빈 문자열
            glyph_blocks.append(ops)
    if not glyph_blocks:
        return "", warnings

    # ── 색(CMYK k fill) + q…Q 래핑(기존 규약과 동일) ──
    c, m, y, k = _normalize_cmyk(color)
    color_op = f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k"
    body = "\n".join(glyph_blocks)
    ops_str = f"q\n{color_op}\n{body}\nf\nQ"
    return ops_str, warnings


def place_name(text, font, em_pt: float, pitch_pt: float, baseline_y: float,
               center_x: float, color):
    """이름('김경원' 등)을 em_pt 크기로, 음절 피치 pitch_pt 간격, baseline 고정,
    center_x 가운데정렬로 배치.

    의뢰서 §4 공식:
      · scale = em_pt / upm  (em_pt=136.40, upm=1024 → 글자 한 칸이 em_pt pt).
      · 음절을 pitch_pt 간격으로 baseline_y 에 고정, 전체를 center_x 가운데정렬.
      · 원본은 음절 사이 공백+Tc(자간)로 간격을 줬으므로, 여기서는 '음절당 피치 한 칸'으로
        재현한다. 입력에 공백이 섞여 있어도 공백 자체는 피치 한 칸을 차지하는 것으로 본다.

    인자:
      text       : 이름 문자열("김경원"). 빈값/None 이면 아무것도 안 그림.
      font       : 폰트 절대경로. 없으면 친절 에러.
      em_pt      : 글자 1em 크기(pt). 예: 136.40.
      pitch_pt   : 음절 중심 간 간격(pt). 예: 195.4.
      baseline_y : 글자 baseline 의 시트 절대 y(pt). 예: 4765.7.
      center_x   : 이름 전체 가로 중심(시트 절대좌표 pt). 예: 3219.8.
      color      : CMYK (c,m,y,k). 0~1 또는 0~100 모두 허용.
    반환: (ops_str, warnings).
    """
    warnings: List[str] = []

    # ── 빈 텍스트: 그릴 것 없음(정상). ──
    if text is None or str(text).strip() == "":
        return "", warnings
    text = str(text)

    # ── 값 검증(em/pitch 0·음수 방지) ──
    if em_pt <= 0:
        warnings.append(f"🟡 이름 '{text}' 의 글자 크기값이 잘못됐습니다(em_pt {em_pt}). 건너뜁니다.")
        return "", warnings
    if pitch_pt <= 0:
        warnings.append(f"🟡 이름 '{text}' 의 음절 간격값이 잘못됐습니다(pitch {pitch_pt}). 건너뜁니다.")
        return "", warnings

    glyphset, cmap, upm = _load_glyphset(font)
    if not upm:
        warnings.append(f"🟡 이름 '{text}' 의 폰트 upm 을 읽지 못해 건너뜁니다.")
        return "", warnings

    # ── '음절 단위'로 자른다(공백 포함, 글자 하나=한 음절=피치 한 칸) ──
    #    피치는 advance 가 아니라 '고정 간격'이라, 음절 폭이 달라도 중심 간격이 일정하다.
    syllables = list(text)                   # 한글 음절/숫자/공백 각각 한 칸
    n = len(syllables)

    # ── 전체 폭 = (음절수-1)×pitch (중심~중심 거리 합). 1글자면 폭 0(중심에 그대로). ──
    total_span = (n - 1) * pitch_pt
    # 첫 음절의 '중심 x' = center_x - total_span/2, 이후 음절마다 +pitch.
    first_center_x = center_x - total_span / 2.0

    # ── em → pt 배율(글리프 좌표=폰트단위에 곱할 값) ──
    s = em_pt / upm

    # ── 1차 임시배치: 음절을 피치 간격으로 좌→우 배치(아직 잉크 보정 전 상대 dx) ──
    #    각 음절을 '자기 advance 폭의 가운데'가 피치칸 중심에 오게 둔다(기존 방식 유지).
    #    아래에서 배치된 전체 잉크 bbox 를 재서 가로 잉크중심을 center_x 에 맞춰 평행이동한다.
    #    seg = (글리프이름, 이 글자의 가로 시작점 dx)
    segs: List[Tuple[str, float]] = []
    missing: List[str] = []
    for i, ch in enumerate(syllables):
        if ch.strip() == "":                 # 공백 음절: 피치 한 칸만 차지(그릴 윤곽 없음)
            continue
        gname = cmap.get(ord(ch))
        if gname is None:                    # 폰트에 없는 글자 수집(아래서 통째 처리)
            missing.append(ch)
            continue
        # 이 음절의 중심 x(피치 기준).
        syl_center_x = first_center_x + i * pitch_pt
        # 글리프를 '자기 advance 폭의 가운데'가 syl_center_x 에 오게 좌측 시작점 보정.
        adv = glyphset[gname].width
        dx = syl_center_x - (adv * s) / 2.0
        segs.append((gname, dx))

    # ── R-F: 폰트에 없는 글자가 있으면 통째 미출력(이름 깨짐 방지) ──
    if missing:
        miss_str = "".join(missing)
        warnings.append(
            f"🟡 이름 '{text}' 중 '{miss_str}' 글자가 폰트에 없어 전체를 그리지 않습니다(입력값 확인).")
        return "", warnings
    if not segs:                              # 전부 공백 등 — 그릴 윤곽 없음
        return "", warnings

    # ── 배치된 전체 글리프의 '실제 잉크 가로 bbox' 측정 → 가로 잉크중심을 center_x 에 평행이동 ──
    #    이름도 번호(이슈2)와 같은 잉크 기준으로 통일한다(2글자 이름 등 미세 치우침 예방).
    #    세로는 baseline_y 고정(의뢰서 §4: baseline 고정) — 가로만 잉크 기준 보정.
    ink_min_x = float("inf")
    ink_max_x = float("-inf")
    for gname, dx in segs:
        b = _glyph_ink_bounds(glyphset, gname)   # (xMin,yMin,xMax,yMax) 폰트단위 | None(공백)
        if b is None:
            continue
        ink_min_x = min(ink_min_x, b[0] * s + dx)   # 폰트단위→pt 환산 + 글자 시작점
        ink_max_x = max(ink_max_x, b[2] * s + dx)
    # 측정된 잉크가 있으면 가로 잉크중심을 center_x 로 맞춘다(없으면 보정 0).
    shift_x = 0.0 if ink_min_x == float("inf") else center_x - (ink_min_x + ink_max_x) / 2.0

    # ── 최종 경로 누적(dx + shift_x = 최종 시트 x, baseline_y 고정) ──
    glyph_blocks: List[str] = []
    for gname, dx in segs:
        ops = _glyph_path_ops(glyphset, gname, s, dx + shift_x, baseline_y)  # baseline 고정
        if ops:
            glyph_blocks.append(ops)
    if not glyph_blocks:                      # 전부 공백 등 — 그릴 윤곽 없음
        return "", warnings

    # ── 색(CMYK k fill) + q…Q 래핑 ──
    c, m, y, k = _normalize_cmyk(color)
    color_op = f"{fmt(c)} {fmt(m)} {fmt(y)} {fmt(k)} k"
    body = "\n".join(glyph_blocks)
    ops_str = f"q\n{color_op}\n{body}\nf\nQ"
    return ops_str, warnings
