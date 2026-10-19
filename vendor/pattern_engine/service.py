# 재단 패턴 엔진 «창구» — 서버(그레이더)가 부르는 단 하나의 입구 (F10 2단계, 2026-10-19)
#
#   왜 이 파일이 있나(비유):
#     엔진 파일들은 원래 «사람이 명령줄에서 하나씩 돌리는 공구» 다. 그대로 서버에 붙이면 두 군데서 터진다.
#       ① gas_warmup_build.py · gas_warmup_grade.py 는 «불러오는 순간» 명령줄 인자를 읽는다
#          → 서버가 import 하면 서버의 인자(uvicorn …)를 먹고 죽는다.
#       ② 글꼴이 C:/Windows/Fonts/malgun.ttf 로 박혀 있다 → 리눅스(Render)에는 없다.
#     그래서 엔진 파일은 한 줄도 고치지 않고, 이 «창구» 가 ①은 «따로 띄운 일꾼 프로세스 안에서 인자를 대신 쥐여 주고»,
#     ②는 «글꼴 주소를 그 자리에서 바꿔 끼워» 막는다.
#
#   하는 일 — 입력 → 출력
#     입력 A (원본): 가스 웜업 원본 .ai 4개(가스 상의·하의 2XL · 표준 웜업 상의·팬츠 13사이즈) — 기본 fixtures/gas-warmup-2026
#       → ① 2XL 수정(build) → ② 점별 규칙 그레이딩 S~5XL(grade) → ③ 조각 명세 9벌(spec)
#         → ④ AAMA DXF·RUL·전 사이즈 DXF·기준 1:1 PDF(aama) + A4 분할(tile_pdf) → ⑤ 화면용 view.json + exports.zip(cad_view)
#     입력 B (명세 JSON): 이미 만든 결과 폴더(spec/spec_*.json · graded/검산.json · graded/<사이즈>/ …) → ⑤ 만
#     출력: <work>/cad/<style_id>/view.json · exports.zip  (cad_view.py 와 같은 모양 — 그레이더 1단계 올리기 검사를 그대로 통과)
#
#   부르는 법
#     서버(부모 프로세스):  import service; service.rebuild(work_dir, groups=["top"], on_step=…)   ← 일꾼 프로세스를 띄운다
#     명령줄:  python tools/pattern-engine/service.py build --work <폴더> [--groups top bottom] [--no-aama] [--result r.json]
#              python tools/pattern-engine/service.py view  --src <gas-warmup 결과 폴더> --out <폴더> [--aama <aama 폴더>]
#              python tools/pattern-engine/service.py font          ← 지금 어떤 글꼴을 쓰게 되는지
#   F10 3단계(기준점 끌어서 다시 그레이딩):
#     서버:    service.regrade(work, "top", 전체_규칙표, full=False|True, on_step=…)   ← 같은 일꾼 길(미리보기 약 10초 · 저장용 full 약 1분)
#     명령줄:  python tools/pattern-engine/service.py regrade --work <폴더> --group top --rules-file <표.json> [--full]
#     규칙표 = {조각: {기준점: {사이즈: [Δx, Δy]}}} (RULE_FRAME 참고) — rules_from_view(view) 로 기존 버전에서 읽고,
#              merge_rules(표, 바꾼칸) 으로 합치고, mesh_checks 가 맞물림(래글런·옆선·소매 밑선·안솔기)을 초록/빨강으로 판정한다
#   🚫 쇼핑몰 운영 DB·드라이브를 읽지도 쓰지도 않는다. 결과는 <work> 안에만 생긴다.
#   🚫 marker.py 는 부르지 않는다(4단계 · 다른 작업자가 효율 개선 중).
import sys, os, json, math, time, shutil, argparse, datetime, contextlib, subprocess, threading, runpy, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures", "gas-warmup-2026")
FONT_HARD = "C:/Windows/Fonts/malgun.ttf"                 # 엔진 파일 곳곳에 박혀 있는 글꼴 주소 — 이 창구가 바꿔 끼운다
FONT_ENV = "PATTERN_ENGINE_FONT"                           # 이 환경변수에 글꼴 파일 주소를 주면 그것을 1순위로 쓴다
CACHE_ENV = "PATTERN_ENGINE_CACHE"                         # 대체 글꼴을 꺼내 둘 폴더(없으면 임시 폴더)
NO_SYS_ENV = "PATTERN_ENGINE_NO_SYSTEM_FONTS"              # "1" 이면 후보 목록을 건너뛴다 — 윈도우에서 «리눅스처럼 글꼴이 없을 때» 를 시험하려고
# 후보 글꼴 — 위에서부터 «있는 것» 을 쓴다. 하나도 없으면 오류가 아니라 PyMuPDF 에 든 한중일 글꼴(Droid Sans Fallback)로 대신한다
FONT_CANDIDATES = [
    FONT_HARD,                                                              # 윈도우 — 맑은 고딕(지금까지 쓰던 것, 결과가 그대로 같다)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",               # 데비안·우분투 fonts-noto-cjk
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",                    # 아치
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",             # 페도라
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",                      # fonts-nanum
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",                           # 맥
]
SOURCE_KEYS = ("top", "bottom", "std_top", "std_pants")
DEFAULT_SOURCES = {"top": os.path.join(FIX, "gas_top_2xl.ai"), "bottom": os.path.join(FIX, "gas_bottom_2xl.ai"),
                   "std_top": os.path.join(FIX, "std_warmup_top.ai"), "std_pants": os.path.join(FIX, "std_warmup_pants.ai")}
