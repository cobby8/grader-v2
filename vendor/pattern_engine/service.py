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
#   F10 4단계(마커·요척):
#     서버:    service.marker(work, "top", {"S": 1, …}, width_cm=150, gap_mm=3, rules=…|None, check_view=<버전 view.json>, on_step=…)
#              ← 일꾼 두 번: ① 원본 → 그레이딩(graded.json, 그 버전 모양과 같은지 확인) ② marker.py 로 배치(PDF·DXF·PNG·JSON)
#     명령줄:  python tools/pattern-engine/service.py graded --work <폴더> --group top [--rules-file 표.json] [--check-view view.json]
#              python tools/pattern-engine/service.py marker --work <폴더> --graded graded.json --request-file 요청.json
#     배치 계산은 marker.main(명령줄과 «같은 함수») 을 그대로 부른다 → 같은 입력이면 명령줄 결과와 길이·조각 자리가 같다.
#     서버 기본: 일꾼 수 1 · FFT 기억 100MB · 탐색 한도 120초(MARKER_SERVER) — Render 512MB 안
#   F10 6단계(새 스타일 들여오기 — OptiCad 여러 사이즈 .ai):
#     서버:    service.import_style(work, 원본.ai, "M", "std-warmup-top", on_step=…)   ← 일꾼(약 30초 · 최고 약 140MB) → view.json·exports.zip·확인 목록
#              service.restyle(work, 그 버전 exports.zip, rule_changes=…|names=…)      ← 이름 고치기 · 규칙 바꿔 다시 그레이딩(약 6초)
#              service.marker(work, "imported", {…}, spec_zip=그 버전 exports.zip, spec_files={경로: 지문}, …)   ← 명세 묶음으로 마커
#     명령줄:  python tools/pattern-engine/service.py import --work <폴더> --src 원본.ai --base M --style-id std-warmup-top
#              python tools/pattern-engine/service.py restyle --work <폴더> --zip exports.zip [--changes-file 표.json] [--names-file 이름.json]
#     입장 판정(admit_import): 파일 크기로 메모리·시간을 어림(IMPORT_FIT 실측) — 512MB 상자 안 · 일꾼 안 시계(--max-seconds)로 원본 읽기 상한
#   🚫 쇼핑몰 운영 DB·드라이브를 읽지도 쓰지도 않는다. 결과는 <work> 안에만 생긴다(주문 명단은 부르는 쪽이 넘긴다).
import sys, os, re, json, math, time, shutil, argparse, datetime, contextlib, subprocess, threading, runpy, hashlib

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

# ════════ 마커(F10 4단계) — 원단 폭에 사이즈별 벌수를 깔아 «벌당 요척» ════════
MARKER_STEPS = ["build", "grade", "check", "marker"]       # ①② 원본 → 그레이딩 · ③ 그 버전 모양과 같은가 · ④ 배치+파일
STEP_KO.update({"check": "버전 모양 확인", "marker": "원단 배치(마커)·파일"})
MARKER_WIDTH_CM = (50.0, 300.0)                             # 원단 폭(cm) 허용 범위 — 실제 원단은 110~180cm
MARKER_GAP_MM = (0.0, 20.0)                                 # 조각 간격(mm)
MARKER_MAX_BUNDLES = 200                                    # 한 번에 까는 벌수 합 상한(조각 수·시간이 벌수에 비례)
MARKER_BUDGET_MAX_S = 120.0                                 # 탐색 시간 상한(초) — 서버 일꾼 한 명이 오래 붙잡지 않게
# 서버 기본값 — 결과는 일꾼 수·기억 한도와 무관(속도만 다르다).
#   2026-10-20 실측(윈도우 · 빠르게 · 상의): FFT 기억 100MB → 0 으로 7벌 315→216MB · 14벌 386→287MB, 시간은 거의 같다(8.4→8.6초)
#   → 서버는 기억하지 않는다(cache 0)
MARKER_SERVER = {"jobs": 1, "cache_mb": 0.0, "budget": 120.0, "seed": 0}
# ── 서버 입장 판정(admit_marker) — «벌수 × 장수» 로 일꾼 메모리·시간을 미리 어림한다(근거: MARKER_MODEL 실측 표) ──
MARKER_BOX_MB = 512.0                                       # Render starter 상자
MARKER_SERVER_MB = 160.0                                    # 서버(uvicorn) 몫 — 실측 151MB(마커 2번 돈 뒤) + 여유
MARKER_MARGIN_MB = 20.0                                     # 어림 오차 여유
MARKER_SLOW = 1.3                                           # Render 가 이 PC 보다 느린 배수 · 시간 어림에 곱한다
#   2026-10-20 Render 첫 실측 ÷ 어림(배수 1): 마커(들여온 상의 13벌·117장) 62.4초 ÷ 56.9초 = 1.10 ·
#   들여오기(표준 웜업 상의 276KB) 37초 ÷ 60.7초 = 0.61(어림 자체가 넉넉) → 큰 쪽 + 여유로 1.3(예전 가정 2.0 은 과했다)
#   참고: 들여오기 Render 37초 ÷ 윈도우 실측 25.9초 = 1.43 이 «서버가 느린 정도» 그대로지만, 어림이 실측의 2.3배라 1.3 을 곱해도 덮는다
# 리눅스 메모리 배수 — 어림(MARKER_FIT·IMPORT_FIT)은 윈도우 실측으로 맞췄는데 리눅스 RSS 가 더 크다.
#   2026-10-20 Render 실측: 마커 13벌 어림 228.1MB → 실제 289.2MB(×1.27) · 들여오기 어림 152.7 → 실제 152.5MB
#   → 리눅스에서는 메모리 어림에 1.3 을 곱한다(PATTERN_ENGINE_MEM_FACTOR 로 바꿀 수 있다 · 윈도우는 1.0)
def _mem_factor():
    try:
        v = float(os.environ.get("PATTERN_ENGINE_MEM_FACTOR") or 0)
    except ValueError:
        v = 0.0
    if v > 0:
        return min(5.0, max(0.5, v))
    return 1.3 if sys.platform.startswith("linux") else 1.0
MARKER_GRADE_S = 12.0                                       # 그레이딩 일꾼(원본 → graded + 버전 대조) 이 PC 실측 9~10초
# 실측 맞춤(2026-10-20 · 윈도우 · 일꾼 1·cache 0 · 폭 150cm · 빠르게 · 배치+PDF/DXF/PNG 합) — 아래 값보다 늘 «같거나 크게» 어림하게 맞췄다
#   상의(벌당 17장)  조각 136 → 204MB·19초 | 238 → 213MB·32초 | 476 → 254MB·80초 | 714 → 294MB·217초 | 952 → 339MB·517초
#   하의(벌당 14장)  조각 112 → 224MB·25초 | 196 → 243MB·64초 | 210 → 247MB·95초 | 392 → 290MB·231초   ← 하의 조각이 길어 장당 훨씬 느리다
#   (같은 크기도 다시 재면 ±30% 흔들린다 — 하의 210장이 어림 76초보다 느린 95초 → 계수를 올려 «넘치지 않게» 맞췄다)
#   시간은 조각 수에 «제곱보다 가파르게» 는다(끝부분 압축·다시 넣기) → 상의는 3제곱 항, 하의는 1.85제곱으로 맞췄다
#   여러 번 깔기(일꾼 1·한도 95~120초) 메모리 = 빠르게 + 0~16MB 실측(상의 8벌 211·14벌 229·24벌 245 · 하의 8벌 232·15벌 236MB) → 몫 30MB
MARKER_FIT = {
    "top": {"rss0": 185.0, "rss_per_piece": 0.165, "t0": 13.0, "t_lin": 0.06, "t_k": 5.5e-7, "t_pow": 3.0},
    "bottom": {"rss0": 200.0, "rss_per_piece": 0.24, "t0": 8.0, "t_lin": 0.0, "t_k": 0.0055, "t_pow": 1.85},   # t0: 작은 주문(3벌 10초)도 넘지 않게
    "search_mb": 30.0,                                        # 여러 번 깔기 메모리 몫(실측 최대 +16MB)
    # 원단 폭·간격 배수(2026-10-20 재리뷰 실측 — 폭 150·간격 3 기준 대비, 빠르게):
    #   상의 14벌  폭 220 ×1.33 · 폭 300 ×1.59 · 간격 10 ×1.25 · 간격 20 ×1.18 · 폭 300+간격 20 ×1.50 | 상의 24벌 폭 300+간격 20 ×2.00(132초)
    #   하의 8벌   폭 300 ×1.53 · 간격 20 ×1.62 · 폭 300+간격 20 ×2.06 | 하의 12벌 폭 300+간격 20 ×2.07(78초)
    #   → 시간 × max(1, (폭/150)^0.75) × (1 + 0.035 × max(0, 간격−3)) — 실측보다 늘 크게(폭 300+간격 20 = ×2.69).
    #     폭이 150 보다 좁으면 1 로 둔다(격자는 좁아도 마커가 길어진다 — 줄여 어림하지 않는다)
    #   메모리: 폭 150 을 넘는 1cm 마다 +0.15MB(하의 12벌 폭 300+간격 20 = 258MB, 기준 어림 240MB)
    "w_pow": 0.75, "gap_per_mm": 0.035, "rss_per_cm": 0.15,
    "files_share": 0.3,                                       # 시간 중 파일 내보내기 몫(상의 476장 80초 중 24초)
}
MARKER_VIEW_TOL_MM = 0.05                                   # «다시 만든 모양 = 그 버전 모양» 허용 차(view.json 점 줄이기 오차와 같다)
MARKER_FILES = {"json": "marker.json", "pdf": "marker.pdf", "dxf": "marker.dxf", "png": "marker.png"}   # 결과 파일(영문 이름)
_SIZE_ALIAS = {"XXL": "2XL", "XXXL": "3XL", "XXXXL": "4XL", "XXXXXL": "5XL", "2X": "2XL", "3X": "3XL", "4X": "4XL", "5X": "5XL"}

