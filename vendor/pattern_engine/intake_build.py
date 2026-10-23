# 패턴 의뢰 → 패턴 자동 제작 + 그레이딩 (2026-10-22)
#
#   왜: 직원이 그레이더 «패턴 의뢰»(실물 옷 사진·치수)를 제출하면, 사람이 손으로 제도하지 않아도
#       설계도(styles/<옷>.json, 치수표→패턴 F9)로 기준 사이즈 M 패턴을 그리고 하키티 증분으로 S~3XL 까지 만든다.
#       결과는 그레이더 «재단 패턴» 이 받는 묶음(view.json + exports.zip)과 사람이 읽는 확인표(confirm.md)로 낸다.
#       공장에 보내기 전에는 사람이 «검토 완료» 를 한다 — 이 도구는 «검토 대기» 판을 만든다.
#
#   지금 아는 옷: 럭비(긴팔 하키) 저지 — 소매 상의 · V넥 립 · 긴팔 · 립 커프스 · 요크 (styles/rugby_jersey.json)
#   다른 구성은 «자동 제도기가 없는 옷» 으로 멈춘다(엉뚱한 설계도로 그리지 않는다).
#
#   치수 환산(의뢰 앱 정의 → 설계도 정의 · 이상훈 2026-10-22 확인):
#     V 깊이   앱 = 두 옆목점 잇는 선에서 V 꼭짓점까지 세로   → 설계도 = 옆목점에서 V 꼭짓점 직선  √(세로² + (목너비/2)²)
#     뒤 요크  앱 = 옆목점 잇는 선에서                         → 설계도 = 뒷목에서  (앱 값 − 뒷목 깊이)
#     어깨 처짐 앱엔 없음 — 어깨선 길이·어깨너비·목너비로 계산   √(어깨선² − (어깨너비/2 − 목너비/2)²)
#     단면 값은 × 2 해 둘레로 · 시접은 디자이너 규칙(옆 0.7cm · 밑단 2cm — 실물 오버록 0.5cm)
#
#   실행(저장소 루트): python tools/pattern-engine/intake_build.py <의뢰.json> --out <폴더> [--sizes S M L XL 2XL 3XL] [--style-id …]
#     의뢰.json = 그레이더 pattern_intakes 행(code·product_name·size_label·base_type·parts·data) 그대로
import argparse, datetime, json, math, os, re, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)

import cad_view
import parametric
import seam_check
from piecespec import compute_cut

