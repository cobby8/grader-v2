# 노치 6종 모양 (차용 명세서 F3 — Seamly2D 의 일자·T·V·U·다이아몬드·성곽을 «생각만» 빌려 새로 짠 것, 코드 복사 없음)
#
#   왜 따로 두나: 공장마다 쓰는 노치가 다르다. 지금 엔진(notching.py)은 «일자 5mm 홈» 하나만 외곽선에 박는다.
#   여기서는 «모양»만 만든다 — 점 하나와 방향을 받아 선분(또는 재단선에 파고드는 꺾은선) 목록을 돌려준다.
#   외곽선에 끼우거나 DXF 4번 레이어 짧은 선으로 쓰는 것은 부르는 쪽이 정한다.
#
#   좌표: mm. 기준 틀 = 노치 자리 p(재단선 위) · w(몸판 안쪽 단위벡터) · u(변 방향 단위벡터, w 에 수직)
#     slit     일자      p → p+w·depth                                   (angle 로 기울일 수 있다 — 일자만)
#     T        T자       일자 + 안쪽 끝에 가로대(폭 width)
#     V        V자       재단선 위 두 점(±width/2) → 안쪽 끝 하나            ← 재단선에 파고드는 꺾은선
#     U        U자       재단선 위 두 점에서 안쪽으로 내려가 반원으로 닫힘     ← 파고드는 꺾은선
#     diamond  다이아몬드 p · 안쪽 끝 · 좌우(±width/2, 깊이 절반) 네 점 마름모(닫힌 고리)
#     castle   성곽(네모) 재단선 위 두 점 → 안쪽으로 depth → 가로 → 다시 재단선 ← 파고드는 꺾은선
#   count 2·3 = 변 방향으로 gap 간격(기본 20mm — notching.py 의 더블 노치 관례와 같다) 가운데 맞춤
#
#   실행하면 확인용 1:1 PDF 를 그린다:  python tools/pattern-engine/notchshapes.py [결과 폴더]
#     → 기본 tmp/pattern-engine/notch6/notch6.pdf
import math, os, sys

NOTCH_TYPES = ("slit", "T", "V", "U", "diamond", "castle")   # piecespec.NOTCH_TYPES 와 같은 이름·순서
DEPTH = 5.0
WIDTH = 3.0
GAP = 20.0                                                   # 더블·트리플 노치 간격 (notching.DOUBLE_GAP 과 같은 값)
OPEN_TYPES = ("V", "U", "castle")                            # 재단선을 «파고드는» 모양 — 외곽선 대신 이 꺾은선으로 돌아간다


def _unit(v):
    m = math.hypot(*v)
    if m < 1e-12: raise ValueError("방향 벡터 길이 0")
    return (v[0] / m, v[1] / m)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def notch_dir(inward, edge_dir=None, edge_in=None, edge_out=None, mode="perpendicular"):
    """노치가 들어가는 방향 w 와 변 방향 u 를 정한다 → (w, u)
       mode="perpendicular" 변에 수직(기본) — edge_dir(없으면 edge_out·edge_in)에 수직이고 inward 쪽
       mode="bisector"      모서리 점 — 들어오는 변 edge_in(앞점→이 점) · 나가는 변 edge_out(이 점→뒷점)의 각을 반으로
       inward 는 «대략 안쪽» 힌트(부호만 쓴다). 노치 방향이 바깥으로 뒤집히지 않게 한다"""
    hint = _unit(inward)
    if mode == "bisector":
        if edge_in is None or edge_out is None: raise ValueError("bisector 는 edge_in·edge_out 이 필요")
        a, b = _unit(edge_in), _unit(edge_out)
        s = (-a[0] + b[0], -a[1] + b[1])                     # 이 점에서 두 이웃 쪽으로 가는 벡터의 합 = 이등분선
        if math.hypot(*s) < 1e-9:                            # 일직선(180°) — 이등분선 = 변에 수직
            mode, edge_dir = "perpendicular", b
        else:
            w = _unit(s)
            if _dot(w, hint) < 0: w = (-w[0], -w[1])
            return w, (w[1], -w[0])
    if mode != "perpendicular": raise ValueError(f"방향 방식 {mode!r} — perpendicular·bisector 중 하나")
    d = edge_dir or edge_out or edge_in
    if d is None:                                            # 변 방향을 모르면 안쪽 힌트를 그대로
        return hint, (hint[1], -hint[0])
    u = _unit(d); w = (-u[1], u[0])
    if _dot(w, hint) < 0: w = (-w[0], -w[1])
    return w, u