# 서버에서 «다시 만들기» 가 되는 스타일 → 옷 종류(cad_view.GROUPS 와 같아야 한다 — 시험이 본다). 원본 .ai 가 fixtures 에 있는 것만
REBUILDABLE = {"gas-warmup-2026-top": "top", "gas-warmup-2026-bottom": "bottom"}
STEP_MARK = "@@STEP"                                       # 일꾼이 «지금 몇 번째 단계» 를 부모에게 알리는 줄머리(진행률)
STEPS = ["build", "grade", "spec", "aama", "view"]
STEP_KO = {"build": "2XL 수정", "grade": "S~5XL 그레이딩", "spec": "조각 명세", "aama": "AAMA·A4 내보내기", "view": "화면 자료·묶음"}

# ════════ 그레이딩 규칙표(F10 3단계) — «기준점마다 사이즈별 이동량(Δx,Δy)» ════════
#   규칙 값의 틀 = gas_warmup_grade.py 의 «최종 규칙»(검산.json «상의 규칙»·«하의 규칙» 과 같다): 조각 기준 좌표, 2XL 대비 mm, y 위(+).
#   화면(view.json, y 아래로 +)에서 기준점이 움직인 양 = (sx × Δx, −Δy) — sx 는 조각마다 «x 가 화면에서 어느 쪽인가».
#     뒤판: 좌우 대칭이라 한 규칙이 두 점(R=+1·L=−1)을 움직인다 · 앞판·소매 −1 · 바지 앞판 −1 · 뒤판 +1
#     (gas_warmup_grade.py top_cards·pants_cards 의 카드 이동량 부호 그대로 — 시험이 «view 에서 읽은 규칙 = 검산.json 규칙» 으로 확인)
GRADE_SIZES = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
BASE_SIZE = "2XL"                                           # 규칙의 0 점 — 이 사이즈는 움직이지 않는다
RULE_FRAME = {
    "top": {
        "뒤판": {"옆밑단": [["옆밑단R", 1], ["옆밑단L", -1]], "겨드랑이": [["겨드랑이R", 1], ["겨드랑이L", -1]],
                 "목옆": [["목옆R", 1], ["목옆L", -1]], "뒤목중심": [["뒤목중심", 1]]},
        "앞판": {k: [[k, -1]] for k in ("앞중심목", "목옆", "겨드랑이", "옆밑단")},
        "소매": {k: [[k, -1]] for k in ("밑단앞", "밑단뒤", "겨드랑이앞", "겨드랑이뒤", "목앞", "목뒤", "어깨")},
    },
    "bottom": {
        "앞판": {k: [[k, -1]] for k in ("옆밑단", "안솔기밑단", "가랑이", "허리옆", "허리중심")},
        "뒤판": {k: [[k, 1]] for k in ("옆밑단", "안솔기밑단", "가랑이", "허리옆", "허리중심")},
    },
}
LOCK_X = [["top", "뒤판", "뒤목중심"], ["top", "앞판", "앞중심목"]]   # 가운데선 점 — 가로로 움직이면 좌우가 비뚤어진다(세로만)
RULE_MAX_MM = 400.0                                         # 규칙 값 상한(오타 방어 — 실제 규칙은 ±100mm 안)
# 맞물림 검산(«미리보기» 초록/빨강) — 검산.json 값이 목표에서 허용 안이면 초록. 목표 None = 2XL 값(원본 차를 지킨다)
MESH = {
    "top": [("raglan_front", "앞 래글런 몸판=소매", "상의 검산", "앞 래글런 몸판−소매", 0.0, 0.5),
            ("raglan_back", "뒤 래글런 몸판=소매", "상의 검산", "뒤 래글런 몸판−소매", 0.0, 0.5),
            ("side", "옆선 앞=뒤", "상의 검산", "옆선 앞−뒤", 0.0, 0.5),
            ("sleeve_under", "소매 밑선 앞=뒤", "상의 검산", "소매 밑선 앞−뒤", 0.0, 0.5)],
    "bottom": [("inseam", "안솔기 앞−뒤(2XL 차 유지)", "하의 검산", "안솔기 앞−뒤", None, 0.5),
               ("pants_side_front", "앞판 옆선=앞배색", "하의 검산", "앞판 옆선−앞배색", 0.0, 1.0),
               ("pants_side_back", "뒤판 옆선=뒤배색", "하의 검산", "뒤판 옆선−뒤배색", 0.0, 1.0)],
}


class ServiceError(RuntimeError):
    """창구가 내는 오류 — 메시지는 한국어(직원 화면에 그대로 보여도 되는 말)"""


# ════════ 글꼴 ════════
def builtin_cjk_font(cache_dir=None):
    """PyMuPDF 안에 든 한중일 글꼴(Droid Sans Fallback, Apache-2.0)을 파일로 꺼내 그 주소를 돌려준다.
    왜 파일로: 엔진은 «글꼴 파일 주소» 를 받는 꼴(fontfile=…)이라, 주소만 바꿔 끼우면 엔진을 안 고쳐도 된다.
    (2026-10-19 실측: 엔진 글자 610종 — 맑은 고딕에 있는 것 — 이 이 글꼴에 전부 있다)"""
    import fitz
    d = cache_dir or os.environ.get(CACHE_ENV) or os.path.join(__import__("tempfile").gettempdir(), "stiz-pattern-engine")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "DroidSansFallbackFull.ttf")
    buf = fitz.Font("cjk").buffer
    if not (os.path.isfile(path) and os.path.getsize(path) == len(buf)):
        tmp = f"{path}.tmp-{os.getpid()}"
        with open(tmp, "wb") as f: f.write(buf)
        os.replace(tmp, path)                                 # 반쯤 쓴 파일을 다른 일꾼이 읽지 않게
    return path


