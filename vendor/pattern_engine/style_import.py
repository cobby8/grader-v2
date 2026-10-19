# 새 스타일 들여오기 — F10 6단계 (2026-10-20)
#
#   왜: 지금 엔진은 가스 웜업 전용 이름(gas_warmup_*)이 많아, 새 옷을 넣으려면 코드를 새로 짜야 했다.
#       그런데 공장 CAD(OptiCad)가 «이미 그레이딩한» 파일을 주면, 규칙은 새로 «만드는» 것이 아니라 «읽어 내는» 것이다.
#       (비유: 사이즈별 사진 13장을 겹쳐 놓고, 점마다 «한 사이즈 갈 때 얼마나 움직였나» 를 자로 재 적어 두는 일)
#
#   하는 일 — OptiCad «Adobe Export» .ai (여러 사이즈가 레이어로 든 파일) 하나 →
#     ① 사이즈별 조각 꺼내기: 재단선(CUT 고리) · 재봉선(SEW) · 안쪽선(DRAW · CUT 레이어 안쪽선=자르는 선) · 식서 · 노치(5mm 뾰족점)
#     ② 조각 이름(%AI3_Note) · 장수(«Quantity: n» 글자) · 사이즈끼리 같은 조각 짝짓기(이름 → 같은 이름이 여럿이면 순서)
#     ③ 기준점 후보 자동 — 꺾인 점(25°) · 노치 점 · 곡선 점(비례 배분이 어긋나는 곳 = 대개 곡률이 큰 곳)
#        기준 사이즈 ↔ 다른 사이즈 대응은 «이웃 사이즈 사슬»로 잡는다(M→L→XL…, M→S→XS…) — 한 칸씩은 많이 안 움직여 헷갈리지 않는다
#     ④ 사이즈별 이동량 = 실측 규칙표(rules.json, AAMA RUL 도 함께) — 그 사이 점은 선 길이 비율 배분(aama.distribute)
#     ⑤ 검산: 기준 사이즈 + 규칙표만으로 13사이즈를 다시 만들어 «원본 CAD 사이즈» 와 대조
#        그레이드 점(꺾인 점·노치) 0.05mm · 그 사이 모양(하우스도르프) 0.5mm · 노치 수 같음 · 안쪽선 0.5mm
#        원본 «되돌이 점»(다른 자리로 돌아오는 삐죽점, 다른 사이즈엔 없음)만 그 점 하나씩 빼고 재며 빠짐없이 적는다(REV_DEG 아래)
#     ⑥ 묶음: spec_base.json(기준 명세) · rules.json · specs/spec_<사이즈>.json · view.json(그레이더 화면용) ·
#        검산.json · 확인필요.md(사람이 이름을 확인할 목록) · exports.zip
#
#   자동 이름은 «임시» 다 — 조각명_P1 … (사람이 «겨드랑이» 처럼 고쳐 주어야 한다). 확인필요.md 에 다 적는다.
#
#   실행(저장소 루트):
#     python tools/pattern-engine/style_import.py <원본.ai> --base M --out <폴더> [--style-id std-warmup-top] [--name "…"] [--dxf]
#   서버(service.py)에서 부를 함수: import_style(path, base, style_id, out=None) — 🚫 아직 service.py 에 연결하지 않았다(다음 단계)
#
#   🚫 기존 엔진 파일은 읽기·import 만 한다(opticad · cardinal · piecespec · aama · cad_view · patlib)
#   🚫 운영 DB·드라이브 무접촉. 결과는 --out(기본 tmp/pattern-engine/style-import/<style_id>/)에만
import sys, os, json, math, re, copy, zipfile, argparse, datetime, hashlib, shutil

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from shapely.geometry import Polygon, LineString, Point
import opticad
from cardinal import tips
from piecespec import from_legacy, validate, clean_ring
import aama                                                  # turn_points · distribute · _cum · _at_fraction · Rules · find_grain (읽기만)
import cad_view                                              # 화면용 조각 압축(piece_mm · pack …) 재사용 (읽기만)

FORMAT_RULES = "stiz-style-rules"; FORMAT_BASE = "stiz-style-base"; FORMAT_VERSION = 1
TOL_KNOT = 0.05          # 그레이드 점(꺾인 점·노치) 허용 어긋남(mm) — aama 검산과 같은 기준
TOL_SHAPE = 0.5          # 그 사이 모양(비례 배분 점) 허용 어긋남(mm)
TOL_PICK = 0.2           # 곡선 점을 더 넣는 기준(mm) — 0.5 목표에 여유를 두려고 더 촘촘히
TURN_DEG = aama.TURN_DEG # 꺾인 점 기준 25° (cardinal.corners 와 같다)
TURN_RELAX = 10.0        # 다른 사이즈에서 꺾인 점을 찾을 때는 느슨하게(사이즈마다 24°·26° 로 흔들리는 점이 있다 — 앞판사이바 4XL 실측)
MAX_PICK = 300           # 곡선 점 추가 상한(무한 반복 방지)
SIZE_ORDER = opticad.SIZES13


class StyleImportError(Exception):
    """들여오기를 멈춰야 하는 문제(사람이 원본을 봐야 한다) — 메시지는 한국어"""


# ════════ ① 원본 읽기 ════════
def _area(P):
    n = len(P)
    return abs(sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))) / 2 if n > 2 else 0.0


SIZE_RE = re.compile(r"^(\d{0,2}X{0,4}[SML]|X{1,4}[SL]|F|FREE|\d{1,3}(호)?)$", re.I)   # 5XS·XS·M·2XL·90·100호·FREE


def _size_of(lay):
    """레이어 스택에서 사이즈 레이어 찾기 — 바깥에 이름 없는 레이어가 감싸도 된다(가스 2XL 원본: [이름 없음, 2XL, CUT]).
       안쪽부터가 아니라 바깥부터 «사이즈처럼 생긴 이름» 첫 번째. 없으면 종류 레이어(마지막)를 뺀 이름 있는 레이어가 하나뿐일 때 그것"""
    names = [l for l in (lay[:-1] if lay and lay[-1] in ("CUT", "SEW", "DRAW") else lay or []) if l]
    for l in names:
        if l in SIZE_ORDER or SIZE_RE.match(l): return l
    return names[0] if len(names) == 1 else None


# ── 원본 상한(2026-10-20 보안 리뷰 «작은 파일 폭탄») — 실측 표준 웜업: 레이어 깊이 2 · 경로 598 · 선분 8.3천 · 좌표 최대 5,672pt ·
#    조각 하나 점 4,875(쪼갠 뒤). 604바이트(한 변 1e6pt 사각형)가 9초에 511MB, 레이어 8000겹 328KB 가 읽기만으로 489MB 였다 →
#    opticad.parse 에 넘기기 «전에» 글자만 훑어 거른다(opticad 는 가스 그레이딩도 쓰는 공용 파일이라 그대로 둔다)
MAX_LAYER_DEPTH = 16       # 레이어 겹 — 그림마다 레이어 목록을 복사하므로 깊이 × 그림 수 만큼 메모리를 쓴다
MAX_PATHS = 20000          # 경로(그림) 수
MAX_SEGS = 400000          # 선분 명령 수(곡선 하나 = 점 16개로 편다)
MAX_COORD_PT = 1e5         # 좌표 절댓값(pt) — 35m. 옷 조각은 1m 안팎
MAX_SIZES = 30             # 사이즈 레이어 수(service.IMPORT_MAX_SIZES 와 같다)
MAX_PIECE_MM = 5000.0      # 조각 하나 외곽 상자 한 변(mm)
MAX_PIECE_POINTS = 20000   # 조각 하나 점 수(재봉선·재단선·안쪽선 — 2mm 로 쪼갠 뒤) — 실측 최대의 4배
SIZE_NAME_RE = re.compile(r"[A-Za-z0-9]{1,8}")   # 사이즈 이름은 파일 경로(specs/spec_<사이즈>.json)·ZIP 이름에 쓰인다 — 영문·숫자만
_OP_ARGS = {"m": 2, "l": 2, "L": 2, "c": 6, "C": 6, "v": 4, "V": 4, "y": 4, "Y": 4}


def prescan(path):
    """opticad.parse 전 «글자만» 훑어 상한·형식 검사 — 틀리면 StyleImportError(한국어 · 원인이 보이게).
       opticad 가 숫자로 읽는 칸은 같은 규칙으로 미리 읽어 본다(못 읽으면 일꾼이 «종료 코드 1» 로 죽던 자리)"""
    with open(path, "rb") as f:
        raw = f.read()
    if b"%%EOF" not in raw[-2048:]:
        raise StyleImportError("파일 끝 표시(%%EOF)가 없다 — 내보내기·올리기가 중간에 끊긴 파일 같다. OptiCad 에서 다시 내보낼 것")
    depth = mx = paths = segs = 0
    for no, ln in enumerate(raw.decode("cp949", errors="replace").splitlines(), 1):
        s = ln.strip()
        if s.startswith("%AI5_BeginLayer"):
            depth += 1; mx = max(mx, depth)
            if depth > MAX_LAYER_DEPTH: raise StyleImportError(f"레이어가 {MAX_LAYER_DEPTH}겹을 넘는다({no}번째 줄) — 정상 원본은 2~3겹")
            continue
        if s.startswith("%AI5_EndLayer"):
            depth -= 1
            if depth < 0: raise StyleImportError(f"레이어 시작·끝 짝이 안 맞는다({no}번째 줄에서 끝이 더 많다) — 원본 확인")
            continue
        if s.endswith(") Ln") and depth == 0:
            raise StyleImportError(f"레이어 밖에 레이어 이름이 있다({no}번째 줄) — 원본 확인")
        p = s.split()
        if not p or p[-1] not in _OP_ARGS: continue
        op = p[-1]; need = _OP_ARGS[op]
        if op in ("l", "L", "c", "C") and len(p) != need + 1: continue          # opticad 도 개수가 다르면 건너뛴다
        if len(p) < need + 1:
            raise StyleImportError(f"{no}번째 줄 «{s[:40]}» 좌표 수가 모자란다 — 파일이 깨졌다")
        for t in p[:need]:
            try:
                v = float(t)
            except ValueError:
                raise StyleImportError(f"{no}번째 줄 좌표 «{t[:20]}» 를 숫자로 읽지 못했다 — 파일이 깨졌다")
            if not math.isfinite(v): raise StyleImportError(f"{no}번째 줄 좌표가 숫자가 아니다(NaN·무한대) — 파일이 깨졌다")
            if abs(v) > MAX_COORD_PT: raise StyleImportError(f"{no}번째 줄 좌표 {v:.0f}pt 가 너무 크다(±{MAX_COORD_PT:.0f}pt 까지)")
        segs += 1; paths += op == "m"
        if paths > MAX_PATHS: raise StyleImportError(f"경로가 너무 많다({MAX_PATHS}개 넘음)")
        if segs > MAX_SEGS: raise StyleImportError(f"선분이 너무 많다({MAX_SEGS}개 넘음)")
    if depth != 0:
        raise StyleImportError(f"레이어 시작·끝 짝이 안 맞는다(끝나지 않은 레이어 {depth}개) — 파일이 중간에 잘렸거나 깨졌다")
    return {"layer_depth": mx, "paths": paths, "segs": segs}


