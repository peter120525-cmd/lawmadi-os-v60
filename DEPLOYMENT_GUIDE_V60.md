# Lawmadi OS v60 배포 가이드

**버전:** v60.0.0
**작성일:** 2026-02-13
**배포 순서:** 로컬 테스트 → Cloud Run → Firebase Hosting

---

## 📋 사전 준비사항

### 1. 필수 도구 확인
```bash
# gcloud CLI 설치 확인
gcloud --version

# Firebase CLI 설치 확인
firebase --version

# 프로젝트 확인
gcloud config get-value project
```

### 2. 환경변수 시크릿 설정 (Google Cloud Secret Manager)

**필수 시크릿:**
```bash
# Gemini API Key
gcloud secrets create GEMINI_API_KEY --data-file=- <<< "your-api-key"

# 국가법령정보센터 API Key
gcloud secrets create LAWGO_DRF_OC --data-file=- <<< "your-api-key"

# Anthropic API Key (Claude)
gcloud secrets create ANTHROPIC_API_KEY --data-file=- <<< "your-api-key"

# Database URL
gcloud secrets create DATABASE_URL --data-file=- <<< "your-db-url"
```

**권한 부여:**
```bash
PROJECT_NUMBER=$(gcloud projects describe lawmadi-db --format="value(projectNumber)")

gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding LAWGO_DRF_OC \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding DATABASE_URL \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 🚀 배포 프로세스

### Step 1: 로컬 테스트 ✅ (완료)

```bash
# 서버 시작
uvicorn main:app --reload --port 8080

# 브라우저 테스트
open http://localhost:8080

# 주요 기능 확인:
# - 법률 질문 (/ask)
# - 문서 업로드 (v60 신규)
# - 60 Leaders 페이지
```

**확인 사항:**
- [x] 메인 페이지 로드
- [x] /health 엔드포인트 응답
- [x] 문서 업로드 UI 표시
- [x] 법률 질문 정상 작동

---

### Step 2: Cloud Run 배포

#### 방법 1: 자동 배포 스크립트 (권장)

```bash
# 배포 스크립트 실행
./scripts/deploy_cloud_run_v60.sh
```

#### 방법 2: 수동 배포

```bash
# 1. 프로젝트 설정
gcloud config set project lawmadi-db

# 2. Cloud Build로 이미지 빌드
gcloud builds submit --tag gcr.io/lawmadi-db/lawmadi-os-v60 .

# 3. Cloud Run 배포
gcloud run deploy lawmadi-os-v60 \
  --image gcr.io/lawmadi-db/lawmadi-os-v60 \
  --platform managed \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 80 \
  --max-instances 10 \
  --set-env-vars "PORT=8080" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,LAWGO_DRF_OC=LAWGO_DRF_OC:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest"

# 4. 서비스 URL 확인
gcloud run services describe lawmadi-os-v60 \
  --region asia-northeast3 \
  --format 'value(status.url)'
```

**배포 시간:** 약 5-7분

**확인 사항:**
```bash
# 헬스 체크
SERVICE_URL=$(gcloud run services describe lawmadi-os-v60 --region asia-northeast3 --format 'value(status.url)')
curl $SERVICE_URL/health

# 메트릭 확인
curl $SERVICE_URL/metrics
```

---

### Step 3: 데이터베이스 마이그레이션 (선택적)

Cloud Run 서비스가 실행된 후:

```bash
# Cloud Run 인스턴스에서 실행
gcloud run services update lawmadi-os-v60 \
  --region asia-northeast3 \
  --command "python,scripts/run_migration.py"

# 또는 로컬에서 실행 (DATABASE_URL 설정 필요)
python scripts/run_migration.py
```

**확인:**
```sql
-- PostgreSQL에서 확인
SELECT table_name FROM information_schema.tables
WHERE table_name = 'uploaded_documents';
```

---

### Step 4: Firebase Hosting 업데이트

#### 4.1 프론트엔드 파일 확인

```bash
# frontend/public/ 폴더 확인
ls -la frontend/public/

# 필수 파일:
# - index.html
# - leaders.html (선택)
# - clevel.html (선택)
```

#### 4.2 Firebase 배포

```bash
# Firebase 로그인 (최초 1회)
firebase login

# 프로젝트 선택
firebase use lawmadi-db

# 배포
firebase deploy --only hosting

# 배포 완료 후 URL 확인
# https://lawmadi-db.web.app
```

**배포 시간:** 약 1-2분

---

## 🧪 배포 후 테스트

### 1. Cloud Run 엔드포인트 테스트

```bash
# 환경변수 설정
export SERVICE_URL="https://lawmadi-os-v60-xxxxx.a.run.app"

# 헬스 체크
curl $SERVICE_URL/health