def _one(p, w, u, kind, depth, width, angle):
    """노치 하나의 꺾은선 목록 — 점은 p + u·a + w·b 로 만든다"""
    at = lambda a, b: (p[0] + u[0] * a + w[0] * b, p[1] + u[1] * a + w[1] * b)
    h = width / 2
    if kind == "slit":
        if angle:                                            # 일자만 기울기 허용 — w 를 u 쪽으로 angle(도) 돌림
            r = math.radians(angle)
            return [[p, at(math.sin(r) * depth, math.cos(r) * depth)]]
        return [[p, at(0, depth)]]
    if kind == "T":
        return [[p, at(0, depth)], [at(-h, depth), at(h, depth)]]
    if kind == "V":
        return [[at(-h, 0), at(0, depth), at(h, 0)]]
    if kind == "castle":
        return [[at(-h, 0), at(-h, depth), at(h, depth), at(h, 0)]]
    if kind == "U":                                          # 곧은 두 벽 + 바닥 반원(반지름 = 폭/2) — 바닥 끝이 깊이 depth
        r = h; ry = min(r, depth); straight = depth - ry; n = 12   # 폭 > 깊이×2 면 바닥을 납작한 반타원으로 — 깊이를 넘지 않게
        arc = [at(-r * math.cos(math.pi * k / n), straight + ry * math.sin(math.pi * k / n)) for k in range(n + 1)]
        return [[at(-r, 0)] + arc + [at(r, 0)]]
    if kind == "diamond":
        return [[p, at(-h, depth / 2), at(0, depth), at(h, depth / 2), p]]
    raise ValueError(f"노치 종류 {kind!r} — {', '.join(NOTCH_TYPES)} 중 하나")


def notch_paths(p, inward, edge_dir=None, kind="slit", depth=DEPTH, width=WIDTH, count=1, gap=GAP,
                mode="perpendicular", edge_in=None, edge_out=None, angle=None):
    """노치 모양을 꺾은선 목록으로 — [[(x,y), …], …]. count 개를 변 방향 gap 간격으로 가운데 맞춰 놓는다"""
    if kind not in NOTCH_TYPES: raise ValueError(f"노치 종류 {kind!r} — {', '.join(NOTCH_TYPES)} 중 하나")
    if count not in (1, 2, 3): raise ValueError(f"노치 개수 {count!r} — 1~3")
    if not (depth > 0 and width > 0 and gap > 0): raise ValueError("깊이·폭·간격은 0보다 커야 한다")
    if count > 1 and gap <= width: raise ValueError("간격이 폭보다 좁으면 노치끼리 겹친다")
    w, u = notch_dir(inward, edge_dir, edge_in, edge_out, mode)
    out = []
    for k in range(count):
        off = (k - (count - 1) / 2) * gap                    # 1개 0 · 2개 ±gap/2 · 3개 -gap·0·+gap
        q = (p[0] + u[0] * off, p[1] + u[1] * off)
        out += _one(q, w, u, kind, depth, width, angle)
    return out


def notch_shape(p, inward, edge_dir=None, kind="slit", depth=DEPTH, width=WIDTH, count=1, gap=GAP, **kw):
    """노치 모양을 선분 목록으로 — [((x1,y1),(x2,y2)), …]  (DXF 4번 레이어·PDF 에 그대로 그린다)"""
    segs = []
    for path in notch_paths(p, inward, edge_dir, kind, depth, width, count, gap, **kw):
        segs += [(path[i], path[i + 1]) for i in range(len(path) - 1)]
    return segs


