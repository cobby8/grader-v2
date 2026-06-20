# -*- coding: utf-8 -*-
"""/api 엔드포인트 핸들러(1단계: health · patterns · settings 읽기).

각 핸들러는 '엔진 호출을 감싸는 얇은 래퍼' 다. 비즈니스 로직(합성·검증)은
engine/ 에 있고, 여기서는 그걸 호출해 화면이 먹기 좋은 JSON 으로 바꿔 줄 뿐이다.

설계 제약:
  - 엔진 공개 API(load_preset 등)는 '호출' 만 한다. 수정 금지.
  - 에러는 한국어로 "원인 + 다음 행동" 을 함께.
"""
from __future__ import annotations

import io
import os
import tempfile
import threading
import traceback
import zipfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, Body
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse

from . import state
from .state import DEFAULT_PORT

# 엔진 공개 API 는 import 만 한다(수정 금지). preset.json 로드/검증을 재사용한다.
from engine.grade import load_preset
# 주문서 파싱·투명도 평탄화/스캔·채움수집 헬퍼도 '호출' 만 한다(엔진 무수정).
from engine.order import parse_order
from engine.flatten import flatten_transparency
from engine.verify import scan_transparency
from engine.reference import _collect_fills
# 생성 본체. run_job 은 '호출' 만 한다(시그니처·동작 무수정).
from engine.job import run_job

import json

import pikepdf

# /api 아래로 묶일 라우터. main.py 가 이 router 를 앱에 붙인다.
router = APIRouter(prefix="/api")

# ── 디자인 점검 임계값(소스 상수, preset 외 보정 휴리스틱) ──────────────────
#   왜 이 숫자들이 여기 있나: ②/④ 판정의 '경계선'이라 한 곳에 모아 둔다.
#   실파일 측정으로 잡은 값이며, 디자인이 바뀌면 여기만 손보면 된다.
#
#   - 본체 누락(②): 정상 빈본체는 page0 콘텐츠가 88KB 급. PDF호환 저장 실패본은
#     3.4KB 급(껍데기만 남음). 그 사이 안전선으로 10KB 를 둔다.
_BODY_MIN_BYTES = 10_000
#   - 베이크(④) 흰글리프 임계: 번호영역으로 좁혀 흰색 글리프를 셀 때
#       정상 빈템플릿 = 12개(앞6/뒤6, 디자인 기본 글리프)
#       완성본       = 16개(번호 4개 추가)
#     → 두 값 사이(14)를 임계로 둬, 빈템플릿은 통과·완성본만 베이크로 잡는다.
#     단, 1차 신호는 'Tj 라이브 텍스트 존재'(빈템플릿 0 / 완성본 1)라 거의 이걸로 갈린다.
_BAKED_WHITE_GLYPH_MAX = 14
#   - 번호영역 박스 배율: preset center 기준 ±(cap_height * 배율)을 번호영역으로 본다.
#     글리프가 cap 높이로 가로로 두 자리 퍼지므로 가로는 넉넉히, 세로는 글자높이만큼만.
_AREA_PAD_X = 2.0
_AREA_PAD_Y = 1.2


@router.get("/health")
def health() -> Dict[str, Any]:
    """서버 살아있음 신호. 화면 사이드바의 '서버 연결됨 · :8000' 표식이 이걸 부른다.

    반환: {status: "ok", port: 8000}
    """
    return {"status": "ok", "port": DEFAULT_PORT}


