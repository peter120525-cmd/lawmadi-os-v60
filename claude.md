# Lawmadi OS v50 — 법률 AI 의사결정 운영체제

대한민국 법률 AI 시스템. FastAPI 백엔드 + Google Gemini LLM + 국가법령정보센터(DRF) API.
60개 전문가 페르소나(Swarm Leader)가 법률 질문을 분석하고, DRF에서 실시간 검증된 법령·판례만으로 답변합니다.

## 6대 절대 원칙 — 모든 코드 변경 시 반드시 준수

1. **SSOT_FACT_ONLY** — 법률 근거는 DRF 실시간 검증 데이터만 사용. LLM이 법조문을 생성하면 안 됨
2. **ZERO_INFERENCE** — DRF 미검증 데이터로 법률·판례를 추론하거나 창작 금지
3. **FAIL_CLOSED** — 불확실하면 답변 차단. "모르면 멈춘다"가 원칙
4. **IDENTITY** — 변호사 사칭 금지. "변호사입니다", "변호사로서" 포함 시 거버넌스 차단
5. **TIMELINE_RULE** — now_utc 외 임의 날짜 생성 금지. YYYY-MM-DD, 2024-MM-DD 등 플레이스홀더 차단
6. **SOURCE_TRANSPARENCY** — 인용 법령에 법령ID + 시행일자 메타데이터 필수

## 보안 규칙 — 절대 위반 금지

- **.env 파일을 절대 커밋하지 말 것.** .gitignore에 이미 등록됨
- **API 키, 비밀번호를 코드에 하드코딩 금지.** 환경변수(os.getenv)로만 접근
- **os.getenv() 기본값에 실제 시크릿 금지.** `os.getenv("KEY", "")` 형태만 허용
- **CORS allow_origins에 `"*"` 사용 금지.** 도메인 명시 필수 (현재: lawmadi.com, lawmadi-os.web.app)
- **모든 공개 엔드포인트에 인증 필요성 검토.** /metrics, /diagnostics는 내부용
- **print() 대신 logger 사용.** core/security.py의 print문은 향후 logger로 교체 필요

## 기술 스택

- **언어**: Python 3.10+
- **프레임워크**: FastAPI + Uvicorn
- **LLM**: Google Gemini (gemini-2.5-flash-preview-09-2025)
- **외부 API**: 국가법령정보센터 DRF (law.go.kr)
- **DB**: Cloud SQL (PostgreSQL) via pg8000 + Google Cloud SQL Connector
- **배포**: Google Cloud Run (asia-northeast3) + Artifact Registry
- **CI/CD**: GitHub Actions → Docker Build → Cloud Run Deploy
- **프론트엔드**: Vanilla HTML/CSS/JS (Firebase Hosting)

## 프로젝트 구조

```
main.py                  ← FastAPI 커널. 라우팅, 스웜 리더 선택, /ask 엔드포인트
config.json              ← 시스템 설정 SSOT (아키텍처 레이어, 보안 정책, DRF 엔드포인트)
leaders.json             ← 60개 전문가 페르소나 레지스트리 (L01~L60)
prompts/constitution.yaml← 헌법: 6대 원칙, 안전 가드레일, 위기 프로토콜 정의

core/
  security.py            ← SafetyGuard (입력 필터링, Anti-Leak, Crisis 감지) + CircuitBreaker
  gate_kernel.py         ← 3-Gate Hardening Architecture (DRF 데이터 무결성 오케스트레이션)
  law_selector.py        ← Gemini 기반 지능형 법령 매칭 엔진 (L5 Jurisprudence)
  parser.py              ← 법률 텍스트 구조화 파서 (조-항-호-목)
  action_router.py       ← 사용자 선택 기반 법리 탐색 경로 결정
  case_summarizer.py     ← 판례 요약 엔진
  evidence_explainer.py  ← 증거 설명 생성기
  drf_integrity.py       ← DRF 데이터 무결성 검증
  drf_query_builder.py   ← DRF 쿼리 빌더

connectors/
  drf_client.py          ← DRF API 커넥터 (Recon→Selection→Strike 패턴, 캐시, Rate Limit)
  db_client.py           ← Cloud SQL 커넥션 풀 + 테이블 초기화
  db_client_v2.py        ← 감사 로그(audit log) 기능
  db_driver_adapter.py   ← pg8000/psycopg2 드라이버 어댑터
  validator.py           ← SHA-256 무결성 서명, 식별자 검증 (LMD-CONST-005/007/009)

engines/
  temporal_v2.py         ← 시계열 분석 엔진 (행위시법 vs 재판시법, 부칙/경과조치)
  addenda_parser.py      ← 법령 부칙 파서

agents/
  swarm_manager.py       ← 멀티에이전트 리더 선택 매니저

services/
  search_service.py      ← DRF 법령/판례 검색 서비스 래퍼

frontend/                ← HTML/CSS/JS 프론트엔드 (Firebase 배포)
.github/workflows/
  deploy.yml             ← CI/CD: main push → Docker Build → Cloud Run 배포
```

## 핵심 아키텍처 흐름 (/ask 엔드포인트)

