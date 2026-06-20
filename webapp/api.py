# -*- coding: utf-8 -*-
"""/api 엔드포인트 핸들러(1단계: health · patterns · settings 읽기).

각 핸들러는 '엔진 호출을 감싸는 얇은 래퍼' 다. 비즈니스 로직(합성·검증)은
engine/ 에 있고, 여기서는 그걸 호출해 화면이 먹기 좋은 JSON 으로 바꿔 줄 뿐이다.

설계 제약:
  - 엔진 공개 API(load_preset 등)는 '호출' 만 한다. 수정 금지.
  - 에러는 한국어로 "원인 + 다음 행동" 을 함께.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List

from fastapi import APIRouter, UploadFile, File

from . import state
from .state import DEFAULT_PORT

# 엔진 공개 API 는 import 만 한다(수정 금지). preset.json 로드/검증을 재사용한다.
from engine.grade import load_preset
# 주문서 파싱·투명도 평탄화/스캔·채움수집 헬퍼도 '호출' 만 한다(엔진 무수정).
from engine.order import parse_order
from engine.flatten import flatten_transparency
from engine.verify import scan_transparency
from engine.reference import _collect_fills

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
    checks: List[Dict[str, Any]] = []

    def result(status: str, message: str, flattened: bool = False) -> Dict[str, Any]:
        return {"status": status, "checks": checks, "message": message,
                "flattened": flattened}

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
