# 기준점(꼭짓점) 찾기 — 표준 웜업 CAD 와 가스공사 패턴을 «같은 이름의 점»으로 맞춘다
#   점 좌표는 조각마다 정한 기준(원점·방향)으로 바꿔 돌려준다:
#     몸판 뒤판   원점 = 뒤중심 밑단, x = 뒤중심에서 옆으로(+), y = 위(+)   — 좌우는 대칭이라 오른쪽(+x)만 쓴다
#     몸판 앞판   원점 = 앞중심 밑단, x = 앞중심에서 옆선 쪽(+)            — 표준은 앞판+앞판사이바를 이어 붙여 한 장으로 본다
#     소매        원점 = 밑단 가운데, x = 앞쪽(+), y = 위(+)
#     바지 앞·뒤판 원점 = 옆선 밑단, x = 옆선에서 가랑이 쪽(+), y = 위(+)
import math


def tips(P):
    n = len(P)
    return {i for i in range(n) if 3 < math.dist(P[i - 1], P[i]) < 7 and 3 < math.dist(P[i], P[(i + 1) % n]) < 7
            and math.dist(P[i - 1], P[(i + 1) % n]) < 0.5}


def clean(P):
    t = tips(P); out = []
    for i, v in enumerate(P):
        if i in t: continue
        if out and math.dist(out[-1], v) < 0.5: continue
        out.append(tuple(v))
    if math.dist(out[0], out[-1]) < 0.5: out.pop()
    return out


def corners(P, thr=25):
    P = clean(P); n = len(P); ang = lambda a, b: math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    return [P[i] for i in range(n) if abs((ang(P[i], P[(i + 1) % n]) - ang(P[i - 1], P[i]) + 180) % 360 - 180) > thr]


def notches(P):
    return [tuple(P[i - 1]) for i in sorted(tips(P))]


# ── 상의 ──
def back_pts(P):
    C = corners(P); N = notches(P)
    hem_y = min(c[1] for c in C); top_y = max(c[1] for c in C)
    hem = sorted([c for c in C if c[1] < hem_y + 5], key=lambda c: c[0])
    cbx = (hem[0][0] + hem[-1][0]) / 2
    top = sorted([c for c in C if c[1] > top_y - 5], key=lambda c: c[0])
    ua = sorted([c for c in C if hem_y + 5 < c[1] < top_y - 5], key=lambda c: c[0])
    T = lambda q: (q[0] - cbx, q[1] - hem_y)
    return {"옆밑단": T(hem[-1]), "겨드랑이": T(ua[-1]), "목옆": T(top[-1]), "뒤목중심": (0.0, top_y - hem_y)}, (cbx, hem_y)


def front_pts_gas(P):
    C = corners(P)
    cfx = max(c[0] for c in C); hem_y = min(c[1] for c in C)
    cf = sorted([c for c in C if c[0] > cfx - 2], key=lambda c: c[1])
    rest = [c for c in C if c[0] <= cfx - 2]
    side_hem = min(rest, key=lambda c: c[1]); top = max(rest, key=lambda c: c[1])
    ua = [c for c in rest if c not in (side_hem, top)][0]
    T = lambda q: (cfx - q[0], q[1] - hem_y)
    return {"앞중심목": T(cf[-1]), "목옆": T(top), "겨드랑이": T(ua), "옆밑단": T(side_hem)}, (cfx, hem_y)


def front_pts_std(Pf, Ps):
    """표준 앞판(앞중심~가운데 솔기) + 앞판사이바(솔기~옆선) 를 가운데 솔기 밑단에서 이어 붙인다"""
    C = corners(Pf); S = corners(Ps)
    cfx = max(c[0] for c in C); hem_y = min(c[1] for c in C if c[0] > cfx - 2)
    cf = sorted([c for c in C if c[0] > cfx - 2], key=lambda c: c[1])
    seam_f = min(C, key=lambda c: (c[0], c[1]))                      # 앞판 가운데 솔기 밑단(왼쪽 아래)
    seam_f_hem = min([c for c in C if c[0] < seam_f[0] + 2], key=lambda c: c[1])
    neck = max([c for c in C if c[0] < cfx - 2], key=lambda c: c[1])
    sx = max(c[0] for c in S); s_hem = min([c for c in S if c[0] > sx - 2], key=lambda c: c[1])
    side_hem = min([c for c in S if c[0] < sx - 2], key=lambda c: c[1]); ua = max([c for c in S if c[0] < sx - 2], key=lambda c: c[1])
    off_x = cfx - seam_f_hem[0]; off_y = seam_f_hem[1] - hem_y
    Tf = lambda q: (cfx - q[0], q[1] - hem_y)
    Ts = lambda q: (off_x + (sx - q[0]), off_y + (q[1] - s_hem[1]))
    return {"앞중심목": Tf(cf[-1]), "목옆": Tf(neck), "겨드랑이": Ts(ua), "옆밑단": Ts(side_hem)}


def sleeve_pts(P, front_is_right):
    C = corners(P); N = notches(P)
    hem_y = min(c[1] for c in C)
    hem = sorted([c for c in C if c[1] < hem_y + 5], key=lambda c: c[0])
    hx = (hem[0][0] + hem[-1][0]) / 2
    sg = 1 if front_is_right else -1
    T = lambda q: (sg * (q[0] - hx), q[1] - hem_y)
    up = [c for c in C if c[1] > hem_y + 5]
    ua = sorted(sorted(up, key=lambda c: c[1])[:2], key=lambda c: sg * c[0])        # 낮은 두 점 = 겨드랑이
    top = sorted(sorted(up, key=lambda c: c[1])[2:], key=lambda c: sg * c[0])      # 높은 두 점 = 목 앞·뒤
    sh = max(N, key=lambda q: q[1])                                                  # 가장 높은 노치 = 어깨선
    hemB, hemF = sorted(hem, key=lambda c: sg * c[0])[0], sorted(hem, key=lambda c: sg * c[0])[-1]
    return {"밑단앞": T(hemF), "밑단뒤": T(hemB), "겨드랑이앞": T(ua[1]), "겨드랑이뒤": T(ua[0]),
            "목앞": T(top[1]), "목뒤": T(top[0]), "어깨": T(sh)}, (hx, hem_y, sg)


# ── 바지 ──
def pants_pts(P, crotch_right):
    C = corners(P)
    sg = 1 if crotch_right else -1
    hem_y = min(c[1] for c in C)
    hem = sorted([c for c in C if c[1] < hem_y + 5], key=lambda c: sg * c[0])
    side_hem, ins_hem = hem[0], hem[-1]
    T = lambda q: (sg * (q[0] - side_hem[0]), q[1] - hem_y)
    up = [c for c in C if c[1] > hem_y + 5]
    mx = max(sg * c[0] for c in up)
    crotch = max([c for c in up if sg * c[0] > mx - 15], key=lambda c: c[1])   # 가랑이 끝 — 표준은 거젯 모서리가 옆에 하나 더 있어 높은 쪽
    tops = sorted([c for c in up if c[1] > crotch[1] + 100], key=lambda c: sg * c[0])
    out = {"옆밑단": (0.0, 0.0), "안솔기밑단": T(ins_hem), "가랑이": T(crotch), "허리옆": T(tops[0]), "허리중심": T(tops[-1])}
    return out, (side_hem[0], hem_y, sg)