def read_ai(path):
    """OptiCad .ai → {"style": 글자, "sizes": [사이즈 순서], "sample": 글자가 든 사이즈,
                      "pieces": {사이즈: {조각키: 옛 형식 조각}}, "qty": {조각이름: n}, "names": [조각키 순서]}
       조각키 = %AI3_Note 이름(이름이 없으면 «조각N»). 같은 이름 아래 큰 재단 고리가 둘이면 멈춘다(_legacy_piece)"""
    prescan(path)                                            # 상한·형식 먼저(폭탄·깨진 파일은 여기서 멈춘다)
    _, items = opticad.parse(path)
    style, qty, cur_piece = None, {}, None
    text_count, size_seen = {}, []
    raw = {}                                                 # (사이즈, 원래 이름) → {CUT:[], SEW:[], DRAW:[]}
    order_in_size = {}                                       # 사이즈마다 처음 나온 조각 순서
    for it in items:
        lay = it["layers"]
        size = _size_of(lay)
        if size is not None and size not in size_seen: size_seen.append(size)
        if it["t"] == "text":
            s = it["s"]; text_count[size] = text_count.get(size, 0) + 1
            if s.startswith("Style Name:") and style is None: style = s.split(":", 1)[1].strip()
            elif s.startswith("Piece Name:"): cur_piece = s.split(":", 1)[1].strip()
            elif s.startswith("Quantity:") and cur_piece is not None:
                try: qty.setdefault(cur_piece, int(s.split(":", 1)[1].strip()))
                except ValueError: pass
            continue
        kind = lay[-1] if lay else None
        if kind not in ("CUT", "SEW", "DRAW"): continue
        note = it.get("note")
        lst = order_in_size.setdefault(size, [])
        # OptiCad 내보내기는 CUT 전부 → SEW 전부 → DRAW 전부 순서라 «이름» 으로만 묶는다(같은 이름 두 조각은 아래에서 멈춤)
        rec = raw.get((size, note))
        if rec is None:
            rec = raw[(size, note)] = {"CUT": [], "SEW": [], "DRAW": []}; lst.append(note)
        rec[kind].append({"pts": opticad.flat(it["seg"]), "closed": bool(it.get("closed")), "nodes": len(it["seg"])})
    sizes = [s for s in size_seen if s is not None]
    if all(s in SIZE_ORDER for s in sizes): sizes.sort(key=SIZE_ORDER.index)
    if not sizes: raise StyleImportError("사이즈 레이어를 찾지 못했다 — OptiCad «Adobe Export» 파일인지 확인")
    if len(sizes) > MAX_SIZES: raise StyleImportError(f"사이즈 레이어가 너무 많다({len(sizes)}개 — {MAX_SIZES}개 까지)")
    for s in sizes:                                          # 사이즈 이름은 파일 경로·ZIP 이름이 된다
        if not (SIZE_NAME_RE.fullmatch(s) and SIZE_RE.match(s)):
            raise StyleImportError(f"사이즈 레이어 이름 «{str(s)[:20]}» 을 쓸 수 없다 — 영문·숫자 사이즈(5XS~5XL·90 등)만")
    sample = max(text_count, key=lambda s: text_count[s]) if text_count else None
    pieces, names = {}, []
    for size in sizes:
        out = {}; k = 0
        for note in order_in_size.get(size, []):
            rec = raw[(size, note)]; k += 1
            key = note if note else f"조각{k}"
            out[key] = _legacy_piece(key, rec)
        pieces[size] = out
    names = list(pieces[sizes[0]].keys())
    return {"style": style, "sizes": sizes, "sample": sample, "pieces": pieces, "qty": qty, "names": names}


def _legacy_piece(name, rec):
    """원본 레이어 묶음 → 옛 형식 조각 {name, cut, sew, draw, notch, fold}
       재단선 = CUT 중 가장 넓은 고리 · 나머지 CUT = 자르는 안쪽선(cut=True) · DRAW = 그리기 안쪽선"""
    cuts = sorted(rec["CUT"], key=lambda d: -_area(d["pts"]))
    if not cuts: raise StyleImportError(f"{name}: CUT(재단선) 레이어가 없다")
    cut = cuts[0]["pts"]
    if len(cuts) > 1 and cuts[1]["closed"] is not None and _area(cuts[1]["pts"]) > 0.3 * _area(cut):
        raise StyleImportError(f"{name}: 같은 이름 아래 큰 재단 고리가 둘 — 원본 CAD 에서 조각 이름을 따로 달아 다시 내보낼 것")
    sew = max(rec["SEW"], key=lambda d: _area(d["pts"]))["pts"] if rec["SEW"] else list(cut)
    draw = []
    for d in cuts[1:]:
        draw.append({"pts": d["pts"], "closed": d["closed"], "new": False, "cut": True, "src": "CUT"})
    for d in rec["DRAW"]:
        draw.append({"pts": d["pts"], "closed": d["closed"], "new": False, "src": "DRAW"})
    return {"name": name, "cut": cut, "sew": sew, "draw": draw, "notch": [], "fold": None, "no_sew": not rec["SEW"]}


# ════════ ② 선 하나 그레이딩 규칙 읽기 ════════
def _angle(P, i, closed):
    """i 점에서 꺾인 각도(도) — 0 길이 변은 건너 이웃을 본다(aama.turn_points 와 같은 규칙). 열린 선 양 끝 = 180"""
    n = len(P)
    if not closed and i in (0, n - 1): return 180.0
    j = (i - 1) % n
    while math.dist(P[j], P[i]) < 1e-6 and j != i: j = (j - 1) % n
    k = (i + 1) % n
    while math.dist(P[k], P[i]) < 1e-6 and k != i: k = (k + 1) % n
    a = math.atan2(P[i][1] - P[j][1], P[i][0] - P[j][0]); b = math.atan2(P[k][1] - P[i][1], P[k][0] - P[i][0])
    return abs((math.degrees(b - a) + 180) % 360 - 180)


def _features(P, closed, notch_idx=()):
    """특징점 {번호: 종류} — 꺾인 점 «turn» · 노치 «notch» · 열린 선 양 끝 «end»"""
    out = {i: "turn" for i in aama.turn_points(P, closed)}
    if not closed:
        out[0] = "end"; out[len(P) - 1] = "end"
    for i in notch_idx: out[i] = "notch"
    return out


def _cyc_order_ok(seq, n, closed):
    """대응한 사이즈 점 번호가 기준 순서대로(고리는 한 바퀴 안에서) 늘어나는가"""
    if len(seq) < 2: return True
    if not closed: return all(b > a for a, b in zip(seq, seq[1:]))
    steps = [(b - a) % n for a, b in zip(seq, seq[1:] + seq[:1])]
    return all(s > 0 for s in steps) and sum(steps) == n


def _dedupe(P, closed):
    """이웃한 같은 자리 점(0 길이 변)·닫는 중복 점을 뺀 선 + 새 번호 → 원래 번호(처음 나온 것)
       — 원본 재봉선은 끝에 시작점이 두 번 더 붙어 있다(주머니 273·274 = 0, 실측). 그대로 두면 «특징점 순서» 판정이 꼬인다"""
    R, back = [], []
    for i, v in enumerate(P):
        if R and math.dist(R[-1], v) < 1e-6: continue
        R.append(tuple(v)); back.append(i)
    if closed:
        while len(R) > 2 and math.dist(R[0], R[-1]) < 1e-6: R.pop(); back.pop()
    return R, back


def grade_line(base_P, closed, targets, base_size, sizes, base_notch=(), target_notch=None, label=""):
    """grade_line 겉 — 같은 자리 중복 점을 빼고 재고, 그레이드 점 번호는 «원래 점 목록» 번호로 돌려준다
       (중복 점은 규칙으로 다시 만들 때 쌍둥이와 같은 자리로 따라간다 — 길이 0 이라 비례 배분 비율이 같다)"""
    B, bb = _dedupe(base_P, closed); inv = {o: r for r, o in enumerate(bb)}
    TT, tn = {}, {}
    for s in sizes:
        T, tb = _dedupe(targets[s], closed); TT[s] = T; ti = {o: r for r, o in enumerate(tb)}
        tn[s] = [ti[k] for k in (target_notch or {}).get(s, ()) if k in ti]
    g = _grade_core(B, closed, TT, base_size, sizes, [inv[k] for k in base_notch if k in inv], tn, label)
    m = lambda i: bb[i]
    return {"knots": [m(i) for i in g["knots"]], "kind": {m(i): v for i, v in g["kind"].items()},
            "disp": {m(i): v for i, v in g["disp"].items()}, "mode": g["mode"]}