def resolve_font(env=None, candidates=None, cache_dir=None):
    """쓸 글꼴을 고른다 → {"path", "source": env|candidate|builtin, "fallback": 참이면 대체 글꼴, "note"}
    순서: 환경변수 PATTERN_ENGINE_FONT → 후보 목록 → (없으면) PyMuPDF 내장 한중일 글꼴. 🚫 «없어서 실패» 는 없다"""
    env = os.environ if env is None else env
    cands = FONT_CANDIDATES if candidates is None else candidates
    if candidates is None and (env.get(NO_SYS_ENV) or "").strip() == "1":
        cands = []
    note = None
    want = (env.get(FONT_ENV) or "").strip()
    if want:
        if os.path.isfile(want):
            return {"path": want, "source": "env", "fallback": False, "note": None}
        note = f"{FONT_ENV} 에 적힌 글꼴이 없다({want}) — 후보 목록으로 넘어감"
    for c in cands:
        if c and os.path.isfile(c):
            return {"path": c, "source": "candidate", "fallback": False, "note": note}
    return {"path": builtin_cjk_font(cache_dir), "source": "builtin", "fallback": True,
            "note": (note + " · " if note else "") + "후보 글꼴이 하나도 없어 PyMuPDF 내장 한중일 글꼴(Droid Sans Fallback)로 대신함"}


@contextlib.contextmanager
def font_shim(font_path):
    """이 안에서는 엔진이 «C:/Windows/Fonts/malgun.ttf» 나 «없는 글꼴 파일» 을 달라고 하면 font_path 를 대신 준다.
    바꾸는 곳: fitz.Font(fontfile=…) · Page.insert_text(fontfile=…) · Page.insert_font(fontfile=…) — 엔진이 글꼴을 쓰는 세 군데 전부.
    나가면 원래대로 되돌린다(이 프로세스 밖에는 영향 없음)."""
    import fitz
    hard = os.path.normcase(os.path.normpath(FONT_HARD))

    def remap(ff):
        if isinstance(ff, str) and ff and (os.path.normcase(os.path.normpath(ff)) == hard or not os.path.isfile(ff)):
            return font_path
        return ff

    OrigFont, orig_text, orig_font = fitz.Font, fitz.Page.insert_text, fitz.Page.insert_font

    class Font(OrigFont):                                       # fitz.Font(fontfile=FONT) → 바꿔 끼운 글꼴
        def __init__(self, fontname=None, fontfile=None, *a, **k):
            super().__init__(fontname, remap(fontfile), *a, **k)

    def insert_text(self, *a, **k):
        if "fontfile" in k: k["fontfile"] = remap(k["fontfile"])
        return orig_text(self, *a, **k)

    def insert_font(self, *a, **k):
        if "fontfile" in k: k["fontfile"] = remap(k["fontfile"])
        return orig_font(self, *a, **k)

    fitz.Font, fitz.Page.insert_text, fitz.Page.insert_font = Font, insert_text, insert_font
    try:
        yield font_path
    finally:
        fitz.Font, fitz.Page.insert_text, fitz.Page.insert_font = OrigFont, orig_text, orig_font


# ════════ 메모리·판 표시 ════════
def peak_rss_mb():
    """이 프로세스가 지금까지 쓴 메모리 최고치(MB, 실제 RAM — Render 512MB 한도와 견줄 숫자)"""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            c = PMC(); c.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32"); psapi = ctypes.WinDLL("psapi")
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return round(c.PeakWorkingSetSize / 2 ** 20, 1)
            return None
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(r / 2 ** 20 if sys.platform == "darwin" else r / 1024, 1)   # 리눅스는 KB, 맥은 바이트
    except Exception:
        return None


def engine_version():
    """엔진 판 — 그레이더 복사본이면 ENGINE_VERSION.json(stizshop 커밋 + 파일 지문), 아니면 stizshop git"""
    p = os.path.join(HERE, "ENGINE_VERSION.json")
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as f: ev = json.load(f)
            dirty = bool(ev.get("dirty_files"))                    # 복사할 때 stizshop 에 커밋 안 된 엔진 파일이 있었다
            c = ev.get("commit_short") or ev.get("commit")
            return {"commit": (c + "+dirty") if (c and dirty) else c, "dirty": dirty, "source": "vendor"}
        except Exception:
            return {"commit": None, "dirty": None, "source": "vendor(읽기 실패)"}
    sys.path.insert(0, HERE)
    import cad_view
    head = cad_view.git_head()
    return {"commit": head, "dirty": bool(head and head.endswith("+dirty")), "source": "git"}


def vm_status_mb():
    """리눅스 /proc/self/status 의 VmPeak(주소 공간 최고치)·VmHWM(실제 RAM 최고치) MB — 안전띠 상한(RLIMIT_AS)과 견줄 숫자.
    리눅스가 아니면 빈 dict"""
    out = {}
    try:
        with open("/proc/self/status", encoding="ascii", errors="replace") as f:
            for line in f:
                for key, name in (("VmPeak:", "vm_peak_mb"), ("VmHWM:", "vm_hwm_mb")):
                    if line.startswith(key):
                        out[name] = round(int(line.split()[1]) / 1024, 1)        # kB → MB
    except Exception:
        pass
    return out


# ════════ 규칙표 — 읽기·검사·합치기·맞물림 판정 (표준 라이브러리만 — 서버가 불러와도 엔진이 돌지 않는다) ════════
def _num(v):
    """진짜 유한한 숫자인가 — 참·거짓·NaN·무한대, float 로 못 바꾸는 아주 큰 정수(400자리 등 → OverflowError)는 아니다"""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (OverflowError, ValueError):
        return False
    return f == f and abs(f) != float("inf")