# 법률 질문 테스트
curl -X POST $SERVICE_URL/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "전세 계약 해지 방법"}'

# 문서 업로드 테스트 (v60 신규)
curl -X POST $SERVICE_URL/upload \
  -F "file=@test_contract.pdf"
```

### 2. Firebase Hosting 테스트

```bash
# 메인 페이지
open https://lawmadi-db.web.app

# 60 Leaders
open https://lawmadi-db.web.app/leaders.html

# 브라우저에서:
# 1. 법률 질문 입력 테스트
# 2. 문서 업로드 버튼 클릭
# 3. 이미지/PDF 업로드 및 분석
```

### 3. 통합 테스트 체크리스트

- [ ] 메인 페이지 로드 정상
- [ ] 법률 질문 응답 정상
- [ ] 문서 업로드 성공
- [ ] 문서 분석 결과 표시
- [ ] 60 Leaders 페이지 정상
- [ ] 모바일 반응형 정상
- [ ] 로딩 속도 < 3초

---

## 📊 배포 모니터링

### Cloud Run 로그 확인

```bash
# 실시간 로그
gcloud run services logs tail lawmadi-os-v60 --region asia-northeast3

# 최근 로그 조회
gcloud run services logs read lawmadi-os-v60 \
  --region asia-northeast3 \
  --limit 50
```

### 메트릭 확인

```bash
# Cloud Console에서 확인
# https://console.cloud.google.com/run/detail/asia-northeast3/lawmadi-os-v60/metrics

# 또는 API로 확인
curl $SERVICE_URL/metrics
```

---

## 🔧 문제 해결

### 1. Cloud Run 배포 실패

**증상:** `ERROR: (gcloud.run.deploy) ...`

**해결:**
```bash
# 권한 확인
gcloud projects get-iam-policy lawmadi-db

# Cloud Build API 활성화
gcloud services enable cloudbuild.googleapis.com

# Cloud Run API 활성화
gcloud services enable run.googleapis.com
```

### 2. 환경변수 미설정

**증상:** `GEMINI_API_KEY not found`

**해결:**
```bash
# 시크릿 확인
gcloud secrets list

# 시크릿 재생성
gcloud secrets create GEMINI_API_KEY --data-file=-
```

### 3. 문서 업로드 실패

**증상:** `413 Request Entity Too Large`

**해결:**
- Cloud Run 메모리 증가: `--memory 4Gi`
- 파일 크기 확인: 10MB 이하

### 4. Firebase Hosting 404

**증상:** `File not found`

**해결:**
```bash
# firebase.json 확인
cat firebase.json

# public 폴더 확인
ls -la frontend/public/

# 재배포
firebase deploy --only hosting
```

---

## 🔄 롤백 절차

### Cloud Run 이전 버전으로 복원

```bash
# 이전 리비전 확인
gcloud run revisions list \
  --service lawmadi-os-v60 \
  --region asia-northeast3

# 트래픽을 이전 리비전으로 전환
gcloud run services update-traffic lawmadi-os-v60 \
  --region asia-northeast3 \
  --to-revisions REVISION_NAME=100
```

### Firebase Hosting 이전 버전으로 복원

```bash
# 배포 히스토리 확인
firebase hosting:channel:list

# 이전 버전으로 롤백
firebase hosting:clone SOURCE_SITE_ID:SOURCE_CHANNEL_ID DEST_SITE_ID:live
```

---

## 📝 배포 체크리스트

### 배포 전
- [ ] 로컬 테스트 완료
- [ ] 환경변수 시크릿 설정
- [ ] Dockerfile 최신화
- [ ] requirements.txt 최신화
- [ ] firebase.json 설정 확인

### 배포 중
- [ ] Cloud Build 성공
- [ ] Cloud Run 배포 성공
- [ ] DB 마이그레이션 실행
- [ ] Firebase Hosting 배포

### 배포 후
- [ ] 헬스 체크 성공
- [ ] 주요 엔드포인트 테스트
- [ ] 문서 업로드 테스트
- [ ] 로그 모니터링
- [ ] 성능 확인

---

## 🎯 배포 완료 기준

✅ **모든 항목 충족 시 배포 완료**

1. Cloud Run 서비스 정상 실행
2. Health check 응답 정상
3. Firebase Hosting 배포 완료
4. 문서 업로드 기능 작동
5. 법률 질문 응답 정상
6. 로그에 에러 없음

---

## 📞 지원

**문제 발생 시:**
1. 로그 확인: `gcloud run services logs`
2. 헬스 체크: `curl $SERVICE_URL/health`
3. 메트릭 확인: Cloud Console

**긴급 연락:**
- GitHub Issues
- claude.md 문서 참조

---

**작성자:** Claude Code
**버전:** v60.0.0
**최종 업데이트:** 2026-02-13
