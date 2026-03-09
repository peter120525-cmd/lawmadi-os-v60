# ═══════════════════════════════════════════════════
# Lawmadi OS v60 — Multi-Stage Docker Build (항목 #18)
# ═══════════════════════════════════════════════════

# Stage 1: Builder — 의존성 설치 (build-essential 포함)
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime — 최소 이미지 (build-essential 제외)
FROM python:3.10-slim AS runtime

WORKDIR /app

# Builder에서 설치된 패키지만 복사
COPY --from=builder /install /usr/local

# 소스 코드 및 설정 파일 복사
COPY core/ ./core/
COPY connectors/ ./connectors/
COPY utils/ ./utils/
COPY routes/ ./routes/
COPY tools/ ./tools/
COPY main.py .
COPY config.json .
COPY leaders.json .
# law_cache: Vertex AI Search 전환 완료 → Docker 이미지에서 제거 (614MB 절감)
# 로컬 개발 시 필요하면 GCS에서 다운로드: gs://lawmadi-db-law-cache/
COPY data/ ./data/
COPY agents/ ./agents/
COPY engines/ ./engines/
COPY services/ ./services/
COPY prompts/ ./prompts/
COPY frontend/ ./frontend/
COPY static/ ./static/
COPY fonts/ ./fonts/

# LLM-readable reference files
COPY llms.txt .
COPY README.md .
COPY license .

# 비루트 사용자 생성 및 디렉토리 설정
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && mkdir -p temp logs uploads \
    && chown -R appuser:appuser /app

USER appuser

# 헬스체크 — Cloud Run + Docker 자체 모니터링 겸용
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=4)" || exit 1

# 포트 설정 및 실행
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