def rules_from_view(view):
    """view.json 에서 규칙표를 읽어 낸다 — 기준점이 사이즈마다 움직인 양을 2XL 대비로 재서 RULE_FRAME 부호로 되돌린다.
    반환 {조각: {기준점: {사이즈: [Δx, Δy]}}} (0.01mm 반올림 — view.json 좌표 단위가 0.01mm 라 그 이상은 정확하지 않다).
    왜: 1단계에서 올린 버전·2단계 다시 만든 버전에는 규칙표 파일이 없다. 그 버전이 «실제로 보여 주는 모양» 의 규칙을 그대로 꺼낸다."""
    try:
        group = view["style"]["group"]; q = float(view["q"])
        frame = RULE_FRAME[group]
    except Exception:
        raise ServiceError("이 스타일은 그레이딩 규칙을 읽을 수 없습니다(옷 종류를 모름).")
    if BASE_SIZE not in view.get("sizes", {}):
        raise ServiceError(f"view.json 에 기준 사이즈({BASE_SIZE})가 없습니다.")
    sizes = [s for s in GRADE_SIZES if s in view["sizes"]]
    cache = {}

    def node(sid, piece, nm):
        k = (sid, piece)
        if k not in cache:
            cache[k] = next((p for p in view["sizes"][sid]["pieces"] if p.get("name") == piece), None)
        p = cache[k]
        if p is None or nm not in (p.get("nodes") or {}):
            raise ServiceError(f"view.json 의 {sid} {piece} 에 기준점 «{nm}» 이 없습니다.")
        i = p["nodes"][nm]
        return p["seam"][2 * i] * q, p["seam"][2 * i + 1] * q

    out = {}
    for pc, pts in frame.items():
        out[pc] = {}
        for k, nodes in pts.items():
            out[pc][k] = {}
            for s in sizes:
                xs, ys = [], []
                for nm, sx in nodes:
                    (x, y), (bx, by) = node(s, pc, nm), node(BASE_SIZE, pc, nm)
                    xs.append(sx * (x - bx)); ys.append(-(y - by))
                out[pc][k][s] = [round(sum(xs) / len(xs), 2) + 0.0, round(sum(ys) / len(ys), 2) + 0.0]   # +0.0 = -0.0 없애기
    return out


def check_rules(group, table, full=False):
    """규칙표(일부 또는 전체)를 검사해 깨끗한 사본을 돌려준다. 틀리면 ServiceError(한국어 — 화면에 그대로 보여도 된다).
    full=True 면 RULE_FRAME 의 모든 조각·기준점·사이즈가 있어야 한다(엔진에 넘기는 표)."""
    frame = RULE_FRAME.get(group)
    if frame is None:
        raise ServiceError(f"모르는 옷 종류: {group}")
    if not isinstance(table, dict):
        raise ServiceError("규칙표는 {조각: {기준점: {사이즈: [Δx, Δy]}}} 모양이어야 합니다.")
    lock = {(g, p, k) for g, p, k in LOCK_X}
    out = {}
    for pc, pts in table.items():
        if pc not in frame:
            raise ServiceError(f"그레이딩할 수 없는 조각: {str(pc)[:30]}")
        if not isinstance(pts, dict):
            raise ServiceError(f"{pc} 규칙 모양이 다릅니다.")
        for k, bys in pts.items():
            if k not in frame[pc]:
                raise ServiceError(f"{pc} 에 «{str(k)[:30]}» 기준점이 없습니다.")
            if not isinstance(bys, dict):
                raise ServiceError(f"{pc} {k} 규칙 모양이 다릅니다.")
            for s, v in bys.items():
                if s not in GRADE_SIZES:
                    raise ServiceError(f"모르는 사이즈: {str(s)[:20]}")
                if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(_num(a) for a in v)):
                    raise ServiceError(f"{pc} {k} {s} 값은 숫자 두 개 [Δx, Δy] 여야 합니다.")
                dx, dy = float(v[0]), float(v[1])
                if abs(dx) > RULE_MAX_MM or abs(dy) > RULE_MAX_MM:
                    raise ServiceError(f"{pc} {k} {s} 이동량이 너무 큽니다(±{RULE_MAX_MM:.0f}mm 이하).")
                if s == BASE_SIZE and (abs(dx) > 1e-6 or abs(dy) > 1e-6):
                    raise ServiceError(f"기준 사이즈({BASE_SIZE})는 움직이지 않습니다 — {pc} {k}")
                if (group, pc, k) in lock and abs(dx) > 1e-6:
                    raise ServiceError(f"{pc} {k} 는 가운데선 점이라 가로(Δx)는 0 이어야 합니다.")
                out.setdefault(pc, {}).setdefault(k, {})[s] = [dx, dy]
    if full:
        miss = [f"{pc}/{k}/{s}" for pc, pts in frame.items() for k in pts for s in GRADE_SIZES if s not in out.get(pc, {}).get(k, {})]
        if miss:
            raise ServiceError("규칙표에 빠진 칸이 있습니다: " + ", ".join(miss[:5]) + (" …" if len(miss) > 5 else ""))
    return out


def merge_rules(base, changes):
    """base(전체 표) 위에 changes(일부 — 바꾼 칸만, 값은 최종 규칙)를 얹은 새 표"""
    out = {pc: {k: {s: list(v) for s, v in bys.items()} for k, bys in pts.items()} for pc, pts in base.items()}
    for pc, pts in (changes or {}).items():
        for k, bys in pts.items():
            for s, v in bys.items():
                out.setdefault(pc, {}).setdefault(k, {})[s] = [float(v[0]), float(v[1])]
    return out


def diff_rules(base, new, eps=0.005):
    """바뀐 칸 목록 — [{"piece","point","size","from","to"}] (기록·화면 표시용)"""
    out = []
    for pc, pts in new.items():
        for k, bys in pts.items():
            for s, v in bys.items():
                b = base.get(pc, {}).get(k, {}).get(s)
                if b is None or abs(b[0] - v[0]) > eps or abs(b[1] - v[1]) > eps:
                    out.append({"piece": pc, "point": k, "size": s, "from": b, "to": [round(v[0], 2), round(v[1], 2)]})
    return out


