# 1. 가볍고 안정적인 Python 3.10 이미지 사용
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 필수 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Lawmadi OS v50.0.0 소스 코드 및 설정 파일 복사
# (사장님의 폴더 구조를 유지합니다)
COPY core/ ./core/
COPY connectors/ ./connectors/
COPY main.py .
COPY config.json .
COPY leaders.json .

# 6. 포트 설정 및 실행
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
