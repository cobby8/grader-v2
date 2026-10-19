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
    res_path, log_path = os.path.join(work, "result.json"), os.path.join(work, "engine.log")
    cmd = [python or sys.executable, os.path.abspath(__file__), "build", "--work", work, "--result", res_path, "--emit-steps",
           "--groups", *groups]
    if not aama: cmd.append("--no-aama")
    for k in SOURCE_KEYS:
        if sources and sources.get(k): cmd += [f"--{k.replace('_', '-')}", sources[k]]
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
    sub.add_parser("font", help="쓰게 될 글꼴")
    a = ap.parse_args(argv)
    if a.cmd == "font":
        print(json.dumps(resolve_font(), ensure_ascii=False)); return 0
    try:
        if a.cmd == "build":
            r = build_all(a.work, {k: getattr(a, k) for k in SOURCE_KEYS}, a.groups, not a.no_aama, emit=a.emit_steps)
        else:
            r = build_view(a.src, a.out, a.aama, a.groups)
    except ServiceError as e:
        print(f"[service] 실패: {e}", flush=True); return 2
    r["peak_rss_mb"] = peak_rss_mb()                          # 끝난 뒤 다시 — 마지막 단계까지 포함한 최고치
    if getattr(a, "result", None):
        tmp = a.result + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False, indent=1)
        os.replace(tmp, a.result)
    print(f"[service] 끝 · 최고 메모리 {r['peak_rss_mb']} MB · " + " · ".join(f"{k} {s['view_bytes']:,}B/{s['zip_bytes']:,}B"
                                                                       for k, s in r["styles"].items()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