def _scan_one_pattern(folder: str) -> Dict[str, Any] | None:
    """패턴 폴더 1개를 읽어 화면용 요약 dict 로 만든다. 실패하면 None.

    화면(work.html / patterns.html)의 PATTERNS 배열 한 칸과 모양을 맞춘다:
      {id, name, sizes[], pieces, icon, glyph_source(bool), disabled_sizes[]}
    """
    preset_path = os.path.join(folder, "preset.json")
    if not os.path.exists(preset_path):
        return None  # preset.json 없는 폴더는 패턴이 아니므로 건너뛴다.

    # 엔진의 load_preset 으로 읽으면 필수 키 검증까지 같은 규약으로 처리된다.
    preset = load_preset(preset_path)

    # id: 폴더 이름(예: "농구_V넥_양면"). 화면이 패턴을 구분하는 키로 쓴다.
    pattern_id = os.path.basename(folder.rstrip(os.sep))

    # sizes: 활성 사이즈 이름만 뽑는다(disabled 는 아래에서 따로).
    sizes: List[str] = [s["name"] for s in preset.get("sizes", [])]

    # pieces: 조각 개수(앞/뒤/밴드 등).
    pieces = len(preset.get("pieces", []))

    # glyph_source: 배번 영역(앞/뒤)에 디자이너 글리프셋이 지정돼 있으면 True.
    # (둘 중 하나라도 glyph_source 키가 있으면 글리프셋 사용 패턴으로 본다.)
    front = preset.get("front_number_area", {}) or {}
    back = preset.get("back_number_area", {}) or {}
    glyph_source = bool(front.get("glyph_source") or back.get("glyph_source"))

    # disabled_sizes: 자산 결함 등으로 비활성된 사이즈 목록(이름+사유 그대로 전달).
    disabled_sizes = [
        {"name": d.get("name"), "reason": d.get("reason", "")}
        for d in preset.get("disabled_sizes", [])
    ]

    # icon: 화면 카드에 쓰는 Material Symbols 아이콘 이름(현재는 통일된 기본값).
    return {
        "id": pattern_id,
        "name": preset.get("preset_name", pattern_id),
        "sizes": sizes,
        "pieces": pieces,
        "icon": "checkroom",
        "glyph_source": glyph_source,
        "disabled_sizes": disabled_sizes,
    }


@router.get("/patterns")
def patterns() -> List[Dict[str, Any]]:
    """등록된 패턴 프리셋 목록. data/patterns/*/preset.json 을 스캔한다.

    반환: [{id, name, sizes[], pieces, icon, glyph_source, disabled_sizes[]}, ...]
    이름순 정렬로 돌려줘 화면 표시 순서가 매번 같도록 한다.
    """
    base = state.get_patterns_dir()
    result: List[Dict[str, Any]] = []
    if not os.path.isdir(base):
        return result  # 패턴 폴더 자체가 없으면 빈 목록(에러 아님).

    for name in sorted(os.listdir(base)):
        folder = os.path.join(base, name)
        if not os.path.isdir(folder):
            continue
        try:
            item = _scan_one_pattern(folder)
        except Exception:
            # 한 패턴이 깨져도 전체 목록이 죽으면 안 되므로 그 패턴만 건너뛴다.
            item = None
        if item:
            result.append(item)
    return result


@router.get("/settings")
def settings() -> Dict[str, Any]:
    """설정값. 설정 JSON 이 있으면 그 값을, 없으면 안전한 기본값을 돌려준다."""
    return state.read_settings()


# ── 주문서 파싱 엔드포인트 ────────────────────────────────────────────────
@router.post("/order/parse")
async def order_parse(file: UploadFile = File(...)) -> Dict[str, Any]:
    """업로드한 주문서 xlsx 를 엔진 parse_order 로 읽어 화면용 표 데이터로 돌려준다.

    반환: {rows:[{name,number,size,qty}], warnings:[...], total:int, empty_size:int}
      - total: 유효 행 수
      - empty_size: 사이즈가 비어 있는(파싱 불완전) 행 수 — 화면에서 빨간 표시용
    """
    # 업로드 파일을 디스크에 임시 저장(엔진은 경로를 받는다).
    saved_path = state.save_upload(file)

    warnings: List[str] = []
    try:
        rows = parse_order(saved_path, warnings)
    except Exception as e:
        # parse_order 는 보통 크래시하지 않지만, 만약을 위해 한국어 안내로 흘린다.
        return {
            "rows": [],
            "warnings": [f"⚠️ 주문서를 읽는 중 문제가 발생했습니다: {e}"],
            "total": 0,
            "empty_size": 0,
        }

    # 사이즈가 빈 행 수를 따로 센다(직원이 "이 사람 사이즈 비었네" 를 바로 보게).
    empty_size = sum(1 for r in rows if not (r.get("size") or "").strip())

    return {
        "rows": rows,
        "warnings": warnings,
        "total": len(rows),
        "empty_size": empty_size,
    }


# ── 디자인 점검 헬퍼 ──────────────────────────────────────────────────────
def _number_areas() -> List[Dict[str, Any]]:
    """V넥 preset 에서 앞/뒤 번호영역(center, cap_height)을 읽어 온다.

    왜 preset 에서 읽나: 번호영역 좌표를 코드에 박으면 디자인이 바뀔 때 어긋난다.
    preset 에 이미 정답 좌표가 있으니 그걸 단일 출처로 쓴다. 없으면 빈 리스트.
    """
    areas: List[Dict[str, Any]] = []
    preset_path = os.path.join(
        state.get_patterns_dir(), "농구_V넥_양면", "preset.json")
    if not os.path.exists(preset_path):
        return areas
    try:
        preset = load_preset(preset_path)
    except Exception:
        return areas
    for key in ("front_number_area", "back_number_area"):
        a = preset.get(key) or {}
        c = a.get("center")
        cap = a.get("cap_height")
        if c and cap:
            areas.append({"cx": float(c[0]), "cy": float(c[1]), "cap": float(cap)})
    return areas


