# -*- coding: utf-8 -*-
"""사이즈 택 라이브러리 만들기 — «택작업 무기고.ai» 에서 계열·사이즈별 택을 잘라 작은 PDF 로 저장(2026-10-20).

왜: 그레이더는 기준 사이즈 디자인을 키우고 줄이기만 해서, L 출력에도 «XL» 택이 찍혔다
    (최근 주문 5건 전부). 디자이너는 사이즈마다 택을 그 사이즈 것으로 바꾼다.
    → 사이즈별 택(벡터·CMYK 그대로)을 라이브러리로 두고, 출력 때 그 사이즈 택을 덮어 찍는다(engine/size_tag.py).

사용(저장소 루트):
    python scripts/build_size_tags.py ["<택작업 무기고.ai 경로>"]
    → data/size_tags/<계열>/<사이즈>.pdf + data/size_tags/index.json

무기고 배치: 머리글(농구/페가수스/축구 사이즈택 모음) 아래, 사이즈 글자(5XL…5XS·기본·2호…14호) 오른쪽에 택 1개.
"""
from __future__ import annotations

import json
import os
import sys

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = r"G:/공유 드라이브/디자인/00_템플릿·폼/커스텀패턴/2026 커스텀용 패턴/00. 작업 보조자료/택작업 무기고.ai"
OUT = os.path.join(ROOT, "data", "size_tags")
FAMILY_HEAD = {"농구": "basketball", "페가수스": "pegasus", "축구": "soccer"}
SIZES = ["5XL", "4XL", "3XL", "2XL", "XL", "L", "M", "S", "XS", "2XS", "3XS", "4XS", "5XS", "기본",
         "2호", "4호", "6호", "8호", "10호", "12호", "14호"]
FILE_NAME = {"기본": "BASE"}   # 파일 이름에 한글을 피한다(호수는 «8호» → 8HO)


_PAINT = {"f", "F", "f*", "B", "B*", "b", "b*", "S", "s", "n"}
_PATH = {"m", "l", "c", "v", "y", "re", "h"}
_STATE = {"cs", "CS", "sc", "scn", "SC", "SCN", "g", "G", "rg", "RG", "k", "K", "gs", "w", "J", "j", "M", "d", "ri", "i"}


def _mul(a, b):
    """PDF 행렬 곱 a×b (a 를 먼저 적용)."""
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