# ════════ 새 스타일 들여오기(F10 6단계) — OptiCad .ai → 들여온 스타일(style_import) ════════
IMPORT_STEPS = ["read", "pieces", "verify", "bundle"]       # 원본 읽기 · 조각마다 규칙 읽기(대부분의 시간) · 원본 대조 · 묶음
INTAKE_STEPS = ["intake_read", "intake_draft", "intake_grade", "intake_export", "intake_bundle"]   # 패턴 의뢰 → 패턴(2026-10-22) — 들여오기 «read» 와 겹치지 않게 intake_ 를 붙인다
RESTYLE_STEPS = ["load", "apply", "verify", "bundle"]       # 이름 고치기·규칙 바꾸기 — 묶음 열기 · 바꾸기 · 원본 대조 · 묶음
IMARKER_STEPS = ["specs", "marker"]                        # 들여온 스타일 마커 — 명세 꺼내기·지문 확인 · 배치
STEP_KO.update({"read": "원본 .ai 읽기", "pieces": "조각마다 그레이딩 규칙 읽기", "bundle": "명세·화면 자료·묶음 쓰기",
                "load": "묶음 열기", "apply": "이름·규칙 바꾸기", "verify": "원본 대조·재생성 검산",
                "specs": "사이즈별 명세 꺼내기·지문 확인"})
STEP_KO.update({"intake_read": "의뢰 치수 읽기", "intake_draft": "기준 사이즈 패턴 그리기", "intake_grade": "S~3XL 그레이딩",
                "intake_export": "사이즈별 .ai·DXF·PDF 쓰기", "intake_bundle": "확인표·화면 자료·묶음"})
IMPORT_MAX_BYTES = 50 * 1024 * 1024                         # 원본 .ai 업로드 상한(설계 §7)
IMPORT_MAX_SIZES = 30                                       # 사이즈 레이어 상한(어림 밖 — 이상한 파일)
IMPORT_MAX_SECONDS = 600.0                                  # 일꾼 안 시계 — 원본 읽기·규칙 읽기 전체 상한(초)
# 입장 판정 어림 — 2026-10-20 실측(윈도우 · 일꾼 한 명): 표준 웜업 상의 276KB 13사이즈 → 최고 135.5MB · 26.3초 |
#   팬츠 219KB 13사이즈 → 116.7MB · 33.4초. 엔진만 불러온 바닥 84MB. 메모리·시간 모두 «원본 점 수» 에 비례 → 파일 크기로 어림.
#   일꾼(창구 + 엔진)으로 재면 상의 142.6MB(2026-10-20). 아래 값은 실측보다 늘 크게(상의 153MB·61초 · 팬츠 142MB·50초) 어림한다(시험 ImportRun 이 지킨다)
IMPORT_FIT = {"rss0": 100.0, "rss_per_mb": 200.0, "t0": 8.0, "t_per_mb": 200.0}   # 시간: 다른 시험과 겹쳐 돌 때 팬츠 41.4초 실측 → 160 에서 올림
IMPORT_SIZE_RE = re.compile(r"^(\d{0,2}X{0,4}[SML]|X{1,4}[SL]|F|FREE|\d{1,3}(호)?)$", re.I)   # style_import.SIZE_RE 와 같다(시험이 견준다)
IMPORT_STYLE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]")   # 그레이더 STYLE_ID_RE 와 같다(디스크 폴더·창고 열쇠)
IMPORT_NAME_BAD = set('<>"/\\')                              # 조각·기준점 이름에 못 쓰는 글자(style_import.NAME_BAD 와 같다)
IMPORT_MESH_DEF = [("valid", "명세 검사(문제 수)", 0.0), ("twist", "재봉선 꼬임(조각 수)", 0.0),
                   ("cover", "재단선 밖 재봉선(mm)", 0.5), ("echo", "규칙과 기준점 차(mm)", 0.01), ("notch", "노치 수 차", 0.0)]


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


def current_rss_mb():
    """이 프로세스가 «지금» 쓰는 실제 RAM(MB) — 서버가 마커 입장 판정에 «서버 몫» 으로 쓴다(고정값 대신). 못 재면 None"""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t)] + [(f"x{i}", ctypes.c_size_t) for i in range(6)]
            c = PMC(); c.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32"); psapi = ctypes.WinDLL("psapi")
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return round(c.WorkingSetSize / 2 ** 20, 1)
            return None
        with open("/proc/self/status", encoding="ascii", errors="replace") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        return None
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


# ════════ 들여오기·들여온 스타일 — 서버(부모)가 일꾼을 띄우기 전에 부르는 것 (표준 라이브러리만) ════════
def ai_header_kind(head):
    """파일 머리(앞부분 바이트) → "ps"(PostScript .ai — 읽을 수 있다) · "pdf"(PDF 형식 .ai — 아직 못 읽는다) · None(.ai 아님)
    OptiCad «Adobe Export» 는 «%!PS-Adobe-3.0» 으로 시작한다(2026-10-20 표준 웜업·가스 원본 4개 실측)."""
    h = bytes(head[:1024] or b"")
    if h.startswith(b"\xef\xbb\xbf"): h = h[3:]
    if h.startswith(b"%!PS-Adobe"): return "ps"
    if h.startswith(b"%PDF-"): return "pdf"
    return None


_LAYER_RE = re.compile(rb"^[ \t]*\(([^)\r\n]{1,40})\)[ \t]+Ln[ \t]*\r?$", re.M)   # opticad.parse 의 레이어 이름 줄 «(M) Ln»
_SIZES13 = ["5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


def ai_complete(data):
    """파일 끝 표시(%%EOF)가 있는가 — 없으면 올리기·내보내기가 중간에 끊긴 파일(style_import.prescan 과 같은 규칙)"""
    return b"%%EOF" in bytes(data[-2048:])


def peek_sizes(data):
    """원본 바이트에서 «사이즈처럼 생긴 레이어 이름» 만 빠르게(엔진 없이) — 기준 사이즈 확인·입장 판정용.
    정본 판정은 일꾼(style_import.read_ai)이 한다. 표준 13사이즈면 작은 것부터 정렬"""
    out = []
    for m in _LAYER_RE.finditer(bytes(data)):
        nm = m.group(1).decode("cp949", errors="replace").strip()
        if nm and nm not in ("CUT", "SEW", "DRAW") and IMPORT_SIZE_RE.match(nm) and re.fullmatch(r"[A-Za-z0-9]{1,8}", nm) and nm not in out:
            out.append(nm)
            if len(out) > IMPORT_MAX_SIZES: break
    if out and all(s in _SIZES13 for s in out): out.sort(key=_SIZES13.index)
    return out


def default_style_id(filename, data):
    """스타일 번호를 비워 두면 — 파일 이름에서(영문 소문자·숫자·- 만). 남는 것이 없거나 짧으면 «style-지문8자리»"""
    stem = os.path.splitext(os.path.basename(str(filename or "").replace("\\", "/")))[0].lower()
    s = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")[:64].strip("-")
    if not IMPORT_STYLE_ID_RE.fullmatch(s):
        s = "style-" + hashlib.sha256(bytes(data)).hexdigest()[:8]
    return s


def estimate_import(nbytes):
    """들여오기 일꾼 최고 메모리(MB)·시간(초, 이 PC) 어림 — IMPORT_FIT(실측보다 늘 크게)"""
    mb = nbytes / 2 ** 20; F = IMPORT_FIT
    rss = (F["rss0"] + F["rss_per_mb"] * mb) * _mem_factor()      # 리눅스 배수(_mem_factor)
    return {"mb": round(mb, 3), "rss_mb": round(rss, 1), "secs": round(F["t0"] + F["t_per_mb"] * mb, 1)}


def admit_import(nbytes, n_sizes, time_limit_s=IMPORT_MAX_SECONDS, box_mb=MARKER_BOX_MB, server_mb=MARKER_SERVER_MB, slow=MARKER_SLOW):
    """들여오기 입장 판정 — 크기·사이즈 수를 먼저 보고, 어림 메모리가 상자(512MB − 서버 몫 − 여유)·시간 한도를 넘으면 ServiceError.
    반환: 어림 + 일꾼 안 시계(max_seconds)"""
    if nbytes <= 0:
        raise ServiceError("원본 파일이 비어 있습니다.")
    if nbytes > IMPORT_MAX_BYTES:
        raise ServiceError(f"원본이 너무 큽니다({nbytes / 2 ** 20:.1f}MB — {IMPORT_MAX_BYTES // 2 ** 20}MB 이하).")
    if n_sizes < 2:
        raise ServiceError("사이즈 레이어가 둘 이상인 OptiCad «Adobe Export» .ai 만 들여올 수 있습니다(규칙은 사이즈 사이 이동량이라).")
    if n_sizes > IMPORT_MAX_SIZES:
        raise ServiceError(f"사이즈 레이어가 너무 많습니다({n_sizes}개 — {IMPORT_MAX_SIZES}개 이하).")
    e = estimate_import(nbytes); F = IMPORT_FIT
    cap_mb = box_mb - server_mb - MARKER_MARGIN_MB
    need_s = slow * e["secs"]
    if e["rss_mb"] > cap_mb or need_s > time_limit_s:
        max_mb = min((cap_mb / _mem_factor() - F["rss0"]) / F["rss_per_mb"], (time_limit_s / slow - F["t0"]) / F["t_per_mb"])
        raise ServiceError(f"원본이 서버에서 읽기엔 큽니다({e['mb']:.2f}MB — 메모리·시간 한도로 약 {max(0.0, max_mb):.2f}MB 까지). "
                           "사이즈를 나눠 내보내 주세요.")
    return dict(e, sizes=n_sizes, cap_mb=cap_mb, need_s=round(need_s, 1), slow=slow, max_seconds=float(time_limit_s))


def imported_rules_ui(doc):
    """들여온 스타일 rules.json → 화면 규칙표 {"rules": {조각: {기준점: {사이즈: [Δx, Δy]}}}, "frame", "sizes", "base_size"}
    값 = 기준 사이즈 대비 이동량(mm · 조각 좌표 · y 위 +). 틀 = {조각: {기준점: [[기준점, 1]]}} — 화면 점 이동 = (Δx, −Δy)
    (가스 RULE_FRAME 과 같은 꼴이라 그레이딩 화면이 그대로 쓴다)"""
    try:
        sizes = [str(s) for s in doc["sizes"]]; base = str(doc["base_size"]); T = doc["rules"]; pieces = doc["pieces"]
        table, frame = {}, {}
        for pc, pr in pieces.items():
            for k in pr.get("seam") or []:
                nm = k.get("name")
                if not isinstance(nm, str) or not nm: continue
                row = T[int(k["rule"])]
                table.setdefault(pc, {})[nm] = {s: [float(row[j][0]) + 0.0, float(row[j][1]) + 0.0] for j, s in enumerate(sizes)}
                frame.setdefault(pc, {})[nm] = [[nm, 1]]
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        raise ServiceError("들여온 스타일의 규칙표(rules.json)를 읽지 못했습니다.")
    return {"rules": table, "frame": frame, "sizes": sizes, "base_size": base}


def check_imported_changes(ui, changes):
    """들여온 스타일 규칙 변경(바꾼 칸만) 검사 → 깨끗한 사본. 틀리면 ServiceError(한국어) — check_rules 의 들여온 판"""
    if not isinstance(changes, dict):
        raise ServiceError("규칙표는 {조각: {기준점: {사이즈: [Δx, Δy]}}} 모양이어야 합니다.")
    frame, sizes, base = ui["frame"], ui["sizes"], ui["base_size"]
    out = {}
    for pc, pts in changes.items():
        if pc not in frame or not isinstance(pts, dict):
            raise ServiceError(f"그레이딩할 수 없는 조각: {str(pc)[:30]}")
        for k, bys in pts.items():
            if k not in frame[pc] or not isinstance(bys, dict):
                raise ServiceError(f"{pc} 에 «{str(k)[:30]}» 기준점이 없습니다.")
            for s, v in bys.items():
                if s not in sizes:
                    raise ServiceError(f"모르는 사이즈: {str(s)[:20]}")
                if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(_num(a) for a in v)):
                    raise ServiceError(f"{pc} {k} {s} 값은 숫자 두 개 [Δx, Δy] 여야 합니다.")
                dx, dy = float(v[0]), float(v[1])
                if abs(dx) > RULE_MAX_MM or abs(dy) > RULE_MAX_MM:
                    raise ServiceError(f"{pc} {k} {s} 이동량이 너무 큽니다(±{RULE_MAX_MM:.0f}mm 이하).")
                if s == base and (abs(dx) > 1e-6 or abs(dy) > 1e-6):
                    raise ServiceError(f"기준 사이즈({base})는 움직이지 않습니다 — {pc} {k}")
                out.setdefault(pc, {}).setdefault(k, {})[s] = [dx, dy]
    return out


