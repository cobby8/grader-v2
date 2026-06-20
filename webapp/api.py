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
from typing import Any, Dict, List

from fastapi import APIRouter

from . import state
from .state import DEFAULT_PORT

# 엔진 공개 API 는 import 만 한다(수정 금지). preset.json 로드/검증을 재사용한다.
from engine.grade import load_preset

# /api 아래로 묶일 라우터. main.py 가 이 router 를 앱에 붙인다.
router = APIRouter(prefix="/api")


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
