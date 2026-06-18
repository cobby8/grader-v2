# -*- coding: utf-8 -*-
"""job — 주문서(선수 명단) × 디자인 → 선수별 통합 출력 오케스트레이터.

배경(왜 grade() 로 부족한가):
  grade() 는 number/name 을 "단일 값"으로 받아 **전 사이즈 1PDF** 를 만든다.
  하지만 실제 작업 단위는 **선수별**이다 — 같은 사이즈라도 선수마다 배번·이름이 다르고,
  한 선수는 자기 사이즈 1페이지만 필요하다. 그래서 주문 행마다 그 선수의 사이즈 레이아웃을
  골라 배번/이름을 갈아끼워 출력하는 응용 계층이 따로 필요하다 — 이게 job.py 다.

설계 비유(식당 주방장):
  주문서(전표)를 한 장씩 보고, 그 선수의 사이즈 '레시피'만 골라 배번·이름을 얹어
  1인분(=PDF 1개/페이지 1장)을 굽는다. 오븐(compose)·레시피해석(build_layouts)·
  검수(verify_output)는 기존 것을 **그대로** 호출한다(불변 제약 준수).

불변 제약(절대 지킴):
  compose / Piece / SizeLayout / parse_svg / scale_translate / verify_output 의
  시그니처·동작을 수정하지 않는다. build_layouts / grade 도 무수정(있는 인자만 사용).
  '사이즈 좁히기'는 preset dict 를 **얕게 복제**해 sizes 만 1개로 교체하는 방식으로
  처리한다(원본 preset 변형 금지 — _dir / number_area 등 보존).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from typing import List, Optional

from .compose import compose
from .grade import build_layouts, load_preset
from .verify import all_passed, verify_output

try:
    # 미리보기 PNG 는 선택 기능. PyMuPDF 미설치 환경에서도 job 핵심은 동작해야 하므로
    # import 실패를 치명적으로 보지 않는다(미리보기만 생략).
    from . import preview as _preview
except Exception:  # pragma: no cover - 방어적
    _preview = None


# ── 파일명 안전화 ────────────────────────────────────────────────────────────
_FORBIDDEN = set('/\\:*?"<>|')


def _safe_name(value: str) -> str:
    """파일명에 쓸 수 없는 문자를 _ 로 바꾸고 공백을 정리한다. 빈 이름은 'noname'.

    한글은 그대로 허용한다(Windows/한글 파일명 OK). 경로 구분/금지문자만 치환한다.
    """
    s = "".join("_" if ch in _FORBIDDEN else ch for ch in (value or "")).strip()
    return s or "noname"


def _num_for_filename(number: str) -> str:
    """파일명용 배번. 숫자면 2자리 zero-pad(정렬·식별 편의), 아니면 안전화한 원본.

    ⚠️ 출력 글자(실제 배번)는 원본 그대로 쓴다 — zero-pad 는 **파일명에만** 적용한다.
    """
    n = (number or "").strip()
    if not n:
        return "noNum"
    return n.zfill(2) if n.isdigit() else _safe_name(n)


def _atomic_save_compose(design_pdf: str, layouts, final_path: str) -> int:
    """compose 를 임시 파일에 쓰고 os.replace 로 최종 경로에 원자적 배치한다.

    중간에 죽어도 부분 파일이 최종 경로에 남지 않게 하기 위함(작업폴더 원자적 쓰기 원칙).
    Returns: compose 가 돌려준 배치(Do) 횟수 — verify 의 expected_placements 로 그대로 넘긴다.
    """
    out_dir = os.path.dirname(os.path.abspath(final_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=out_dir)
    os.close(fd)  # compose 가 직접 경로에 쓰므로 핸들은 닫는다.
    try:
        placements = compose(design_pdf, layouts, tmp, design_page=0)
        os.replace(tmp, final_path)  # 원자적 이동(같은 볼륨)
        return placements
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _checks_to_dicts(checks) -> list:
    """verify 의 Check 데이터클래스 목록을 JSON 직렬화 가능한 dict 목록으로 바꾼다."""
    return [asdict(c) for c in checks]


def _sized_preset(preset: dict, size_def: dict) -> dict:
    """preset 을 얕게 복제하고 sizes 만 [size_def] 1개로 좁힌다(원본 무변형).

    number_area / name_area / pieces / _dir 등 나머지 키는 공유한다(읽기 전용 사용).
    """
    return {**preset, "sizes": [size_def]}


def run_job(preset: str,
            design_pdf: str,
            order_rows: List[dict],
            out_dir: str,
            font_path: Optional[str] = None,
            split: str = "per_player",
            make_preview: bool = True) -> dict:
    """주문 행(선수)마다 그 선수 사이즈 1페이지에 배번/이름을 얹어 PDF 한 벌을 만든다.

    매개변수
      preset      : preset.json 경로(str). 내부에서 load_preset 한다.
      design_pdf  : 기준 디자인(.ai/.pdf) 경로.
      order_rows  : parse_order 결과 [{name, number, size, qty}] 리스트.
      out_dir     : 작업 루트(예: data/jobs/<날짜_주문명>/). 아래 output/·preview/·job.json 생성.
      font_path   : (현재 미사용) 폰트는 preset 의 number_area/name_area.font 에 박혀 있다.
                    인터페이스 안정성을 위해 받되, 추후 area.font 오버라이드 훅으로 활용 예정.
      split       : "per_player"(기본, 선수별 파일) | "single"(다페이지 1PDF).
      make_preview: True 면 출력마다 검수용 PNG 생성(PyMuPDF 있을 때만).

    반환(dict): {"outputs": [...], "summary": {...}}  — 자세한 형태는 아래 코드 참조.
    실패 정책: 행 단위 실패(사이즈 없음/미지원/렌더 오류)는 skip + 사유 기록으로 흘리고
              전체를 죽이지 않는다(부분 성공). 디자인/preset 자체 누락은 시작 전 예외 전파.
    """
    if split not in ("per_player", "single"):
        raise ValueError(f"split 은 'per_player' 또는 'single' 이어야 합니다(받은 값: {split!r})")

    # ── 시작 전 차단: preset/디자인은 여기서 한 번 검증한다(없으면 친절한 예외 전파). ──
    preset_dict = load_preset(preset)  # FileNotFoundError/ValueError 친절 메시지
    if not os.path.exists(design_pdf):
        raise FileNotFoundError(f"디자인 파일 없음: {design_pdf}")

    # 사용 가능한 사이즈 맵(이름 → 사이즈 정의). 주문 사이즈를 여기에 대조한다.
    size_map = {s["name"]: s for s in preset_dict["sizes"]}

    output_dir = os.path.join(out_dir, "output")
    preview_dir = os.path.join(out_dir, "preview")
    os.makedirs(output_dir, exist_ok=True)

    outputs: list = []
    skipped: list = []
    warnings: list = []
    missing_sizes: set = set()
    used_filenames: set = set()  # 파일명 충돌 회피용

    # single 모드에서 누적할 (layout, meta) 목록.
    single_layouts: list = []
    single_meta: list = []

    for idx, row in enumerate(order_rows):
        size = (row.get("size") or "").strip()
        name = row.get("name") or ""
        number = row.get("number") or ""

        # ── 엣지: 사이즈 빈값 → skip ──
        if not size:
            skipped.append({"row": idx, "name": name, "reason": "사이즈 빈값"})
            continue
        # ── 엣지: preset 에 없는 사이즈(아직 패턴 미확보 등) → skip + missing 집계 ──
        if size not in size_map:
            missing_sizes.add(size)
            skipped.append({"row": idx, "name": name,
                            "reason": f"preset 에 없는 사이즈 '{size}'"})
            continue

        # ── 이 선수의 사이즈만 남긴 preset 으로 레이아웃 1개 생성(배번/이름 주입). ──
        sized = _sized_preset(preset_dict, size_map[size])
        row_warns: list = []
        try:
            layouts = build_layouts(sized, design_pdf,
                                    number=number, name=name, warnings=row_warns)
        except Exception as e:  # 렌더 단계 행 실패는 흘린다(부분 성공).
            skipped.append({"row": idx, "name": name,
                            "reason": f"레이아웃 생성 실패: {e}"})
            continue
        # build_layouts 는 사이즈 1개를 줬으니 layout 도 1개.
        layout = layouts[0]

        # 글리프 누락 등 행 경고는 선수 식별과 함께 전체 warnings 에 누적(사람 검수용).
        for w in row_warns:
            warnings.append(f"[행{idx} {name or '(무명)'} {size}] {w}")

        # ── 파일/페이지 식별자 ──
        fn_num = _num_for_filename(number)
        base_id = f"{size}_{fn_num}_{_safe_name(name)}"
        # 충돌 회피: 이미 쓴 식별자면 _2, _3 … 접미사.
        ident = base_id
        n = 2
        while ident in used_filenames:
            ident = f"{base_id}_{n}"
            n += 1
        used_filenames.add(ident)

        meta = {"row": idx, "size": size, "name": name, "number": number,
                "qty": row.get("qty", ""), "ident": ident}

        if split == "single":
            # 페이지 식별을 위해 SizeLayout.name 을 선수 식별자로 덮어쓴다(읽기 전용 표식).
            layout.name = ident
            single_layouts.append(layout)
            single_meta.append(meta)
            continue

        # ── per_player: 선수 1명 = PDF 1개(원자적 저장) → verify → (옵션)미리보기 ──
        pdf_path = os.path.join(output_dir, f"{ident}.pdf")
        try:
            placements = _atomic_save_compose(design_pdf, [layout], pdf_path)
        except Exception as e:
            skipped.append({"row": idx, "name": name, "reason": f"합성 실패: {e}"})
            used_filenames.discard(ident)
            continue

        checks = verify_output(pdf_path, design_pdf, placements)
        verify_pass = all_passed(checks)

        preview_rel = None
        if make_preview and _preview is not None:
            try:
                os.makedirs(preview_dir, exist_ok=True)
                png = os.path.join(preview_dir, f"{ident}.png")
                _preview.render_page(pdf_path, png, page=0)
                preview_rel = os.path.relpath(png, out_dir).replace("\\", "/")
            except Exception as e:
                warnings.append(f"[행{idx} {name}] 미리보기 생성 실패(무시): {e}")

        outputs.append({
            "size": size, "name": name, "number": number,
            "pdf": os.path.relpath(pdf_path, out_dir).replace("\\", "/"),
            "preview": preview_rel,
            "checks": _checks_to_dicts(checks),
            "verify_pass": verify_pass,
        })

    # ── single 모드 마무리: 누적 레이아웃을 1회 compose → 1회 verify ──
    if split == "single" and single_layouts:
        job_name = os.path.basename(os.path.normpath(out_dir)) or "job"
        pdf_path = os.path.join(output_dir, f"{_safe_name(job_name)}_all.pdf")
        placements = _atomic_save_compose(design_pdf, single_layouts, pdf_path)
        checks = verify_output(pdf_path, design_pdf, placements)
        verify_pass = all_passed(checks)

        previews_rel = []
        if make_preview and _preview is not None:
            try:
                os.makedirs(preview_dir, exist_ok=True)
                pngs = _preview.render_previews(pdf_path, preview_dir, prefix=_safe_name(job_name))
                previews_rel = [os.path.relpath(p, out_dir).replace("\\", "/") for p in pngs]
            except Exception as e:
                warnings.append(f"single 미리보기 생성 실패(무시): {e}")

        # single 은 다페이지 1개라 outputs 도 1개로 묶되, 어떤 선수가 몇 페이지인지 players 로 남긴다.
        outputs.append({
            "size": "(multi)", "name": "(전체)", "number": "",
            "pdf": os.path.relpath(pdf_path, out_dir).replace("\\", "/"),
            "preview": previews_rel,
            "players": [{"page": i + 1, **single_meta[i]} for i in range(len(single_meta))],
            "checks": _checks_to_dicts(checks),
            "verify_pass": verify_pass,
        })

    # ── summary 집계 ──
    produced = len(outputs)
    verify_ok = sum(1 for o in outputs if o.get("verify_pass"))
    summary = {
        "job_dir": os.path.abspath(out_dir),
        "split": split,
        "total_players": len(order_rows),
        "produced": produced,
        "verify_pass": verify_ok,
        "verify_fail": produced - verify_ok,
        "skipped": skipped,
        "warnings": warnings,
        "missing_sizes": sorted(missing_sizes),
    }
    result = {"outputs": outputs, "summary": summary}

    # ── job.json 덤프(폴더+JSON 저장 원칙). 원자적으로 쓴다. ──
    job_json = os.path.join(out_dir, "job.json")
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=out_dir)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, job_json)

    return result
