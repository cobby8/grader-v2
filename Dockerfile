# grader-v2 배포 컨테이너 (Render 등 Docker 런타임용)
#
# 무엇을 담나(비유): 직원 PC 에 깔던 것을 '상자 하나' 에 미리 다 넣어 둔다.
#   파이썬 + Ghostscript(EPS 변환) + 폰트 + 우리 코드 → 어디서 켜도 똑같이 돈다.
FROM python:3.11-slim

# ── 시스템 패키지: Ghostscript(EPS 변환) + fontconfig(폰트 처리) ──
#   --no-install-recommends 로 불필요한 추천 패키지를 빼 이미지를 가볍게 한다.
#   설치 후 apt 캐시를 지워(이미지 용량 절감) 한 RUN 으로 묶는다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ghostscript fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── 파이썬 의존성 먼저 설치(레이어 캐시 활용) ──
#   requirements 만 먼저 복사해 설치하면, 코드만 바뀌었을 때 이 레이어는 재사용된다.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ── 애플리케이션 코드 복사 ──
#   .dockerignore 가 data/jobs·uploads·.venv·design_source·.git 등을 제외한다.
COPY . .

# ── 배포 환경변수(기본값) ──
#   GRADER_NO_BROWSER=1 : 서버에서 브라우저 자동오픈 시도 안 함(헤드리스).
#   GS_BIN=gs           : Ghostscript 경로를 PATH 의 'gs' 로 강제(eps.find_ghostscript 1순위).
#   GRADER_REQUIRE_AUTH=1: 배포는 항상 로그인 인증 ON(로컬과 달리 무인증 진입 차단).
#   (SUPABASE_* 비밀키는 여기에 절대 넣지 않는다 — Render env 로만 주입)
ENV GRADER_NO_BROWSER=1 \
    GS_BIN=gs \
    GRADER_REQUIRE_AUTH=1

# 문서용 포트(실제 바인딩은 아래 CMD 와 PORT 환경변수가 결정).
#   Render 등은 컨테이너에 $PORT(보통 10000)를 주입하고 그 포트로 헬스체크/트래픽을 보낸다.
#   EXPOSE 는 문서용일 뿐 실제 바인딩에 영향 없으므로 8000 그대로 둔다(Render 는 $PORT 사용).
EXPOSE 8000

# ── 서버 기동 ──
#   0.0.0.0 으로 외부 접속 허용. 포트는 ${PORT:-8000} — Render 가 주입한 $PORT 가 있으면 그 포트로,
#   없으면(로컬 docker run 등) 8000 으로 폴백한다(로컬 무영향).
#   ⚠️ exec form(JSON 배열)은 환경변수 확장이 안 되므로 반드시 shell form 으로 작성해야
#      ${PORT:-8000} 이 셸에서 확장된다. sh -c 로 감싸 셸이 변수를 풀게 한다.
#   --workers 1 유지(상태/메모리 job 저장소가 단일 워커 전제라 여러 워커면 job 진행상태가 갈린다 — 불변 제약).
CMD ["sh", "-c", "python -m uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
