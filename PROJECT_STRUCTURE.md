# Lawmadi OS v60 - 프로젝트 구조

**최종 업데이트:** 2026-02-13
**버전:** v60.0.0

---

## 📁 최적화된 디렉토리 구조

```
lawmadi-os-v60/
│
├── 🔧 Backend (애플리케이션 코어)
│   ├── main.py                     # FastAPI 진입점 (v60.0.0)
│   ├── config.json                 # 시스템 설정
│   ├── requirements.txt            # Python 의존성
│   │
│   ├── core/                       # 핵심 로직
│   │   ├── __init__.py
│   │   ├── response_framework.py  # C-Level 응답 프레임워크
│   │   └── verification.py        # Claude 검증 로직
│   │
│   ├── connectors/                 # 외부 API 연결
│   │   ├── __init__.py
│   │   ├── drf_client.py          # DRF API (7 SSOT)
│   │   ├── db_client_v2.py        # PostgreSQL
│   │   └── schema.sql
│   │
│   ├── services/                   # 비즈니스 로직
│   │   ├── __init__.py
│   │   └── search_service.py      # 검색 서비스
│   │
│   ├── agents/                     # Swarm 에이전트
│   │   ├── __init__.py
│   │   ├── swarm_orchestrator.py  # 60 Leaders 오케스트레이터
│   │   ├── swarm_manager.py       # Swarm 관리자
│   │   └── clevel_handler.py      # C-Level 핸들러
│   │
│   ├── engines/                    # 생성 엔진
│   │   ├── __init__.py
│   │   └── generation_engine.py   # Gemini 생성 엔진
│   │
│   └── prompts/                    # 프롬프트 템플릿
│       └── system_prompts.py
│
├── 🎨 Frontend (사용자 인터페이스)
│   ├── public/                     # 공개 정적 파일
│   │   ├── index.html             # 메인 페이지
│   │   ├── leaders.html           # 60 Leaders 페이지
│   │   │
│   │   ├── css/                   # 스타일시트
│   │   │   ├── main.css
│   │   │   └── leaders.css
│   │   │
│   │   ├── js/                    # JavaScript
│   │   │   ├── main.js
│   │   │   └── leaders.js
│   │   │
│   │   └── images/                # 일반 이미지
│   │       ├── logo.png
│   │       ├── banner.jpg
│   │       └── icons/
│   │
│   └── assets/                     # 추가 에셋
│       └── fonts/
│
├── 📦 Static (정적 리소스)
│   ├── leaders/                    # 60 Leaders 미디어
│   │   ├── images/                # 인물 이미지 ✨ NEW
│   │   │   ├── profiles/         # 프로필 사진 (고해상도)
│   │   │   │   ├── leader-001.jpg
│   │   │   │   ├── leader-002.jpg
│   │   │   │   └── ...
│   │   │   │
│   │   │   └── thumbnails/       # 썸네일 (최적화)
│   │   │       ├── leader-001-thumb.jpg
│   │   │       ├── leader-002-thumb.jpg
│   │   │       └── ...
│   │   │
│   │   └── videos/                # 인물 동영상 ✨ NEW
│   │       ├── intros/            # 소개 영상
│   │       │   ├── leader-001-intro.mp4
│   │       │   ├── leader-002-intro.mp4
│   │       │   └── ...
│   │       │
│   │       └── demos/             # 시연 영상
│   │           ├── leader-001-demo.mp4
│   │           └── ...
│   │
│   └── assets/                     # 기타 정적 파일
│       ├── documents/             # 문서 파일
│       └── downloads/             # 다운로드 가능 파일
│
├── 📊 Data (데이터 파일)
│   ├── leaders.json                # 60 Leaders 메타데이터
│   ├── prompts/                    # 프롬프트 데이터
│   └── cache/                      # 캐시 데이터 (선택)
│
├── 📚 Docs (문서)
│   ├── api/                        # API 문서
│   │   └── endpoints.md
│   │
│   ├── guides/                     # 사용 가이드
│   │   ├── deployment.md
│   │   └── configuration.md
│   │
│   ├── reports/                    # 개발 보고서
│   │   ├── V60_SSOT_EXPANSION_COMPLETE.md
│   │   └── SSOT_IMPLEMENTATION_STATUS.md
│   │
│   └── claude.md                   # 시스템 문서 (루트에도 심볼릭 링크)
│
├── 🧪 Tests (테스트)
│   ├── unit/                       # 단위 테스트
│   ├── integration/                # 통합 테스트
│   │   └── test_ssot_comprehensive.py
│   └── e2e/                        # E2E 테스트
│
├── 🛠️ Scripts (유틸리티)
│   ├── deploy.sh                   # 배포 스크립트
│   ├── backup.sh                   # 백업 스크립트
│   └── optimize_images.py          # 이미지 최적화
│
├── 🐳 Deployment (배포 설정)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .dockerignore
│   ├── firebase.json
│   └── .firebaserc
│
├── 🔒 Config (설정 파일)
│   ├── .env                        # 환경변수 (Git 제외)
│   ├── .env.example                # 환경변수 템플릿
│   ├── .gitignore
│   └── .gcloudignore
│
├── 📝 Root Files (루트 파일)
│   ├── README.md                   # 프로젝트 문서
│   ├── LICENSE
│   └── .github/
│       └── workflows/
│           └── deploy.yml
│
└── 📦 Temporary (임시 파일 - Git 제외)
    ├── uploads/                    # 사용자 업로드
    ├── temp/                       # 임시 파일
    └── logs/                       # 로그 파일
```

