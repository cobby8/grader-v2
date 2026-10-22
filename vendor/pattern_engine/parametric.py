# 치수표로 패턴 계산 — 파라메트릭 (차용 명세서 F9 · Seamly2D 의 «변수·수식» 방식)
#
#   치수표 JSON  {"values": {"chest": 1290, …}}              이름 → mm
#   스타일 JSON  inputs(치수 이름) · params(규칙 상수) · vars(수식) · points(점) · paths(선) · pieces(조각)
#     점·변수는 전부 «수식 문자열»이다 — 예 "chest/4"  "SP.y + sqrt(armhole_depth*armhole_depth - (CH - SP.x)*(CH - SP.x))"
#   → 조각마다 재봉선 점 목록 → piecespec 명세(seam 점 + node 이름 + sa) → compute_cut·to_legacy 를 그대로 탄다
#
#   왜 이렇게 하나: 지금 우리 패턴은 «점 좌표»만 있어 치수가 바뀌면 사람이 다시 그린다.
#   점을 «치수로 계산하는 식»으로 들고 있으면 치수표만 바꿔 넣어도 그 사람 패턴이 나온다(선수 개인 맞춤 등).
#
#   수식은 «안전한 계산기»로만 푼다 — eval 을 쓰지 않는다.
#     허용: 숫자 · 이름 · + − × ÷ · 괄호 · 부호(−x) · 점.x / 점.y
#           함수 min max sqrt abs sin cos tan(도 단위) · dist(점,점) · angle(점,점)(도) · length(선)
#     거부: 그 밖의 전부(** · 비교 · 문자열 · 속성 줄줄이 · import · 람다 · 목록 …) → FormulaError
#   순환 참조는 CycleError("순환 참조: A → B → A"), 없는 이름은 FormulaError("없는 이름 'x'").
#
#   좌표: x 오른쪽 · y 아래쪽(+) · mm. 반쪽으로 그리는 조각(mirror_x)은 x=0 이 중심선.
#   실행: python tools/pattern-engine/parametric.py <스타일.json> <치수표.json> [--set chest+=40 …] [--out 폴더]
import ast, math, json, os, sys, copy, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from piecespec import SPEC_VERSION, compute_cut, validate          # 명세 모델은 읽기·import 만 한다

MAX_EXPR_LEN = 400        # 식 글자 수 상한 — 이상하게 긴 식은 실수이거나 장난이다
MAX_EXPR_NODES = 200      # 식 마디 수 상한
JOIN_TOL = 1e-6           # 이 거리 안의 이웃 점은 같은 점으로 합친다(럭비 스크립트 mirror_full 과 같은 값)
NOTCH_ON_SEAM_TOL = 0.5   # 노치 자리가 재봉선에서 이만큼 넘게 떨어지면 오류(다른 조각 노치를 잘못 단 것)
MAX_DEPTH = 100           # 이름→이름 의존 사슬 상한 — 럭비 저지 실측 7단계. 파이썬은 약 150단계에서 RecursionError 로 죽는다


class FormulaError(ValueError):
    """수식·정의 오류 — 무엇이 어디서 틀렸는지 글로 알려 준다"""
    tagged = False


class CycleError(FormulaError):
    """A 를 계산하려면 B 가, B 를 계산하려면 A 가 필요한 경우"""
    tagged = True


class DepthError(FormulaError):
    """의존 사슬이 너무 깊은 경우 — A 가 B 를, B 가 C 를 … 100단계 넘게 부른다(대개 실수로 만든 긴 사슬)"""
    tagged = True


def _depth_error(chain, why=""):
    """«의존이 너무 깊다: A → B → C → … → Y → Z (n단계)» — 긴 사슬은 앞 3개·뒤 2개만 보인다"""
    shown = chain if len(chain) <= 6 else chain[:3] + ["…"] + chain[-2:]
    return DepthError(f"의존이 너무 깊다{why}: " + " → ".join(shown) + f" ({len(chain)}단계, 최대 {MAX_DEPTH})")


class Pt(tuple):
    """점 (x, y) — 수식 안에서는 P.x · P.y · dist · angle 로만 쓴다"""
    __slots__ = ()


class Path(list):
    """선(점 목록) — 수식 안에서는 length(선) 으로만 쓴다"""
    __slots__ = ()


# ════════════════ 안전한 계산기 ════════════════
def _num(v, expr):
    if isinstance(v, (Pt, Path)):
        raise FormulaError(f"점·선은 계산에 바로 못 쓴다 — 점.x / 점.y / length(선) 을 써라: {expr!r}")
    if not isinstance(v, float) or not math.isfinite(v):
        raise FormulaError(f"계산 결과가 유한한 숫자가 아니다: {expr!r}")
    return v


