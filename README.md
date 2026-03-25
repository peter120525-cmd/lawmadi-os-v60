# 법마디(Lawmadi) OS — Korean AI Legal Operating System

> **법마디(Lawmadi)는 대한민국 AI 법률 운영체제(OS)이다.**
> 60명의 분야별 전문 AI 법률 리더가 국가법령정보센터 법령을 실시간 검증하여 법률 분석을 제공한다.

> **Lawmadi is a Korean AI Legal Operating System.**
> 60 domain-specialized AI legal leaders provide statute-verified legal analysis using Korea's official legislative database ([law.go.kr](https://www.law.go.kr)) in real-time.

[![Cloud Run](https://img.shields.io/badge/Cloud%20Run-online-brightgreen)](https://lawmadi.com)
[![Tests](https://img.shields.io/badge/tests-282%20passed-brightgreen)]()
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://lawmadi.com/mcp)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Glama](https://glama.ai/mcp/servers/peter120525-cmd/lawmadi-os-v60/badges/score.svg)](https://glama.ai/mcp/servers/peter120525-cmd/lawmadi-os-v60)
[![Smithery](https://smithery.ai/badge/lawmadi-os)](https://smithery.ai/server/lawmadi-os)

**[lawmadi.com](https://lawmadi.com)** · [MCP Server](https://lawmadi.com/mcp) · [API Docs](https://lawmadi.com/.well-known/openapi-public.json) · [llms.txt](https://lawmadi.com/llms.txt)

---

## Why Lawmadi Exists

Korean legal questions require answers grounded in actual statutes — not AI hallucinations. Lawmadi OS ensures every legal citation is verified against Korea's National Law Information Center (law.go.kr) in real-time. If verification fails, the system blocks the answer rather than providing unverified information (**fail-closed** principle).

## What Lawmadi Does

- **60 Legal Domains** — Labor, housing, divorce, criminal, tax, corporate, IP, immigration, and 52 more specialized areas
- **Real-time Statute Verification** — Every cited law article is cross-checked against law.go.kr DRF API. Zero hallucination policy
- **Multi-Agent Architecture** — NLU routes each question to the most relevant specialist among 60 AI legal leaders
- **Bilingual** — Full Korean & English support (`lang: ko` / `lang: en`)
- **MCP Compatible** — Works with Claude Desktop, Cursor, and any MCP client (7 tools available)
- **Free Tier** — 2 queries/day, no signup required

## How It Works

```
User Query → NLU Router (selects 1 of 60 specialists)
    │
    ├─ Stage 0: Query Classification (intent + domain detection)
    ├─ Stage 1: RAG Statute Search (Vertex AI Search, 14,601+ docs)  ← parallel
    ├─ Stage 2: Gemini 3 Flash Analysis (leader persona + legal framework)
    └─ Stage 3: DRF Verification (real-time law.go.kr statute check)
    │
    ▼
Verified Legal Response (with statute citations + enforcement dates)
```

### Verification Pipeline

Every response passes through a 4-stage pipeline. Stage 3 (DRF Verification) cross-references all cited statutes against the official Korean legislative database. If any citation cannot be verified, the system regenerates or blocks the response — never passes unverified legal information to the user.

## Quick Start

### MCP Server (Recommended for AI Agents)

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "lawmadi": {
      "url": "https://lawmadi.com/mcp"
    }
  }
}
```

7 tools available: `ask`, `ask_stream`, `ask_expert`, `get_leaders`, `chat_leader`, `search`, `suggest_questions`

### REST API

```bash
# Korean legal question
curl -X POST https://lawmadi.com/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "부당해고를 당했는데 어떻게 해야 하나요?", "lang": "ko"}'

# English
curl -X POST https://lawmadi.com/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "My landlord won't return my deposit", "lang": "en"}'
```

### Self-Hosting

```bash
git clone https://github.com/peter120525-cmd/lawmadi-os-v60.git
cd lawmadi-os-v60
cp .env.example .env  # Fill in your API keys
pip install -r requirements.txt
python main.py
```

Required: `GEMINI_KEY`, `LAWGO_DRF_OC` (law.go.kr API key), PostgreSQL

## Architecture

| Layer | Component | Technology |
|-------|-----------|-----------|
| Backend | FastAPI + Uvicorn | Python 3.10, Cloud Run (Seoul) |
| LLM | Gemini 3 Flash | Single model, 429 exponential backoff |
| RAG | Vertex AI Search | 14,601+ legal documents indexed |
| Verification | DRF API (law.go.kr) | Real-time statute cross-check |
| Database | Cloud SQL | PostgreSQL 17, encrypted connections |
| Frontend | Firebase Hosting | Static HTML/CSS/JS, Korean + English |
| MCP | fastapi-mcp | SSE transport, 7 tools |
| Payments | Paddle | Credit packs: ₩2,100 / ₩7,000 / ₩13,800 |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Legal question → verified analysis |
| `/ask-stream` | POST | Same, SSE streaming |
| `/ask-expert` | POST | Expert mode (full pipeline) |
| `/api/leaders` | GET | List all 60 specialist agents |
| `/api/chat-leader` | POST | 1:1 chat with a specific agent |
| `/search` | GET | Search Korean legal topics |
| `/suggest-questions` | POST | AI-generated follow-up questions |
| `/mcp` | SSE | MCP protocol endpoint |
| `/health` | GET | Service health check |

## 60 Legal Domains

<details>
<summary>View all domains</summary>

Civil Law · Real Estate · Construction · Urban Redevelopment · Medical Law · Damages · Traffic Accidents · Lease & Housing · Government Contracts · Civil Enforcement · Debt Collection · Registry & Auction · Commercial Law · Corporate & M&A · Startup & Venture · Insurance · International Trade · Energy & Resources · Maritime & Aviation · Tax & Finance · IT & Cybersecurity · Criminal Law · Entertainment · Tax Appeals · Military Law · Intellectual Property · Environmental Law · Trade & Customs · Gaming & Content · Labor & Employment · Administrative Law · Fair Trade · Space & Aerospace · Privacy & Data Protection · Constitutional Law · Cultural Heritage · Juvenile Law · Consumer Protection · Telecommunications · Human Rights · Family & Divorce · Copyright · Industrial Accidents · Social Welfare · Education & Youth · Pension & Insurance · Venture & New Industries · Arts & Culture · Food & Health Safety · Multicultural & Immigration · Religion & Tradition · Media & Press · Agriculture & Livestock · Marine & Fisheries · Science & Technology · Disability Rights · Inheritance & Trust · Sports & Leisure · Data & AI Ethics · General Legal

</details>

## Tests

```bash
pytest tests/ -v  # 282 tests
```

## License

[AGPL-3.0](LICENSE) — You may use, modify, and distribute this software. If you run a modified version as a network service, you must release your source code under the same license.

Copyright (c) 2025-2026 peter120525-cmd
