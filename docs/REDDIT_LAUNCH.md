# Lawmadi OS — Reddit Launch Posts

> 서브레딧별 맞춤 포스트 (규칙 준수 + 자연스러운 톤)

---

## 타겟 서브레딧 목록

| # | Subreddit | 구독자 | 포스트 타입 | 자기홍보 규칙 |
|:--|:----------|:------|:----------|:------------|
| 1 | r/SideProject | ~200K | Show & Tell | 허용 (메인 목적) |
| 2 | r/startups | ~1.2M | Share Your Startup | 허용 (주간 스레드) |
| 3 | r/artificial | ~1M | Link/Text | 기술 중심이면 허용 |
| 4 | r/LegalTech | ~10K | Text | 허용 |
| 5 | r/korea | ~300K | Text | 한국 관련 허용 |
| 6 | r/MachineLearning | ~3M | [P] Project | [P] 태그 필수 |
| 7 | r/webdev | ~2M | Showoff Saturday | 토요일만 허용 |
| 8 | r/Entrepreneur | ~2M | Text | 가치 제공 필수 |
| 9 | r/legaladvice | ~3M | 참고용 | 직접 홍보 금지, 댓글에서 언급만 |

---

## Post 1: r/SideProject (메인 런칭)

**Title:**
```
I built an AI legal OS with 60 specialized agents that verify every answer against live government databases — Lawmadi OS
```

**Body:**
```
Hey r/SideProject!

I've been working on Lawmadi OS — an AI-powered legal operating system for Korean law.

**The problem:** In Korea, when you have a legal issue, your options are expensive lawyers, unreliable internet searches, or AI chatbots that confidently cite laws that don't exist.

**What I built:**
- 60 domain-specialized AI agents (labor law, divorce, real estate, traffic accidents, criminal law, etc.)
- 3-layer NLU routing: regex patterns → keyword matching → Gemini classification
- 4-stage pipeline: Intent Classification → RAG (14,601 docs) → Gemini 2.5 Flash analysis → DRF real-time verification
- Every statute citation is verified against Korea's official legislative API (law.go.kr) in real-time
- **Fail-Closed**: if verification fails, the system refuses to answer instead of hallucinating

**Tech stack:**
- Backend: Python/FastAPI on GCP Cloud Run
- LLM: Google Gemini 2.5 Flash
- RAG: Vertex AI Search (14,601 legal documents)
- Verification: 법제처 DRF API (10 government data sources)
- Frontend: Static HTML/JS on Firebase Hosting
- Billing: Paddle (credit-based, no subscription)
- CI/CD: GitHub Actions (5-stage: test → staging → backend → frontend → notify)

**Some numbers (last 7 days):**
- 114 unique visitors
- 481 legal queries processed
- 99.6% success rate
- Average response time: ~40s (Gemini analysis + verification)

**Pricing:** Free tier (2 queries/day), paid packs start at $1.50 for 20 queries.

Live at: https://lawmadi.com

Would love feedback on:
1. The multi-agent routing approach — is 60 agents overkill or does specialization matter?
2. The fail-closed verification — would you trust a legal AI more knowing it refuses to answer when unsure?
3. Any ideas for reducing the ~40s response time?

Happy to answer any technical questions!
```

---

## Post 2: r/startups (주간 Share Your Startup 스레드)

**Title/Comment:**
```
Lawmadi OS — AI legal operating system for Korean law

**URL:** https://lawmadi.com
**Purpose:** Providing affordable, verified legal guidance to anyone in Korea
**Stage:** Live (launched)
**Looking for:** Feedback, early users, legal domain experts

**Details:**

60 AI legal agents analyze your question and route it to the right domain expert. Every statute citation is verified in real-time against Korea's official legislative database. If verification fails, the system refuses to answer.

- Free: 2 queries/day
- Paid: starts at $1.50 for 20 queries
- Bilingual: Korean + English
- 481 queries processed last week with 99.6% success rate

**Differentiator:** Most legal AI chatbots hallucinate laws. We verify every citation against 10 live government data sources before showing the answer. If we can't verify it, we don't show it.
```

---

## Post 3: r/artificial

**Title:**
```
Built a multi-agent legal AI system with 60 domain-specialized agents and real-time government database verification
```

