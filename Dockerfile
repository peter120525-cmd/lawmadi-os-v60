# Base
FROM python:3.11-slim

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source
COPY . .

# Remove .env if accidentally copied (secrets come from Cloud Run env)
RUN rm -f .env

# Cloud Run default port
ENV PORT=8080

# Run
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]