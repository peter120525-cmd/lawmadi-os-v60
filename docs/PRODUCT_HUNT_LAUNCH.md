# Lawmadi OS — Product Hunt Launch Guide

> 런칭 전 체크리스트 + 콘텐츠 초안

---

## 1. 기본 정보

| 필드 | 내용 |
|:---|:---|
| **Product Name** | Lawmadi OS |
| **Website** | https://lawmadi.com |
| **Tagline** (60자 이내) | AI legal OS with 60 expert agents for Korean law — real-time verified |
| **Topics** | `Legal Tech`, `Artificial Intelligence`, `SaaS`, `Productivity` |
| **Pricing** | Freemium |
| **Made with** | Python, FastAPI, Gemini, GCP |

---

## 2. Tagline 후보 (택 1)

1. **AI legal OS with 60 expert agents for Korean law — real-time verified**
2. **60 AI legal experts that verify every answer against live Korean statutes**
3. **Turn legal anxiety into action — 60 AI agents, real-time statute verification**
4. **Your AI legal team: 60 domain experts powered by real-time Korean law data**

---

## 3. Description (Product Hunt용, 영문)

### Short Description (추천 — 260자)

Lawmadi OS is an AI-powered legal operating system for Korean law. 60 domain-specialized AI agents analyze your legal situation, route it to the right expert, and verify every statute citation against live government databases (law.go.kr) in real-time. Free to start.

### Full Description

**Lawmadi OS** is a legal decision operating system that turns legal anxiety into clear action plans.

**How it works:**
- Ask any Korean legal question in Korean or English
- Our NLU engine routes your query to the right expert among **60 specialized AI legal agents** (labor, divorce, real estate, traffic accidents, criminal law, and 55 more)
- Every response goes through a **4-stage pipeline**: Intent Classification → RAG Search → Gemini Analysis → Real-time Statute Verification
- All statute citations are **verified against live government APIs** (법제처 DRF) — no hallucinated laws

**What makes Lawmadi OS different:**
- **60 Domain Experts** — Each agent specializes in a specific area of Korean law with domain-tuned prompts and knowledge
- **Real-time Verification** — Every legal citation is cross-checked against 10 official government data sources (law.go.kr) in real-time
- **Empathy-First Responses** — 5-stage framework: Emotional acknowledgment → Situation diagnosis → Action roadmap → Safety net guidance → Supportive closing
- **Bilingual** — Full Korean and English support
- **C-Level Governance** — CSO, CCO, and CRO oversee agent coordination, compliance, and risk assessment
- **Circuit Breaker & Fail-Closed** — If verification fails, the system refuses to answer rather than risk providing unverified legal guidance

**Pricing:**
- Free: 2 queries/day
- Starter: 20 queries — ₩2,100 (~$1.50)
- Standard: 100 queries — ₩7,000 (~$4.99)
- Pro: 300 queries — ₩13,800 (~$9.99)

**Tech Stack:** FastAPI + Google Gemini 2.5 Flash + Vertex AI Search + Cloud SQL + Cloud Run + Firebase

---

## 4. First Comment (Maker's Comment)

### 한국어 원문

안녕하세요, Lawmadi OS를 만든 최재남입니다.

한국에서 법률 문제를 겪을 때 대부분의 사람들은 어디서부터 시작해야 할지 모릅니다. 변호사 상담은 비싸고, 인터넷 검색은 부정확하고, AI 챗봇은 존재하지 않는 법 조문을 만들어냅니다.

Lawmadi OS는 이 문제를 해결하기 위해 만들었습니다:
- 60개 법률 도메인 전문 AI 에이전트가 질문을 분석합니다
- 모든 법 조문 인용은 법제처 공공 API로 실시간 검증합니다
- 검증에 실패하면 답변을 거부합니다 (Fail-Closed)

아직 초기 단계이지만, 지난 7일간 114명의 사용자가 481건의 법률 질문을 했고 99.6%의 성공률을 기록했습니다.

피드백과 질문 환영합니다!

### English Version

Hi Product Hunt! I'm Jainam, the maker of Lawmadi OS.

When people in Korea face legal issues, most don't know where to start. Lawyer consultations are expensive, internet searches are unreliable, and AI chatbots hallucinate laws that don't exist.

I built Lawmadi OS to solve this:
- **60 specialized AI agents** analyze your legal question and route it to the right domain expert
- **Every statute citation is verified in real-time** against Korea's official legislative database (law.go.kr)
- **If verification fails, the system refuses to answer** — we'd rather say "I don't know" than give you wrong legal information