FORMAT = "stiz-intake-build"; FORMAT_VERSION = 1
SA_SIDE = 7.0; SA_HEM = 20.0                  # 디자이너 규칙(김현서 10-22): 옆면 시접 0.7cm · 밑단 시접 2cm
STYLE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]")
SIZE_ORDER = ["5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
STEPS = ["read", "draft", "grade", "export", "bundle"]
SIZE_ALIAS = {"XXS": "2XS", "XXL": "2XL", "XXXL": "3XL", "XXXXL": "4XL"}   # 의뢰 «사이즈» 칸의 옛 표기

# 의뢰 옷 구성 → 설계도. need = 반드시 있어야 하는 부품 · 하나라도 빠지면 그 설계도가 아니다
STYLES = [
    {"key": "rugby_jersey", "ko": "럭비(긴팔 하키) 저지", "base_type": "sleeve_top",
     "need": ["neck:v_rib", "length:long", "cuff:rib", "extra:yoke"], "allow_sleeve": ["sleeve:set_in"],
     "style": "styles/rugby_jersey.json", "grade": "styles/rugby_jersey_grade.json"},
]


class IntakeBuildError(ValueError):
    """사람에게 보일 한국어 사유"""


def _parts(row):
    p = row.get("parts")
    if isinstance(p, str):
        try: p = json.loads(p)
        except ValueError: p = []
    return [str(x) for x in (p or [])]


def _data(row):
    d = row.get("data")
    if isinstance(d, str):
        d = json.loads(d)
    return d if isinstance(d, dict) else {}


def select_style(row):
    """의뢰 행 → STYLES 한 칸. 없으면 IntakeBuildError"""
    parts = set(_parts(row))
    for st in STYLES:
        if row.get("base_type") != st["base_type"]: continue
        if not all(n in parts for n in st["need"]): continue
        sl = [x for x in parts if x.startswith("sleeve:")]
        if sl and not all(x in st["allow_sleeve"] for x in sl): continue
        return st
    raise IntakeBuildError("자동 제도기가 없는 옷 구성입니다(" + ", ".join(sorted(parts)) + ") — 패턴사에게 맡겨 주세요.")


def _num(meas, key, field="v"):
    """의뢰 치수 칸 → cm 숫자. 못 잰 칸·빈 칸은 None"""
    m = meas.get(key)
    if not isinstance(m, dict): return None
    if (m.get("skip") or {}).get(field): return None
    v = (m.get("values") or {}).get(field)
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def to_values(row):
    """의뢰 치수(cm, 앱 정의) → 설계도 입력(mm, 설계도 정의) + 환산표(확인표용)"""
    meas = _data(row).get("measures") or {}
    need = {"body_length": "총장", "shoulder_width": "어깨너비", "chest_half": "가슴 단면", "hem_half": "밑단 단면",
            "sleeve_length": "소매 길이", "bicep_half": "소매통", "armhole_depth": "진동 깊이", "neck_width": "목너비",
            "front_neck_drop": "앞목 깊이", "back_neck_drop": "뒷목 깊이", "shoulder_seam": "어깨선 길이",
            "neck_rib_width": "목 립 폭", "cuff_height": "커프스 높이", "sleeve_end_half": "소매 밑단 단면"}
    got = {k: _num(meas, k) for k in need}
    got["yoke_back"] = _num(meas, "yoke_pos", "back"); got["yoke_front"] = _num(meas, "yoke_pos", "front")
    got["cuff_relaxed"] = _num(meas, "cuff_half", "relaxed") if _num(meas, "cuff_half", "relaxed") is not None else _num(meas, "cuff_half")
    miss = [need[k] for k in need if got[k] is None] + (["요크 위치(뒤)"] if got["yoke_back"] is None else []) \
        + (["소매 입구"] if got["cuff_relaxed"] is None else [])
    if miss:
        raise IntakeBuildError("패턴을 그리려면 이 치수가 더 있어야 합니다: " + ", ".join(miss))
    mm = lambda cm: round(cm * 10.0, 1)
    nw = mm(got["neck_width"])
    half_reach = mm(got["shoulder_width"]) / 2 - nw / 2
    seam = mm(got["shoulder_seam"])
    if seam < half_reach:
        raise IntakeBuildError(f"어깨선 길이({got['shoulder_seam']}cm)가 어깨너비·목너비로 계산한 가로 거리보다 짧습니다 — 다시 재 주세요.")
    v = {
        "length_cb": mm(got["body_length"]), "shoulder_width": mm(got["shoulder_width"]),
        "chest": mm(got["chest_half"]) * 2, "hem": mm(got["hem_half"]) * 2, "sleeve_length": mm(got["sleeve_length"]),
        "cuff": mm(got["cuff_relaxed"]) * 2, "armhole_depth": mm(got["armhole_depth"]), "sleeve_width_25": mm(got["bicep_half"]),
        "v_depth": round(math.hypot(mm(got["front_neck_drop"]), nw / 2), 1),
        "yoke_back": round(mm(got["yoke_back"]) - mm(got["back_neck_drop"]), 1),
        "sleeve_hem": mm(got["sleeve_end_half"]) * 2, "neck_width": nw, "back_neck_depth": mm(got["back_neck_drop"]),
        "shoulder_drop": round(math.sqrt(seam * seam - half_reach * half_reach), 1),
        "cuff_height": mm(got["cuff_height"]), "rib_width": mm(got["neck_rib_width"]),
    }
    conv = [
        ("총장", f"{got['body_length']:g}", v["length_cb"], "뒷목 봉제선 → 밑단 끝"),
        ("어깨너비", f"{got['shoulder_width']:g}", v["shoulder_width"], ""),
        ("가슴", f"단면 {got['chest_half']:g}", v["chest"], "둘레(× 2)"),
        ("밑단", f"단면 {got['hem_half']:g}", v["hem"], "둘레(× 2)"),
        ("소매 길이", f"{got['sleeve_length']:g}", v["sleeve_length"], ""),
        ("소매 입구", f"단면 {got['cuff_relaxed']:g}", v["cuff"], "늘이지 않은 둘레(× 2)"),
        ("진동 깊이", f"{got['armhole_depth']:g}", v["armhole_depth"], ""),
        ("소매통", f"{got['bicep_half']:g}", v["sleeve_width_25"], "단면 그대로"),
        ("V 깊이", f"세로 {got['front_neck_drop']:g}", v["v_depth"], "옆목점 → V 꼭짓점 직선으로 환산"),
        ("뒤 요크", f"옆목점 선에서 {got['yoke_back']:g}", v["yoke_back"], "뒷목 기준으로 환산(− 뒷목 깊이)"),
        ("소매 끝", f"단면 {got['sleeve_end_half']:g}", v["sleeve_hem"], "오그리기 전 둘레(× 2) · 커프스에 오그려 붙임"),
        ("목너비", f"{got['neck_width']:g}", v["neck_width"], ""),
        ("뒷목 깊이", f"{got['back_neck_drop']:g}", v["back_neck_depth"], ""),
        ("어깨 처짐", f"어깨선 {got['shoulder_seam']:g}", v["shoulder_drop"], "어깨선·어깨너비·목너비로 계산"),
        ("커프스 높이", f"{got['cuff_height']:g}", v["cuff_height"], ""),
        ("목 립 폭", f"{got['neck_rib_width']:g}", v["rib_width"], ""),
    ]
    notes = []
    if got["yoke_front"] is not None:
        notes.append(f"앞 요크 위치 {got['yoke_front']:g}cm 는 아직 설계도에 쓰지 않는다 — 앞 요크 이음선은 V 꼭짓점 높이를 따른다")
    return v, conv, notes


def base_size_of(row, table):
    """의뢰 «사이즈» 칸(실물을 잰 사이즈) → 증분표의 사이즈 이름. 돌려주는 값 (사이즈, 메모 목록)
    «M(95)»·«L 100» 처럼 뒤에 붙은 글자는 버리고, XXL → 2XL 처럼 옛 표기를 맞춘다. 비어 있으면 표의 기준(M)"""
    raw = str(row.get("size_label") or "").strip()
    if not raw:
        return table["base"], [f"의뢰에 사이즈가 비어 있어 {table['base']} 로 보고 만들었다 — 실물 사이즈를 확인"]
    m = re.match(r"[0-9]*X*[SML]", raw.upper().replace(" ", ""))
    s = SIZE_ALIAS.get(m.group(0), m.group(0)) if m else ""
    if s not in table["sizes"]:
        raise IntakeBuildError(f"의뢰 사이즈 «{raw}» 를 증분표에서 찾지 못했습니다(가능: {' '.join(table['sizes'])}) — 사이즈 칸을 고쳐 주세요.")
    return s, []


def grade_values(base, table, sizes, base_size=None):
    """기준 사이즈 값 + 증분표 → {사이즈: 값}. 증분표는 M 기준이라 기준 사이즈만큼 빼서 다시 잰다(2026-10-22 — L 실물도 맞게).
    표에 없는 사이즈는 IntakeBuildError"""
    known = table["sizes"]
    bs = base_size or table["base"]
    bad = [s for s in list(sizes) + [bs] if s not in known]
    if bad:
        raise IntakeBuildError("증분표에 없는 사이즈: " + ", ".join(dict.fromkeys(bad)) + f" (가능: {' '.join(known)})")
    bi = known.index(table["base"])
    inc = lambda d, s: d["by_size"][s] if "by_size" in d else d.get("step", 0) * (known.index(s) - bi)
    out = {}
    for s in sizes:
        v = dict(base)
        for key, d in table["delta"].items():
            if key not in v: continue
            v[key] = round(base[key] + inc(d, s) - inc(d, bs), 1)
        out[s] = v
    return out


def _flip_spec(sp):
    """parametric 명세(y 아래로 +) → 들여온 스타일 명세와 같은 방향(y 위로 +) + 계산 재단선을 cut_builtin 에(화면 자료용)"""
    cut = compute_cut(sp)
    F = lambda p: [p[0], -p[1]]
    seam = []
    for s in sp["seam"]:
        t = dict(s, y=-s["y"])
        if s.get("notch"):
            nt = dict(s["notch"]); u = nt.get("dir") or [0, 0]; nt["dir"] = [u[0], -u[1]]; t["notch"] = nt
        seam.append(t)
    out = dict(sp, seam=seam, cut_builtin=[F(p) for p in cut], sa_builtin=True)
    out["internal"] = [dict(d, pts=[F(p) for p in d["pts"]], **({"snap": F(d["snap"])} if d.get("snap") else {}))
                       for d in sp.get("internal") or []]
    out["notch_lines"] = [[F(a), F(b)] for a, b in (sp.get("notch_lines") or [])]
    out["fold"] = [F(p) for p in sp["fold"]] if sp.get("fold") else None
    return out


def _md_table(rows, head):
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def confirm_md(row, st, conv, notes, table, sizes, values, measured, made_at, base_size, seams=None):
    d = table["delta"]
    keys = list(values[sizes[0]].keys())
    label = {"length_cb": "총장", "shoulder_width": "어깨너비", "chest": "가슴둘레", "hem": "밑단둘레", "sleeve_length": "소매 길이",
             "cuff": "소매 입구 둘레", "armhole_depth": "진동 깊이", "sleeve_width_25": "소매통(단면)", "v_depth": "V 깊이(직선)",
             "yoke_back": "뒤 요크(뒷목~)", "sleeve_hem": "소매 끝 둘레", "neck_width": "목너비", "back_neck_depth": "뒷목 깊이",
             "shoulder_drop": "어깨 처짐", "cuff_height": "커프스 높이", "rib_width": "목 립 폭"}
    assumed = assumed_changed(table, sizes, values, base_size)
    size_rows = []
    for k in keys:
        mark = "※ " if (d.get(k) or {}).get("from") == "가정" else ""
        size_rows.append([mark + label.get(k, k)] + [f"{values[s][k]:g}" for s in sizes] + [(d.get(k) or {}).get("note", "")])
    meas_keys = list(measured[sizes[0]].keys())
    meas_rows = [[mk] + [f"{measured[s][mk]:.1f}" for s in sizes] for mk in meas_keys]
    parts = []
    parts.append(f"# 확인표 — {row.get('product_name') or st['ko']} ({row.get('code') or '의뢰'})\n")
    parts.append(f"만든 때 {made_at} · 설계도 «{st['ko']}» · 기준 사이즈 {base_size}(실물 {row.get('size_label') or base_size} 실측) · 사이즈 {' '.join(sizes)}\n")
    parts.append("**상태: 검토 대기** — 패턴사·디자이너가 확인한 뒤 «검토 완료» 를 해야 공장·합성에 쓴다.\n")
    parts.append(f"## 1. 의뢰 치수 → 설계도 값 ({base_size}, mm)\n")
    parts.append(_md_table([[a, b, f"{c:g}", e] for a, b, c, e in conv], ["항목", "의뢰 값(cm)", "설계도 값(mm)", "환산"]))
    parts.append(f"\n시접: 옆·어깨·소매 {SA_SIDE:g}mm · 밑단 {SA_HEM:g}mm (디자이너 규칙 — 실물 오버록 0.5cm)\n")
    parts.append("## 2. 사이즈별 설계도 값 (mm) — ※ = 가정한 증분\n")
    parts.append(f"증분 출처: {table['source']}\n")
    parts.append(_md_table(size_rows, ["항목"] + sizes + ["증분 근거"]))
    parts.append("\n## 3. 만들어진 패턴 완성 치수 (mm, 재봉선 기준)\n")
    parts.append(_md_table(meas_rows, ["치수"] + sizes))
    if seams:
        parts.append(f"\n## 4. 솔기 대조 — 꿰매지는 짝 {seams['seams']}쌍 (mm · ✖ 어긋남 · ⚠ 주의)\n")
        parts.append("같음 짝은 길이 차(b−a) · 소매산은 여유(소매산−진동) · 립은 몸판 대비 길이(%). 왼쪽은 오른쪽의 거울이라 같다.\n")
        parts.append(seam_check.md_section(seams, sizes))
    parts.append("\n## 5. 확인할 것\n")
    items = []
    if seams:
        items += seam_check.md_issues(seams, sizes)
        if not seams["bad"] and not seams["warn"]:
            items.append(f"솔기 대조 {seams['seams']}쌍 모두 맞음 — 길이·시접·노치")
    if assumed:
        items.append("※ 가정한 증분(하키티에 없는 항목): " + ", ".join(label.get(k, k) for k in assumed) + " — 실제 사이즈 샘플로 확인")
    far = [s for s in sizes if s in ("2XL", "3XL") and s != base_size]
    if far:
        items.append("·".join(far) + " 는 하키티(XS~XL)에 없어 L→XL 간격으로 늘렸다")
    if sizes == [base_size]:
        items.append(f"기준 사이즈 {base_size} 만 만들었다 — 다른 사이즈는 의뢰 화면에서 골라 그레이딩")
    items.append("V 인서트 조각은 아직 설계도에 없다(10/18 결정 «V 인서트 넣는다» — 다음 설계도 판)")
    items += notes
    parts.append("\n".join(f"- [ ] {t}" for t in items))
    return "\n".join(parts) + "\n"


def assumed_changed(table, sizes, values, base_size):
    """이번에 만든 사이즈에서 실제로 값이 바뀐 «가정» 증분 칸 — 기준 사이즈만 만들면 없다"""
    d = table["delta"]
    return [k for k in values[sizes[0]] if (d.get(k) or {}).get("from") == "가정" and any(values[s][k] != values[base_size][k] for s in sizes)]


def build(row, out, sizes=None, style_id=None, export=True, progress=None):
    """의뢰 행 → 묶음 쓰기. sizes 를 안 주면 기준 사이즈(의뢰 «사이즈» 칸)만, 주면 기준 + 그 사이즈들(2026-10-22).
    돌려주는 값 {style_id, sizes, base_size, paths, summary}"""
    step = progress or (lambda _s: None)
    step("read")
    st = select_style(row)
    style = parametric.load_json(os.path.join(HERE, st["style"]))
    style = json.loads(json.dumps(style)); style["params"]["sa"] = SA_SIDE; style["params"]["hem_sa"] = SA_HEM
    table = parametric.load_json(os.path.join(HERE, st["grade"]))
    bs, bnotes = base_size_of(row, table)
    sizes = sorted(dict.fromkeys(list(sizes or []) + [bs]), key=lambda s: SIZE_ORDER.index(s) if s in SIZE_ORDER else 99)
    code = str(row.get("code") or "intake")
    sid = style_id or re.sub(r"[^a-z0-9-]+", "-", f"{st['key'].replace('_', '-')}-{code.lower()}").strip("-")
    if not STYLE_ID_RE.fullmatch(sid):
        raise IntakeBuildError(f"스타일 번호가 이상합니다: {sid!r}")
    base, conv, notes = to_values(row)
    notes = bnotes + notes
    step("draft")
    vals = grade_values(base, table, sizes, bs)
    step("grade")
    os.makedirs(os.path.join(out, "specs"), exist_ok=True)
    specs, measured, extra, models = {}, {}, [], {}
    name = f"{row.get('product_name') or st['ko']} ({code})"
    for s in sizes:
        meas = {"name": f"{name} {s}", "size": s, "unit": "mm", "values": vals[s]}
        try:
            R = parametric.build(style, meas)
        except parametric.FormulaError as e:
            raise IntakeBuildError(f"{s} 사이즈 패턴을 그리지 못했습니다: {e}")
        specs[s] = R["specs"]; measured[s] = parametric.measures(R, style); models[s] = R["model"]
        with open(os.path.join(out, "specs", f"spec_{s}.json"), "w", encoding="utf-8") as f:
            json.dump({"format": "stiz-style-size", "size": s, "pieces": R["specs"]}, f, ensure_ascii=False, separators=(",", ":"))
        if export:
            if s == sizes[0]: step("export")
            d = os.path.join(out, "sizes", s)
            E = parametric.export_pattern(R, style, meas, d, f"{sid}_{s}")
            for fp in E["files"]:
                if fp.endswith((".dxf", ".pdf", ".ai")) and os.path.isfile(fp):
                    extra.append((fp, f"sizes/{s}/{os.path.basename(fp).replace('1대1', '1to1')}"))
    step("bundle")
    made_at = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    P = {"intake": os.path.join(out, "intake.json"), "check": os.path.join(out, "check.json"),
         "confirm": os.path.join(out, "confirm.md"), "view": os.path.join(out, "view.json"), "zip": os.path.join(out, "exports.zip")}
    with open(P["intake"], "w", encoding="utf-8") as f:
        json.dump({"code": code, "product_name": row.get("product_name"), "size_label": row.get("size_label"),
                   "base_type": row.get("base_type"), "parts": _parts(row), "measures": _data(row).get("measures"),
                   "answers": _data(row).get("answers")}, f, ensure_ascii=False, indent=1)
    assumed = assumed_changed(table, sizes, vals, bs)
    try:
        seams = seam_check.check(specs, style["sewing"], models) if style.get("sewing") else None
    except seam_check.SeamCheckError as e:
        raise IntakeBuildError(f"솔기 대조를 하지 못했습니다: {e}")
    check = {"format": FORMAT, "version": FORMAT_VERSION, "style": st["key"], "base_size": bs, "base_values": base, "values": vals,
             "measured": measured, "grade_source": table["source"],
             "assumed": sorted(assumed), "seams": seams, "made_at": made_at}
    with open(P["check"], "w", encoding="utf-8") as f: json.dump(check, f, ensure_ascii=False, indent=1)
    with open(P["confirm"], "w", encoding="utf-8") as f: f.write(confirm_md(row, st, conv, notes, table, sizes, vals, measured, made_at, bs, seams))
    entries = [(P["check"], "check.json"), (P["confirm"], "confirm.md")]
    entries += [(os.path.join(out, "specs", f"spec_{s}.json"), f"specs/spec_{s}.json") for s in sizes] + extra
    files = []
    for fp, zn in entries:
        assert all(c.isascii() for c in zn), zn
        kind = "check" if zn == "check.json" else "confirm" if zn == "confirm.md" else \
            "spec" if zn.startswith("specs/") else zn.rsplit(".", 1)[-1]
        f = {"kind": kind, "path": zn, "orig": os.path.basename(fp), "bytes": os.path.getsize(fp), "sha256": cad_view.sha256(fp)}
        m = re.match(r"(?:specs/spec_|sizes/)([A-Za-z0-9]+)", zn)
        if m: f["size"] = m.group(1)
        files.append(f)
    with zipfile.ZipFile(P["zip"], "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for fp, zn in entries + [(P["intake"], "intake.json")]:
            zi = zipfile.ZipInfo(zn, cad_view.ZIP_TIME); zi.compress_type = zipfile.ZIP_DEFLATED
            with open(fp, "rb") as fh: z.writestr(zi, fh.read())
        zi = zipfile.ZipInfo("manifest.json", cad_view.ZIP_TIME); zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, json.dumps({"style_id": sid, "made_at": made_at, "intake": code, "files": files}, ensure_ascii=False, indent=1))
    zinfo = {"name": "exports.zip", "sha256": cad_view.sha256(P["zip"]), "bytes": os.path.getsize(P["zip"])}
    import style_import as SI                                      # 화면 자료는 들여온 스타일과 같은 꼴(build_view)로
    pieces = list(specs[sizes[0]].keys())
    smeta = {"id": sid, "name": name, "sizes": sizes, "pieces": pieces, "made_at": made_at, "source_file": f"{code}.json",
             "garment": st["ko"], "group": "intake"}
    flipped = {s: {n: _flip_spec(sp) for n, sp in specs[s].items()} for s in sizes}
    view = SI.build_view(smeta, flipped, bs, {"sizes": {}}, files, zinfo)
    view["style"]["imported"] = False
    view["style"]["intake"] = code
    view["source"].update(engine="stizshop tools/pattern-engine (intake_build)", inputs=[f"패턴 의뢰 {code}"],
                          note=f"패턴 의뢰 {code} 치수로 자동 제작 · 하키티 증분 · 검토 대기")
    with open(P["view"], "w", encoding="utf-8") as f: json.dump(view, f, ensure_ascii=False, separators=(",", ":"))
    summary = {"style_id": sid, "style": st["key"], "sizes": sizes, "base_size": bs, "available": list(table["sizes"]),
               "pieces": len(pieces), "intake": code, "assumed": check["assumed"], "made_at": made_at,
               "seams": {"pairs": seams["seams"], "ok": seams["ok"], "bad": len(seams["bad"]), "warn": len(seams["warn"]),
                         "issues": [f"{s_} {ko}: {say}" for s_, ko, say in (seams["bad"] + seams["warn"])][:20]} if seams else None}
    return {"style_id": sid, "sizes": sizes, "base_size": bs, "pieces": pieces, "name": name, "paths": P, "summary": summary}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="패턴 의뢰 → 패턴 자동 제작 + 그레이딩")
    ap.add_argument("intake", help="그레이더 pattern_intakes 행 JSON")
    ap.add_argument("--out", required=True); ap.add_argument("--sizes", nargs="*"); ap.add_argument("--style-id")
    ap.add_argument("--no-export", action="store_true", help=".ai·PDF·DXF 는 빼고 명세·화면 자료만")
    a = ap.parse_args(argv)
    with open(a.intake, encoding="utf-8") as f: row = json.load(f)
    try:
        r = build(row, a.out, a.sizes, a.style_id, export=not a.no_export, progress=lambda s: print("·", s, flush=True))
    except IntakeBuildError as e:
        print("실패:", e); return 2
    print(json.dumps(r["summary"], ensure_ascii=False))
    for k, p in r["paths"].items(): print(f"  {k}: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
