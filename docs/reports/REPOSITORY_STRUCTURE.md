# 📁 Lawmadi OS v50 - 저장소 구조

**정리 일자:** 2026-02-14
**버전:** v50.3.0-VERIFIED

---

## 🎯 프로덕션 필수 파일

### 핵심 애플리케이션
```
main.py                  # FastAPI 메인 애플리케이션
config.json              # 시스템 설정
leaders.json             # 60인 리더 정보
requirements.txt         # Python 의존성
```

### 배포 관련
```
Dockerfile               # Docker 이미지 빌드
firebase.json            # Firebase Hosting 설정
.firebaserc              # Firebase 프로젝트 설정
.env                     # 환경변수 (Git 제외)
```

### 문서
```
README.md                # 프로젝트 설명
claude.md                # Claude Code 시스템 문서
llms.txt                 # LLM 친화적 문서
DEPLOYMENT_SUCCESS_V50.3.0.md  # 최신 배포 보고서
```

---

## 📂 프로덕션 디렉토리

### Backend 코드
```
agents/                  # AI 에이전트 (Swarm, C-Level)
├── swarm_orchestrator.py
├── swarm_manager.py
└── clevel_handler.py

connectors/              # 외부 API 연결
├── drf_client.py       # DRF API 클라이언트
├── db_client_v2.py     # PostgreSQL 클라이언트
└── validator.py        # 응답 검증기

core/                    # 핵심 비즈니스 로직
├── gate_kernel.py      # 메인 커널
├── law_selector.py     # 법률 선택기
├── evidence_explainer.py
└── parser.py

engines/                 # 처리 엔진
├── response_verifier.py # Claude API 검증
└── temporal_v2.py      # 시간축 분석

services/                # 서비스 레이어
└── search_service.py   # 검색 서비스 Facade

prompts/                 # 프롬프트 템플릿
└── system_prompts.py
```

### Frontend 코드
```
frontend/                # HTML/CSS/JS (Firebase)
├── index.html          # 메인 페이지 (프리미엄 UI)
├── clevel.html         # C-Level 페이지
├── leaders.html        # 리더스 페이지
├── app.js              # 애플리케이션 로직
├── style.css           # 스타일시트
└── leaders.json        # 리더스 데이터
```

---

## 📦 Archive 폴더 (비필수)

개발 과정에서 생성된 파일들을 보관합니다.
상세 내용은 [`archive/README.md`](archive/README.md) 참조.

```
archive/
├── tests/              (44개) - 모든 테스트 파일
├── reports/            (26개) - 개발 과정 보고서
├── scripts/            (10개) - 유틸리티 스크립트
├── backups/            (8개)  - 백업 파일
├── results/            (3개)  - 테스트 결과
└── logs/               (3개)  - 서버 로그
```

---

## 🚀 배포 아키텍처

```
GitHub Repository
    │
    ├─→ Docker Build → Artifact Registry → Cloud Run
    │                                        (Backend API)
    │
    └─→ Firebase Deploy → Firebase Hosting
                          (Frontend)
```

---

## 📊 저장소 통계

### 프로덕션 코드
- **Python 파일:** 25개 (core, agents, connectors, engines, services)
- **Frontend 파일:** 6개 (HTML, CSS, JS)
- **설정 파일:** 4개 (config.json, Dockerfile, firebase.json, etc.)

### Archive (개발 히스토리)
- **테스트 파일:** 44개
- **보고서:** 26개
- **스크립트:** 10개
- **백업/로그:** 14개

### 총계
- **필수 파일:** ~35개
- **보관 파일:** ~95개
- **총 디렉토리:** 12개

---

## 🔍 주요 파일 설명

### main.py (77,021 bytes)
FastAPI 기반 메인 애플리케이션:
- `/ask` - Gemini + SSOT 9개 통합
- `/health` - 헬스 체크
- Swarm 60인 리더 협업 시스템
- C-Level 삼권 체계 (CSO/CCO/CTO)

### config.json (7,599 bytes)
시스템 설정:
- SSOT 9개 레지스트리
- Dual SSOT 설정
- API 엔드포인트
- 캐시 설정

### claude.md (27,125 bytes)
Claude Code 시스템 문서:
- SSOT 10개 정의
- 응답 프레임워크 (5단계)
- C-Level 삼권 체계
- 개발 가이드라인

### frontend/index.html (42,684 bytes)
프리미엄 메인 페이지:
- CSS 애니메이션 (fadeInDown, fadeInUp, scaleIn)
- 17개 그라디언트 효과
- 3D 호버 트랜스폼
- "Lawmadi OS" 브랜딩

---

## 🛠️ 개발 워크플로우

### 1. 로컬 개발
```bash
# 환경 설정
cp .env.example .env
pip install -r requirements.txt

# 서버 실행
python main.py
```

### 2. 테스트 (Archive에서)
```bash
# SSOT 테스트
python archive/tests/test_ssot_phase4_id_based.py

# 검증 시스템 테스트
python archive/tests/test_verification_system.py
```

### 3. 배포
```bash
# Docker 빌드
docker build -t lawmadi-os:latest .

# Firebase 배포
firebase deploy --only hosting

# Cloud Run 배포
gcloud run deploy lawmadi-os-v50 --image=...
```

---

## 📌 참고사항

### Git 관리
- `.gitignore` - Python 캐시, 환경변수, 로그 제외
- `.dockerignore` - Archive 폴더 제외
- Archive 폴더는 커밋되지만 배포 시 제외

### 보안
- API 키는 `.env` 파일에 저장 (Git 제외)
- Cloud Run 환경변수로 주입
- Firebase는 공개 호스팅 (정적 파일)

### 모니터링
- Cloud Run: 자동 로깅 및 메트릭
- Firebase: Analytics 및 Hosting 메트릭
- DB: PostgreSQL 로그

---

**정리 작업:** Claude Code (Sonnet 4.5)
**마지막 업데이트:** 2026-02-14
