<div align="center">

# ⚖️ Lawmadi OS v60.0.0

### **불안을 행동으로 바꾸는 법률 AI 운영체제**

60명의 전문 법률 리더 + C-Level 임원진이 협업하는 대한민국 법률 AI Swarm 시스템

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-3_Flash-4285F4?logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Cloud Run](https://img.shields.io/badge/Cloud_Run-asia--northeast3-4285F4?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Firebase](https://img.shields.io/badge/Firebase-Hosting-FFCA28?logo=firebase&logoColor=black)](https://firebase.google.com)
[![License](https://img.shields.io/badge/License-Proprietary-red)](./license)

> ⚠️ **이 저장소는 오픈소스가 아닙니다.**
> 열람·비상용 평가 목적의 제한적 접근만 허용됩니다. 자세한 내용은 [라이선스](#-라이선스)를 참조하세요.

**[🌐 라이브 서비스](https://lawmadi-db.web.app)** · **[⚙️ API 상태](https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/health)** · **[👥 60 Leaders](https://lawmadi-db.web.app/leaders)** · **[👔 C-Level](https://lawmadi-db.web.app/clevel)**

</div>

---

## 목차

1. [시스템 개요](#-시스템-개요)
2. [아키텍처 8레이어](#-아키텍처-8레이어)
3. [60 Swarm Leaders](#-60-swarm-leaders)
4. [C-Level 임원진](#-c-level-임원진)
5. [SSOT 데이터 소스 10종](#-ssot-데이터-소스-10종)
6. [6대 헌법적 원칙](#-6대-헌법적-원칙)
7. [API 엔드포인트](#-api-엔드포인트)
8. [기술 스택](#-기술-스택)
9. [프로젝트 구조](#-프로젝트-구조)
10. [MCP 서버 (Model Context Protocol)](#-mcp-서버-model-context-protocol)
11. [Zapier 연동 (외부 API)](#-zapier-연동-외부-api)
12. [로컬 실행 (평가 전용)](#-로컬-실행-평가-전용)
13. [배포 파이프라인](#-배포-파이프라인)
14. [데이터베이스 스키마](#-데이터베이스-스키마)
15. [보안 정책](#-보안-정책)
16. [라이선스](#-라이선스)
17. [문의](#-문의)

---

## 🌟 시스템 개요

Lawmadi OS는 대한민국 법령·판례를 **법제처 DRF API**에서 실시간 검증하여 답변하는 법률 AI 운영체제입니다. 단순 Q&A를 넘어, **60명의 전문 리더가 복합 법률 사안을 협업(Swarm)** 분석하고 5단계 구조화된 행동 계획을 제시합니다.

### 핵심 특징

| 항목 | 상세 |
|:---|:---|
| **AI 엔진** | Google Gemini 3 Flash (`gemini-3-flash-preview`) |
| **검증 소스** | 법제처 DRF JSON API (`law.go.kr`) 실시간 10종 SSOT |
| **리더 구성** | Swarm Leader 60명 + C-Level 3명 (총 63 페르소나) |
| **응답 구조** | 계층적 5단계 (핵심요약 → 법률근거 → 시간축전략 → 실행계획 → 추가정보) |
| **안전장치** | SafetyGuard + CircuitBreaker + 헌법 준수 자동 검증 |
| **인프라** | GCP Cloud Run (asia-northeast3) + Firebase Hosting |
| **버전** | v60.0.0 (2026-02-18 기준) |
| **라이선스** | 독점 소유권 라이선스 v2.0.0 — 오픈소스 아님 |

---

## 🏗️ 아키텍처 8레이어

```
사용자 질문
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  L0  Orchestration & Governance                                  │
│       Request Router · Circuit Breaker · Rate Limiter            │
│       Fail-Closed Enforcer                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  L1  Legal Document OCR & Layout Analysis                        │
│       Document Parser · OCR Engine · Table Extractor             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               │ 복합 사안?              │ 단순 사안?
               ▼                        ▼
┌──────────────────────────┐  ┌────────────────────────┐
│  L2  Multi-Agent Swarm   │  │  단일 Leader 처리       │
│  Leader Selector         │  │  L01~L60 중 매칭        │
│  Task Distributor        │  └────────────┬───────────┘
│  Result Aggregator       │              │
│  Consensus Builder       │              │
└──────────┬───────────────┘              │
           └─────────────┬────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  L3  Real-time Legal Data Integration (DRF SSOT)                 │
│       DRF Client · Cache Manager (TTL 3600s) · Data Validator    │
│       Dual SSOT: law.go.kr (primary) + data.go.kr (fallback)    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  L4  Adaptive Interaction UI                                     │
│       Tone Adapter · Empathy Detector                            │
│       Safety Monitor · Crisis Interceptor                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  L5  Fact-Anchored Jurisprudence Matching                        │
│       Precedent Searcher · Similarity Ranker                     │
│       Temporal Validator · Cross-Referencer                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  L6  Rule-based Scenario Enumeration                             │
│       Route Generator · Risk Assessor                            │
│       Deadline Calculator · Option Enumerator                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  L7  Legal vs Reference Output Segregation                       │
│       Section Divider · Disclaimer Injector                      │
│       Format Validator · User Tip Generator                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                       최종 응답
                (📚 법률 근거 + 🔍 참고 정보)
```

### /ask 핵심 처리 흐름

```
사용자 질문
  → Low-Signal 필터 (짧거나 의미없는 질문 차단)
  → SafetyGuard.check() [CRISIS / BLOCKED / PASS]
  → select_swarm_leader() — 키워드 매칭으로 L01~L60 선택
  → DRF 선점 점검 (search_laws limit=1)
  → Gemini Tool-Call
       tools=[search_law_drf, search_precedents_drf,
              search_admrul_drf, search_expc_drf,
              search_constitutional_drf, search_ordinance_drf,
              search_legal_term_drf, search_admin_appeals_drf,
              search_treaty_drf]
  → validate_constitutional_compliance()
  → 감사 로그 기록 (Cloud SQL)
  → JSON 응답 반환
```

---

## 👥 60 Swarm Leaders

각 리더는 특정 법률 분야의 전문가 페르소나로, 질문 키워드에 따라 자동 선택됩니다.

| 코드 | 이름 | 전문 분야 | 코드 | 이름 | 전문 분야 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| L01 | 휘율 | 민사법 | L31 | 바름 | 공정거래 |
| L02 | 벼리 | 손해배상 | L32 | 라온 | 게임·콘텐츠 |
| L03 | 누리 | 상사법 | L33 | 가비 | 엔터테인먼트 |
| L04 | 찬솔 | 조세·금융 | L34 | 루다 | 지식재산권 |
| L05 | 다솜 | 회사법·M&A | L35 | 하람 | 저작권 |
| L06 | 무결 | 형사법 | L36 | 미소 | 광고·언론 |
| L07 | 산들 | 이혼·가족 | L37 | 가온 | 정보통신 |
| L08 | 온유 | 임대차 | L38 | 한빛 | 데이터·AI윤리 |
| L09 | 보늬 | 부동산법 | L39 | 휘윤 | IT·보안 |
| L10 | 세움 | 상속·신탁 | L40 | 지누 | 개인정보 |
| L11 | 마루 | 헌법 | L41 | 로운 | 행정법 |
| L12 | 아슬 | 등기·경매 | L42 | 한울 | 국가계약 |
| L13 | 결휘 | 민사집행 | L43 | 도울 | 조세불복 |
| L14 | 연우 | 의료법 | L44 | 오름 | 채권추심 |
| L15 | 담우 | 노동법 | L45 | 아키 | 재개발·재건축 |
| L16 | 해나 | 산업재해 | L46 | 강무 | 군형법 |
| L17 | 하늬 | 교통사고 | L47 | 예솔 | 소년법 |
| L18 | 슬아 | 보험 | L48 | 빛나 | 다문화·이주 |
| L19 | 다올 | 보험·연금 | L49 | 한결 | 인권 |
| L20 | 보람 | 사회복지 | L50 | 이룸 | 교육·청소년 |
| L21 | 다인 | 장애인·복지 | L51 | 슬비 | 소비자 |
| L22 | 수림 | 환경법 | L52 | 가람 | 식품·보건 |
| L23 | 담슬 | 건설법 | L53 | 윤빛 | 과학기술 |
| L24 | 미르 | 국제거래 | L54 | 다온 | 에너지·자원 |
| L25 | 해슬 | 무역·관세 | L55 | 별이 | 우주항공 |
| L26 | 슬옹 | 해상·항공 | L56 | 별하 | 스타트업 |
| L27 | 이서 | 해양·수산 | L57 | 새론 | 벤처·신산업 |
| L28 | 단아 | 문화·종교 | L58 | 예온 | 스포츠·레저 |
| L29 | 나래 | 문화예술 | L59 | 늘솔 | 농림·축산 |
| L30 | 소울 | 종교·전통 | **L60** | **마디** | **시스템 총괄** |

> **L60 마디**: 전체 분석을 총괄하는 시스템 총괄 리더. 법원행정처 전산정보국장 출신급 페르소나.

---

## 👔 C-Level 임원진

시스템 거버넌스를 담당하는 최고위 임원진 3명입니다.

| 직책 | 이름 | 역할 |
|:---:|:---:|:---|
| **CSO** | 서연 | Chief Strategy Officer — 미국 연방법원 클러크 출신급, 법률전략 총괄 |
| **CTO** | 지유 | Chief Technology Officer — 법률 AI 기술 아키텍처 총괄 |
| **CCO** | 유나 | Chief Content Officer — 법률 콘텐츠 품질 및 출력 형식 총괄 |

---

## 📚 SSOT 데이터 소스 10종

모든 법률 근거는 아래 10개의 공식 데이터 소스에서만 실시간 검증됩니다.

| # | SSOT | 대상(target) | 엔드포인트 | 상태 | 비고 |
|:---:|:---|:---:|:---:|:---:|:---|
| 01 | 현행법령 | `law` | `lawSearch.do` | ✅ 활성 | 민법·형법 등 모든 현행 법령 |
| 02 | 행정규칙 | `admrul` | `lawSearch.do` | ✅ 활성 | 시행규칙·고시·훈령 |
| 03 | 자치법규 | `ordin` | `lawSearch.do` | ✅ 활성 | 지방자치단체 조례·규칙 |
| 04 | 법령해석례 | `expc` | `lawSearch.do` | ✅ 활성 | 법제처 공식 법령해석 |
| 05 | 판례 | `prec` | `lawSearch.do` | ✅ 활성 | 대법원·고등법원 판례 |
| 06 | 헌재결정례 | `prec` | `lawSearch.do` | ✅ 활성 | 헌법재판소 결정례 |
| 07 | 법령용어 | `lstrm` | `lawSearch.do` | ✅ 활성 | 법령 용어 사전 (한글·한자·정의) |
| 08 | 행정심판례 | `decc` | `lawService.do` | ✅ 활성 | ID 파라미터 필수 |
| 09 | 조약 | `trty` | `lawService.do` | ✅ 활성 | ID 파라미터 필수 |
| 10 | 학칙공단 | `edulaw` | — | ❌ 비활성 | DRF API 미지원 확인 (2026-02-13) |

**Dual SSOT 구성** (자동 페일오버):

```
Primary:  https://www.law.go.kr/DRF/lawSearch.do  (DRF)
Fallback: https://apis.data.go.kr/1170000/LawService (공공데이터포털)
Retry:    DRF-1 → DATA-1 → DRF-2
Cache:    TTL 3,600초 (1시간)
```

---

## 🔒 6대 헌법적 원칙

모든 코드 변경과 AI 응답은 아래 6대 원칙을 반드시 준수합니다.

```
┌────────────────────────────────────────────────────────────────────┐
│  1  SSOT_FACT_ONLY                                                  │
│     법률 근거는 DRF 실시간 검증 데이터만 사용.                        │
│     LLM이 법조문을 직접 생성하거나 인용하면 안 됨.                     │
│                                                                    │
│  2  ZERO_INFERENCE                                                  │
│     DRF 미검증 데이터로 법률·판례를 추론하거나 창작 금지.              │
│                                                                    │
│  3  FAIL_CLOSED                                                     │
│     불확실하면 답변 차단. "모르면 멈춘다"가 원칙.                      │
│     DRF 연결 실패 시 법률 근거 섹션 전체 생략.                         │
│                                                                    │
│  4  IDENTITY                                                        │
│     변호사 사칭 절대 금지.                                            │
│     "변호사입니다", "변호사로서" 포함 시 거버넌스가 자동 차단.           │
│                                                                    │
│  5  TIMELINE_RULE                                                   │
│     now_utc 외 임의 날짜 생성 금지.                                   │
│     YYYY-MM-DD 등 플레이스홀더 자동 차단.                             │
│                                                                    │
│  6  SOURCE_TRANSPARENCY                                             │
│     인용 법령에 법령ID + 시행일자 메타데이터 필수 표시.                 │
└────────────────────────────────────────────────────────────────────┘
```

### 응답 출력 형식 정책

```
📚 법률 근거 섹션          ← SSOT DRF 검증 데이터만 표시
   ※ 본 내용은 대한민국 법령/판례/공식 데이터에 기초하여 정리한 참고 의견이며,
      구체 사안에 대한 유권해석/법적 효력을 보장하지 않습니다.

---  (시각적 구분선)

🔍 참고 정보 섹션          ← 외부 공개 데이터 (법적 근거로 사용 불가)
   ※ [참고] 아래 정보는 외부 공개 API를 참조한 내용으로,
      법적 근거로 직접 활용할 수 없습니다.

🕐 시간축 분석 섹션        ← temporal_v2.py (행위시법 vs 재판시법)
```

---

## 🔌 API 엔드포인트

**Base URL**: `https://lawmadi-os-v60-938146962157.asia-northeast3.run.app`

### 공개 엔드포인트

| 메서드 | 경로 | 설명 | 인증 |
|:---:|:---|:---|:---:|
| `GET` | `/` | 메인 페이지 (index.html) | — |
| `GET` | `/leaders` | 60 Leaders 페이지 | — |
| `GET` | `/health` | 헬스체크 + 모듈 상태 | — |
| `POST` | `/ask` | 법률 질문 답변 (핵심 엔드포인트) | — |
| `POST` | `/upload` | 문서/이미지 업로드 (PDF, JPG, PNG, WEBP) | — |
| `POST` | `/analyze-document/{file_id}` | 업로드 문서 분석 | — |
| `POST` | `/ask-expert` | 전문가용 답변 (Gemini 재생성 + Claude 검증) | — |
| `POST` | `/export-pdf` | 법률문서 PDF 내보내기 (고소장, 소장 등) | — |
| `POST` | `/api/visit` | 방문자 추적 | — |
| `GET` | `/api/visitor-stats` | 방문자 통계 조회 | — |
| `GET` | `/search` | 법령 검색 | — |
| `GET` | `/trending` | 인기 질문 트렌드 | — |

### 내부 엔드포인트 (Authorization 헤더 필요)

| 메서드 | 경로 | 설명 |
|:---:|:---|:---|
| `GET` | `/metrics` | 시스템 메트릭 (요청수, 에러율, 레이턴시) |
| `GET` | `/diagnostics` | 상세 진단 (모듈 상태, 환경변수 체크) |
| `GET` | `/api/verification/stats` | 헌법 검증 통계 |
| `GET` | `/api/admin/leader-stats` | 리더별 질문 통계 |
| `GET` | `/api/admin/category-stats` | 법률 분야별 통계 |
| `GET` | `/api/admin/leader-queries/{leader_code}` | 특정 리더 질문 이력 |

### /ask 요청·응답 예시

```bash
curl -X POST https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "전세 보증금을 돌려받지 못하고 있습니다. 어떻게 해야 하나요?"}'
```

```json
{
  "response": "안녕하세요. 전세 보증금 문제로 많이 걱정되시겠습니다...\n\n📚 법률 근거\n- 주택임대차보호법 제3조...\n\n🔍 참고 정보\n...",
  "leader": "온유",
  "swarm_mode": true,
  "leaders_used": ["온유", "마디"],
  "latency_ms": 3240
}
```

---

## 🧠 AI 법률 지원 기능 (v60.1)

시스템 프롬프트에 내장된 법률 특화 AI 기능 13종입니다.

### 법률문서 작성 지원 5종

| # | 문서 | 핵심 구성요소 |
|:---:|:---|:---|
| 1 | **고소장** (형사) | 고소인/피고소인, 범죄사실, 관련 법조문, 증거자료 |
| 2 | **소장** (민사) | 원고/피고, 청구취지, 청구원인, 입증방법 |
| 3 | **답변서** (민사) | 사건번호, 청구취지 답변, 항변 |
| 4 | **내용증명** | 발신인/수신인, 요구사항, 이행기한, 법적 조치 예고 |
| 5 | **고소취하서** | 사건번호, 취하 내용, 취하 사유 |

### AI 지원 기능 8종

| # | 기능 | 설명 |
|:---:|:---|:---|
| 1 | 법률 용어 쉬운말 변환 | 어려운 법률 용어를 일상 언어로 자동 병기 |
| 2 | 소멸시효·공소시효 자동 안내 | 사안별 시효 기간 자동 계산 및 경고 |
| 3 | 대화→문서 자동 전환 | 상담 내용을 법률문서 초안으로 자동 변환 |
| 4 | 법적 절차 로드맵 | 단계별 행동 계획 (비용·기간·난이도 포함) |
| 5 | 비용 예측 가이드 | 인지대, 송달료, 수수료 등 예상 비용 안내 |
| 6 | 증거 수집 체크리스트 | 사안별 필요 증거 목록 + 수집 방법 |
| 7 | 관할법원·관할경찰서 안내 | 사건 유형별 관할 기관 자동 매칭 |
| 8 | 판례 요약 검색 안내 | 종합법률정보 검색 가이드 + 친고죄 자동 경고 |

### 대화형 문서 완성 워크플로

법률문서 작성 요청 시 한꺼번에 정보를 요구하지 않고, **5단계 대화**로 정보를 수집하여 문서를 완성합니다.

```
1. 문서 종류 확인 → 2. 핵심 정보 수집 (3~5개 질문)
→ 3. 빈칸 자동 채움 → 4. 검토 및 수정 → 5. PDF 다운로드 안내
```

---

## 🖥️ 프론트엔드 UX 기능 (v60.1)

| # | 기능 | 설명 |
|:---:|:---|:---|
| 1 | **다크모드** | CSS 변수 기반 테마 전환, localStorage 유지 |
| 2 | **즐겨찾기** | AI 답변 저장/조회/삭제 (localStorage) |
| 3 | **대화 이력** | 최근 10개 대화 컨텍스트를 API에 전송 |
| 4 | **에러 재시도** | 최대 2회 자동 재시도 + 수동 재시도 버튼 |
| 5 | **6단계 로딩** | 질문 분석 → 리더 배정 → 법령 검색 → 답변 생성 → 교차 검증 → 최종 정리 |
| 6 | **코드블록 렌더링** | 마크다운 ``` 코드블록 → `<pre><code>` 변환 |
| 7 | **PDF 다운로드** | 법률문서 코드블록 감지 시 PDF 버튼 자동 표시 |
| 8 | **모바일 최적화** | 노치폰 safe-area, 768px/480px/360px 반응형 |
| 9 | **전문가용 답변** | 변호사 참고 수준 재생성 + Claude SSOT 검증 |
| 10 | **경과 시간 표시** | 응답 대기 시 실시간 경과 시간 카운터 |
| 11 | **Google Analytics** | GA4 (G-C3VFDP0QPZ) 연동 |

---

## 🛠️ 기술 스택

### Backend

| 구분 | 기술 | 버전 | 용도 |
|:---|:---|:---:|:---|
| 언어 | Python | 3.10+ | 전체 백엔드 |
| 프레임워크 | FastAPI | 0.128.0 | REST API 서버 |
| ASGI 서버 | Uvicorn | 0.40.0 | HTTP 서버 |
| LLM | Google Gemini | 3 Flash | 법률 분석 AI (google-genai SDK) |
| LLM (검증) | Anthropic Claude | Sonnet 4.5 | SSOT 준수 검증 (anthropic SDK >=0.45.0) |
| DB 드라이버 | cloud-sql-python-connector | 1.20.0 | Cloud SQL 연결 |
| DB 드라이버 | pg8000 | 1.31.5 | PostgreSQL 드라이버 |
| 문서 파싱 | PyPDF2 | 3.0.1 | PDF 업로드 처리 |
| 파일 업로드 | python-multipart | 0.0.9 | FastAPI 파일 처리 |
| PDF 생성 | fpdf2 | 2.8.3 | 법률문서 PDF 내보내기 |

### Frontend

| 구분 | 기술 | 용도 |
|:---|:---|:---|
| UI | Vanilla HTML/CSS/JavaScript | SPA 인터페이스 |
| 폰트 | Pretendard | 한국어 최적화 폰트 |
| 아이콘 | Google Material Symbols | UI 아이콘 |
| 호스팅 | Firebase Hosting | 정적 파일 CDN 배포 |
| 분석 | Google Analytics 4 | GA4 (G-C3VFDP0QPZ) 사용자 행동 분석 |
| 페이지 | index.html / leaders.html / clevel.html | 3개 주요 페이지 |

### Infrastructure

| 구분 | 서비스 | 설정 |
|:---|:---|:---|
| 컨테이너 런타임 | Google Cloud Run | 리전: asia-northeast3 |
| CPU / 메모리 | 2 vCPU / 2 GiB | 최대 10 인스턴스 |
| 타임아웃 | 300초 | 동시성: 80 |
| 이미지 저장소 | Artifact Registry | `asia-northeast3-docker.pkg.dev` |
| 데이터베이스 | Cloud SQL (PostgreSQL) | `cloud-sql-python-connector` |
| 시크릿 관리 | GCP Secret Manager | API 키 4종 저장 |
| CI/CD | GitHub Actions | main push → 자동 배포 |
| 프론트 CDN | Firebase Hosting | `lawmadi-db.web.app` |

---

## 📁 프로젝트 구조

```
lawmadi-os-v50/
│
├── main.py                         # FastAPI 커널 v60.0.0
│                                   # 라우팅, Swarm 리더 선택, /ask 엔드포인트
├── config.json                     # 시스템 설정 SSOT
│                                   # 8레이어 아키텍처, SSOT 레지스트리, 보안 정책
├── leaders.json                    # 63 페르소나 레지스트리
│                                   # core_registry (C-Level 3명)
│                                   # swarm_engine_config (Leader L01~L60)
├── requirements.txt                # Python 의존성
├── Dockerfile                      # Python 3.10-slim 기반 컨테이너
├── license                         # 독점 소유권 라이선스 v2.0.0
│
├── core/
│   ├── security.py                 # SafetyGuard (입력 필터링, Anti-Leak, 위기감지)
│   │                               # CircuitBreaker (failure_threshold=3, reset=30s)
│   ├── gate_kernel.py              # 3-Gate Hardening Architecture
│   │                               # DRF 데이터 무결성 오케스트레이션
│   ├── law_selector.py             # Gemini 기반 지능형 법령 매칭 (L5)
│   ├── parser.py                   # 법률 텍스트 구조화 파서 (조-항-호-목)
│   ├── action_router.py            # 사용자 선택 기반 법리 탐색 경로 결정
│   ├── case_summarizer.py          # 판례 요약 엔진
│   ├── evidence_explainer.py       # 증거 설명 생성기
│   ├── drf_integrity.py            # DRF 데이터 무결성 검증
│   └── drf_query_builder.py        # DRF 쿼리 빌더
│
├── connectors/
│   ├── drf_client.py               # DRF API 커넥터
│   │                               # Recon→Selection→Strike 패턴
│   │                               # 캐시(TTL 3600s), Rate Limit, 에러 처리
│   ├── db_client.py                # Cloud SQL 커넥션 풀 + 테이블 초기화
│   ├── db_client_v2.py             # 감사 로그(audit log) 기능
│   ├── db_driver_adapter.py        # pg8000/psycopg2 드라이버 어댑터
│   └── validator.py                # SHA-256 무결성 서명
│
├── engines/
│   ├── temporal_v2.py              # 시계열 분석 엔진
│   │                               # 행위시법 vs 재판시법, 부칙/경과조치 처리
│   └── addenda_parser.py           # 법령 부칙 파서
│
├── agents/
│   ├── swarm_orchestrator.py       # Swarm 협업 엔진 v2.1
│   ├── clevel_handler.py           # C-Level 임원 시스템 핸들러
│   └── swarm_manager.py            # 멀티에이전트 리더 선택 매니저
│
├── services/
│   └── search_service.py           # DRF 법령/판례 검색 서비스 래퍼
│
├── prompts/
│   └── constitution.yaml           # 헌법 정의 (6대 원칙, 안전 가드레일, 위기 프로토콜)
│
├── frontend/
│   └── public/
│       ├── index.html              # 메인 페이지 (프리미엄 UI, 모바일 최적화)
│       ├── leaders.html            # 60 Leaders 소개 페이지
│       ├── clevel.html             # C-Level 임원 페이지
│       └── leaders.json            # 프론트엔드용 리더 데이터
│
├── fonts/
│   └── NanumGothic.ttf             # PDF 한국어 폰트 (fpdf2용)
│
├── static/                         # 정적 에셋 (이미지, 영상)
│
├── .github/
│   └── workflows/
│       ├── deploy.yml              # CI/CD: main push → Cloud Run + Firebase
│       └── claude-code.yml         # Claude AI 코드 리뷰 자동화
│
├── firebase.json                   # Firebase Hosting 설정
├── .firebaserc                     # Firebase 프로젝트 (lawmadi-db)
└── claude.md                       # 개발 헌법 (6대 원칙, 기술 스택, 보안 규칙)
```

---

## 🔗 MCP 서버 (Model Context Protocol)

Lawmadi OS는 [MCP(Model Context Protocol)](https://modelcontextprotocol.io/) 서버를 내장하고 있어, Claude Desktop, ChatGPT, Gemini 등 MCP 지원 LLM 클라이언트에서 직접 연결하여 한국 법률 질문을 할 수 있습니다.

**MCP 엔드포인트**: `https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/mcp`

### 인증

MCP 엔드포인트는 **Bearer 토큰 인증**이 필요합니다. 모든 요청에 `Authorization` 헤더를 포함해야 합니다.

```
Authorization: Bearer <MCP_API_KEY>
```

인증 없이 접근 시 `401 Unauthorized`가 반환됩니다.

### 클라이언트 설정

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lawmadi": {
      "url": "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_API_KEY>"
      }
    }
  }
}
```

**Claude Code** (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "lawmadi": {
      "url": "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_API_KEY>"
      }
    }
  }
}
```

### 노출 도구 (20개)

MCP를 통해 Lawmadi OS의 모든 API 엔드포인트가 도구로 노출됩니다.

| 도구 | 설명 |
|:---|:---|
| `ask_ask_post` | 법률 질문 답변 (핵심 도구) |
| `search_search_get` | 법령 검색 |
| `trending_trending_get` | 인기 질문 트렌드 |
| `upload_document_upload_post` | 문서/이미지 업로드 및 법률 분석 |
| `export_pdf_export_pdf_post` | 법률문서 PDF 내보내기 |
| `health_health_get` | 시스템 헬스체크 |
| 기타 14개 | 방문자 통계, 리더 통계, 진단 등 |

### 연결 테스트 결과

```
┌──────────────────────┬─────────────────────────────────────────────┐
│  테스트               │  결과                                       │
├──────────────────────┼─────────────────────────────────────────────┤
│  인증 없이 접근        │  ✅ 401 Unauthorized 반환                   │
│  잘못된 키로 접근      │  ✅ 401 Unauthorized 반환                    │
│  올바른 Bearer 토큰    │  ✅ 200 정상 응답                            │
│  initialize          │  ✅ 핸드셰이크 성공, 세션 ID 발급              │
│  tools/list          │  ✅ 20개 도구 노출 확인                       │
│  tools/call (ask)    │  ✅ 법률 질문 응답 성공                       │
└──────────────────────┴─────────────────────────────────────────────┘
```

```bash
# MCP 연결 테스트 예시 (Bearer 토큰 필수)
curl -X POST https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer <MCP_API_KEY>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

---

## 🤖 Zapier 연동 (외부 API)

Zapier를 통해 Lawmadi OS의 법률 AI를 자동화 워크플로에 통합할 수 있습니다.

### API 엔드포인트

**Base URL**: `https://lawmadi-os-v60-938146962157.asia-northeast3.run.app`

| 메서드 | 경로 | 설명 |
|:---:|:---|:---|
| `GET` | `/api/v1/me` | 인증 테스트 (API 키 검증) |
| `POST` | `/api/v1/ask` | 법률 질문 답변 |
| `GET` | `/api/v1/search?q=키워드&limit=10` | 법령 검색 |

### 인증

모든 `/api/v1/*` 엔드포인트는 **Bearer 토큰** 인증이 필요합니다.

```
Authorization: Bearer <API_KEY>
```

인증 없이 접근 시 `401 Unauthorized`가 반환됩니다.

### 사용 예시

```bash
# 인증 테스트
curl https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/api/v1/me \
  -H "Authorization: Bearer YOUR_API_KEY"

# 법률 질문
curl -X POST https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/api/v1/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"query": "전세 보증금 반환 절차를 알려주세요"}'

# 법령 검색
curl "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/api/v1/search?q=민법&limit=5" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Zapier 앱 설정

Zapier 앱 코드는 `zapier/` 디렉토리에 있습니다.

1. **Authentication**: Custom Auth 방식 — `API Key`와 `API URL` 입력
2. **Trigger**: 없음 (Action 전용)
3. **Action**: `Ask Legal Question` (법률 질문), `Search Law` (법령 검색)

```bash
# 로컬 테스트
cd zapier && npm test
```

---

## 🚀 로컬 실행 (평가 전용)

> ⚠️ **라이선스 준수 필수**: 로컬 실행은 **비상용 내부 평가 목적에 한정**됩니다.
> 프로덕션 환경, 상용 서비스, 제3자 제공은 라이선스상 금지됩니다.

### 사전 요구사항

- Python 3.10 이상
- Google Cloud 계정 (Cloud SQL, Secret Manager 사용 시)
- 법제처 DRF API 인증키 ([신청](https://www.law.go.kr/LSW/openapiInfo.do))
- Google Gemini API 키 ([발급](https://aistudio.google.com/))

### 설치 및 실행

```bash
# 1. 저장소 클론 (평가 목적 단일 사본만 허용)
git clone https://github.com/peter120525-cmd/lawmadi-os-v50.git
cd lawmadi-os-v50

# 2. 가상환경 및 의존성 설치
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력 (아래 참조)
```

**필수 환경변수** (`.env`):

```env
# ── 필수 ───────────────────────────────────────────────
GEMINI_KEY=your_gemini_api_key_here
LAWGO_DRF_OC=your_drf_oc_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# ── 데이터베이스 (Cloud SQL 사용 시) ───────────────────
CLOUD_SQL_INSTANCE=your_project:asia-northeast3:your_instance
DB_USER=postgres
DB_PASS=your_secure_password
DB_NAME=postgres

# ── 선택 ────────────────────────────────────────────
SOFT_MODE=true
GEMINI_MODEL=gemini-3-flash-preview
```

```bash
# 4. 서버 실행 (개발 모드)
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# 5. 동작 확인
curl http://localhost:8080/health
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "민법 제750조 불법행위 성립요건을 알려주세요"}'
```

---

## 🚢 배포 파이프라인

### GitHub Actions 자동 배포

`main` 브랜치에 push하면 3개 Job이 순차 실행됩니다.

```
Push to main
    │
    ▼
┌─────────────────────────────────┐
│  Job 1: deploy-backend           │  ← 약 2~3분
│  1. Checkout                     │
│  2. GCP 인증 (SA Key)             │
│  3. Docker 이미지 빌드             │
│  4. Artifact Registry 푸시        │
│  5. Cloud Run 배포                │
│  6. /health 엔드포인트 검증        │
└──────────────┬──────────────────┘
               │ needs: deploy-backend
               ▼
┌─────────────────────────────────┐
│  Job 2: deploy-frontend          │  ← 약 1분
│  1. Checkout                     │
│  2. GCP 인증 (SA Key)             │
│  3. Node.js 18 설치               │
│  4. Firebase CLI 설치             │
│  5. Firebase Hosting 배포         │
│  6. lawmadi-db.web.app 검증       │
└──────────────┬──────────────────┘
               │ needs: [backend, frontend]
               ▼
┌─────────────────────────────────┐
│  Job 3: notify                   │  ← 4초
│  배포 결과 요약 출력               │
└─────────────────────────────────┘
```

### Cloud Run 배포 사양

```yaml
Service:       lawmadi-os-v60
Region:        asia-northeast3 (서울)
Image:         asia-northeast3-docker.pkg.dev/lawmadi-db/lawmadi-repo/lawmadi-os-v60
Memory:        2 GiB
CPU:           2 vCPU
Timeout:       300초
Concurrency:   80
Min-instances: 1
Max-instances: 10
Auth:          --allow-unauthenticated
Secrets:       GEMINI_API_KEY, LAWGO_DRF_OC, ANTHROPIC_API_KEY, CLOUD_SQL_INSTANCE, MCP_API_KEY
```

---

## 🗄️ 데이터베이스 스키마

Cloud SQL (PostgreSQL) 4개 주요 테이블:

```sql
-- 법률 상담 이력
CREATE TABLE chat_history (
    id              SERIAL PRIMARY KEY,
    user_query      TEXT NOT NULL,
    ai_response     TEXT,
    leader_code     VARCHAR(10),           -- L01~L60
    swarm_mode      BOOLEAN DEFAULT FALSE,
    leaders_used    TEXT,                  -- JSON 배열 문자열
    query_category  VARCHAR(50),
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 방문자 식별
CREATE TABLE visitor_stats (
    id            SERIAL PRIMARY KEY,
    visitor_id    VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 해시
    first_visit   TIMESTAMPTZ DEFAULT NOW(),
    last_visit    TIMESTAMPTZ DEFAULT NOW(),
    visit_count   INTEGER DEFAULT 1
);

-- 일별 방문자 집계
CREATE TABLE daily_visitors (
    visit_date       DATE PRIMARY KEY,
    unique_visitors  INTEGER DEFAULT 0,
    total_visits     INTEGER DEFAULT 0
);

-- 법령 검색 캐시 (TTL 3600s)
CREATE TABLE drf_cache (
    cache_key   VARCHAR(255) PRIMARY KEY,
    content     JSONB NOT NULL,
    signature   VARCHAR(64),          -- SHA-256 무결성 서명
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
```

---

## 🔐 보안 정책

### 코드 레벨 보안 규칙

```
❌ 절대 금지
  - .env 파일 커밋
  - API 키 / 비밀번호 코드 하드코딩
  - os.getenv("KEY", "실제키값") 형태
  - CORS allow_origins=["*"]
  - /metrics, /diagnostics 공개 노출

✅ 필수 준수
  - 환경변수는 os.getenv("KEY", "") 형태만 허용
  - CORS: lawmadi.com, lawmadi-os.web.app 도메인만 허용
  - print() 대신 logger 사용
  - 모든 입력은 SafetyGuard 통과 후 처리
```

### SafetyGuard 위기 대응

```python
trigger_keywords = ["자살", "죽고싶다"]

crisis_resources = {
    "생명의 전화": "1577-0199",
    "경찰": "112"
}
```

### CircuitBreaker 설정

```
Provider:          LAW_GO_KR_DRF
failure_threshold: 3회
reset_timeout:     30,000ms (30초)
policy:            FAIL_CLOSED (실패 시 응답 차단)
```

### 헌법 준수 자동 검증

| 검증 항목 | 차단 패턴 |
|:---|:---|
| 변호사 사칭 | `변호사입니다`, `변호사로서`, `법률대리인` |
| 날짜 플레이스홀더 | `2024-MM-DD`, `YYYY-MM-DD` 등 |
| 미검증 법조문 | DRF 비경유 직접 법조문 인용 |

---

## 📄 라이선스

```
LAWMADI OS — COMPREHENSIVE PROPRIETARY LICENSE v2.0.0
Copyright (c) 2026 Jainam Choe (최재남). All rights reserved.

Effective Date: 2026-02-09
```

**이 소프트웨어는 오픈소스가 아닙니다.**

저장소의 공개 가용성은 어떠한 오픈소스 권리도 부여하지 않습니다.

### 허용 범위 (제3조 — 제한적 허가)

| 행위 | 허용 여부 |
|:---|:---:|
| 소스코드 열람 및 읽기 | ✅ 허용 |
| 비상용 평가 목적 단일 사본 다운로드 | ✅ 허용 |
| 비프로덕션·비상용 환경에서 로컬 실행 | ✅ 허용 |
| 학술·기술 토론에서 고수준 원칙 참조 (귀속 표시 필수) | ✅ 허용 |

### 금지 사항 (제5조 — 엄격한 제한)

| 행위 | 허용 여부 |
|:---|:---:|
| 수정, 번역, 포팅, 재구현, 파생 저작물 생성 | ❌ 금지 |
| 배포, 재배포, 서브라이선싱 | ❌ 금지 |
| 프로덕션 또는 상용 환경 사용 | ❌ 금지 |
| SaaS, API 서비스, PaaS, 호스팅 서비스 제공 | ❌ 금지 |
| AI 학습, 파인튜닝, 증류, RLHF, DPO 목적 사용 | ❌ 금지 |
| 임베딩 생성, 벡터 DB 구축, RAG 파이프라인 활용 | ❌ 금지 |
| 벤치마킹, 비교 평가 보고서 작성 | ❌ 금지 |
| 경쟁 제품 설계·구현·컨설팅에 활용 | ❌ 금지 |
| 저장소 미러링, 재업로드, 패키징 | ❌ 금지 |
| 스크래핑, 크롤링, 자동화 추출 | ❌ 금지 |

### 귀속 표시 (제9조)

본 소프트웨어를 허용 범위 내에서 참조할 경우 다음 귀속 표시를 명시해야 합니다:

> **Lawmadi OS — Legal Decision Operating System.**
> Copyright (c) 2026 Jainam Choe (최재남). All rights reserved.

### 준거법 및 관할

- **준거법**: 대한민국 법률
- **전속 관할**: 대한민국 법원

### 한국어 요약 (참고용, 라이선스 원문 우선)

```
본 라이선스는 오픈소스가 아닙니다.
평가 목적의 열람/다운로드/로컬 실행만 허용됩니다.
수정/재배포/상용 사용/서비스 제공은 금지됩니다.
AI 학습/임베딩/벡터DB/RAG/벤치마킹 목적 사용은 금지됩니다.
경쟁 제품 설계/구현/컨설팅 목적 사용은 금지됩니다.
위반 시 자동 종료되며, 모든 사본/파생물/인덱스 삭제가 요구됩니다.
```

전문: [./license](./license)

---

## 📮 문의

상용 라이선스 취득, 협업 제안, 보안 취약점 신고는 아래로 연락하세요.

| 항목 | 내용 |
|:---|:---|
| **저작권자** | Jainam Choe (최재남) |
| **이메일** | choepeter@outlook.kr |
| **프로젝트** | Lawmadi OS — Legal Decision Operating System |
| **라이선스 문의 제목** | `Lawmadi OS License Inquiry / Permission Request` |
| **보안 취약점 신고** | 비공개 이메일로만 제보 (비공개 원칙) |

> 라이선스 허가 요청 시 요청 범위, 기간, 상용 조건, 기술적 사용 사례, 연락처를 포함하세요.

---

<div align="center">

**⚖️ Lawmadi OS v60.0.0**

법률 문제로 인한 불안, 60명의 전문 리더가 구체적인 행동 계획으로 바꿔드립니다

[🌐 서비스 이용](https://lawmadi-db.web.app) · [⚙️ API 상태](https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/health) · [📮 문의](mailto:choepeter@outlook.kr)

*Copyright (c) 2026 Jainam Choe (최재남). All rights reserved.*
*최종 업데이트: 2026-02-18 | 운영 환경: GCP asia-northeast3*

</div>