---

## 🎯 주요 변경사항 (v60)

### 신규 폴더

1. **`static/leaders/images/`** ✨
   - `profiles/` - 고해상도 프로필 사진 (1200x1200px)
   - `thumbnails/` - 최적화된 썸네일 (300x300px)

2. **`static/leaders/videos/`** ✨
   - `intros/` - 인물 소개 영상 (30초~1분)
   - `demos/` - 기능 시연 영상 (1~3분)

3. **`docs/`**
   - API 문서, 가이드, 보고서 통합 관리

4. **`tests/`**
   - 테스트 파일 체계적 관리

### 재구성된 폴더

1. **`frontend/` → `frontend/public/`**
   - 정적 파일을 public 하위로 이동
   - 명확한 구조화

2. **기존 개발 문서 → `docs/reports/`**
   - 보고서 파일들을 docs/reports로 이동

---

## 📋 파일 명명 규칙

### 이미지 파일
```
static/leaders/images/profiles/leader-{ID}.{ext}
static/leaders/images/thumbnails/leader-{ID}-thumb.{ext}

예시:
- leader-001.jpg (Chief Legal Officer)
- leader-002.jpg (사건분석관)
- leader-060.jpg (국제법 전문가)
```

### 동영상 파일
```
static/leaders/videos/intros/leader-{ID}-intro.mp4
static/leaders/videos/demos/leader-{ID}-demo.mp4

예시:
- leader-001-intro.mp4 (CLO 소개)
- leader-015-demo.mp4 (판례분석관 시연)
```

### 문서 파일
```
docs/{category}/{name}.md

예시:
- docs/api/endpoints.md
- docs/guides/deployment.md
- docs/reports/SSOT_IMPLEMENTATION_STATUS.md
```

---

## 🔧 FastAPI 정적 파일 서빙 설정

### main.py 추가 필요

```python
from fastapi.staticfiles import StaticFiles

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend/public"), name="frontend")

# 60 Leaders 이미지 전용 엔드포인트 (최적화)
app.mount("/leaders/images", StaticFiles(directory="static/leaders/images"), name="leader_images")
app.mount("/leaders/videos", StaticFiles(directory="static/leaders/videos"), name="leader_videos")
```

---

## 📦 권장 파일 크기

