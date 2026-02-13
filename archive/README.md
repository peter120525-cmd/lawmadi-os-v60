# 📦 Archive 폴더

이 폴더는 Lawmadi OS 개발 과정에서 생성된 **비필수 파일들을 보관**하는 곳입니다.
프로덕션 운영에는 필요하지 않지만, 개발 히스토리와 참고 자료로 보관됩니다.

**정리 일자:** 2026-02-14
**총 보관 파일:** 95개

---

## 📁 폴더 구조

```
archive/
├── tests/          (44개) - 모든 테스트 파일
├── reports/        (26개) - 개발 과정 보고서
├── scripts/        (9개)  - 유틸리티 스크립트
├── backups/        (8개)  - 백업 및 샘플 파일
├── results/        (3개)  - 테스트 결과 JSON
└── logs/           (3개)  - 서버 로그 파일
```

---

## 🧪 tests/ (44개)

개발 과정에서 작성된 모든 테스트 파일입니다.

### Phase별 테스트
- `test_ssot_phase1.py` - SSOT Phase 1 테스트
- `test_ssot_phase4_id_based.py` - SSOT Phase 4 (ID 기반)
- `test_phase2_*.py` - Phase 2 관련 테스트

### 기능별 테스트
- `test_drf_*.py` - DRF API 연동 테스트
- `test_data_go_kr_*.py` - data.go.kr API 테스트
- `test_law_*.py` - 법령 검색 테스트
- `test_verification_system.py` - Claude 검증 시스템

### 통합 테스트
- `test_main_*.py` - 메인 엔드포인트 테스트
- `test_live_deployment.py` - 라이브 배포 테스트
- `test_all_targets.py` - 전체 타겟 테스트

---

## 📄 reports/ (26개)

개발 과정의 주요 마일스톤 보고서입니다.

### CI/CD 보고서
- `FINAL_CI_CD_SUCCESS.md` - 최종 CI/CD 파이프라인 완료
- `FIREBASE_DEPLOYMENT_SUCCESS.md` - Firebase 배포 보고서
- `DEPLOYMENT_REPORT.md` - 배포 상세 보고서

### Phase별 완료 보고서
- `PHASE3_SUCCESS.md` - Phase 3 완료 (법령용어)
- `PHASE4_COMPLETE_REPORT.md` - Phase 4 완료 (90% SSOT)

### SSOT 구현 보고서
- `SSOT_PHASE1_IMPLEMENTATION_REPORT.md` - Phase 1 (5개 SSOT)
- `SSOT_PHASE2_REPORT.md` - Phase 2 (자치법규)
- `SSOT_PHASE3_REPORT.md` - Phase 3 (법령용어)
- `SSOT_FINAL_REPORT.md` - 전체 SSOT 최종 보고서
- `FINAL_SSOT_STATUS.md` - SSOT 상태 요약

### 기술 문서
- `DRF_CONNECTION_SUCCESS.md` - DRF API 연동 성공
- `DATA_GO_KR_CONNECTION_REPORT.md` - data.go.kr 연동 보고서
- `SWARM_IMPLEMENTATION_SUCCESS.md` - Swarm 시스템 구현
- `CLEVEL_SYSTEM_SUMMARY.md` - C-Level 시스템 요약

### 가이드
- `API_KEY_GUIDE.md` - API 키 설정 가이드
- `QUICK_FIX_GUIDE.md` - 빠른 수정 가이드
- `SSOT_QUICK_REFERENCE.md` - SSOT 빠른 참조

### 분석 보고서
- `LAWMADI_PHILOSOPHY_REPORT.md` - Lawmadi 철학 보고서
- `CORE_FUNCTIONS_ANALYSIS.md` - 핵심 기능 분석
- `HOMEPAGE_EVALUATION.md` - 홈페이지 평가

---

## 🛠️ scripts/ (9개)

개발 및 디버깅에 사용된 유틸리티 스크립트입니다.

### 분석 도구
- `analyze_law_response.py` - 법령 응답 분석
- `db_diagnostics.py` - DB 진단 도구
- `inspect_decc_response.py` - 행정심판례 응답 검사

### 시스템 체크
- `final_system_check.py` - 최종 시스템 점검
- `final_system_check_v2.py` - 최종 시스템 점검 v2

### 유틸리티
- `quick_stats.py` - 빠른 통계
- `check_prec_structure.py` - 판례 구조 확인
- `ui_server.py` - UI 서버 (개발용)
- `setup_law_api_keys.sh` - API 키 설정 스크립트

---

## 💾 backups/ (8개)

백업 파일과 샘플 데이터입니다.

### 코드 백업
- `main_20260211.py` - main.py 백업 (2026-02-11)
- `config.json.bak.20260211_043108` - config.json 백업
- `db_client.py.bak.20260202_071453` - db_client.py 백업
- `drf_client.py.bak.20260211_044833` - drf_client.py 백업

### 프론트엔드 백업
- `index_backup_20260212_150804.html` - 메인 페이지 백업
- `index_improved.html` - 개선된 메인 페이지

### 샘플 데이터
- `law_response_sample.json` - 법령 API 응답 샘플

---

## 📊 results/ (3개)

테스트 실행 결과 파일입니다.

- `all_targets_test.json` - 전체 타겟 테스트 결과
- `drf_test_results.json` - DRF API 테스트 결과
- `prec_test_results.json` - 판례 검색 테스트 결과

---

## 📝 logs/ (3개)

서버 실행 로그 파일입니다.

- `server.log` - 메인 서버 로그
- `server_new.log` - 새 서버 로그
- `test_results.log` - 테스트 결과 로그

---

## 🔍 파일 찾기

### 특정 Phase 보고서 찾기
```bash
ls archive/reports/PHASE*.md
ls archive/reports/SSOT_PHASE*.md
```

### 특정 기능 테스트 찾기
```bash
ls archive/tests/test_drf*.py        # DRF 관련
ls archive/tests/test_data_go_kr*.py # data.go.kr 관련
ls archive/tests/test_ssot*.py       # SSOT 관련
```

### 백업 파일 확인
```bash
ls archive/backups/*.bak.*
```

---

## 📌 참고사항

### 프로덕션에 필요한 파일
프로덕션 운영에 필요한 파일은 **루트 디렉토리**에 있습니다:
- `main.py` - 메인 애플리케이션
- `config.json` - 시스템 설정
- `requirements.txt` - Python 의존성
- `Dockerfile` - 컨테이너 빌드
- `claude.md` - 시스템 문서
- `README.md` - 프로젝트 설명

### Archive 폴더 관리
- 이 폴더는 Git에 커밋되지만, 배포 시 제외됩니다 (.dockerignore)
- 필요시 언제든 파일을 루트로 복사하여 사용 가능
- 오래된 파일은 정기적으로 삭제 가능

---

**정리 작업:** Claude Code (Sonnet 4.5)
**정리 일자:** 2026-02-14 02:45:00 (KST)