def mesh_checks(report, group):
    """맞물림 판정 — 검산.json(그레이딩이 잰 값)을 목표·허용과 견준다 → {"ok", "sizes": {사이즈: [칸…]}}"""
    rows_by, all_ok = {}, True
    for s in GRADE_SIZES:
        if s not in report: continue
        rows = []
        for key, label, sect, name, target, tol in MESH[group]:
            v = (report[s].get(sect) or {}).get(name)
            t = target if target is not None else (report.get(BASE_SIZE, {}).get(sect) or {}).get(name)
            ok = None if (not _num(v) or not _num(t)) else abs(v - t) <= tol + 1e-9
            if ok is False: all_ok = False
            rows.append({"key": key, "label": label, "value": v, "target": t, "tol": tol, "ok": ok})
        rows_by[s] = rows
    return {"ok": all_ok, "sizes": rows_by}


def max_rule_gap(a, b):
    """두 규칙표가 가장 크게 다른 칸(mm) — «넘긴 규칙» 과 «만든 모양에서 다시 읽은 규칙» 견주기(부호·틀 실수 잡기)"""
    worst = 0.0
    for pc, pts in a.items():
        for k, bys in pts.items():
            for s, v in bys.items():
                w = (b.get(pc, {}).get(k, {}) or {}).get(s)
                if w is None: return float("inf")
                worst = max(worst, abs(v[0] - w[0]), abs(v[1] - w[1]))
    return round(worst, 4)


# ════════ 단계 — 일꾼 프로세스 안에서만 돈다 ════════
def _run_script(name, argv):
    """명령줄 인자를 import 시점에 읽는 엔진 파일을 «그 인자를 쥐여 준 채» 새 이름공간에서 돌린다(파일은 안 고친다)"""
    path = os.path.join(HERE, name)
    old = sys.argv[:]
    sys.argv = [path] + [str(a) for a in argv]
    try:
        runpy.run_path(path, run_name="__main__")
    finally:
        sys.argv = old


def _check_sources(sources):
    src = dict(DEFAULT_SOURCES); src.update({k: v for k, v in (sources or {}).items() if v})
    bad = [k for k in SOURCE_KEYS if not os.path.isfile(src[k])]
    if bad:
        raise ServiceError("원본 .ai 가 없습니다: " + ", ".join(f"{k}={src[k]}" for k in bad))
    return src


def _step(i, name, emit):
    if emit: print(f"{STEP_MARK} {i}/{len(STEPS)} {name}", flush=True)


def _view_step(src, aama_dir, out, groups, when, ev):
    """⑤ cad_view.build_style 로 view.json + exports.zip — 엔진 판 표시만 창구가 채운다(복사본에는 git 이 없어서)"""
    import cad_view
    styles = {}
    for g in groups:
        G = cad_view.GROUPS[g]
        vpath, zpath, rep, files = cad_view.build_style(src, aama_dir, g, os.path.join(out, G["style_id"]), when)
        with open(vpath, encoding="utf-8") as f: view = json.load(f)
        view["source"].update(commit=ev.get("commit"), engine_source=ev.get("source"), built_by="service.py")
        with open(vpath, "w", encoding="utf-8") as f:
            json.dump(view, f, ensure_ascii=False, separators=(",", ":"))   # cad_view 와 같은 꼴(압축)
        bad = [r for r in rep if r[4] is False]
        styles[G["style_id"]] = {"group": g, "view": vpath, "zip": zpath, "files": len(files), "view_bytes": os.path.getsize(vpath),
                                 "zip_bytes": os.path.getsize(zpath), "checks_bad": [list(r) for r in bad]}
        try:                                                  # 맞물림 판정(3단계 화면의 초록/빨강) — 다시 만들기에도 같이 싣는다
            with open(os.path.join(src, "graded", "검산.json"), encoding="utf-8") as f:
                styles[G["style_id"]]["mesh"] = mesh_checks(json.load(f), g)
        except Exception:
            styles[G["style_id"]]["mesh"] = None
    return styles


def build_all(work, sources=None, groups=("top", "bottom"), aama=True, font=None, emit=False):
    """입력 A — 원본 .ai 에서 처음부터 끝까지. 일꾼 프로세스 안에서 부른다(엔진 모듈이 sys.argv·sys.stdout 을 만진다)."""
    groups = list(groups or ("top", "bottom"))
    for g in groups:
        if g not in ("top", "bottom"): raise ServiceError(f"모르는 옷 종류: {g}")
    src = _check_sources(sources)
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    gw = os.path.join(work, "gas-warmup"); d2, dg, ds = (os.path.join(gw, x) for x in ("2xl", "graded", "spec"))
    da, dc = os.path.join(work, "aama"), os.path.join(work, "cad")
    if HERE not in sys.path: sys.path.insert(0, HERE)
    fnt = font or resolve_font()
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    ev = engine_version()
    timings, t0 = {}, time.time()
    with font_shim(fnt["path"]):
        _step(1, "build", emit); t = time.time()
        _run_script("gas_warmup_build.py", [src["top"], src["bottom"], d2]); timings["build"] = round(time.time() - t, 1)
        _step(2, "grade", emit); t = time.time()
        _run_script("gas_warmup_grade.py", ["--pieces", os.path.join(d2, "pieces_after.json"), "--std-top", src["std_top"],
                                            "--std-pants", src["std_pants"], "--src-top", src["top"], "--src-bottom", src["bottom"],
                                            "--out", dg]); timings["grade"] = round(time.time() - t, 1)
        _step(3, "spec", emit); t = time.time()
        import gas_warmup_spec
        gas_warmup_spec.main(["--pieces", os.path.join(d2, "pieces_after.json"), "--graded", os.path.join(dg, "graded.json"),
                              "--out", ds]); timings["spec"] = round(time.time() - t, 1)
        _step(4, "aama", emit); t = time.time()
        if aama:
            import aama as A, tile_pdf
            A.FONT = fnt["path"]                                  # aama 는 «글꼴 파일이 있나» 를 먼저 본다 — 없으면 한글이 helv 로 깨진다
            A.main(["--graded", os.path.join(dg, "graded.json"), "--out", da])
            for ko, en in (("상의", "TOP"), ("하의", "BOTTOM")):    # README 와 같은 A4 분할 — 기준 2XL 1:1 PDF 를 자른다
                one = os.path.join(da, f"GAS_WARMUP_{en}_2XL_1대1.pdf")
                if os.path.isfile(one):
                    tile_pdf.tile(one, os.path.join(da, f"{ko}_2XL_A4분할.pdf"))
        timings["aama"] = round(time.time() - t, 1)
        _step(5, "view", emit); t = time.time()
        styles = _view_step(gw, da if aama else None, dc, groups, when, ev); timings["view"] = round(time.time() - t, 1)
    timings["total"] = round(time.time() - t0, 1)
    return {"ok": True, "mode": "sources", "work": work, "styles": styles, "font": fnt, "engine": ev,
            "sources": {k: os.path.basename(v) for k, v in src.items()}, "timings_s": timings, "peak_rss_mb": peak_rss_mb(),
            "made_at": when}


