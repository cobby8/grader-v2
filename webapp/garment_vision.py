"""패턴 의뢰 — 사진으로 옷 모양 판단 (2026-10-19)

현장 직원이 찍은 앞·뒤 전체 사진을 AI(Claude)에게 보여 주고, 패턴 의뢰 1단계 «옷 고르기»의
선택지(목 모양·소매 달기·소매 길이·소매 끝·밑단·더 붙은 것)를 미리 골라 받는다.
직원은 확인만 하고, 최종 결정은 사람이 한다(확신 낮음·모름은 화면이 «확인 필요»로 표시).

· 선택지와 판단 지시서는 목록 파일(static/intake/catalog.json)에서 만든다 —
  부품을 목록에 추가하면 AI 가 고를 수 있는 것도 따라 늘어난다.
· AI 키는 환경변수 ANTHROPIC_API_KEY 로만 받는다. 없으면 이 기능은 «꺼짐»(화면에 카드가 안 나온다).
  🚫 키를 응답·로그에 내보내지 않는다.
· 답은 «도구 호출»(정해 둔 JSON 모양)로 받고, 목록에 없는 열쇠가 오면 «모름»으로 바꾼다.

정확도 시험(2026-10-19, 정답 모르는 판단기 11개·22건): 확실한 칸 81/83, 기본 형태 22/22.
틀린 2개는 모두 소매가 화면 밖으로 잘린 현장 사진 → 아래 지시서 8번 규칙을 넣었다.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List, Tuple

import httpx

from . import state

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("INTAKE_VISION_MODEL", "claude-opus-5-5").strip() or "claude-opus-5-5"
TIMEOUT_S = 90.0
MAX_IMAGE_BYTES = 4 * 1024 * 1024          # 폰에서 1600px 로 줄여 보내므로 보통 0.3~0.6MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
CONFIDENCE = ("high", "medium", "low")
GROUPS = ("neck", "sleeve", "length", "cuff", "hem")


class VisionError(Exception):
    """화면에 그대로 보여 줄 한국어 안내와 HTTP 상태를 담는다."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def enabled() -> bool:
    """AI 키가 있으면 켜짐. 값은 보지 않고 «있는지»만 본다."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


_catalog_cache: Dict[str, Any] = {"mtime": None, "data": None}


def load_catalog() -> Dict[str, Any]:
    """목록 파일을 읽는다(파일이 바뀌면 다시 읽음)."""
    path = os.path.join(state.get_static_dir(), "intake", "catalog.json")
    mtime = os.path.getmtime(path)
    if _catalog_cache["mtime"] != mtime:
        with open(path, encoding="utf-8") as f:
            _catalog_cache["data"] = json.load(f)
        _catalog_cache["mtime"] = mtime
    return _catalog_cache["data"]


def _sleeve_top(cat: Dict[str, Any]) -> Dict[str, Any]:
    return next(b for b in cat["bases"] if b["key"] == "sleeve_top")


def _opt_line(o: Dict[str, Any]) -> str:
    return "`%s` %s%s" % (o["key"], o["name"], (" (" + o["hint"] + ")") if o.get("hint") else "")


def build_instructions(cat: Dict[str, Any]) -> str:
    """판단 지시서 — 목록 파일의 기본 형태·묶음·선택지로 만든다."""
    st = _sleeve_top(cat)
    L: List[str] = [
        "너는 스포츠 의류 패턴 담당자다. 사진 속 옷 **한 벌**을 보고, 아래 목록에서 옷 모양을 고른다.",
        "사진은 그 옷의 앞·뒤(또는 뒤집은 안쪽) 사진이다. 현장에서 테이블에 펴고 찍은 사진일 수도, 판매용 사진(사람 착용·3D 그림)일 수도 있다.",
        "",
        "## 판단 원칙",
        "1. **보이는 것만 고른다.** 사진으로 확인되지 않으면 `unknown` — 짐작해서 채우지 않는다.",
        "2. **프린트와 이음선을 구분한다.** 승화 인쇄 옷은 색 구분이 조각처럼 보인다. 요크·옆 절개는 봉제선이나 다른 원단이 보일 때만 고르고, 색만 다르면 고르지 않는다(애매하면 confidence low).",
        "3. **래글런**: 소매 이음선이 목에서 겨드랑이로 사선으로 내려간다. **일반**: 어깨끝(어깨 봉제선 끝)에서 소매가 달린다.",
        "4. **소매 끝·밑단**: 립 = 골지 니트 밴드(세로 골이 보이고 몸판과 다른 조직) · 고무줄 = 주름 잡힌 밴드 · 접어박기 = 같은 원단을 접어 박음.",
        "5. 겉 사진으로는 보통 알 수 없는 것(인서트·양면·옆 트임)은 확실히 보일 때만 고른다.",
        "6. 목록에 없는 모양이면 `other` 로 하고 note 에 무엇인지 적는다(예: 단추 여밈).",
        "7. 사진 상태 때문에 판단이 흔들리면 photo_notes 에 적고 확신을 낮춘다.",
        "8. **잘린 사진**: 소매 끝이나 밑단이 사진 밖으로 나갔거나, 접히거나 가려서 끝이 안 보이면 "
        "소매 길이(length)·소매 끝(cuff)·밑단(hem)은 `unknown` 으로 둔다. 팔꿈치 근처에서 사진이 잘렸다고 반팔로 보지 않는다.",
        "9. 옷을 뒤집어(안쪽이 보이게) 찍은 사진이면 photo_notes 에 적는다. 안쪽에서 보이는 봉제선(요크·옆 절개 등)은 판단에 써도 된다.",
        "",
        "## 기본 형태 (base)",
    ]
    for b in cat["bases"]:
        L.append("- `%s` %s — %s" % (b["key"], b["name"], b.get("desc", "")))
    L += ["- `unknown` 판단 불가", "", "소매 상의(`sleeve_top`)가 아니면 아래 묶음은 모두 `unknown` 으로 둔다.", "", "## 소매 상의 — 묶음별 선택지"]
    for g in st["groups"]:
        if g["pick"] == "many":
            continue
        L.append("- **%s** (`%s`) — 하나: %s; `other`; `unknown`" % (g["name"], g["key"], "; ".join(_opt_line(o) for o in g["options"])))
    ex = next(g for g in st["groups"] if g["pick"] == "many")
    L.append("- **%s** (`extras`) — 있는 것만 여러 개: %s; 목록에 없으면 `other`" % (ex["name"], "; ".join(_opt_line(o) for o in ex["options"])))
    L += ["", "판단이 끝나면 report_garment 도구로 답한다. reason 은 한국어 한 줄."]
    return "\n".join(L)


def _choice_schema(values: List[str]) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "value": {"type": "string", "enum": values},
            "confidence": {"type": "string", "enum": list(CONFIDENCE)},
            "reason": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["value", "confidence", "reason"],
    }


def tool_schema(cat: Dict[str, Any]) -> Dict[str, Any]:
    """답 모양 — 선택지 열쇠를 enum 으로 묶어 엉뚱한 값이 오지 않게 한다."""
    st = _sleeve_top(cat)
    props: Dict[str, Any] = {"base": _choice_schema([b["key"] for b in cat["bases"]] + ["unknown"])}
    for g in st["groups"]:
        if g["pick"] == "one":
            props[g["key"]] = _choice_schema([o["key"] for o in g["options"]] + ["other", "unknown"])
    ex = next(g for g in st["groups"] if g["pick"] == "many")
    props["extras"] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": [o["key"] for o in ex["options"]] + ["other"]},
                "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                "reason": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["key", "confidence", "reason"],
        },
    }
    props["photo_notes"] = {"type": "string"}
    return {"type": "object", "properties": props, "required": ["base"] + [g for g in GROUPS] + ["extras", "photo_notes"]}


def _clip(s: Any, n: int) -> str:
    return str(s or "").strip()[:n]


def normalize(raw: Dict[str, Any], cat: Dict[str, Any]) -> Dict[str, Any]:
    """AI 답을 검사해 화면이 믿고 쓸 수 있는 모양으로 바꾼다 — 모르는 열쇠·확신은 «모름»·«낮음»."""
    st = _sleeve_top(cat)
    raw = raw if isinstance(raw, dict) else {}

    def pick(field: Any, allowed: List[str]) -> Dict[str, Any]:
        f = field if isinstance(field, dict) else {}
        v = f.get("value")
        c = f.get("confidence")
        out = {"value": v if v in allowed else "unknown", "confidence": c if c in CONFIDENCE else "low", "reason": _clip(f.get("reason"), 200)}
        if out["value"] == "other":
            out["note"] = _clip(f.get("note"), 200)
        return out

    result: Dict[str, Any] = {"base": pick(raw.get("base"), [b["key"] for b in cat["bases"]] + ["unknown"])}
    is_sleeve = result["base"]["value"] == "sleeve_top"
    for g in st["groups"]:
        if g["pick"] != "one":
            continue
        allowed = [o["key"] for o in g["options"]] + ["other", "unknown"]
        result[g["key"]] = pick(raw.get(g["key"]), allowed) if is_sleeve else {"value": "unknown", "confidence": "low", "reason": ""}
    ex_keys = [o["key"] for o in next(g for g in st["groups"] if g["pick"] == "many")["options"]] + ["other"]
    extras, seen = [], set()
    for e in ((raw.get("extras") or []) if is_sleeve else []):
        if not isinstance(e, dict) or e.get("key") not in ex_keys:
            continue
        if e["key"] in seen and e["key"] != "other":
            continue
        seen.add(e["key"])
        item = {"key": e["key"], "confidence": e.get("confidence") if e.get("confidence") in CONFIDENCE else "low", "reason": _clip(e.get("reason"), 200)}
        if e["key"] == "other":
            item["note"] = _clip(e.get("note"), 200)
        extras.append(item)
    result["extras"] = extras[:12]
    result["photo_notes"] = _clip(raw.get("photo_notes"), 500)
    return result


def build_request(images: List[Tuple[bytes, str, str]], cat: Dict[str, Any]) -> Dict[str, Any]:
    """AI 에 보낼 요청 본문. images = [(바이트, 형식, 무슨 사진인지)]"""
    content: List[Dict[str, Any]] = []
    for i, (data, media_type, label) in enumerate(images, 1):
        content.append({"type": "text", "text": "사진 %d: %s" % (i, label)})
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode("ascii")}})
    content.append({"type": "text", "text": "위 사진의 옷 한 벌을 판단해 report_garment 도구로 답하라."})
    return {
        "model": MODEL,
        "max_tokens": 2000,
        "system": build_instructions(cat),
        "tools": [{"name": "report_garment", "description": "사진 속 옷 모양 판단 결과를 보고한다", "input_schema": tool_schema(cat)}],
        "tool_choice": {"type": "tool", "name": "report_garment"},
        "messages": [{"role": "user", "content": content}],
    }


def _error_for(status: int) -> VisionError:
    if status in (401, 403):
        return VisionError(502, "AI 키가 맞지 않습니다(관리자에게 문의).")
    if status == 429:
        return VisionError(503, "AI 사용이 몰렸습니다. 잠시 후 다시 눌러 주세요.")
    if status == 400:
        return VisionError(400, "사진을 읽지 못했습니다. 다시 찍어 주세요.")
    return VisionError(503, "AI 서버가 바쁩니다. 잠시 후 다시 눌러 주세요.")


async def classify(images: List[Tuple[bytes, str, str]], client: Any = None) -> Dict[str, Any]:
    """사진 1~2장 → 판단 결과. client 는 시험용(가짜 응답)으로 바꿔 끼울 수 있다."""
    if not enabled():
        raise VisionError(503, "사진 판단이 꺼져 있습니다(관리자에게 문의).")
    cat = load_catalog()
    body = build_request(images, cat)
    headers = {
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        resp = await client.post(API_URL, headers=headers, json=body)
    except httpx.TimeoutException:
        raise VisionError(504, "AI 응답이 늦습니다. 다시 눌러 주세요.")
    except httpx.HTTPError:
        raise VisionError(503, "AI 서버에 연결하지 못했습니다. 잠시 후 다시 눌러 주세요.")
    finally:
        if own:
            await client.aclose()
    if resp.status_code != 200:
        raise _error_for(resp.status_code)
    try:
        payload = resp.json()
        block = next(b for b in payload.get("content", []) if b.get("type") == "tool_use" and b.get("name") == "report_garment")
        raw = block.get("input") or {}
    except Exception:
        raise VisionError(502, "AI 답을 읽지 못했습니다. 다시 눌러 주세요.")
    return {"model": payload.get("model", MODEL), "catalog_version": cat.get("version", ""), "result": normalize(raw, cat)}
