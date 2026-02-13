# 🔒 Lawmadi OS v50 백업 정보

**백업 일자:** 2026-02-14 02:52:00 (KST)
**버전:** v50.3.0-VERIFIED
**다음 버전:** v60 (업그레이드 예정)

---

## 📦 백업 위치

### 1. Git 태그
```bash
태그: v50.3.0-VERIFIED
GitHub: https://github.com/peter120525-cmd/lawmadi-os-v50/releases/tag/v50.3.0-VERIFIED
```

### 2. Google Cloud Storage
```bash
버킷: gs://lawmadi-backups-v50/
파일: lawmadi-os-v50.3.0-VERIFIED-20260213-175152.tar.gz
크기: 364KB
```

### 3. Docker 이미지
```bash
저장소: asia-northeast3-docker.pkg.dev/lawmadi-db/lawmadi-images
이미지: lawmadi-os:v50-stable
태그: v50.3.0, v50-stable
SHA256: 4b703e5fb6cdf1b8927581051539d900a11b30d930d96027313029176fbae9a9
```

### 4. Cloud Run
```bash
서비스: lawmadi-os-v50
리전: asia-northeast3
URL: https://lawmadi-os-v50-938146962157.asia-northeast3.run.app
리비전: lawmadi-os-v50-00083-xq6 (v50 배포)
```

### 5. Firebase Hosting
```bash
프로젝트: lawmadi-db
URL: https://lawmadi-db.web.app
배포 시각: 2026-02-14 02:35:00
```

---

## 🔄 복구 방법

### 방법 1: 자동 복구 스크립트 (권장)
```bash
# v60에서 v50으로 롤백
bash RESTORE_V50.sh
```

복구 스크립트는 다음 작업을 자동으로 수행합니다:
1. Git 저장소를 v50.3.0-VERIFIED 태그로 복원
2. GCS 백업 복원 (선택)
3. Docker 이미지를 v50-stable로 변경
4. Cloud Run 재배포
5. Firebase 재배포 (선택)

### 방법 2: 수동 복구 (단계별)

#### 2.1 Git 저장소 복원
```bash
# 현재 상태 백업
git checkout -b backup-before-restore
git add -A
git commit -m "백업: v50 복구 전"

# v50 태그로 복원
git checkout v50.3.0-VERIFIED
```

#### 2.2 GCS에서 코드 복원 (선택)
```bash
# 백업 파일 다운로드
gcloud storage cp \
  gs://lawmadi-backups-v50/lawmadi-os-v50.3.0-VERIFIED-20260213-175152.tar.gz \
  /tmp/restore-v50.tar.gz

# 압축 해제
tar -xzf /tmp/restore-v50.tar.gz -C /workspaces/lawmadi-os-v50/
```

#### 2.3 Cloud Run 재배포
```bash
gcloud run deploy lawmadi-os-v50 \
  --image=asia-northeast3-docker.pkg.dev/lawmadi-db/lawmadi-images/lawmadi-os:v50-stable \
  --region=asia-northeast3 \
  --platform=managed \
  --port=8080 \
  --memory=2Gi \
  --cpu=2 \
  --max-instances=10 \
  --allow-unauthenticated
```

#### 2.4 Firebase 재배포
```bash
firebase deploy --only hosting
```

---

## 🔍 백업 검증

### Git 태그 확인
```bash
git tag -l "v50*"
git show v50.3.0-VERIFIED
```

### GCS 백업 확인
```bash
gcloud storage ls gs://lawmadi-backups-v50/
gcloud storage cat gs://lawmadi-backups-v50/lawmadi-os-v50.3.0-VERIFIED-20260213-175152.tar.gz | tar -tzf - | head -20
```

### Docker 이미지 확인
```bash
gcloud artifacts docker images list \
  asia-northeast3-docker.pkg.dev/lawmadi-db/lawmadi-images/lawmadi-os \
  --filter="tags:v50-stable"
```