def regrade_all(work, group, rules, sources=None, full=False, font=None, emit=False):
    """F10 3단계 — 규칙표(전체)를 받아 그 옷을 다시 그레이딩한다. 일꾼 프로세스 안에서 부른다.
       full=False(미리보기): 그레이딩 시트·AAMA 를 안 만든다(약 10초) — 화면 자료와 맞물림 판정만
       full=True(새 버전 저장): 사이즈별 DXF·PDF·.ai + AAMA·RUL·A4 까지(다시 만들기와 같은 묶음)
       돌려주는 것: build_all 과 같은 모양 + rules(넘긴 표) · mesh(맞물림) · rules_echo_max_mm(만든 모양에서 다시 읽은 규칙과의 차)"""
    if group not in RULE_FRAME:
        raise ServiceError(f"모르는 옷 종류: {group}")
    table = check_rules(group, rules, full=True)                # 엔진에 넘기기 전에 — 빠진 칸이 있으면 트루잉 없는 표준 값이 섞인다
    src = _check_sources(sources)
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    gw = os.path.join(work, "gas-warmup"); d2, dg, ds = (os.path.join(gw, x) for x in ("2xl", "graded", "spec"))
    da, dc = os.path.join(work, "aama"), os.path.join(work, "cad")
    if HERE not in sys.path: sys.path.insert(0, HERE)
    fnt = font or resolve_font()
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    ev = engine_version()
    rpath = os.path.join(work, "rules_in.json")
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump({group: table}, f, ensure_ascii=False)
    timings, t0 = {}, time.time()
    with font_shim(fnt["path"]):
        _step(1, "build", emit); t = time.time()
        _run_script("gas_warmup_build.py", [src["top"], src["bottom"], d2]); timings["build"] = round(time.time() - t, 1)
        _step(2, "grade", emit); t = time.time()
        _run_script("gas_warmup_grade.py", ["--pieces", os.path.join(d2, "pieces_after.json"), "--std-top", src["std_top"],
                                            "--std-pants", src["std_pants"], "--src-top", src["top"], "--src-bottom", src["bottom"],
                                            "--out", dg, "--rules", rpath] + ([] if full else ["--no-export"]))
        timings["grade"] = round(time.time() - t, 1)
        _step(3, "spec", emit); t = time.time()
        import gas_warmup_spec
        gas_warmup_spec.main(["--pieces", os.path.join(d2, "pieces_after.json"), "--graded", os.path.join(dg, "graded.json"),
                              "--out", ds]); timings["spec"] = round(time.time() - t, 1)
        _step(4, "aama", emit); t = time.time()
        if full:
            import aama as A, tile_pdf
            A.FONT = fnt["path"]
            A.main(["--graded", os.path.join(dg, "graded.json"), "--out", da])
            ko, en = ("상의", "TOP") if group == "top" else ("하의", "BOTTOM")
            one = os.path.join(da, f"GAS_WARMUP_{en}_2XL_1대1.pdf")
            if os.path.isfile(one):
                tile_pdf.tile(one, os.path.join(da, f"{ko}_2XL_A4분할.pdf"))
        timings["aama"] = round(time.time() - t, 1)
        _step(5, "view", emit); t = time.time()
        styles = _view_step(gw, da if full else None, dc, [group], when, ev); timings["view"] = round(time.time() - t, 1)
    for sid, s in styles.items():                               # 넘긴 규칙이 정말 그대로 들어갔나 — 만든 모양에서 다시 읽어 견준다
        with open(s["view"], encoding="utf-8") as f:
            echo = rules_from_view(json.load(f))
        s["rules_echo_max_mm"] = max_rule_gap(table, echo)
        if s["rules_echo_max_mm"] > 0.1:
            raise ServiceError(f"넘긴 규칙과 만든 모양이 {s['rules_echo_max_mm']}mm 어긋납니다(엔진·화면 부호 확인 필요).")
    timings["total"] = round(time.time() - t0, 1)
    return {"ok": True, "mode": "regrade", "full": bool(full), "work": work, "styles": styles, "font": fnt, "engine": ev,
            "rules": table, "timings_s": timings, "peak_rss_mb": peak_rss_mb(), "made_at": when}


