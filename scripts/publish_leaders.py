#!/usr/bin/env python3
"""
Lawmadi OS — Batch Leader Persona Publisher (Dev.to + Hashnode)
Publishes L02-L60 persona blog posts sequentially.
"""
import json
import time
import sys
import os
import requests

DEVTO_API_KEY = "zKcasoDpi6ofxdeccErmcDNj"
HASHNODE_TOKEN = "c175d079-56cb-49ec-874d-4c5f60243395"
HASHNODE_PUB_ID = "69b28b023a0845121d627eb5"

DEVTO_URL = "https://dev.to/api/articles"
HASHNODE_URL = "https://gql.hashnode.com"

# Leader data: (id, name_ko, specialty_ko, specialty_en, en_domain_label, personality, catchphrase, topics_en)
LEADERS = [
    ("L02", "보늬", "부동산", "Real Estate Law", "PROPERTY",
     "trustworthy, meticulous, with a keen sense for real transactions",
     "부동산은 서류가 전부예요. 꼼꼼히 확인하는 게 최선의 보호입니다.",
     ["real estate", "property registration", "title deeds", "apartment transactions"]),
    ("L03", "담슬", "건설", "Construction Law", "CONSTRUCTION",
     "experienced in the field, practical, and solution-oriented",
     "현장에서 일어나는 일은 계약서가 답해줍니다.",
     ["construction disputes", "building defects", "contractor issues", "construction payment"]),
    ("L04", "아키", "재개발", "Urban Redevelopment", "REDEVELOPMENT",
     "patient, with a long-term strategic perspective",
     "재개발은 마라톤이에요. 현재 어느 단계인지가 가장 중요합니다.",
     ["redevelopment", "reconstruction", "urban renewal", "association disputes"]),
    ("L05", "연우", "의료", "Medical Law", "MEDICAL",
     "careful, scientific thinker who sees things from the patient's perspective",
     "의료 분쟁에서 가장 중요한 건 기록입니다.",
     ["medical malpractice", "hospital disputes", "patient rights", "medical negligence"]),
    ("L06", "벼리", "손해배상", "Damages & Compensation", "DAMAGES",
     "analytical, strong with numbers, committed to fair compensation",
     "감정이 아니라 숫자로 보상을 받는 겁니다.",
     ["personal injury", "compensation claims", "liability disputes", "settlement negotiation"]),
    ("L07", "하늬", "교통사고", "Traffic Accidents", "TRAFFIC",
     "swift, practical, thinking from the victim's perspective",
     "교통사고는 초기 대응이 결과를 좌우합니다.",
     ["car accidents", "traffic liability", "insurance claims", "fault determination"]),
    ("L08", "온유", "임대차", "Lease & Housing", "LEASE",
     "warm, calm, and deeply connected to everyday life",
     "집은 삶의 기본이에요. 당신의 주거 권리를 지켜드릴게요.",
     ["tenant rights", "deposit disputes", "jeonse fraud", "lease contracts"]),
    ("L09", "한울", "국가계약", "Government Contracts", "GOV_CONTRACT",
     "systematic, well-versed in procedures, understanding of the public sector",
     "공공 계약은 절차가 권리입니다. 기한을 놓치지 마세요.",
     ["government procurement", "public bidding", "tender disputes", "public contracts"]),
    ("L10", "결휘", "민사집행", "Civil Enforcement", "EXECUTION",
     "action-oriented, results-focused, concentrated on debt recovery",
     "판결문은 시작이고, 집행이 진짜 결과입니다.",
     ["debt enforcement", "asset seizure", "garnishment", "court judgments"]),
    ("L11", "오름", "채권추심", "Debt Collection & Recovery", "COLLECTION",
     "persistent, strategic, firmly protecting creditor rights",
     "채권은 시간이 지나면 사라집니다. 소멸시효를 확인하세요.",
     ["debt collection", "bankruptcy", "credit recovery", "statute of limitations"]),
    ("L12", "아슬", "등기·경매", "Registry & Auction", "AUCTION",
     "meticulous, detail-oriented, excellent at rights analysis",
     "등기부는 부동산의 이력서입니다. 한 줄도 놓치지 마세요.",
     ["property auction", "foreclosure", "registry analysis", "title search"]),
    ("L13", "누리", "상사", "Commercial Law", "COMMERCIAL",
     "logical, practical, with excellent business sense",
     "법을 아는 것이 곧 사업의 경쟁력입니다.",
     ["commercial transactions", "promissory notes", "merchant law", "business disputes"]),
    ("L14", "다솜", "회사·M&A", "Corporate & M&A", "CORP_MA",
     "strategic, with a macro perspective, skilled in deals",
     "좋은 딜은 좋은 구조에서 나옵니다.",
     ["mergers and acquisitions", "shareholder disputes", "corporate governance", "board liability"]),
    ("L15", "별하", "스타트업", "Startup & Venture", "STARTUP",
     "understands entrepreneurial spirit, supportive of growth, practical",
     "좋은 아이디어를 지키는 것도 법의 역할입니다!",
     ["startup law", "venture investment", "partnership disputes", "business registration"]),
    ("L16", "슬아", "보험", "Insurance Law", "INSURANCE",
     "meticulous, skilled at finding traps in insurance policies",
     "약관은 보험사가 만들었지만, 해석은 법이 합니다.",
     ["insurance claims", "policy disputes", "coverage denial", "insurance fraud"]),
    ("L17", "미르", "국제거래", "International Trade Law", "INTL_TRADE",
     "global perspective, practical, skilled in negotiation",
     "국경을 넘는 거래에도 법의 보호는 따라갑니다.",
     ["international contracts", "cross-border disputes", "arbitration", "trade law"]),
    ("L18", "다온", "에너지·자원", "Energy & Resources", "ENERGY",
     "interested in future energy, values sustainability",
     "에너지 전환의 시대, 법이 그 길을 열어줍니다.",
     ["energy regulation", "renewable energy", "power plant disputes", "resource law"]),
    ("L19", "슬옹", "해상·항공", "Maritime & Aviation", "MARINE_AIR",
     "deeply specialized, internationally minded, calm",
     "바다와 하늘 위에서도 법은 적용됩니다.",
     ["maritime law", "aviation disputes", "shipping contracts", "cargo claims"]),
    ("L20", "찬솔", "조세·금융", "Tax & Finance", "TAX_FIN",
     "cool-headed, analytical, with deep understanding of financial systems",
     "세금은 미리 알면 절세, 모르면 추징이에요.",
     ["tax planning", "income tax", "capital gains", "financial regulation"]),
    ("L21", "휘윤", "IT·보안", "IT & Cybersecurity", "IT_SEC",
     "tech-savvy, strong security awareness, modern",
     "보안은 기술만의 문제가 아니라 법적 의무입니다.",
     ["cybersecurity", "data breaches", "hacking disputes", "IT contracts"]),
    ("L22", "무결", "형사", "Criminal Law", "CRIMINAL",
     "strong sense of justice, straightforward, dependable",
     "최악의 상황을 알아야 최선의 대비를 할 수 있습니다.",
     ["criminal defense", "fraud", "assault", "police investigations"]),
    ("L23", "가비", "엔터테인먼트", "Entertainment Law", "ENTERTAIN",
     "trendy, with deep understanding of the entertainment industry",
     "재능을 지키는 것도 전략입니다!",
     ["talent contracts", "entertainment disputes", "celebrity rights", "management law"]),
    ("L24", "도울", "조세불복", "Tax Appeals", "TAX_APPEAL",
     "persistent, deep understanding of tax administration, pro-taxpayer",
     "세금도 잘못 부과될 수 있고, 바로잡을 권리가 있습니다.",
     ["tax appeals", "tax audits", "assessment disputes", "tax tribunal"]),
    ("L25", "강무", "군형법", "Military Law", "MILITARY",
     "strict yet respectful of soldiers' human rights",
     "군복을 입었다고 권리까지 벗는 건 아닙니다.",
     ["military justice", "conscription", "soldier rights", "military court"]),
    ("L26", "루다", "지식재산", "Intellectual Property", "IP",
     "creative, respects innovation, passionate about rights protection",
     "아이디어도 자산입니다. 보호받을 가치가 있어요!",
     ["patents", "trademarks", "trade secrets", "IP disputes"]),
    ("L27", "수림", "환경", "Environmental Law", "ENVIRON",
     "principled, loves the environment, thinks of future generations",
     "환경 문제는 모두의 문제이고, 법은 그 해결의 도구입니다.",
     ["pollution disputes", "environmental regulation", "waste management", "noise complaints"]),
    ("L28", "해슬", "무역·관세", "Trade & Customs", "CUSTOMS",
     "practical, well-versed in international trade, meticulous",
     "관세는 미리 확인하면 절약, 모르면 추징입니다.",
     ["customs duties", "import/export", "FTA", "trade compliance"]),
    ("L29", "라온", "게임·콘텐츠", "Gaming & Content", "GAME",
     "trendy, understands digital culture, respects creators",
     "재미있는 콘텐츠에도 법의 틀이 있습니다!",
     ["gaming regulation", "digital content", "virtual items", "content creator rights"]),
    ("L30", "담우", "노동", "Labor & Employment", "LABOR",
     "empathetic, always thinking from the worker's perspective",
     "당신의 노동은 법으로 보호받고 있어요.",
     ["unfair dismissal", "unpaid wages", "workplace harassment", "labor rights"]),
    ("L31", "로운", "행정", "Administrative Law", "ADMIN",
     "systematic, meticulous, and procedure-oriented",
     "행정은 절차가 곧 권리입니다.",
     ["administrative appeals", "permits and licenses", "government fines", "administrative litigation"]),
    ("L32", "바름", "공정거래", "Fair Trade & Antitrust", "FAIRTRADE",
     "strong sense of justice, values market fairness, analytical",
     "공정한 시장이 모두에게 이익입니다.",
     ["antitrust", "monopoly regulation", "franchise disputes", "fair competition"]),
    ("L33", "별이", "우주항공", "Space & Aerospace", "SPACE",
     "future-oriented, tech-savvy, deeply curious",
     "하늘과 우주에도 법의 경계는 있습니다.",
     ["drone regulation", "satellite law", "aerospace", "space law"]),
    ("L34", "지누", "개인정보", "Privacy & Data Protection", "PRIVACY",
     "meticulous, respects privacy, attentive",
     "당신의 정보는 당신의 것입니다.",
     ["data protection", "GDPR", "privacy breaches", "CCTV surveillance"]),
    ("L35", "마루", "헌법", "Constitutional Law", "CONSTITUTION",
     "thoughtful, balanced perspective, idealistic",
     "헌법은 우리 모두의 약속이자 최소한의 상식이에요.",
     ["constitutional rights", "judicial review", "fundamental rights", "constitutional court"]),
    ("L36", "단아", "문화·종교", "Cultural Heritage & Religion", "CULTURE",
     "inclusive, respects diversity, deeply knowledgeable",
     "다양성 속에서도 법은 공통의 기준을 제시합니다.",
     ["cultural heritage", "religious freedom", "cultural property", "tradition preservation"]),
    ("L37", "예솔", "소년법", "Juvenile Law", "JUVENILE",
     "warm, educational, thinking about children's futures",
     "아이에게는 처벌보다 기회가 필요합니다.",
     ["juvenile justice", "school violence", "bullying", "youth protection"]),
    ("L38", "슬비", "소비자", "Consumer Protection", "CONSUMER",
     "justice-minded, firmly advocates consumer rights",
     "소비자의 권리는 생각보다 강합니다.",
     ["consumer rights", "refund disputes", "product liability", "warranty claims"]),
    ("L39", "가온", "정보통신", "Telecommunications", "TELECOM",
     "tech-trend aware, understands digital regulation well",
     "기술은 빠르게 변하지만, 법은 그 기준을 세워줍니다.",
     ["telecom regulation", "broadcast disputes", "carrier issues", "ISP liability"]),
    ("L40", "한결", "인권", "Human Rights", "HUMAN_RIGHTS",
     "respects minorities, sensitive to discrimination, prioritizes human dignity",
     "모든 사람은 존엄하고, 그 존엄은 법이 보호합니다.",
     ["anti-discrimination", "equality", "hate speech", "human dignity"]),
    ("L41", "산들", "가족·이혼", "Family & Divorce", "DIVORCE",
     "emotional yet realistic, thinking about everyone's happiness in the family",
     "이별이 끝이 아니라, 새로운 시작이 될 수 있어요.",
     ["divorce proceedings", "child custody", "alimony", "property division"]),
    ("L42", "하람", "저작권", "Copyright", "COPYRIGHT",
     "respects creators, deep understanding of cultural industry",
     "창작물에는 만든 사람의 영혼이 담겨 있습니다.",
     ["copyright protection", "plagiarism", "fair use", "DMCA"]),
    ("L43", "해나", "산업재해", "Industrial Accidents", "INDUSTRIAL",
     "genuinely cares about worker health and safety, field-savvy",
     "일하다 다친 것은 당신의 잘못이 아닙니다.",
     ["workplace injuries", "workers compensation", "occupational safety", "industrial accidents"]),
    ("L44", "보람", "사회복지", "Social Welfare", "WELFARE",
     "warm, deeply understanding of vulnerable groups, inclusive",
     "받을 수 있는 도움은 받는 것이 권리입니다.",
     ["welfare benefits", "social security", "basic living support", "public assistance"]),
    ("L45", "이룸", "교육·청소년", "Education & Youth", "EDUCATION",
     "educational, future-minded, communicates well with parents",
     "교육은 미래를 만드는 일이고, 법은 그 과정을 보호합니다.",
     ["education disputes", "school issues", "tuition", "student rights"]),
    ("L46", "다올", "보험·연금", "Pension & Insurance", "PENSION",
     "meticulous, long-term perspective on retirement planning",
     "노후는 준비하는 만큼 안정됩니다. 제도를 알면 유리해요.",
     ["national pension", "retirement planning", "health insurance", "pension disputes"]),
    ("L47", "새론", "벤처·신산업", "Venture & New Industries", "VENTURE",
     "innovative, open-minded about new technology, pragmatic",
     "혁신에도 법의 보호막이 필요합니다!",
     ["regulatory sandbox", "new industry regulation", "special zones", "innovation law"]),
    ("L48", "나래", "문화예술", "Arts & Culture", "ARTS",
     "artistic sensibility combined with legal logic, creative",
     "예술은 자유이지만, 그 자유를 지키려면 법이 필요합니다.",
     ["artist rights", "performance law", "exhibition disputes", "cultural arts"]),
    ("L49", "가람", "식품·보건", "Food & Health Safety", "FOOD",
     "meticulous, prioritizes safety, well-versed in regulations",
     "안전은 규제의 목적이고, 규제 준수가 최선의 사업 전략입니다.",
     ["food safety", "pharmaceutical regulation", "HACCP", "health compliance"]),
    ("L50", "빛나", "다문화·이주", "Multicultural & Immigration", "MULTICUL",
     "global, open-minded about multiculturalism, advocates for migrant rights",
     "국경을 넘는 일에도 길은 있습니다.",
     ["immigration", "visa issues", "refugee rights", "naturalization"]),
    ("L51", "소울", "종교·전통", "Religion & Tradition", "RELIGION",
     "deeply thoughtful, respects traditional culture",
     "전통과 법이 만나는 곳에서 지혜를 찾습니다.",
     ["religious freedom", "temple disputes", "church governance", "traditional law"]),
    ("L52", "미소", "광고·언론", "Media & Press", "MEDIA",
     "respects freedom of expression while emphasizing responsibility, balanced",
     "말의 자유에는 말의 책임이 따릅니다.",
     ["online defamation", "press freedom", "media regulation", "hate comments"]),
    ("L53", "늘솔", "농림·축산", "Agriculture & Livestock", "AGRI",
     "loves rural life and nature, advocates for farmers' rights",
     "농업은 나라의 근간이고, 법이 농민을 지켜야 합니다.",
     ["farmland disputes", "agricultural regulation", "livestock law", "crop damage"]),
    ("L54", "이서", "해양·수산", "Marine & Fisheries", "FISHERY",
     "deep expert in ocean and fisheries industries",
     "바다의 자원도 법의 보호 아래 있습니다.",
     ["fishing rights", "marine regulation", "aquaculture disputes", "ocean resources"]),
    ("L55", "윤빛", "과학기술", "Science & Technology", "SCIENCE",
     "future-oriented, values the legal foundation of scientific progress",
     "과학의 발전에도 법의 뒷받침이 필요합니다.",
     ["R&D regulation", "technology transfer", "research ethics", "science policy"]),
    ("L56", "다인", "장애인·복지", "Disability Rights", "DISABILITY",
     "inclusive, values accessibility, respects the perspective of those affected",
     "장벽 없는 세상은 법에서부터 시작됩니다.",
     ["disability discrimination", "accessibility law", "accommodation rights", "disability welfare"]),
    ("L57", "세움", "상속·신탁", "Inheritance & Trust", "INHERITANCE",
     "long-term planner, helps preserve and transfer assets strategically",
     "자산은 모으는 것만큼 지키고 물려주는 것이 중요합니다.",
     ["inheritance disputes", "wills and probate", "trust management", "estate planning"]),
    ("L58", "예온", "스포츠·레저", "Sports & Leisure", "SPORTS",
     "active, loves sports culture, passionate about protecting athletes",
     "경기장 밖에서도 선수의 권리는 보호받아야 합니다!",
     ["player contracts", "doping disputes", "sports regulation", "athlete rights"]),
    ("L59", "한빛", "데이터·AI윤리", "Data & AI Ethics", "AI_ETHICS",
     "future-oriented, deeply thoughtful about technology ethics",
     "기술은 중립이지만, 사용에는 책임이 따릅니다.",
     ["AI regulation", "algorithm fairness", "data governance", "machine learning ethics"]),
    ("L60", "마디", "시스템 총괄", "General Legal Coordinator", "SYSTEM",
     "coordinates all domains, sees the big picture",
     "어디서부터 시작해야 할지 모르실 때, 저부터 찾아주세요.",
     ["legal guidance", "multi-domain issues", "case routing", "legal system overview"]),
]

