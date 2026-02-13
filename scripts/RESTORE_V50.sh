#!/bin/bash
###############################################################################
# Lawmadi OS v50 복구 스크립트
# v60 업그레이드 실패 시 v50으로 롤백
###############################################################################

set -e  # 에러 발생 시 중단

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         🔄 Lawmadi OS v50 복구 스크립트 🔄                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 복구 확인
echo -e "${YELLOW}⚠️  경고: v60을 v50으로 롤백합니다.${NC}"
echo ""
echo "다음 작업이 수행됩니다:"
echo "  1. Git 저장소를 v50.3.0-VERIFIED 태그로 복원"
echo "  2. Google Cloud Storage에서 코드 백업 복원 (선택)"
echo "  3. Docker 이미지를 v50-stable로 변경"
echo "  4. Cloud Run을 v50으로 재배포"
echo "  5. Firebase를 v50 코드로 재배포"
echo ""
read -p "계속하시겠습니까? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}✗ 복구 취소됨${NC}"
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Git 저장소 복원"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 현재 변경사항 백업
echo "📦 현재 변경사항 백업 중..."
BACKUP_BRANCH="backup-before-v50-restore-$(date +%Y%m%d-%H%M%S)"
git checkout -b "$BACKUP_BRANCH" 2>/dev/null || true
git add -A
git commit -m "BACKUP: v50 복구 전 백업 ($(date))" 2>/dev/null || echo "   커밋할 변경사항 없음"

# v50 태그로 체크아웃
echo "🔄 v50.3.0-VERIFIED 태그로 복원 중..."
git checkout v50.3.0-VERIFIED

echo -e "${GREEN}✅ Git 저장소 복원 완료${NC}"
echo ""

# Google Cloud Storage 복원 (선택)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Google Cloud Storage 백업 복원 (선택)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

read -p "GCS 백업에서 복원하시겠습니까? (yes/no): " USE_GCS

if [ "$USE_GCS" == "yes" ]; then
    echo "📥 GCS에서 백업 다운로드 중..."

    # 최신 백업 파일 찾기
    BACKUP_FILE=$(gcloud storage ls gs://lawmadi-backups-v50/ | grep "v50.3.0-VERIFIED" | sort -r | head -1)

    if [ -z "$BACKUP_FILE" ]; then
        echo -e "${RED}✗ 백업 파일을 찾을 수 없습니다${NC}"
    else
        echo "   백업 파일: $BACKUP_FILE"

        # 백업 다운로드
        gcloud storage cp "$BACKUP_FILE" /tmp/restore-v50.tar.gz

        # 백업 해제
        echo "📦 백업 압축 해제 중..."
        tar -xzf /tmp/restore-v50.tar.gz -C .

        echo -e "${GREEN}✅ GCS 백업 복원 완료${NC}"
    fi
else
    echo "⏭️  GCS 복원 건너뜀"
fi

echo ""

# Docker 이미지 복원
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  Docker 이미지 복원"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🐳 Docker 이미지 확인 중..."
V50_IMAGE="asia-northeast3-docker.pkg.dev/lawmadi-db/lawmadi-images/lawmadi-os:v50-stable"

if gcloud artifacts docker images list asia-northeast3-docker.pkg.dev/lawmadi-db/lawmadi-images/lawmadi-os | grep -q "v50-stable"; then
    echo "   ✅ v50-stable 이미지 존재 확인"
else
    echo -e "${YELLOW}   ⚠️  v50-stable 이미지를 찾을 수 없습니다. 새로 빌드합니다...${NC}"
    docker build -t lawmadi-os:v50-stable .
    docker tag lawmadi-os:v50-stable "$V50_IMAGE"
    docker push "$V50_IMAGE"
fi

echo -e "${GREEN}✅ Docker 이미지 준비 완료${NC}"
echo ""

# Cloud Run 재배포
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  Cloud Run 재배포"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "☁️  Cloud Run 서비스 업데이트 중..."

gcloud run deploy lawmadi-os-v50 \
  --image="$V50_IMAGE" \
  --region=asia-northeast3 \
  --platform=managed \
  --port=8080 \
  --memory=2Gi \
  --cpu=2 \
  --max-instances=10 \
  --set-env-vars="SOFT_MODE=true,SWARM_MULTI=true,LAWGO_DRF_OC=choepeter" \
  --allow-unauthenticated \
  --quiet

echo -e "${GREEN}✅ Cloud Run 재배포 완료${NC}"
echo ""

# Firebase 재배포
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  Firebase 재배포"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

read -p "Firebase를 재배포하시겠습니까? (yes/no): " DEPLOY_FIREBASE

if [ "$DEPLOY_FIREBASE" == "yes" ]; then
    echo "🔥 Firebase 배포 중..."
    firebase deploy --only hosting --quiet
    echo -e "${GREEN}✅ Firebase 재배포 완료${NC}"
else
    echo "⏭️  Firebase 재배포 건너뜀"
fi

echo ""

# 복구 완료
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 복구 완료"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 복구 결과:"
echo "   Git: v50.3.0-VERIFIED"
echo "   Docker: $V50_IMAGE"
echo "   Cloud Run: https://lawmadi-os-v50-938146962157.asia-northeast3.run.app"
echo "   Firebase: https://lawmadi-db.web.app"
echo ""
echo "백업된 브랜치: $BACKUP_BRANCH"
echo "   → git checkout $BACKUP_BRANCH (복구 전 상태로 돌아가기)"
echo ""

# 헬스 체크
echo "🔍 헬스 체크 중..."
sleep 5
HEALTH_STATUS=$(curl -s https://lawmadi-os-v50-938146962157.asia-northeast3.run.app/health | jq -r '.status' 2>/dev/null || echo "error")

if [ "$HEALTH_STATUS" == "online" ]; then
    echo -e "${GREEN}✅ 서비스 정상 작동 중${NC}"
else
    echo -e "${YELLOW}⚠️  헬스 체크 실패 - 수동 확인 필요${NC}"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              ✅ v50 복구가 완료되었습니다 ✅                      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
