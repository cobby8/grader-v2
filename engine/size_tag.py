# -*- coding: utf-8 -*-
"""사이즈 택 바꾸기 — 디자인 속 기준 사이즈 택을 찾아, 출력 사이즈의 택을 그 자리에 덮어 찍는다(2026-10-20).

왜: 그레이더는 기준 사이즈 디자인을 키우고 줄이기만 해서 L 출력에도 «XL» 택이 찍혔다(최근 주문 5건 전부).
    디자이너는 사이즈마다 그 사이즈 택으로 바꾼다.

어떻게:
  1) 택 라이브러리(data/size_tags, scripts/build_size_tags.py 가 «택작업 무기고.ai» 에서 만든 벡터 PDF)
  2) find_tags: 디자인을 1px/mm 로 그려 계열(농구·페가수스·축구)별 «기준 사이즈 택»을 그림 맞추기로 찾는다
     (크기 0.8~1.25배까지). 맞춤 점수가 낮으면 아무것도 안 한다 — 엉뚱한 곳에 택을 찍지 않는다.
  3) 출력 때 그 조각에 «출력 사이즈 택»을 Form 으로 덮어 찍는다(compose 의 Piece.overlays).
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.environ.get("GRADER_SIZE_TAG_DIR") or os.path.join(ROOT, "data", "size_tags")
MM = 25.4 / 72


def load_library(lib_dir: str = LIB_DIR) -> Dict[str, Dict[str, dict]]:
    p = os.path.join(lib_dir, "index.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        fams = json.load(f).get("families", {})
    for fam in fams.values():
        for meta in fam.values():
            meta["path"] = os.path.join(lib_dir, meta["file"])
    return fams


def _gray(page, zoom, clip=None):
    import numpy as np
    import fitz
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()


def _refine(page, tdoc, cand_rect_pt, H, zoom_fine, scale0):
    """후보 자리 둘레를 3px/mm 로 다시 그려, 택 «안쪽»(테두리 빼고)만으로 맞춰 본다.

    짙은 바탕(양면 자주 면)에선 택 바깥 검정 테두리가 바탕에 묻혀 1차 점수가 0.7 대로 떨어지고,
    엉뚱한 곳(다른 계열 택 본)도 0.65 까지 나와 가르기 어려웠다 → 안쪽 무늬(글자·로고)로 확인한다.
    반환: (점수, [x0,y0,x1,y1] pt) 또는 None
    """
    import cv2
    import numpy as np
    import fitz
    x0, y0, x1, y1 = cand_rect_pt
    w, h = x1 - x0, y1 - y0
    clip = fitz.Rect(x0 - 0.25 * w, H - y1 - 0.25 * h, x1 + 0.25 * w, H - y0 + 0.25 * h) & page.rect
    img = _gray(page, zoom_fine, clip).astype(np.float32)
    best = None
    for k in [scale0 + 0.02 * i for i in range(-4, 5)]:
        tpl = _gray(tdoc[0], zoom_fine * k).astype(np.float32)
        th, tw = tpl.shape
        iy, ix = int(th * 0.15), int(tw * 0.08)
        inner = tpl[iy:th - iy, ix:tw - ix]
        if inner.shape[0] >= img.shape[0] or inner.shape[1] >= img.shape[1] or inner.size < 64:
            continue
        res = np.nan_to_num(cv2.matchTemplate(img, inner, cv2.TM_CCOEFF_NORMED), nan=0.0, posinf=0.0, neginf=0.0)
        _, mv, _, ml = cv2.minMaxLoc(res)
        if best is None or mv > best[0]:
            px0 = clip.x0 + (ml[0] - ix) / zoom_fine
            py0 = clip.y0 + (ml[1] - iy) / zoom_fine
            best = (float(mv), [px0, H - (py0 + th / zoom_fine), px0 + tw / zoom_fine, H - py0], k)
    return best


def find_tags(design_pdf: str, base_size: str, lib: Optional[dict] = None, *,
              px_per_mm: float = 1.0, threshold: float = 0.6, confirm: float = 0.8,
              max_hits: int = 6) -> List[dict]:
    """디자인에서 기준 사이즈 택 자리를 찾는다.

    반환: [{family, size, rect_pt:[x0,y0,x1,y1](디자인 PDF 좌표, y 위로), score, scale}]
      · 계열마다 base_size 택(없으면 «기본» 택)을 본으로 쓴다.
      · cv2 가 없거나 라이브러리가 없으면 빈 목록(예전 동작 그대로).
    """
    try:
        import cv2
        import numpy as np
        import fitz
    except Exception:
        return []
    lib = lib if lib is not None else load_library()
    if not lib:
        return []
    doc = fitz.open(design_pdf)
    page = doc[0]
    H = page.rect.height
    zoom = px_per_mm * MM
    img = _gray(page, zoom).astype(np.float32)
    hits: List[dict] = []
    for fam, sizes in lib.items():
        meta = sizes.get(base_size) or sizes.get("기본")
        if not meta:
            continue
        tdoc = fitz.open(meta["path"])
        best = None
        for k in [0.8 + 0.05 * i for i in range(10)]:
            tpl = _gray(tdoc[0], zoom * k).astype(np.float32)
            if tpl.shape[0] < 8 or tpl.shape[1] < 8 or tpl.shape[0] >= img.shape[0] or tpl.shape[1] >= img.shape[1]:
                continue
            res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
            work = res.copy()
            for _ in range(max_hits):
                _, mv, _, ml = cv2.minMaxLoc(work)
                if mv < threshold:
                    break
                x, y = ml
                h, w = tpl.shape
                cand = {"family": fam, "size": base_size if base_size in sizes else "기본",
                        "score": float(mv), "scale": k, "px": (x, y, x + w, y + h)}
                hits.append(cand)
                work[max(0, y - h // 2):y + h // 2 + 1, max(0, x - w // 2):x + w // 2 + 1] = -1
        tdoc.close()
    # 겹치는 후보는 점수 높은 것 하나만
    hits.sort(key=lambda d: -d["score"])
    kept: List[dict] = []
    for h in hits:
        x0, y0, x1, y1 = h["px"]
        if any(min(x1, q["px"][2]) - max(x0, q["px"][0]) > 0.3 * (x1 - x0) and
               min(y1, q["px"][3]) - max(y0, q["px"][1]) > 0.3 * (y1 - y0) for q in kept):
            continue
        kept.append(h)
    out = []
    for h in kept[:max_hits * 2]:
        x0, y0, x1, y1 = h["px"]
        # px(위 원점) → pt(디자인 PDF, y 위로)
        rect = [x0 / zoom, H - y1 / zoom, x1 / zoom, H - y0 / zoom]
        meta = lib[h["family"]].get(h["size"])
        tdoc = fitz.open(meta["path"])
        ref = _refine(page, tdoc, rect, H, 3.0 * MM, h["scale"])
        tdoc.close()
        if not ref or ref[0] < confirm:
            continue                       # 안쪽 무늬가 안 맞으면 택이 아니다 — 아무것도 안 찍는다
        out.append({"family": h["family"], "size": h["size"], "score": round(ref[0], 3),
                    "scale": round(ref[2], 3), "rect_pt": [round(v, 2) for v in ref[1]]})
    doc.close()
    return out[:max_hits]


def overlay_for(hit: dict, target_size: str, lib: Optional[dict] = None):
    """찾은 택 자리에 target_size 택을 찍을 (pdf 경로, 디자인 좌표 행렬). 그 사이즈 택이 없으면 None."""
    lib = lib if lib is not None else load_library()
    meta = (lib.get(hit["family"]) or {}).get(target_size)
    if not meta:
        return None
    bx0, by0, bx1, by1 = meta["box_pt"]
    rx0, ry0, rx1, ry1 = hit["rect_pt"]
    k = (rx1 - rx0) / (bx1 - bx0)
    # 택 PDF 는 원본(무기고) 좌표 그대로 MediaBox 만 택 상자 → 상자 왼아래를 찾은 자리 왼아래로
    return meta["path"], (k, 0.0, 0.0, k, rx0 - k * bx0, ry0 - k * by0)