def _count_white_glyphs_in_number_area(fills: list) -> int:
    """번호영역 안에 든 '흰색(0,0,0,0) 채움(글리프)' 개수를 센다.

    영역을 번호 중심±(cap*배율)로 좁히는 이유(중요):
      빈 템플릿에도 디자인상 흰색 글리프(로고 등)가 곳곳에 있다. 영역을 안 좁히면
      그것까지 세어 정상 빈템플릿을 '베이크'로 오판한다. 번호 자리만 보도록 좁히면
      정상 빈템플릿(번호 없음)과 완성본(번호 글리프 추가)이 또렷이 갈린다.
    """
    areas = _number_areas()
    if not areas:
        return 0
    count = 0
    for f in fills:
        if f.get("color") != (0.0, 0.0, 0.0, 0.0):
            continue  # 흰색(CMYK 0000) 채움만 번호 글리프 후보로 본다.
        b = f["bbox"]
        cx = (b[0] + b[2]) / 2.0
        cy = (b[1] + b[3]) / 2.0
        for a in areas:
            if (abs(cx - a["cx"]) <= a["cap"] * _AREA_PAD_X
                    and abs(cy - a["cy"]) <= a["cap"] * _AREA_PAD_Y):
                count += 1
                break  # 한 채움은 한 번만 센다(앞/뒤 영역 겹침 방지).
    return count