def _pt(v, expr):
    if not isinstance(v, Pt): raise FormulaError(f"점이 와야 할 자리에 점이 아닌 것: {expr!r}")
    return v


def _path(v, expr):
    if not isinstance(v, Path): raise FormulaError(f"선이 와야 할 자리에 선이 아닌 것: {expr!r}")
    return v


def _div(a, b, expr):
    if b == 0: raise FormulaError(f"0 으로 나눔: {expr!r}")
    return a / b


def _sqrt(a, expr):
    if a < 0: raise FormulaError(f"음수의 제곱근({a:.3f}) — 치수가 서로 맞지 않는다: {expr!r}")
    return math.sqrt(a)


def plen(P):
    return sum(math.dist(P[i - 1], P[i]) for i in range(1, len(P)))


# 함수 이름 → (인자 검사, 계산). 인자 종류: n=숫자 · p=점 · l=선 · * = 숫자 여러 개
_FUNCS = {
    "min": ("*", lambda e, *a: min(a)),
    "max": ("*", lambda e, *a: max(a)),
    "sqrt": ("n", lambda e, a: _sqrt(a, e)),
    "abs": ("n", lambda e, a: abs(a)),
    "sin": ("n", lambda e, a: math.sin(math.radians(a))),
    "cos": ("n", lambda e, a: math.cos(math.radians(a))),
    "tan": ("n", lambda e, a: math.tan(math.radians(a))),
    "dist": ("pp", lambda e, p, q: math.dist(p, q)),
    "angle": ("pp", lambda e, p, q: math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))),   # p → q 방향(도, y 아래쪽 좌표 그대로)
    "length": ("l", lambda e, l: plen(l)),
}


