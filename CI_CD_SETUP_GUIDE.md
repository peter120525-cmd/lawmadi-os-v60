# CI/CD 파이프라인 설정 가이드

**자동 배포:** main push → Docker Build → Cloud Run + Firebase Hosting

---

## 🎯 CI/CD 흐름

```
main 브랜치 push
    ↓
GitHub Actions 트리거
    ↓
┌─────────────────────────────┐
│ Job 1: deploy-backend       │
│  1. Docker 이미지 빌드      │
│  2. Artifact Registry 푸시  │
│  3. Cloud Run 배포          │
│  4. 헬스 체크               │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Job 2: deploy-frontend      │
│  1. Firebase CLI 설치       │
│  2. Firebase Hosting 배포   │
│  3. 배포 확인               │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Job 3: notify               │
│  배포 완료 알림             │
└─────────────────────────────┘
```

---

## 📋 사전 준비사항

### 1. GCP 서비스 계정 생성

**Google Cloud Console에서:**

1. **IAM & Admin > Service Accounts**
2. **"Create Service Account"** 클릭
3. 이름: `github-actions-deployer`
4. 역할 부여:
   - `Cloud Run Admin`
   - `Storage Admin`
   - `Artifact Registry Administrator`
   - `Service Account User`
5. **"Create Key"** → JSON 선택
6. JSON 키 파일 다운로드

---

### 2. Firebase CI Token 생성

```bash
# Firebase CLI로 토큰 생성
firebase login:ci

# 출력된 토큰 복사 (예: 1//0xxx...)
```

---

### 3. GitHub Secrets 설정

**GitHub Repository > Settings > Secrets and variables > Actions**

#### 필수 Secrets (2개)

| Secret 이름 | 값 | 설명 |
|------------|-----|------|
| `GCP_SA_KEY` | `{ "type": "service_account", ... }` | GCP 서비스 계정 JSON (전체 내용) |
| `FIREBASE_TOKEN` | `1//0xxx...` | Firebase CI 토큰 |

**GCP_SA_KEY 설정:**
```bash
# 다운로드한 JSON 파일 내용 전체를 복사
cat ~/Downloads/lawmadi-db-xxxx.json
# GitHub Secrets에 붙여넣기
```

**FIREBASE_TOKEN 설정:**
```bash
# firebase login:ci 명령어 결과를 복사
# GitHub Secrets에 붙여넣기
```

---

## 🚀 배포 프로세스

### 자동 배포 (권장)

```bash
# 로컬에서 작업
git add .
git commit -m "feat: 새로운 기능 추가"
git push origin main

# GitHub Actions가 자동으로:
# 1. Docker 이미지 빌드 (약 2-3분)
# 2. Cloud Run 배포 (약 1-2분)
# 3. Firebase Hosting 배포 (약 30초)
# 총 소요 시간: 약 4-6분
```

### 수동 배포

**GitHub에서:**
1. **Actions** 탭
2. **Deploy to Cloud Run and Firebase** 선택
3. **Run workflow** 클릭
4. 브랜치 선택 (main)
5. **Run workflow** 실행

---

## 📊 배포 모니터링

### GitHub Actions 로그

**실시간 확인:**
1. GitHub Repository > **Actions** 탭
2. 최신 Workflow 클릭
3. 각 Job 로그 확인

**주요 로그:**
```
✅ Checkout code
✅ Build Docker image (2-3분)
✅ Push to Artifact Registry (1-2분)
✅ Deploy to Cloud Run (1분)
✅ Health check passed
✅ Deploy to Firebase Hosting (30초)
✅ Firebase Hosting deployed successfully
```

---

## 🔧 배포 설정

### Cloud Run 설정

**`.github/workflows/deploy.yml`에서 수정 가능:**

```yaml
--memory=2Gi           # 메모리 (512Mi, 1Gi, 2Gi, 4Gi)
--cpu=2                # CPU (1, 2, 4, 8)
--timeout=300          # 타임아웃 (초)
--concurrency=80       # 동시 요청 수
--max-instances=10     # 최대 인스턴스
```

### Firebase Hosting 설정

**`firebase.json`:**
```json
{
  "hosting": {
    "public": "frontend/public",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**"
    ]
  }
}
```

---

## ⚠️ 트러블슈팅

### 1. Docker Build 실패

**증상:** `docker build` 단계에서 실패

**해결:**
```bash
# 로컬에서 Docker 빌드 테스트
docker build -t test-image .

# Dockerfile 구문 확인
docker run --rm -i hadolint/hadolint < Dockerfile
```

### 2. Cloud Run 배포 실패

**증상:** `gcloud run deploy` 실패

**원인:**
- GCP_SA_KEY 권한 부족
- Secret Manager 접근 불가

