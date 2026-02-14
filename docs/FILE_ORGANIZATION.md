# Lawmadi OS v60 — 파일 조직 정책

**최종 업데이트**: 2026-02-14

---

## 디렉토리 구조 원칙

### 1. 루트 디렉토리 (최소화)
루트에는 **시스템 필수 파일**만 유지합니다.

#### 허용되는 파일
```
✅ main.py              — 메인 애플리케이션
✅ config.json          — 시스템 설정
✅ leaders.json         — 60 리더 레지스트리
✅ requirements.txt     — Python 의존성
✅ Dockerfile           — 컨테이너 빌드 명세
✅ firebase.json        — Firebase Hosting 설정
✅ README.md            — 공개 시스템 문서
✅ license              — 독점 라이선스
✅ llms.txt             — LLM 참조 명세
✅ claude.md            — 개발 가이드 (Claude Code용)
✅ .env                 — 환경변수 (gitignored)
✅ .gitignore, .dockerignore, .gcloudignore
```

#### 금지되는 파일
```
❌ 테스트 스크립트 (test_*.py)       → tests/ 로 이동
❌ 문서 파일 (*.md, 가이드 등)         → docs/ 로 이동
❌ 임시 파일 (.bak, _old, _backup)    → temp/ 또는 삭제
❌ 로그 파일 (*.log)                   → logs/ 로 자동 생성
❌ 캐시 파일 (__pycache__, *.pyc)     → .gitignore 처리
```

---

## 2. 자동 생성 디렉토리

다음 디렉토리는 **런타임 시 자동 생성**됩니다 (`main.py` 부팅 시).

| 디렉토리 | 용도 | .gitignore |
|---------|------|-----------|
| `temp/` | 임시 파일, 테스트 결과 | ✅ (내용물만) |
| `logs/` | 애플리케이션 로그 | ✅ (내용물만) |
| `uploads/` | 사용자 업로드 문서 | ✅ (내용물만) |

### .gitkeep 파일
각 디렉토리에 `.gitkeep` 파일을 두어 **디렉토리 구조는 Git에 보존**하되 **내용물은 무시**합니다.

```bash
temp/.gitkeep       # Git에 추적됨
temp/test_*.log     # .gitignore로 무시됨
```

---

## 3. 코드 디렉토리

| 디렉토리 | 역할 |
|---------|------|
| `core/` | 핵심 시스템 모듈 (security, law_selector, etc.) |
| `connectors/` | 외부 API 클라이언트 (DRF, DB, etc.) |
| `agents/` | Swarm 에이전트 (swarm_manager, clevel_handler, etc.) |
| `engines/` | 처리 엔진 (temporal_v2, etc.) |
| `services/` | 비즈니스 로직 서비스 |
| `prompts/` | 시스템 프롬프트 (constitution.yaml, etc.) |

---

## 4. 정적 자산

| 디렉토리 | 역할 |
|---------|------|
| `frontend/` | 프론트엔드 HTML/CSS/JS (Firebase Hosting 소스) |
| `static/` | 정적 파일 (이미지, 비디오 등) |

---

## 5. 문서 및 테스트

| 디렉토리 | 역할 | 규칙 |
|---------|------|------|
| `docs/` | 모든 문서 파일 | 아카이브는 `docs/archive/` |
| `tests/` | 모든 테스트 코드 | `unit/`, `integration/`, `e2e/` 하위 구조 |
| `scripts/` | 유틸리티 스크립트 | 배포, 마이그레이션 등 |

---

## 6. 파일 이동 이력 (2026-02-14 정리)

### 문서 파일 → `docs/archive/`
```
CI_CD_COMPLETE.md
CI_CD_SETUP_GUIDE.md
DEPLOYMENT_GUIDE_V60.md
DEPLOYMENT_SUCCESS_V60.md
PROJECT_STRUCTURE.md
QUICK_CICD_SETUP.md
SYSTEM_CHECK_REPORT_V60.md
SYSTEM_INTEGRITY_FINAL.md
SYSTEM_INTEGRITY_REPORT.md
V50_VS_V60_COMPARISON.md
V60_DOCUMENT_UPLOAD_SUMMARY.md
```

### 테스트 파일 → `tests/`
```
test_system_integrity.py
```

### 삭제됨
```
__pycache__/ (전체)
*.pyc (전체)
```

---

## 7. 디렉토리 자동 생성 로직

### main.py (부팅 시)
```python
# [v60] 필수 디렉토리 자동 생성
for directory in ["temp", "logs", "uploads"]:
    Path(directory).mkdir(exist_ok=True)
```

### Dockerfile
```dockerfile
# 6. 필수 디렉토리 생성 (v60: temp, logs, uploads)
RUN mkdir -p temp logs uploads
```

---

## 8. .gitignore 정책

### 디렉토리 무시 패턴
```gitignore
# 내용물만 무시, 디렉토리 구조는 보존
uploads/*
!uploads/.gitkeep
temp/*
!temp/.gitkeep
logs/*
!logs/.gitkeep

# 완전히 무시
__pycache__/
.venv/
venv/
cache/
```

---

## 9. 테스트/임시 파일 생성 규칙

### Python 테스트 코드
```python
# ✅ 올바른 방법: temp/ 사용
output_path = Path("temp") / f"test_result_{timestamp}.json"

# ❌ 잘못된 방법: 루트에 생성
output_path = Path(f"test_result_{timestamp}.json")
```

### 로그 파일
```python
# ✅ 올바른 방법: logs/ 사용
logger.addHandler(logging.FileHandler("logs/app.log"))

# ❌ 잘못된 방법: 루트에 생성
logger.addHandler(logging.FileHandler("app.log"))
```

---

## 10. 정리 유지 관리

### 주기적 점검
```bash
# 루트에 불필요한 파일 확인
ls -1 /workspaces/lawmadi-os-v50/*.{md,log,txt,bak} 2>/dev/null | grep -v "README\|claude\|llms\|requirements"

# __pycache__ 제거
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete

# temp/ 정리 (30일 이상 된 파일)
find temp/ -type f -mtime +30 -delete
```

---

**정리 실행일**: 2026-02-14  
**정리 책임자**: Claude Sonnet 4.5  
**다음 점검**: 메이저 릴리스 전 또는 월 1회