def _clean_name(v, n, what):
    if not isinstance(v, str):
        raise ServiceError(f"{what}은(는) 글자여야 합니다.")
    s = " ".join(v.split())                                    # 앞뒤·겹친 공백 정리
    if not s or len(s) > n:
        raise ServiceError(f"{what}은(는) 1~{n}자여야 합니다.")
    if any(c in IMPORT_NAME_BAD or not c.isprintable() for c in s):
        raise ServiceError(f"{what}에 쓸 수 없는 글자가 있습니다(< > \" / \\ 와 제어 문자).")
    return s


def check_names(conf, payload):
    """이름 확인 화면의 변경 검사 → 깨끗한 사본 {"pieces": {지금 이름: {바뀐 칸만}}}. 틀리면 ServiceError(한국어).
    conf = 그 버전의 confirm.json. 바꿀 수 있는 것: name(조각 이름) · en_name(DXF 영문) · qty(장수 1~20) · mirror(2장 이상일 때 좌우 짝?)
    · points({옛 기준점: 새 이름}) · confirmed(확인함). 모양은 바꿀 수 없다(좌표·규칙 칸이 없다)"""
    if not isinstance(payload, dict) or not isinstance(payload.get("pieces"), dict) or not payload["pieces"]:
        raise ServiceError("바꿀 조각이 없습니다({pieces: {조각: {…}}}).")
    known = {c.get("piece"): c for c in (conf or {}).get("pieces") or [] if isinstance(c, dict)}
    out = {}
    for cur, ch in payload["pieces"].items():
        if cur not in known:
            raise ServiceError(f"이 판에 없는 조각: {str(cur)[:30]}")
        if not isinstance(ch, dict):
            raise ServiceError(f"{cur} 의 변경 모양이 다릅니다.")
        bad = set(ch) - {"name", "en_name", "qty", "mirror", "points", "confirmed"}
        if bad:
            raise ServiceError(f"바꿀 수 없는 칸: {sorted(bad)[0][:20]}")
        c = known[cur]; o = {}
        if ch.get("name") is not None:
            nm = _clean_name(ch["name"], 40, "조각 이름")
            if nm != cur: o["name"] = nm
        if ch.get("en_name") is not None:
            if not isinstance(ch["en_name"], str):
                raise ServiceError("영문 이름은 글자여야 합니다.")
            en = " ".join(ch["en_name"].upper().split())
            if not re.fullmatch(r"[A-Z0-9 _-]{0,30}", en):
                raise ServiceError("영문 이름은 영문·숫자·공백·- _ 만 30자까지 쓸 수 있습니다(DXF 에 들어갑니다).")
            if (en or None) != (c.get("en_name") or None): o["en_name"] = en
        if ch.get("qty") is not None:
            q = _int_like(ch["qty"])
            if q is None or not (1 <= q <= 20):
                raise ServiceError(f"{cur} 장수는 1~20 사이 정수여야 합니다.")
            if q != int(c.get("qty") or 1): o["qty"] = q
        for key, ko in (("mirror", "좌우 짝"), ("confirmed", "확인함")):
            if ch.get(key) is not None:
                if not isinstance(ch[key], bool):
                    raise ServiceError(f"{ko} 은(는) 참/거짓이어야 합니다.")
                if ch[key] != bool(c.get(key, key == "mirror")): o[key] = ch[key]
        if ch.get("points") is not None:
            pts = ch["points"]
            if not isinstance(pts, dict):
                raise ServiceError("기준점 이름은 {옛 이름: 새 이름} 모양이어야 합니다.")
            now = [p.get("name") for p in c.get("points") or [] if isinstance(p, dict)]
            ren = {}
            for old, new in pts.items():
                if old not in now:
                    raise ServiceError(f"{cur} 에 «{str(old)[:30]}» 기준점이 없습니다.")
                nn = _clean_name(new, 30, "기준점 이름")
                if nn != old: ren[old] = nn
            final = [ren.get(x, x) for x in now]
            if len(set(final)) != len(final):
                raise ServiceError(f"{cur} 기준점 이름이 겹칩니다 — 서로 다른 이름을 붙여 주세요.")
            if ren: o["points"] = ren
        if o: out[cur] = o
    final = [(out.get(n) or {}).get("name") or n for n in known]
    if len(set(final)) != len(final):
        raise ServiceError("조각 이름이 겹칩니다 — 서로 다른 이름을 붙여 주세요.")
    if not out:
        raise ServiceError("바뀐 것이 없습니다.")
    return {"pieces": out}


def same_shape(a, b, piece_map=None, point_map=None):
    """이름만 고친 두 view.json(dict)이 «모양은 점 하나까지 같은가» — 0.01mm 정수 배열을 그대로 견준다.
    piece_map {옛 조각: 새 조각} · point_map {새 조각: {옛 기준점: 새 기준점}} → 다른 곳 목록(빈 목록 = 같음)"""
    piece_map = piece_map or {}; point_map = point_map or {}; diffs = []
    if a.get("q") != b.get("q") or a.get("sheet") != b.get("sheet"): diffs.append("q·sheet 다름")
    sizes = (a.get("style") or {}).get("sizes") or []
    if sizes != (b.get("style") or {}).get("sizes"): diffs.append("사이즈 목록 다름")
    for sid in sizes:
        A = {p.get("name"): p for p in ((a.get("sizes") or {}).get(sid) or {}).get("pieces") or []}
        B = {p.get("name"): p for p in ((b.get("sizes") or {}).get(sid) or {}).get("pieces") or []}
        if len(A) != len(B): diffs.append(f"{sid} 조각 수 다름"); continue
        for n, p in A.items():
            nn = piece_map.get(n, n); q = B.get(nn)
            if q is None: diffs.append(f"{sid} {nn} 없음"); continue
            for k in ("seam", "cut", "internal", "notches", "holes", "grain", "fold"):
                if p.get(k) != q.get(k): diffs.append(f"{sid} {nn} {k} 다름")
            pm = point_map.get(nn) or {}
            want = {pm.get(k, k): v for k, v in (p.get("nodes") or {}).items()}
            if want != (q.get("nodes") or {}): diffs.append(f"{sid} {nn} 기준점 자리 다름")
    return diffs


# ════════ 마커 요청 — 명단 → 벌수 · 입력 검사 (표준 라이브러리만 — 서버가 일꾼을 띄우기 전에 부른다) ════════
def norm_size(s):
    """사이즈 글자 정리 — ' 2xl ' → '2XL', 'XXL' → '2XL'. 빈칸이면 ''. (marker.norm_size 와 같은 규칙 — 시험이 견준다)"""
    t = str(s or "").strip().upper().replace(" ", "")
    return _SIZE_ALIAS.get(t, t)


def counts_from_members(members, garment):
    """주문 명단 [{topSize, bottomSize}…] → {사이즈: 벌수} — marker.counts_from_members 와 «같은 규칙» 의 가벼운 사본.
    왜 사본: marker.py 는 불러오는 순간 numpy·shapely 를 읽는다(서버 메모리). 서버는 이 함수로 벌수만 센다.
    피스 규칙(stizshop CLAUDE.md «수량은 피스로 센다»): 상의 = topSize 가 채워진 사람 수 · 하의 = bottomSize 가 채워진 사람 수.
    «세트» 로 묶지 않는다(상의만 입는 사람 · 위아래 사이즈가 다른 사람이 실제로 있다). 모르는 사이즈도 버리지 않고 뒤에 둔다."""
    key = {"top": "topSize", "상의": "topSize", "bottom": "bottomSize", "하의": "bottomSize"}[garment]
    out = {}
    for m in members or []:
        s = norm_size((m or {}).get(key))
        if s:
            out[s] = out.get(s, 0) + 1
    return {s: out[s] for s in sorted(out, key=lambda s: (GRADE_SIZES.index(s) if s in GRADE_SIZES else 99, s))}


def _int_like(v):
    """정수(또는 2.0 같은 정수 실수)면 int, 아니면 None — 참·거짓은 숫자로 보지 않는다"""
    if isinstance(v, bool) or not _num(v):
        return None
    return int(v) if float(v) == int(v) else None