def build_view(src, out, aama_dir=None, groups=("top", "bottom")):
    """입력 B — 이미 만든 명세·그레이딩 결과 폴더에서 화면 자료만(⑤). 엔진 계산을 다시 하지 않아 가볍다."""
    if HERE not in sys.path: sys.path.insert(0, HERE)
    need = [os.path.join(src, "graded", "검산.json"), os.path.join(src, "spec", "spec_2XL수정.json")]
    miss = [p for p in need if not os.path.isfile(p)]
    if miss: raise ServiceError("명세·검산 결과가 없습니다: " + ", ".join(miss))
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    styles = _view_step(src, aama_dir, out, list(groups), when, engine_version())
    return {"ok": True, "mode": "results", "styles": styles, "peak_rss_mb": peak_rss_mb(), "made_at": when}


# ════════ 부모(서버) 쪽 — 일꾼 프로세스를 띄워 기다린다 ════════
def rebuild(work, groups=("top", "bottom"), sources=None, aama=True, timeout=1800, python=None, on_step=None, env=None):
    """서버가 부르는 함수 — 엔진을 «따로 띄운 프로세스» 에서 돌린다.
    왜 따로: ① 엔진 파일이 sys.argv·sys.stdout 을 만진다 ② 무거운 계산이 끝나면 메모리가 운영체제로 통째로 돌아간다
             ③ 엔진이 죽어도 서버는 산다.
    on_step(i, total, name) — 단계가 넘어갈 때마다(진행률). 반환: build_all 의 결과 + log(일꾼 출력 파일 주소)."""
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    res_path = os.path.join(work, "result.json")
    cmd = [python or sys.executable, os.path.abspath(__file__), "build", "--work", work, "--result", res_path, "--emit-steps",
           "--groups", *groups]
    if not aama: cmd.append("--no-aama")
    for k in SOURCE_KEYS:
        if sources and sources.get(k): cmd += [f"--{k.replace('_', '-')}", sources[k]]
    return _spawn(cmd, work, res_path, timeout, on_step, env)


def regrade(work, group, rules, full=False, sources=None, timeout=900, python=None, on_step=None, env=None):
    """서버가 부르는 함수(F10 3단계) — 규칙표(전체)로 다시 그레이딩. rebuild 와 같은 «따로 띄운 일꾼» 길.
    rules 는 부모에서 먼저 검사한다(틀린 표로 1분짜리 일꾼을 띄우지 않게)."""
    table = check_rules(group, rules, full=True)
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    res_path, rfile = os.path.join(work, "result.json"), os.path.join(work, "rules_req.json")
    with open(rfile, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False)
    cmd = [python or sys.executable, os.path.abspath(__file__), "regrade", "--work", work, "--group", group, "--rules-file", rfile,
           "--result", res_path, "--emit-steps"] + (["--full"] if full else [])
    for k in SOURCE_KEYS:
        if sources and sources.get(k): cmd += [f"--{k.replace('_', '-')}", sources[k]]
    return _spawn(cmd, work, res_path, timeout, on_step, env)


def _spawn(cmd, work, res_path, timeout, on_step, env):
    """일꾼 프로세스를 띄워 출력은 engine.log 에, 단계 줄(@@STEP)은 on_step 으로 — 끝나면 result.json 을 읽어 돌려준다"""
    log_path = os.path.join(work, "engine.log")
    e = dict(os.environ if env is None else env); e["PYTHONIOENCODING"] = "utf-8"; e.setdefault("PYTHONUTF8", "1")
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", env=e)
    killed = {"v": False}

    def _kill():
        killed["v"] = True
        try: p.kill()
        except Exception: pass
    timer = threading.Timer(timeout, _kill); timer.daemon = True; timer.start()
    tail = []
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            for line in p.stdout:
                log.write(line)
                tail.append(line); tail[:] = tail[-40:]
                if line.startswith(STEP_MARK) and on_step:
                    try:
                        _, frac, name = line.split()[:3]; i, n = frac.split("/")
                        on_step(int(i), int(n), name.strip())
                    except Exception:
                        pass
        rc = p.wait()
    finally:
        timer.cancel()
        if p.stdout: p.stdout.close()                         # 읽는 관 닫기(열어 둔 채 두면 파일 손잡이가 샌다)
    if killed["v"]:
        raise ServiceError(f"엔진이 {timeout}초 안에 끝나지 않아 멈췄습니다.")
    if rc != 0 or not os.path.isfile(res_path):
        raise ServiceError("엔진이 실패했습니다(종료 코드 %s). 마지막 출력:\n%s" % (rc, "".join(tail[-15:]).strip()))
    with open(res_path, encoding="utf-8") as f: out = json.load(f)
    out["log"] = log_path; out["wall_s"] = round(time.time() - t0, 1)
    return out


# ════════ view.json 견주기 — «서버가 만든 것 = 로컬이 만든 것» 확인용 ════════
def _unflat(a):
    return [(a[k], a[k + 1]) for k in range(0, len(a), 2)]


