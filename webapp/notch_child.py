# -*- coding: utf-8 -*-
"""노치 엔진 일꾼 — 웹 프로세스 밖(별도 프로세스)에서 엔진 사본(notch_rules·preset_export)을 돌린다.

왜 따로 도나(2026-10-20 리뷰): 엔진은 fitz·shapely·ezdxf·aama 를 불러 웹 프로세스 메모리를 ~33MB 늘리고,
  엔진 폴더를 sys.path 에 넣으면 service·illustrator·notching 같은 이름이 웹 전역에서 보인다.
  cad.py 가 엔진을 «일꾼»으로 돌리는 것과 같은 생각 — 일이 끝나면 프로세스가 사라져 메모리도 돌려준다.

부르는 법: python -m webapp.notch_child <요청.json>   (결과는 요청의 "result" 경로에 JSON 으로)
  op=convert : 한 사이즈 .ai/.svg → <사이즈>.svg(깨끗한 외곽선) + <사이즈>.notched.svg(노치 든 재단선) + 노치 자리
  op=dxf     : 프리셋 폴더 → 공장용 재단 패턴 DXF zip(사이즈마다 한 장)
"""
import json
import os
import sys
import zipfile

MM = 25.4 / 72


def _engine(eng_dir):
    for f in ("notch_rules.py", "preset_export.py"):
        if not os.path.isfile(os.path.join(eng_dir, f)):
            raise RuntimeError(f"엔진 사본에 {f} 가 없습니다({eng_dir}) — scripts/sync_pattern_engine.py 로 맞춰 주세요")
    sys.path.insert(0, eng_dir)
    import notch_rules, preset_export  # noqa: E402
    return notch_rules, preset_export


def convert(req, nr, pe):
    r = nr.grader_size(req["src"], req["rule"], req.get("side"), req.get("select"))
    if not r["pieces"]:
        raise RuntimeError("고른 조각이 이 사이즈 파일에 없습니다" + (f"(남긴 이름 {req.get('select')})" if req.get("select") else ""))
    w = pe.write_svgs(r["pieces"], req["out_svg"], req["notched_svg"])
    return {"pieces_written": w["pieces_written"], "viewBox": w["viewBox"],
            "meta": {"pieces": w["sites_pt"], "kinds": [q["kind"] for q in r["pieces"]],
                     "mirror": [bool(q.get("mirror")) for q in r["pieces"]],
                     "notched": r["notched"], "existing": r["existing"], "dropped": r["dropped"]},
            "clipped": len(r.get("clipped") or [])}


def dxf(req, nr, pe):
    with open(os.path.join(req["pattern_dir"], "preset.json"), encoding="utf-8") as f:
        preset = json.load(f)
    nmeta = (preset.get("notches") or {}).get("sizes") or {}
    title = req["title"]; n = 0
    with zipfile.ZipFile(req["out_zip"], "w", zipfile.ZIP_DEFLATED) as zf:
        for m in preset.get("sizes") or []:
            svg = os.path.join(req["pattern_dir"], m["pattern_file"])
            if not os.path.isfile(svg):
                continue
            doc = nr.read_svg_doc(svg)
            outlines = [d["subpaths"][0][:-1] for d in doc["drawings"]]
            meta = nmeta.get(m["name"]) or {}
            sites_all = meta.get("pieces") or []; kinds = meta.get("kinds") or []; mir = meta.get("mirror") or []
            pieces = []
            for i, P in enumerate(outlines):                       # 손으로 고친 preset 이라 개수가 모자라도 죽지 않게
                sites = [{"p": (s["p"][0] * MM, s["p"][1] * MM), "w": tuple(s["w"]), "depth": s.get("depth_mm", 5.0)}
                         for s in (sites_all[i] if i < len(sites_all) else [])]
                pieces.append({"outline": P, "sites": sites, "kind": kinds[i] if i < len(kinds) else "part",
                               "mirror": mir[i] if i < len(mir) else False})
            zf.writestr(f"{title}_{m['name']}.dxf", pe.dxf_bytes(pieces, m["name"], title)); n += 1
    return {"files": n}


def main(argv):
    with open(argv[1], encoding="utf-8") as f:
        req = json.load(f)
    out = {}
    try:
        nr, pe = _engine(req["engine_dir"])
        out = {"ok": True, **(convert(req, nr, pe) if req["op"] == "convert" else dxf(req, nr, pe))}
    except Exception as e:                                         # 일꾼 오류는 결과 파일로 돌려준다(웹이 경고로 옮긴다)
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    with open(req["result"], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