**Body:**
```
I wanted to share an approach I've been working on for legal AI that I think addresses the hallucination problem in a meaningful way.

**Architecture overview:**

The system uses 60 domain-specialized AI agents (one per legal domain: labor, divorce, real estate, criminal, tax, IP, etc.) coordinated by a 3-layer routing system:

1. **NLU Layer** — Regex-based Korean/English legal intent patterns
2. **Keyword Layer** — Domain-specific keyword matching
3. **Gemini Classification** — LLM-based fallback routing

Once routed, each query goes through a 4-stage pipeline:
- **Stage 0**: Intent classification & leader selection
- **Stage 1**: RAG retrieval (Vertex AI Search, 14,601 legal documents)
- **Stage 3**: Gemini 2.5 Flash analysis with domain-specific prompts
- **Stage 4**: Real-time DRF verification against law.go.kr (Korea's official legislative database)

**The key insight:** Stage 4 cross-checks every statute citation in the response against live government APIs. If a cited law doesn't exist or the article number is wrong, the system flags it. This is a **fail-closed** design — unverified responses are rejected.

**Results so far:**
- 99.6% success rate across 481 queries
- 84.7/100 average verification score
- 82.5% Korean statute citation accuracy (working on improving this)
- 25.6% English statute citation accuracy (known issue, actively improving)

**Challenges:**
- Response latency (~40s, mostly Gemini processing)
- English statute citation matching is significantly harder than Korean
- Balancing agent specialization vs. maintainability with 60 agents

Curious what this community thinks about multi-agent specialization vs. single generalist agent approaches for domain-specific AI.

Live demo: https://lawmadi.com
```

---

## Post 4: r/LegalTech

**Title:**
```
Lawmadi OS: Open-access AI legal analysis for Korean law with real-time statute verification
```

**Body:**
```
I built Lawmadi OS to make Korean legal guidance more accessible. Here's what it does differently from other legal AI tools:

**Real-time verification against official sources:**
Every response goes through a verification stage that checks cited statutes against Korea's legislative database (법제처, law.go.kr) via their public DRF API. We pull from 10 different government data sources to cross-reference.

**60 domain-specialized agents:**
Instead of one generalist legal AI, we have 60 specialists. When you ask about unfair dismissal, your question goes to the labor law agent. Divorce custody questions go to the family law agent. This specialization allows for much more targeted prompts and better domain knowledge.

**Structured response framework:**
Every response follows a 5-stage framework:
1. Emotional acknowledgment (many people are stressed when seeking legal help)
2. Situation diagnosis
3. Action roadmap with specific steps
4. Safety net information (legal aid, hotlines, etc.)
5. Supportive closing

**Not a replacement for lawyers** — this is a first-step tool. It helps people understand their legal situation and know what questions to ask when they do consult a professional.

**Pricing:** Free tier available (2 queries/day). Paid packs from $1.50.

https://lawmadi.com (Korean default, English at /en)

Would appreciate feedback from anyone in the legal tech space, especially regarding:
- Verification methodology — what other sources should we cross-reference?
- The balance between accessibility and responsible AI in legal contexts
- How other jurisdictions handle similar challenges
```

---

## Post 5: r/korea

**Title:**
```
Made a free AI legal assistant for Korean law — verifies every answer against 법제처 API in real-time
```

**Body:**
```
Hey r/korea,

I built Lawmadi OS (로마디 OS), a free AI legal assistant specifically for Korean law. Thought it might be useful for people here who've had to navigate the Korean legal system.

**What it does:**
- You ask a legal question in Korean or English
- One of 60 specialized AI agents analyzes your situation (labor, housing/전세, divorce, traffic, criminal, immigration, etc.)
- Every law cited in the response is verified against 법제처 (law.go.kr) in real-time
- You get a structured response with specific steps you can take

**Why I built it:**
Navigating Korean law as anyone — Korean or foreigner — is confusing. Legal consultations start at ₩100,000+, and searching Naver/Google gives you outdated or wrong information. AI chatbots like ChatGPT will confidently cite Korean laws that don't exist.

**Key features:**
- Bilingual: Korean (/) and English (/en)
- Free: 2 questions per day, no account needed
- Paid: 20 queries for ₩2,100 if you need more
- All 60 legal domains covered (노동, 임대차, 이혼, 교통, 형사, 출입국, 세금, 상속, etc.)
- 법제처 DRF API로 법 조문 실시간 검증

**Disclaimer:** This is NOT a substitute for professional legal advice. It's a first-step tool to help you understand your situation.

https://lawmadi.com

Would love to hear if this is useful, especially from foreigners dealing with Korean legal issues or Koreans who've struggled to find affordable legal guidance.
```

---

## Post 6: r/MachineLearning

**Title:**
```
[P] Multi-agent legal AI with 60 domain-specialized agents, 3-layer NLU routing, and real-time government API verification
```