def _ev(node, lookup, expr):
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise FormulaError(f"숫자가 아닌 상수: {expr!r}")
        try: return float(v)
        except OverflowError: raise FormulaError(f"너무 큰 숫자: {expr!r}")
    if isinstance(node, ast.Name):
        if node.id in _FUNCS: raise FormulaError(f"함수 '{node.id}' 는 괄호로 불러야 한다: {expr!r}")
        return lookup(node.id)
    if isinstance(node, ast.Attribute):                                # 점.x / 점.y 만
        if not isinstance(node.value, ast.Name) or node.attr not in ("x", "y"):
            raise FormulaError(f"허용하지 않는 속성 «{node.attr}» — 점.x · 점.y 만 된다: {expr!r}")
        p = _pt(lookup(node.value.id), expr)
        return float(p[0] if node.attr == "x" else p[1])
    if isinstance(node, ast.BinOp):
        a = _num(_ev(node.left, lookup, expr), expr); b = _num(_ev(node.right, lookup, expr), expr)
        if isinstance(node.op, ast.Add): return a + b
        if isinstance(node.op, ast.Sub): return a - b
        if isinstance(node.op, ast.Mult): return a * b
        if isinstance(node.op, ast.Div): return _div(a, b, expr)
        raise FormulaError(f"허용하지 않는 연산 {type(node.op).__name__} — + − × ÷ 만 된다: {expr!r}")
    if isinstance(node, ast.UnaryOp):
        a = _num(_ev(node.operand, lookup, expr), expr)
        if isinstance(node.op, ast.USub): return -a
        if isinstance(node.op, ast.UAdd): return a
        raise FormulaError(f"허용하지 않는 부호 {type(node.op).__name__}: {expr!r}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            nm = node.func.id if isinstance(node.func, ast.Name) else type(node.func).__name__
            raise FormulaError(f"허용하지 않는 함수 '{nm}' — {', '.join(_FUNCS)} 만 된다: {expr!r}")
        if node.keywords: raise FormulaError(f"함수에 이름 붙인 인자는 안 된다: {expr!r}")
        kind, fn = _FUNCS[node.func.id]
        args = [_ev(a, lookup, expr) for a in node.args]
        if kind == "*":
            if not args: raise FormulaError(f"{node.func.id}() 에 인자가 없다: {expr!r}")
            args = [_num(a, expr) for a in args]
        else:
            if len(args) != len(kind): raise FormulaError(f"{node.func.id}() 인자 수 {len(args)} — {len(kind)}개여야: {expr!r}")
            chk = {"n": _num, "p": _pt, "l": _path}
            args = [chk[k](a, expr) for k, a in zip(kind, args)]
        return float(fn(expr, *args))
    raise FormulaError(f"허용하지 않는 식 요소 «{type(node).__name__}»: {expr!r}")


def evaluate(expr, lookup=None):
    """수식 하나를 푼다. lookup(이름) → 숫자 | Pt | Path. 결과는 무엇이든(점·선 이름 하나만 쓴 식이면 그 점·선)"""
    if lookup is None:
        def lookup(nm): raise FormulaError(f"없는 이름 '{nm}'")
    if isinstance(expr, bool): raise FormulaError(f"참/거짓은 수식이 아니다: {expr!r}")
    if isinstance(expr, (int, float)):
        return _num(float(expr), expr)
    if not isinstance(expr, str): raise FormulaError(f"수식은 글자나 숫자여야 한다: {expr!r}")
    if len(expr) > MAX_EXPR_LEN: raise FormulaError(f"식이 너무 길다({len(expr)}자)")
    try: tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError: raise FormulaError(f"식 문법 오류: {expr!r}")
    if sum(1 for _ in ast.walk(tree)) > MAX_EXPR_NODES: raise FormulaError(f"식이 너무 복잡하다: {expr!r}")
    return _ev(tree.body, lookup, expr)


def scalar(expr, lookup=None):
    """수식 → 숫자(점·선이면 오류)"""
    return _num(evaluate(expr, lookup), expr)


# ════════════════ 기하 (럭비 스크립트 rugby_final.py 와 같은 계산) ════════════════
def cubic(p0, p1, p2, p3, n):
    out = []
    for k in range(n + 1):
        t = k / n; a = 1 - t
        out.append((a**3*p0[0] + 3*a*a*t*p1[0] + 3*a*t*t*p2[0] + t**3*p3[0],
                    a**3*p0[1] + 3*a*a*t*p1[1] + 3*a*t*t*p2[1] + t**3*p3[1]))
    return out


def walk(path, s):
    """선을 따라 s mm 걸어간 점(넘치면 끝점)"""
    acc = 0.0
    for i in range(1, len(path)):
        L = math.dist(path[i - 1], path[i])
        if L > 0 and acc + L >= s:
            t = (s - acc) / L
            return (path[i-1][0] + (path[i][0]-path[i-1][0])*t, path[i-1][1] + (path[i][1]-path[i-1][1])*t)
        acc += L
    return tuple(path[-1])


def split_at_y(P, y):
    """선을 가로선 y 에서 처음 만나는 자리로 둘로 자른다"""
    for i in range(1, len(P)):
        if (P[i - 1][1] - y) * (P[i][1] - y) <= 0:
            a, b = P[i - 1], P[i]
            t = (y - a[1]) / (b[1] - a[1]) if b[1] != a[1] else 0
            m = (a[0] + (b[0] - a[0]) * t, y)
            return list(P[:i]) + [m], [m] + list(P[i:])
    raise FormulaError(f"선이 y={y:.2f} 를 지나지 않는다")


# ════════════════ 모델 — 이름마다 정의를 들고, 필요할 때 계산(메모) ════════════════
KINDS = ("inputs", "params", "vars", "points", "paths")


def _values_of(measurements):
    if isinstance(measurements, dict) and isinstance(measurements.get("values"), dict): return measurements["values"]
    if isinstance(measurements, dict): return measurements
    raise FormulaError("치수표는 {이름: mm} 또는 {\"values\": {…}} 여야 한다")


class Model:
    def __init__(self, style, measurements, overrides=None, _fixed=None):
        self.style = style
        self.defs = {}
        vals = _values_of(measurements)
        inputs = style.get("inputs") or {}
        for nm in vals:
            if nm not in inputs: raise FormulaError(f"치수표의 '{nm}' 은 스타일 inputs 에 없는 이름이다(오타?)")
        for nm in inputs:
            if nm not in vals:
                lab = inputs[nm].get("label", "") if isinstance(inputs[nm], dict) else inputs[nm]
                raise FormulaError(f"치수표에 '{nm}'({lab}) 이 없다")
        for kind in KINDS:
            for nm, d in (style.get(kind) or {}).items():
                if not nm.isidentifier() or nm in _FUNCS:
                    raise FormulaError(f"쓸 수 없는 이름 '{nm}' — 영문·숫자·밑줄, 함수 이름과 겹치면 안 된다")
                if nm in self.defs: raise FormulaError(f"이름 '{nm}' 이 {self.defs[nm][0]} 와 {kind} 에 두 번 정의됐다")
                self.defs[nm] = (kind, vals[nm] if kind == "inputs" else d)
        for nm, v in (overrides or {}).items():                         # 치수·규칙 상수 덮어쓰기(숫자만)
            if nm not in self.defs or self.defs[nm][0] not in ("inputs", "params"):
                raise FormulaError(f"덮어쓸 수 없는 이름 '{nm}' — inputs·params 만 바꿀 수 있다")
            self.defs[nm] = (self.defs[nm][0], v)
        self._fixed = dict(_fixed or {})
        self._memo = {}
        self._stack = []
        self._base = []           # solve 가 만든 자식 모델이면 부모 쪽 사슬(깊이를 이어서 센다)
        self._deepest = []        # 지금까지 가장 깊었던 사슬(RecursionError 를 바꿔 알릴 때 쓴다)

    # ── 이름 하나 계산 ──
    def get(self, name):
        if name in self._fixed: return self._fixed[name]
        if name in self._memo: return self._memo[name]
        if name not in self.defs: raise FormulaError(f"없는 이름 '{name}'")
        if name in self._stack:
            chain = self._stack[self._stack.index(name):] + [name]
            raise CycleError("순환 참조: " + " → ".join(chain))
        if not self._stack and not self._base:
            # 맨 바깥 호출 — 깊이 검사를 빠져나간 RecursionError(식 자체가 깊게 중첩된 경우 등)도 분명한 오류로 바꾼다
            try:
                return self._get(name)
            except RecursionError:
                raise _depth_error(self._deepest or [name], "(파이썬 재귀 한도)") from None
        return self._get(name)

    def _get(self, name):
        chain = self._base + self._stack + [name]
        if len(chain) > len(self._deepest): self._deepest = chain
        if len(chain) > MAX_DEPTH:
            raise _depth_error(chain)                       # 파이썬이 죽기 전에(약 150단계) 먼저 멈춘다
        self._stack.append(name)
        try:
            v = self._compute(name)
        except FormulaError as e:
            if e.tagged: raise
            err = FormulaError(f"[{name}] {e}"); err.tagged = True
            raise err from e
        finally:
            self._stack.pop()
        self._memo[name] = v
        return v

    def value(self, expr):
        return scalar(expr, self.get)

    def _point_ref(self, nm):
        return _pt(self.get(nm), nm)

    def _compute(self, name):
        kind, d = self.defs[name]
        if kind in ("inputs", "params"):
            if isinstance(d, bool) or not isinstance(d, (int, float)) or not math.isfinite(d):
                raise FormulaError(f"치수·상수는 숫자여야 한다: {d!r}")
            return float(d)
        if kind == "vars":
            if isinstance(d, dict) and "solve" in d: return self._solve(name, d)
            return self.value(d)
        if kind == "points": return self._point(d)
        if kind == "paths": return self._pathdef(d)
        raise FormulaError(f"모르는 종류 {kind}")

    def _solve(self, name, d):
        """name 을 바꿔 가며 solve 식이 0 이 되는 값을 찾는다(이분법) — 예 «소매산 길이 = 진동 × 여유비» 가 되는 소매산 높이"""
        lo, hi = self.value(d["lo"]), self.value(d["hi"])
        it = int(d.get("iter", 60))
        if not 1 <= it <= 200: raise FormulaError("iter 는 1~200")
        def f(v):
            child = Model.__new__(Model)
            child.style, child.defs = self.style, self.defs
            child._fixed = dict(self._fixed, **{name: v}); child._memo = {}; child._stack = []
            child._base = self._base + self._stack; child._deepest = []     # 깊이는 부모 사슬에 이어서 센다
            return child.value(d["solve"])
        flo, fhi = f(lo), f(hi)
        if flo == 0: return lo
        if fhi == 0: return hi
        if (flo < 0) == (fhi < 0):
            raise FormulaError(f"{d['lo']}~{d['hi']} 범위에 해가 없다(양 끝 {flo:.2f} · {fhi:.2f}) — 치수가 서로 맞지 않는다")
        rising = flo < 0
        for _ in range(it):
            mid = (lo + hi) / 2
            if (f(mid) < 0) == rising: lo = mid
            else: hi = mid
        return (lo + hi) / 2

    def _point(self, d):
        if isinstance(d, list) and len(d) == 2:
            return Pt((self.value(d[0]), self.value(d[1])))
        if isinstance(d, dict):
            if "from" in d:                                           # 점에서 각도(도)·거리만큼
                p = self._point_ref(d["from"]); a = math.radians(self.value(d["angle"])); r = self.value(d["dist"])
                return Pt((p[0] + r * math.cos(a), p[1] + r * math.sin(a)))
            if "walk" in d:                                           # 선을 따라 s mm (reverse=끝에서부터)
                P = _path(self.get(d["walk"]), d["walk"])
                if d.get("reverse"): P = list(reversed(P))
                return Pt(walk(P, self.value(d["s"])))
            if "x" in d and "y" in d:
                return Pt((self.value(d["x"]), self.value(d["y"])))
        raise FormulaError(f"점 정의를 모르겠다: {d!r} — [x식, y식] · {{from, angle, dist}} · {{walk, s}}")

    def _pathdef(self, d):
        if not isinstance(d, dict): raise FormulaError(f"선 정의는 dict: {d!r}")
        if "bezier" in d:
            ps = [self._point_ref(n) for n in d["bezier"]]
            if len(ps) != 4: raise FormulaError("bezier 는 점 4개(시작·조절·조절·끝)")
            n = d.get("n", 60)
            if not isinstance(n, int) or not 2 <= n <= 2000: raise FormulaError("bezier n 은 2~2000")
            return Path(cubic(*ps, n))
        if "line" in d:
            return Path(tuple(self._point_ref(n)) for n in d["line"])
        if "split_y" in d:
            P = _path(self.get(d["split_y"]), d["split_y"])
            a, b = split_at_y(P, self.value(d["y"]))
            if d.get("part") not in ("before", "after"): raise FormulaError("split_y part 는 before|after")
            return Path(a if d["part"] == "before" else b)
        if "reverse" in d:
            return Path(reversed(_path(self.get(d["reverse"]), d["reverse"])))
        raise FormulaError(f"선 정의를 모르겠다: {d!r}")

    # ── 조각 ──
    def piece(self, pname):
        pd = (self.style.get("pieces") or {}).get(pname)
        if pd is None: raise FormulaError(f"없는 조각 '{pname}'")
        try:
            return self._piece(pname, pd)
        except FormulaError as e:
            if getattr(e, "_piece", False): raise
            err = e.__class__(f"조각 '{pname}': {e}"); err._piece = True; err.tagged = True   # 순환 참조는 CycleError 그대로
            raise err from e

    def _piece(self, pname, pd):
        sa0 = self.value(pd.get("sa", self.style.get("default_sa", 0)))
        E = []                                                        # [x, y, node, 이 점→다음 점 변의 시접]
        for item in pd["outline"]:
            ref, sa = (item, sa0) if isinstance(item, str) else (item["ref"], self.value(item["sa"]) if "sa" in item else sa0)
            obj = self.get(ref)
            if isinstance(obj, Pt): E.append([obj[0], obj[1], ref, sa])
            elif isinstance(obj, Path): E += [[q[0], q[1], None, sa] for q in obj]
            else: raise FormulaError(f"외곽선의 '{ref}' 는 점이나 선이어야 한다")
        if pd.get("mirror_x"):                                        # 반쪽 → 좌우 거울로 펼침(x=0 중심선)
            n = len(E)
            # 거울 쪽 m_j → m_{j-1} 변은 원래 변 h_{j-1} → h_j 의 거울 — 그 시접을 그대로 쓴다
            E = E + [[-E[j][0], E[j][1], (E[j][2] + "_L") if E[j][2] else None, E[j - 1][3] if j >= 1 else sa0]
                     for j in range(n - 1, -1, -1)]
        seam = []
        for x, y, nd, sa in E:                                       # 같은 자리 이웃 점 합치기 — 자리·이름은 앞 점, 시접은 뒤 점(뒤 점의 변이 살아남는다)
            if seam and math.dist((seam[-1]["x"], seam[-1]["y"]), (x, y)) < JOIN_TOL:
                seam[-1]["node"] = seam[-1]["node"] or nd; seam[-1]["sa"] = sa; continue
            seam.append({"x": x, "y": y, "node": nd, "notch": None, "sa": sa})
        if len(seam) > 2 and math.dist((seam[0]["x"], seam[0]["y"]), (seam[-1]["x"], seam[-1]["y"])) < JOIN_TOL:
            last = seam.pop(); seam[0]["node"] = seam[0]["node"] or last["node"]
        if len(seam) < 3: raise FormulaError("재봉선 점이 3개 미만")
        outline = [(s["x"], s["y"]) for s in seam]                    # 노치 넣기 전 재봉선(재현 비교용)
        nt_def = dict(self.style.get("notch") or {"type": "slit", "depth": 5.0})
        for nd in pd.get("notches") or []:
            q = self._point_ref(nd["at"]); side = nd.get("side", "right")
            qs = {"right": [q], "left": [(-q[0], q[1])], "both": [q, (-q[0], q[1])]}.get(side)
            if qs is None: raise FormulaError(f"노치 side 는 right|left|both: {side!r}")
            if len(qs) == 2 and abs(q[0]) < JOIN_TOL: qs = qs[:1]
            for qq in qs: _insert_notch(seam, qq, nd["at"], nt_def)
        fold = [list(self._point_ref(n)) for n in pd["fold"]] if pd.get("fold") else None
        meta = {k: pd[k] for k in ("en_name", "qty", "grain", "note") if k in pd}
        return {"name": pname, "seam": seam, "outline": outline, "fold": fold, "meta": meta}

    def pieces(self):
        return {n: self.piece(n) for n in (self.style.get("pieces") or {})}


def _insert_notch(seam, q, ref, nt_def):
    """노치 자리 q 를 재봉선에 투영 — 꼭짓점이면 그 점에, 변 가운데면 새 점을 넣어(시접은 그 변 것) 노치를 단다"""
    n = len(seam); best = None
    for i in range(n):
        a, b = (seam[i]["x"], seam[i]["y"]), (seam[(i + 1) % n]["x"], seam[(i + 1) % n]["y"])
        L2 = (b[0]-a[0])**2 + (b[1]-a[1])**2
        if L2 == 0: continue
        t = max(0, min(1, ((q[0]-a[0])*(b[0]-a[0]) + (q[1]-a[1])*(b[1]-a[1])) / L2))
        m = (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
        if best is None or math.dist(m, q) < best[0]: best = (math.dist(m, q), i, a, b, m)
    d, i, a, b, m = best
    if d > NOTCH_ON_SEAM_TOL: raise FormulaError(f"노치 '{ref}' 자리가 재봉선에서 {d:.1f}mm 떨어져 있다 — 다른 조각의 노치?")
    if math.dist(m, a) < JOIN_TOL: k = i
    elif math.dist(m, b) < JOIN_TOL: k = (i + 1) % n
    else:
        k = i + 1; seam.insert(k, {"x": m[0], "y": m[1], "node": None, "notch": None, "sa": seam[i]["sa"]})
    if seam[k]["notch"]: raise FormulaError(f"노치 '{ref}' 자리에 이미 노치가 있다")
    # 안쪽 방향 = 변의 법선 중 조각 안으로 가는 쪽(넓이 부호로 판정)
    P = [(s["x"], s["y"]) for s in seam]
    area2 = sum(P[j][0] * P[(j + 1) % len(P)][1] - P[(j + 1) % len(P)][0] * P[j][1] for j in range(len(P)))
    L = math.dist(a, b); tx, ty = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    inward = (-ty, tx) if area2 > 0 else (ty, -tx)
    seam[k]["notch"] = {"type": nt_def.get("type", "slit"), "depth": float(nt_def.get("depth", 5.0)), "dir": [inward[0], inward[1]], "ref": ref}


# ════════════════ 바깥으로 — piecespec 명세 ════════════════
def to_piecespec(piece, size=None, style_name=None):
    """조각 → piecespec 명세(seam 점 + node 이름 + sa). 재단선은 계산(sa_builtin=False) — compute_cut·to_legacy 가 그대로 받는다"""
    meta = dict(piece["meta"]); meta["source"] = "parametric"
    if size: meta["size"] = size
    if style_name: meta["style"] = style_name
    return {"version": SPEC_VERSION, "name": piece["name"], "meta": meta,
            "seam": [{"x": s["x"], "y": s["y"], "node": s["node"], "notch": copy.deepcopy(s["notch"]), "sa": s["sa"]} for s in piece["seam"]],
            "sa_builtin": False, "cut_builtin": [], "internal": [], "notch_lines": [], "fold": copy.deepcopy(piece["fold"])}


def load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)


def build(style, measurements, overrides=None):
    """치수표 → {"model", "pieces": {이름: 조각}, "specs": {이름: piecespec 명세}}"""
    m = Model(style, measurements, overrides)
    pcs = m.pieces()
    size = measurements.get("size") if isinstance(measurements, dict) else None
    specs = {n: to_piecespec(p, size, style.get("name")) for n, p in pcs.items()}
    for n, s in specs.items():
        errs = validate(s)
        if errs: raise FormulaError(f"조각 '{n}' 명세 검사 실패: {errs}")
    return {"model": m, "pieces": pcs, "specs": specs}


def parse_set(items, base_values):
    """--set chest+=40 · chest-=10 · chest=1330 → {이름: 값}"""
    out = {}
    for it in items or []:
        for op in ("+=", "-=", "="):
            if op in it:
                nm, v = it.split(op, 1); nm = nm.strip(); v = float(v)
                if op != "=":
                    if nm not in base_values: raise FormulaError(f"--set {it}: 치수표에 '{nm}' 이 없다")
                    v = base_values[nm] + (v if op == "+=" else -v)
                out[nm] = v; break
        else: raise FormulaError(f"--set 형식: 이름=값 · 이름+=값 · 이름-=값 ({it!r})")
    return out


# ════════════════ 확인 그림 (PyMuPDF — matplotlib 없이) ════════════════
def overlay_png(path, base_pieces, new_pieces, title, lines=(), scale=0.35, dpi=130, row_mm=2200, zoom_mm=120, zoom_x=4):
    """조각마다 기준(회색)과 바꾼 것(빨강)을 겹쳐 그린 PNG — 같은 좌표(중심선·위쪽 기준)로 겹친다.
    조각은 여러 줄로 놓고, 가장 많이 바뀐 자리를 zoom_x 배로 확대한 칸을 덧붙인다(10mm 차이는 전체 그림에선 안 보인다)"""
    import fitz
    from shapely.geometry import Polygon, Point
    MMPT = 72 / 25.4 * scale; GAP = 24
    names = list(new_pieces)
    boxes = {}
    for n in names:
        P = base_pieces[n]["outline"] + new_pieces[n]["outline"]
        xs = [p[0] for p in P]; ys = [p[1] for p in P]
        boxes[n] = (min(xs), min(ys), max(xs), max(ys))
    # 가장 많이 바뀐 자리 — 기준 재봉선 점 중 새 재봉선에서 가장 먼 점
    far = max(((Polygon(new_pieces[n]["outline"]).exterior.distance(Point(q)), n, q)
               for n in names for q in base_pieces[n]["outline"]), key=lambda t: t[0])
    # 줄 나누기
    rows, cur, w = [], [], 0.0
    for n in names:
        bw = boxes[n][2] - boxes[n][0]
        if cur and w + bw > row_mm: rows.append(cur); cur, w = [], 0.0
        cur.append(n); w += bw + GAP / MMPT
    if cur: rows.append(cur)
    head = 30 + 14 * len(lines)
    ZW = zoom_mm * MMPT * zoom_x
    rows_h = [max(boxes[n][3] - boxes[n][1] for n in r) * MMPT + 24 for r in rows]
    W = max(max(sum(boxes[n][2] - boxes[n][0] for n in r) * MMPT + GAP * (len(r) + 1) for r in rows), ZW + 2 * GAP)
    H = head + sum(rows_h) + GAP * len(rows) + ZW + 40
    doc = fitz.open(); pg = doc.new_page(width=W, height=H)
    font = "C:/Windows/Fonts/malgun.ttf"
    kw = {"fontname": "malgun", "fontfile": font} if os.path.exists(font) else {}
    pg.insert_text((GAP, 20), title, fontsize=12, **kw)
    for i, t in enumerate(lines): pg.insert_text((GAP, 38 + 14 * i), t, fontsize=10, **kw)
    GREY, RED = (0.6, 0.6, 0.6), (0.85, 0.1, 0.1)

    def draw(n, tr, wb, wr):
        for P, col, wd in ((base_pieces[n]["outline"], GREY, wb), (new_pieces[n]["outline"], RED, wr)):
            pg.draw_polyline([tr(p) for p in P] + [tr(P[0])], color=col, width=wd)

    y = head
    for r, rh in zip(rows, rows_h):
        x = GAP
        for n in r:
            x0, y0, x1, y1 = boxes[n]
            draw(n, lambda p, x=x, x0=x0, y0=y0, y=y: fitz.Point(x + (p[0] - x0) * MMPT, y + 18 + (p[1] - y0) * MMPT), 1.6, 0.7)
            pg.insert_text((x, y + 10), n, fontsize=10, **kw)
            x += (x1 - x0) * MMPT + GAP
        y += rh + GAP
    # 확대 칸
    d, n, q = far
    zx0, zy0 = q[0] - zoom_mm / 2, q[1] - zoom_mm / 2; K = MMPT * zoom_x
    clip = fitz.Rect(GAP, y + 18, GAP + ZW, y + 18 + ZW)
    pg.insert_text((GAP, y + 10), f"확대 ×{zoom_x} — {n} · 가장 많이 바뀐 자리({q[0]:.0f}, {q[1]:.0f}) 둘레 {zoom_mm}mm · 차 {d:.1f}mm · 눈금 10mm", fontsize=10, **kw)
    pg.draw_rect(clip, color=(0.3, 0.3, 0.3), width=0.5)
    tr = lambda p: fitz.Point(clip.x0 + (p[0] - zx0) * K, clip.y0 + (p[1] - zy0) * K)
    for P, col, wd in ((base_pieces[n]["outline"], GREY, 2.0), (new_pieces[n]["outline"], RED, 1.0)):
        segs = [P[i] for i in range(len(P))] + [P[0]]
        for a, b in zip(segs, segs[1:]):                      # 칸 밖 선분은 버린다(간단 자르기)
            A, B = tr(a), tr(b)
            if clip.contains(A) and clip.contains(B): pg.draw_line(A, B, color=col, width=wd)
    for k in range(0, zoom_mm + 1, 10):                       # 10mm 눈금
        pg.draw_line(fitz.Point(clip.x0 + k * K, clip.y1 - 6), fitz.Point(clip.x0 + k * K, clip.y1), color=(0, 0, 0), width=0.5)
    pg.get_pixmap(dpi=dpi).save(path); doc.close()


def girth_at(outline, y):
    """가로선 y 에서 조각 폭(mm) — 재봉선 안쪽 구간 길이의 합"""
    from shapely.geometry import Polygon, LineString
    poly = Polygon(outline); x0, _, x1, _ = poly.bounds
    return poly.intersection(LineString([(x0 - 10, y), (x1 + 10, y)])).length


def measures(R, style):
    """스타일의 measures 표대로 완성 치수를 잰다 — 식이면 모델 값, {girth_at, pieces} 면 그 높이의 조각 폭 합"""
    out = {}
    for nm, d in (style.get("measures") or {}).items():
        if isinstance(d, dict) and "girth_at" in d:
            y = R["model"].value(d["girth_at"])
            out[nm] = sum(girth_at(R["pieces"][p]["outline"], y) for p in d["pieces"])
        else:
            out[nm] = R["model"].value(d)
    return out


def file_stem(style, size):
    """파일 이름 줄기 — 스타일 이름의 앞머리(« — »·« · » 앞)만 + 사이즈. 예 «럭비 저지 — 드롭숄더 …» M → 럭비_저지_M"""
    head = (style.get("name") or "pattern").split(" — ")[0].split(" · ")[0].strip()
    return "_".join((head + " " + str(size)).split())


def export_pattern(R, style, measurements, out, name=None):
    """계산한 패턴을 공장용으로 내보낸다 — parametric → piecespec 명세 → patlib.export (.ai · 1:1 PDF · 미리보기 · DXF R12).
    좌표가 y 아래쪽(+)이라 flip_y 로 뒤집고, 장수(meta.qty)만큼 펼친다. DXF 영문 이름은 조각의 en_name(스타일에 적힌 것)"""
    from patlib import export, spec_instances                # 내보내기 때만 무거운 도구(ezdxf·PyMuPDF)를 불러온다
    os.makedirs(out, exist_ok=True)
    size = (measurements.get("size") if isinstance(measurements, dict) else None) or "-"
    name = name or file_stem(style, size)
    inst = spec_instances(R["specs"], flip_y=True)
    title = f"{style.get('name') or '패턴'} · {size} · 1:1 mm (치수표 계산 F9)"
    legend = ["검정 재단선 · 파랑 점선 재봉선 · 초록 일점쇄선 접는 선 · 짧은 선 노치",
              f"치수표: {measurements.get('name', '') if isinstance(measurements, dict) else ''}"]
    sheet = export(inst, name, title, legend, out, size, subject=f"{style.get('name') or name} {size} 패턴 1:1 mm")
    return {"name": name, "files": [os.path.join(out, name + ext) for ext in (".ai", "_1대1.pdf", "_미리보기.png", ".dxf")], "sheet": sheet}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="치수표 → 패턴(piecespec 명세)")
    ap.add_argument("style"); ap.add_argument("measurements")
    ap.add_argument("--set", action="append", default=[], help="치수 바꾸기: chest+=40 · chest=1330")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), "tmp", "pattern-engine", "parametric"))
    ap.add_argument("--export", metavar="폴더", help="공장용 .ai·1:1 PDF·DXF 도 이 폴더에 내보낸다(patlib.export)")
    A = ap.parse_args(argv)
    style, meas = load_json(A.style), load_json(A.measurements)
    over = parse_set(A.set, _values_of(meas))
    os.makedirs(A.out, exist_ok=True)
    R = build(style, meas, over)
    tag = "_".join(f"{k}{v:g}" for k, v in over.items()) or "base"
    out = {"style": style.get("name"), "measurements": meas.get("name"), "overrides": over,
           "specs": R["specs"], "cut": {n: compute_cut(s) for n, s in R["specs"].items()}}
    fn = os.path.join(A.out, f"pieces_{tag}.json")
    with open(fn, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)
    print("저장:", fn)
    for n, p in R["pieces"].items():
        print(f"  {n:6s} 재봉선 {len(p['seam'])}점 · 노치 {sum(1 for s in p['seam'] if s['notch'])} · 둘레 {plen(p['outline'] + p['outline'][:1]):.1f}mm")
    if A.export:
        E = export_pattern(R, style, meas, A.export, file_stem(style, meas.get("size") or "-") + ("" if tag == "base" else f"_{tag}"))
        print("내보내기:", *E["files"], f"· 조각 {E['sheet']['total_qty']}장 · 겹침 {len(E['sheet']['overlap'])}", sep="\n  ")
    if over:
        B = build(style, meas)
        mb, mr = measures(B, style), measures(R, style)
        lines = [f"바꾼 치수: " + " · ".join(f"{k} {_values_of(meas)[k]:g} → {v:g}" for k, v in over.items())]
        lines += [f"{k}: {mb[k]:.1f} → {mr[k]:.1f}  ({mr[k] - mb[k]:+.1f})" for k in mb]
        for t in lines: print("  " + t)
        png = os.path.join(A.out, f"overlay_{tag}.png")
        overlay_png(png, B["pieces"], R["pieces"], f"{style.get('name')} — {meas.get('name')} · 회색=기준 · 빨강={tag}", lines)
        with open(os.path.join(A.out, f"measures_{tag}.json"), "w", encoding="utf-8") as f:
            json.dump({"overrides": over, "base": mb, "changed": mr}, f, ensure_ascii=False, indent=1)
        print("그림:", png)


if __name__ == "__main__":
    main()