def _filtered_content(instructions, keep_rect) -> bytes:
    """페이지 콘텐츠에서 keep_rect(PDF 좌표, y 위로) 와 겹치는 «칠한 경로»만 남긴다.

    무기고 한 장에 택 45개의 경로(2MB)가 들어 있어 잘라 붙이면 택 하나가 1MB 가 됐다.
    상태 연산(q/Q·cm·색·선·gs·표시 내용)과 자르개(W n)는 모두 남기고, 그림 경로만 고른다.
    글자(BT…ET)는 사이즈 표기·머리글뿐이라 뺀다(택 안 글씨는 외곽선 경로다).
    """
    import pikepdf
    x0, y0, x1, y1 = keep_rect
    ctm = (1, 0, 0, 1, 0, 0)
    stack = []
    out = []
    path_ops = []
    pts = []
    in_text = False
    clip_pending = False
    for operands, op in instructions:
        o = str(op)
        if o == "BT":
            in_text = True
            continue
        if o == "ET":
            in_text = False
            continue
        if in_text:
            # 글자 블록 안의 색·그래픽 상태 설정은 ET 뒤에도 남는다(PDF 규약) — 빼면 뒤 경로가 검정이 된다
            if o in _STATE:
                out.append((operands, op))
            continue
        if o == "q":
            stack.append(ctm); out.append((operands, op)); continue
        if o == "Q":
            ctm = stack.pop() if stack else ctm; out.append((operands, op)); continue
        if o == "cm":
            ctm = _mul(tuple(float(v) for v in operands), ctm); out.append((operands, op)); continue
        if o in _PATH:
            path_ops.append((operands, op))
            v = [float(x) for x in operands]
            if o == "re":
                cand = [(v[0], v[1]), (v[0] + v[2], v[1] + v[3])]
            else:
                cand = [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
            for px, py in cand:
                pts.append((ctm[0] * px + ctm[2] * py + ctm[4], ctm[1] * px + ctm[3] * py + ctm[5]))
            continue
        if o in ("W", "W*"):
            clip_pending = True
            path_ops.append((operands, op))
            continue
        if o in _PAINT:
            keep = clip_pending                     # 자르개 경로는 늘 남긴다(상태)
            if pts and not keep:
                bx0 = min(p[0] for p in pts); bx1 = max(p[0] for p in pts)
                by0 = min(p[1] for p in pts); by1 = max(p[1] for p in pts)
                keep = bx1 >= x0 and bx0 <= x1 and by1 >= y0 and by0 <= y1
            if keep:
                out.extend(path_ops)
                out.append((operands, op))
            path_ops, pts, clip_pending = [], [], False
            continue
        out.append((operands, op))                  # 색·선·gs·BDC/EMC 등 상태 연산
    # 칠한 것이 하나도 없는 q…Q 묶음은 통째로 뺀다(뺀 경로를 감싸던 껍데기 4천여 개)
    cleaned = []
    starts = []
    for item in out:
        o = str(item[1])
        if o == "q":
            starts.append(len(cleaned))
            cleaned.append(item)
        elif o == "Q":
            s = starts.pop() if starts else None
            if s is not None and not any(str(x[1]) in _PAINT and str(x[1]) != "n" for x in cleaned[s:]):
                del cleaned[s:]
            else:
                cleaned.append(item)
        else:
            cleaned.append(item)
    return pikepdf.unparse_content_stream(cleaned)


def build(src: str = DEFAULT_SRC, out: str = OUT) -> dict:
    doc = fitz.open(src)
    page = doc[0]
    words = page.get_text("words")
    drawings = page.get_drawings()
    heads = sorted((w[0], FAMILY_HEAD[w[4]]) for w in words if w[4] in FAMILY_HEAD)
    index: dict = {}
    import pikepdf
    psrc = pikepdf.open(src)
    ppage = psrc.pages[0]
    instructions = list(pikepdf.parse_content_stream(ppage))
    res = {k: v for k, v in ppage.Resources.items() if k != "/Font"}
    # 색공간: ICC 기반 CMYK(4채널, 프로필 380KB) → DeviceCMYK. 수치는 그대로라 그레이더의 device CMYK 출력과 같고,
    #   택마다 프로필이 붙어 1개 400KB 가 되던 것을 10KB 대로 줄인다.
    cs = dict(res.get("/ColorSpace", {}))
    for k, v in list(cs.items()):
        if isinstance(v, pikepdf.Array) and str(v[0]) == "/ICCBased" and int(v[1].get("/N", 0)) == 4:
            cs[k] = pikepdf.Name.DeviceCMYK
    if cs:
        res["/ColorSpace"] = pikepdf.Dictionary(cs)
    res_no_font = psrc.make_indirect(pikepdf.Dictionary(res))
    for w in words:
        if w[4] not in SIZES:
            continue
        x0, y0, x1, y1 = w[:4]
        cy = (y0 + y1) / 2
        fam = [h for h in heads if h[0] <= x0 + 200][-1][1]
        if w[4].endswith("호"):
            fam = "soccer"          # 축구 계열 오른쪽 줄 = 아동 호수
        band = fitz.Rect(x1 + 15, cy - 81, x1 + 420, cy + 81)   # 그 줄의 택만(위·아래 이웃 택은 안 들어오게)
        rects = [d["rect"] for d in drawings if band.contains(d["rect"])]
        if not rects:
            print(f"택 없음: {fam} {w[4]}")
            continue
        r = fitz.Rect(rects[0])
        for q in rects[1:]:
            r |= q
        size = w[4]
        fname = FILE_NAME.get(size, size.replace("호", "HO"))
        os.makedirs(os.path.join(out, fam), exist_ok=True)
        # fitz(y 아래) → PDF(y 위) 좌표의 택 상자. 새 PDF 는 원본 좌표 그대로 두고 MediaBox 만 택 상자로.
        H = page.rect.height
        box = [r.x0, H - r.y1, r.x1, H - r.y0]
        pdst = pikepdf.new()
        content = _filtered_content(instructions, box)
        new_page = pikepdf.Dictionary(
            Type=pikepdf.Name.Page, MediaBox=pikepdf.Array(box),
            Resources=pdst.copy_foreign(res_no_font),
            Contents=pdst.make_stream(content))
        pdst.pages.append(pikepdf.Page(new_page))
        rel = f"{fam}/{fname}.pdf"
        pdst.save(os.path.join(out, rel), compress_streams=True)
        index.setdefault(fam, {})[size] = {"file": rel, "box_pt": [round(v, 3) for v in box],
                                           "w_pt": round(r.width, 3), "h_pt": round(r.height, 3)}
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"source": os.path.basename(src), "families": index}, f, ensure_ascii=False, indent=1)
    return index


if __name__ == "__main__":
    idx = build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC)
    for fam, sizes in idx.items():
        print(fam, len(sizes), "개:", " ".join(sizes))
