# 마커(원단 배치) + 요척 — 명세서 F7 «큰 조각부터 깔기» + 효율 올리기(접촉 점수·여러 번 깔기·지역 개선·끝부분 다시 깔기)
#
#   왜 필요한가: 원단 폭에 실제 주문 수량을 깔아 봐야 «벌당 요척(원단 m)» 이 나오고, 그게 원가·원단 발주다.
#   마커 효율 1%p ≈ 원단 길이 1.2% — 효율이 곧 원단 원가다. nest.py 는 «사이즈 겹침 그림» 일 뿐 배치가 아니다.
#
#   좌표: 마커 x = 원단 폭 방향(0 ~ 폭) · y = 원단 길이 방향(0 = 원단 시작). 조각 좌표의 y 축 = 식서(세로).
#   회전은 식서 기준 0°/180° 만 — 옆으로 눕히면 식서가 틀어져 옷이 늘어난다. 원단 결(--nap)이 있으면 0° 만.
#   뒤집기(겉/안 바꿈)는 기본 금지 — R/L 은 이미 거울로 펼쳐 놓았으니 뒤집으면 R 이 L 로 바뀐다.
#
#   방식(외부 배치 라이브러리 없이 — 라이선스 확인 전):
#     ① 격자(기본 2mm)에 조각을 «간격/2 + 격자 반대각선» 만큼 부풀려 칠한다 → 칸이 안 겹치면 실제로도 간격 이상 떨어진다(보수적)
#     ② 빈자리 찾기 = 깐 칸과 조각 칸의 겹침 수를 FFT 상관으로 한 번에. 아래부터 «띠» 하나씩만 계산하고,
#        조각 안 직사각형이 통째로 비어 들어갈 수 없는 행은 FFT 전에 누적합으로 걸러 빠르게 한다
#     ③ 자리 고르기 = 가장 낮은 빈자리 근처에서 «낮음 + 둘레가 이미 깐 조각·원단 가장자리에 많이 닿음(접촉 점수)»
#     ④ 여러 번 깔기(search_marker): 깔 순서 × 기준 조합 · 무작위 섞기(시드 고정) · 언덕 오르기(맞바꾸기·당기기)
#        · 끝부분 다시 깔기(마커 끝 조각을 빼고 다시 짓기) — 병렬 일꾼, 결과는 일꾼 수와 무관
#     ⑤ 격자 때문에 남은 틈은 «정확한 도형(shapely)» 으로 아래·왼쪽으로 밀어 메우고(압축),
#        끝에 걸린 조각을 빼서 더 낮은 빈자리에 다시 넣는다
#     ⑥ 마지막에 모든 조각 쌍의 실제 거리를 다시 재서 보고한다(검산)
#
#   실행(저장소 루트에서):
#     python tools/pattern-engine/marker.py --garment top                     # 가스 웜업 상의 S~5XL 각 1벌 · 폭 150cm (약 2분)
#     python tools/pattern-engine/marker.py --garment bottom --counts S=1 M=2 --width 150 --gap 3 --nap
#     python tools/pattern-engine/marker.py --garment top --quick             # 한 번만 깔기(상의 약 12~13초·하의 약 17~18초)
#     결과: tmp/pattern-engine/marker/마커_<상의|하의>.{pdf,dxf,json} · _미리보기.png
import os, sys, json, math, time, argparse, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import shapely
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.affinity import translate
from shapely.ops import unary_union, polylabel

SIZES = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
PDF_MAX_MM = 5000.0          # PDF 한 쪽 최대 200인치(5080mm) — 넘으면 여러 쪽으로 나눠 이어 붙인다
FONT = "C:/Windows/Fonts/malgun.ttf"


# ════════════════ 수량: 주문 명단 → 사이즈별 벌수 ════════════════
_SIZE_ALIAS = {"XXL": "2XL", "XXXL": "3XL", "XXXXL": "4XL", "XXXXXL": "5XL", "2X": "2XL", "3X": "3XL", "4X": "4XL", "5X": "5XL"}


def norm_size(s):
    """사이즈 글자 정리 — ' 2xl ' → '2XL', 'XXL' → '2XL'. 빈칸이면 ''."""
    t = str(s or "").strip().upper().replace(" ", "")
    return _SIZE_ALIAS.get(t, t)


def counts_from_members(members, garment):
    """주문 명단(orderSheet.members) → {사이즈: 벌수}.
    피스 규칙(CLAUDE.md «수량은 피스로 센다»): 상의 = topSize 가 채워진 사람 수, 하의 = bottomSize 가 채워진 사람 수.
    상의만 입는 사람·사이즈가 위아래 다른 사람이 실제로 있어 «세트» 로 묶지 않는다.
    운영 DB 는 읽지 않는다 — 명단은 부르는 쪽이 넘겨준다."""
    key = {"top": "topSize", "상의": "topSize", "bottom": "bottomSize", "하의": "bottomSize"}[garment]
    out = {}
    for m in members or []:
        s = norm_size((m or {}).get(key))
        if s:
            out[s] = out.get(s, 0) + 1
    # 표준 사이즈 순서로, 모르는 사이즈는 뒤에(버리지 않는다 — 부른 쪽이 알아채게)
    return {s: out[s] for s in sorted(out, key=lambda s: (SIZES.index(s) if s in SIZES else 99, s))}


# ════════════════ 조각 준비 ════════════════
def _polys(g):
    """GeometryCollection 안의 면(Polygon)만 꺼낸다 — 원본 재단선의 노치 뾰족점이 «넓이 0 선» 으로 갈라져 나오는 것을 버린다."""
    if g.geom_type == "Polygon":
        return [g] if g.area > 0 else []
    if hasattr(g, "geoms"):
        return [q for h in g.geoms for q in _polys(h)]
    return []


def clean_geom(pts):
    """재단선 점 → 올바른 도형. 노치 뾰족점의 자기 교차(넓이 0)를 정리한다 — 면적은 그대로."""
    g = Polygon(pts)
    if not g.is_valid:
        g = unary_union(_polys(shapely.make_valid(g)))
    return g


def pieces_from_graded(graded, garment, counts, spec=None, exclude=()):
    """그레이딩 결과(graded.json) + 사이즈별 벌수 → 배치할 조각 목록.
    장수·좌우(R/L 거울)는 gas_warmup_meta 의 SPEC 을 patlib.expand 로 펼친다(그레이딩·명세와 같은 규칙)."""
    from patlib import expand
    from gas_warmup_meta import SPEC_T, SPEC_B
    g = {"top": "top", "상의": "top", "bottom": "bottom", "하의": "bottom", "imported": "imported"}[garment]
    if g == "imported" and not spec:                          # 들여온 스타일 — 펼침표(--spec-file)가 꼭 있어야 한다(가스 표를 쓰면 엉뚱한 조각)
        raise ValueError("들여온 스타일은 펼침표(--spec-file)가 필요하다")
    spec = spec or (SPEC_T if g == "top" else SPEC_B)
    out = []
    for size, n in counts.items():
        if n <= 0:
            continue
        if size not in graded:
            raise KeyError(f"그레이딩 결과에 {size} 사이즈가 없다")
        inst = expand(graded[size][g], spec)
        for b in range(1, n + 1):
            for name, (p, base, side, note) in inst.items():
                if base in exclude:
                    continue
                out.append({"id": f"{size}#{b} {name}", "name": name, "base": base, "size": size, "bundle": b,
                            "side": side, "cut": p["cut"], "flip": p.get("flip", "금지" if side else "허용")})
    return out