**Body:**
```
**TL;DR:** Built a legal AI system that routes queries through 60 specialized agents and verifies every statute citation against live government databases. Fail-closed design — unverified answers are rejected.

**System Architecture:**

```
User Query
  → NLU (regex intent patterns, 264 test cases)
  → Keyword matching (60 domain vocabularies)
  → Gemini classification (fallback)
  → Selected Agent (1 of 60)
  → RAG (Vertex AI Search, 14.6K docs)
  → Gemini 2.5 Flash (domain-tuned prompt)
  → DRF Verification (law.go.kr API, 10 data sources)
  → Structured Response
```

**Routing approach:**
3-layer routing with priority ordering. Layer 1 (regex NLU) catches ~70% of queries. Layer 2 (keyword) catches ~20%. Layer 3 (Gemini classification) handles the rest. We chose this over pure LLM routing for latency and cost reasons.

**Verification pipeline:**
The key innovation is Stage 4 — every statute citation in the generated response is extracted and verified against Korea's legislative API in real-time. We check:
- Does the cited law exist?
- Does the cited article number exist within that law?
- Is the content accurate?

If verification fails, the system applies a fail-closed policy and rejects the response.

**Current metrics:**
- 99.6% success rate (481 queries/7d)
- Verification score: 84.7/100 avg
- Latency: ~40s avg (bottleneck: Gemini generation ~30s)
- NLU accuracy: 264/264 test cases passing

**Challenges I'd love input on:**
1. Agent specialization granularity — 60 agents provides good domain coverage but maintaining 60 system prompts is non-trivial
2. Latency — Stage 3 (Gemini) takes ~30s. Streaming helps UX but doesn't reduce total time
3. Cross-lingual statute matching — Korean statute citations are 82.5% accurate but English drops to 25.6%

Live: https://lawmadi.com | Tech: FastAPI + Gemini 2.5 Flash + Vertex AI Search + Cloud Run
```

---

## Post 7: r/Entrepreneur

**Title:**
```
I built an AI legal assistant for the Korean market — 481 queries in the first week, here's what I learned
```

**Body:**
```
I launched Lawmadi OS, an AI-powered legal assistant for Korean law, and wanted to share some learnings.

**The market opportunity:**
- Korea has ~50M people, most can't afford legal consultations (starts at ₩100,000 / ~$75 per session)
- Legal information online is fragmented, outdated, or plain wrong
- AI chatbots hallucinate laws — a serious problem in the legal domain

**What I built:**
An AI system with 60 domain-specialized agents that analyze legal questions and verify every cited law against government databases in real-time. If verification fails, it refuses to answer.

**First week numbers:**
- 114 unique visitors
- 481 legal queries
- 99.6% success rate
- Most popular domains: labor law (90), housing/lease (83), divorce (50), traffic accidents (48)
- Peak hours: 10am and 1pm KST

**Business model:**
- Free: 2 queries/day (acquisition)
- Starter: 20 queries / $1.50
- Standard: 100 queries / $4.99
- Pro: 300 queries / $9.99
- Credit-based, no subscription (lower friction)
- Payments via Paddle

**What I learned:**
1. **Labor law is #1** — unfair dismissal, unpaid wages, and workplace harassment are the biggest pain points
2. **Trust matters more than speed** — users prefer waiting 40s for a verified answer over instant unverified ones
3. **Free tier is essential** — most users need 1-2 questions answered, not ongoing access
4. **Bilingual matters** — foreigners in Korea have even fewer legal resources

**Infrastructure costs:** Running on GCP Cloud Run with min 1 instance. Monthly cost is manageable at this scale.

https://lawmadi.com

Happy to answer questions about the tech, business model, or Korean market.
```

---

## 게시 순서 및 타이밍

| 순서 | 시간 (KST) | 서브레딧 | 비고 |
|:-----|:----------|:---------|:-----|
| 1 | 화~목 22:00 | r/SideProject | 미국 오전, 가장 허용적 |
| 2 | 같은 날 22:30 | r/artificial | 기술 관심 높은 시간 |
| 3 | +1시간 | r/LegalTech | 니치 커뮤니티 |
| 4 | +1시간 | r/korea | 한국 관련 |
| 5 | 토요일 22:00 | r/webdev | Showoff Saturday |
| 6 | 다음 주 초 | r/MachineLearning | [P] 태그 |
| 7 | 다음 주 초 | r/Entrepreneur | 비즈니스 앵글 |

## 주의사항
- 같은 날 3개 이상 서브레딧에 올리면 스팸 필터에 걸릴 수 있음
- 각 포스트 후 댓글에 적극 응답 (Reddit은 참여도 중요)
- 절대 크로스포스트 금지 — 각 서브레딧 맞춤 콘텐츠 필수
- r/legaladvice는 직접 포스팅 금지, 관련 질문 댓글에서만 언급