def check_marker_request(group, counts, width_cm=150.0, gap_mm=3.0, nap=False, quick=False, budget=None, cache_mb=None,
                         jobs=None, seed=0, exclude=(), sizes=None, pieces=None, per_bundle=None):
    """마커 요청 검사 → 깨끗한 사본(dict). 틀리면 ServiceError(한국어 — 직원 화면에 그대로 보여도 된다).
    sizes: 고를 수 있는 사이즈(그 버전 사이즈 · 없으면 S~5XL) · pieces: 뺄 수 있는 조각 이름(없으면 검사 안 함)
    group "imported"(들여온 스타일 · F10 6단계): sizes 가 꼭 있어야 하고(13사이즈 등 그 버전 순서 그대로) per_bundle(한 벌 장수)을 넘긴다"""
    if group not in ("top", "bottom", "imported"):
        raise ServiceError(f"모르는 옷 종류: {str(group)[:20]}")
    if group == "imported":
        if not sizes:
            raise ServiceError("들여온 스타일은 사이즈 목록이 있어야 합니다.")
        allowed = [str(s) for s in sizes]
        pb = _int_like(per_bundle)
        if pb is None or not (1 <= pb <= 500):
            raise ServiceError("들여온 스타일의 한 벌 장수를 알 수 없습니다.")
    else:
        allowed = [s for s in GRADE_SIZES if sizes is None or s in sizes]
    if not isinstance(counts, dict) or not counts:
        raise ServiceError("사이즈별 벌수를 하나 이상 넣어 주세요(예: {\"M\": 2}).")
    clean = {}
    for k, v in counts.items():
        s = norm_size(k)
        if s not in allowed:
            raise ServiceError(f"이 스타일에 없는 사이즈: {str(k)[:20]} (있는 사이즈: {'·'.join(allowed)})")
        n = _int_like(v)
        if n is None or n < 0 or n > MARKER_MAX_BUNDLES:
            raise ServiceError(f"{s} 벌수는 0~{MARKER_MAX_BUNDLES} 사이 정수여야 합니다.")
        clean[s] = clean.get(s, 0) + n
    clean = {s: clean[s] for s in allowed if clean.get(s)}       # 표준 순서 · 0벌은 뺀다
    total = sum(clean.values())
    if total < 1:
        raise ServiceError("벌수 합이 0 입니다 — 한 벌 이상 넣어 주세요.")
    if total > MARKER_MAX_BUNDLES:
        raise ServiceError(f"벌수 합이 {total}벌입니다 — 한 번에 {MARKER_MAX_BUNDLES}벌까지 깔 수 있습니다(나눠서 까세요).")
    if not _num(width_cm) or not (MARKER_WIDTH_CM[0] <= float(width_cm) <= MARKER_WIDTH_CM[1]):
        raise ServiceError(f"원단 폭은 {MARKER_WIDTH_CM[0]:.0f}~{MARKER_WIDTH_CM[1]:.0f}cm 사이 숫자여야 합니다.")
    if not _num(gap_mm) or not (MARKER_GAP_MM[0] <= float(gap_mm) <= MARKER_GAP_MM[1]):
        raise ServiceError(f"조각 간격은 {MARKER_GAP_MM[0]:.0f}~{MARKER_GAP_MM[1]:.0f}mm 사이 숫자여야 합니다.")
    budget = MARKER_SERVER["budget"] if budget is None else budget
    if not _num(budget) or not (5.0 <= float(budget) <= MARKER_BUDGET_MAX_S):
        raise ServiceError(f"탐색 시간은 5~{MARKER_BUDGET_MAX_S:.0f}초 사이여야 합니다.")
    cache_mb = MARKER_SERVER["cache_mb"] if cache_mb is None else cache_mb
    if not _num(cache_mb) or not (0.0 <= float(cache_mb) <= 300.0):
        raise ServiceError("FFT 기억 한도는 0~300MB 사이여야 합니다.")
    jobs = MARKER_SERVER["jobs"] if jobs is None else _int_like(jobs)
    if jobs is None or not (1 <= jobs <= 4):
        raise ServiceError("일꾼 수는 1~4 사이 정수여야 합니다.")
    seed = _int_like(seed)
    if seed is None or not (0 <= seed < 2 ** 31):
        raise ServiceError("시드는 0 이상 정수여야 합니다.")
    if exclude is None:
        exclude = []
    if not isinstance(exclude, (list, tuple)) or not all(isinstance(x, str) and x for x in exclude):
        raise ServiceError("뺄 조각은 이름 목록이어야 합니다.")
    exclude = sorted(set(exclude))
    if pieces is not None:
        bad = [x for x in exclude if x not in pieces]
        if bad:
            raise ServiceError(f"이 스타일에 없는 조각: {bad[0][:30]}")
        if len(exclude) >= len(set(pieces)):
            raise ServiceError("조각을 전부 뺄 수는 없습니다.")
    out = {"group": group, "counts": clean, "bundles": total, "width_cm": float(width_cm), "gap_mm": float(gap_mm),
           "nap": bool(nap), "quick": bool(quick), "budget": float(budget), "cache_mb": float(cache_mb), "jobs": jobs,
           "seed": seed, "exclude": exclude}
    if group == "imported":                                    # 일꾼이 다시 검사할 때도 같은 사이즈·장수로(marker_all)
        out["sizes"] = allowed; out["per_bundle"] = pb
    return out