@router.post("/design/check")
async def design_check(file: UploadFile = File(...)) -> Dict[str, Any]:
    """업로드한 디자인(.ai/PDF)을 5케이스 우선순위로 점검한다.

    우선순위(앞에서 걸리면 거기서 판정 종료):
      ① 첫 바이트가 %!PS-Adobe  → fail "PDF 호환 형식이 아닙니다"
      ② %PDF 인데 본체 콘텐츠 < 10KB → fail "본체 누락(PDF 호환 저장 실패)"
      ④ 베이크(Tj 라이브 텍스트 존재 OR 번호영역 흰글리프 임계 초과) → warn "빈 본체를 올려주세요"(진행 허용)
      ③ 투명도(ca/CA<1 또는 SMask) → flatten 성공 시 pass(+flattened) / SMask 등으로 평탄화 불가 시 fail
      ⑤ 위 어디에도 안 걸리면 pass

    반환: {status:"pass"|"warn"|"fail", checks:[{name,ok,detail}], message, flattened:bool}
    """
    saved_path = state.save_upload(file)
    # design_token: 방금 저장한 업로드 파일을 '나중에 다시 찾기 위한 영수증' 이다.
    #   화면 JS 가 이 토큰을 들고 있다가 POST /api/jobs 호출 때 그대로 넘기면,
    #   서버가 이 토큰으로 업로드 폴더에서 그 파일을 다시 찾아 생성에 쓴다.
    #   (업로드 폴더 안 파일명만 토큰으로 쓴다 — 폴더 밖 경로 접근은 막는다.)
    design_token = os.path.basename(saved_path)
    checks: List[Dict[str, Any]] = []

    def result(status: str, message: str, flattened: bool = False) -> Dict[str, Any]:
        return {"status": status, "checks": checks, "message": message,
                "flattened": flattened, "design_token": design_token}

    # ── ① 첫 바이트 검사: PostScript(%!PS) 는 PDF 호환이 아님 ──────────────
    try:
        with open(saved_path, "rb") as f:
            head = f.read(20)
    except Exception as e:
        checks.append({"name": "파일 읽기", "ok": False, "detail": str(e)})
        return result("fail", f"업로드 파일을 읽지 못했습니다: {e}")

    if head.startswith(b"%!PS-Adobe"):
        checks.append({"name": "파일 형식", "ok": False,
                       "detail": "첫 바이트가 %!PS-Adobe (PostScript)"})
        return result(
            "fail",
            "PDF 호환 형식이 아닙니다. 일러스트레이터에서 'PDF 호환 파일 만들기'를 "
            "켜고 .ai 로 다시 저장해 주세요.")
    checks.append({"name": "파일 형식", "ok": True,
                   "detail": "PDF 호환(%PDF) 헤더 확인"})

    # 여기부터는 PDF 로 열어야 한다. 못 열면 형식 문제로 본다.
    try:
        pdf = pikepdf.open(saved_path)
    except Exception as e:
        checks.append({"name": "PDF 열기", "ok": False, "detail": str(e)})
        return result(
            "fail",
            "PDF 로 열 수 없습니다. PDF 호환으로 저장된 .ai 인지 확인해 주세요.")

    try:
        page = pdf.pages[0]

        # ── ② 본체 콘텐츠 크기: 너무 작으면 본체 누락(PDF 호환 저장 실패) ──
        body_bytes = 0
        contents = page.obj.get("/Contents")
        streams = contents if isinstance(contents, pikepdf.Array) else [contents]
        for s in streams:
            try:
                body_bytes += len(s.read_bytes())
            except Exception:
                pass

        if body_bytes < _BODY_MIN_BYTES:
            checks.append({"name": "본체 콘텐츠", "ok": False,
                           "detail": f"본체 {body_bytes:,}바이트 < {_BODY_MIN_BYTES:,} (누락 의심)"})
            return result(
                "fail",
                f"디자인 본체가 비어 있습니다(콘텐츠 {body_bytes:,}바이트). "
                "PDF 호환 저장이 제대로 안 된 파일입니다. 일러스트에서 "
                "'PDF 호환 파일 만들기'를 켜고 다시 저장해 주세요.")
        checks.append({"name": "본체 콘텐츠", "ok": True,
                       "detail": f"{body_bytes:,}바이트 (정상)"})

        # ── ④ 베이크 검사: 라이브 텍스트(Tj) OR 번호영역 흰글리프 임계초과 ──
        fills, texts = _collect_fills(page)
        live_text = len(texts)
        white_glyphs = _count_white_glyphs_in_number_area(fills)
        baked = (live_text > 0) or (white_glyphs > _BAKED_WHITE_GLYPH_MAX)
        detail_baked = (f"라이브 텍스트(Tj) {live_text}개 · "
                        f"번호영역 흰글리프 {white_glyphs}개 "
                        f"(임계 {_BAKED_WHITE_GLYPH_MAX})")
        if baked:
            checks.append({"name": "빈 본체 여부", "ok": False, "detail": detail_baked})
            return result(
                "warn",
                "이미 번호·이름이 들어간 완성본으로 보입니다. 가능하면 번호·이름이 "
                "없는 '빈 본체'를 올려주세요. (이대로도 진행은 가능합니다)")
        checks.append({"name": "빈 본체 여부", "ok": True, "detail": detail_baked})
    finally:
        pdf.close()

    # ── ③ 투명도 검사 + 평탄화 ──────────────────────────────────────────
    #   투명도가 있으면 EPS 등에서 래스터화 위험 → flatten_transparency 로 평탄화 시도.
    #   평탄화 후에도 잔여 투명도(SMask 등)가 남으면 자동 처리 불가 → fail.
    try:
        chk = pikepdf.open(saved_path)
    except Exception as e:
        checks.append({"name": "투명도 검사", "ok": False, "detail": str(e)})
        return result("fail", f"투명도 검사 중 파일을 다시 열지 못했습니다: {e}")
    try:
        trans = scan_transparency(chk)
    finally:
        chk.close()

    if not trans:
        # ── ⑤ 정상: 형식·본체·빈본체·투명도 모두 통과 ──
        checks.append({"name": "투명도", "ok": True, "detail": "투명도 없음"})
        return result("pass", "점검 통과 — 출력에 사용할 수 있는 정상 빈 본체입니다.")

    # 투명도 있음 → 평탄화 시도(임시 출력 파일로).
    tmp_out = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    try:
        info = flatten_transparency(saved_path, tmp_out)
        left = info.get("transparency_left") or []
        if left:
            # 평탄화 후에도 남음(SMask 등) → 자동 처리 불가.
            checks.append({"name": "투명도", "ok": False,
                           "detail": f"평탄화 후 잔여: {left}"})
            return result(
                "fail",
                "투명도를 자동으로 평탄화하지 못했습니다(SMask 등). 일러스트에서 "
                "원본을 평탄화(투명도 분할·병합)한 뒤 다시 올려주세요.")
        checks.append({"name": "투명도", "ok": True,
                       "detail": f"평탄화 완료(흔적 {len(trans)}개 처리)"})
        return result("pass",
                      "투명도를 자동 평탄화했습니다 — 출력에 사용할 수 있습니다.",
                      flattened=True)
    except Exception as e:
        checks.append({"name": "투명도", "ok": False, "detail": f"평탄화 실패: {e}"})
        return result(
            "fail",
            f"투명도 평탄화 중 문제가 발생했습니다: {e} 원본을 평탄화해 다시 올려주세요.")
    finally:
        # 임시 평탄화 결과 파일은 점검용일 뿐이라 정리한다.
        try:
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
        except Exception:
            pass


