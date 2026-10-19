# -*- coding: utf-8 -*-
"""엔진 일꾼 프로세스의 «안전띠» — 파이썬이 켜질 때 저절로 먼저 읽는 파일(sitecustomize).

왜 이 파일이 있나(비유):
  Render starter 는 상자 하나에 메모리 512MB 다. 엔진 일꾼이 부풀면 커널이 «누군가» 를 죽이는데,
  그게 서버(직원 화면 전체)면 안 된다. 그래서 일꾼이 켜지는 순간 스스로 두 가지를 건다.
    ① oom_score_adj = 1000 — «메모리가 모자라면 나부터 죽여라» (서버 대신 일꾼만 죽는다. 리눅스 커널 규칙)
    ② RLIMIT_AS(주소 공간 상한) — 고장으로 끝없이 커지면 커널보다 먼저 MemoryError 로 멈춘다(백스톱)
  webapp/cad.py 가 일꾼을 띄울 때만 PYTHONPATH 에 이 폴더를 넣는다 → 서버 자신이나 다른 파이썬에는 영향 없음.
  윈도우(직원 PC·로컬 시험)에서는 아무것도 하지 않는다 — 두 기능 다 리눅스 전용.

환경변수:
  GRADER_ENGINE_LIMIT_AS_MB   주소 공간 상한(MB). 0 이면 걸지 않는다. (값과 근거는 webapp/cad.py ENGINE_AS_LIMIT_MB_DEFAULT)
  GRADER_ENGINE_OOM_ADJ       기본 1000 (−1000~1000, 클수록 먼저 죽는다). 빈 값이면 건드리지 않는다.
"""
import os
import sys


def _apply():
    applied = {}
    if not sys.platform.startswith("linux"):
        os.environ["GRADER_ENGINE_GUARD"] = "skipped:" + sys.platform     # 시험이 «읽혔는지» 볼 수 있게 표시만
        return applied
    adj = os.environ.get("GRADER_ENGINE_OOM_ADJ", "1000").strip()
    if adj:
        try:
            with open("/proc/self/oom_score_adj", "w") as f:              # 올리는 것은 권한 없이도 된다(내리는 것만 막힌다)
                f.write(adj)
            applied["oom_score_adj"] = adj
        except Exception as e:
            applied["oom_score_adj"] = f"실패 {type(e).__name__}"
    mb = os.environ.get("GRADER_ENGINE_LIMIT_AS_MB", "").strip()
    if mb and mb != "0":
        try:
            import resource
            lim = int(mb) * 2 ** 20
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            if hard != resource.RLIM_INFINITY:
                lim = min(lim, hard)
            resource.setrlimit(resource.RLIMIT_AS, (lim, hard))
            applied["rlimit_as_mb"] = lim // 2 ** 20
        except Exception as e:
            applied["rlimit_as_mb"] = f"실패 {type(e).__name__}"
    os.environ["GRADER_ENGINE_GUARD"] = ",".join(f"{k}={v}" for k, v in applied.items()) or "none"
    return applied


_apply()
