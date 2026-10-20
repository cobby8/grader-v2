# 노치 넣기 — 가장 흔한 «외곽선에 박힌 일자 홈»(재단선에서 안쪽 5mm)만 (2026-10-19 사장님: 일반적인 것만)
#   우리 활성 제품(하키티·농구 상의·반팔 슈팅저지·가스 웜업)이 쓰는 모양: 외곽선 → 안쪽 5mm → 같은 자리로 되돌아와 계속
#   앞 1개 · 뒤 2개(더블, 간격 20mm)
import math
from shapely.geometry import Polygon, Point

DEPTH = 5.0
DOUBLE_GAP = 20.0


def _closed(P):
    return P[:-1] if len(P) > 2 and math.dist(P[0], P[-1]) < 0.5 else P[:]


def nearest(P, q):
    return min(range(len(P)), key=lambda i: math.dist(P[i], q))


def edge(P, a, b, expect=None):
    """닫힌 외곽선 P 에서 꼭짓점 a → b 로 가는 점 번호 목록(두 방향 중 expect 길이에 가까운 쪽, 없으면 짧은 쪽)"""
    Q = _closed(P); n = len(Q); i, j = nearest(Q, a), nearest(Q, b)
    f = [(i + k) % n for k in range((j - i) % n + 1)]; g = [(i - k) % n for k in range((i - j) % n + 1)]
    L = lambda w: sum(math.dist(Q[w[k]], Q[w[k + 1]]) for k in range(len(w) - 1))
    return min((f, g), key=(lambda w: abs(L(w) - expect)) if expect else L)


def length(P, idx):
    Q = _closed(P); return sum(math.dist(Q[idx[k]], Q[idx[k + 1]]) for k in range(len(idx) - 1))


def point_at(P, idx, d):
    """경로 idx 를 따라 d(mm) 간 자리 → (점, 그 점이 놓인 토막 (앞번호, 뒷번호))"""
    Q = _closed(P); s = 0.0
    for k in range(len(idx) - 1):
        a, b = Q[idx[k]], Q[idx[k + 1]]; L = math.dist(a, b)
        if s + L >= d - 1e-9:
            t = (d - s) / L if L else 0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), (idx[k], idx[k + 1])
        s += L
    raise ValueError(f"경로 길이 {s:.1f} 보다 먼 자리 {d:.1f}")


def insert_slits(P, marks, depth=DEPTH):
    """marks: [(점, (앞번호, 뒷번호))] → 그 자리에 «바닥 → 안쪽 끝 → 바닥» 세 점을 끼운 새 외곽선(닫힘 모양 유지)"""
    closed = len(P) > 2 and math.dist(P[0], P[-1]) < 0.5
    Q = _closed(P); poly = Polygon(Q)
    ins = {}
    for q, (i, j) in marks:
        a, b = Q[i], Q[j]; L = math.dist(a, b); u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        nrm = (-u[1], u[0])
        if not poly.contains(Point(q[0] + nrm[0] * 0.5, q[1] + nrm[1] * 0.5)): nrm = (-nrm[0], -nrm[1])   # 안쪽으로
        tip = (q[0] + nrm[0] * depth, q[1] + nrm[1] * depth)
        # 토막 (i→j) 의 순서대로 끼운다 — 이 외곽선에서 i 다음이 j 인지, j 다음이 i 인지에 따라 앞 점을 고른다
        first = i if (i + 1) % len(Q) == j else j
        ins.setdefault(first, []).append((math.dist(Q[first], q), [q, tip, q]))
    out = []
    for k, v in enumerate(Q):
        out.append(v)
        for _, trio in sorted(ins.get(k, [])):
            out.extend(trio)
    if closed: out.append(out[0])
    return out


def marks_from(P, a, b, distances, expect=None):
    """꼭짓점 a 에서 b 쪽으로 distances(mm) 마다 노치 자리"""
    idx = edge(P, a, b, expect)
    return [point_at(P, idx, d) for d in distances], length(P, idx)


def single(d):
    return [d]


def double(d, gap=DOUBLE_GAP):
    """d 를 가운데로 한 더블 노치(간격 gap)"""
    return [d - gap / 2, d + gap / 2]