```
사용자 질문 → Low Signal 필터 → GEMINI_KEY 확인
→ SafetyGuard.check() [CRISIS / False / True]
→ select_swarm_leader() (키워드 매칭 → L01~L60 중 선택)
→ DRF 선점 점검 (search_laws limit=1)
→ Gemini GenerativeModel (tools=[search_law_drf, search_precedents_drf])
→ validate_constitutional_compliance() (변호사 사칭, 플레이스홀더 차단)
→ 감사 로그 기록 → 응답 반환
```

## 주요 명령어

```bash
# 개발 서버
uvicorn main:app --reload --port 8080

# 도커 빌드 및 실행
docker build -t lawmadi .
docker run -p 8080:8080 --env-file .env lawmadi

# 테스트 (향후 추가)
python -m pytest tests/ -v
```

## 환경변수 (필수)

| 변수명 | 용도 | 비고 |
|--------|------|------|
| GEMINI_KEY | Google Gemini API | 미설정 시 FAIL_CLOSED |
| LAWGO_DRF_OC | 국가법령정보센터 인증키 | 기본값 금지 |
| DB_USER, DB_PASS, DB_NAME | Cloud SQL 자격증명 | |
| CLOUD_SQL_INSTANCE | Cloud SQL 인스턴스 | lawmadi-db:asia-northeast3:lawmadi-db-v1 |
| DB_DISABLED | "1"이면 DB 비활성화 | 로컬 개발 시 사용 |
| SOFT_MODE | "true"면 모듈 실패 시에도 서버 기동 | 기본값 true |
| GEMINI_MODEL | Gemini 모델명 | 기본 gemini-2.5-flash-preview-09-2025 |
| CORS_EXTRA_ORIGINS | 추가 CORS 도메인 (콤마 구분) | 개발용 |

## 코드 스타일

- Python 3.10+, type hints 필수 (typing 모듈 사용)
- 함수 시그니처에 반환 타입 명시: `def func(x: str) -> Dict[str, Any]:`
- 환경변수는 `os.getenv("KEY", "")` 패턴. 기본값에 절대 시크릿 넣지 않음
- 로깅은 `logging.getLogger("LawmadiOS.모듈명")` 사용. print() 금지
- 외부 API 호출에 반드시 timeout 설정
- 새 모듈은 optional_import 패턴으로 추가 (서버 부팅 실패 방지)
- DRF API 응답은 JSON Content-Type 확인 후에만 파싱 (HTML/XML 방어)
- 에러 처리: try/except에서 구체적 예외 타입 사용. bare except 지양

## 알려진 이슈 — 수정 시 참고

1. **main.py:48** — `from services.search_service import SearchService` hard import가 line 68의 optional_import와 충돌. line 48 제거 필요
2. **services/search_service.py:18** — `os.getenv("LAWGO_DRF_OC", "choepeter")` 하드코딩 기본값 잔존. 빈 문자열로 변경 필요
3. **connectors/db_client.py:46-53** — `_get_connector()` 내 return 이후 dead code 존재. 제거 필요
4. **config.json** — os_version이 "v50.2.3-HARDENED"로 main.py의 "v50.2.4-HARDENED"와 불일치
5. **config.json DRF 엔드포인트** — lawSearch/lawService가 HTTP, precSearch/precService가 HTTPS. 전부 HTTPS로 통일 필요
6. **requirements.txt** — 모든 패키지 버전 미고정. `pip freeze`로 고정 필요
7. **backups/ 폴더** 및 루트의 `*.bak`, `*_backup*`, `*_old*` 파일들 — 프로덕션 불필요. .gitignore에 패턴 추가 후 제거
8. **core/security.py** — CircuitBreaker와 SafetyGuard 내 print()문을 logger로 교체
9. **main.py:102-103** — `allow_methods=["*"]`, `allow_headers=["*"]` 와일드카드. 필요한 메서드/헤더만 명시
10. **connectors/db_client_v2.py:13** — `_ENV_VERSION = "v50.2.3-HARDENED"` 버전 하드코딩. OS_VERSION 상수 참조로 변경
11. **엔드포인트 인증 부재** — /metrics, /diagnostics, /ask, /search, /trending 전부 무인증. 최소 /metrics, /diagnostics에 인증 추가

## DRF API 사용 규칙

- 엔드포인트: law.go.kr/DRF/ (lawSearch.do, lawService.do)
- 인증: OC 파라미터 (환경변수 LAWGO_DRF_OC)
- 응답 형식: JSON (type=json 파라미터)
- target: "law" (법령), "prec" (판례)
- Content-Type이 JSON이 아니면 파싱 금지 (HTML 응답 방어)
- Rate Limit: DB 기반 추적 (rate_limit_tracker 테이블)
- 캐시: DB 기반 (drf_cache 테이블), SHA-256 서명 무결성 검증

## 브랜치 규칙

- main: 프로덕션 (push 시 자동 Cloud Run 배포)
- hotfix/*: 긴급 수정
- feature/*: 기능 개발
- main에 직접 push 금지. PR을 통해서만 머지