# ── 확인용 1:1 PDF ──
def draw_pdf(out_path):
    import fitz                                              # PyMuPDF
    PT = 72 / 25.4                                           # mm → pt
    W_MM, H_MM = 297, 210                                    # A4 가로
    doc = fitz.open(); page = doc.new_page(width=W_MM * PT, height=H_MM * PT)
    font = "C:/Windows/Fonts/malgun.ttf"
    has_font = os.path.exists(font)
    if has_font: page.insert_font(fontname="mg", fontfile=font)

    def text(x, y, s, size=7):
        page.insert_text(fitz.Point(x * PT, y * PT), s, fontsize=size, fontname="mg" if has_font else "helv")

    def line(a, b, color=(0, 0, 0), wd=0.25):
        page.draw_line(fitz.Point(a[0] * PT, a[1] * PT), fitz.Point(b[0] * PT, b[1] * PT), color=color, width=wd)

    text(12, 14, "노치 6종 확인 — 1:1 (A4 가로, 100% 로 인쇄해 자로 재기) · 깊이 5mm · 폭 3mm · 2·3개는 간격 20mm", 9)
    line((12, 20), (62, 20), wd=0.6); [line((12 + 10 * k, 18.5), (12 + 10 * k, 21.5), wd=0.4) for k in range(6)]
    text(64, 21, "50mm 자(10mm 눈금)")
    NAME = {"slit": "일자 slit", "T": "T자 T", "V": "V자 V", "U": "U자 U", "diamond": "다이아몬드 diamond", "castle": "성곽 castle"}
    # 칸: 종류 6줄 × 개수 3칸. 재단선 = 가로선, 몸판은 아래쪽(안쪽 = +y). 칸마다 재단선 60mm
    y0, dy, x0, dx = 38, 26, 60, 70
    for c in range(3): text(x0 + c * dx + 18, y0 - 8, f"{c + 1}개")
    for r, kind in enumerate(NOTCH_TYPES):
        y = y0 + r * dy; text(12, y + 3, NAME[kind], 8)
        for c in range(3):
            cx = x0 + c * dx + 25
            line((cx - 30, y), (cx + 30, y), color=(0.6, 0.6, 0.6))          # 재단선(회색)
            for a, b in notch_shape((cx, y), (0, 1), (1, 0), kind, count=c + 1):
                line(a, b, color=(0.85, 0, 0), wd=0.3)                        # 노치(빨강)
    # 모서리 이등분선 예 — 직각 모서리(밑단 왼쪽 끝 같은 자리)
    yc, cx = 200, 70                                         # 몸판 = 모서리의 오른쪽 위
    line((cx, yc - 22), (cx, yc), color=(0.6, 0.6, 0.6)); line((cx, yc), (cx + 30, yc), color=(0.6, 0.6, 0.6))
    for a, b in notch_shape((cx, yc), (1, -1), kind="slit", mode="bisector", edge_in=(0, 1), edge_out=(1, 0)):
        line(a, b, color=(0, 0, 0.85), wd=0.3)
    for a, b in notch_shape((cx, yc - 12), (1, 0), (0, 1), "T"):
        line(a, b, color=(0.85, 0, 0), wd=0.3)
    text(12, yc - 8, "모서리 노치", 8)
    text(cx + 34, yc - 2, "이등분선(파랑, 직각 모서리 45°) · 변에 수직(빨강 T)", 7)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path); doc.close()
    return out_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    here = os.path.dirname(os.path.abspath(__file__)); repo = os.path.dirname(os.path.dirname(here))
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo, "tmp", "pattern-engine", "notch6")
    print("확인 그림:", draw_pdf(os.path.join(out_dir, "notch6.pdf")))
