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

from fastapi import APIRouter, UploadFile, File, Body, Form, Depends
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse

from . import state
from . import gdrive  # Google Drive 연동(서비스계정 읽기전용). 미설정이면 이 기능만 비활성.
from .state import DEFAULT_PORT
# 관리자 전용 게이트(Dependency). 패턴 등록·설정 저장처럼 '쓰기' 작업에만 건다.
# (로컬 무인증이면 admin_required 도 통과 — 회귀 0. 배포는 role=='admin' 만.)
from .auth import admin_required

# 엔진 공개 API 는 import 만 한다(수정 금지). preset.json 로드/검증을 재사용한다.
from engine.grade import load_preset
# 주문서 파싱·투명도 평탄화/스캔·채움수집 헬퍼도 '호출' 만 한다(엔진 무수정).
from engine.order import parse_order
from engine.flatten import flatten_transparency
from engine.verify import scan_transparency
from engine.reference import _collect_fills, build_area_preset
# 생성 본체. run_job 은 '호출' 만 한다(시그니처·동작 무수정).
from engine.job import run_job
# 패턴 등록(2단계 핵심)에서 호출만 하는 엔진 API 들(전부 무수정).
from engine.svg_normalize import normalize_svg, check_size_monotonicity
from engine.number_glyphs import extract_number_glyphs, save_glyphset_json

# .ai → path SVG 추출 보조 스크립트(scripts/, engine 코어 아님). 함수만 호출.
import importlib.util as _ilu

import json

import pikepdf

# /api 아래로 묶일 라우터. main.py 가 이 router 를 앱에 붙인다.
# ⚠️ 인증(require_auth)은 main.py 가 이 router 를 붙일 때 전역으로 건다.
#    단, 헬스체크(/api/health)만은 무인증이어야 한다(아래 public_router 참고).
#    이유: Render 의 healthCheckPath(/api/health)는 로그인 토큰 없이 호출되므로,
#    여기에 인증을 걸면 배포가 '부팅 실패' 로 막힌다.
router = APIRouter(prefix="/api")

# 무인증 공개 라우터(헬스체크 전용). main.py 가 인증 dependency 없이 따로 붙인다.
public_router = APIRouter(prefix="/api")

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


# ⚠️ health 만 public_router(무인증)에 둔다 — Render healthCheck 가 토큰 없이 부른다.
@public_router.get("/health")
def health() -> Dict[str, Any]:
    """서버 살아있음 신호. 화면 사이드바의 '서버 연결됨 · :8000' 표식이 이걸 부른다.

    무인증 공개 엔드포인트(인증 켜져 있어도 토큰 없이 통과) — 배포 헬스체크 호환.
    반환: {status: "ok", port: 8000}
    """
    return {"status": "ok", "port": DEFAULT_PORT}


@public_router.get("/public-config")
def public_config() -> Dict[str, Any]:
    """프런트(login.html)가 런타임에 읽는 '공개 설정'.

    왜 엔드포인트인가(비유): 빌드 단계가 없어 HTML 에 키를 직접 박기 곤란하다.
    그래서 로그인 화면이 켜질 때 서버에 "공개키 뭐예요?" 하고 물어보게 한다.

    ⚠️ 여기서 내보내는 값은 '공개해도 되는 것만' 이다:
       · auth_required : 인증이 켜져 있는지(꺼져 있으면 로그인 없이 바로 진입).
       · supabase_url  : Supabase 프로젝트 URL(공개).
       · supabase_publishable_key : Supabase 공개키(프런트 노출용으로 설계된 키).
    SUPABASE_SECRET_KEY 같은 '비밀키' 는 절대 내보내지 않는다(응답에 키 이름조차 없음).
    """
    from .auth import auth_required
    return {
        "auth_required": auth_required(),
        "supabase_url": os.environ.get("SUPABASE_URL", ""),
        "supabase_publishable_key": os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
    }


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