### Cloud Run 상태 확인
```bash
gcloud run services describe lawmadi-os-v50 --region=asia-northeast3
curl https://lawmadi-os-v50-938146962157.asia-northeast3.run.app/health
```

---

## 📊 v50 시스템 사양

### 핵심 기능
- SSOT 커버리지: 90% (9/10 sources)
- 응답 프레임워크: C-Level 삼권 체계 + 5단계
- 자동 검증: Claude API 통합
- UI/UX: 프리미엄 애니메이션 + 그라디언트
- 브랜딩: "Lawmadi OS" 통일

### 기술 스택
```
Backend:
  - Python 3.10
  - FastAPI + Uvicorn
  - Google Gemini Pro
  - Claude API (검증)
  - PostgreSQL (Cloud SQL)

Frontend:
  - HTML5/CSS3/JavaScript
  - Firebase Hosting
  - CSS 애니메이션

Infrastructure:
  - Cloud Run (Backend)
  - Firebase Hosting (Frontend)
  - Artifact Registry (Docker)
  - Cloud Storage (백업)
```

### 배포 상태
```
Backend:
  URL: https://lawmadi-os-v50-938146962157.asia-northeast3.run.app
  Region: asia-northeast3
  Memory: 2Gi
  CPU: 2 vCPU
  Max Instances: 10

Frontend:
  URL: https://lawmadi-db.web.app
  CDN: Firebase Global CDN
  HTTPS: 자동 인증서
```

---

## ⚠️ v60 업그레이드 시 주의사항

### 업그레이드 전 체크리스트
- [ ] v50 백업 완료 확인 (Git + GCS + Docker)
- [ ] 복구 스크립트 테스트 (RESTORE_V50.sh)
- [ ] 현재 서비스 상태 기록
- [ ] 롤백 계획 수립
- [ ] 사용자 공지 (다운타임 예상 시)

### 롤백 시나리오
1. **즉시 롤백 (긴급)**: `bash RESTORE_V50.sh` → 5분 내 복구
2. **부분 롤백**: Cloud Run만 v50 이미지로 변경
3. **완전 롤백**: Git + Cloud Run + Firebase 전체 복원

### 백업 보관 기간
- Git 태그: 영구 보관
- GCS 백업: 90일 (자동 삭제 정책)
- Docker 이미지: 영구 보관
- Cloud Run 리비전: 최근 10개 자동 보관

---

## 📚 관련 문서

- `RESTORE_V50.sh` - 자동 복구 스크립트
- `REPOSITORY_STRUCTURE.md` - 저장소 구조
- `DEPLOYMENT_SUCCESS_V50.3.0.md` - v50 배포 보고서
- `FINAL_CI_CD_SUCCESS.md` - CI/CD 파이프라인
- `claude.md` - 시스템 문서

---

## 🔐 보안 정보

### 환경변수 (복구 시 필요)
```bash
SOFT_MODE=true
SWARM_MULTI=true
LAWGO_DRF_OC=choepeter
GEMINI_KEY=AIzaSyB...
ANTHROPIC_API_KEY=sk-ant...
```

**⚠️ 주의:** 환경변수는 `.env` 파일에 별도 보관 (Git 제외)

### 접근 권한
- GCS 버킷: lawmadi-db 프로젝트 소유자
- Artifact Registry: lawmadi-db 프로젝트 소유자
- Cloud Run: IAM 권한 필요
- Firebase: Firebase 프로젝트 소유자

---

## 📞 문제 발생 시

### 복구 실패 시
1. `RESTORE_V50.sh` 로그 확인
2. 수동 복구 단계별 실행
3. GCS 백업에서 직접 복원

### 서비스 장애 시
1. Cloud Run 로그 확인: `gcloud run services logs read lawmadi-os-v50`
2. Firebase 상태 확인: Firebase Console
3. 긴급 롤백: `bash RESTORE_V50.sh`

---

**백업 담당:** Claude Code (Sonnet 4.5)
**백업 일자:** 2026-02-14 02:52:00 (KST)
**다음 점검:** v60 업그레이드 완료 후