It's still early days, but in the last 7 days, 114 users asked 481 legal questions with a 99.6% success rate.

I'd love your feedback and questions!

---

## 5. Gallery / Media Assets

Product Hunt에 최소 3~5개 이미지 또는 1개 동영상 필요.

### 필요한 에셋 목록

| # | 에셋 | 설명 | 권장 크기 |
|:--|:-----|:-----|:---------|
| 1 | **Thumbnail** | 로고 + 태그라인 | 240×240 px |
| 2 | **Hero Image** | 메인 UI 스크린샷 (대화 화면) | 1270×760 px |
| 3 | **60 Leaders** | 리더 목록 페이지 스크린샷 | 1270×760 px |
| 4 | **Pipeline Diagram** | 4-Stage 파이프라인 인포그래픽 | 1270×760 px |
| 5 | **Verification** | 법 조문 실시간 검증 결과 예시 | 1270×760 px |
| 6 | **Demo Video** (선택) | 질문→답변 전체 플로우 30~60초 | 1920×1080 |

### 기존 에셋

- `frontend/public/og-image.png` — OG 이미지 (소셜 공유용)
- `frontend/public/icon-192.png` — PWA 아이콘 192px
- `frontend/public/icon-512.png` — PWA 아이콘 512px
- `frontend/public/images/new_icon.png` — 새 아이콘

### Thumbnail 용 로고

`icon-512.png`를 240×240으로 리사이즈하여 사용 가능.

---

## 6. Product Hunt 업로드 절차

### 사전 준비
1. [ ] [producthunt.com](https://www.producthunt.com) 계정 생성/로그인
2. [ ] Maker 프로필 설정 (이름, 사진, 바이오)
3. [ ] Gallery 이미지 5장 준비 (위 에셋 목록 참조)
4. [ ] 데모 영상 촬영 (선택, 권장)

### 업로드 단계
1. [producthunt.com/posts/new](https://www.producthunt.com/posts/new) 접속
2. **Name**: `Lawmadi OS`
3. **Tagline**: 위 후보 중 택 1
4. **Links**: `https://lawmadi.com`
5. **Description**: 위 Full Description 붙여넣기
6. **Topics**: `Legal Tech`, `Artificial Intelligence`, `SaaS`
7. **Pricing**: `Freemium` 선택
8. **Gallery**: 이미지 5장 업로드
9. **Makers**: 본인 태그
10. **Launch date**: 원하는 날짜 선택 (PST 기준 00:01 시작)
11. **Submit**

### 런칭 당일 체크리스트
- [ ] First Comment 즉시 게시 (위 Maker's Comment)
- [ ] 소셜 미디어 공유 (Twitter/X, LinkedIn, Facebook)
- [ ] 커뮤니티 알림 (관련 Slack/Discord/카카오톡)
- [ ] 댓글에 빠르게 응답
- [ ] 서버 모니터링 (Cloud Run 스케일링 확인)

---

## 7. 런칭 최적화 팁

1. **런칭 시간**: PST 화요일~목요일 00:01 (KST 화~목 17:01) 권장
2. **네트워크**: 런칭 전 PH 커뮤니티에서 활동하며 팔로워 확보
3. **응답 속도**: 런칭 후 첫 2시간 내 모든 댓글에 답변
4. **업데이트**: 런칭 중 실시간 통계 업데이트 공유 (사용자 수, 쿼리 수 등)
5. **감사**: 업보트/댓글에 개인적 감사 메시지

---

## 8. SEO / Social Sharing

### Twitter/X Post

```
🚀 Lawmadi OS is live on Product Hunt!

60 AI legal experts for Korean law — every answer verified against live government databases.

No more hallucinated laws. No more expensive consultations.

Free to try → [Product Hunt 링크]

#ProductHunt #LegalTech #AI #Korea
```

### LinkedIn Post

```
Excited to launch Lawmadi OS on Product Hunt today!

I built Lawmadi OS because navigating the Korean legal system shouldn't require expensive lawyers or unreliable AI chatbots.

What makes it different:
→ 60 domain-specialized AI legal agents
→ Real-time statute verification against official government APIs
→ Fail-Closed: refuses to answer if verification fails
→ Bilingual (Korean + English)

481 legal questions answered in the last 7 days with 99.6% success rate.

Check it out: [Product Hunt 링크]
```

---

*이 문서는 Product Hunt 런칭 준비를 위해 생성되었습니다.*
*마지막 업데이트: 2026-03-12*