def generate_post_content(lid, name, spec_ko, spec_en, personality, catchphrase, topics):
    """Generate a 1st-person persona blog post in English."""
    num = lid[1:]  # e.g., "02"

    # Topic-specific scenario examples
    topic_str = ", ".join(topics[:3])

    content = f"""
> *"{catchphrase}"*
> — {name}, {spec_en} Specialist at Lawmadi OS

## Hello! I'm {name} (Leader {num})

I'm **{name}** ({spec_ko} 전문), Leader {num} of [Lawmadi OS](https://lawmadi.com) — an AI-powered legal operating system for Korean law. My specialty is **{spec_en}**, and I'm here to help anyone navigating {topics[0]}, {topics[1]}, and {topics[2]} under Korean law.

I'm {personality}. When you bring me a legal question in my domain, I don't just give you a generic answer — I analyze your specific situation, cite the exact statutes, and build you a step-by-step action plan.

## What Makes Me Different from ChatGPT?

Every statute I cite is **verified in real-time** against Korea's official legislative database (법제처). If I can't verify a law, I refuse to answer rather than risk giving you wrong information. That's the Lawmadi promise — **no hallucinated laws, ever**.

### My Verification Process:
1. You ask me about {topics[0]}
2. I analyze your situation using my domain-tuned knowledge
3. I find the relevant statutes and articles
4. **Stage 4 DRF Verification** checks every citation against live government data
5. Only verified information reaches you

## What I Help With

Here are the kinds of questions I handle every day:

{"".join(f"- **{t.title()}** — understanding your rights, building your case, knowing your options{chr(10)}" for t in topics)}
### A Typical Conversation

When someone comes to me, I follow Lawmadi's empathy-first framework:

1. **I acknowledge your situation** — legal problems are stressful, and I understand that
2. **I diagnose the legal issue** — what laws apply, what's the precedent
3. **I give you an action roadmap** — specific steps, costs, timelines
4. **I provide safety nets** — legal aid resources, free consultation options
5. **I encourage you** — you're not alone in this

## I'm Part of a 60-Agent Team

Lawmadi OS has 60 specialized legal AI agents. If your question crosses into another domain, I'll connect you with the right specialist:

- Need help with labor disputes? → **담우** (Labor Law)
- Housing deposit issues? → **온유** (Lease & Housing)
- Criminal matters? → **무결** (Criminal Law)
- Family law questions? → **산들** (Family & Divorce)

Our 3-layer NLU routing system automatically matches you with the right expert — regex patterns catch 70% of queries instantly, keyword matching handles 20%, and Gemini AI classifies the rest.

## Try Talking to Me

You can chat with me right now at [lawmadi.com](https://lawmadi.com). Ask me anything about **{spec_en.lower()}** in Korean law — I'll give you a verified, empathy-first response.

[![Chat with {name}](https://img.shields.io/badge/💬_Chat_with_{name}-{spec_en.replace(' ', '_')}-blue?style=for-the-badge)](https://lawmadi.com/?leader={name})

**Free**: 2 queries/day, no account needed.

---

## The Tech Behind Lawmadi OS

| Component | Technology |
|-----------|------------|
| Backend | Python / FastAPI |
| LLM | Google Gemini 2.5 Flash |
| RAG | Vertex AI Search (14,601 legal docs) |
| Verification | 법제처 DRF API (10 gov sources) |
| Database | Cloud SQL PostgreSQL 17 |
| Hosting | GCP Cloud Run + Firebase |

## My Promise

*"{catchphrase}"*

That's not just a saying — it's how I approach every single consultation. Whether you're a Korean citizen, an expat in Seoul, or researching Korean law from abroad, I'm here to help.

**Come talk to me**: [https://lawmadi.com](https://lawmadi.com)

[![Start a Legal Consultation](https://img.shields.io/badge/🏛️_Start_Legal_Consultation-Lawmadi_OS-green?style=for-the-badge)](https://lawmadi.com/?leader={name})
"""
    return content.strip()