def compare_views(a, b):
    """두 view.json(dict)의 그림을 점 하나씩 견준다 → {"max_mm", "points", "diffs": [구조가 다른 곳]}
    판 표시(made_at·commit 등)·묶음 지문은 보지 않는다 — PDF 안 날짜 때문에 묶음 지문은 매번 다르다."""
    diffs, worst, npts = [], 0.0, 0
    q = a.get("q");
    if q != b.get("q"): diffs.append(f"q {a.get('q')} != {b.get('q')}")
    for k in ("sheet",):
        if a.get(k) != b.get(k): diffs.append(f"{k} 다름")
    sa, sb = a.get("style", {}), b.get("style", {})
    for k in ("id", "sizes", "pieces", "base_size", "graded_from"):
        if sa.get(k) != sb.get(k): diffs.append(f"style.{k} 다름")
    for sid in sa.get("sizes") or []:
        A, B = a["sizes"].get(sid), b["sizes"].get(sid)
        if A is None or B is None: diffs.append(f"{sid} 없음"); continue
        if len(A["pieces"]) != len(B["pieces"]): diffs.append(f"{sid} 조각 수 다름"); continue
        for pa, pb in zip(A["pieces"], B["pieces"]):
            tag = f"{sid}/{pa.get('name')}"
            if pa.get("name") != pb.get("name") or pa.get("nodes") != pb.get("nodes"): diffs.append(f"{tag} 이름·기준점 다름")
            lines = [("seam", pa.get("seam"), pb.get("seam")), ("cut", pa.get("cut"), pb.get("cut")),
                     ("grain", pa.get("grain") or [], pb.get("grain") or []), ("fold", pa.get("fold") or [], pb.get("fold") or [])]
            lines += [(f"internal{i}", x.get("p"), y.get("p")) for i, (x, y) in enumerate(zip(pa["internal"], pb["internal"]))]
            lines += [(f"notch{i}", x, y) for i, (x, y) in enumerate(zip(pa["notches"], pb["notches"]))]
            for x, y in zip(pa["holes"], pb["holes"]):                 # 구멍 = [중심x, 중심y, 반지름] 세 칸
                worst = max(worst, math.dist(x[:2], y[:2]) * q, abs(x[2] - y[2]) * q); npts += 1
            if len(pa["internal"]) != len(pb["internal"]) or len(pa["notches"]) != len(pb["notches"]) or len(pa["holes"]) != len(pb["holes"]):
                diffs.append(f"{tag} 안쪽선·노치·구멍 수 다름")
            for nm, x, y in lines:
                if len(x) != len(y): diffs.append(f"{tag} {nm} 점 수 다름 {len(x)}/{len(y)}"); continue
                for u, v in zip(_unflat(x), _unflat(y)):
                    worst = max(worst, math.dist(u, v) * q); npts += 1
        ca = [(c.get("key"), c.get("value"), c.get("ok")) for c in A.get("checks") or []]
        cb = [(c.get("key"), c.get("value"), c.get("ok")) for c in B.get("checks") or []]
        if ca != cb: diffs.append(f"{sid} 검산표 다름")
    fa = sorted((f["path"], f["kind"]) for f in a.get("files") or []); fb = sorted((f["path"], f["kind"]) for f in b.get("files") or [])
    if fa != fb: diffs.append("묶음 파일 목록 다름")
    return {"max_mm": round(worst, 4), "points": npts, "diffs": diffs}


# ════════ 명령줄 ════════
def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="재단 패턴 엔진 창구(F10 2단계)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="원본 .ai → view.json + exports.zip (입력 A)")
    b.add_argument("--work", required=True); b.add_argument("--result")
    b.add_argument("--groups", nargs="*", default=["top", "bottom"]); b.add_argument("--no-aama", action="store_true")
    b.add_argument("--emit-steps", action="store_true", help="진행 단계 줄(@@STEP)을 찍는다 — 부모가 진행률로 쓴다")
    for k in SOURCE_KEYS: b.add_argument(f"--{k.replace('_', '-')}")
    v = sub.add_parser("view", help="이미 만든 명세·검산 결과 → view.json + exports.zip (입력 B)")
    v.add_argument("--src", required=True); v.add_argument("--out", required=True); v.add_argument("--aama")
    v.add_argument("--groups", nargs="*", default=["top", "bottom"]); v.add_argument("--result")
    g = sub.add_parser("regrade", help="규칙표(전체 JSON) → 그 옷만 다시 그레이딩 (F10 3단계)")
    g.add_argument("--work", required=True); g.add_argument("--group", required=True, choices=sorted(RULE_FRAME))
    g.add_argument("--rules-file", required=True, help="{조각: {기준점: {사이즈: [Δx, Δy]}}} — 전체 표")
    g.add_argument("--full", action="store_true", help="그레이딩 시트·AAMA 까지(새 버전 저장용). 없으면 미리보기")
    g.add_argument("--result"); g.add_argument("--emit-steps", action="store_true")
    for k in SOURCE_KEYS: g.add_argument(f"--{k.replace('_', '-')}")
    sub.add_parser("font", help="쓰게 될 글꼴")
    a = ap.parse_args(argv)
    if a.cmd == "font":
        print(json.dumps(resolve_font(), ensure_ascii=False)); return 0
    try:
        if a.cmd == "build":
            r = build_all(a.work, {k: getattr(a, k) for k in SOURCE_KEYS}, a.groups, not a.no_aama, emit=a.emit_steps)
        elif a.cmd == "regrade":
            with open(a.rules_file, encoding="utf-8") as f: rules = json.load(f)
            r = regrade_all(a.work, a.group, rules, {k: getattr(a, k) for k in SOURCE_KEYS}, a.full, emit=a.emit_steps)
        else:
            r = build_view(a.src, a.out, a.aama, a.groups)
    except ServiceError as e:
        print(f"[service] 실패: {e}", flush=True); return 2
    r["peak_rss_mb"] = peak_rss_mb()                          # 끝난 뒤 다시 — 마지막 단계까지 포함한 최고치
    r["guard"] = os.environ.get("GRADER_ENGINE_GUARD")        # 그레이더 일꾼 안전띠(sitecustomize)가 건 것 — 없으면 None(명령줄)
    r.update(vm_status_mb())                                  # 리눅스: VmPeak·VmHWM (안전띠 상한과 견줄 숫자)
    if getattr(a, "result", None):
        tmp = a.result + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False, indent=1)
        os.replace(tmp, a.result)
    print(f"[service] 끝 · 최고 메모리 {r['peak_rss_mb']} MB" + (f" · VmPeak {r['vm_peak_mb']} MB" if r.get("vm_peak_mb") else "")
          + (f" · 안전띠 {r['guard']}" if r.get("guard") else "") + " · "
          + " · ".join(f"{k} {s['view_bytes']:,}B/{s['zip_bytes']:,}B" for k, s in r["styles"].items()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
