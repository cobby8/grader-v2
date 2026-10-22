# -*- coding: utf-8 -*-
"""design_color — 주문서 «디자인(컬러 이름)» 으로 한 대지의 여러 벌 중 그 선수가 입을 벌을 고른다 (2026-10-22).

배경(김현서 답): 홈·원정이 따로인 유니폼은 «주문서대로» 찍는다. 관리자 주문서는 선수마다 «디자인» 칸에
컬러 이름(블루·옐로우 …)을 적고, 범례에 그 색 코드(#02218D)를 둔다. 옛 주문서는 비고 칸에 홈·어웨이·컬러를 적었다.
→ 벌마다 바탕색(본체색, CMYK)을 재 두었으니, 디자인 색과 가장 가까운 벌 하나만 찍는다.

안 고르는 경우(모든 벌을 그대로 찍는다):
  · 주문의 디자인이 한 가지뿐 — 양면 유니폼은 앞·뒷면이 디자인 하나다(쇼핑몰 isReversibleOrder)
  · «홈/어웨이» 처럼 색이 없는 이름, 컬러가 둘 이상 든 이름(«화이트/네이비»), 가까운 벌이 뚜렷하지 않을 때
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

RGB = Tuple[int, int, int]

# 색 이름표 — 쇼핑몰 디자인 이름·디자이너가 비고에 적는 말. 긴 말부터 찾는다(«스카이블루» 가 «블루» 보다 먼저).
_NAMES: Dict[str, RGB] = {
    "스카이블루": (110, 180, 230), "하늘": (110, 180, 230), "스카이": (110, 180, 230), "SKY": (110, 180, 230),
    "네이비": (20, 30, 80), "남색": (20, 30, 80), "곤색": (20, 30, 80), "NAVY": (20, 30, 80),
    "블루": (20, 50, 170), "파랑": (20, 50, 170), "파란": (20, 50, 170), "BLUE": (20, 50, 170),
    "화이트": (250, 250, 250), "흰색": (250, 250, 250), "하양": (250, 250, 250), "백색": (250, 250, 250), "WHITE": (250, 250, 250),
    "블랙": (20, 20, 20), "검정": (20, 20, 20), "검은": (20, 20, 20), "BLACK": (20, 20, 20),
    "레드": (210, 30, 40), "빨강": (210, 30, 40), "빨간": (210, 30, 40), "RED": (210, 30, 40),
    "옐로우": (248, 226, 2), "옐로": (248, 226, 2), "노랑": (248, 226, 2), "노란": (248, 226, 2), "YELLOW": (248, 226, 2),
    "그린": (20, 130, 60), "초록": (20, 130, 60), "녹색": (20, 130, 60), "GREEN": (20, 130, 60),
    "민트": (120, 210, 190), "MINT": (120, 210, 190),
    "퍼플": (110, 40, 140), "보라": (110, 40, 140), "PURPLE": (110, 40, 140),
    "오렌지": (240, 120, 20), "주황": (240, 120, 20), "ORANGE": (240, 120, 20),
    "핑크": (240, 130, 170), "분홍": (240, 130, 170), "PINK": (240, 130, 170),
    "그레이": (128, 128, 128), "회색": (128, 128, 128), "GRAY": (128, 128, 128), "GREY": (128, 128, 128),
    "버건디": (110, 20, 40), "와인": (110, 20, 40), "자주": (110, 20, 40), "마룬": (110, 20, 40), "MAROON": (110, 20, 40),
    "골드": (200, 160, 40), "금색": (200, 160, 40), "GOLD": (200, 160, 40),
    "실버": (180, 180, 185), "은색": (180, 180, 185), "SILVER": (180, 180, 185),
    "베이지": (220, 200, 160), "BEIGE": (220, 200, 160),
    "브라운": (110, 70, 40), "갈색": (110, 70, 40), "BROWN": (110, 70, 40),
    "카키": (120, 120, 70), "KHAKI": (120, 120, 70),
}
_ORDER = sorted(_NAMES, key=len, reverse=True)


def color_words(text: str) -> List[str]:
    """글자 안의 색 이름(겹치지 않게, 앞에서부터). «스카이블루» 는 한 개."""
    t = (text or "").upper()
    found: List[str] = []
    used = [False] * len(t)
    for w in _ORDER:
        start = 0
        while True:
            i = t.find(w, start)
            if i < 0:
                break
            if not any(used[i:i + len(w)]):
                found.append(w)
                for k in range(i, i + len(w)):
                    used[k] = True
            start = i + 1
    return found


def hex_rgb(hex_text: str) -> Optional[RGB]:
    h = (hex_text or "").strip().lstrip("#")
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def cmyk_rgb(cmyk: Sequence[float]) -> RGB:
    c, m, y, k = [max(0.0, min(1.0, float(v))) for v in cmyk]
    return (round(255 * (1 - c) * (1 - k)), round(255 * (1 - m) * (1 - k)), round(255 * (1 - y) * (1 - k)))


def design_rgb(design: str, design_hex: str = "") -> Optional[RGB]:
    """디자인의 색. 범례 색 코드가 먼저, 없으면 이름 속 색 이름(정확히 하나일 때만)."""
    rgb = hex_rgb(design_hex)
    if rgb:
        return rgb
    words = color_words(design)
    if len(set(_NAMES[w] for w in words)) == 1:
        return _NAMES[words[0]]
    return None


def _dist(a: RGB, b: RGB) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def pick_sides(rows: Sequence[dict], side_cmyk: Sequence[Optional[Sequence[float]]],
               reversible: bool = False) -> Tuple[Dict[int, int], List[str]]:
    """행 번호 → 찍을 벌(0=첫 벌). 고르지 않는 행은 빠진다(모든 벌). 반환: (고른 것, 안내 문구들)."""
    notes: List[str] = []
    designs = {}
    for i, r in enumerate(rows):
        d = str(r.get("design") or "").strip()
        if d:
            designs.setdefault(d, []).append(i)
    if len(side_cmyk) < 2 or not designs:
        return {}, notes
    if reversible:
        return {}, ["[디자인] 양면 패턴이라 주문서 디자인과 상관없이 두 면을 모두 찍습니다."]
    if len(designs) < 2:
        return {}, notes                      # 디자인이 하나뿐 — 고를 일이 없다(양면 앞·뒷면 등)
    if any(c is None for c in side_cmyk):
        return {}, ["🟡 [디자인] 벌마다 바탕색을 재지 못해 주문서 디자인으로 벌을 고르지 않고 모두 찍습니다."]
    sides = [cmyk_rgb(c) for c in side_cmyk]
    got: Dict[int, int] = {}
    done, miss = [], []
    for d, idxs in designs.items():
        hx = next((str(rows[i].get("design_hex") or "") for i in idxs if rows[i].get("design_hex")), "")
        rgb = design_rgb(d, hx)
        if rgb is None:
            miss.append(d)
            continue
        ds = sorted((_dist(rgb, s), k) for k, s in enumerate(sides))
        best, k = ds[0]
        if best > 160 or (len(ds) > 1 and ds[1][0] - best < 40):
            miss.append(d)
            continue
        for i in idxs:
            got[i] = k
        done.append(f"{d} {len(idxs)}명 → {k + 1}면")
    if done:
        notes.append("[디자인] 주문서 디자인(컬러)대로 그 벌만 찍습니다: " + " · ".join(done))
    if miss:
        notes.append(f"🟡 [디자인] «{', '.join(miss)}» 은 대지의 어느 벌인지 색으로 가리지 못해 모든 벌을 찍습니다 — 결과를 확인해 주세요.")
    return got, notes
