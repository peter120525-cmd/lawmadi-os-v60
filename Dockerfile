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
COPY law_cache.json .
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

# 포트 설정 및 실행
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