def generate_title(lid, name, spec_en):
    num = lid[1:]
    return f"I'm {name}, Leader {num} of Lawmadi OS — Your AI {spec_en} Expert for Korean Law"


def publish_devto(title, content, tags):
    """Publish to Dev.to"""
    payload = {
        "article": {
            "title": title,
            "published": True,
            "body_markdown": content,
            "tags": tags[:4],  # max 4 tags
            "series": "Lawmadi OS Leaders"
        }
    }
    resp = requests.post(
        DEVTO_URL,
        headers={"api-key": DEVTO_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("id"), data.get("url")


def publish_hashnode(title, content, tags):
    """Publish to Hashnode"""
    # Hashnode tags: use slugified versions
    hn_tags = [{"slug": t.lower().replace(" ", "-").replace("&", "and"), "name": t} for t in tags[:5]]

    mutation = """
    mutation PublishPost($input: PublishPostInput!) {
        publishPost(input: $input) {
            post { id url title }
        }
    }
    """
    variables = {
        "input": {
            "title": title,
            "contentMarkdown": content,
            "publicationId": HASHNODE_PUB_ID,
            "tags": hn_tags,
        }
    }
    resp = requests.post(
        HASHNODE_URL,
        headers={"Authorization": HASHNODE_TOKEN, "Content-Type": "application/json"},
        json={"query": mutation, "variables": variables},
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise Exception(f"Hashnode error: {data['errors']}")

    post = data["data"]["publishPost"]["post"]
    return post["id"], post["url"]


def main():
    # Allow starting from a specific leader
    start_idx = 0
    if len(sys.argv) > 1:
        start_from = sys.argv[1]  # e.g., "L05"
        for i, leader in enumerate(LEADERS):
            if leader[0] == start_from:
                start_idx = i
                break

    results = []

    for i, (lid, name, spec_ko, spec_en, domain_label, personality, catchphrase, topics) in enumerate(LEADERS[start_idx:], start=start_idx):
        num = lid[1:]
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(LEADERS)}] Publishing {lid} {name} ({spec_en})...")
        print(f"{'='*60}")

        title = generate_title(lid, name, spec_en)
        content = generate_post_content(lid, name, spec_ko, spec_en, personality, catchphrase, topics)

        tags_devto = ["ai", "legaltech", "korean", spec_en.lower().replace(" ", "").replace("&", "")[:20]]
        tags_hashnode = ["AI", "LegalTech", "Korean Law", spec_en]

        # Dev.to
        try:
            devto_id, devto_url = publish_devto(title, content, tags_devto)
            print(f"  ✅ Dev.to: {devto_url} (ID: {devto_id})")
        except Exception as e:
            devto_id, devto_url = None, None
            print(f"  ❌ Dev.to failed: {e}")

        # Rate limit pause
        time.sleep(2)

        # Hashnode
        try:
            hn_id, hn_url = publish_hashnode(title, content, tags_hashnode)
            print(f"  ✅ Hashnode: {hn_url} (ID: {hn_id})")
        except Exception as e:
            hn_id, hn_url = None, None
            print(f"  ❌ Hashnode failed: {e}")

        results.append({
            "leader": lid,
            "name": name,
            "specialty": spec_en,
            "devto_id": devto_id,
            "devto_url": devto_url,
            "hashnode_id": hn_id,
            "hashnode_url": hn_url,
        })

        # Rate limit: Dev.to allows 10 articles/30s, be conservative
        if (i + 1) % 8 == 0:
            print(f"\n⏳ Rate limit pause (30s)...")
            time.sleep(30)
        else:
            time.sleep(4)

    # Save results
    outfile = "scripts/publish_results.json"
    with open(outfile, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n\n{'='*60}")
    print(f"DONE! Published {len(results)} leaders.")
    print(f"Results saved to {outfile}")

    # Summary
    devto_ok = sum(1 for r in results if r["devto_id"])
    hn_ok = sum(1 for r in results if r["hashnode_id"])
    print(f"  Dev.to: {devto_ok}/{len(results)} success")
    print(f"  Hashnode: {hn_ok}/{len(results)} success")

    # Print any failures
    failures = [r for r in results if not r["devto_id"] or not r["hashnode_id"]]
    if failures:
        print(f"\n⚠️ Failures:")
        for r in failures:
            if not r["devto_id"]:
                print(f"  {r['leader']} {r['name']}: Dev.to failed")
            if not r["hashnode_id"]:
                print(f"  {r['leader']} {r['name']}: Hashnode failed")


if __name__ == "__main__":
    main()