@router.put("/settings", dependencies=[Depends(admin_required)])
def update_settings(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """설정을 '머지' 방식으로 저장한다(부분 갱신 → 전체 반환).

    화면(settings.html)이 바뀐 값만 보내도, 나머지 값은 보존된다(state.write_settings
    가 기존 값 위에 덮어쓰기). 저장 직후의 전체 설정을 돌려줘 화면이 곧장 반영한다.

    반환: 저장된 전체 설정 dict.
    """
    try:
        saved = state.write_settings(payload or {})
    except Exception as e:
        # 디스크 쓰기 실패 등(권한·디스크 가득) — 한국어로 원인+다음 행동 안내.
        return JSONResponse(
            status_code=500,
            content={"error": f"설정을 저장하지 못했습니다: {e} "
                              "data 폴더 쓰기 권한·디스크 공간을 확인해 주세요."})
    return saved


# ── 작업 기록(jobs) 목록 ─────────────────────────────────────────────────
def _job_summary(job_dir: str) -> Dict[str, Any] | None:
    """작업 폴더 1개의 job.json 을 읽어 기록 목록용 요약 dict 로 만든다(실패 시 None).

    화면(history.html)의 JOBS 한 줄과 모양을 맞춘다:
      {id, date, name, pattern, count, status}

    구·신 경로/스키마 모두 방어적으로 읽는다(키가 없어도 안 죽게):
      - id      : 폴더명(예: web_260620_120000_ab12cd / 260620_연세대V넥_빈본체).
      - date    : job.json 의 생성시각(created/finished) 또는 폴더 수정시각.
      - name    : summary.order_name 또는 주문서 파일명 → 없으면 폴더명.
      - pattern : summary.preset_name(preset 이름) → 없으면 "-".
      - count   : produced(생성 수) 또는 outputs 길이.
      - status  : verify_fail 0 이면 done, 1개라도 있으면 warn.
    """
    job_json = os.path.join(job_dir, "job.json")
    if not os.path.exists(job_json):
        return None  # job.json 없는 폴더는 작업 결과가 아니므로 건너뛴다.

    folder = os.path.basename(os.path.normpath(job_dir))
    data: Dict[str, Any] = {}
    try:
        with open(job_json, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        # job.json 이 깨졌어도 목록 전체가 죽으면 안 되므로, 폴더명만으로 최소 표기.
        data = {}

    summary = data.get("summary", {}) or {}
    outputs = data.get("outputs", []) or []

    # 날짜: job.json 기록 우선 → 없으면 폴더 수정시각으로 폴백.
    date_raw = (summary.get("created") or summary.get("finished")
                or data.get("created_at") or data.get("created"))
    if not date_raw:
        try:
            import time as _t
            date_raw = _t.strftime(
                "%Y-%m-%d %H:%M", _t.localtime(os.path.getmtime(job_dir)))
        except Exception:
            date_raw = ""

    # 주문명: 여러 후보 키를 차례로 본다(스키마 차이 흡수).
    name = (summary.get("order_name") or summary.get("order")
            or data.get("order_name")
            or os.path.basename(str(summary.get("order_file") or "")) or "")
    if not name:
        name = folder  # 끝까지 없으면 폴더명으로 표시(빈칸 방지).

    pattern = (summary.get("preset_name") or summary.get("pattern")
               or data.get("preset_name") or "-")

    # 파일 수: produced(생성 수) → 없으면 outputs 길이.
    count = summary.get("produced")
    if count is None:
        count = len(outputs)

    # 상태: verify 실패가 1건이라도 있으면 '확인 필요(warn)', 없으면 '완료(done)'.
    fail = summary.get("verify_fail", 0) or 0
    status = "warn" if fail else "done"

    return {
        "id": folder,
        "date": str(date_raw),
        "name": str(name),
        "pattern": str(pattern),
        "count": int(count or 0),
        "status": status,
    }


@router.get("/jobs")
def list_jobs() -> List[Dict[str, Any]]:
    """완료된 작업 기록 목록. data/jobs/*/job.json 을 스캔한다.

    반환: [{id, date, name, pattern, count, status}, ...]
      최신 폴더가 위로 오도록 폴더 수정시각 내림차순 정렬.
    """
    base = state.get_jobs_dir()
    rows: List[Dict[str, Any]] = []
    if not os.path.isdir(base):
        return rows  # jobs 폴더 자체가 없으면 빈 목록(에러 아님).

    for name in os.listdir(base):
        job_dir = os.path.join(base, name)
        if not os.path.isdir(job_dir):
            continue
        try:
            item = _job_summary(job_dir)
        except Exception:
            # 한 작업이 깨져도 전체 목록이 죽지 않게 그 작업만 건너뛴다.
            item = None
        if item:
            rows.append(item)

    # 최신순 정렬(폴더 수정시각 내림차순). 시각 못 읽으면 맨 뒤로.
    def _mtime(r: Dict[str, Any]) -> float:
        try:
            return os.path.getmtime(os.path.join(base, r["id"]))
        except Exception:
            return 0.0
    rows.sort(key=_mtime, reverse=True)
    return rows


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


# ════════════════════════════════════════════════════════════════════════════
#  패턴 등록(2단계 — 핵심)  POST /api/patterns
# ════════════════════════════════════════════════════════════════════════════
#  화면(patterns.html)이 FormData 로 보내는 것을 받아 data/patterns/{이름}/ 폴더와
#  preset.json 을 만든다. 비유로 보면 '레시피 카드' 한 장을 정식 등록하는 과정이다.
#
#  처리 순서(부분 실패해도 죽지 않고 경고로 흘린다 — 직원이 보충하게):
#    1) 사이즈별 패턴(size_<사이즈>): .ai → ai_to_path_svg → normalize_svg → <사이즈>.svg
#                                     / .svg 는 그대로 복사. 조각수 검증.
#       2개 이상이면 check_size_monotonicity 로 자산결함(좌표동일) → disabled_sizes.
#    2) 글리프셋(glyphset, 선택): extract_number_glyphs → number_glyphs.json.
#       없으면 폰트 폴백(glyph_source 생략).
#    3) 완성본(reference, 선택): build_area_preset → front/back number_area + back_name_area.
#    4) preset.json 생성(design/sizes/pieces/area/glyph_source/disabled_sizes).

# ── 사이즈 정렬 순서(작은→큰). 단조성(높이 증가) 검사와 화면 표기에 쓴다. ──
_SIZE_ORDER = ["5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL",
               "2XL", "3XL", "4XL", "5XL"]

# ai_to_path_svg.py 를 한 번만 동적 로드해 캐시한다(scripts/ 는 패키지가 아니라서
# import 가 안 되므로 파일 경로로 모듈을 직접 읽어 함수만 빌려 쓴다 — engine 무관).
_AI_TO_PATH_MOD = None


def _ai_to_path_svg(in_path: str, out_path: str) -> dict:
    """scripts/ai_to_path_svg.py 의 ai_to_path_svg() 를 동적 로드해 호출한다.

    왜 동적 로드인가(비유): 그 파일은 '엔진 코어'가 아니라 scripts/ 의 독립 도구라
    패키지 import 경로가 없다. 그래서 파일 주소로 직접 펼쳐 함수만 빌려 온다.
    원본 파일은 절대 수정하지 않는다(호출만).
    """
    global _AI_TO_PATH_MOD
    if _AI_TO_PATH_MOD is None:
        script_path = os.path.join(
            state.PROJECT_ROOT, "scripts", "ai_to_path_svg.py")
        spec = _ilu.spec_from_file_location("ai_to_path_svg", script_path)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _AI_TO_PATH_MOD = mod
    return _AI_TO_PATH_MOD.ai_to_path_svg(in_path, out_path)


def _fix_mojibake(s: Optional[str]) -> str:
    """multipart 텍스트 필드의 한글 깨짐(mojibake)을 복원한다.

    왜 필요한가(원인):
      starlette(1.3.x) multipart 파서는 파트에 charset 이 안 붙어 있으면 텍스트
      필드를 'latin-1'로 디코딩한다(self._charset="" → LookupError → latin-1 폴백).
      브라우저 FormData 는 charset 을 안 붙이므로, UTF-8 한글이 latin-1 로 잘못
      읽혀 '웹앱' → 'ì›¹ì•±' 같은 깨짐이 생긴다.

    복원(비유): 잘못된 안경(latin-1)으로 읽은 글자를 원래 바이트로 되돌린 뒤
      올바른 안경(utf-8)으로 다시 읽는다. 이미 정상(ASCII 등)이면 그대로 둔다.
    """
    if not s:
        return s or ""
    # 모두 ASCII 면 깨질 일이 없다(영문 사이즈명 등) → 그대로.
    if all(ord(c) < 128 for c in s):
        return s
    # latin-1 폴백으로 디코딩된 문자열을 '원래 바이트'로 되돌린다.
    try:
        raw = s.encode("latin-1")
    except UnicodeEncodeError:
        # latin-1 범위를 벗어남 = 이미 정상 유니코드(깨진 게 아님) → 그대로.
        return s
    # 원래 바이트를 올바른 인코딩으로 다시 읽는다.
    #   1순위 utf-8(브라우저 FormData 표준), 2순위 cp949(일부 한글 윈도 클라이언트).
    for codec in ("utf-8", "cp949"):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            continue
    return s  # 어느 것으로도 못 읽으면 원본 유지(파괴 금지).


def _safe_pattern_dirname(name: str) -> str:
    """패턴 이름을 폴더명으로 안전하게 다듬는다(경로조작·금지문자 제거).

    한글·영문·숫자·언더스코어는 그대로 두고, 경로 구분자나 윈도 금지문자만 '_'로.
    공백은 '_'로 모아 폴더명을 깔끔하게 한다.
    """
    raw = (name or "").strip()
    # 폴더 탈출·금지문자 차단(\\ / : * ? " < > |) + 제어문자.
    bad = set('\\/:*?"<>|')
    cleaned = "".join("_" if (c in bad or ord(c) < 32) else c for c in raw)
    cleaned = "_".join(cleaned.split())  # 연속 공백 → 단일 '_'
    # 양끝의 점(.)만 제거(경로 탈출 ".."·"." 방지). 선행 언더스코어(_test_*)는
    # 의미가 있으니 보존한다(테스트 패턴 정리·식별에 쓰임).
    cleaned = cleaned.strip(".")
    return cleaned or "패턴"


def _build_pieces(svg_index_count: int, page_w: float, page_h: float,
                  warnings: List[str]) -> List[Dict[str, Any]]:
    """조각 개수만큼 pieces 항목을 만든다(svg_index 매핑 + design_region 추정).

    왜 추정값인가(중요·솔직):
      디자인↔조각 영역(design_region_pt)은 본래 '완성본 자동추출' 대상이 아니라
      디자이너가 매핑해 주는 값이다(화면 B단계). API 단독 등록에서는 그 값을 알 수
      없으므로, 일단 페이지를 조각 수로 세로 균등분할한 '추정 영역'을 넣고 경고를
      남긴다. 직원이 preset.json 에서 design_region_pt 를 보정하면 된다.
      (조각 분류·svg_index 자체는 정확하다 — 추정은 design_region 좌표뿐.)
    """
    pieces: List[Dict[str, Any]] = []
    # 조각 id/이름: 통념상 0=앞판, 1=뒤판, 2=밴드, 그 외는 piece_N.
    default_names = [("front", "앞판"), ("back", "뒤판"), ("band", "넥밴드")]
    n = max(1, svg_index_count)
    band = page_h / n  # 세로 균등분할 높이(추정용)
    for i in range(n):
        if i < len(default_names):
            pid, pname = default_names[i]
        else:
            pid, pname = (f"piece_{i}", f"조각{i}")
        # 위에서부터 i번째 띠를 추정 영역으로(좌하단 원점 pt 기준).
        y1 = round(page_h - band * i, 2)
        y0 = round(page_h - band * (i + 1), 2)
        pieces.append({
            "id": pid,
            "name": pname,
            "svg_index": i,
            "design_region_pt": [0.0, y0, round(page_w, 2), y1],
        })
    warnings.append(
        "🟡 디자인↔조각 영역(design_region_pt)은 페이지 균등분할로 추정해 넣었습니다. "
        "정확한 합성을 위해 preset.json 의 design_region_pt 를 보정해 주세요.")
    return pieces


@router.post("/patterns", dependencies=[Depends(admin_required)])
async def create_pattern(
    name: str = Form(...),
    base_size: Optional[str] = Form(None),
    glyph_artbox: Optional[str] = Form(None),
    glyph_order: Optional[str] = Form(None),
    glyphset: Optional[UploadFile] = File(None),
    reference: Optional[UploadFile] = File(None),
    files: List[UploadFile] = File(default=[]),
) -> Dict[str, Any]:
    """패턴 1개를 등록한다(폴더 + preset.json 생성). 핵심 2단계 엔드포인트.

    FormData 필드:
      name        : 패턴 이름(폴더명·preset_name).
      base_size   : 기준 사이즈(없으면 업로드된 것 중 XL→첫 사이즈 순으로 추정).
      files       : 사이즈별 패턴 파일들. 각 파일의 filename 앞에 "<사이즈>." 또는
                    "<사이즈>_" 가 붙어 있으면 그 사이즈로 인식한다(예: "XL.ai",
                    "M.svg", "2XL_..ai"). 화면이 size_<사이즈> 슬롯으로 모아 보낸다.
      glyphset    : (선택) 번호 0~9 아웃라인 글리프셋 소스(.ai/.pdf).
      reference   : (선택) 번호·이름 박힌 완성본 1장(.ai/.pdf) — area 자동추출.
      glyph_artbox: (선택) "x0,y0,x1,y1" 글리프 추출영역(미지정 시 엔진 기본값).
      glyph_order : (선택) 글리프 정렬 대응 문자열(미지정 시 "1234567890").

    반환: {ok, pattern_id, preset_path, sizes, pieces, glyph_source,
           disabled_sizes, warnings, area}
    """
    warnings: List[str] = []

    # multipart 텍스트 필드의 한글 깨짐(latin-1 폴백)을 먼저 복원한다.
    name = _fix_mojibake(name)
    base_size = _fix_mojibake(base_size) if base_size else base_size
    glyph_order = _fix_mojibake(glyph_order) if glyph_order else glyph_order

    # ── 0) 폴더 준비(이름 정리 + 중복 차단) ──────────────────────────────
    pattern_id = _safe_pattern_dirname(name)
    pattern_dir = os.path.join(state.get_patterns_dir(), pattern_id)
    if os.path.exists(pattern_dir):
        return JSONResponse(
            status_code=409,
            content={"error": f"이미 같은 이름의 패턴이 있습니다: {pattern_id}. "
                              "다른 이름을 쓰거나 기존 패턴을 먼저 정리해 주세요."})

    # 사이즈별 파일이 하나도 없으면 등록할 게 없다(차단).
    size_files = [f for f in (files or []) if f and f.filename]
    if not size_files:
        return JSONResponse(
            status_code=400,
            content={"error": "사이즈별 패턴 파일이 없습니다. 최소 한 사이즈 이상 "
                              "올려주세요(.ai 또는 .svg)."})

    os.makedirs(pattern_dir, exist_ok=True)

    # ── 1) 사이즈별 패턴: .ai → path SVG → polyline SVG / .svg 는 그대로 ──
    #   _tmp_path/ 에 path SVG 중간산출을 떨어뜨렸다가 정리한다.
    tmp_path_dir = os.path.join(pattern_dir, "_tmp_path")
    os.makedirs(tmp_path_dir, exist_ok=True)

    sizes_meta: List[Dict[str, Any]] = []  # preset sizes 용 [{name,pattern_file,scale}]
    converted_map: Dict[str, str] = {}      # {사이즈명: 출력 svg 경로} — 단조성 검사용
    piece_counts: Dict[str, int] = {}       # {사이즈명: 조각수} — 일치 검증용
    page_dims: Optional[List[float]] = None  # 첫 .ai 변환에서 viewBox(가로/세로) 회수

    for up in size_files:
        # 파일명에서 사이즈 토큰을 뽑는다("XL.ai"·"2XL_무엇.svg" → "XL"·"2XL").
        # 한글 파일명도 mojibake 복원(혹시 한글이 섞여도 안전하게).
        base = os.path.basename(_fix_mojibake(up.filename) or "")
        stem = os.path.splitext(base)[0]
        ext = os.path.splitext(base)[1].lower()
        # 구분자(., _, 공백) 앞 토큰을 사이즈로 본다.
        token = stem.replace(" ", "_").split("_")[0].split(".")[0]
        size_name = token.upper() if token else stem.upper()

        out_svg = os.path.join(pattern_dir, f"{size_name}.svg")
        try:
            saved = state.save_upload(up)  # 업로드를 디스크로(엔진은 경로를 먹음)
            if ext == ".svg":
                # 이미 polyline SVG 라면 그대로 패턴 폴더로 복사.
                import shutil as _sh
                _sh.copyfile(saved, out_svg)
                rep = {"pieces_written": None}  # 조각수 미상(직접 검증 생략)
            else:
                # .ai/.pdf → ① path SVG(tmp) → ② polyline SVG(out_svg).
                tmp_svg = os.path.join(tmp_path_dir, f"{size_name}.svg")
                a = _ai_to_path_svg(saved, tmp_svg)
                # 첫 변환에서 페이지 치수(viewBox 가로·세로)를 회수한다(pieces 추정용).
                if page_dims is None and a.get("viewBox"):
                    try:
                        vb = [float(x) for x in str(a["viewBox"]).split()]
                        page_dims = [vb[2], vb[3]]  # [w, h]
                    except Exception:
                        pass
                rep = normalize_svg(tmp_svg, out_svg)
            # 조각수 기록(검증용).
            pc = rep.get("pieces_written")
            if pc is not None:
                piece_counts[size_name] = pc
            converted_map[size_name] = out_svg
            sizes_meta.append({"name": size_name,
                               "pattern_file": f"{size_name}.svg", "scale": 1.0})
            # normalize 경고가 있으면 사이즈명을 붙여 모은다.
            for w in (rep.get("warnings") or []):
                warnings.append(f"[{size_name}] {w}")
        except Exception as e:
            warnings.append(
                f"🔴 [{size_name}] 사이즈 변환 실패(이 사이즈는 제외): {e}")

    # 변환에 성공한 사이즈가 하나도 없으면 등록 실패(폴더 정리 후 에러).
    if not sizes_meta:
        _cleanup_dir(tmp_path_dir)
        return JSONResponse(
            status_code=400,
            content={"error": "모든 사이즈 변환에 실패했습니다. 파일이 PDF 호환 .ai "
                              "또는 polyline SVG 인지 확인해 주세요.",
                     "warnings": warnings})

    # 사이즈를 표준 순서로 정렬(작은→큰). 목록·단조성 검사 일관성.
    def _size_key(m: Dict[str, Any]) -> int:
        try:
            return _SIZE_ORDER.index(m["name"])
        except ValueError:
            return len(_SIZE_ORDER)  # 모르는 사이즈는 맨 뒤로
    sizes_meta.sort(key=_size_key)
    order = [m["name"] for m in sizes_meta]

    # 조각수 일관성 점검: 사이즈마다 조각수가 다르면 경고(자산 의심).
    distinct_pc = set(piece_counts.values())
    if len(distinct_pc) > 1:
        warnings.append(
            f"🟡 사이즈별 조각 수가 다릅니다: {piece_counts}. "
            "보조선 누락/추가 의심 — 결과를 확인해 주세요.")
    # 기준 조각수(가장 흔한 값) — pieces 생성에 쓴다.
    if piece_counts:
        piece_n = max(set(piece_counts.values()),
                      key=lambda v: list(piece_counts.values()).count(v))
    else:
        piece_n = 3  # SVG 직접 업로드 등으로 조각수 미상 → 앞/뒤/밴드 가정.
        warnings.append("🟡 조각 수를 확정하지 못해 3조각(앞/뒤/밴드)으로 가정했습니다.")

    # ── 1-b) 사이즈 단조성(자산결함) 검사 → disabled_sizes 산출 ───────────
    disabled_sizes: List[Dict[str, Any]] = []
    if len(converted_map) >= 2:
        try:
            guard = check_size_monotonicity(converted_map, size_order=order)
            for w in (guard.get("warnings") or []):
                warnings.append(w)
            # 좌표 100% 동일한 쌍이 있으면, '둘 중 더 큰 사이즈'를 비활성한다
            # (작은 쪽을 살리고 결함 복붙본을 차단 — 이슈3와 같은 안전 정책).
            seen_disabled = set()
            for (a_sz, b_sz) in (guard.get("duplicates") or []):
                bigger = a_sz if _size_key({"name": a_sz}) > _size_key({"name": b_sz}) else b_sz
                if bigger not in seen_disabled:
                    seen_disabled.add(bigger)
                    disabled_sizes.append({
                        "name": bigger,
                        "reason": f"{a_sz}·{b_sz} 좌표 100% 동일(자산 복붙 결함) — 재확보 필요"})
        except Exception as e:
            warnings.append(f"🟡 사이즈 단조성 검사 건너뜀: {e}")

    # 비활성 사이즈는 sizes 에서 빼서 별도 섹션으로(build_layouts 가 sizes 만 순회).
    disabled_names = {d["name"] for d in disabled_sizes}
    active_sizes = [m for m in sizes_meta if m["name"] not in disabled_names]
    if not active_sizes:
        # 전부 결함이면 등록 의미가 없다(폴더 정리 후 에러).
        _cleanup_dir(tmp_path_dir)
        _cleanup_dir(pattern_dir)
        return JSONResponse(
            status_code=400,
            content={"error": "모든 사이즈가 자산 결함(좌표 동일)으로 비활성됩니다. "
                              "올바른 사이즈 파일로 다시 등록해 주세요.",
                     "warnings": warnings})

    # 페이지 치수 폴백(전부 .svg 업로드 등으로 못 구한 경우 V넥 기본값).
    if page_dims is None:
        page_dims = [4478.74, 5669.29]
        warnings.append(
            "🟡 페이지 치수를 자동으로 못 구해 기본값(4478.74×5669.29)을 넣었습니다. "
            "preset.json 의 design.page_size_pt 를 확인해 주세요.")

    # ── 2) 글리프셋(선택): 0~9 아웃라인 추출 → number_glyphs.json ──────────
    glyph_source = None      # preset area 에 부착할 글리프셋 파일명(없으면 폰트 폴백)
    glyph_result: Dict[str, Any] = {"used": False}
    if glyphset and glyphset.filename:
        try:
            gpath = state.save_upload(glyphset)
            # artbox/order 파싱(미지정 시 엔진 기본값 사용).
            kwargs: Dict[str, Any] = {}
            if glyph_artbox:
                try:
                    kwargs["artbox"] = [float(x) for x in glyph_artbox.split(",")]
                except Exception:
                    warnings.append("🟡 glyph_artbox 형식이 잘못돼 기본값을 씁니다(x0,y0,x1,y1).")
            if glyph_order:
                kwargs["order"] = glyph_order
            gs = extract_number_glyphs(gpath, **kwargs)
            n_glyph = len(gs.get("glyphs", {}))
            out_json = os.path.join(pattern_dir, "number_glyphs.json")
            save_glyphset_json(gs, out_json)
            glyph_source = "number_glyphs.json"
            glyph_result = {"used": True, "count": n_glyph,
                            "cap_height": gs.get("cap_height")}
            if n_glyph < 10:
                warnings.append(
                    f"🟡 글리프셋에서 {n_glyph}자만 인식했습니다(기대 10자). "
                    "artbox/순서를 확인하거나 기본 폰트 폴백을 고려하세요.")
        except Exception as e:
            warnings.append(
                f"🟡 글리프셋 추출 실패(기본 폰트로 폴백): {e}")
            glyph_result = {"used": False, "error": str(e)}

    # ── 3) 완성본(선택): area 자동추출(front/back number + back name) ──────
    area_result: Dict[str, Any] = {"used": False}
    areas: Dict[str, Any] = {}
    if reference and reference.filename:
        try:
            rpath = state.save_upload(reference)
            built = build_area_preset(rpath)
            areas = built.get("areas", {}) or {}
            for w in (built.get("warnings") or []):
                warnings.append(w)
            area_result = {
                "used": True,
                "front_number": areas.get("front_number_area") is not None,
                "back_number": areas.get("back_number_area") is not None,
                "back_name": areas.get("back_name_area") is not None,
            }
        except Exception as e:
            warnings.append(f"🟡 완성본 area 자동추출 실패(영역은 직접 입력 필요): {e}")
            area_result = {"used": False, "error": str(e)}

    # ── 4) preset.json 조립 ──────────────────────────────────────────────
    base = (base_size or "").strip().upper()
    if base not in order:
        base = "XL" if "XL" in order else order[len(order) // 2]  # XL→중앙값

    pieces = _build_pieces(piece_n, page_dims[0], page_dims[1], warnings)

    preset: Dict[str, Any] = {
        "preset_name": pattern_id,
        "version": 1,
        "design": {
            "base_size": base,
            # 완성본을 받았으면 그걸, 아니면 빈본체 기본 경로를 넣어 둔다(직원이 교체).
            "design_file": "../../../design_source/연세대_V넥_빈템플릿_본체포함_XL.ai",
            "page_size_pt": [round(page_dims[0], 2), round(page_dims[1], 2)],
        },
        "sizes": active_sizes,
        "pieces": pieces,
        "design_mapping": {
            "mode": "anchor", "anchor": "bottom-left",
            "fit": "contain", "preserve_aspect": True,
        },
        "shrink": {"x": 1.0, "y": 1.0},
        "output": {
            "format": "pdf",
            "ghostscript_path": state.read_settings().get("ghostscript_path", ""),
        },
    }
    if disabled_sizes:
        preset["disabled_sizes"] = disabled_sizes

    # area(번호·이름) — 완성본에서 추출된 것만 붙이고, 글리프셋이 있으면 number_area
    # 에 glyph_source 를 함께 단다(없으면 폰트 폴백이라 키 생략).
    fa = areas.get("front_number_area")
    ba = areas.get("back_number_area")
    na = areas.get("back_name_area")
    if fa:
        if glyph_source:
            fa["glyph_source"] = glyph_source
        preset["front_number_area"] = fa
    if ba:
        if glyph_source:
            ba["glyph_source"] = glyph_source
        preset["back_number_area"] = ba
    if na:
        preset["back_name_area"] = na
    if not (fa or ba):
        warnings.append(
            "🟡 번호 영역(front/back_number_area)이 없습니다. 완성본을 올리거나 "
            "preset.json 에 직접 좌표를 넣어야 번호가 합성됩니다.")

    preset_path = os.path.join(pattern_dir, "preset.json")
    with open(preset_path, "w", encoding="utf-8") as f:
        json.dump(preset, f, ensure_ascii=False, indent=2)

    # 중간 path SVG 폴더는 정리(결과물은 polyline SVG·json·preset 만 남긴다).
    _cleanup_dir(tmp_path_dir)

    return {
        "ok": True,
        "pattern_id": pattern_id,
        "preset_path": os.path.relpath(preset_path, state.PROJECT_ROOT).replace("\\", "/"),
        "sizes": order,
        "active_sizes": [m["name"] for m in active_sizes],
        "pieces": piece_n,
        "glyph_source": bool(glyph_source),
        "glyph": glyph_result,
        "area": area_result,
        "disabled_sizes": disabled_sizes,
        "warnings": warnings,
    }


def _cleanup_dir(path: str) -> None:
    """폴더를 통째로 정리한다(없으면 무시, 실패해도 조용히 넘어간다)."""
    try:
        import shutil as _sh
        if os.path.isdir(path):
            _sh.rmtree(path, ignore_errors=True)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════
# Google Drive 패턴 라이브러리 (공유드라이브 트리 탐색 → 폴더 선택 → 등록)
#   서버가 '서비스 계정(로봇 계정)' 으로 공유드라이브를 '읽기 전용' 탐색한다.
#   전부 admin 전용(로컬 무인증이면 통과 — 회귀 0). 실제 Drive 접속은 webapp/gdrive.py.
#   미설정(GDRIVE_* env 없음)이면 에러가 아니라 200 + {configured:false} 로 안내한다
#   → 화면이 "관리자 설정 필요" 빈상태를 그려 주면 된다(관리자가 아직 안 켠 정상 상태).
# ══════════════════════════════════════════════════════════════════════════

def _drive_not_configured_payload() -> Dict[str, Any]:
    """Drive 미설정 안내 본문(여러 엔드포인트 공용)."""
    return {
        "configured": False,
        "message": (
            "Google Drive 연동이 설정되지 않았습니다. 관리자에게 문의하세요"
            " (서버 환경변수 GDRIVE_SA_JSON · GDRIVE_ROOT_FOLDER_ID 필요)."
        ),
    }


@router.get("/drive/tree", dependencies=[Depends(admin_required)])
def drive_tree(folderId: Optional[str] = None) -> JSONResponse:
    """폴더 하나의 '바로 아래' 항목(하위폴더·파일)을 1단계만 나열(트리 지연 로딩).

    비유: 파일 탐색기에서 폴더 하나를 '펼치면' 그 안 항목만 보이는 것과 같다.
    깊은 트리를 한 번에 다 읽지 않고, 화면이 펼칠 때마다 이 API 를 폴더별로 부른다.

    쿼리:
      folderId : 펼칠 폴더 ID. 없으면 루트(GDRIVE_ROOT_FOLDER_ID)부터.
    반환:
      · 미설정 : {configured:false, message}
      · 정상   : {configured:true, folderId, isRoot, items:[{id,name,isFolder,mimeType}]}
                 items 는 폴더 먼저·이름순.
    """
    if not gdrive.is_configured():
        return JSONResponse(content=_drive_not_configured_payload())

    fid = (folderId or "").strip() or gdrive.root_folder_id()
    try:
        items = gdrive.list_children(fid)
    except gdrive.DriveConfigError as e:
        # 키/자격증명 문제 = 서버 설정 오류.
        return JSONResponse(status_code=500, content={"error": f"Drive 설정 오류: {e}"})
    except gdrive.DriveError as e:
        # 권한 없음·잘못된 폴더ID·네트워크 등 Drive 호출 실패.
        return JSONResponse(status_code=502, content={"error": f"Drive 접근 실패: {e}"})

    return JSONResponse(content={
        "configured": True,
        "folderId": fid,
        "isRoot": fid == gdrive.root_folder_id(),
        "items": items,
    })


# ── 사이즈 파서(파일명 → 사이즈 토큰) ──────────────────────────────────────
#   왜 필요한가: 실제 드라이브 파일명이 제각각이다(언더바/공백/중복공백/소문자 혼재).
#     "농구유니폼_U넥_스탠다드_암홀X_XL.ai" · "U넥 상의 슬림 XL.ai" · "v넥 상의 스탠다드  XS.ai"
#   방식: 확장자를 떼고 [공백/_/-] 로 토큰화한 뒤, '토큰 하나가 사이즈 목록과 정확히 일치' 하는
#     것만 사이즈로 인정한다(부분매칭 금지 → "U넥"의 U, "암홀X"의 X 오인 방지). 여러 개면 끝의 것.
_SIZE_TOKENS = [
    "5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L",
    "XL", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL",
]
_SIZE_SET = set(_SIZE_TOKENS)
_SIZE_RANK = {s: i for i, s in enumerate(_SIZE_TOKENS)}  # 정렬용(작은→큰)

# 등록 후보로 볼 파일 확장자(대소문자 무시). 나머지는 후보에서 제외.
_PATTERN_FILE_EXTS = {".ai", ".pdf", ".svg"}


def _parse_size_from_filename(filename: str) -> Optional[str]:
    """파일명에서 사이즈 토큰(예 'XL')을 뽑는다. 못 찾으면 None.

    확장자 제거 → [공백/_/-] 로 토큰화 → 사이즈 목록과 '정확히' 일치하는 토큰만 수집 →
    여러 개면 마지막(파일명 끝쪽)을 사이즈로 본다(예: 'XL_최종' → XL).
    """
    import re
    stem = os.path.splitext(filename or "")[0]
    tokens = [t for t in re.split(r"[\s_\-]+", stem) if t]
    found = [t.upper() for t in tokens if t.upper() in _SIZE_SET]
    return found[-1] if found else None


def _is_temp_or_aux_file(name: str) -> bool:
    """임시/보조 파일인지(등록 후보에서 빼야 하는지). 예: '~ai-...tmp'.

    규칙: '~' 로 시작하거나 확장자가 '.tmp' 면 임시로 본다.
    ('원본'·'0.원본'·'원본 작업용' 은 대개 폴더라 트리 탐색에서 보이되, 여기 파일 판정과는 별개.)
    """
    n = (name or "").strip()
    if n.startswith("~"):
        return True
    return os.path.splitext(n)[1].lower() == ".tmp"


def _scan_folder_pattern_files(fid: str):
    """폴더 내 사이즈별 패턴 파일 후보를 분류한다(미리보기 엔드포인트·등록에서 공용).

    반환: (files, warnings)
      files    : [{id,name,size,mimeType}] — .ai/.pdf/.svg 이고 사이즈 인식됨(작은→큰 정렬).
      warnings : [{name,reason}] — 임시/보조 파일이거나 사이즈 미상.
    gdrive 예외(DriveConfigError/DriveError)는 호출부가 처리하도록 그대로 올린다.
    """
    children = gdrive.list_children(fid)
    files: List[Dict[str, Any]] = []
    warnings: List[Dict[str, str]] = []
    for it in children:
        if it.get("isFolder"):
            continue  # 하위 폴더는 트리 탐색(/drive/tree)에서 다룬다.
        name = it.get("name") or ""
        if _is_temp_or_aux_file(name):
            warnings.append({"name": name, "reason": "임시/보조 파일(자동 제외)"})
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in _PATTERN_FILE_EXTS:
            continue  # .ai/.pdf/.svg 가 아니면 패턴 후보 아님(조용히 무시).
        size = _parse_size_from_filename(name)
        if not size:
            warnings.append({"name": name, "reason": "사이즈를 인식하지 못함(파일명 확인 필요)"})
            continue
        files.append({
            "id": it.get("id"),
            "name": name,
            "size": size,
            "mimeType": it.get("mimeType"),
        })
    # 사이즈 작은→큰 순 정렬(가독성). 알 수 없는 값은 뒤로.
    files.sort(key=lambda f: _SIZE_RANK.get(f["size"], len(_SIZE_TOKENS)))
    return files, warnings


@router.get("/drive/folder/{folder_id}/patternfiles", dependencies=[Depends(admin_required)])
def drive_pattern_files(folder_id: str) -> JSONResponse:
    """폴더 안 '사이즈별 패턴 파일 후보' + 파싱된 사이즈 미리보기(등록 전 확인용).

    비유: 폴더를 열어 "이건 XL, 저건 2XL…" 하고 옷 사이즈표를 만들어 보여주는 일.
    등록(from-drive) 전에 사람이 눈으로 '사이즈 인식이 맞는지' 확인하라고 미리 보여준다.

    분류:
      · files    : .ai/.pdf/.svg 이면서 사이즈가 인식된 것(사이즈 작은→큰 순). 등록 후보.
      · warnings : 임시/보조(.tmp·~)이거나, 후보 확장자인데 사이즈를 못 읽은 것(사유 포함).
      (하위 폴더·기타 확장자는 여기서 제외 — 파일 미리보기 목적.)
    """
    if not gdrive.is_configured():
        return JSONResponse(content=_drive_not_configured_payload())

    fid = (folder_id or "").strip()
    if not fid:
        return JSONResponse(status_code=400, content={"error": "folder_id 가 비어 있습니다."})
    try:
        files, warnings = _scan_folder_pattern_files(fid)
    except gdrive.DriveConfigError as e:
        return JSONResponse(status_code=500, content={"error": f"Drive 설정 오류: {e}"})
    except gdrive.DriveError as e:
        return JSONResponse(status_code=502, content={"error": f"Drive 접근 실패: {e}"})

    return JSONResponse(content={
        "configured": True,
        "folderId": fid,
        "files": files,
        "warnings": warnings,
    })


class _DriveUpload:
    """create_pattern 이 먹는 UploadFile 흉내(duck-type).

    create_pattern 은 업로드 객체에서 '.filename' 과 state.save_upload() 만 쓰고,
    save_upload 는 다시 '.filename'·'.file'(seek/read) 만 쓴다(정독으로 확인). 그래서
    이 둘만 갖추면 기존 등록 로직을 안전하게 그대로 재사용할 수 있다(엔진·등록 무수정).
    """

    def __init__(self, filename: str, fileobj) -> None:
        self.filename = filename
        self.file = fileobj


@router.post("/patterns/from-drive", dependencies=[Depends(admin_required)])
async def create_pattern_from_drive(payload: Dict[str, Any] = Body(...)) -> Any:
    """Google Drive 폴더 하나를 골라 패턴으로 등록한다(기존 create_pattern 재사용).

    payload:
      folderId          : (필수) 등록할 폴더 ID.
      name              : (필수) 패턴 이름.
      base_size         : (선택) 기준 사이즈(없으면 XL→중앙 자동).
      glyph_file_id     : (선택) 글리프셋 소스 파일 ID(폴더 내).
      reference_file_id : (선택) 완성본 파일 ID(area 자동추출).
      glyph_artbox      : (선택) "x0,y0,x1,y1".
      glyph_order       : (선택) 글리프 정렬 문자열.

    흐름: Drive 다운로드(임시) → 파일명을 '<사이즈>.<확장자>' 로 정리 → '가짜 업로드'로
    감싸 create_pattern 에 넘긴다 → 기존 변환·검증·preset 생성이 그대로 돈다. 임시파일 정리.
    """
    if not gdrive.is_configured():
        return JSONResponse(content=_drive_not_configured_payload())

    folder_id = str(payload.get("folderId") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not folder_id:
        return JSONResponse(status_code=400, content={"error": "folderId 가 필요합니다."})
    if not name:
        return JSONResponse(status_code=400, content={"error": "패턴 이름(name)이 필요합니다."})

    # 1) 폴더 스캔 → 사이즈 인식된 파일 목록(미리보기와 동일 로직).
    try:
        files, scan_warnings = _scan_folder_pattern_files(folder_id)
    except gdrive.DriveConfigError as e:
        return JSONResponse(status_code=500, content={"error": f"Drive 설정 오류: {e}"})
    except gdrive.DriveError as e:
        return JSONResponse(status_code=502, content={"error": f"Drive 접근 실패: {e}"})

    if not files:
        return JSONResponse(status_code=400, content={
            "error": "등록할 사이즈 파일이 없습니다(사이즈 인식 실패 또는 빈 폴더).",
            "warnings": scan_warnings,
        })

    base_size = payload.get("base_size") or None
    glyph_artbox = payload.get("glyph_artbox") or None
    glyph_order = payload.get("glyph_order") or None
    glyph_file_id = str(payload.get("glyph_file_id") or "").strip()
    reference_file_id = str(payload.get("reference_file_id") or "").strip()

    # 2) 임시 다운로드 폴더(끝나면 통째 삭제). 열린 파일핸들도 finally 에서 닫는다.
    tmp_dir = tempfile.mkdtemp(prefix="fromdrive_")
    open_handles: List[Any] = []
    try:
        # 2a) 사이즈 파일들 다운로드 → '<사이즈>.<ext>' 어댑터(create_pattern 파서가 정확히 읽음).
        size_uploads: List[_DriveUpload] = []
        for f in files:
            ext = os.path.splitext(f["name"])[1].lower() or ".ai"
            dest = os.path.join(tmp_dir, f"src_{f['size']}{ext}")
            gdrive.download_file(f["id"], dest)
            fh = open(dest, "rb")
            open_handles.append(fh)
            size_uploads.append(_DriveUpload(f"{f['size']}{ext}", fh))

        # 2b) 글리프셋(선택).
        glyph_upload = None
        if glyph_file_id:
            meta = gdrive.get_file_meta(glyph_file_id)
            gext = os.path.splitext(meta.get("name") or "")[1].lower() or ".ai"
            gdest = os.path.join(tmp_dir, f"glyph{gext}")
            gdrive.download_file(glyph_file_id, gdest)
            gfh = open(gdest, "rb")
            open_handles.append(gfh)
            glyph_upload = _DriveUpload(f"glyph{gext}", gfh)

        # 2c) 완성본(선택).
        ref_upload = None
        if reference_file_id:
            meta = gdrive.get_file_meta(reference_file_id)
            rext = os.path.splitext(meta.get("name") or "")[1].lower() or ".ai"
            rdest = os.path.join(tmp_dir, f"reference{rext}")
            gdrive.download_file(reference_file_id, rdest)
            rfh = open(rdest, "rb")
            open_handles.append(rfh)
            ref_upload = _DriveUpload(f"reference{rext}", rfh)

        # 3) 기존 등록 로직 재사용(중복 구현 금지). create_pattern 은 async.
        result = await create_pattern(
            name=name,
            base_size=base_size,
            glyph_artbox=glyph_artbox,
            glyph_order=glyph_order,
            glyphset=glyph_upload,
            reference=ref_upload,
            files=size_uploads,
        )
    except gdrive.DriveError as e:
        return JSONResponse(status_code=502, content={"error": f"Drive 파일 다운로드 실패: {e}"})
    finally:
        for fh in open_handles:
            try:
                fh.close()
            except Exception:
                pass
        _cleanup_dir(tmp_dir)

    # create_pattern 은 성공 시 dict, 실패 시 JSONResponse 를 돌려준다 → 그대로 전달.
    #   등록 성공이면 스캔 경고(사이즈 미상 등)를 덧붙여 화면이 함께 보여줄 수 있게 한다.
    if isinstance(result, dict) and scan_warnings:
        result.setdefault("drive_warnings", scan_warnings)
    return result