# ── 생성 작업(job) 엔드포인트 ─────────────────────────────────────────────
#   흐름(비유): 화면이 "생성 시작" 을 누르면 곧장 끝나길 기다리지 않는다.
#   주방(백그라운드 스레드)에 주문을 넣고 영수증(job_id)만 즉시 받아, 화면이
#   주기적으로 "다 됐나요?(progress)" 를 물어본다. 끝나면 결과(jobs/{id})를 읽어
#   검수 그리드를 그린다. 진행상태는 state 메모리 딕셔너리에 둔다.

def _resolve_design_path(token: Optional[str], explicit: Optional[str]) -> str:
    """디자인 파일 절대경로를 안전하게 해석한다.

    우선순위:
      1) design_token(업로드 영수증) — uploads 폴더 안의 그 파일.
      2) design(명시 경로) — 프로젝트 루트 기준 상대/절대경로(빈 본체 기본값 등).
    경로 조작 방지: 토큰은 '파일명' 만 받아 uploads 폴더 안에서만 찾는다.
    """
    if token:
        # 토큰에서 폴더 구분자를 떼어 파일명만 쓴다(uploads 밖 접근 차단).
        safe = os.path.basename(token)
        cand = os.path.join(state.UPLOADS_DIR, safe)
        if os.path.exists(cand):
            return cand
        raise FileNotFoundError(
            f"업로드한 디자인 파일을 찾지 못했습니다(만료되었을 수 있어요). "
            f"디자인을 다시 업로드해 주세요. (token={safe})")
    if explicit:
        # 절대경로면 그대로, 아니면 프로젝트 루트 기준으로 푼다.
        p = explicit if os.path.isabs(explicit) else os.path.join(
            state.PROJECT_ROOT, explicit)
        if os.path.exists(p):
            return p
        raise FileNotFoundError(f"디자인 파일을 찾지 못했습니다: {explicit}")
    raise ValueError("디자인이 지정되지 않았습니다(design_token 또는 design 필요).")