def _grade_core(base_P, closed, targets, base_size, sizes, base_notch=(), target_notch=None, label=""):
    """기준 선 base_P 와 사이즈별 같은 선 targets{사이즈: 점 목록} → 그레이드 점과 사이즈별 이동량.
       돌려주는 값 {"knots": [번호], "kind": {번호: turn|notch|end|curve}, "disp": {번호: {사이즈: (dx,dy)}}, "mode": index|fraction}
         index    — 모든 사이즈의 점 수·특징점 번호가 기준과 같다 → 점마다 실제 이동량을 그대로 잰다
         fraction — 사이즈마다 점 수가 다르다(곡선을 다르게 쪼갬) → 특징점끼리 맞추고, 그 사이는 «특징점 사이 길이 비율이 같은 자리»
       특징점 대응은 이웃 사이즈 사슬: 앞 사이즈 자리 + 앞 칸 이동량으로 예측 → 예측에 가장 가까운 같은 종류 점"""
    n = len(base_P); target_notch = target_notch or {}
    feat = _features(base_P, closed, base_notch)
    if closed and len(feat) < 2:                             # 꺾인 점 없는 고리(동그라미 등) — 0번·가운데 점을 «닻» 으로(점 수 비율 자리끼리)
        feat = {0: "anchor", n // 2: "anchor"}
    K = sorted(feat)
    if len(K) < 2: raise StyleImportError(f"{label}: 특징점이 둘 미만 — 맞출 수 없다")
    bi = sizes.index(base_size)
    match = {base_size: {k: k for k in K}}                   # 사이즈 → {기준 특징점 번호: 사이즈 점 번호}
    for step in (1, -1):                                     # 기준에서 바깥으로 한 칸씩
        prev, pd = base_size, {k: (0.0, 0.0) for k in K}
        j = bi + step
        while 0 <= j < len(sizes):
            s = sizes[j]; T = targets[s]; m = len(T)
            Tn = set(target_notch.get(s, ()))
            cand_turn = [i for i in range(m) if _angle(T, i, closed) > TURN_RELAX and (closed or 0 < i < m - 1)]   # 열린 선 끝은 «끝» 몫
            cand_set = set(cand_turn)
            Pprev = base_P if prev == base_size else targets[prev]
            mm = {}
            pred = {}
            for k in K:
                q = Pprev[match[prev][k]]; pred[k] = (q[0] + pd[k][0], q[1] + pd[k][1])
            # 노치 — 개수가 같으니 «순서를 지킨 채 시작점만 돌려» 맞춘다(겹노치 20mm 간격을 한 칸 이동량이 넘어도 안 헷갈린다)
            BN = [k for k in K if feat[k] == "notch"]; TN = sorted(Tn)
            if BN:
                if len(TN) != len(BN): raise StyleImportError(f"{label}: 사이즈 {s} 노치 수가 다르다({len(TN)} ≠ {len(BN)})")
                r = len(BN)
                rot = min(range(r) if closed else [0], key=lambda o: sum(math.dist(T[TN[(a + o) % r]], pred[BN[a]]) for a in range(r)))
                for a in range(r): mm[BN[a]] = TN[(a + rot) % r]
            for k in K:
                if feat[k] == "notch": continue
                if feat[k] == "end":                          # 열린 선 양 끝은 끝끼리(짧은 선이 한 칸에 제 길이보다 많이 움직여도)
                    mm[k] = 0 if k == 0 else m - 1; continue
                if feat[k] == "anchor":
                    mm[k] = round(k * m / n) % m; continue
                if not cand_turn: raise StyleImportError(f"{label}: 사이즈 {s} 에 꺾인 점 후보가 없다")
                pk = match[prev][k]
                if m == len(Pprev) and pk in cand_set:            # 점 수가 앞 사이즈와 같고 같은 번호도 꺾인 점 → 같은 번호(같은 구조로 내보낸 선)
                    mm[k] = pk; continue
                mm[k] = min(cand_turn, key=lambda i: math.dist(T[i], pred[k]))
            for k in K:
                if math.dist(T[mm[k]], pred[k]) > 40:
                    raise StyleImportError(f"{label}: 사이즈 {s} 특징점 대응이 예측에서 40mm 넘게 벗어났다 — 원본 확인")
            seq = [mm[k] for k in K]
            if len(set(seq)) != len(seq) or not _cyc_order_ok(seq, m, closed):
                raise StyleImportError(f"{label}: 사이즈 {s} 특징점 순서가 기준과 다르다 — 원본 확인")
            pd = {k: (T[mm[k]][0] - Pprev[match[prev][k]][0], T[mm[k]][1] - Pprev[match[prev][k]][1]) for k in K}
            match[s] = mm; prev = s; j += step
    others = [s for s in sizes if s != base_size]
    index_mode = all(len(targets[s]) == n and all(match[s][k] == k for k in K) for s in others)
    # 점마다 «대응점» 이동량 D[사이즈][번호]
    D = {}
    s_cum, s_tot = aama._cum(base_P, closed)
    for s in others:
        T = targets[s]
        if index_mode:
            D[s] = [(T[i][0] - base_P[i][0], T[i][1] - base_P[i][1]) for i in range(n)]; continue
        Ds = [None] * n
        pairs = list(zip(K, K[1:])) + ([(K[-1], K[0])] if closed else [])
        for a, b in pairs:
            La = (s_cum[b] - s_cum[a]) if b > a else (s_tot - s_cum[a] + s_cum[b])
            ta, tb = match[s][a], match[s][b]; i = a
            while True:
                d = (s_cum[i] - s_cum[a]) if i >= a else (s_tot - s_cum[a] + s_cum[i])
                qq = aama._at_fraction(T, closed, ta, tb, d / La if La > 1e-9 else 0.0)
                Ds[i] = (qq[0] - base_P[i][0], qq[1] - base_P[i][1])
                if i == b: break
                i = (i + 1) % n
        for k in K: Ds[k] = (T[match[s][k]][0] - base_P[k][0], T[match[s][k]][1] - base_P[k][1])
        D[s] = Ds
    kind = dict(feat); knots = set(K)
    if others:
        knots = _pick(base_P, closed, knots, D, targets, index_mode)
        for i in knots: kind.setdefault(i, "curve")
    disp = {i: {s: (0.0, 0.0) if s == base_size else D[s][i] for s in sizes} for i in sorted(knots)}
    return {"knots": sorted(knots), "kind": {i: kind[i] for i in sorted(knots)}, "disp": disp,
            "mode": "index" if index_mode else "fraction"}


def _pick(P, closed, K, D, targets, index_mode):
    """곡선 점 고르기 — 지금 그레이드 점만으로 비례 배분했을 때 가장 크게 어긋나는 점을 하나씩 더한다.
       index 모드: 점마다 실제 이동량과 비교(0.05mm 까지) · fraction 모드: 다시 만든 선 ↔ 원본 사이즈 선 거리(TOL_PICK 까지)"""
    K = set(K); n = len(P)
    mk = (lambda q: Polygon(q).exterior) if closed else LineString
    tgt = {s: mk(T) for s, T in targets.items() if s in D}
    tol = aama.TOL_KNOT if index_mode else TOL_PICK
    for _ in range(MAX_PICK):
        worst, wi = 0.0, None
        for s, Ds in D.items():
            R = aama.distribute(P, closed, sorted(K), {k: Ds[k] for k in K})
            rec = [(P[i][0] + R[i][0], P[i][1] + R[i][1]) for i in range(n)]
            if index_mode:
                for i in range(n):
                    e = math.dist(R[i], Ds[i])
                    if e > worst: worst, wi = e, i
                continue
            for i in range(n):                                # 다시 만든 점 → 원본 선
                if i in K: continue
                e = tgt[s].distance(Point(rec[i]))
                if e > worst: worst, wi = e, i
        if worst <= tol or wi is None or wi in K: break
        K.add(wi)
    if index_mode: return K
    # 2단계 — 원본 쪽 꺾임(기준에서는 25° 안 되는 작은 꺾임이 큰 사이즈에서 19° 로 자라는 곳 · 팬츠 앞판 4XL 0.44mm 실측)
    #   원본 점 → 다시 만든 선 거리가 큰 곳에, 대응점이 가장 가까운 기준 점을 그레이드 점으로 «시험 삼아» 넣고
    #   실제로 줄면 남기고 안 줄면 뺀다(⚠️ 무조건 넣으면 긴 직선 변처럼 못 줄이는 곳에서 기준 점을 전부 그레이드 점으로 만든다 — 실측)
    stuck = set()
    def tside(s, KK):
        R = aama.distribute(P, closed, sorted(KK), {k: D[s][k] for k in KK})
        rl = mk([(P[i][0] + R[i][0], P[i][1] + R[i][1]) for i in range(n)])
        return [rl.distance(Point(q)) for q in targets[s]]
    for _ in range(MAX_PICK):
        worst, ws, wq = 0.0, None, None
        for s in D:
            for j, e in enumerate(tside(s, K)):
                if e > worst and (s, j) not in stuck: worst, ws, wq = e, s, j
        if worst <= tol or ws is None: return K
        q = targets[ws][wq]; free = [i for i in range(n) if i not in K]
        if not free: return K
        wi = min(free, key=lambda i: math.dist((P[i][0] + D[ws][i][0], P[i][1] + D[ws][i][1]), q))
        if tside(ws, K | {wi})[wq] < worst * 0.7: K.add(wi)
        else: stuck.add((ws, wq))
    return K


# ════════ ③ 조각 하나 → 명세 + 규칙 ════════
def _seam_xy(spec):
    return [(s["x"], s["y"]) for s in spec["seam"]]


def _notch_idx(spec):
    return [k for k, s in enumerate(spec["seam"]) if s.get("notch")]


def _cut_ring(p):
    return [tuple(v) for v in clean_ring(p["cut"])]


def _is_symmetric(P, tol=1.0):
    """세로축(외곽 상자 가운데) 좌우 대칭인가 — 장수(한 쌍?) 힌트용"""
    xs = [q[0] for q in P]; c = (min(xs) + max(xs)) / 2
    try:
        return _haus(P, [(2 * c - x, y) for x, y in P], True) <= tol   # 중복 점을 뺀 _haus 로(그냥 재면 NaN → «비대칭» 으로 잘못 나온다)
    except Exception:
        return False


def _where(P, q):
    """점 자리를 사람 말로 — 조각 외곽 상자 안에서 위·가운데·아래 / 왼쪽·가운데·오른쪽"""
    xs = [p[0] for p in P]; ys = [p[1] for p in P]
    fx = (q[0] - min(xs)) / max(max(xs) - min(xs), 1e-9); fy = (q[1] - min(ys)) / max(max(ys) - min(ys), 1e-9)
    v = "위" if fy > 2 / 3 else ("아래" if fy < 1 / 3 else "가운데 높이")
    h = "오른쪽" if fx > 2 / 3 else ("왼쪽" if fx < 1 / 3 else "가운데")
    return f"{v}·{h}"


KIND_KO = {"turn": "꺾인 점", "notch": "노치", "curve": "곡선 점", "end": "선 끝", "anchor": "닻(꺾임 없는 고리)"}


REV_DEG = 170.0          # 이보다 꺾이면 «되돌이 점»(선이 갔다가 거꾸로 돌아옴)
SAME_PLACE = 0.5         # 뾰족점 앞뒤 점이 이 안(mm)이면 «같은 자리로 돌아옴» = 노치 모양 — 깊이와 상관없이 결함이 아니다
REV_LEN = 20.0           # (보조) 결함으로 자동으로 빼는 되돌이의 짧은 쪽 변 상한(mm) — 더 길면 빼지 않고 검산 실패로 사람에게 넘긴다
#   판정은 «모양» 으로 한다(깊이가 아니라):
#     같은 자리로 돌아옴(앞뒤 점 0.5mm 안)        → 노치 모양. 깊이 2.5·10·15mm 여도 절대 빼지 않는다
#     다른 자리로 돌아옴 + 다른 사이즈에는 없음    → 원본 결함. 빼고 «다 적는다» (조각마다 사이즈별 되돌이 수가 모두 같으면 디자인으로 보고 둔다)
#   실측(2026-10-20): 표준 웜업 앞판사이바 재봉선 «시작점» 은 옆선 위 직선 위의 점인데(M 22mm·5XS~3XL 2~27mm 위),
#     꼭짓점과 다른 규칙으로 움직여 4XL 에서 꼭짓점 밑 3mm·5XL 8mm 로 «넘어가» 되돌이가 생긴다 — 규칙으로는 만들 수 없는 점


def find_reversals(P, closed=True):
    """결함 모양 되돌이 점 번호(중복 점 뺀 선 기준) — 앞뒤 점이 «다른 자리» 인 것만. 노치 모양(같은 자리로 돌아옴)은 깊이와 무관하게 제외"""
    n = len(P); out = []
    for i in range(n):
        if not closed and i in (0, n - 1): continue
        a, c = P[(i - 1) % n], P[(i + 1) % n]
        la, lc = math.dist(a, P[i]), math.dist(P[i], c)
        if min(la, lc) < 1e-6 or _angle(P, i, closed) <= REV_DEG: continue
        if math.dist(a, c) < SAME_PLACE: continue            # 같은 자리로 돌아옴 = 노치 모양
        if min(la, lc) < REV_LEN: out.append(i)
    return out


def drop_reversals(P, closed=True):
    """결함 모양 되돌이 점을 뺀 선 + 뺀 점 목록(같은 자리 중복 점도 정리된다)"""
    P = _dedupe(P, closed)[0]; dropped = []                 # 같은 자리 중복 점(원본 끝에 시작점이 또 붙는다)부터 빼야 이웃이 보인다
    while True:
        R = find_reversals(P, closed)
        if not R: return P, dropped
        i = R[0]; dropped.append([round(P[i][0], 2), round(P[i][1], 2)]); P.pop(i)


def same_place_spikes(P, closed=True):
    """같은 자리로 돌아오는 뾰족점(노치 모양) 중 «깊이 3~7mm» 밖이라 노치 속성으로 못 읽은 것 — [(점, 깊이)]"""
    P = _dedupe(P, closed)[0]; T = tips(P) if closed else set(); n = len(P); out = []
    for i in range(n):
        if i in T or (not closed and i in (0, n - 1)): continue
        a, c = P[(i - 1) % n], P[(i + 1) % n]
        if math.dist(a, P[i]) > 1e-6 and math.dist(a, c) < SAME_PLACE and _angle(P, i, closed) > REV_DEG:
            out.append(((round(P[i][0], 1), round(P[i][1], 1)), round(math.dist(a, P[i]), 1)))
    return out


def defect_sizes(by_size):
    """조각 하나의 사이즈별 옛 형식 → 되돌이를 뺄 사이즈 {사이즈: True}.
       «다른 사이즈엔 없음» 판정 — 되돌이가 없는 사이즈가 하나라도 있으면 있는 사이즈만 결함.
       모든 사이즈에 같은 수만큼 있으면 디자인으로 보고 둔다. 수가 다르고 없는 사이즈도 없으면 사람이 봐야 한다(멈춤)"""
    cnt = {s: (len(find_reversals(_dedupe(p["sew"], True)[0])), len(find_reversals(_dedupe(p["cut"], True)[0])))
           for s, p in by_size.items()}
    out = {}
    for k in (0, 1):
        vals = {s: c[k] for s, c in cnt.items()}
        if min(vals.values()) == 0:
            for s, v in vals.items():
                if v: out[s] = True
        elif len(set(vals.values())) > 1:
            raise StyleImportError(f"{next(iter(by_size.values())).get('name')}: 되돌이 점 수가 사이즈마다 다르다 {vals} — 원본 확인")
    return out


def clean_piece(p, drop=True):
    """재봉선·재단선의 되돌이 점을 뺀 사본 + {"sew": [...], "cut": [...]} 뺀 점. drop=False 면 그대로(사본만)"""
    if not drop: return dict(p), {}
    q = dict(p); q["sew"], ds = drop_reversals(p["sew"]); q["cut"], dc = drop_reversals(p["cut"])
    return q, {k: v for k, v in (("sew", ds), ("cut", dc)) if v}


DENSIFY = 2.0            # 기준 선의 변이 이보다 길면 같은 간격으로 점을 더 찍는다(mm) — 5mm 면 팬츠 앞판 4XL 0.44 · 2mm 0.26 (1mm 도 0.26, 두 배 느림 — 실측)
#   왜: 공장 CAD 는 기준 사이즈의 «직선» 변 가운데에 그레이드 점을 둘 수 있다 — 다른 사이즈에서는 그 자리가 꺾여 나온다.
#       기준 선에 그 자리 점이 없으면 아무리 규칙을 읽어도 못 따라간다(표준 팬츠 앞판 5XL 2.57mm 어긋남, 2026-10-20 실측).
#       점을 더 찍어도 모양·시접은 그대로다(같은 직선 위). 노치 뾰족점(3~7mm 변)은 8mm 미만이라 건드리지 않는다


def _densify(P, closed, step=None):
    step = step or DENSIFY; out = []; n = len(P); m = n if closed else n - 1
    for i in range(m):
        a, b = P[i], P[(i + 1) % n]; out.append(tuple(a))
        L = math.dist(a, b)
        if L > max(step * 1.5, 8.0):                         # 노치 뾰족점 변(3~7mm)은 절대 쪼개지 않는다 — 쪼개면 노치가 사라진다
            k = int(math.ceil(L / step))
            for t in range(1, k): out.append((a[0] + (b[0] - a[0]) * t / k, a[1] + (b[1] - a[1]) * t / k))
    if not closed: out.append(tuple(P[-1]))
    return out


def densify_piece(p):
    """기준 사이즈 조각의 재봉선·재단선·안쪽선에 점을 더 찍은 사본 — 원본 조각은 안 바꾼다"""
    q = copy.deepcopy(p)
    q["sew"] = _densify(p["sew"], True); q["cut"] = _densify(p["cut"], True)
    q["draw"] = [dict(d, pts=_densify(d["pts"], bool(d.get("closed")))) for d in p["draw"]]
    return q


def import_piece(name, by_size, base, sizes, qty_read):
    """조각 하나(사이즈별 옛 형식) → (기준 명세, 조각 규칙 원본{선: grade_line 결과}, 확인 필요 목록)"""
    for s, p in by_size.items():                             # 상한 — 쪼개기(2mm) 전에 크기부터(한 변 35m 사각형이 70만 점이 된다)
        xs = [q[0] for q in p["cut"]]; ys = [q[1] for q in p["cut"]]
        if max(xs) - min(xs) > MAX_PIECE_MM or max(ys) - min(ys) > MAX_PIECE_MM:
            raise StyleImportError(f"{name}: 사이즈 {s} 조각이 너무 크다(한 변 {MAX_PIECE_MM / 1000:.0f}m 넘음) — 원본 확인")
    bad = defect_sizes(by_size)                              # 되돌이가 «다른 사이즈엔 없는» 사이즈만
    cleaned = {s: clean_piece(by_size[s], s in bad) for s in sizes}   # 원본 결함(되돌이 점) 빼기 — 뺀 자리는 확인 필요 목록에
    by_size = {s: c[0] for s, c in cleaned.items()}
    dropped = {s: c[1] for s, c in cleaned.items() if c[1]}
    bp = densify_piece(by_size[base])                        # 기준만 긴 직선 변에 점을 더 찍는다(모양은 그대로) — 아래 DENSIFY 참고
    npts = len(bp["sew"]) + len(bp["cut"]) + sum(len(d["pts"]) for d in bp["draw"])
    if npts > MAX_PIECE_POINTS or any(len(by_size[s]["sew"]) + len(by_size[s]["cut"]) > MAX_PIECE_POINTS for s in sizes):
        raise StyleImportError(f"{name}: 조각 점이 너무 많다({npts:,}개 — {MAX_PIECE_POINTS:,}개 까지) — 원본 확인")
    sb = from_legacy(bp)                                     # 기준 사이즈 명세 — 시접은 원본 재단선에서 읽는다
    tsp = {s: from_legacy(by_size[s]) for s in sizes}
    lab = f"{name}"
    # 재봉선
    g_seam = grade_line(_seam_xy(sb), True, {s: _seam_xy(tsp[s]) for s in sizes}, base, sizes,
                        _notch_idx(sb), {s: _notch_idx(tsp[s]) for s in sizes}, label=f"{lab} 재봉선")
    for s in sizes:
        if len(_notch_idx(tsp[s])) != len(_notch_idx(sb)):
            raise StyleImportError(f"{lab}: 노치 수가 사이즈 {s} 에서 다르다({len(_notch_idx(tsp[s]))} ≠ {len(_notch_idx(sb))})")
    # 재단선(노치 뾰족점 뺀 고리)
    g_cut = grade_line(_cut_ring(bp), True, {s: _cut_ring(by_size[s]) for s in sizes}, base, sizes, label=f"{lab} 재단선")
    # 안쪽선 — 같은 순서(같은 레이어 출처)끼리
    g_int = []
    for j, d in enumerate(bp["draw"]):
        T = {}
        for s in sizes:
            dl = by_size[s]["draw"]
            if len(dl) != len(bp["draw"]) or dl[j].get("src") != d.get("src"):
                raise StyleImportError(f"{lab}: 안쪽선 수/종류가 사이즈 {s} 에서 다르다")
            T[s] = dl[j]["pts"]
        g_int.append(grade_line(d["pts"], bool(d.get("closed")), T, base, sizes, label=f"{lab} 안쪽선 {j + 1}"))
    # 기준점 임시 이름 — 재봉선 그레이드 점마다 조각명_P1 …
    for n_, i in enumerate(g_seam["knots"], 1):
        sb["seam"][i]["node"] = f"{name}_P{n_}"
    # 식서 · 장수 · 메타
    gj = aama.find_grain(by_size[base], by_size[base]["draw"])   # 점을 더 찍기 «전» 기준으로 — find_grain 은 두 점짜리 선만 식서로 본다
    if gj is not None:
        P = bp["draw"][gj]["pts"]; sb["grain"] = {"from": list(P[0]), "to": list(P[-1]), "arrow": "both"}
    sym = _is_symmetric(_seam_xy(sb))
    qty = qty_read.get(name)
    sb["meta"] = {"qty": qty or 1, "qty_read": qty, "symmetric": sym, "grain_line": gj, "source_note": name,
                  "auto_names": True, "no_sew": bool(bp.get("no_sew"))}
    sb["name"] = name
    conf = _confirm_piece(name, sb, g_seam, g_cut, g_int, bp, qty, sym, gj)
    for s, d in dropped.items():
        for k, pts in d.items():
            where = "재봉선" if k == "sew" else "재단선"
            conf["notes"].append(f"원본 결함: 사이즈 {s} {where}에 되돌이 점 {len(pts)}개(" + ", ".join(f"({x:.1f}, {y:.1f})" for x, y in pts)
                                 + ") — 다른 자리로 돌아오는 삐죽점이고 다른 사이즈에는 없어 원본에서 «그 점만» 빼고 들여왔다(검산도 그 점만 빼고 잰다 —"
                                 " 둘레를 따로 빼지 않는다). 노치라면 전 사이즈에 넣고 다시 들여올 것")
    for q, depth in same_place_spikes(by_size[base]["sew"]):
        conf["notes"].append(f"노치 모양(같은 자리로 돌아오는 뾰족점) 깊이 {depth}mm ({q[0]}, {q[1]}) — 노치 속성은 깊이 3~7mm 만 읽어서"
                             " 이 점은 선 모양(꺾인 점)으로 들여왔다. 노치면 명세에서 노치로 바꿀 것")
    sb["meta"]["dropped"] = dropped
    return sb, {"seam": g_seam, "cut": g_cut, "internal": g_int}, conf


def _confirm_piece(name, sb, g_seam, g_cut, g_int, bp, qty, sym, gj):
    """사람이 확인할 것 — 이름·장수·기준점 이름·자르는 안쪽선·식서"""
    P = _seam_xy(sb); out = []
    out.append(f"조각 이름 «{name}» — 원본 %AI3_Note 그대로. 영문 이름(DXF)은 비어 있다 → PIECE n 으로 나간다")
    if qty is None: out.append("장수 글자(Quantity)를 못 찾아 1장으로 두었다")
    if (qty or 1) == 1 and not sym:
        out.append(f"장수 {qty or 1}장(원본 표기)인데 좌우 비대칭 — 몸 한쪽만 그린 조각이면 한 쌍(2장, R/L)으로 고쳐야 한다")
    if bp.get("no_sew"): out.append("재봉선(SEW)이 없어 재단선을 재봉선으로 썼다 — 시접 0")
    ncut = sum(1 for d in sb["internal"] if d.get("cut"))
    if ncut: out.append(f"CUT 레이어 안쪽선 {ncut}개를 «자르는 선»(트임)으로 넣었다 — 표시선이면 자르지 않게 바꿀 것")
    if gj is None: out.append("식서선을 못 찾았다 — 세로(원단 길이 방향) 기본으로 나간다")
    data = []                                                # 화면(이름 확인 칸)이 쓰는 구조 자료 — 글자 목록(points)은 confirm.md 용
    for n_, i in enumerate(g_seam["knots"], 1):
        data.append({"name": f"{name}_P{n_}", "kind": g_seam["kind"][i], "where": _where(P, P[i]),
                     "x": round(P[i][0], 1), "y": round(P[i][1], 1)})
    return {"piece": name, "notes": out, "points": [_point_line(d) for d in data], "points_data": data}


def _point_line(d):
    """기준점 하나를 confirm.md 한 줄로 — «소매_P1 = 꺾인 점 · 위·왼쪽 (x, y)»"""
    return f"{d['name']} = {KIND_KO.get(d['kind'], d['kind'])} · {d['where']} ({d['x']:.1f}, {d['y']:.1f})"


# ════════ ④ 규칙표 ════════
def build_rules(style_id, base, sizes, raw):
    """raw: {조각: {"seam": g, "cut": g, "internal": [g]}} → rules.json 내용 + aama.Rules(RUL 쓰기용)
       같은 이동량 묶음(0.01mm 반올림)은 규칙 번호 하나 — 0번 = 움직이지 않는 점"""
    R = aama.Rules(sizes)
    pieces = {}
    def pack(g):
        return [{"i": i, "kind": g["kind"][i], "rule": R.add(g["disp"][i])} for i in g["knots"]]
    for name, rr in raw.items():
        pieces[name] = {"seam": pack(rr["seam"]), "cut": pack(rr["cut"]), "internal": [pack(g) for g in rr["internal"]],
                        "mode": {"seam": rr["seam"]["mode"], "cut": rr["cut"]["mode"],
                                 "internal": [g["mode"] for g in rr["internal"]]}}
        for n_, k in enumerate(pieces[name]["seam"], 1): k["name"] = f"{name}_P{n_}"
    table = [[list(v) for v in key] for key in R.order]
    return {"format": FORMAT_RULES, "version": FORMAT_VERSION, "style_id": style_id, "base_size": base, "sizes": sizes,
            "unit": "mm", "note": "rules[n][사이즈 순번] = 기준 사이즈 대비 (Δx, Δy) · 그 사이 점은 선 길이 비율 배분",
            "rules": table, "pieces": pieces}, R


# ════════ ⑤ 규칙표로 다시 만들기(regrade) ════════
def _move(P, closed, knots, table, si):
    K = [k["i"] for k in knots]
    kd = {k["i"]: tuple(table[k["rule"]][si]) for k in knots}
    D = aama.distribute(P, closed, K, kd)
    return [(P[i][0] + D[i][0], P[i][1] + D[i][1]) for i in range(len(P))]


def _tangent(P, k):
    n = len(P); a = P[(k - 1) % n]; b = P[(k + 1) % n]
    j = (k - 1) % n
    while math.dist(P[j], P[k]) < 1e-6 and j != k: j = (j - 1) % n
    m = (k + 1) % n
    while math.dist(P[m], P[k]) < 1e-6 and m != k: m = (m + 1) % n
    return math.atan2(P[m][1] - P[j][1], P[m][0] - P[j][0])


_FOLLOW = {}             # id(기준 명세) → (명세, 재단선 점마다 가장 가까운 재봉선 점 번호) — 한 번만 잰다(사이즈 13번 되풀이)


def _follow_map(spec):
    """기준 재단선(clean_ring) 점마다 가장 가까운 기준 재봉선 점 번호.
       왜: 화면에서 재봉선 기준점을 옮기면(F10 3단계) 재단선(시접)도 그만큼 따라가야 시접 폭이 지켜진다.
       재단선 규칙은 원본에서 «원래 재봉선 규칙과 짝으로» 읽은 것이라, 바뀐 양(δ)만 가장 가까운 재봉선 점에서 빌려 온다"""
    hit = _FOLLOW.get(id(spec))
    if hit is not None and hit[0] is spec: return hit[1]
    P0 = _seam_xy(spec); C0 = [tuple(v) for v in clean_ring(spec["cut_builtin"])]
    m = [min(range(len(P0)), key=lambda i: (P0[i][0] - c[0]) ** 2 + (P0[i][1] - c[1]) ** 2) for c in C0]
    if len(_FOLLOW) > 512: _FOLLOW.clear()                    # 일꾼 하나에서 쌓이지 않게
    _FOLLOW[id(spec)] = (spec, m)
    return m


def regrade_piece(spec, prules, table, si):
    """기준 명세 + 조각 규칙 → si 번째 사이즈 명세(점 수·속성은 기준과 같고 자리만 옮긴다)
       prules["seam_orig"] 가 있으면(화면에서 재봉선 규칙을 바꾼 판) 재단선은 «원래 규칙대로 옮긴 자리 + 재봉선이 더 움직인 양»"""
    out = copy.deepcopy(spec)
    P0 = _seam_xy(spec); P1 = _move(P0, True, prules["seam"], table, si)
    for k, s in enumerate(out["seam"]):
        s["x"], s["y"] = P1[k]
        nt = s.get("notch")
        if nt:                                               # 노치 방향은 재봉선 접선과 이루는 각을 지킨다
            rot = _tangent(P1, k) - _tangent(P0, k); u = nt["dir"]
            c, sn = math.cos(rot), math.sin(rot); v = (u[0] * c - u[1] * sn, u[0] * sn + u[1] * c); m = math.hypot(*v)
            nt["dir"] = [v[0] / m, v[1] / m]
    C0 = [tuple(v) for v in clean_ring(spec["cut_builtin"])]
    C1 = _move(C0, True, prules["cut"], table, si)
    if prules.get("seam_orig"):                                # 재봉선 규칙을 바꾼 판 — 바뀐 양만큼 재단선이 따라간다
        Pold = _move(P0, True, prules["seam_orig"], table, si)
        dl = [(P1[k][0] - Pold[k][0], P1[k][1] - Pold[k][1]) for k in range(len(P0))]
        if any(abs(a) > 1e-9 or abs(b) > 1e-9 for a, b in dl):
            fm = _follow_map(spec)
            C1 = [(c[0] + dl[fm[j]][0], c[1] + dl[fm[j]][1]) for j, c in enumerate(C1)]
    out["cut_builtin"] = [list(v) for v in C1]
    for j, d in enumerate(out["internal"]):
        d["pts"] = [list(v) for v in _move([tuple(v) for v in spec["internal"][j]["pts"]], bool(d.get("closed")),
                                           prules["internal"][j], table, si)]
    gj = (spec.get("meta") or {}).get("grain_line")
    if gj is not None and out.get("grain"):
        Pg = out["internal"][gj]["pts"]; out["grain"] = dict(out["grain"], **{"from": list(Pg[0]), "to": list(Pg[-1])})
    return out


def regrade(base_specs, rules, size):
    si = rules["sizes"].index(size)
    return {n: regrade_piece(sp, rules["pieces"][n], rules["rules"], si) for n, sp in base_specs.items()}


# ════════ ⑥ 검산 — 다시 만든 사이즈 ↔ 원본 CAD 사이즈 (매칭 결과를 쓰지 않고 원본만 다시 읽어 잰다) ════════
def _haus(A, B, closed):
    """두 선의 하우스도르프 거리(mm) — 같은 자리 중복 점을 빼고 잰다(중복 점이 있으면 GEOS 가 NaN 을 낸다, 실측)"""
    A = _dedupe(A, closed)[0]; B = _dedupe(B, closed)[0]
    mk = (lambda q: Polygon(q).exterior) if closed else LineString
    if len(A) < 2 or len(B) < 2: return 0.0 if len(A) == len(B) and (not A or math.dist(A[0], B[0]) < 1e-9) else float(math.dist(A[0], B[0]))
    return float(mk(A).hausdorff_distance(mk(B)))


def check_piece(spec, prules, orig, size=None):
    """spec = 규칙으로 다시 만든 조각 명세 · orig = 원본 .ai 의 그 사이즈 옛 형식 조각 · size = 그 사이즈 이름.
       원본에서 빼는 것은 들여올 때 «결함» 으로 적어 둔 사이즈(meta.dropped)의 되돌이 점뿐이다 — 나머지 사이즈는 원본 그대로 잰다"""
    orig, dropped = clean_piece(orig, size in ((spec.get("meta") or {}).get("dropped") or {}))
    so = from_legacy(orig); T = _seam_xy(so); m = len(T)
    Tn = [T[k] for k in _notch_idx(so)]
    Tt = [T[i] for i in range(m) if _angle(T, i, True) > TURN_RELAX]
    P = _seam_xy(spec); ext = Polygon(T).exterior
    r = {"knot": 0.0, "curve": 0.0, "shape": 0.0, "cut": 0.0, "cut_knot": 0.0, "internal": 0.0, "span": 0.0,
         "notch_count": [len(_notch_idx(spec)), len(Tn)]}
    for k in prules["seam"]:
        q = P[k["i"]]
        if k["kind"] == "notch": e = min(math.dist(q, t) for t in Tn) if Tn else 99.0
        elif k["kind"] == "turn": e = min(math.dist(q, t) for t in Tt) if Tt else 99.0
        else: e = None
        if e is None: r["curve"] = max(r["curve"], ext.distance(Point(q)))
        else: r["knot"] = max(r["knot"], e)
    r["shape"] = _haus(P, T, True)
    # 특징점 사이 변 길이 — 원본의 가장 가까운 같은 자리 사이 길이와 비교(맞물림에 직접 걸리는 값)
    feats = [k["i"] for k in prules["seam"] if k["kind"] in ("turn", "notch")]
    if len(feats) >= 2:
        near = lambda q: min(range(m), key=lambda i: math.dist(T[i], q))
        for a, b in zip(feats, feats[1:] + feats[:1]):
            la = cad_view.path_len(P, a, b); ta, tb = near(P[a]), near(P[b])
            lb = cad_view.path_len(T, ta, tb) if ta != tb else 0.0
            if ta != tb: r["span"] = max(r["span"], abs(la - lb))
    C = [tuple(v) for v in spec["cut_builtin"]]; CO = [tuple(v) for v in clean_ring(orig["cut"])]
    r["cut"] = _haus(C, CO, True)
    COt = [CO[i] for i in range(len(CO)) if _angle(CO, i, True) > TURN_RELAX]
    for k in prules["cut"]:
        if k["kind"] == "turn" and COt: r["cut_knot"] = max(r["cut_knot"], min(math.dist(C[k["i"]], t) for t in COt))
    if len(spec["internal"]) != len(orig["draw"]): r["internal"] = 99.0
    else:
        for d, o in zip(spec["internal"], orig["draw"]):
            a, b = [tuple(v) for v in d["pts"]], [tuple(v) for v in o["pts"]]
            if len(a) < 2 or len(b) < 2: continue
            r["internal"] = max(r["internal"], _haus(a, b, bool(d.get("closed"))))
    # 🚫 NaN 은 «통과» 로 새지 않게 실패 값으로 — max()·<= 비교는 NaN 을 조용히 넘긴다
    r = {k: ((99.0 if math.isnan(v) else round(v, 4)) if isinstance(v, float) else v) for k, v in r.items()}
    r["ok"] = (r["knot"] <= TOL_KNOT and r["cut_knot"] <= TOL_KNOT and r["shape"] <= TOL_SHAPE and r["curve"] <= TOL_SHAPE
               and r["cut"] <= TOL_SHAPE and r["internal"] <= TOL_SHAPE and r["span"] <= TOL_SHAPE
               and r["notch_count"][0] == r["notch_count"][1])
    if dropped: r["dropped"] = dropped                       # 원본에서 뺀 되돌이 점(있을 때만)
    return r


def check_all(base_specs, rules, src):
    """13사이즈 전부 — {사이즈: {조각: 결과}} + 요약(최대값)"""
    res, worst = {}, {"knot": 0.0, "curve": 0.0, "shape": 0.0, "cut": 0.0, "cut_knot": 0.0, "internal": 0.0, "span": 0.0}
    bad = []
    for s in rules["sizes"]:
        specs = regrade(base_specs, rules, s); res[s] = {}
        for n, sp in specs.items():
            on = (base_specs[n].get("meta") or {}).get("source_note") or n   # 이름을 고친 판 — 원본 .ai 에서는 원래 이름(%AI3_Note)으로 찾는다
            c = check_piece(sp, rules["pieces"][n], src["pieces"][s][on], s); res[s][n] = c
            for k in worst: worst[k] = max(worst[k], c[k])
            if not c["ok"]: bad.append(f"{s} {n}")
    return {"tol": {"knot": TOL_KNOT, "shape": TOL_SHAPE}, "max": {k: round(v, 4) for k, v in worst.items()},
            "ok": not bad, "bad": bad, "sizes": res}


# ════════ ⑦ 화면용 view.json (cad_view.py 와 같은 꼴) ════════
def build_view(style, sizes_specs, base, check, files, zinfo=None):
    names = style["pieces"]
    mm = {s: {n: cad_view.piece_mm(sizes_specs[s][n]) for n in names} for s in style["sizes"]}
    ub = {}
    for n in names:
        boxes = [cad_view.bbox(mm[s][n]["cut"]) for s in style["sizes"]]
        ub[n] = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    # 자리 순서의 동점 가르기는 «원래 이름» 으로 — 이름을 고쳐도 조각 자리가 그대로여야 «모양 같음» 을 점 하나까지 견줄 수 있다
    src_nm = lambda n: str((sizes_specs[style["sizes"][0]][n].get("meta") or {}).get("source_note") or n)
    order = sorted(names, key=lambda n: (-(ub[n][3] - ub[n][1]), src_nm(n)))
    place, x, y, rowh = {}, 0.0, 0.0, 0.0
    for n in order:
        w, h = ub[n][2] - ub[n][0], ub[n][3] - ub[n][1]
        if x > 0 and x + w > cad_view.SHEET_W: x, y, rowh = 0.0, y + rowh + cad_view.GAP, 0.0
        place[n] = (x - ub[n][0], y - ub[n][1]); x += w + cad_view.GAP; rowh = max(rowh, h)
    sheet = [0, 0, cad_view.q(max(place[n][0] + ub[n][2] for n in names)), cad_view.q(max(place[n][1] + ub[n][3] for n in names))]
    out_sizes = {}
    for s in style["sizes"]:
        pcs = []
        for n in order:
            p = cad_view.shift_piece(mm[s][n], *place[n]); sp = sizes_specs[s][n]
            g = sp.get("grain")
            p["grain"] = [(g["from"][0] + place[n][0], -g["from"][1] + place[n][1]), (g["to"][0] + place[n][0], -g["to"][1] + place[n][1])] \
                if g and g.get("from") else cad_view.grain_of(p["seam"])
            vp = cad_view.pack(p); meta = sp.get("meta") or {}
            vp.update(name=n, en=meta.get("en_name"), qty=int(meta.get("qty") or 1), instances=[],
                      seam_len=round(sum(math.dist(p["seam"][k], p["seam"][(k + 1) % len(p["seam"])]) for k in range(len(p["seam"]))), 1))
            pcs.append(vp)
        cs = check["sizes"].get(s, {})
        out_sizes[s] = {"label": s, "pieces": pcs, "checks": [], "measures": None,
                        "import_check": {"ok": all(c["ok"] for c in cs.values()),
                                         "max_knot": max((c["knot"] for c in cs.values()), default=0.0),
                                         "max_shape": max((max(c["shape"], c["cut"]) for c in cs.values()), default=0.0)}}
    return {"format": cad_view.FORMAT, "version": cad_view.FORMAT_VERSION, "unit": "mm", "q": cad_view.Q,
            "simplify": cad_view.SIMPLIFY, "y_down": True,
            "style": {"id": style["id"], "name": style["name"], "garment": style.get("garment"), "group": style.get("group"),
                      "base_size": base, "sizes": style["sizes"], "size_labels": {s: s for s in style["sizes"]},
                      "graded_from": base, "pieces": order, "imported": True},
            "source": {"engine": "stizshop tools/pattern-engine (style_import)", "commit": cad_view.git_head(),
                       "made_at": style["made_at"], "inputs": [style["source_file"]],
                       "note": "OptiCad 원본 → 규칙표로 다시 만든 사이즈. 기준점 이름은 임시(조각명_P1…) — 확인필요.md"},
            "sheet": sheet, "sizes": out_sizes, "files": files, "exports_zip": zinfo, "tol_check": cad_view.TOL_CHECK}


# ════════ ⑧ 확인 필요 목록 ════════
def confirm_md(style, confs, check, src):
    L = [f"# 확인 필요 — {style['name']} ({style['id']})", "",
         f"- 원본: `{style['source_file']}` · 사이즈 {len(style['sizes'])}개({' '.join(style['sizes'])}) · 기준 {style['base_size']}"
         f" · CAD 글자가 든 사이즈(Sample Size 추정) {src['sample']}",
         f"- {'원본 대조(규칙을 바꾼 판이라 원본과 다른 것이 정상일 수 있다)' if style.get('rules_changed') else '검산'}: "
         f"{'통과' if check['ok'] else '실패'} — 그레이드 점 최대 {check['max']['knot']}mm(허용 {TOL_KNOT}) · "
         f"재봉선 모양 최대 {check['max']['shape']}mm · 재단선 최대 {check['max']['cut']}mm · 안쪽선 최대 {check['max']['internal']}mm"
         f"(허용 {TOL_SHAPE}) · 변 길이 최대 {check['max']['span']}mm",
         "", "아래 이름은 **자동으로 붙인 임시 이름**이다. 맞는 이름(예: 겨드랑이·목옆)으로 고치면 그레이딩 화면·검산표에 그대로 쓰인다.", ""]
    if style["sample"] and style["sample"] != style["base_size"]:
        L.insert(4, f"- ⚠️ 기준 사이즈({style['base_size']})가 CAD 글자 사이즈({style['sample']})와 다르다 — 의도한 것인지 확인")
    for c in confs:
        x = "x" if c.get("confirmed") else " "               # 사람이 «확인함» 을 누른 조각(이름 확인 화면)
        done = f" — 확인함 {c.get('confirmed_at') or ''}".rstrip() if c.get("confirmed") else ""   # 누가 = 묶음(공장 전달)에 안 넣는다
        L.append(f"## {c['piece']}{done}")
        for t in c["notes"]: L.append(f"- [{x}] {t}")
        L.append(f"- [{x}] 기준점 {len(c['points'])}개 이름 확인")
        for t in c["points"]: L.append(f"  - {t}")
        L.append("")
    if check["bad"]:
        L.append("## 검산 실패"); L += [f"- {b}" for b in check["bad"]]
    return "\n".join(L) + "\n"


# ════════ ⑨ 통째로 — 서버(service.py)가 부를 함수 ════════
STYLE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def default_style_id(path):
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    s = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    if not s:                                                 # 한글뿐인 파일 이름 — 지문 앞 8자리
        with open(path, "rb") as f: s = "style-" + hashlib.sha256(f.read()).hexdigest()[:8]
    return s[:64]


def _r4(o):
    """파일에 쓸 때 좌표를 0.0001mm 로 줄인다(크기 절반 — 모양 차이는 0.00005mm 이하)"""
    if isinstance(o, float): return round(o, 4)
    if isinstance(o, dict): return {k: _r4(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_r4(v) for v in o]
    return o


def _dump(path, obj, compact=False):
    obj = _r4(obj)
    with open(path, "w", encoding="utf-8") as f:
        if compact: json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else: json.dump(obj, f, ensure_ascii=False, indent=1)


def _safe_name(s, n=120):
    """원본 파일 이름 기록용 — 경로·제어 문자 빼고 길이 자르기(화면·Content-Disposition 에 쓰인다)"""
    s = os.path.basename(str(s or "").replace("\\", "/"))
    return "".join(c for c in s if c.isprintable() and c not in '<>"')[:n] or "source.ai"


def import_style(path, base="M", style_id=None, out=None, name=None, dxf=False, write=True, source_name=None, progress=None):
    """OptiCad .ai → 스타일 묶음. 돌려주는 값 {"style", "rules", "base_specs", "check", "confirm", "confirm_doc", "paths", "summary"}
       write=False 면 파일을 쓰지 않는다(시험·서버 미리보기)
       source_name: 원본의 원래 파일 이름(서버는 올린 파일을 영문 이름으로 저장하므로 따로 넘긴다) · progress(단계): 진행률 알림"""
    step = progress or (lambda _s: None)
    if not os.path.isfile(path): raise StyleImportError(f"원본 파일이 없다: {path}")
    style_id = style_id or default_style_id(path)
    if not STYLE_ID_RE.match(style_id): raise StyleImportError(f"style_id 는 영문 소문자·숫자·- 만 (64자 안): {style_id!r}")
    step("read")
    src = read_ai(path); sizes = src["sizes"]
    if base not in sizes: raise StyleImportError(f"기준 사이즈 {base} 가 원본에 없다 — 있는 사이즈: {' '.join(sizes)}")
    if len(sizes) < 2:                                       # 규칙은 «사이즈 사이 이동량» 이라 사이즈 하나로는 읽을 것이 없다(전부 0 규칙 = 거짓 통과)
        raise StyleImportError(f"사이즈가 하나({sizes[0]})라 그레이딩 규칙을 읽을 수 없다 — 여러 사이즈가 레이어로 든 CAD 파일을 넣을 것")
    names = src["names"]
    for s in sizes:
        if set(src["pieces"][s]) != set(names):
            miss = set(names) ^ set(src["pieces"][s])
            raise StyleImportError(f"사이즈 {s} 의 조각이 기준과 다르다: {', '.join(sorted(map(str, miss)))}")
    step("pieces")
    base_specs, raw, confs = {}, {}, []
    for n in names:
        sb, rr, conf = import_piece(n, {s: src["pieces"][s][n] for s in sizes}, base, sizes, src["qty"])
        base_specs[n] = sb; raw[n] = rr; confs.append(conf)
    rules, R = build_rules(style_id, base, sizes, raw)
    # 파일(spec_base.json)에 쓰는 0.0001mm 반올림을 «먼저» 한다 — 그래야 이 판의 사이즈·화면 자료가 파일로 다시 만든 것과
    #   점 하나까지 같다(이름만 고친 다음 판이 «모양 같음» 을 0.01mm 정수까지 견줄 수 있게 · 2026-10-20 실측: 안 하면 78곳이 1칸 달랐다)
    base_specs = {n: _r4(sp) for n, sp in base_specs.items()}
    for n, sp in base_specs.items():
        errs = validate(sp)
        if errs: raise StyleImportError(f"{n} 명세 검사 실패: {errs[:3]}")
    step("verify")
    check = check_all(base_specs, rules, src)
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    style = {"id": style_id, "name": name or src["style"] or style_id, "base_size": base, "sizes": sizes, "pieces": names,
             "sample": src["sample"], "source_file": _safe_name(source_name or path), "made_at": when, "garment": None, "group": None}
    nk = {n: len(rules["pieces"][n]["seam"]) for n in names}
    summary = {"style_id": style_id, "pieces": len(names), "sizes": len(sizes), "seam_knots": nk,
               "seam_knots_total": sum(nk.values()), "rules": len(rules["rules"]), "check_ok": check["ok"], "check_max": check["max"]}
    result = {"style": style, "rules": rules, "base_specs": base_specs, "check": check, "confirm": confs,
              "confirm_doc": confirm_doc(style, confs, base_specs), "summary": summary, "paths": {}, "_R": R, "_src": src}
    if write:
        step("bundle")
        result["paths"] = write_bundle(result, path, out or os.path.join(REPO, "tmp", "pattern-engine", "style-import", style_id), dxf)
    for k in ("_R", "_src", "_sizes_specs"): result.pop(k, None)
    return result


ZIP_TIME = cad_view.ZIP_TIME


def write_bundle(res, src_path, out, dxf=False):
    """묶음 쓰기 → {이름: 경로}. ZIP 안 이름은 영문·숫자뿐(07-09 한글 열쇠 사고)"""
    style, rules, base_specs, check = res["style"], res["rules"], res["base_specs"], res["check"]
    os.makedirs(os.path.join(out, "specs"), exist_ok=True)
    P = {"spec_base": os.path.join(out, "spec_base.json"), "rules": os.path.join(out, "rules.json"),
         "rul": os.path.join(out, "rules.rul"), "check": os.path.join(out, "check.json"),
         "confirm": os.path.join(out, "confirm.md"), "names": os.path.join(out, "confirm.json"),
         "view": os.path.join(out, "view.json"), "zip": os.path.join(out, "exports.zip")}
    _dump(P["spec_base"], {"format": FORMAT_BASE, "version": FORMAT_VERSION, "style": style, "pieces": base_specs}, compact=True)
    _dump(P["rules"], rules)
    res["_R"].write(P["rul"], style["id"].upper(), style["base_size"], datetime.datetime.now())
    _dump(P["check"], check)
    with open(P["confirm"], "w", encoding="utf-8") as f: f.write(confirm_md(style, res["confirm"], check, res["_src"]))
    _dump(P["names"], res.get("confirm_doc") or confirm_doc(style, res["confirm"], base_specs))   # 이름 확인 화면용(구조 자료)
    sizes_specs = {}
    for s in style["sizes"]:
        sizes_specs[s] = regrade(base_specs, rules, s)
        _dump(os.path.join(out, "specs", f"spec_{s}.json"), {"format": "stiz-style-size", "size": s, "pieces": sizes_specs[s]}, compact=True)
    res["_sizes_specs"] = sizes_specs                           # 재생성 검산(regen_check)이 다시 계산하지 않게
    extra = []
    if dxf:                                                  # (선택) 사이즈별 공장용 .ai · 1:1 PDF · DXF — patlib.export (글꼴 맑은 고딕 필요)
        import patlib
        for s in style["sizes"]:
            d = os.path.join(out, "dxf", s); os.makedirs(d, exist_ok=True)
            patlib.export(patlib.spec_instances(sizes_specs[s]), f"{style['id']}_{s}", style["name"], [], d, size=s)
            for fn in sorted(os.listdir(d)):
                if fn.endswith((".dxf", ".pdf", ".ai")):
                    extra.append((os.path.join(d, fn), f"sizes/{s}/{fn.replace('1대1', '1to1')}"))
    entries = [(P["spec_base"], "spec_base.json"), (P["rules"], "rules.json"), (P["rul"], "rules.rul"),
               (P["check"], "check.json"), (P["confirm"], "confirm.md"), (P["names"], "confirm.json")]
    entries += [(os.path.join(out, "specs", f"spec_{s}.json"), f"specs/spec_{s}.json") for s in style["sizes"]]
    entries += [(src_path, "source/original.ai")] + extra
    files = []
    for fp, zn in entries:
        assert all(c.isascii() for c in zn), zn
        kind, size = file_kind(zn)
        f = {"kind": kind, "path": zn, "orig": style.get("source_file") if kind == "source" else os.path.basename(fp),
             "bytes": os.path.getsize(fp), "sha256": cad_view.sha256(fp)}
        if size: f["size"] = size
        files.append(f)
    with zipfile.ZipFile(P["zip"], "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for (fp, zn) in entries:
            zi = zipfile.ZipInfo(zn, ZIP_TIME); zi.compress_type = zipfile.ZIP_DEFLATED
            with open(fp, "rb") as fh: z.writestr(zi, fh.read())
        zi = zipfile.ZipInfo("manifest.json", ZIP_TIME); zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, json.dumps({"style_id": style["id"], "made_at": style["made_at"], "files": files}, ensure_ascii=False, indent=1))
    zinfo = {"name": "exports.zip", "sha256": cad_view.sha256(P["zip"]), "bytes": os.path.getsize(P["zip"])}
    _dump(P["view"], build_view(style, sizes_specs, style["base_size"], check, files, zinfo), compact=True)
    return P


# ════════ ⑩ 들여온 스타일 다시 묶기 — 이름 고치기 · 규칙 바꿔 다시 그레이딩 · 마커용 펼침표 (F10 6단계 서버 연결) ════════
#   왜: 들여온 스타일은 «원본 .ai + 기준 명세 + 규칙표» 가 정본이다(묶음 ZIP 안에 셋 다 있다).
#       이름을 고치든 규칙을 바꾸든 «그 셋으로 13사이즈를 다시 만들어» 새 묶음을 쓴다 — 원본 대조 검산도 같이 다시 한다.
FORMAT_CONFIRM = "stiz-style-confirm"
_KIND_FIXED = {"spec_base.json": "spec_base", "rules.json": "rules", "rules.rul": "rul", "check.json": "check",
               "confirm.md": "confirm", "confirm.json": "names", "source/original.ai": "source"}


def file_kind(zn):
    """ZIP 안 이름 → (종류, 사이즈) — 그레이더 내려받기 종류(FILE_KINDS)와 같은 낱말.
       specs/spec_M.json → ("spec", "M") · sizes/M/x.dxf → ("dxf", "M") · 그 밖은 위 표"""
    if zn in _KIND_FIXED: return _KIND_FIXED[zn], None
    m = re.fullmatch(r"specs/spec_([A-Za-z0-9]+)\.json", zn)
    if m: return "spec", m.group(1)
    m = re.fullmatch(r"sizes/([A-Za-z0-9]+)/[^/]+\.(dxf|pdf|ai)", zn)
    if m: return m.group(2), m.group(1)
    return os.path.splitext(zn)[1].lstrip(".") or "file", None


def confirm_doc(style, confs, base_specs):
    """확인 필요 목록 → 이름 확인 화면용 구조 자료(confirm.json). 조각마다 «확인함» 표시가 있다(처음엔 모두 확인 전)"""
    pieces = []
    for c in confs:
        m = base_specs[c["piece"]].get("meta") or {}
        pieces.append({"piece": c["piece"], "source_note": m.get("source_note", c["piece"]), "en_name": m.get("en_name"),
                       "qty": int(m.get("qty") or 1), "qty_read": m.get("qty_read"), "symmetric": bool(m.get("symmetric")),
                       "mirror": bool(m.get("mirror", True)), "notes": list(c.get("notes") or []),
                       "points": list(c.get("points_data") or []), "confirmed": bool(c.get("confirmed")),
                       "confirmed_by": c.get("confirmed_by"), "confirmed_at": c.get("confirmed_at")})
    return {"format": FORMAT_CONFIRM, "version": 1, "style_id": style["id"], "base_size": style["base_size"],
            "sample": style.get("sample"), "pieces": pieces}


def confs_from_doc(doc):
    """confirm.json → confirm_md 가 받는 목록(points 는 글자 한 줄씩)"""
    return [dict(c, points=[_point_line(d) for d in c.get("points") or []], points_data=c.get("points") or []) for c in doc["pieces"]]


def _doc_from_specs(style, base_specs, rules):
    """옛 묶음(confirm.json 없음)용 — 명세·규칙에서 기준점 목록만 다시 만든다(메모 없음)"""
    confs = []
    for n, sp in base_specs.items():
        P = _seam_xy(sp)
        data = [{"name": k.get("name"), "kind": k["kind"], "where": _where(P, P[k["i"]]),
                 "x": round(P[k["i"]][0], 1), "y": round(P[k["i"]][1], 1)} for k in rules["pieces"][n]["seam"]]
        confs.append({"piece": n, "notes": [], "points_data": data})
    return confirm_doc(style, confs, base_specs)


def expand_table(specs):
    """명세 묶음 → 마커 펼침표 {원본이름: [[조각이름, 거울?, 좌우, 메모], …]} — patlib.spec_instances 와 같은 규칙
       (장수 1 = 그대로 · 2장 이상 = 1·2·3… 짝수 번째는 좌우 뒤집음 — meta.mirror=False 면 뒤집지 않고 같은 모양 n장)"""
    out = {}
    for base, sp in specs.items():
        m = sp.get("meta") or {}; qty = int(m.get("qty") or 1); mir = bool(m.get("mirror", True))
        if qty <= 1:
            out[base] = [[base, False, "", ""]]
        else:
            out[base] = [[f"{base} {j + 1}", bool(mir and j % 2), (("R" if j % 2 == 0 else "L") if mir else ""), f"{qty}장 중 {j + 1}"]
                         for j in range(qty)]
    return out


def rules_obj(rules):
    """rules.json → aama.Rules(RUL 쓰기용) — 번호 순서 그대로"""
    R = aama.Rules(rules["sizes"]); R.order, R.table = [], {}
    for n, row in enumerate(rules["rules"]):
        key = tuple((float(v[0]) + 0.0, float(v[1]) + 0.0) for v in row)
        R.order.append(key); R.table.setdefault(key, n)
    return R


def apply_rule_changes(rules, changes):
    """화면 규칙 변경 {조각: {기준점이름: {사이즈: [Δx, Δy]}}}(바꾼 칸만·최종 값, 기준 사이즈 대비 · y 위 +) → (새 rules, 바뀐 칸 목록)
       바꾼 기준점은 새 규칙 번호를 받는다(같은 이동량 줄이 이미 있으면 그 번호) — 같은 규칙을 쓰던 다른 점은 안 움직인다.
       처음 바꿀 때 그 조각의 «원래 재봉선 규칙» 을 seam_orig 에 남긴다 → regrade_piece 가 재단선을 «바뀐 양» 만큼 따라 옮긴다"""
    out = copy.deepcopy(rules); T = out["rules"]; sizes = out["sizes"]; base = out["base_size"]
    index = {}
    for n, row in enumerate(T): index.setdefault(tuple(tuple(float(a) for a in v) for v in row), n)
    diff = []
    if not isinstance(changes, dict): raise StyleImportError("규칙 변경은 {조각: {기준점: {사이즈: [Δx, Δy]}}} 모양이어야 한다")
    for pc, pts in changes.items():
        pr = out["pieces"].get(pc)
        if pr is None or not isinstance(pts, dict): raise StyleImportError(f"없는 조각: {str(pc)[:40]}")
        orig_seam = copy.deepcopy(pr["seam"]); touched = False
        byname = {k.get("name"): k for k in pr["seam"]}
        for nm, bys in pts.items():
            k = byname.get(nm)
            if k is None or not isinstance(bys, dict): raise StyleImportError(f"{pc} 에 «{str(nm)[:30]}» 기준점이 없다")
            row = [[float(a) for a in v] for v in T[k["rule"]]]; changed = False
            for s, v in bys.items():
                if s not in sizes: raise StyleImportError(f"모르는 사이즈: {str(s)[:20]}")
                ok = isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(a, (int, float)) and not isinstance(a, bool)
                                                                          and math.isfinite(a) for a in v)
                if not ok: raise StyleImportError(f"{pc} {nm} {s} 값은 숫자 두 개 [Δx, Δy] 여야 한다")
                dx, dy = round(float(v[0]), 2) + 0.0, round(float(v[1]), 2) + 0.0
                if abs(dx) > 400 or abs(dy) > 400: raise StyleImportError(f"{pc} {nm} {s} 이동량이 너무 크다(±400mm)")
                if s == base and (dx or dy): raise StyleImportError(f"기준 사이즈({base})는 움직이지 않는다 — {pc} {nm}")
                j = sizes.index(s); old = row[j]
                if abs(old[0] - dx) > 0.005 or abs(old[1] - dy) > 0.005:
                    diff.append({"piece": pc, "point": nm, "size": s, "from": [round(old[0], 2), round(old[1], 2)], "to": [dx, dy]})
                    row[j] = [dx, dy]; changed = True
            if changed:
                key = tuple(tuple(v) for v in row); n = index.get(key)
                if n is None: T.append(row); n = len(T) - 1; index[key] = n
                k["rule"] = n; touched = True
        if touched and not pr.get("seam_orig"): pr["seam_orig"] = orig_seam   # 맨 처음 원본 규칙만(두 번째 바꿀 때도 «원본 대비» 로 따라간다)
    return out, diff


NAME_BAD = set('<>"/\\')


def apply_names(base_specs, rules, conf, style, changes, by=None, when=None):
    """이름 확인 화면의 변경 → (명세, 규칙, 확인 자료, 스타일, 바뀐 것 목록). 모양(좌표·규칙 번호)은 하나도 안 바꾼다.
       changes = {"pieces": {지금 조각 이름: {name, en_name, qty, mirror, points: {옛 기준점: 새 이름}, confirmed}}} — 서버가 먼저 검사한 것
       (service.check_names). 여기서는 «있는 조각·기준점인가 · 겹치지 않는가» 만 다시 본다(일꾼 안 두 번째 방어)."""
    when = when or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    ch_all = (changes or {}).get("pieces") or {}
    for cur in ch_all:
        if cur not in base_specs: raise StyleImportError(f"없는 조각: {str(cur)[:40]}")
    rename = {n: ((ch_all.get(n) or {}).get("name") or n) for n in base_specs}
    if len(set(rename.values())) != len(rename): raise StyleImportError("조각 이름이 겹친다 — 서로 다른 이름을 붙일 것")
    for n0, nn in rename.items():
        if nn == n0: continue                                # 안 고친 원본 이름(«FRONT/BACK» 등)은 검사하지 않는다 — «확인함» 만 눌러도 막히지 않게
        if not nn or len(nn) > 40 or any(c in NAME_BAD or not c.isprintable() for c in nn): raise StyleImportError(f"쓸 수 없는 조각 이름: {nn[:40]!r}")
    cmap = {c["piece"]: c for c in conf["pieces"]}
    specs2, prs2, confs2, log = {}, {}, [], []
    for n in base_specs:
        ch = ch_all.get(n) or {}
        sp = copy.deepcopy(base_specs[n]); pr = copy.deepcopy(rules["pieces"][n])
        c = copy.deepcopy(cmap.get(n) or {"piece": n, "notes": [], "points": [], "confirmed": False})
        meta = sp.setdefault("meta", {}); meta.setdefault("source_note", n)
        nn = rename[n]
        if nn != n:
            sp["name"] = nn; c["piece"] = nn; log.append({"piece": n, "field": "name", "from": n, "to": nn})
        pts = ch.get("points") or {}
        if pts:
            now = [k.get("name") for k in pr["seam"]]
            for old in pts:
                if old not in now: raise StyleImportError(f"{n} 에 «{str(old)[:30]}» 기준점이 없다")
            final = [pts.get(x, x) for x in now]
            if len(set(final)) != len(final): raise StyleImportError(f"{nn} 기준점 이름이 겹친다")
            for new in pts.values():
                if not new or len(new) > 30 or any(ch_ in NAME_BAD or not ch_.isprintable() for ch_ in new):
                    raise StyleImportError(f"쓸 수 없는 기준점 이름: {str(new)[:30]!r}")
            for lst in (pr["seam"], pr.get("seam_orig") or []):
                for k in lst: k["name"] = pts.get(k.get("name"), k.get("name"))
            for s_ in sp["seam"]:
                if s_.get("node") in pts: s_["node"] = pts[s_["node"]]
            for d in c.get("points") or []: d["name"] = pts.get(d.get("name"), d.get("name"))
            log += [{"piece": nn, "field": "point", "from": o, "to": w} for o, w in pts.items() if o != w]
        for key, dflt in (("en_name", None), ("qty", 1), ("mirror", True)):
            if key in ch and ch[key] is not None:
                val = (ch[key] or None) if key == "en_name" else ch[key]
                old = meta.get(key, dflt)
                if old != val:
                    meta[key] = val; c[key] = val; log.append({"piece": nn, "field": key, "from": old, "to": val})
        if ch.get("confirmed") is not None and bool(ch["confirmed"]) != bool(c.get("confirmed")):
            # 누가 눌렀는지(직원 이메일)는 공장에 가는 묶음(confirm.json)에 넣지 않는다 — 바뀐 것 목록(서버 meta 에만 남는다)에만
            c["confirmed"] = bool(ch["confirmed"]); c["confirmed_by"] = None
            c["confirmed_at"] = when if c["confirmed"] else None
            log.append({"piece": nn, "field": "confirmed", "from": not c["confirmed"], "to": c["confirmed"], "by": by})
        specs2[nn] = sp; prs2[nn] = pr; confs2.append(c)
    return specs2, dict(rules, pieces=prs2), dict(conf, pieces=confs2), dict(style, pieces=list(specs2)), log


REGEN_DEF = [("valid", "명세 검사(문제 수)", 0.0), ("twist", "재봉선 꼬임(조각 수)", 0.0),
             ("cover", "재단선 밖 재봉선(mm)", TOL_SHAPE), ("echo", "규칙과 기준점 차(mm)", 0.01), ("notch", "노치 수 차", 0.0)]


def regen_check(base_specs, rules, sizes_specs):
    """재생성 검산 — 기준 명세 + 규칙표로 다시 만든 사이즈가 «옷본으로 성립하나» (원본 .ai 와 견주는 것이 아니다)
       valid 명세 검사 · twist 재봉선이 스스로 꼬였나 · cover 재봉선이 재단선 밖으로 나갔나(기준 사이즈보다 더) ·
       echo 재봉선 기준점이 규칙대로 옮겨졌나 · notch 노치 수가 기준과 같은가
       → {"ok", "sizes": {사이즈: [{key, label, value, target, tol, ok}]}} (그레이더 «맞물림» 표와 같은 꼴 — 화면·저장 조건을 같이 쓴다)"""
    import shapely
    T = rules["rules"]; sizes = rules["sizes"]; out, all_ok = {}, True

    def cover_mm(sp):
        C = clean_ring(sp["cut_builtin"]); cp = Polygon(C).buffer(0)
        P = _dedupe(_seam_xy(sp), True)[0]
        pts = shapely.points([list(q) for q in P])
        inside = shapely.covers(cp, pts)
        outs = [q for q, ok in zip(pts, inside) if not ok]
        return max((cp.boundary.distance(q) for q in outs), default=0.0)   # boundary — 꼬인 재단선은 buffer(0) 뒤 여러 조각(MultiPolygon)이 된다(실측)
    base_cover = {n: cover_mm(sp) for n, sp in base_specs.items()}
    base_twist = {n: not Polygon(_dedupe(_seam_xy(sp), True)[0]).is_valid for n, sp in base_specs.items()}
    base_notch = {n: len(_notch_idx(sp)) for n, sp in base_specs.items()}
    for j, s in enumerate(sizes):
        specs = sizes_specs[s]
        valid = sum(len(validate(sp)) for sp in specs.values())
        twist = sum(1 for n, sp in specs.items() if not Polygon(_dedupe(_seam_xy(sp), True)[0]).is_valid and not base_twist[n])
        cover = max((max(0.0, cover_mm(sp) - base_cover[n]) for n, sp in specs.items()), default=0.0)
        echo, notch = 0.0, 0
        for n, sp in specs.items():
            P0, P1 = _seam_xy(base_specs[n]), _seam_xy(sp)
            for k in rules["pieces"][n]["seam"]:
                d = T[k["rule"]][j]; i = k["i"]
                echo = max(echo, abs(P1[i][0] - P0[i][0] - d[0]), abs(P1[i][1] - P0[i][1] - d[1]))
            notch += abs(len(_notch_idx(sp)) - base_notch[n])
        rows = []
        for key, label, tol in REGEN_DEF:
            v = {"valid": valid, "twist": twist, "cover": round(cover, 3), "echo": round(echo, 4), "notch": notch}[key]
            ok = v <= tol + 1e-9 and not (isinstance(v, float) and math.isnan(v))
            all_ok = all_ok and ok
            rows.append({"key": key, "label": label, "value": v, "target": 0.0, "tol": tol, "ok": ok})
        out[s] = rows
    return {"ok": all_ok, "sizes": out, "kind": "regen"}


def load_bundle(zip_path, work):
    """묶음 ZIP → (기준 명세 문서, 규칙, 확인 자료|None, 원본 .ai 주소) — 원본은 work 에 꺼낸다"""
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = set(z.namelist())
            for need in ("spec_base.json", "rules.json", "source/original.ai"):
                if need not in names: raise StyleImportError(f"들여온 묶음에 {need} 가 없다 — 들여온 스타일이 아니다")
            base_doc = json.loads(z.read("spec_base.json").decode("utf-8"))
            rules = json.loads(z.read("rules.json").decode("utf-8"))
            conf = json.loads(z.read("confirm.json").decode("utf-8")) if "confirm.json" in names else None
            os.makedirs(work, exist_ok=True); src_ai = os.path.join(work, "_source.ai")
            with open(src_ai, "wb") as f: f.write(z.read("source/original.ai"))
    except zipfile.BadZipFile:
        raise StyleImportError("묶음 ZIP 을 읽지 못했다")
    if base_doc.get("format") != FORMAT_BASE or rules.get("format") != FORMAT_RULES:
        raise StyleImportError("들여온 스타일 형식이 아니다(spec_base·rules 형식 다름)")
    if conf is not None and conf.get("format") != FORMAT_CONFIRM: conf = None
    return base_doc, rules, conf, src_ai


def restyle(zip_path, out, rule_changes=None, names=None, by=None, progress=None):
    """들여온 스타일 묶음(ZIP) → 이름·규칙을 바꿔 새 묶음(out). 원본 대조 검산·재생성 검산을 다시 한다.
       돌려주는 값 {"style", "rules", "base_specs", "check", "confirm_doc", "paths", "mesh", "rule_changes", "name_changes", "summary"}"""
    step = progress or (lambda _s: None)
    step("load")
    base_doc, rules, conf, src_ai = load_bundle(zip_path, out)
    base_specs = base_doc["pieces"]; style = dict(base_doc["style"])
    conf = conf or _doc_from_specs(style, base_specs, rules)
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    step("apply")
    name_log, diff = [], []
    if names:
        base_specs, rules, conf, style, name_log = apply_names(base_specs, rules, conf, style, names, by, when)
    if rule_changes:
        rules, diff = apply_rule_changes(rules, rule_changes)
    style["made_at"] = when
    if any(pr.get("seam_orig") for pr in rules["pieces"].values()): style["rules_changed"] = True
    step("verify")
    src = read_ai(src_ai)
    check = check_all(base_specs, rules, src)
    res = {"style": style, "rules": rules, "base_specs": base_specs, "check": check, "confirm": confs_from_doc(conf),
           "confirm_doc": conf, "_R": rules_obj(rules), "_src": src}
    step("bundle")
    res["paths"] = write_bundle(res, src_ai, out)
    res["mesh"] = regen_check(base_specs, rules, res["_sizes_specs"])
    res["rule_changes"] = diff; res["name_changes"] = name_log
    res["summary"] = {"style_id": style["id"], "pieces": len(base_specs), "sizes": len(style["sizes"]), "rules": len(rules["rules"]),
                      "check_ok": check["ok"], "check_max": check["max"], "regen_ok": res["mesh"]["ok"]}
    for k in ("_R", "_src", "_sizes_specs"): res.pop(k, None)
    try: os.remove(src_ai)
    except OSError: pass
    return res


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="OptiCad .ai(여러 사이즈) → 스타일 묶음(명세·규칙표·view·ZIP) + 확인 필요 목록")
    ap.add_argument("path"); ap.add_argument("--base", default="M"); ap.add_argument("--out")
    ap.add_argument("--style-id"); ap.add_argument("--name"); ap.add_argument("--dxf", action="store_true", help="사이즈별 .ai·1:1 PDF·DXF 도")
    a = ap.parse_args(argv)
    try:
        r = import_style(a.path, a.base, a.style_id, a.out, a.name, a.dxf)
    except StyleImportError as e:
        print(f"들여오기 실패: {e}"); return 2
    s = r["summary"]
    print(f"[{s['style_id']}] 조각 {s['pieces']} · 사이즈 {s['sizes']} · 재봉선 그레이드 점 {s['seam_knots_total']} · 규칙 {s['rules']}개")
    for n, k in s["seam_knots"].items(): print(f"   {n:10s} 그레이드 점 {k}")
    m = s["check_max"]
    print(f"검산 {'통과' if s['check_ok'] else '실패'} — 그레이드 점 {m['knot']}mm · 곡선 점 {m['curve']}mm · 모양 {m['shape']}mm"
          f" · 재단선 {m['cut']}mm · 안쪽선 {m['internal']}mm · 변 길이 {m['span']}mm")
    for k, v in r["paths"].items(): print(f"   {k}: {v}")
    return 0 if s["check_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