def pieces_per_bundle(group, exclude=()):
    """한 벌의 장수(좌우·여러 장 펼친 수) — gas_warmup_meta 의 SPEC(그레이딩·마커와 같은 표). 뺀 조각은 빼고 센다.
    서버 sys.path 를 건드리지 않으려고 파일에서 바로 읽는다(표준 라이브러리만 — 엔진이 돌지 않는다)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_stiz_gas_warmup_meta", os.path.join(HERE, "gas_warmup_meta.py"))
    meta = importlib.util.module_from_spec(spec); spec.loader.exec_module(meta)
    table = meta.SPEC_T if group == "top" else meta.SPEC_B
    return sum(len(v) for k, v in table.items() if k not in set(exclude or ()))


def estimate_marker(pieces, quick, group="top", width_cm=150.0, gap_mm=3.0):
    """일꾼 하나의 «최고 메모리(MB)·걸리는 시간(초, 이 PC — 한 번 깔기 + 파일)» 어림 — 조각 수(벌수 × 장수)·원단 폭·간격으로.
    근거: MARKER_FIT(실측 맞춤 — 실측보다 늘 크게, 시험 MarkerEstimate 가 지킨다).
    여러 번 깔기는 시간이 한도(budget)로 잘리므로 시간은 «한 번 깔기» 만 어림하고, 메모리는 탐색 몫을 더한다."""
    F = MARKER_FIT
    f = F[group if group in ("top", "bottom") else "bottom"]
    w, g = float(width_cm), float(gap_mm)
    rss = f["rss0"] + f["rss_per_piece"] * pieces + F["rss_per_cm"] * max(0.0, w - 150.0) + (0.0 if quick else F["search_mb"])
    rss *= _mem_factor()                                            # 리눅스 배수 — 윈도우 맞춤 어림이 Render 실측보다 작았다(×1.27)
    mult = max(1.0, (w / 150.0) ** F["w_pow"]) * (1.0 + F["gap_per_mm"] * max(0.0, g - 3.0))
    secs = (f["t0"] + f["t_lin"] * pieces + f["t_k"] * (pieces ** f["t_pow"])) * mult
    return {"rss_mb": round(rss, 1), "quick_s": round(secs, 1)}


def admit_marker(req, time_limit_s=180.0, box_mb=MARKER_BOX_MB, server_mb=MARKER_SERVER_MB, slow=MARKER_SLOW):
    """서버 입장 판정 — 어림이 상자(512MB)·시간 한도를 넘으면: 여러 번 깔기는 «빠르게» 로 바꾸고(forced_quick),
    빠르게도 넘으면 ServiceError(«한 번에 N벌까지»). 반환: req 사본 + estimate·forced_quick·budget(남은 시간에 맞춤)."""
    per = req.get("per_bundle") if req.get("group") == "imported" else None   # 들여온 스타일 — 장수는 명세(meta.qty)에서 센 값
    pcs = req["bundles"] * (per or pieces_per_bundle(req["group"], req["exclude"]))
    cap_mb = box_mb - server_mb - MARKER_MARGIN_MB
    cap_s = float(time_limit_s)

    def fits(quick):
        e = estimate_marker(pcs, quick, req["group"], req["width_cm"], req["gap_mm"])
        need_s = slow * (MARKER_GRADE_S + e["quick_s"])             # 그레이딩 + 한 번 깔기 + 파일(어림에 포함) — 느린 서버 배수
        return e, e["rss_mb"] <= cap_mb and need_s <= cap_s, need_s
    out = dict(req)
    e, ok, need_s = fits(req["quick"])
    # «빠르게로 바꾸기» — 기본값(메모리 몫 30MB · 시간은 두 길 모두 «한 번 깔기» 로 어림)에서는 여기 닿지 않는다:
    #   여러 번 깔기가 넘치면 빠르게도 시간에서 먼저 넘친다. 운영값(MARKER_FIT·서버 몫)이 바뀌어 메모리만 넘칠 때를 위한 길로 남겨 둔다
    if not ok and not req["quick"]:
        e, ok, need_s = fits(True)
        if ok:
            out["quick"] = True; out["forced_quick"] = True           # 탐색 몫까지는 안 들어간다 — 빠르게로
    if not ok:
        n = req["bundles"]
        per = pcs // req["bundles"]
        est = lambda k: estimate_marker(k * per, True, req["group"], req["width_cm"], req["gap_mm"])
        while n > 1 and not (est(n)["rss_mb"] <= cap_mb and slow * (MARKER_GRADE_S + est(n)["quick_s"]) <= cap_s):
            n -= 1
        raise ServiceError(f"한 번에 깔기엔 너무 많습니다({req['bundles']}벌 · {pcs}장 — 서버 메모리·시간 한도). "
                           f"{n}벌 이하로 나눠 까 주세요.")
    # 여러 번 깔기 시간 한도 = 전체 한도 − (그레이딩 + 파일 몫). 빠르게는 쓰지 않는다
    files_s = slow * (e["quick_s"] * MARKER_FIT["files_share"])
    out["budget"] = float(max(5.0, min(req["budget"], cap_s - slow * MARKER_GRADE_S - files_s - 10.0)))
    out["estimate"] = {"pieces": pcs, "rss_mb": e["rss_mb"], "need_s": round(need_s, 1), "files_s": round(files_s + 5.0, 1),
                       "cap_mb": cap_mb, "cap_s": cap_s, "slow": slow}
    return out


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


def _step(i, name, emit, total=None):
    # total: 단계 수(기본 = 다시 만들기 5단계). 마커는 MARKER_STEPS 4단계라 따로 준다
    if emit: print(f"{STEP_MARK} {i}/{total or len(STEPS)} {name}", flush=True)


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


def graded_all(work, group, rules=None, check_view=None, sources=None, font=None, emit=False):
    """F10 4단계 ①②③ — 원본 .ai → 2XL 수정 → 그레이딩(graded.json, 사이즈별 DXF·PDF 는 안 만든다). 일꾼 프로세스 안에서 부른다.
       rules:      그 버전의 규칙표(다시 그레이딩한 버전 — rules.json) · None 이면 표준 규칙(처음 만든 판과 같다)
       check_view: 그 버전의 view.json 주소 — 주면 이 그레이딩으로 화면 자료를 다시 만들어 «점 하나씩» 견준다(③).
                   어긋나면 마커가 그 버전이 아닌 다른 모양으로 깔리니, 부모가 그 차(view_match)를 보고 멈춘다.
       돌려주는 것: {"graded": graded.json 주소, "view_match": {max_mm, points, diffs} | None, …}"""
    if group not in ("top", "bottom"):
        raise ServiceError(f"모르는 옷 종류: {group}")
    table = check_rules(group, rules, full=True) if rules else None
    src = _check_sources(sources)
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    gw = os.path.join(work, "gas-warmup"); d2, dg, ds = (os.path.join(gw, x) for x in ("2xl", "graded", "spec"))
    if HERE not in sys.path: sys.path.insert(0, HERE)
    fnt = font or resolve_font()
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    extra = []
    if table:
        rpath = os.path.join(work, "rules_in.json")
        with open(rpath, "w", encoding="utf-8") as f:
            json.dump({group: table}, f, ensure_ascii=False)
        extra = ["--rules", rpath]
    n = len(MARKER_STEPS)
    timings, t0 = {}, time.time()
    view_match = None
    with font_shim(fnt["path"]):
        _step(1, "build", emit, n); t = time.time()
        _run_script("gas_warmup_build.py", [src["top"], src["bottom"], d2]); timings["build"] = round(time.time() - t, 1)
        _step(2, "grade", emit, n); t = time.time()
        _run_script("gas_warmup_grade.py", ["--pieces", os.path.join(d2, "pieces_after.json"), "--std-top", src["std_top"],
                                            "--std-pants", src["std_pants"], "--src-top", src["top"], "--src-bottom", src["bottom"],
                                            "--out", dg, "--no-export"] + extra)
        timings["grade"] = round(time.time() - t, 1)
        if check_view:
            _step(3, "check", emit, n); t = time.time()
            with open(check_view, encoding="utf-8") as f:
                want = json.load(f)
            import gas_warmup_spec, cad_view
            gas_warmup_spec.main(["--pieces", os.path.join(d2, "pieces_after.json"), "--graded", os.path.join(dg, "graded.json"),
                                  "--out", ds])
            sid = cad_view.GROUPS[group]["style_id"]
            vpath, _z, _rep, _files = cad_view.build_style(gw, None, group, os.path.join(work, "cad", sid), when)
            with open(vpath, encoding="utf-8") as f:
                got = json.load(f)
            view_match = compare_cuts(want, got)            # 마커가 쓰는 것은 재단선뿐 — 노치·안쪽선이 바뀐 옛 판도 재단선이 같으면 통과
            timings["check"] = round(time.time() - t, 1)
    graded = os.path.join(dg, "graded.json")
    if not os.path.isfile(graded):
        raise ServiceError("그레이딩 결과(graded.json)를 만들지 못했습니다.")
    timings["total"] = round(time.time() - t0, 1)
    return {"ok": True, "mode": "graded", "work": work, "group": group, "graded": graded, "graded_sha256": _file_sha(graded),
            "rules_used": bool(table), "view_match": view_match, "font": fnt, "engine": engine_version(),
            "timings_s": timings, "peak_rss_mb": peak_rss_mb(), "made_at": when}


# ── 들여오기·다시 묶기·명세 꺼내기 — 일꾼 프로세스 안에서만 돈다(style_import · piecespec 이 shapely 를 읽는다) ──
def _watchdog(max_seconds, what):
    """일꾼 안 시계 — max_seconds 가 지나면 한국어 사유를 남기고 일꾼 스스로 끝낸다(부모 시계보다 먼저 · 깨끗한 사유)"""
    if not max_seconds: return None
    def boom():
        print(f"[service] 실패: {what} 시간이 {round(max_seconds)}초를 넘어 멈췄습니다 — 원본이 너무 크거나 이상합니다.", flush=True)
        os._exit(3)
    t = threading.Timer(float(max_seconds), boom); t.daemon = True; t.start()
    return t


def _bundle_entry(res, sid):
    """style_import 결과 → 그레이더가 받는 styles 칸 {view, zip, …} (다시 만들기 결과와 같은 꼴)
    view.json 의 엔진 판 표시는 창구가 채운다(_view_step 과 같이 — 복사본에는 git 이 없어 cad_view.git_head 가 그레이더 판을 적는다)"""
    P = res["paths"]; chk = res["check"]
    ev = engine_version()
    with open(P["view"], encoding="utf-8") as f: view = json.load(f)
    view["source"].update(commit=ev.get("commit"), engine_source=ev.get("source"), built_by="service.py")
    with open(P["view"], "w", encoding="utf-8") as f: json.dump(view, f, ensure_ascii=False, separators=(",", ":"))
    return {"group": "imported", "view": P["view"], "zip": P["zip"], "view_bytes": os.path.getsize(P["view"]),
            "zip_bytes": os.path.getsize(P["zip"]), "checks_bad": [], "check_ok": bool(chk["ok"]), "check_max": chk["max"],
            "check_bad": list(chk.get("bad") or [])[:30], "confirm_open": sum(1 for c in (res.get("confirm_doc") or {}).get("pieces") or []
                                                                             if not c.get("confirmed"))}


def import_all(work, src, base, style_id, name=None, source_name=None, emit=False, max_seconds=IMPORT_MAX_SECONDS):
    """F10 6단계 — OptiCad .ai → 들여온 스타일 묶음(work/out). 일꾼 프로세스 안에서 부른다.
    돌려주는 것: {"styles": {style_id: {view, zip, check_ok, …}}, "summary", "confirm_doc" 요약, 메모리·시간}"""
    if not IMPORT_STYLE_ID_RE.fullmatch(style_id or ""):
        raise ServiceError("스타일 번호는 영문 소문자·숫자·- 만 쓸 수 있습니다(3~64자).")
    if not os.path.isfile(src):
        raise ServiceError("원본 .ai 가 없습니다.")
    with open(src, "rb") as f:
        kind = ai_header_kind(f.read(1024))
    if kind != "ps":
        raise ServiceError("OptiCad «Adobe Export»(PostScript) .ai 만 들여올 수 있습니다." + (" PDF 형식 .ai 는 아직 못 읽습니다." if kind == "pdf" else ""))
    if HERE not in sys.path: sys.path.insert(0, HERE)
    dog = _watchdog(max_seconds, "원본 읽기·규칙 읽기")
    import style_import as SI
    n = len(IMPORT_STEPS); idx = {k: i + 1 for i, k in enumerate(IMPORT_STEPS)}
    timings, t0, last = {}, time.time(), {"k": None, "t": time.time()}

    def prog(k):
        if last["k"]: timings[last["k"]] = round(time.time() - last["t"], 1)
        last.update(k=k, t=time.time()); _step(idx.get(k, 1), k, emit, n)
    out = os.path.join(os.path.abspath(work), "out")
    try:
        res = SI.import_style(src, base, style_id, out, name=name, source_name=source_name, progress=prog)
    except SI.StyleImportError as e:
        raise ServiceError(f"들여오지 못했습니다: {e}")
    finally:
        if dog: dog.cancel()
    if last["k"]: timings[last["k"]] = round(time.time() - last["t"], 1)
    timings["total"] = round(time.time() - t0, 1)
    ent = _bundle_entry(res, style_id)
    return {"ok": True, "mode": "import", "work": os.path.abspath(work), "styles": {style_id: ent}, "summary": res["summary"],
            "base_size": base, "sizes": res["style"]["sizes"], "pieces": res["style"]["pieces"], "name": res["style"]["name"],
            "engine": engine_version(), "font": None, "timings_s": timings, "peak_rss_mb": peak_rss_mb(),
            "made_at": res["style"]["made_at"]}


def restyle_all(work, zip_path, rule_changes=None, names=None, by=None, check_view=None, emit=False):
    """들여온 스타일 다시 묶기(이름 고치기 · 규칙 바꿔 다시 그레이딩) — 일꾼 안에서. 결과 칸에 재생성 검산(mesh)을 싣는다.
    names 만 바꿨고 check_view(그 버전 view.json)를 주면 «모양이 점 하나까지 같은가» 를 견주고 다르면 멈춘다"""
    if not os.path.isfile(zip_path or ""):
        raise ServiceError("그 버전의 묶음(exports.zip)이 없습니다.")
    if not rule_changes and not names:
        raise ServiceError("바꿀 것이 없습니다.")
    if HERE not in sys.path: sys.path.insert(0, HERE)
    import style_import as SI
    n = len(RESTYLE_STEPS); idx = {k: i + 1 for i, k in enumerate(RESTYLE_STEPS)}
    t0 = time.time()
    out = os.path.join(os.path.abspath(work), "out")
    try:
        res = SI.restyle(zip_path, out, rule_changes=rule_changes, names=names, by=by, progress=lambda k: _step(idx.get(k, 1), k, emit, n))
    except SI.StyleImportError as e:
        raise ServiceError(f"다시 묶지 못했습니다: {e}")
    sid = res["style"]["id"]
    ent = _bundle_entry(res, sid)
    ent["mesh"] = res["mesh"]; ent["rule_changes"] = res["rule_changes"]; ent["name_changes"] = res["name_changes"]
    if names and not rule_changes and check_view:              # 이름만 — 모양 같음을 0.01mm 정수까지 견준다
        with open(check_view, encoding="utf-8") as f: old = json.load(f)
        with open(ent["view"], encoding="utf-8") as f: new = json.load(f)
        pmap = {c["from"]: c["to"] for c in res["name_changes"] if c["field"] == "name"}
        ptmap = {}
        for c in res["name_changes"]:
            if c["field"] == "point": ptmap.setdefault(c["piece"], {})[c["from"]] = c["to"]
        ent["shape_diffs"] = same_shape(old, new, pmap, ptmap)
        if ent["shape_diffs"]:
            raise ServiceError(f"이름만 바꿨는데 모양이 달라졌습니다({ent['shape_diffs'][0]}) — 저장하지 않습니다.")
    return {"ok": True, "mode": "restyle", "work": os.path.abspath(work), "styles": {sid: ent}, "summary": res["summary"],
            "engine": engine_version(), "font": None, "timings_s": {"total": round(time.time() - t0, 1)}, "peak_rss_mb": peak_rss_mb(),
            "made_at": res["style"]["made_at"]}


def specs_graded(work, zip_path, files, emit=False):
    """들여온 스타일 마커 ① — 그 버전 묶음의 사이즈별 명세(specs/spec_<사이즈>.json)를 꺼내 지문을 맞추고
    marker.py 가 받는 graded.json({사이즈: {"imported": {조각: 옛 형식(재단선)}}}) + 펼침표(expand.json)를 만든다. 일꾼 안에서.
    files = {ZIP 안 경로: sha256} (그 버전 meta 의 files 중 kind=spec) — 하나라도 다르면 멈춘다(버전 모양과 다른 것으로 깔지 않게)"""
    import zipfile
    if not isinstance(files, dict) or not files:
        raise ServiceError("그 버전에 사이즈별 명세가 없습니다.")
    if HERE not in sys.path: sys.path.insert(0, HERE)
    _step(1, "specs", emit, len(IMARKER_STEPS))
    from piecespec import to_legacy
    import style_import as SI
    t0 = time.time(); graded, table = {}, None
    with zipfile.ZipFile(zip_path) as z:
        for path, sha in files.items():
            m = re.fullmatch(r"specs/spec_([A-Za-z0-9]+)\.json", str(path))
            if not m:
                raise ServiceError(f"명세 경로가 이상합니다: {str(path)[:60]}")
            b = z.read(path)
            if hashlib.sha256(b).hexdigest() != sha:
                raise ServiceError(f"{m.group(1)} 명세 지문이 그 버전과 다릅니다(손상) — 마커를 만들지 않았습니다.")
            doc = json.loads(b.decode("utf-8")); pcs = doc["pieces"]
            graded[m.group(1)] = {"imported": {n: {"cut": to_legacy(sp)["cut"], "sew": [], "draw": [], "notch": [], "fold": None}
                                               for n, sp in pcs.items()}}
            if table is None: table = SI.expand_table(pcs)
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    gp, ep = os.path.join(work, "graded_imported.json"), os.path.join(work, "expand.json")
    with open(gp, "w", encoding="utf-8") as f: json.dump(graded, f, ensure_ascii=False, separators=(",", ":"))
    with open(ep, "w", encoding="utf-8") as f: json.dump(table, f, ensure_ascii=False)
    return {"ok": True, "mode": "specs", "graded": gp, "expand": ep, "sizes": list(graded), "graded_sha256": _file_sha(gp),
            "per_bundle": sum(len(v) for v in table.values()), "timings_s": {"specs": round(time.time() - t0, 1)},
            "peak_rss_mb": peak_rss_mb()}


def _file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def marker_argv(graded, out_dir, req, name="marker", spec_file=None, title=None):
    """검사한 요청 → marker.py 명령줄 인자. 서버 길과 명령줄 길이 «같은 인자» 를 쓰게 한 곳에서 만든다(시험이 이것으로 명령줄을 돌린다).
    spec_file·title: 들여온 스타일(group "imported") — 장수·좌우 펼침표 파일 · 그림 제목"""
    argv = ["--garment", req["group"], "--graded", graded, "--out", out_dir, "--name", name,
            "--width", f"{req['width_cm']:g}", "--gap", f"{req['gap_mm']:g}", "--seed", str(req["seed"]),
            "--jobs", str(req["jobs"]), "--budget", f"{req['budget']:g}", "--cache-mb", f"{req['cache_mb']:g}",
            "--counts", *[f"{s}={k}" for s, k in req["counts"].items()]]
    if req["nap"]: argv.append("--nap")
    if req["quick"]: argv.append("--quick")
    if req["exclude"]: argv += ["--exclude", *req["exclude"]]
    if spec_file: argv += ["--spec-file", spec_file]
    if title: argv.append("--title=" + str(title)[:80])
    return argv


def marker_all(work, graded, req, font=None, emit=False, spec_file=None, title=None):
    """F10 4단계 ④ — graded.json + 요청 → 마커(배치) + 1:1 PDF · DXF(R2000 mm) · 미리보기 PNG · 요약 JSON. 일꾼 안에서 부른다.
    배치는 marker.main(명령줄과 같은 함수)에 «같은 인자» 를 넘겨 돌린다 — 서버 결과가 명령줄 결과와 갈라질 길을 없앤다.
    창구가 하는 일은 ① 글꼴 주소 바꿔 끼우기(리눅스엔 맑은 고딕이 없다 — PDF·PNG 둘 다) ② 결과 파일 이름을 영문으로
    ③ 다시 재서 검산(겹침·간격·폭 밖·식서 0°/180°)을 결과에 붙이기."""
    req = check_marker_request(**{k: req.get(k) for k in ("group", "counts", "width_cm", "gap_mm", "nap", "quick", "budget",
                                                           "cache_mb", "jobs", "seed", "exclude", "sizes", "per_bundle")})
    if req["group"] == "imported" and not (spec_file and os.path.isfile(spec_file)):
        raise ServiceError("들여온 스타일 마커에 펼침표(장수·좌우)가 없습니다.")
    if not graded or not os.path.isfile(graded):
        raise ServiceError(f"그레이딩 결과(graded.json)가 없습니다: {graded}")
    work = os.path.abspath(work); out = os.path.join(work, "marker"); os.makedirs(out, exist_ok=True)
    if HERE not in sys.path: sys.path.insert(0, HERE)
    fnt = font or resolve_font()
    when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    nst = len(IMARKER_STEPS) if spec_file else len(MARKER_STEPS)
    _step(nst, "marker", emit, nst)
    t0 = time.time()
    import marker as MK
    MK.FONT = fnt["path"]                                  # PNG(PIL)은 글꼴 파일을 직접 연다 — font_shim 이 못 막는 자리라 주소를 바꾼다
    try:
        with font_shim(fnt["path"]):
            S = MK.main(marker_argv(graded, out, req, spec_file=spec_file, title=title))
    except ValueError as e:                                # 조각이 원단보다 넓다 등 — 직원이 고칠 수 있는 입력 문제
        raise ServiceError(f"원단에 깔지 못했습니다: {e}")
    except KeyError as e:
        raise ServiceError(f"그레이딩 결과에 없는 사이즈입니다: {e}")
    except SystemExit as e:                                # marker.main 이 graded.json 을 못 찾으면 sys.exit(글)
        raise ServiceError(str(e.code) if not isinstance(e.code, int) else "마커 계산이 멈췄습니다.")
    secs = round(time.time() - t0, 1)
    png_ko = os.path.join(out, "marker_미리보기.png")       # marker.py 가 붙이는 한글 이름 → 영문으로
    if os.path.isfile(png_ko):
        os.replace(png_ko, os.path.join(out, MARKER_FILES["png"]))
    files = {}
    for kind, nm in MARKER_FILES.items():
        p = os.path.join(out, nm)
        if os.path.isfile(p):
            files[kind] = {"path": p, "bytes": os.path.getsize(p), "sha256": _file_sha(p)}
    allowed = {0} if req["nap"] else {0, 180}
    pl = S.get("placements") or []
    chk = S.get("check") or {}
    verify = {"overlaps": len(chk.get("overlaps") or []), "outside": len(chk.get("outside") or []),
              "min_gap_mm": chk.get("min_gap_mm"), "gap_ok": chk.get("min_gap_mm") is None or chk["min_gap_mm"] >= req["gap_mm"] - 0.01,
              "rotations": sorted({q.get("rot") for q in pl}), "grain_ok": all(q.get("rot") in allowed for q in pl),
              "flipped": sum(1 for q in pl if q.get("flip"))}
    verify["ok"] = verify["overlaps"] == 0 and verify["outside"] == 0 and verify["gap_ok"] and verify["grain_ok"]
    summary = {k: v for k, v in S.items() if k != "placements"}
    return {"ok": True, "mode": "marker", "work": work, "group": req["group"], "request": req, "graded": graded,
            "graded_sha256": _file_sha(graded), "summary": summary, "verify": verify, "files": files, "font": fnt,
            "engine": engine_version(), "timings_s": {"marker": secs}, "peak_rss_mb": peak_rss_mb(), "made_at": when}


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


def intake_all(work, intake_path, style_id=None, sizes=None, emit=False):
    """패턴 의뢰 → 패턴 자동 제작 + 그레이딩(2026-10-22). 일꾼 프로세스 안에서 부른다 — 글꼴은 font_shim 으로 맞춘다.
    돌려주는 것은 들여오기와 같은 꼴 {"styles": {style_id: {view, zip, …}}, …} — 그레이더가 같은 저장 길(_store_from_engine)을 탄다"""
    if HERE not in sys.path: sys.path.insert(0, HERE)
    import intake_build as IB
    try:
        with open(intake_path, encoding="utf-8") as f: row = json.load(f)
    except (OSError, ValueError):
        raise ServiceError("의뢰 자료를 읽지 못했습니다.")
    n = len(INTAKE_STEPS); idx = {k: i + 1 for i, k in enumerate(INTAKE_STEPS)}
    step = lambda k: _step(idx.get("intake_" + k, 1), "intake_" + k, emit, n)
    t0 = time.time()
    out = os.path.join(os.path.abspath(work), "out")
    fnt = resolve_font()
    try:
        with font_shim(fnt["path"]):
            res = IB.build(row, out, sizes, style_id, progress=step)
    except IB.IntakeBuildError as e:
        raise ServiceError(str(e))
    P = res["paths"]; ev = engine_version()
    with open(P["view"], encoding="utf-8") as f: view = json.load(f)
    view["source"].update(commit=ev.get("commit"), engine_source=ev.get("source"), built_by="service.py")
    with open(P["view"], "w", encoding="utf-8") as f: json.dump(view, f, ensure_ascii=False, separators=(",", ":"))
    sid = res["style_id"]
    ent = {"group": "intake", "view": P["view"], "zip": P["zip"], "view_bytes": os.path.getsize(P["view"]),
           "zip_bytes": os.path.getsize(P["zip"]), "checks_bad": [], "check_ok": True, "confirm": P["confirm"]}
    return {"ok": True, "mode": "intake", "work": os.path.abspath(work), "styles": {sid: ent}, "summary": res["summary"],
            "sizes": res["sizes"], "pieces": res["pieces"], "name": res["name"], "engine": ev, "font": fnt,
            "timings_s": {"total": round(time.time() - t0, 1)}, "peak_rss_mb": peak_rss_mb()}


def build_intake(work, intake_path, style_id=None, sizes=None, timeout=600, python=None, on_step=None, env=None):
    """서버가 부르는 함수 — 패턴 의뢰 → 패턴(따로 띄운 일꾼). 반환: intake_all 의 결과 + wall_s"""
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    res_path = os.path.join(work, "result.json")
    cmd = [python or sys.executable, os.path.abspath(__file__), "intake", "--work", work, "--intake", os.path.abspath(intake_path),
           "--result", res_path, "--emit-steps"]
    if style_id: cmd += ["--style-id", style_id]
    if sizes: cmd += ["--sizes", *sizes]
    try:
        return _spawn(cmd, work, res_path, timeout, on_step, env)
    except ServiceError as e:
        raise ServiceError(_worker_reason(os.path.join(work, "engine.log")) or str(e))


def import_style(work, src, base, style_id, name=None, source_name=None, timeout=900, max_seconds=IMPORT_MAX_SECONDS, python=None,
                 on_step=None, env=None):
    """서버가 부르는 함수(F10 6단계) — 원본 .ai 를 «따로 띄운 일꾼» 에서 들여온다. 머리·스타일 번호는 부모에서 먼저 본다.
    max_seconds: 일꾼 안 시계(원본 읽기·규칙 읽기 상한) · timeout: 부모 시계(일꾼을 죽이는 마지막 방어)"""
    if not IMPORT_STYLE_ID_RE.fullmatch(style_id or ""):
        raise ServiceError("스타일 번호는 영문 소문자·숫자·- 만 쓸 수 있습니다(3~64자).")
    if not isinstance(base, str) or not IMPORT_SIZE_RE.match(base):
        raise ServiceError("기준 사이즈 이름이 이상합니다.")
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    res_path = os.path.join(work, "result.json")
    cmd = [python or sys.executable, os.path.abspath(__file__), "import", "--work", work, "--src", os.path.abspath(src), "--base", base,
           "--style-id", style_id, "--result", res_path, "--emit-steps", "--max-seconds", f"{float(max_seconds):g}"]
    if name: cmd.append("--name=" + str(name)[:80])                # «=» 로 붙여 «-» 로 시작하는 이름이 옵션으로 읽히지 않게
    if source_name: cmd.append("--source-name=" + str(source_name)[:120])
    try:
        return _spawn(cmd, work, res_path, max(float(timeout), float(max_seconds) + 30.0), on_step, env)
    except ServiceError as e:
        raise ServiceError(_worker_reason(os.path.join(work, "engine.log")) or str(e))


def restyle(work, zip_path, rule_changes=None, names=None, by=None, check_view=None, timeout=600, python=None, on_step=None, env=None):
    """서버가 부르는 함수 — 들여온 스타일의 이름 고치기·규칙 바꿔 다시 그레이딩(새 묶음). 같은 «따로 띄운 일꾼» 길"""
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    res_path = os.path.join(work, "result.json")
    cmd = [python or sys.executable, os.path.abspath(__file__), "restyle", "--work", work, "--zip", os.path.abspath(zip_path),
           "--result", res_path, "--emit-steps"]
    for flag, obj, fn in (("--changes-file", rule_changes, "changes_req.json"), ("--names-file", names, "names_req.json")):
        if obj:
            p = os.path.join(work, fn)
            with open(p, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False)
            cmd += [flag, p]
    if by: cmd.append("--by=" + str(by)[:120])
    if check_view: cmd += ["--check-view", os.path.abspath(check_view)]
    try:
        return _spawn(cmd, work, res_path, timeout, on_step, env)
    except ServiceError as e:
        raise ServiceError(_worker_reason(os.path.join(work, "engine.log")) or str(e))


def _worker_reason(log_path):
    """일꾼 출력에서 창구가 남긴 «[service] 실패: …» 사유(한국어) — 없으면 None"""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f if l.startswith("[service] 실패:")]
        return lines[-1].split(":", 1)[1].strip() if lines else None
    except OSError:
        return None


def _marker_failure(e, log_path):
    """마커 일꾼 실패 → 직원에게 보일 한국어 한 줄. 창구가 남긴 사유가 먼저, 없으면 메모리 부족·강제 종료를 알아본다"""
    why = _worker_reason(log_path)
    if why:
        return why
    t = str(e)
    if "MemoryError" in t or "Unable to allocate" in t or "bad_alloc" in t:
        return "메모리가 모자라 마커를 멈췄습니다 — 벌수를 줄이거나 나눠 까 주세요."
    m = re.search(r"종료 코드 (-?\d+)", t)
    if m and int(m.group(1)) < 0:
        return f"마커 일꾼이 강제로 멈췄습니다(신호 {-int(m.group(1))} — 메모리 부족일 수 있음). 벌수를 줄여 다시 눌러 주세요."
    return t.split("\n", 1)[0]


def marker(work, group, counts, width_cm=150.0, gap_mm=3.0, nap=False, quick=False, budget=None, cache_mb=None, jobs=None, seed=0,
           exclude=(), graded=None, rules=None, check_view=None, sizes=None, pieces=None, sources=None, timeout=1800,
           python=None, on_step=None, env=None, view_tol_mm=MARKER_VIEW_TOL_MM, cancel=None, files_reserve_s=20.0,
           spec_zip=None, spec_files=None, title=None, per_bundle=None):
    """서버가 부르는 함수(F10 4단계) — 마커·요척. 요청은 부모에서 먼저 검사한다(틀린 요청으로 일꾼을 띄우지 않게).
    일꾼을 «두 번» 띄운다: ① graded(원본 → 그레이딩, check_view 를 주면 그 버전 모양과 견줌) ② marker(배치 + 파일).
      왜 두 번: 그레이딩(약 200MB)과 배치(약 340MB)의 메모리가 한 프로세스에 겹쳐 쌓이지 않게 — 끝나면 운영체제로 통째로 돌아간다.
    graded 를 주면 ①을 건너뛴다(이미 있는 graded.json). 반환: marker_all 의 결과 + graded_run(① 기록) + wall_s.
    on_step(i, total, name) — MARKER_STEPS 기준(1 build · 2 grade · 3 check · 4 marker).
    timeout: «전체»(두 일꾼 합) 벽시계 상한 — 넘으면 일꾼을 죽이고 ServiceError. 여러 번 깔기 한도(budget)는 그레이딩이 쓴 시간을 빼고
             파일 몫(files_reserve_s)을 남긴 만큼으로 줄여 넘긴다(넘길 것 같으면 그때까지의 최선을 낸다).
    cancel: threading.Event — 세우면 돌고 있는 일꾼을 죽이고 ServiceError("취소했습니다.")
    들여온 스타일(group "imported", F10 6단계): spec_zip(그 버전 exports.zip) + spec_files({specs/spec_<사이즈>.json: 지문}) —
      ① 일꾼이 명세를 꺼내 지문을 맞추고 graded·펼침표를 만든다(원본에서 다시 그레이딩하지 않는다 — 명세 묶음이 정본) ② 배치는 같은 길.
      입장 판정은 같은 어림(벌수 × per_bundle 장수)."""
    req = check_marker_request(group, counts, width_cm, gap_mm, nap, quick, budget, cache_mb, jobs, seed, exclude, sizes, pieces,
                               per_bundle=per_bundle)
    work = os.path.abspath(work); os.makedirs(work, exist_ok=True)
    py = python or sys.executable
    t0 = time.time()
    prep = None; spec_file = None
    if group == "imported":
        if not spec_zip or not os.path.isfile(spec_zip):
            raise ServiceError("들여온 스타일의 묶음(exports.zip)이 없습니다.")
        r1 = os.path.join(work, "result_specs.json"); ff = os.path.join(work, "spec_files.json")
        with open(ff, "w", encoding="utf-8") as f: json.dump(spec_files or {}, f, ensure_ascii=False)
        cmd = [py, os.path.abspath(__file__), "specs", "--work", work, "--zip", os.path.abspath(spec_zip), "--files-file", ff,
               "--result", r1, "--emit-steps"]
        try:
            prep = _spawn(cmd, work, r1, min(timeout, 300), on_step, env, log_name="engine_graded.log", cancel=cancel)
        except ServiceError as e:
            raise ServiceError(_marker_failure(e, os.path.join(work, "engine_graded.log")))
        missing = [s for s in req["counts"] if s not in (prep.get("sizes") or [])]
        if missing:
            raise ServiceError(f"그 버전 명세에 없는 사이즈입니다: {missing[0]}")
        graded, spec_file = prep["graded"], prep["expand"]
        prep["view_match"] = {"max_mm": 0.0, "pieces": len(prep.get("sizes") or []), "diffs": [], "by": "spec_sha256"}
    if graded is None:
        r1 = os.path.join(work, "result_graded.json")
        cmd = [py, os.path.abspath(__file__), "graded", "--work", work, "--group", group, "--result", r1, "--emit-steps"]
        if rules:
            rfile = os.path.join(work, "rules_req.json")
            with open(rfile, "w", encoding="utf-8") as f:
                json.dump(check_rules(group, rules, full=True), f, ensure_ascii=False)
            cmd += ["--rules-file", rfile]
        if check_view:
            cmd += ["--check-view", os.path.abspath(check_view)]
        for k in SOURCE_KEYS:
            if sources and sources.get(k): cmd += [f"--{k.replace('_', '-')}", sources[k]]
        try:
            prep = _spawn(cmd, work, r1, min(timeout, 900), on_step, env, log_name="engine_graded.log", cancel=cancel)
        except ServiceError as e:
            raise ServiceError(_marker_failure(e, os.path.join(work, "engine_graded.log")))
        vm = prep.get("view_match")
        if check_view and (vm is None or vm.get("diffs") or (vm.get("max_mm") or 0) > view_tol_mm):
            why = (vm or {}).get("diffs") or [f"점 차 최대 {(vm or {}).get('max_mm')}mm"]
            raise ServiceError(f"서버에서 다시 만든 모양이 이 버전과 달라 마커를 만들지 않았습니다({why[0]}).")
        graded = prep["graded"]
    left = timeout - (time.time() - t0)
    if left < 5.0:
        raise ServiceError(f"그레이딩에 시간을 다 써서({round(time.time() - t0)}초) 마커를 깔지 못했습니다. 잠시 후 다시 눌러 주세요.")
    req["budget"] = float(max(5.0, min(req["budget"], left - files_reserve_s)))   # 벽시계 전체를 지키게 — 파일 몫을 남긴다
    rq = os.path.join(work, "marker_req.json")
    with open(rq, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False)
    r2 = os.path.join(work, "result.json")
    cmd = [py, os.path.abspath(__file__), "marker", "--work", work, "--graded", os.path.abspath(graded), "--request-file", rq,
           "--result", r2, "--emit-steps"]
    if spec_file: cmd += ["--spec-file", os.path.abspath(spec_file)]
    if title: cmd.append("--title=" + str(title)[:80])
    try:
        out = _spawn(cmd, work, r2, max(5.0, timeout - (time.time() - t0)), on_step, env, cancel=cancel)
    except ServiceError as e:
        raise ServiceError(_marker_failure(e, os.path.join(work, "engine.log")))
    if prep:
        out["graded_run"] = {k: prep.get(k) for k in ("graded_sha256", "rules_used", "view_match", "timings_s", "peak_rss_mb",
                                                       "vm_peak_mb", "vm_hwm_mb", "guard", "wall_s")}
    peaks = [x for x in (out.get("peak_rss_mb"), (prep or {}).get("peak_rss_mb")) if isinstance(x, (int, float))]
    out["peak_rss_mb_max"] = max(peaks) if peaks else None    # 두 일꾼 중 큰 쪽(동시에 돌지 않는다)
    out["wall_s"] = round(time.time() - t0, 1)
    return out


def _spawn(cmd, work, res_path, timeout, on_step, env, log_name="engine.log", cancel=None):
    """일꾼 프로세스를 띄워 출력은 engine.log 에, 단계 줄(@@STEP)은 on_step 으로 — 끝나면 result.json 을 읽어 돌려준다.
    cancel(threading.Event, 선택): 세워지면 일꾼을 죽이고 ServiceError("취소했습니다.")"""
    log_path = os.path.join(work, log_name)
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
    cancelled = {"v": False}
    if cancel is not None:                                    # 취소 지켜보기 — 일꾼이 끝나면 스스로 멈춘다
        def _watch():
            while p.poll() is None:
                if cancel.wait(0.3):
                    cancelled["v"] = True
                    _kill()
                    return
        threading.Thread(target=_watch, daemon=True).start()
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
    if cancelled["v"]:
        raise ServiceError("취소했습니다.")
    if killed["v"]:
        raise ServiceError(f"엔진이 {round(timeout)}초 안에 끝나지 않아 멈췄습니다.")
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


def compare_cuts(a, b):
    """마커용 견주기 — 두 view.json 의 «재단선» 만, 사이즈(S~5XL)·조각마다 하우스도르프 거리(가장 먼 어긋남, mm).
    → {"max_mm", "pieces", "diffs"}. 점 수가 달라도 모양이 같으면 0 이다(점 줄이기 차이에 흔들리지 않게). 일꾼 안에서만(shapely)."""
    from shapely.geometry import LineString
    diffs, worst, n = [], 0.0, 0
    qa, qb = float(a.get("q") or 0.01), float(b.get("q") or 0.01)
    line = lambda flat, q: LineString([(flat[k] * q, flat[k + 1] * q) for k in range(0, len(flat), 2)])
    for sid in GRADE_SIZES:                                       # 가스 S~5XL 만(«2XL-edit» 같은 덧붙은 판은 안 견준다 — 들여온 스타일은 명세 지문으로 확인)
        A, B = (a.get("sizes") or {}).get(sid), (b.get("sizes") or {}).get(sid)
        if A is None and B is None: continue
        if A is None or B is None: diffs.append(f"{sid} 없음"); continue
        pa = {p.get("name"): p for p in A.get("pieces") or []}; pb = {p.get("name"): p for p in B.get("pieces") or []}
        if set(pa) != set(pb): diffs.append(f"{sid} 조각 이름 다름"); continue
        for nm in pa:
            try:
                d = line(pa[nm]["cut"], qa).hausdorff_distance(line(pb[nm]["cut"], qb))
            except Exception:
                diffs.append(f"{sid}/{nm} 재단선 못 읽음"); continue
            worst = max(worst, d); n += 1
    if not n and not diffs: diffs.append("견줄 재단선이 없음")
    return {"max_mm": round(worst, 4), "pieces": n, "diffs": diffs}


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
    gd = sub.add_parser("graded", help="원본 → 그레이딩(graded.json)만 — 마커 ①②③ (F10 4단계)")
    gd.add_argument("--work", required=True); gd.add_argument("--group", required=True, choices=["top", "bottom"])
    gd.add_argument("--rules-file", help="그 버전의 규칙표(다시 그레이딩한 버전) — 없으면 표준 규칙")
    gd.add_argument("--check-view", help="그 버전의 view.json — 다시 만든 모양과 점 하나씩 견준다")
    gd.add_argument("--result"); gd.add_argument("--emit-steps", action="store_true")
    for k in SOURCE_KEYS: gd.add_argument(f"--{k.replace('_', '-')}")
    mk = sub.add_parser("marker", help="graded.json + 요청 JSON → 마커·요척 PDF/DXF/PNG/JSON (F10 4단계 ④)")
    mk.add_argument("--work", required=True); mk.add_argument("--graded", required=True)
    mk.add_argument("--request-file", required=True, help="check_marker_request 모양의 JSON(group·counts·width_cm·gap_mm …)")
    mk.add_argument("--result"); mk.add_argument("--emit-steps", action="store_true")
    mk.add_argument("--spec-file", help="들여온 스타일 펼침표(specs 결과 expand.json)"); mk.add_argument("--title")
    im = sub.add_parser("import", help="OptiCad .ai(여러 사이즈) → 들여온 스타일 묶음 (F10 6단계)")
    im.add_argument("--work", required=True); im.add_argument("--src", required=True); im.add_argument("--base", default="M")
    im.add_argument("--style-id", required=True); im.add_argument("--name"); im.add_argument("--source-name")
    im.add_argument("--max-seconds", type=float, default=IMPORT_MAX_SECONDS, help="일꾼 안 시계 — 넘으면 한국어 사유를 남기고 멈춘다")
    im.add_argument("--result"); im.add_argument("--emit-steps", action="store_true")
    rs = sub.add_parser("restyle", help="들여온 스타일 묶음 → 이름 고치기·규칙 바꿔 다시 그레이딩 (F10 6단계)")
    rs.add_argument("--work", required=True); rs.add_argument("--zip", required=True)
    rs.add_argument("--changes-file", help="{조각: {기준점: {사이즈: [Δx, Δy]}}} — 바꾼 칸만"); rs.add_argument("--names-file")
    rs.add_argument("--by"); rs.add_argument("--check-view", help="이름만 바꿀 때 — 그 버전 view.json 과 모양을 점 하나까지 견준다")
    rs.add_argument("--result"); rs.add_argument("--emit-steps", action="store_true")
    sp = sub.add_parser("specs", help="들여온 스타일 묶음 → 마커용 graded·펼침표 (지문 확인)")
    sp.add_argument("--work", required=True); sp.add_argument("--zip", required=True); sp.add_argument("--files-file", required=True)
    sp.add_argument("--result"); sp.add_argument("--emit-steps", action="store_true")
    ik = sub.add_parser("intake", help="패턴 의뢰 JSON → 패턴 자동 제작 + 그레이딩 (2026-10-22)")
    ik.add_argument("--work", required=True); ik.add_argument("--intake", required=True); ik.add_argument("--style-id")
    ik.add_argument("--sizes", nargs="*"); ik.add_argument("--result"); ik.add_argument("--emit-steps", action="store_true")
    sub.add_parser("font", help="쓰게 될 글꼴")
    a = ap.parse_args(argv)
    if a.cmd == "font":
        print(json.dumps(resolve_font(), ensure_ascii=False)); return 0
    try:
        if a.cmd == "graded":
            rules = None
            if a.rules_file:
                with open(a.rules_file, encoding="utf-8") as f: rules = json.load(f)
            r = graded_all(a.work, a.group, rules, a.check_view, {k: getattr(a, k) for k in SOURCE_KEYS}, emit=a.emit_steps)
        elif a.cmd == "marker":
            with open(a.request_file, encoding="utf-8") as f: req = json.load(f)
            r = marker_all(a.work, a.graded, req, emit=a.emit_steps, spec_file=a.spec_file, title=a.title)
        elif a.cmd == "intake":
            r = intake_all(a.work, a.intake, a.style_id, a.sizes or None, emit=a.emit_steps)
        elif a.cmd == "import":
            r = import_all(a.work, a.src, a.base, a.style_id, a.name, a.source_name, emit=a.emit_steps, max_seconds=a.max_seconds)
        elif a.cmd == "restyle":
            load = lambda p: json.load(open(p, encoding="utf-8")) if p else None
            r = restyle_all(a.work, a.zip, load(a.changes_file), load(a.names_file), a.by, a.check_view, emit=a.emit_steps)
        elif a.cmd == "specs":
            with open(a.files_file, encoding="utf-8") as f: files = json.load(f)
            r = specs_graded(a.work, a.zip, files, emit=a.emit_steps)
        elif a.cmd == "build":
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
    if r.get("mode") == "marker":                              # 마커 — 길이·요척·효율
        sm = r["summary"]
        what = f"마커 {sm.get('length_m')} m · 벌당 {sm.get('yield_m_per_bundle')} m · 효율 {sm.get('efficiency_pct')}%"
    elif r.get("mode") == "graded":
        what = "graded.json" + (f" · 버전과 차 {r['view_match']['max_mm']}mm" if r.get("view_match") else "")
    elif r.get("mode") == "specs":
        what = f"명세 {len(r.get('sizes') or [])}사이즈 · 한 벌 {r.get('per_bundle')}장"
    else:
        what = " · ".join(f"{k} {s['view_bytes']:,}B/{s['zip_bytes']:,}B" for k, s in r["styles"].items())
    print(f"[service] 끝 · 최고 메모리 {r['peak_rss_mb']} MB" + (f" · VmPeak {r['vm_peak_mb']} MB" if r.get("vm_peak_mb") else "")
          + (f" · 안전띠 {r['guard']}" if r.get("guard") else "") + " · " + what, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