def _preset_path_for(pattern_id: str) -> str:
    """patternId(폴더명) → data/patterns/{id}/preset.json 절대경로."""
    safe = os.path.basename(pattern_id or "")
    path = os.path.join(state.get_patterns_dir(), safe, "preset.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"패턴을 찾지 못했습니다: {pattern_id}")
    return path


def _normalize_rows(rows: Any) -> List[dict]:
    """화면 표(rows) 를 run_job 이 먹는 [{name,number,size,qty}] 로 정리한다.

    화면에서 사용자가 직접 수정한 표를 신뢰원으로 쓴다(주문서 재파싱 아님).
    사이즈가 빈 행은 run_job 이 어차피 매칭 실패로 skip 하지만, 분모를 맞추려
    그대로 넘긴다(skip 사유가 화면에 보이게).
    """
    out: List[dict] = []
    for r in (rows or []):
        out.append({
            "name": (r.get("name") or "").strip(),
            "number": str(r.get("number") or "").strip(),
            "size": (r.get("size") or "").strip(),
            "qty": int(r.get("qty") or 1),
        })
    return out


def _run_job_thread(job_id: str, preset_path: str, design_path: str,
                    rows: List[dict], out_dir: str, out_format: str) -> None:
    """백그라운드 스레드 본체: run_job 을 돌리고 진행상태를 갱신한다.

    run_job 은 내부에서 한 번에 다 돌고 결과를 돌려주는 구조라(행별 콜백 훅이 없다),
    여기서는 '시작=running, 끝=done(진행 100%)' 로 상태를 전이한다. 화면 진행바는
    그 사이 폴링으로 자연스럽게 채워진다(완료 시 done=total 로 점프).
    실패하면 status=error + 한국어 사유를 남긴다(서버는 죽지 않는다).
    """
    try:
        result = run_job(
            preset=preset_path,
            design_pdf=design_path,
            order_rows=rows,
            out_dir=out_dir,
            split="per_player",
            make_preview=True,        # 검수 그리드용 미리보기 PNG 생성
            out_format=out_format,    # pdf | eps | both
        )
        produced = result.get("summary", {}).get("produced", 0)
        # 완료: 진행바를 가득 채우고(=total) done 상태로 전이.
        with state._JOBS_LOCK:
            j = state._JOBS.get(job_id)
            if j:
                j["done"] = j["total"]
                j["status"] = "done"
                j["out_dir"] = os.path.abspath(out_dir)
                j["produced"] = produced
    except Exception as e:
        # 생성 자체가 실패해도 서버는 살아 있어야 한다 → 상태만 error 로.
        tb = traceback.format_exc()
        state.update_job(job_id, status="error",
                         error=f"생성 중 문제가 발생했습니다: {e}",
                         out_dir=os.path.abspath(out_dir))
        # 서버 콘솔에는 자세한 추적을 남긴다(직원 화면엔 한국어 요약만).
        print(f"[job {job_id}] 실패:\n{tb}")


@router.post("/jobs")
async def create_job_endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """생성 작업을 백그라운드로 시작하고 job_id 를 즉시 돌려준다(비동기).

    요청 본문(JSON):
      {
        patternId   : 패턴 폴더명(예: "농구_V넥_양면") — preset.json 을 찾는다.
        design_token: 디자인 점검 때 받은 업로드 영수증(선택).
        design      : 또는 명시 디자인 경로(빈 본체 기본값 등, 선택).
        rows        : [{name,number,size,qty}] 화면 표(사용자 수정 반영).
        out_format  : "pdf" | "eps" | "both" (선택, 기본 preset/pdf).
      }
    반환: {job_id, total}
    """
    pattern_id = payload.get("patternId") or payload.get("pattern_id")
    rows = _normalize_rows(payload.get("rows"))
    out_format = (payload.get("out_format") or payload.get("format") or "").lower() or None

    # 입력 검증(차단). 친절한 한국어 사유로 막는다.
    if not pattern_id:
        return JSONResponse(status_code=400,
                            content={"error": "패턴을 선택해 주세요(patternId 누락)."})
    if not rows:
        return JSONResponse(status_code=400,
                            content={"error": "주문 행이 비어 있습니다. 주문서를 확인해 주세요."})

    try:
        preset_path = _preset_path_for(pattern_id)
        design_path = _resolve_design_path(
            payload.get("design_token"), payload.get("design"))
    except (FileNotFoundError, ValueError) as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    # out_format 미지정이면 설정 기본값을 따른다(설정 ↔ 화면 연동).
    if out_format is None:
        out_format = (state.read_settings().get("output_format") or "pdf").lower()

    # job 등록(진행바 분모=행 수) + 결과 폴더 결정.
    job_id = state.create_job(total=len(rows))
    # 결과 폴더: data/jobs/web_<날짜시각>_<job_id 앞6>/ (사람이 알아보기 쉽게).
    import time as _t
    stamp = _t.strftime("%y%m%d_%H%M%S")
    out_dir = os.path.join(state.get_jobs_dir(), f"web_{stamp}_{job_id[:6]}")
    os.makedirs(out_dir, exist_ok=True)
    state.update_job(job_id, out_dir=os.path.abspath(out_dir))

    # 백그라운드 스레드로 run_job 실행(daemon: 서버 종료 시 함께 정리).
    t = threading.Thread(
        target=_run_job_thread,
        args=(job_id, preset_path, design_path, rows, out_dir, out_format),
        daemon=True,
    )
    t.start()

    return {"job_id": job_id, "total": len(rows), "out_format": out_format}


@router.get("/jobs/{job_id}/progress")
def job_progress(job_id: str) -> Dict[str, Any]:
    """작업 진행상태(폴링용). running/done/error + 완료/전체.

    반환: {status, done, total, error}
    """
    j = state.get_job(job_id)
    if not j:
        return JSONResponse(status_code=404,
                            content={"error": "작업을 찾을 수 없습니다(서버 재시작 등). "
                                              "다시 생성해 주세요."})
    return {
        "status": j.get("status"),
        "done": j.get("done", 0),
        "total": j.get("total", 0),
        "error": j.get("error"),
    }


def _find_job_dir(job_id: str) -> Optional[str]:
    """job_id 로 결과 폴더 절대경로를 찾는다(메모리 우선 → 디스크 스캔 폴백).

    서버를 재시작하면 메모리(_JOBS)는 비지만 결과 폴더는 디스크에 남아 있다.
    그래서 메모리에 없으면 data/jobs/ 에서 폴더명에 job_id 앞6자리가 든 폴더를 찾는다.
    """
    j = state.get_job(job_id)
    if j and j.get("out_dir") and os.path.isdir(j["out_dir"]):
        return j["out_dir"]
    base = state.get_jobs_dir()
    if not os.path.isdir(base):
        return None
    needle = job_id[:6]
    for name in os.listdir(base):
        # web_<stamp>_<id6> 규칙으로 만든 폴더를 우선 매칭.
        if name.endswith("_" + needle) or needle in name:
            cand = os.path.join(base, name)
            if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "job.json")):
                return cand
    return None


