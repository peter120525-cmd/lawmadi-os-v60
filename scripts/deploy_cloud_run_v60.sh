#!/bin/bash
# Lawmadi OS v60 Cloud Run 배포 스크립트
# 작성일: 2026-02-13

set -e  # 에러 발생 시 중단

echo "🚀 Lawmadi OS v60 Cloud Run 배포 시작"
echo "======================================"
echo ""

# 1. 환경 설정
PROJECT_ID="lawmadi-db"
REGION="asia-northeast3"
SERVICE_NAME="lawmadi-os-v60"
REPOSITORY="lawmadi-repo"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}"

echo "📋 배포 설정:"
echo "  프로젝트: ${PROJECT_ID}"
echo "  리전: ${REGION}"
echo "  서비스: ${SERVICE_NAME}"
echo "  이미지: ${IMAGE_NAME}"
echo ""

# 2. 현재 디렉토리 확인
if [ ! -f "main.py" ]; then
    echo "❌ main.py를 찾을 수 없습니다. 프로젝트 루트에서 실행하세요."
    exit 1
fi

echo "✅ 프로젝트 루트 확인됨"
echo ""

# 3. gcloud 프로젝트 설정
echo "🔧 gcloud 프로젝트 설정..."
gcloud config set project ${PROJECT_ID}

# 4. Artifact Registry 인증 및 이미지 빌드
echo ""
echo "🏗️  Docker 이미지 빌드 중..."
echo "  (Cloud Build 사용 - 약 2-3분 소요)"
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
gcloud builds submit --tag ${IMAGE_NAME} .

# 5. Cloud Run 배포
echo ""
echo "🚢 Cloud Run 배포 중..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 15 \
  --min-instances 0 \
  --max-instances 5 \
  --port 8080 \
  --set-env-vars "ENABLE_LAWMADILM=false,LAWMADILM_TIMEOUT=3,USE_VERTEX_AI=true,USE_VERTEX_SEARCH=true,GCP_PROJECT_ID=lawmadi-db,VERTEX_SEARCH_DATA_STORE_ID=lawmadi-legal-cache,VERTEX_SEARCH_ENGINE_ID=lawmadi-search-engine,VERTEX_PROJECT=lawmadi-db,VERTEX_LOCATION=asia-northeast3,SMTP_HOST=smtp.gmail.com,SMTP_PORT=587,SMTP_USER=peter120525@gmail.com,SMTP_FROM=peter120525@gmail.com,PADDLE_ENVIRONMENT=sandbox,PADDLE_CLIENT_TOKEN=test_f28d927d810d5df8c5cfeca8513,DAILY_FREE_LIMIT=2,SESSION_EXPIRY_DAYS=30" \
  --set-secrets "GEMINI_KEY=GEMINI_KEY:latest,LAWGO_DRF_OC=LAWGO_DRF_OC:latest,DATABASE_URL=DATABASE_URL:latest,CLOUD_SQL_INSTANCE=CLOUD_SQL_INSTANCE:latest,DB_USER=DB_USER:latest,DB_PASS=DB_PASS:latest,DB_NAME=DB_NAME:latest,MCP_API_KEY=MCP_API_KEY:latest,API_KEYS=API_KEYS:latest,INTERNAL_API_KEY=INTERNAL_API_KEY:latest,PREMIUM_KEYS=PREMIUM_KEYS:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest,PADDLE_WEBHOOK_SECRET=PADDLE_WEBHOOK_SECRET:latest"

# 6. 배포 URL 확인
echo ""
echo "✅ 배포 완료!"
echo ""
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "🌐 서비스 URL: ${SERVICE_URL}"
echo ""

# 7. 헬스 체크
echo "🏥 헬스 체크 중..."
sleep 5
HEALTH_RESPONSE=$(curl -s ${SERVICE_URL}/health || echo "FAIL")

if [[ $HEALTH_RESPONSE == *"online"* ]]; then
    echo "✅ 헬스 체크 성공"
else
    echo "⚠️  헬스 체크 실패: ${HEALTH_RESPONSE}"
fi

echo ""
echo "======================================"
echo "🎉 Lawmadi OS v60 배포 완료!"
echo "======================================"
echo ""
echo "📋 다음 단계:"
echo "  1. 브라우저에서 접속: ${SERVICE_URL}"
echo "  2. Firebase Hosting 업데이트"
echo "  3. 문서 업로드 기능 테스트"
echo ""