# ════════════════ 배치 ════════════════
def _fast(n):
    """FFT 가 빠른 크기(2·3·5 만의 곱) 중 n 이상인 가장 작은 수."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


def place_pts(pts, sx, sy, dx, dy):
    """원래 조각 좌표 → 마커 좌표. sx·sy 는 ±1 뿐(식서 y 축이 세로로 남는다). 0°: (1,1) · 180°: (−1,−1) · 뒤집기: sx 만 −1."""
    return [(sx * x + dx, sy * y + dy) for x, y in pts]


def _orient(g, rot, flip):
    sx = (-1 if flip else 1) * (-1 if rot == 180 else 1); sy = -1 if rot == 180 else 1
    h = shapely.transform(g, lambda a: a * np.array([sx, sy]))
    x0, y0, _, _ = h.bounds
    return translate(h, -x0, -y0), sx, sy, (x0, y0)


def _maxrun(B):
    """행마다 «가장 긴 연속 True» 의 길이. 조각이 들어갈 수 있는 가장 낮은 행을 미리 거르는 데 쓴다
    (조각 칸의 어느 행이 연속 n 칸이면 그 자리 원단 행에도 연속 빈칸이 n 개 이상 있어야 한다 — 필요조건)."""
    r = B.shape[0]
    z = np.zeros((r, 1), np.int8)
    d = np.diff(np.concatenate([z, B.astype(np.int8), z], 1), axis=1)
    rs, cs = np.nonzero(d == 1); _, ce = np.nonzero(d == -1)       # 행 순서대로 시작·끝이 번갈아 나온다
    out = np.zeros(r, np.int32)
    np.maximum.at(out, rs, ce - cs)
    return out


def _inner_rect(M):
    """칸 묶음 안에 통째로 든 큰 직사각형 (행, 열, 높이, 폭) — FFT 전에 «이 행에선 어차피 안 들어간다» 를 싸게 거르는 데 쓴다.
    행마다 첫 칸~끝 칸이 꽉 찬 행만 보고, 왼쪽·오른쪽 경계 후보 몇 개를 맞춰 가장 넓은 것을 고른다(정확한 최대일 필요는 없다)."""
    B = M > 0
    h, w = B.shape
    cnt = B.sum(1); has = cnt > 0
    Lr = np.where(has, B.argmax(1), w); Rr = np.where(has, w - B[:, ::-1].argmax(1), 0)
    full = has & (cnt == Rr - Lr)
    q = np.linspace(0, 100, 13)
    c0s = np.unique(np.percentile(Lr[full], q).astype(int)) if full.any() else np.array([0])
    c1s = np.unique(np.percentile(Rr[full], q).astype(int)) if full.any() else np.array([1])
    best = (1, 0, 0, 1, 1)
    for c0 in c0s:
        c1 = c1s[c1s > c0]
        if not len(c1):
            continue
        okr = full[None, :] & (Lr[None, :] <= c0) & (Rr[None, :] >= c1[:, None])     # (후보 수, 행)
        runs = _maxrun(okr)
        for k in range(len(c1)):
            if runs[k] * (c1[k] - c0) > best[0]:
                rows = okr[k]
                # 가장 긴 연속 구간의 시작 행
                d = np.diff(np.concatenate([[0], rows.astype(np.int8), [0]]))
                st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
                j = int(np.argmax(en - st))
                best = (int(runs[k] * (c1[k] - c0)), int(st[j]), int(c0), int(en[j] - st[j]), int(c1[k] - c0))
    return best[1:]


def _dilate(M, r):
    """칸을 둥글게 r 칸 넓힌다(접촉 고리용)."""
    h, w = M.shape
    D = np.zeros((h + 2 * r, w + 2 * r), np.float32)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + 0.5:
                sl = D[r + dy:r + dy + h, r + dx:r + dx + w]
                np.maximum(sl, M, out=sl)
    return D


def _prepare(pieces, width_mm=1500.0, gap_mm=3.0, res_mm=4.0, rotations=(0, 180), allow_flip=False, selvage_mm=0.0,
             ring_mm=8.0, cache_mb=None):
    """조각마다 방향(0°/180°·허용 시 뒤집기)별 격자 칸을 만든다. 배치를 여러 번 돌려도 한 번만 한다."""
    W, s, res = float(width_mm), float(selvage_mm), float(res_mm)
    if any(r not in (0, 180) for r in rotations) or not rotations:
        raise ValueError("회전은 식서 기준 0°/180° 만 허용한다")
    # 격자 칸이 안 겹치면 실제 거리 ≥ 간격이 되도록 부풀리는 양 — 칸 중심까지 거리 ≤ 반대각선(0.7071·res),
    #   shapely 버퍼가 원을 다각형으로 근사해 0.5% 작게 나오는 것까지 덮게 넉넉히
    m = gap_mm / 2 + res * 0.7072 / 0.99 + 0.01
    K = int(math.ceil(m / res)) + 1                        # 격자 가장자리 여백 칸(조각 부풀린 부분이 들어갈 자리)
    C = 2 * K + int(math.ceil(W / res)) + 2
    r = max(1, int(round(ring_mm / res)))                  # 접촉 고리 두께(칸)
    Cf = _fast(C + r + 1)                                  # 고리가 왼쪽으로 r 칸 삐져도 감싸 돌지 않게 여유
    extra = max(16, int(round(200 / res)))                 # 한 번에 훑는 띠 높이 여유(약 20cm)
    items = []
    # 같은 모양 나눠 쓰기(2026-10-20 · 메모리) — 같은 사이즈 여러 벌은 재단선이 바이트까지 같다. 예전엔 벌마다 격자 칸·고리를 새로 만들어
    #   상의 28벌에 617MB 였다. 같은 재단선 + 같은 뒤집기 규칙이면 처음 만든 방향 자료(oris)를 그대로 쓴다 — 같은 입력이라 계산 결과도 같다.
    memo = {}
    for i, p in enumerate(pieces):
        can_flip = bool(allow_flip and p.get("flip") != "금지" and not p.get("side"))
        mkey = (np.asarray(p["cut"], dtype=np.float64).tobytes(), can_flip)
        if mkey in memo:
            s0 = memo[mkey]
            items.append({"i": i, "p": p, "g0": s0["g0"], "area": s0["area"], "oris": s0["oris"], "hm": s0["hm"], "hb": s0["hb"], "Rf": s0["Rf"]})
            continue
        g0 = clean_geom(p["cut"])
        oris = []
        for rot in rotations:
            for flip in ([False, True] if can_flip else [False]):
                g, sx, sy, (x0, y0) = _orient(g0, rot, flip)
                _, _, bw, bh = g.bounds
                if bw > W - 2 * s + 1e-9:
                    raise ValueError(f"{p['id']}: 조각 폭 {bw:.0f}mm 가 원단 폭 {W - 2 * s:.0f}mm 보다 넓다")
                buf = g.buffer(m); shapely.prepare(buf)
                wm = 2 * K + int(math.ceil(bw / res)) + 1; hm = 2 * K + int(math.ceil(bh / res)) + 1
                xs = (np.arange(wm) - K + 0.5) * res; ys = (np.arange(hm) - K + 0.5) * res
                X, Y = np.meshgrid(xs, ys)
                M = shapely.contains_xy(buf, X, Y).astype(np.float32)        # 행 = y(아래→위), 열 = x
                ring = _dilate(M, r); ring[r:r + hm, r:r + wm] -= M          # 조각 둘레 고리(접촉 세기)
                oris.append({"rot": rot, "flip": flip, "g": g, "sx": sx, "sy": sy, "x0": x0, "y0": y0, "bw": bw, "bh": bh,
                             "key": (M.shape, hashlib.md5(M.tobytes()).hexdigest()),     # 같은 칸 모양(같은 사이즈 여러 벌)은 FFT 를 나눠 쓴다
                             "M": M, "rows": _maxrun(M > 0), "rect": _inner_rect(M), "ring": ring, "nring": float(ring.sum()),
                             "ccs": np.concatenate([[0.0], np.cumsum(ring.sum(0))]),   # 고리 열 누적(옆 벽 접촉)
                             "crs": np.concatenate([[0.0], np.cumsum(ring.sum(1))]),   # 고리 행 누적(바닥 벽 접촉)
                             "ox_lo": int(math.ceil(s / res - 1e-9)), "ox_hi": int(math.floor((W - s - bw) / res + 1e-9))})
        hm = oris[0]["M"].shape[0]                         # 0°/180°·뒤집기는 외접 사각형이 같다 → 칸 높이도 같다
        hb = hm + max(extra, hm // 2)
        items.append({"i": i, "p": p, "g0": g0, "area": g0.area, "oris": oris, "hm": hm, "hb": hb, "Rf": _fast(hb + 2 * r)})
        memo[mkey] = items[-1]
    return {"items": items, "W": W, "s": s, "res": res, "gap": gap_mm, "m": m, "K": K, "C": C, "Cf": Cf, "r": r,
            "rotations": list(rotations), "allow_flip": allow_flip, "maxhb": max(it["hb"] for it in items),
            "cache": {}, "cache_left": cache_mb_of(cache_mb) * 2 ** 20}


CACHE_MB_DEFAULT = 900                                       # 조각 FFT 기억 한도(MB, 일꾼 하나당) — 크면 빠르고 메모리를 많이 쓴다


def cache_mb_of(v=None):
    """FFT 기억 한도(MB) 정하기 — ① 인자 ② 환경변수 PATTERN_ENGINE_MARKER_CACHE_MB(서버용 — 예: Render 512MB 면 100)
    ③ 기본 900. 0 이면 기억하지 않고 그때그때 계산한다(결과는 같고 느려질 뿐이다)."""
    if v is None:
        env = os.environ.get("PATTERN_ENGINE_MARKER_CACHE_MB", "").strip()
        v = float(env) if env else CACHE_MB_DEFAULT
    v = float(v)
    if v < 0:
        raise ValueError("cache_mb 는 0 이상이어야 한다")
    return v


def _kernel_fft(P, idx, oi, which):
    """조각 칸(M)·고리(ring)의 FFT — 메모리 한도 안에서만 기억해 두고 넘으면 그때그때 계산한다."""
    it = P["items"][idx]; o = it["oris"][oi]
    key = (o["key"], it["Rf"], which)
    F = P["cache"].get(key)
    if F is None:
        F = np.conj(np.fft.rfft2(o[which], s=(it["Rf"], P["Cf"])))
        if F.nbytes <= P["cache_left"]:
            P["cache"][key] = F; P["cache_left"] -= F.nbytes
    return F


class _Grid:
    """깔린 칸 판 — G[행 + r, 열] = 그 칸을 덮은 조각 수(0 = 빈칸). 행 아래에 r 칸 여유(고리가 바닥 밑으로 삐져도 되게).
    f[행] = 그 행의 가장 긴 빈칸 길이(들어갈 수 없는 행을 FFT 전에 거른다). top = 이 행부터 위는 비어 있다."""

    def __init__(self, P, rows=0):
        self.P = P
        # 판은 uint8(칸마다 겹친 조각 수 0·1) — 마커가 길면(상의 28벌 41m) float32 판이 두 배씩 늘며 순간 400MB 를 넘었다(2026-10-20).
        #   FFT 에 넣을 때만 그 띠를 float32 로 바꾼다 → 계산 값은 예전과 똑같다
        self.G = np.zeros((P["r"] + P["K"] + max(rows, 0) + 4 * P["maxhb"], P["C"]), np.uint8)
        self.f = np.full(self.G.shape[0] - P["r"], P["C"], np.int32)
        self.top = P["K"]

    def _ensure(self, need):
        if need > self.G.shape[0]:
            C, r = self.P["C"], self.P["r"]
            n2 = max(need, 2 * self.G.shape[0])
            self.G = np.vstack([self.G, np.zeros((n2 - self.G.shape[0], C), self.G.dtype)])
            self.f = np.concatenate([self.f, np.full(n2 - r - self.f.shape[0], C, np.int32)])

    def snapshot(self):
        """지금 판 상태를 작게 떠 둔다(지역 개선에서 앞부분을 다시 깔지 않으려고). 칸 값은 겹친 조각 수라 uint8 로 충분."""
        r = self.P["r"]
        return (self.G[:r + self.top].astype(np.uint8), self.f[:self.top].copy(), self.top)

    @classmethod
    def restore(cls, P, snap):
        g = cls(P, rows=snap[2])
        g.G[:snap[0].shape[0]] = snap[0]; g.f[:len(snap[1])] = snap[1]; g.top = snap[2]
        return g

    def put(self, M, ox, oy, sign=1.0):
        """칸 묶음 M 을 (열 ox, 행 oy) 에 더하거나(sign=1) 뺀다(−1)."""
        r = self.P["r"]; h, w = M.shape
        self._ensure(r + oy + h + 1)
        sl = self.G[r + oy:r + oy + h, ox:ox + w]
        sl[...] = sl + sign * M                             # 0/1 정수끼리 — uint8 로 그대로 담긴다
        self.f[oy:oy + h] = _maxrun(self.G[r + oy:r + oy + h] < 0.5)
        if sign > 0:
            self.top = max(self.top, oy + h)
        else:
            occ = np.flatnonzero(self.f[:self.top] < self.P["C"])
            self.top = max(self.P["K"], int(occ[-1]) + 1 if len(occ) else 0)

    def _skip(self, it, ok, y, chunk=384):
        """y 부터 위로, 조각 안 직사각형이 통째로 비어 들어갈 수 있는 첫 시작 행(필요조건 — FFT 를 아끼려고 먼저 거른다).
        top 행에서는 위가 다 비어 있으니 반드시 멈춘다. 누적합 판은 방향끼리 같이 쓴다."""
        r, G, C = self.P["r"], self.G, self.P["C"]
        oris = it["oris"]
        lo = min(o["rect"][0] for o in oris); hi = max(o["rect"][0] + o["rect"][2] for o in oris)
        while True:
            y1 = min(y + chunk, len(ok)); n = y1 - y
            occ = G[r + y + lo:r + y1 - 1 + hi] > 0.5               # 행: 격자 행 y+lo ~ y1−1+hi
            I = np.zeros((occ.shape[0] + 1, C + 1), np.int32)
            np.cumsum(np.cumsum(occ, 0, dtype=np.int32), 1, out=I[1:, 1:])
            okr = np.zeros(n, bool)
            for o in oris:
                ri, ci, rh, rw = o["rect"]
                a = I[ri - lo + rh:ri - lo + rh + n] - I[ri - lo:ri - lo + n]   # 직사각형 행 구간의 열 누적
                box = a[:, o["ox_lo"] + ci + rw:o["ox_hi"] + ci + rw + 1] - a[:, o["ox_lo"] + ci:o["ox_hi"] + ci + 1]
                okr |= (box == 0).any(1)                     # 깔린 칸이 하나도 없는 직사각형 자리가 있다
            okr &= ok[y:y1]
            hit = np.flatnonzero(okr)
            if len(hit):
                return y + int(hit[0])
            y = y1

    def find(self, idx, alpha=1.0, depth=0.3):
        """조각 idx 를 놓을 자리 (방향 번호, 열, 행) — 가장 낮은 빈자리 근처에서 비용이 가장 작은 자리."""
        P = self.P
        C, Cf, K, res, r, it = P["C"], P["Cf"], P["K"], P["res"], P["r"], P["items"][idx]
        hm, Rf = it["hm"], it["Rf"]
        R = self.top + hm                                   # 시작 행은 top 이하(top 에는 반드시 빈자리가 있다)
        self._ensure(r + R + it["hb"] + 2 * r)
        G, f = self.G, self.f
        ok = np.zeros(R - hm + 1, bool)
        for o in it["oris"]:
            ok |= (sliding_window_view(f[:R], hm) >= o["rows"]).all(1)
        cand = np.flatnonzero(ok)
        y = self._skip(it, ok, int(cand[0]))
        while True:                                         # 아래부터 띠 하나씩 FFT 상관으로 빈자리를 찾는다
            nb = min(it["hb"], R - y); nv = nb - hm + 1
            FB = np.fft.rfft2(G[y:y + nb + 2 * r].astype(np.float32), s=(Rf, Cf))   # 격자 행 y−r ~ y+nb+r (float32 — 예전 판과 같은 값)
            found = []
            for oi, o in enumerate(it["oris"]):
                cM = np.fft.irfft2(FB * _kernel_fft(P, idx, oi, "M"), s=(Rf, Cf))[r:r + nv, o["ox_lo"]:o["ox_hi"] + 1]
                fr = cM < 0.5                                # 겹치는 칸 0 = 빈자리
                if fr.any():
                    found.append((oi, fr))
            if found:
                break
            y = self._skip(it, ok, int(cand[cand >= y + nv][0]))
        best = None
        if alpha == 0:                                      # 옛 방식: 가장 낮은 행, 그다음 가장 왼쪽
            for oi, fr in found:
                rr = int(np.argmax(fr.any(1))); cx = int(np.argmax(fr[rr]))
                k = (rr, cx)
                if best is None or k < best[0]:
                    best = (k, oi, it["oris"][oi]["ox_lo"] + cx, y + rr)
        else:
            wl = K + int(round(P["s"] / res)); wr = K + int(round((P["W"] - P["s"]) / res))   # 이 열 밖은 원단 밖(벽)
            ymin = min(int(np.argmax(fr.any(1))) for _, fr in found)
            lim = min(nv, ymin + 1 + int(depth * hm))
            oys = y + np.arange(lim)
            for oi, fr in found:
                o = it["oris"][oi]
                oxs = np.arange(o["ox_lo"], o["ox_hi"] + 1)
                cR = np.fft.irfft2(FB * _kernel_fft(P, idx, oi, "ring"), s=(Rf, Cf))[:lim][:, (oxs - r) % Cf]
                n = len(o["ccs"]) - 1; nr = len(o["crs"]) - 1
                wall = (o["ccs"][np.clip(wl - oxs + r, 0, n)] + o["nring"] - o["ccs"][np.clip(wr - oxs + r, 0, n)])[None, :]                     + o["crs"][np.clip(K - oys + r, 0, nr)][:, None]
                cont = np.minimum((cR + wall) / o["nring"], 1.0)
                cost = oys[:, None] * res + o["bh"] / 2 - alpha * o["bh"] * cont
                cost = np.where(fr[:lim], cost, np.inf)
                j = int(np.argmin(cost)); rr, cx = divmod(j, cost.shape[1])
                k = (float(cost[rr, cx]), cx)
                if best is None or k < best[0]:
                    best = (k, oi, o["ox_lo"] + cx, y + rr)
        return best[1], int(best[2]), int(best[3])


def _fill(P, seq, alpha=1.0, depth=0.3):
    """격자 채우기 한 번 — seq 순서로 한 장씩 «가장 낮은 빈자리 근처에서 비용이 가장 작은 자리» 에 놓는다.
      비용 = 조각 가운데 높이 − alpha × 조각 높이 × 접촉 비율(둘레 고리 중 이미 깐 조각·원단 가장자리에 닿는 몫)
      alpha = 0 이면 옛 «왼쪽 아래 채우기» 와 같다(가장 낮은 행, 그다음 가장 왼쪽).
      depth: 가장 낮은 빈자리보다 조각 높이 × depth 만큼 위까지 후보로 본다(더 잘 맞물리는 자리를 고르려고).
    반환: (격자 길이 mm, [(조각 번호, 방향 번호, 열, 행)…])"""
    L, out, _ = _fill_snap(P, seq, alpha, depth, snap_every=0)
    return L, out


def _fill_snap(P, seq, alpha, depth, start=0, state=None, prefix=(), snap_every=8):
    """_fill 과 같은 채우기 — start 번째부터 이어 깔 수 있고(state = 그 직전 판, prefix = 그때까지의 자리),
    snap_every 장마다 판을 떠 둔다 {차례: 판}. 같은 입력이면 처음부터 깐 것과 결과가 똑같다."""
    grid = _Grid.restore(P, state) if state is not None else _Grid(P)
    out, snaps = list(prefix[:start]), {}
    for k in range(start, len(seq)):
        if snap_every and k % snap_every == 0:
            snaps[k] = grid.snapshot()
        idx = seq[k]
        oi, ox, oy = grid.find(idx, alpha, depth)
        grid.put(P["items"][idx]["oris"][oi]["M"], ox, oy)
        out.append((int(idx), oi, ox, oy))
    L = max(oy * P["res"] + P["items"][idx]["oris"][oi]["bh"] for idx, oi, ox, oy in out)
    return L, out, snaps


def _neighbor(seq, rng):
    """지역 개선 한 걸음 — 비슷한 차례의 둘 맞바꾸기, 또는 뒤쪽 한 장을 앞으로 당기기(작은 조각이 큰 조각 사이 빈자리에 먼저).
    반환: (새 순서, 처음 바뀐 차례)"""
    n = len(seq); s2 = list(seq)
    if rng.random() < 0.5:
        i = int(rng.integers(n)); j = min(n - 1, max(0, i + int(rng.integers(-8, 9))))
        s2[i], s2[j] = s2[j], s2[i]
        return s2, min(i, j)
    i = int(rng.integers(n // 3, n)); j = int(rng.integers(0, i + 1))
    s2.insert(j, s2.pop(i))
    return s2, j


def _climb(P, seq, alpha, depth, seed, steps):
    """언덕 오르기 — seq 에서 시작해 이웃 순서를 steps 번 깔아 보고, 길이가 같거나 짧으면 옮겨 간다.
    바뀐 차례 앞부분은 떠 둔 판에서 이어 깔아 시간을 아낀다. 반환: (격자 길이, 순서, 자리)"""
    rng = np.random.default_rng(seed)
    L, out, snaps = _fill_snap(P, seq, alpha, depth)
    for _ in range(steps):
        s2, j = _neighbor(seq, rng)
        k0 = max(k for k in snaps if k <= j)
        L2, out2, sn2 = _fill_snap(P, s2, alpha, depth, start=k0, state=snaps[k0], prefix=out)
        if L2 <= L + 1e-9:
            seq, L, out = s2, L2, out2
            snaps = {k: v for k, v in snaps.items() if k <= k0}; snaps.update(sn2)
    return L, seq, out


def _lns_tail(P, out, seed, steps, alpha=1.0, depth=0.3, lo=600.0, hi=5000.0):
    """끝부분 다시 깔기(부수고 다시 짓기) — 마커 길이는 맨 끝 조각이 정한다. 끝에서 T(0.6~5m, 무작위) 안에 시작하는
    조각을 모두 빼고, 순서·배치 기준을 바꿔 다시 깐다. 길이가 같거나 짧아지면 받아들인다. 반환: (격자 길이, 자리)"""
    rng = np.random.default_rng(seed)
    res, items = P["res"], P["items"]
    top_of = lambda e: e[3] * res + items[e[0]]["oris"][e[1]]["bh"]
    # 견주는 값: (길이, 끝 1m 안에 걸친 조각 면적×높이 합) — 길이가 같으면 끝이 더 «낮게» 쌓인 쪽(다음 걸음에서 길이를 줄이기 쉽다)
    score = lambda o, L: (L, sum(items[e[0]]["area"] * max(0.0, top_of(e) - (L - 1000.0)) for e in o))
    L = max(top_of(e) for e in out); S = score(out, L)
    for _ in range(steps):
        cut = L - float(rng.uniform(lo, hi))
        keep = [e for e in out if e[3] * res < cut]
        tail = [e[0] for e in out if e[3] * res >= cut]
        if len(tail) < 2:
            continue
        grid = _Grid(P, rows=int(L / res) + 2)
        for idx, oi, ox, oy in keep:
            grid.put(items[idx]["oris"][oi]["M"], ox, oy)
        if rng.random() < 0.5:                               # 원래 깐 순서에서 한두 걸음만 바꾸기
            order = list(tail)
            for _ in range(1 + int(rng.integers(3))):
                order, _j = _neighbor(order, rng)
            a, d = alpha, depth
        else:                                                # 크기 순서를 크게 섞고 배치 기준도 바꾸기
            key = np.array([items[i]["area"] for i in tail]) * np.exp(rng.normal(0, 0.3, len(tail)))
            order = [tail[k] for k in np.argsort(-key, kind="stable")]
            a, d = ([(0.0, 0.0)] + _CRIT)[int(rng.integers(len(_CRIT) + 1))]
        new = list(keep)
        for idx in order:
            oi, ox, oy = grid.find(idx, a, d)
            grid.put(items[idx]["oris"][oi]["M"], ox, oy)
            new.append((int(idx), oi, ox, oy))
        L2 = max(top_of(e) for e in new); S2 = score(new, L2)
        if S2 <= S:
            out, L, S = new, L2, S2
    return L, out


def _raster(P, g):
    """정확한 자리에 놓인 도형 → (열, 행, 칸 묶음). 격자에 맞지 않는 자리여도 «부풀린 도형이 칸 안에 든다» 가 그대로 성립한다."""
    res, K, m = P["res"], P["K"], P["m"]
    x0, y0, x1, y1 = g.bounds
    c0 = int(math.floor((x0 - m) / res + K - 0.5)); c1 = int(math.ceil((x1 + m) / res + K - 0.5))
    r0 = int(math.floor((y0 - m) / res + K - 0.5)); r1 = int(math.ceil((y1 + m) / res + K - 0.5))
    buf = g.buffer(m); shapely.prepare(buf)
    X, Y = np.meshgrid((np.arange(c0, c1 + 1) - K + 0.5) * res, (np.arange(r0, r1 + 1) - K + 0.5) * res)
    return c0, r0, shapely.contains_xy(buf, X, Y).astype(np.float32)


def _reinsert(P, placed, passes=4, share=6):
    """빼고 다시 넣기 — 압축으로 생긴 빈자리에, 마커 끝(위)에 걸린 조각을 하나씩 빼서 가장 낮은 자리로 다시 넣는다.
    다시 넣은 자리가 원래보다 낮을 때만 옮긴다. 옮긴 조각 수를 돌려준다."""
    res = P["res"]
    L0 = max(q["geom"].bounds[3] for q in placed)
    grid = _Grid(P, rows=int(L0 / res) + 2)
    cells = []
    for q in placed:
        c0, r0, Mq = _raster(P, q["geom"]); grid.put(Mq, c0, r0); cells.append((c0, r0, Mq))
    moved = 0
    for _ in range(passes):
        tops = [q["geom"].bounds[3] for q in placed]
        cand = sorted(range(len(placed)), key=lambda i: -tops[i])[:max(8, len(placed) // share)]
        n0 = moved
        for i in cand:
            q = placed[i]; c0, r0, Mq = cells[i]
            grid.put(Mq, c0, r0, -1.0)
            idx = q["it"]["i"]
            oi, ox, oy = grid.find(idx, alpha=0.0, depth=0.0)
            o = P["items"][idx]["oris"][oi]
            if oy * res + o["bh"] < q["geom"].bounds[3] - 0.5:            # 더 낮은 자리 — 옮긴다
                X0, Y0 = ox * res, oy * res
                q.update({"o": o, "geom": translate(o["g"], X0, Y0), "dx": X0 - o["x0"], "dy": Y0 - o["y0"]})
                cells[i] = (ox, oy, o["M"]); moved += 1
            grid.put(cells[i][2], cells[i][0], cells[i][1])
        if moved == n0:
            break
    return moved


def _finish(P, out, compact=True, reinsert=True):
    """격자 자리 → 정확한 도형 → 아래·왼쪽 압축 → (끝에 걸린 조각 빼고 다시 넣기 → 다시 압축) → 검산 → 결과 dict."""
    res, W, s, gap = P["res"], P["W"], P["s"], P["gap"]
    placed = []
    for idx, oi, ox, oy in out:
        it = P["items"][idx]; o = it["oris"][oi]
        X0, Y0 = ox * res, oy * res
        placed.append({"it": it, "o": o, "geom": translate(o["g"], X0, Y0), "dx": X0 - o["x0"], "dy": Y0 - o["y0"]})
    moved = _compact(placed, W, s, gap) if compact else 0.0
    n_re = 0
    if compact and reinsert:
        for _ in range(3):                                  # 다시 넣기 → 압축이 또 자리를 만들면 한 번 더
            k = _reinsert(P, placed)
            if k == 0:
                break
            n_re += k
            moved += _compact(placed, W, s, gap)
    L = max(q["geom"].bounds[3] for q in placed)
    area = sum(q["geom"].area for q in placed)
    chk = check_layout([q["geom"] for q in placed], W, gap, s)
    rows = []
    for q in placed:
        p, o = q["it"]["p"], q["o"]
        rows.append({"id": p["id"], "name": p["name"], "base": p.get("base", p["name"]), "size": p["size"],
                     "bundle": p.get("bundle", 1), "side": p.get("side", ""), "rot": o["rot"], "flip": o["flip"],
                     "sx": o["sx"], "sy": o["sy"], "dx": q["dx"], "dy": q["dy"], "area": q["geom"].area,
                     "parts": [list(g.exterior.coords)[:-1] for g in _polys(q["geom"])], "geom": q["geom"]})
    return {"width_mm": W, "gap_mm": gap, "res_mm": res, "selvage_mm": s, "rotations": P["rotations"],
            "allow_flip": P["allow_flip"], "length_mm": L, "piece_area_mm2": area, "efficiency_pct": 100 * area / (W * L),
            "piece_count": len(rows), "check": chk, "compact_moved_mm": round(moved, 1), "reinserted": n_re, "placements": rows}


def _order_seq(P, order="area", noise=0.0, seed=0):
    """깔 순서 — 큰 것부터(면적·높이·폭 중 하나). noise > 0 이면 크기에 무작위 배율 exp(N(0,noise)) 을 곱해 살짝 섞는다(시드 고정)."""
    items = P["items"]
    v = np.array([{"area": it["area"], "height": it["oris"][0]["bh"], "width": it["oris"][0]["bw"]}[order] for it in items])
    if noise > 0:
        v = v * np.exp(np.random.default_rng(seed).normal(0, noise, len(v)))
    return [it["i"] for _, it in sorted(zip(-v, items), key=lambda t: (t[0], -t[1]["area"], t[1]["p"]["id"]))]


def make_marker(pieces, width_mm=1500.0, gap_mm=3.0, res_mm=4.0, rotations=(0, 180), allow_flip=False,
                selvage_mm=0.0, order="area", compact=True, alpha=1.0, depth=0.3, noise=0.0, seed=0, cache_mb=None):
    """pieces: [{id, name, size, side, cut:[(x,y)…] (y = 식서), flip:'금지'|'허용'}] → 배치 결과 dict (한 번 깔기).
    alpha=0 · depth=0 이면 옛 «왼쪽 아래 채우기»."""
    t0 = time.perf_counter()
    P = _prepare(pieces, width_mm, gap_mm, res_mm, rotations, allow_flip, selvage_mm, cache_mb=cache_mb)
    seq = _order_seq(P, order, noise, seed)
    _, out = _fill(P, seq, alpha, depth)
    t_fill = time.perf_counter() - t0
    R = _finish(P, out, compact)
    R.update({"order": order, "alpha": alpha, "depth": depth, "noise": noise, "seed": seed,
              "seconds": round(time.perf_counter() - t0, 2), "seconds_fill": round(t_fill, 2)})
    return R


def _compact(placed, W, s, gap):
    """격자 때문에 생긴 틈 메우기 — 아래 조각부터 정확한 도형으로 아래·왼쪽으로 조금씩 민다(간격 ≥ gap 유지).
    한 바퀴에 움직인 게 없을 때까지(최대 4바퀴) — 왼쪽으로 가면 또 내려갈 자리가 생긴다."""
    geoms = [q["geom"] for q in placed]
    B = np.array([g.bounds for g in geoms])
    arr = np.array(geoms, dtype=object)
    total = 0.0

    def ok(i, g):
        x0, y0, x1, y1 = g.bounds
        if y0 < -1e-9 or x0 < s - 1e-9 or x1 > W - s + 1e-9:
            return False
        near = np.nonzero((B[:, 0] < x1 + gap) & (B[:, 2] > x0 - gap) & (B[:, 1] < y1 + gap) & (B[:, 3] > y0 - gap))[0]
        near = near[near != i]
        if len(near) == 0:
            return True
        return bool(np.all(shapely.distance(g, arr[near]) >= gap))

    for _ in range(4):
        before = total
        for i in sorted(range(len(geoms)), key=lambda i: B[i, 1]):
            for dx, dy in ((0, -1), (-1, 0), (0, -1)):
                for step in (4.0, 2.0, 1.0, 0.5, 0.25):
                    while True:
                        g = translate(geoms[i], dx * step, dy * step)
                        if not ok(i, g):
                            break
                        geoms[i] = g; arr[i] = g; B[i] = g.bounds; total += step
                        placed[i]["dx"] += dx * step; placed[i]["dy"] += dy * step
        if total - before < 1.0:
            break
    for q, g in zip(placed, geoms):
        q["geom"] = g
    return total


def check_layout(geoms, W, gap, selvage=0.0):
    """검산 — 모든 조각 쌍의 실제 거리·겹침 넓이, 원단 폭 밖으로 나간 조각."""
    n = len(geoms); B = np.array([g.bounds for g in geoms]); arr = np.array(geoms, dtype=object)
    min_gap, overlaps = float("inf"), []
    for i in range(n):
        x0, y0, x1, y1 = B[i]
        j = np.nonzero((B[:, 0] < x1 + 3 * gap) & (B[:, 2] > x0 - 3 * gap) & (B[:, 1] < y1 + 3 * gap) & (B[:, 3] > y0 - 3 * gap))[0]
        j = j[j > i]
        if len(j):
            d = shapely.distance(geoms[i], arr[j])
            min_gap = min(min_gap, float(d.min()))
            for jj in j[d < 1e-9]:
                a = geoms[i].intersection(geoms[jj]).area
                if a > 0:
                    overlaps.append([i, int(jj), a])
    outside = [i for i in range(n) if B[i, 0] < selvage - 1e-6 or B[i, 2] > W - selvage + 1e-6 or B[i, 1] < -1e-6]
    return {"min_gap_mm": round(min_gap, 3) if min_gap != float("inf") else None, "overlaps": overlaps, "outside": outside}


def best_marker(pieces, orders=("area",), **kw):
    """여러 깔 순서로 깔아 보고 가장 짧은 마커를 고른다(같은 조각, 같은 규칙)."""
    best, tried = None, []
    for o in orders:
        r = make_marker(pieces, order=o, **kw)
        tried.append({"order": o, "length_m": round(r["length_mm"] / 1000, 3),
                      "efficiency_pct": round(r["efficiency_pct"], 2), "seconds": r["seconds"]})
        if best is None or r["length_mm"] < best["length_mm"]:
            best = r
    best["tried"] = tried
    return best


_WK = {}


def _wk_init(pieces, kw):
    """병렬 일꾼 준비 — 조각 칸을 일꾼마다 한 번 만든다(Windows 는 새 프로세스라 넘겨받지 못한다)."""
    _WK["P"] = _prepare(pieces, **kw)


def _wk_fill(job):
    seq, alpha, depth = job
    return _fill(_WK["P"], seq, alpha, depth)


def _wk_climb(job):
    return _climb(_WK["P"], *job)


def _wk_lns(job):
    return _lns_tail(_WK["P"], *job)


def _wk_finish(job):
    out, compact = job
    return _finish(_WK["P"], out, compact)


class _Runner:
    """배치를 여러 개 돌리는 창구 — jobs > 1 이면 프로세스 여러 개로 나눠 돌린다.
    결과는 일꾼 수와 무관하게 같다(같은 입력 → 같은 계산, 순서는 map 이 지킨다)."""

    def __init__(self, P, pieces, kw, jobs):
        self.P, self.pool = P, None
        if jobs > 1:
            from concurrent.futures import ProcessPoolExecutor
            self.pool = ProcessPoolExecutor(max_workers=jobs, initializer=_wk_init, initargs=(pieces, kw))

    def fill(self, jobs_list):
        if self.pool is None:
            return [_fill(self.P, *j) for j in jobs_list]
        return list(self.pool.map(_wk_fill, jobs_list))

    def climb(self, jobs_list):
        if self.pool is None:
            return [_climb(self.P, *j) for j in jobs_list]
        return list(self.pool.map(_wk_climb, jobs_list))

    def lns(self, jobs_list):
        if self.pool is None:
            return [_lns_tail(self.P, *j) for j in jobs_list]
        return list(self.pool.map(_wk_lns, jobs_list))

    def finish(self, outs, compact):
        if self.pool is None:
            return [_finish(self.P, o, compact) for o in outs]
        return list(self.pool.map(_wk_finish, [(o, compact) for o in outs]))

    def close(self):
        if self.pool is not None:
            self.pool.shutdown()


_CRIT = [(0.5, 0.3), (1.0, 0.3), (1.5, 0.7), (2.0, 0.3)]           # 접촉 점수 (세기 alpha, 후보 깊이 depth)


def default_jobs():
    """병렬 일꾼 수 기본값 — 논리 코어 절반, 최대 8(일꾼마다 FFT 기억 공간을 따로 쓴다)."""
    return max(1, min(8, (os.cpu_count() or 2) // 2))


def search_marker(pieces, width_mm=1500.0, gap_mm=3.0, res_mm=2.0, rotations=(0, 180), allow_flip=False,
                  selvage_mm=0.0, seed=0, jobs=None, explore_rounds=1, chains=8, steps=4, lns_rounds=3, lns_steps=8,
                  finalists=4, time_budget=165.0, compact=True, log=None, cache_mb=None):
    """여러 번 깔아 보고 가장 짧은 마커를 고른다 — 같은 조각, 같은 규칙(겹침·간격·폭·식서 0°/180°).
      ① 옛 방식(면적순·왼쪽 아래) — 비교 기준
      ② 정해 둔 조합 14가지: 깔 순서(면적·높이·폭) × 배치 기준(왼쪽 아래 / 접촉 점수 4가지)
      ③·④ explore_rounds 번 되풀이:
           ③ 무작위 섞기 16번 — 크기 순서에 작은 무작위 배율을 곱해 섞고 배치 기준도 고른다
           ④ 지역 개선 — 지금까지 가장 짧은 순서에서 언덕 오르기 chains 줄 × steps 걸음
              (비슷한 차례 둘 맞바꾸기 · 뒤쪽 한 장을 앞으로 당겨 큰 조각 사이 빈자리에 먼저 넣기)
      ⑤ 끝부분 다시 깔기 lns_rounds 번 — 마커 끝 0.6~5m 안에서 시작하는 조각을 빼고 순서·기준을 바꿔 다시 깐다
         (chains 줄 × lns_steps 걸음, 가장 짧은 것에서 다음 번을 잇는다)
      ⑥ 격자 길이 상위 finalists 개를 정확한 도형으로 압축 + 끝 조각 빼고 다시 넣기 → 실제로 가장 짧은 것
    재현: 같은 seed 면 같은 결과 — 일꾼 수(jobs)와 무관. time_budget(초)은 «벽시계 전체»(조각 준비·①②·⑥ 포함) 안전장치로,
    깔기·마무리 한 묶음 앞마다 «다음 묶음이 넘길 것 같으면» 멈추고 그때까지의 최선을 낸다. 꼭 하는 것은 ① 한 번 + ⑥ 한 묶음뿐
    (그래서 최소 시간 ≈ --quick 한 번). 한도에 걸렸을 때만 결과가 기계 속도에 따라 달라진다 → 결과의 time_budget_hit."""
    t0 = time.perf_counter()
    jobs = default_jobs() if jobs is None else max(1, int(jobs))
    kw = dict(width_mm=width_mm, gap_mm=gap_mm, res_mm=res_mm, rotations=rotations, allow_flip=allow_flip, selvage_mm=selvage_mm,
              cache_mb=cache_mb_of(cache_mb))                      # 일꾼에게도 같은 한도(환경변수는 여기서 한 번 읽는다)
    P = _prepare(pieces, **kw)
    rng = np.random.default_rng(seed)
    pool, stages, n_eval, hit = [], [], [0], [False]        # pool: (격자 길이, 차례, 순서, alpha, depth, 이름, 배치)
    runner = _Runner(P, pieces, kw, jobs)
    say = log or (lambda *_: None)

    last = [0.0]                                            # 바로 앞 한 묶음에 걸린 시간 — 다음 묶음이 한도를 넘을 것 같으면 멈춘다
    fill_s = [0.0]                                          # 깔기 한 번에 걸린 시간(일꾼 하나 기준) — ⑥ 마무리 몫을 남겨 두려고
    last_fin = [0.0]                                        # ⑥ 마무리 한 묶음에 걸린 시간

    def left(need=None):
        # need: 다음 묶음이 걸릴 것 같은 시간(없으면 바로 앞 묶음 시간). ⑥ 마무리(후보 finalists 개 압축·다시 넣기)는
        #   깔기 한 번의 약 1.5배 × 일꾼마다 맡는 개수 — 그 몫도 남긴다
        reserve = 1.5 * fill_s[0] * math.ceil(finalists / jobs)
        if time.perf_counter() - t0 + (last[0] if need is None else need) + reserve < time_budget:
            return True
        hit[0] = True
        return False

    def note(name, k, t_start):
        n_eval[0] += k; last[0] = time.perf_counter() - t_start
        b = min(pool)
        st = next((x for x in stages if x["stage"] == name), None)
        if st is None:
            st = {"stage": name, "tries": 0}; stages.append(st)
        st.update({"tries": st["tries"] + k, "best_grid_length_m": round(b[0] / 1000, 3), "after_s": round(time.perf_counter() - t0, 1)})
        say(f"  {name}: 깔기 {n_eval[0]}번 · 가장 짧은 격자 길이 {b[0] / 1000:.3f} m · {time.perf_counter() - t0:.0f}초")

    def run(cfgs, name):
        # 일꾼 수만큼씩 끊어 깐다 — 한 묶음 앞에서마다 시간 한도를 본다(2026-10-20: 예전엔 ①② 를 한도 밖에서 통째로 돌려
        #   일꾼 1명이면 ②만 60초 넘게 걸려도 못 멈췄다). 맨 처음 한 번(①)은 반드시 깐다 — 낼 결과가 하나는 있어야 한다.
        #   한도에 안 걸리면 예전과 같은 순서·같은 깔기라 결과가 같다.
        for k in range(0, len(cfgs), jobs):
            chunk = cfgs[k:k + jobs]
            if pool and not left():
                return
            ts = time.perf_counter()
            outs = runner.fill([(c["seq"], c["alpha"], c["depth"]) for c in chunk])
            for c, (Lg, out) in zip(chunk, outs):
                pool.append((Lg, len(pool), c["seq"], c["alpha"], c["depth"], c["tag"], out))
            note(name, len(chunk), ts)
            fill_s[0] = max(fill_s[0], last[0])

    def random_cfg():
        o = ["area", "height", "width"][int(rng.integers(3))]; a, d = _CRIT[int(rng.integers(len(_CRIT)))]
        nz = [0.1, 0.2, 0.3][int(rng.integers(3))]; sd = int(rng.integers(2 ** 31))
        return {"seq": _order_seq(P, o, nz, sd), "alpha": a, "depth": d, "tag": f"{o}·a{a}·d{d}·섞기{nz}#{sd}"}

    def climb():
        # 일꾼 수만큼씩 줄을 나눠 돈다 — 묶음 앞마다 «한 줄 = 깔기 steps+1 번» 이 한도 안인지 본다(2026-10-20 재리뷰:
        #   통째로 돌리면 2벌·한도 60초에 73.6초). 씨앗은 예전처럼 한꺼번에 뽑아 두어 한도에 안 걸리면 결과가 같다
        b = min(pool)
        seeds = [int(rng.integers(2 ** 31)) for _ in range(chains)]
        tag = b[5].split(" +")[0] + " +개선"
        per = [None]                                        # 한 묶음 실측(첫 묶음 전엔 깔기 × (steps+1) 로 어림)
        for k in range(0, len(seeds), jobs):
            if not left(per[0] if per[0] is not None else fill_s[0] * (steps + 1)):
                return
            ts = time.perf_counter()
            res = runner.climb([(b[2], b[3], b[4], sd, steps) for sd in seeds[k:k + jobs]])
            for Lg, seq, out in res:
                pool.append((Lg, len(pool), seq, b[3], b[4], tag, out))
            note("④ 지역 개선(언덕 오르기)", len(res) * (steps + 1), ts)
            per[0] = last[0]

    try:
        # ⓪ 맨 먼저 «빠르게(--quick)» 와 같은 깔기(면적순·a1.0·d0.3) — 시간 한도에 일찍 걸려도 빠르게보다 나빠지지 않게(2026-10-20 실측:
        #    예전엔 ①(옛 방식)만 깔고 멈춰 상의 24벌 36.95m 로 빠르게 35.77m 보다 길었다). 깔아 보는 조합 묶음은 예전과 같고 순서만 다르다
        run([{"seq": _order_seq(P, "area"), "alpha": 1.0, "depth": 0.3, "tag": "area·a1.0·d0.3"}], "⓪ 빠르게와 같은 깔기")
        run([{"seq": _order_seq(P, "area"), "alpha": 0.0, "depth": 0.0, "tag": "area·왼쪽아래(옛 방식)"}], "① 옛 방식(면적순·왼쪽 아래)")
        combos = [(o, a, d) for o in ("area", "height", "width") for a, d in [(0.0, 0.0)] + _CRIT
                  if (o, a) != ("area", 0.0) and (o, a, d) != ("area", 1.0, 0.3)]
        run([{"seq": _order_seq(P, o), "alpha": a, "depth": d, "tag": f"{o}·a{a}·d{d}"} for o, a, d in combos],
            "② 깔 순서 × 접촉 점수")
        for _ in range(explore_rounds):
            if left():
                run([random_cfg() for _ in range(16)], "③ 무작위 섞기")
            if steps and left():
                climb()
        per_lns = None                                       # ⑤ 한 묶음 실측(첫 묶음 전엔 깔기 × lns_steps 로 어림 — 끝만 다시 까니 넉넉한 쪽)
        for _ in range(lns_rounds):                          # ⑤ 끝부분 다시 깔기 — 일꾼 수만큼씩, 묶음 앞마다 한도 확인
            if hit[0]:
                break
            b = min(pool)
            seeds = [int(rng.integers(2 ** 31)) for _ in range(chains)]
            for k in range(0, len(seeds), jobs):
                if not left(per_lns if per_lns is not None else fill_s[0] * lns_steps):
                    break
                ts = time.perf_counter()
                res = runner.lns([(b[6], sd, lns_steps, b[3], b[4]) for sd in seeds[k:k + jobs]])
                for Lg, out in res:
                    pool.append((Lg, len(pool), None, b[3], b[4], b[5].split(" +")[0] + " +끝 다시 깔기", out))
                note("⑤ 끝부분 다시 깔기(빼고 다시 짓기)", len(res) * lns_steps, ts)
                per_lns = last[0]
        # ⑥ 격자 길이 상위 몇 개를 정확한 도형으로 → 압축 + 빼고 다시 넣기
        #   일꾼 수만큼씩 — 첫 묶음은 반드시, 다음 묶음은 «지난 묶음만큼 더 걸려도 한도 안» 일 때만(벽시계 전체를 지킨다)
        cand = sorted(pool)[:finalists]
        top, Rs = [], []
        for k in range(0, len(cand), jobs):
            chunk = cand[k:k + jobs]
            if Rs and time.perf_counter() - t0 + last_fin[0] >= time_budget:
                hit[0] = True
                break
            ts = time.perf_counter()
            Rs += runner.finish([x[6] for x in chunk], compact)
            top += chunk
            last_fin[0] = time.perf_counter() - ts
    finally:
        runner.close()
    best = None
    for x, R in zip(top, Rs):
        if best is None or R["length_mm"] < best[1]["length_mm"] - 1e-9:
            best = (x, R)
    x, R = best
    stages.append({"stage": "⑥ 정확한 도형 압축·빼고 다시 넣기", "tries": len(top), "length_m": round(R["length_mm"] / 1000, 3),
                   "efficiency_pct": round(R["efficiency_pct"], 2), "after_s": round(time.perf_counter() - t0, 1)})
    R.update({"finalists": [{"order": y[5], "grid_length_mm": y[0], "length_mm": Q["length_mm"]} for y, Q in zip(top, Rs)],
              "grid_places": x[6], "order": x[5], "alpha": x[3], "depth": x[4], "stages": stages, "tries": n_eval[0], "seed": seed, "jobs": jobs,
              "time_budget_hit": hit[0], "seconds": round(time.perf_counter() - t0, 2),
              "tried": [{"order": y[5], "grid_length_m": round(y[0] / 1000, 3)} for y in sorted(pool)[:10]]})
    return R


def summarize(r, bundles, counts=None, title=""):
    """JSON 요약 — 마커 길이(m) · 벌당 요척(m) · 효율(%)."""
    L = r["length_mm"] / 1000
    return {"title": title, "fabric_width_cm": r["width_mm"] / 10, "gap_mm": r["gap_mm"], "grid_mm": r["res_mm"],
            "selvage_mm": r["selvage_mm"], "rotations": r["rotations"], "allow_flip": r["allow_flip"],
            "counts": counts, "bundles": bundles, "piece_count": r["piece_count"],
            "length_m": round(L, 3), "yield_m_per_bundle": round(L / bundles, 3) if bundles else None,
            "efficiency_pct": round(r["efficiency_pct"], 2),
            "piece_area_m2": round(r["piece_area_mm2"] / 1e6, 3), "fabric_area_m2": round(r["width_mm"] * r["length_mm"] / 1e6, 3),
            "check": r["check"], "order": r["order"], "tried": r.get("tried"),
            "search": {k: r[k] for k in ("stages", "tries", "seed", "jobs", "time_budget_hit", "alpha", "depth") if k in r},
            "compact_moved_mm": r["compact_moved_mm"], "reinserted": r.get("reinserted", 0), "seconds": r["seconds"],
            "placements": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in q.items() if k not in ("geom", "parts")}
                           for q in r["placements"]]}


# ════════════════ 내보내기 ════════════════
_PAL = [(0.85, 0.33, 0.10), (0.00, 0.45, 0.70), (0.00, 0.62, 0.45), (0.80, 0.47, 0.65),
        (0.90, 0.62, 0.00), (0.34, 0.71, 0.91), (0.55, 0.35, 0.20), (0.40, 0.40, 0.40)]


def _color(size):
    return _PAL[SIZES.index(size) % len(_PAL)] if size in SIZES else _PAL[-1]


def _label_pt(g):
    big = max(_polys(g), key=lambda q: q.area)
    a = polylabel(big, tolerance=1.0)
    return a.x, a.y


def export_pdf(r, path, title, legend=()):
    """1:1 PDF — 원단 시작(0 m)이 첫 쪽 아래. 5m 를 넘으면 쪽을 나눈다(PDF 한 쪽 최대 200인치). 조각은 뒤집지 않고 그대로(거울 없음)."""
    import fitz
    PT = 72 / 25.4; MG = 40.0; HEAD = 70.0
    W, L = r["width_mm"], r["length_mm"]
    n_pages = max(1, int(math.ceil(L / PDF_MAX_MM)))
    seg = L / n_pages
    pdf = fitz.open(); font = fitz.Font(fontfile=FONT)
    for k in range(n_pages):
        a, b = k * seg, (k + 1) * seg
        pw, ph = W + 2 * MG, seg + 2 * MG + HEAD
        page = pdf.new_page(width=pw * PT, height=ph * PT)
        T = lambda x, y: fitz.Point((MG + x) * PT, (HEAD + MG + (b - y)) * PT)       # y 위로(+) 그대로 → 거울 없음
        for q in r["placements"]:
            x0, y0, x1, y1 = q["geom"].bounds
            if y1 < a - 1 or y0 > b + 1:
                continue
            sh = page.new_shape()
            for ring in q["parts"]:
                sh.draw_polyline([T(x, y) for x, y in ring])
                sh.finish(color=(0, 0, 0), fill=_color(q["size"]), fill_opacity=0.12, width=0.8, closePath=True)
            cx, cy = _label_pt(q["geom"])
            gl = min(0.5 * (y1 - y0), 200.0)                                       # 식서 화살표(세로)
            sh.draw_line(T(cx, cy - gl / 2), T(cx, cy + gl / 2))
            for e in (-1, 1):
                tip = cy + e * gl / 2
                sh.draw_line(T(cx, tip), T(cx - 4, tip - e * 8)); sh.draw_line(T(cx, tip), T(cx + 4, tip - e * 8))
            sh.finish(color=(0.2, 0.2, 0.2), width=0.5); sh.commit()
            for i, t in enumerate([f"{q['size']} {q['name']}", f"{q['rot']}°" + (" 뒤집음" if q["flip"] else "")]):
                fs = 11 if i == 0 else 8
                page.insert_text(T(cx + 6, cy + 4 - i * 12), t, fontsize=fs, fontname="malgun", fontfile=FONT, color=(0.1, 0.1, 0.1))
        # 이 쪽 구간 밖으로 삐져나온 조각(다음 쪽과 걸친 조각)은 흰 띠로 덮는다 — 머리글·여백과 겹치지 않게
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(0, 0, pw * PT, (HEAD + MG) * PT)); sh.draw_rect(fitz.Rect(0, (HEAD + MG + seg) * PT, pw * PT, ph * PT))
        sh.finish(color=None, fill=(1, 1, 1), width=0); sh.commit()
        sh = page.new_shape()                                                      # 원단 테두리(이 쪽 구간)
        sh.draw_rect(fitz.Rect(T(0, b), T(W, a))); sh.finish(color=(0.6, 0.6, 0.6), width=0.6, dashes="[4 3] 0"); sh.commit()
        # 1m 눈금(원단 왼쪽 가장자리)
        for mtr in range(int(a // 1000), int(b // 1000) + 1):
            y = mtr * 1000.0
            if a - 1e-6 <= y <= b + 1e-6:
                sh = page.new_shape(); sh.draw_line(T(-25, y), T(0, y)); sh.finish(color=(0.8, 0, 0), width=0.8); sh.commit()
                page.insert_text(T(-38, y + 3), f"{mtr} m", fontsize=9, fontname="malgun", fontfile=FONT, color=(0.8, 0, 0))
        page.insert_text(fitz.Point(MG * PT, 22 * PT), f"{title}  ({k + 1}/{n_pages}쪽 · {a / 1000:.2f}~{b / 1000:.2f} m)",
                         fontsize=14, fontname="malgun", fontfile=FONT)
        for i, t in enumerate(legend):
            page.insert_text(fitz.Point(MG * PT, (36 + i * 11) * PT), t, fontsize=9, fontname="malgun", fontfile=FONT)
        sh = page.new_shape()                                                      # 100mm 자
        sh.draw_line(fitz.Point((pw - MG - 100) * PT, 30 * PT), fitz.Point((pw - MG) * PT, 30 * PT)); sh.finish(color=(0, 0, 0), width=0.8); sh.commit()
        page.insert_text(fitz.Point((pw - MG - 65) * PT, 44 * PT), "100 mm", fontsize=9, fontname="malgun", fontfile=FONT)
        page.insert_text(T(W / 2 - 40, a - 22), "▼ 원단 시작 쪽" if k == 0 else "▼ 앞 쪽에서 이어짐", fontsize=9, fontname="malgun", fontfile=FONT)
    pdf.set_metadata({"title": title, "creator": "STIZ pattern-engine marker.py", "subject": "마커 1:1 mm"})
    pdf.subset_fonts(); pdf.save(path, garbage=3, deflate=True)
    return n_pages


def export_png(r, path, title="", px_per_mm=0.2):
    """축소 미리보기 — 원단 길이를 가로로 눕혀 그린다(회전이지 거울이 아니다: 마커 (x,y) → 그림 (y, W−x))."""
    from PIL import Image, ImageDraw, ImageFont
    W, L = r["width_mm"], r["length_mm"]; P = 30
    sc = px_per_mm
    img = Image.new("RGB", (int(L * sc) + 2 * P, int(W * sc) + 2 * P + 30), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 11); ft = ImageFont.truetype(FONT, 14)
    U = lambda x, y: (P + y * sc, P + 30 + (W - x) * sc)
    d.rectangle([U(W, 0), U(0, L)], outline=(150, 150, 150))
    for q in r["placements"]:
        c = tuple(int(255 * (0.75 + 0.25 * v)) for v in _color(q["size"]))
        oc = tuple(int(255 * v) for v in _color(q["size"]))
        for ring in q["parts"]:
            d.polygon([U(x, y) for x, y in ring], fill=c, outline=oc)
        cx, cy = _label_pt(q["geom"])
        d.text(U(cx, cy), q["size"], fill=(0, 0, 0), font=f, anchor="mm")
    for mtr in range(int(L // 1000) + 1):
        u, v = U(0, mtr * 1000.0)
        d.line([(u, v), (u, v + 8)], fill=(200, 0, 0)); d.text((u + 2, v + 8), f"{mtr}m", fill=(200, 0, 0), font=f)
    d.text((P, 6), title, fill=(0, 0, 0), font=ft)
    img.save(path)


_EN = {"뒤판": "BACK", "앞판": "FRONT", "소매": "SLEEVE", "소매중심덧방": "SLEEVE OVERLAY", "카우스": "CUFF RIB", "밑단립": "HEM RIB",
       "에리(립)": "COLLAR RIB", "앞주머니구찌": "POCKET FACING", "앞주머니감": "POCKET BAG", "앞옆배색": "FRONT SIDE PANEL",
       "뒤옆배색": "BACK SIDE PANEL", "앞구찌": "POCKET FACING"}


def export_dxf(r, path):
    """DXF R2000 — 조각 경계 = 레이어 1 · 식서 = 레이어 7 · 원단 테두리 = FABRIC · 글자 = TEXT(영문 — 공장 CAD 호환).
    R12 는 단위를 적을 칸이 없어 CAD 가 «단위 없음» 경고를 냈다 → R2000 으로 저장하고 $INSUNITS = 4(mm) 를 적는다."""
    import ezdxf
    doc = ezdxf.new("R2000"); msp = doc.modelspace()
    doc.units = ezdxf.units.MM                                       # $INSUNITS = 4 (밀리미터)
    doc.header["$MEASUREMENT"] = 1                                   # 미터법
    for name, c in (("1", 7), ("7", 3), ("FABRIC", 8), ("TEXT", 2)):
        doc.layers.add(name, color=c, linetype="Continuous")
    W, L = r["width_mm"], r["length_mm"]
    msp.add_polyline2d([(0, 0), (W, 0), (W, L), (0, L)], close=True, dxfattribs={"layer": "FABRIC"})
    for q in r["placements"]:
        for ring in q["parts"]:
            msp.add_polyline2d(ring, close=True, dxfattribs={"layer": "1"})
        x0, y0, x1, y1 = q["geom"].bounds
        cx, cy = _label_pt(q["geom"]); gl = min(0.5 * (y1 - y0), 200.0)
        msp.add_line((cx, cy - gl / 2), (cx, cy + gl / 2), dxfattribs={"layer": "7"})
        suf = q["name"].split(" ")[-1] if " " in q["name"] else ""
        t = f"{q['size']} {_EN.get(q['base'], 'PIECE')}" + (f" {suf}" if suf else "") + f" ROT{q['rot']}"
        msp.add_text(t, dxfattribs={"layer": "TEXT", "height": 8}).set_placement((cx + 6, cy), align=ezdxf.enums.TextEntityAlignment.LEFT)
    msp.reset_extents((0, 0, 0), (W, L, 0))
    doc.saveas(path)


# ════════════════ 실행 ════════════════
def _parse_counts(lst):
    if not lst:
        return {s: 1 for s in SIZES}
    out = {}
    for t in lst:
        k, _, v = t.partition("=")
        out[norm_size(k)] = int(v or 1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="마커(원단 배치) + 요척")
    ap.add_argument("--garment", choices=["top", "bottom", "imported"], default="top",
                    help="imported = 들여온 스타일(style_import) — graded.json 의 «imported» 칸 + --spec-file 펼침표")
    ap.add_argument("--counts", nargs="*", help="사이즈=벌수 … (기본: S~5XL 각 1벌)")
    ap.add_argument("--width", type=float, default=150.0, help="원단 폭 cm (기본 150)")
    ap.add_argument("--gap", type=float, default=3.0, help="조각 간격 mm (기본 3)")
    ap.add_argument("--grid", type=float, default=2.0, help="격자 mm (작을수록 촘촘·느림, 기본 2)")
    ap.add_argument("--selvage", type=float, default=0.0, help="원단 양쪽 가장자리(쓰지 않는 폭) mm")
    ap.add_argument("--allow-flip", action="store_true", help="좌우 구분 없는 조각은 뒤집어도 된다(원단 겉안 같을 때)")
    ap.add_argument("--nap", action="store_true", help="원단 결(나프·광택·방향 무늬)이 있다 — 회전 0° 만(180° 돌리지 않는다)")
    ap.add_argument("--seed", type=int, default=0, help="무작위 시드(같은 시드 = 같은 결과)")
    ap.add_argument("--jobs", type=int, default=None, help="병렬 일꾼 수(기본: 논리 코어 절반·최대 8) — 결과에는 영향 없음")
    ap.add_argument("--budget", type=float, default=165.0, help="탐색 시간 안전장치(초, 기본 165 — 벽시계 전체. 넘길 것 같으면 그때까지의 최선을 낸다. 최소 = 한 번 깔기)")
    ap.add_argument("--quick", action="store_true", help="여러 번 깔지 않고 한 번만(면적순·접촉 점수) — 상의 약 12~13초·하의 약 17~18초")
    ap.add_argument("--cache-mb", type=float, default=None,
                    help="조각 FFT 기억 한도 MB(일꾼 하나당, 기본 900 또는 환경변수 PATTERN_ENGINE_MARKER_CACHE_MB) — 메모리 작은 서버는 100, 0 = 기억 안 함")
    ap.add_argument("--exclude", nargs="*", default=[], help="뺄 조각(원본 이름) — 예: 카우스 밑단립 에리(립)")
    ap.add_argument("--graded", default=os.path.join(REPO, "tmp", "pattern-engine", "gas-warmup", "graded", "graded.json"))
    ap.add_argument("--out", default=os.path.join(REPO, "tmp", "pattern-engine", "marker"))
    ap.add_argument("--name", default=None, help="결과 파일 이름(기본 마커_상의 / 마커_하의)")
    ap.add_argument("--no-files", action="store_true", help="PDF·DXF·PNG 없이 숫자만")
    ap.add_argument("--spec-file", help="펼침표 JSON {원본이름: [[조각이름, 거울?, 좌우, 메모], …]} — 없으면 가스 웜업 표(gas_warmup_meta)")
    ap.add_argument("--title", help="그림 제목 앞부분(기본: 한국가스공사 웜업 상의/하의 마커)")
    A = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):                     # 시험이 출력을 StringIO 로 받을 때는 건너뛴다
        sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.exists(A.graded):
        sys.exit(f"그레이딩 결과가 없다: {A.graded}\n먼저: python tools/pattern-engine/gas_warmup_grade.py --no-export")
    with open(A.graded, encoding="utf-8") as f:
        graded = json.load(f)
    counts = _parse_counts(A.counts)
    table = None
    if A.spec_file:                                           # 들여온 스타일(F10 6단계) — 장수·좌우 펼침표를 파일로 받는다
        with open(A.spec_file, encoding="utf-8") as f:
            table = {k: [tuple(x) for x in v] for k, v in json.load(f).items()}
    pcs = pieces_from_graded(graded, A.garment, counts, spec=table, exclude=set(A.exclude))
    rot = (0,) if A.nap else (0, 180)
    t_all = time.perf_counter()
    if A.quick:
        r = make_marker(pcs, width_mm=A.width * 10, gap_mm=A.gap, res_mm=A.grid, rotations=rot,
                        allow_flip=A.allow_flip, selvage_mm=A.selvage, cache_mb=A.cache_mb)
    else:
        r = search_marker(pcs, width_mm=A.width * 10, gap_mm=A.gap, res_mm=A.grid, rotations=rot, allow_flip=A.allow_flip,
                          selvage_mm=A.selvage, seed=A.seed, jobs=A.jobs, time_budget=A.budget, log=print, cache_mb=A.cache_mb)
    g_ko = {"top": "상의", "bottom": "하의"}.get(A.garment, "패턴")
    bundles = sum(counts.values())
    head = A.title or f"한국가스공사 웜업 {g_ko} 마커"
    title = f"{head} · 원단 폭 {A.width:g}cm · " + " ".join(f"{k}×{v}" for k, v in counts.items())
    S = summarize(r, bundles, counts, title)
    S["exclude"] = list(A.exclude); S["nap"] = A.nap
    os.makedirs(A.out, exist_ok=True)
    name = A.name or f"마커_{g_ko}"
    if not A.no_files:
        leg = [f"길이 {S['length_m']:.3f} m · 벌당 요척 {S['yield_m_per_bundle']:.3f} m · 효율 {S['efficiency_pct']:.1f}% · "
               f"조각 {S['piece_count']}장 · 간격 {A.gap:g}mm · 식서 세로({'0° 만 — 원단 결' if A.nap else '0°/180° 만'}) · 1:1 mm",
               "검정 = 재단선 · 세로 화살표 = 식서 · 색 = 사이즈 · 빨강 눈금 = 1 m"]
        S["pdf_pages"] = export_pdf(r, os.path.join(A.out, f"{name}.pdf"), title, leg)
        export_png(r, os.path.join(A.out, f"{name}_미리보기.png"), f"{title} — 길이 {S['length_m']:.2f} m · 효율 {S['efficiency_pct']:.1f}%")
        export_dxf(r, os.path.join(A.out, f"{name}.dxf"))
    S["seconds_total"] = round(time.perf_counter() - t_all, 1)                  # 탐색 + 파일 내보내기
    with open(os.path.join(A.out, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: S[k] for k in ("title", "piece_count", "length_m", "yield_m_per_bundle", "efficiency_pct", "check", "seconds_total")},
                     ensure_ascii=False))
    return S


if __name__ == "__main__":
    main()