def _load_job_json(job_dir: str) -> Dict[str, Any]:
    """job.json 을 UTF-8 로 읽는다(없으면 빈 dict)."""
    path = os.path.join(job_dir, "job.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _output_file_rel(job_dir: str, out: Dict[str, Any], kind: str) -> Optional[str]:
    """outputs 항목에서 kind("pdf"|"eps"|"preview") 의 상대경로를 구한다.

    구·신 경로 호환(핵심):
      - 신 구조: job.json 의 out["pdf"] = "output/pdf/XL_11_..pdf" 처럼 기록됨.
      - 구 구조: 기존 job(260620_…)은 "output/XL_11_..pdf" (output 직하).
    job.json 에 기록된 상대경로를 1순위로 쓰고, 그 파일이 실제로 없으면
    구 구조(output/ 직하)로 폴백해 찾는다.
    """
    rel = out.get(kind)
    if not rel:
        return None
    # eps/preview 는 리스트(single 모드)일 수 있다 — 여기선 per_player(문자열) 기준.
    if isinstance(rel, list):
        rel = rel[0] if rel else None
        if not rel:
            return None
    # 1순위: 기록된 상대경로 그대로.
    if os.path.exists(os.path.join(job_dir, rel)):
        return rel.replace("\\", "/")
    # 폴백: 파일명만 떼어 output/ 직하(구 구조)에서 찾는다.
    fname = os.path.basename(rel)
    legacy = os.path.join("output", fname)
    if os.path.exists(os.path.join(job_dir, legacy)):
        return legacy.replace("\\", "/")
    # 그래도 없으면 신 구조 하위(output/pdf|eps)에서 한 번 더.
    for sub in ("output/pdf", "output/eps", "preview"):
        cand = os.path.join(sub, fname)
        if os.path.exists(os.path.join(job_dir, cand)):
            return cand.replace("\\", "/")
    return None


@router.get("/jobs/{job_id}")
def job_result(job_id: str) -> Dict[str, Any]:
    """완료된 작업의 결과(job.json)를 화면 검수용으로 정리해 돌려준다.

    구·신 경로를 모두 처리해 outputs 의 pdf/eps/preview 상대경로를 '실제 존재하는'
    경로로 보정한다. 화면은 preview 경로로 /preview/{file} 를 부른다.

    반환: {summary, outputs:[{size,name,number,pdf,eps,preview,checks,checks_eps,
           verify_pass}], skip, format_summary, ...}
    """
    job_dir = _find_job_dir(job_id)
    if not job_dir:
        return JSONResponse(status_code=404,
                            content={"error": "작업 결과를 찾을 수 없습니다."})
    data = _load_job_json(job_dir)
    summary = data.get("summary", {}) or {}
    raw_outputs = data.get("outputs", []) or []

    outputs: List[Dict[str, Any]] = []
    for o in raw_outputs:
        pdf_rel = _output_file_rel(job_dir, o, "pdf")
        eps_rel = _output_file_rel(job_dir, o, "eps")
        prev_rel = _output_file_rel(job_dir, o, "preview")
        verify_pass = bool(o.get("verify_pass"))
        # EPS 검증도 같이 봐(checks_eps), 둘 다 통과해야 PASS 로 본다.
        ce = o.get("checks_eps")
        eps_ok = True
        if isinstance(ce, list) and ce:
            eps_ok = all(c.get("ok", True) for c in ce)
        status = "pass" if (verify_pass and eps_ok) else "warn"
        outputs.append({
            "size": o.get("size"),
            "name": o.get("name"),
            "number": o.get("number"),
            "pdf": pdf_rel,
            "eps": eps_rel,
            # preview 파일명만 추려 화면이 /preview/{file} 로 부르게 한다.
            "preview": (os.path.basename(prev_rel) if prev_rel else None),
            "checks": o.get("checks", []),
            "checks_eps": ce,
            "verify_pass": verify_pass,
            "status": status,
        })

    # 건너뜀(skip): summary.skipped(행 단위 사유) + disabled_sizes(결함 차단).
    return {
        "job_id": job_id,
        "summary": summary,
        "outputs": outputs,
        "skip": summary.get("skipped", []),
        "disabled_sizes": summary.get("disabled_sizes", {}),
        "format": summary.get("format"),
        "format_summary": summary.get("format_summary"),
        "verify": {"pass": summary.get("verify_pass", 0),
                   "fail": summary.get("verify_fail", 0),
                   "produced": summary.get("produced", 0)},
    }


def _safe_preview_path(job_dir: str, fname: str) -> Optional[str]:
    """preview 폴더 안에서 파일명을 안전하게 찾는다(폴더 밖 접근 차단)."""
    safe = os.path.basename(fname)  # 경로 구분자 제거(상위 폴더 탈출 방지)
    cand = os.path.join(job_dir, "preview", safe)
    if os.path.exists(cand):
        return cand
    return None


@router.get("/jobs/{job_id}/preview/{file}")
def job_preview(job_id: str, file: str):
    """검수 그리드용 미리보기 PNG 를 서빙한다(preview/<file>)."""
    job_dir = _find_job_dir(job_id)
    if not job_dir:
        return JSONResponse(status_code=404, content={"error": "작업을 찾을 수 없습니다."})
    path = _safe_preview_path(job_dir, file)
    if not path:
        return JSONResponse(status_code=404,
                            content={"error": "미리보기 이미지를 찾을 수 없습니다."})
    return FileResponse(path, media_type="image/png")


def _collect_zip_files(job_dir: str, data: Dict[str, Any],
                       fmt: str) -> List[tuple]:
    """ZIP 에 담을 (실제경로, ZIP내경로) 쌍 목록을 만든다(구·신 경로 폴백).

    fmt:
      - "pdf"  : PDF 만, ZIP 루트에 평평하게.
      - "eps"  : EPS 만, ZIP 루트에 평평하게.
      - "both" : PDF 는 pdf/ 하위, EPS 는 eps/ 하위로 분리.
    """
    pairs: List[tuple] = []
    outputs = data.get("outputs", []) or []
    want_pdf = fmt in ("pdf", "both")
    want_eps = fmt in ("eps", "both")
    for o in outputs:
        if want_pdf:
            rel = _output_file_rel(job_dir, o, "pdf")
            if rel:
                src = os.path.join(job_dir, rel)
                arc = (f"pdf/{os.path.basename(rel)}" if fmt == "both"
                       else os.path.basename(rel))
                pairs.append((src, arc))
        if want_eps:
            rel = _output_file_rel(job_dir, o, "eps")
            if rel:
                src = os.path.join(job_dir, rel)
                arc = (f"eps/{os.path.basename(rel)}" if fmt == "both"
                       else os.path.basename(rel))
                pairs.append((src, arc))
    return pairs


@router.get("/jobs/{job_id}/zip")
def job_zip(job_id: str, format: str = "pdf"):
    """선택한 형식의 출력 파일들을 ZIP 으로 묶어 내려준다.

    format=pdf|eps|both. both 면 ZIP 안에서 pdf/ · eps/ 하위폴더로 분리한다.
    구·신 경로를 모두 폴백 처리한다(기존 job 폴더도 동작).
    """
    fmt = (format or "pdf").lower()
    if fmt not in ("pdf", "eps", "both"):
        return JSONResponse(status_code=400,
                            content={"error": "형식은 pdf|eps|both 여야 합니다."})
    job_dir = _find_job_dir(job_id)
    if not job_dir:
        return JSONResponse(status_code=404, content={"error": "작업을 찾을 수 없습니다."})
    data = _load_job_json(job_dir)
    pairs = _collect_zip_files(job_dir, data, fmt)
    if not pairs:
        return JSONResponse(
            status_code=404,
            content={"error": f"내려받을 {fmt.upper()} 파일이 없습니다. "
                              "해당 형식으로 생성되었는지 확인해 주세요."})

    # 메모리 버퍼에 ZIP 을 만든 뒤 스트리밍으로 내려준다(중간 파일 없음).
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in pairs:
            zf.write(src, arc)
    buf.seek(0)
    folder_name = os.path.basename(os.path.normpath(job_dir))
    zip_name = f"{folder_name}_{fmt}.zip"
    # Content-Disposition 헤더는 latin-1 만 허용한다(HTTP 규약). 폴더명에 한글이
    # 들어가면 latin-1 인코딩이 깨지므로:
    #   - filename   : ASCII 안전 이름(비ASCII는 '_' 치환)으로 폴백.
    #   - filename*  : RFC 5987 UTF-8 퍼센트 인코딩(브라우저가 한글 원본명 복원).
    from urllib.parse import quote as _q
    ascii_name = "".join(c if ord(c) < 128 else "_" for c in zip_name)
    disp = (f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{_q(zip_name)}")
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": disp})
