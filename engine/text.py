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

from fontTools.pens.recordingPen import RecordingPen
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
    pen = RecordingPen()
    glyphset[glyph_name].draw(pen)         # 글리프 윤곽을 펜 명령 리스트로 기록

    # 폰트좌표 1점을 시트좌표 pt 로 옮기는 작은 도우미.
    tx = lambda x, y: (x * scale + dx, y * scale + dy)

    parts: List[str] = []
    for cmd, pts in pen.value:
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
