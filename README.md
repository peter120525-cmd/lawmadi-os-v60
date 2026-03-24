# 법마디(Lawmadi) OS — Korean Legal AI

> **60 specialized AI legal agents** with real-time statute verification via [law.go.kr](https://www.law.go.kr)

[![Cloud Run](https://img.shields.io/badge/Cloud%20Run-online-brightgreen)](https://lawmadi.com)
[![Tests](https://img.shields.io/badge/tests-282%20passed-brightgreen)]()
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://lawmadi.com/mcp)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)

**[lawmadi.com](https://lawmadi.com)** · [MCP Endpoint](https://lawmadi.com/mcp) · [API Docs](https://lawmadi.com/.well-known/openapi-public.json)

---

## What is Lawmadi OS?

Lawmadi OS is a Korean legal AI service that routes your legal question to the most relevant specialist among **60 domain-specific AI agents**. Every statute citation is verified in real-time against Korea's official legislative database.

### Key Features

- **60 Legal Domains** — Labor, housing, divorce, criminal, tax, corporate, IP, immigration, and 52 more
- **Real-time Statute Verification** — Every cited law article is checked against law.go.kr (DRF API)
- **Bilingual** — Korean & English (`lang: ko` / `lang: en`)
- **MCP Compatible** — Works with Claude Desktop, Cursor, and any MCP client
- **Free Tier** — 2 queries/day, no auth required

## Architecture

```
User Query
    │
    ▼
┌─────────────┐
│  NLU Router  │  ← Regex + keyword + fallback classification
└──────┬──────┘
       │ selects 1 of 60 specialist agents
       ▼
┌─────────────────────────────────┐
│  3-Stage Legal Pipeline         │
│                                 │
│  Stage 0: Query Classification  │  (parallel)
│  Stage 1: RAG Statute Search    │  (parallel)
│  Stage 2: Gemini LLM Analysis   │
│  Stage 3: DRF Verification      │  ← real-time law.go.kr check
└─────────────────────────────────┘
       │
       ▼
  Verified Legal Response
```

## Quick Start

### As an MCP Server (Recommended)

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lawmadi": {
      "url": "https://lawmadi.com/mcp"
    }
  }
}
```

### As a REST API

```bash
# Ask a legal question
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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Legal question → verified analysis |
| `/ask-stream` | POST | Same as `/ask`, SSE streaming |
| `/ask-expert` | POST | Expert mode (full 4-stage pipeline) |
| `/api/leaders` | GET | List all 60 specialist agents |
| `/api/chat-leader` | POST | 1:1 chat with a specific agent |
| `/search` | GET | Search legal topics |
| `/mcp` | POST | MCP protocol endpoint |

## 60 Legal Domains

<details>
<summary>View all domains</summary>

Civil Law · Real Estate · Construction · Urban Redevelopment · Medical Law · Damages · Traffic Accidents · Lease & Housing · Government Contracts · Civil Enforcement · Debt Collection · Registry & Auction · Commercial Law · Corporate & M&A · Startup & Venture · Insurance · International Trade · Energy & Resources · Maritime & Aviation · Tax & Finance · IT & Cybersecurity · Criminal Law · Entertainment · Tax Appeals · Military Law · Intellectual Property · Environmental Law · Trade & Customs · Gaming & Content · Labor & Employment · Administrative Law · Fair Trade · Space & Aerospace · Privacy & Data Protection · Constitutional Law · Cultural Heritage · Juvenile Law · Consumer Protection · Telecommunications · Human Rights · Family & Divorce · Copyright · Industrial Accidents · Social Welfare · Education & Youth · Pension & Insurance · Venture & New Industries · Arts & Culture · Food & Health Safety · Multicultural & Immigration · Religion & Tradition · Media & Press · Agriculture & Livestock · Marine & Fisheries · Science & Technology · Disability Rights · Inheritance & Trust · Sports & Leisure · Data & AI Ethics · General Legal

</details>

## Tech Stack

- **Backend**: Python, FastAPI, Google Cloud Run
- **LLM**: Gemini Flash (via Vertex AI)
- **Database**: Cloud SQL (PostgreSQL 17)
- **Law Data**: law.go.kr DRF API (real-time verification)
- **Frontend**: Firebase Hosting
- **MCP**: fastapi-mcp
- **Payments**: Paddle

## Tests

```bash
pytest tests/ -v  # 282 tests
```

## License

[AGPL-3.0](LICENSE) — You may use, modify, and distribute this software. If you run a modified version as a network service, you must release your source code under the same license.

Copyright (c) 2025-2026 peter120525-cmd