**해결:**
```bash
# 서비스 계정 권한 확인
gcloud projects get-iam-policy lawmadi-db \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions-deployer@lawmadi-db.iam.gserviceaccount.com"

# 필요한 역할 추가
gcloud projects add-iam-policy-binding lawmadi-db \
  --member="serviceAccount:github-actions-deployer@lawmadi-db.iam.gserviceaccount.com" \
  --role="roles/run.admin"
```

### 3. Firebase 배포 실패

**증상:** `firebase deploy` 실패

**원인:**
- FIREBASE_TOKEN 만료 또는 잘못됨
- 프로젝트 권한 없음

**해결:**
```bash
# 새로운 토큰 생성
firebase login:ci

# 프로젝트 확인
firebase projects:list

# 토큰 테스트
firebase deploy --only hosting --token "YOUR_TOKEN"
```

### 4. 헬스 체크 실패

**증상:** `/health` 엔드포인트 응답 없음

**원인:**
- Cloud Run 서비스 시작 시간 부족
- 환경변수 미설정

**해결:**
```yaml
# deploy.yml에서 대기 시간 증가
- name: Verify deployment
  run: |
    sleep 20  # 10 → 20초로 증가
    curl -f ${{ steps.deploy.outputs.url }}/health || exit 1
```

---

## 📈 배포 히스토리

### Cloud Run

```bash
# 배포 리비전 확인
gcloud run revisions list \
  --service=lawmadi-os-v60 \
  --region=asia-northeast3

# 특정 리비전으로 롤백
gcloud run services update-traffic lawmadi-os-v60 \
  --region=asia-northeast3 \
  --to-revisions=lawmadi-os-v60-00001-abc=100
```

### Firebase Hosting

```bash
# 배포 히스토리
firebase hosting:channel:list

# 이전 버전으로 롤백
firebase hosting:rollback
```

---

## 🔐 보안 설정

### GitHub Secrets 관리

**주의사항:**
- ✅ GCP_SA_KEY는 최소 권한 원칙 적용
- ✅ FIREBASE_TOKEN은 정기적으로 갱신 (6개월마다)
- ✅ Secrets는 절대 로그에 노출되지 않음
- ✅ Pull Request에서는 Secrets 접근 불가

**Secrets 갱신:**
```bash
# GCP 서비스 계정 키 재생성
gcloud iam service-accounts keys create new-key.json \
  --iam-account=github-actions-deployer@lawmadi-db.iam.gserviceaccount.com

# Firebase 토큰 재생성
firebase login:ci

# GitHub Secrets 업데이트
# (GitHub UI에서 수동 업데이트)
```

---

## 📝 배포 체크리스트

### 배포 전
- [ ] 로컬 테스트 완료
- [ ] Docker 이미지 빌드 테스트
- [ ] requirements.txt 최신화
- [ ] config.json 버전 업데이트

### 배포 후
- [ ] Cloud Run URL 접속 확인
- [ ] Firebase Hosting URL 접속 확인
- [ ] /health 엔드포인트 확인
- [ ] 주요 기능 테스트
- [ ] 로그 모니터링 (첫 1시간)

---

## 🎯 고급 기능

### 1. 환경별 배포 (Staging/Production)

```yaml
# .github/workflows/deploy-staging.yml
on:
  push:
    branches:
      - develop  # develop 브랜치는 staging 환경
```

### 2. 조건부 배포

```yaml
# 특정 경로 변경 시만 배포
on:
  push:
    branches:
      - main
    paths:
      - 'main.py'
      - 'requirements.txt'
      - 'Dockerfile'
      - 'frontend/**'
```

### 3. Slack 알림 통합

```yaml
- name: Send Slack notification
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 📊 성능 최적화

### Docker 이미지 크기 최적화

```dockerfile
# Multi-stage build 사용
FROM python:3.11-slim as builder
# ... 빌드 단계 ...

FROM python:3.11-slim
# ... 최종 이미지 ...
```

### 빌드 캐싱

```yaml
- name: Cache Docker layers
  uses: actions/cache@v3
  with:
    path: /tmp/.buildx-cache
    key: ${{ runner.os }}-buildx-${{ github.sha }}
```

---

## 📞 지원

**문제 발생 시:**
1. GitHub Actions 로그 확인
2. Cloud Run 로그 확인: `gcloud run services logs tail lawmadi-os-v60`
3. Firebase 콘솔 확인
4. 이 문서의 트러블슈팅 섹션 참조

**연락처:**
- GitHub Issues: https://github.com/YOUR_ORG/lawmadi-os-v50/issues
- Documentation: CI_CD_SETUP_GUIDE.md

---

**작성자:** Claude Code
**최종 업데이트:** 2026-02-13
**버전:** v1.0