### 이미지
- **프로필 사진:** 1200x1200px, < 500KB (JPEG 85% 품질)
- **썸네일:** 300x300px, < 100KB (JPEG 80% 품질)
- **포맷:** JPEG (사진), PNG (로고/아이콘), WebP (최적화)

### 동영상
- **소개 영상:** 1080p, 30fps, < 50MB (H.264, AAC)
- **시연 영상:** 720p, 30fps, < 100MB
- **포맷:** MP4 (H.264 + AAC)

---

## 🚀 마이그레이션 가이드

### 1단계: 새 폴더 구조 생성
```bash
mkdir -p static/leaders/images/{profiles,thumbnails}
mkdir -p static/leaders/videos/{intros,demos}
mkdir -p static/assets/{documents,downloads}
mkdir -p frontend/public/{css,js,images}
mkdir -p docs/{api,guides,reports}
mkdir -p tests/{unit,integration,e2e}
mkdir -p scripts
mkdir -p uploads temp logs
```

### 2단계: 기존 파일 이동
```bash
# 프론트엔드 파일 이동
mv frontend/*.html frontend/public/
mv frontend/css frontend/public/
mv frontend/js frontend/public/ 2>/dev/null || true

# 문서 파일 이동
mv *_REPORT.md docs/reports/ 2>/dev/null || true
mv *_SUMMARY.md docs/reports/ 2>/dev/null || true
mv SSOT_*.md docs/reports/ 2>/dev/null || true
mv V60_*.md docs/reports/ 2>/dev/null || true

# 테스트 파일 이동
mv test_ssot_comprehensive.py tests/integration/
```

### 3단계: .gitignore 업데이트
```bash
echo "uploads/" >> .gitignore
echo "temp/" >> .gitignore
echo "logs/" >> .gitignore
echo "static/leaders/images/profiles/*.jpg" >> .gitignore
echo "static/leaders/videos/**/*.mp4" >> .gitignore
```

### 4단계: main.py 업데이트
- StaticFiles 마운트 추가
- 경로 수정

### 5단계: 테스트 및 배포
```bash
# 로컬 테스트
uvicorn main:app --reload

# 구조 확인
tree -L 3 -I '__pycache__|.git|node_modules'
```

---

## 📊 예상 디스크 사용량

```
항목                          크기
─────────────────────────────────────
코드 (Python/JS)              ~5MB
설정 파일                     ~1MB
프론트엔드 (HTML/CSS/JS)      ~2MB
60 Leaders 이미지 (profiles)  ~30MB (60명 × 500KB)
60 Leaders 썸네일             ~6MB (60명 × 100KB)
60 Leaders 소개 영상          ~3GB (60명 × 50MB)
60 Leaders 시연 영상          ~6GB (60명 × 100MB)
문서                          ~10MB
─────────────────────────────────────
총계 (동영상 포함)            ~9.05GB
총계 (동영상 제외)            ~54MB
```

**권장:** 동영상은 YouTube/Vimeo에 업로드하고 임베드 방식 사용

---

## 🔒 보안 고려사항

### 업로드 제한
```python
# main.py
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm"}
```

### 파일 검증
- 파일 타입 검증 (MIME type + 확장자)
- 이미지 악성코드 스캔
- 파일명 sanitization
- 크기 제한

### 접근 제어
- `/uploads/` - 인증 필요
- `/static/leaders/` - 공개
- `/logs/` - 관리자만

---

## 📝 체크리스트

- [ ] 새 폴더 구조 생성
- [ ] 기존 파일 마이그레이션
- [ ] main.py StaticFiles 설정 추가
- [ ] .gitignore 업데이트
- [ ] 이미지 최적화 스크립트 작성
- [ ] 동영상 업로드 엔드포인트 구현
- [ ] 60 Leaders 페이지 업데이트 (이미지/동영상 표시)
- [ ] 문서 업데이트
- [ ] 테스트
- [ ] 배포

---

**작성자:** Claude Code (Sonnet 4.5)
**작성 일시:** 2026-02-13
**버전:** v60.0.0
