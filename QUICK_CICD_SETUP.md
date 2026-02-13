# ⚡ CI/CD 빠른 설정 가이드 (5분)

**목표:** GitHub에 push하면 자동으로 Cloud Run + Firebase 배포

---

## 🚀 5분 설정

### Step 1: GCP 서비스 계정 생성 (2분)

```bash
# 1. 프로젝트 설정
gcloud config set project lawmadi-db

# 2. 서비스 계정 생성
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"

# 3. 역할 부여
gcloud projects add-iam-policy-binding lawmadi-db \
  --member="serviceAccount:github-actions-deployer@lawmadi-db.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding lawmadi-db \
  --member="serviceAccount:github-actions-deployer@lawmadi-db.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding lawmadi-db \
  --member="serviceAccount:github-actions-deployer@lawmadi-db.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding lawmadi-db \
  --member="serviceAccount:github-actions-deployer@lawmadi-db.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# 4. JSON 키 생성
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@lawmadi-db.iam.gserviceaccount.com

# 5. JSON 키 내용 출력 (복사)
cat github-actions-key.json
```

---

### Step 2: Firebase 토큰 생성 (1분)

```bash
# Firebase 로그인 후 CI 토큰 생성
firebase login:ci

# 출력된 토큰 복사
# 예: 1//0xxx...
```

---

### Step 3: GitHub Secrets 설정 (2분)

**GitHub Repository > Settings > Secrets and variables > Actions > New repository secret**

#### Secret 1: GCP_SA_KEY
- Name: `GCP_SA_KEY`
- Value: `github-actions-key.json` 파일의 전체 내용 붙여넣기

#### Secret 2: FIREBASE_TOKEN
- Name: `FIREBASE_TOKEN`
- Value: `firebase login:ci` 결과 토큰 붙여넣기

---

### Step 4: 테스트 (1분)

```bash
# 간단한 변경 후 push
git add .
git commit -m "test: CI/CD 테스트"
git push origin main

# GitHub Actions 확인
# Repository > Actions 탭에서 실행 상황 확인
```

---

## ✅ 설정 완료!

이제 `main` 브랜치에 push할 때마다 자동으로 배포됩니다:

1. **Docker 이미지 빌드** (2-3분)
2. **Cloud Run 배포** (1-2분)
3. **Firebase Hosting 배포** (30초)

**총 소요 시간:** 4-6분

---

## 🎯 확인 사항

### GitHub Actions 로그
- Repository > Actions > 최신 Workflow 클릭
- 각 단계별 로그 확인

### 배포 URL
- **Cloud Run:** https://lawmadi-os-v60-uzqkp6kadq-du.a.run.app
- **Firebase:** https://lawmadi-db.web.app

---

## 🔧 문제 발생 시

### Docker Build 실패
```bash
# 로컬에서 테스트
docker build -t test .
```

### Cloud Run 배포 실패
```bash
# 권한 확인
gcloud projects get-iam-policy lawmadi-db | grep github-actions-deployer
```

### Firebase 배포 실패
```bash
# 토큰 재생성
firebase login:ci
# GitHub Secret 업데이트
```

---

## 📝 다음 단계

- **상세 가이드:** `CI_CD_SETUP_GUIDE.md` 참조
- **트러블슈팅:** 문제 발생 시 상세 가이드 확인
- **고급 설정:** Staging 환경, Slack 알림 등

---

**소요 시간:** 5분
**난이도:** 쉬움
**유지보수:** 자동
