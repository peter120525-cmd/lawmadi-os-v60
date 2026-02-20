#!/usr/bin/env python3
"""
law_cache.json 생성 스크립트 — SSOT 10종 전체 적용 + TOP 100
v40 학습 데이터(85,909 Q&A)에서 SSOT 10종 카테고리별 핵심 내용 추출

SSOT 10종:
  law    현행법령        admrul  행정규칙      ordin   자치법규
  expc   법령해석례      prec    판례          decis   헌재결정례
  lstrm  법령용어        decc    행정심판례    trty    조약
  unlaw  훈령/예규/고시
"""
import json
import re
import sys
from collections import defaultdict, Counter

DATA_PATH = "/home/peter120525/LawmadiLM/data/processed/all_qa_dataset_v40.jsonl"
OUTPUT_PATH = "/home/peter120525/Lawmadi-OS/law_cache.json"
REGISTRY_PATH = "/home/peter120525/LawmadiLM/data/leaders_registry.json"

TOP_N = 100  # 법률별 상위 조문 수

# ── SSOT 10종 정의 ──────────────────────────────────────────
SSOT_TYPES = {
    "law":    {"label": "현행법령",      "target": "law",    "endpoint": "lawSearch.do"},
    "admrul": {"label": "행정규칙",      "target": "admrul", "endpoint": "lawSearch.do"},
    "ordin":  {"label": "자치법규",      "target": "ordin",  "endpoint": "lawSearch.do"},
    "expc":   {"label": "법령해석례",    "target": "expc",   "endpoint": "lawSearch.do"},
    "prec":   {"label": "판례",          "target": "prec",   "endpoint": "lawSearch.do"},
    "decis":  {"label": "헌재결정례",    "target": "prec",   "endpoint": "lawSearch.do"},
    "lstrm":  {"label": "법령용어",      "target": "lstrm",  "endpoint": "lawSearch.do"},
    "decc":   {"label": "행정심판례",    "target": "decc",   "endpoint": "lawService.do"},
    "trty":   {"label": "조약",          "target": "trty",   "endpoint": "lawService.do"},
    "unlaw":  {"label": "훈령/예규/고시","target": "admrul",  "endpoint": "lawSearch.do"},
}

# ── SSOT 타입 분류 키워드 ──────────────────────────────────
TYPE_KEYWORDS = {
    "prec":   ["판례", "판결", "대법원", "대법", "선고", "판시", "법원"],
    "admrul": ["행정규칙", "시행규칙", "시행령"],
    "ordin":  ["자치법규", "조례", "지방자치"],
    "expc":   ["법령해석", "해석례", "유권해석", "법제처"],
    "decis":  ["헌법재판", "헌재", "위헌", "헌법재판소", "합헌", "헌법불합치"],
    "lstrm":  ["법령용어", "법률용어", "용어의 뜻", "정의규정"],
    "decc":   ["행정심판", "심판청구", "재결"],
    "trty":   ["조약", "국제협약", "국제법", "협정"],
    "unlaw":  ["훈령", "예규", "고시", "지침"],
}

# ── 법률 목록 로드 ──────────────────────────────────────────
with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
    registry = json.load(f)
ALL_LAWS = registry.get("statistics", {}).get("all_laws_list", [])
EXTRA_LAWS = ["민법", "형법", "상법", "헌법", "근로기준법", "주택임대차보호법",
              "상가건물임대차보호법", "형사소송법", "민사소송법", "도로교통법",
              "국세기본법", "소득세법", "부가가치세법", "법인세법", "지방세법",
              "행정소송법", "행정절차법", "국가배상법", "국가공무원법", "지방공무원법"]
ALL_LAWS = list(set(ALL_LAWS + EXTRA_LAWS))
print(f"법률 수: {len(ALL_LAWS)}")

# 법률명 매칭 정규식 (긴 이름 우선)
law_name_re = re.compile(
    r'(' + '|'.join(re.escape(law) for law in sorted(ALL_LAWS, key=len, reverse=True)) + r')'
)
# 조문 추출 정규식
article_re = re.compile(r'제(\d+)조(?:의(\d+))?(?:\(([^)]+)\))?')

# ── 10종별 데이터 수집 구조 ────────────────────────────────
# type_key -> law_name -> Counter({article_key: freq})
type_law_articles = {t: defaultdict(Counter) for t in SSOT_TYPES}
# type_key -> law_name -> Counter({keyword: freq})
type_law_keywords = {t: defaultdict(Counter) for t in SSOT_TYPES}
# type_key -> law_name -> qa_count
type_law_qa = {t: Counter() for t in SSOT_TYPES}

stop_words = {
    "무엇", "어떻게", "무엇인가요", "내용은", "규정하고", "있나요", "대해",
    "다음과", "같이", "입니다", "합니다", "위하여", "경우에", "관한", "대하여",
    "의하여", "따라", "있는", "하는", "것을", "된다", "한다", "말한다", "경우",
    "이상", "이하", "어떤", "어떠한", "대한", "관하여", "통하여", "때문에",
    "무엇이", "해당하는", "것은", "것이", "있습니다", "없는", "또는", "및",
}


def classify_ssot_types(question: str, answer: str) -> list:
    """Q&A 텍스트를 SSOT 타입으로 분류. 복수 타입 가능."""
    text = question + " " + answer
    types = []
    for stype, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                types.append(stype)
                break
    # 모든 항목은 기본적으로 law 타입
    if "law" not in types:
        types.insert(0, "law")
    else:
        types.insert(0, "law")  # law가 항상 첫번째
        types = list(dict.fromkeys(types))  # 중복 제거, 순서 유지
    return types


def extract_keywords(question: str, law_name: str) -> list:
    """질문에서 의미있는 한글 키워드 추출."""
    words = re.findall(r'[가-힣]{2,8}', question)
    return [w for w in words if w not in stop_words and w != law_name and len(w) >= 2]


# ── 데이터 처리 ────────────────────────────────────────────
count = 0
with open(DATA_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        q = item.get("instruction", "") or item.get("question", "") or item.get("Q", "")
        a = item.get("output", "") or item.get("answer", "") or item.get("A", "")
        text = q + " " + a

        # 법률명 매칭
        found_laws = law_name_re.findall(q)
        if not found_laws:
            found_laws = law_name_re.findall(text[:300])
        if not found_laws:
            count += 1
            continue

        # SSOT 타입 분류
        stypes = classify_ssot_types(q, a)

        for law in set(found_laws):
            for stype in stypes:
                type_law_qa[stype][law] += 1

                # 조문 추출
                for m in article_re.finditer(text):
                    article_num = f"제{m.group(1)}조"
                    if m.group(2):
                        article_num += f"의{m.group(2)}"
                    title = m.group(3) or ""
                    key = f"{article_num}|{title}"
                    type_law_articles[stype][law][key] += 1

                # 키워드 추출
                for kw in extract_keywords(q, law):
                    type_law_keywords[stype][law][kw] += 1

        count += 1
        if count % 20000 == 0:
            print(f"  처리: {count:,}건...")

print(f"\n총 {count:,}건 처리 완료")

# ── SSOT 10종 캐시 구조 생성 ───────────────────────────────
cache = {}
for stype, meta in SSOT_TYPES.items():
    qa_counter = type_law_qa[stype]
    entries = {}

    for law in sorted(qa_counter.keys(), key=lambda x: -qa_counter[x]):
        # 상위 키워드 20개
        top_keywords = [kw for kw, _ in type_law_keywords[stype][law].most_common(20)]

        # 상위 조문 TOP 100
        key_articles = []
        for art_key, freq in type_law_articles[stype][law].most_common(TOP_N):
            parts = art_key.split("|", 1)
            article = parts[0]
            title = parts[1] if len(parts) > 1 and parts[1] else ""
            key_articles.append({
                "조문": article,
                "제목": title,
                "빈도": freq,
            })

        if top_keywords or key_articles:
            entries[law] = {
                "qa_count": qa_counter[law],
                "keywords": top_keywords,
                "key_articles": key_articles,
            }

    cache[stype] = {
        "label": meta["label"],
        "target": meta["target"],
        "endpoint": meta["endpoint"],
        "entry_count": len(entries),
        "entries": entries,
    }

# ── 저장 ───────────────────────────────────────────────────
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

raw_size = len(json.dumps(cache, ensure_ascii=False))
print(f"\n{'='*60}")
print(f"law_cache.json 생성 완료: {OUTPUT_PATH}")
print(f"파일 크기: {raw_size:,} bytes ({raw_size/1024:.1f} KB)")
print(f"{'='*60}")

# ── 10종별 통계 ────────────────────────────────────────────
print(f"\n{'SSOT 타입':<12} {'라벨':<16} {'법률 수':>8} {'총 QA':>10}")
print("-" * 50)
total_entries = 0
for stype, data in cache.items():
    ec = data["entry_count"]
    total_qa = sum(e["qa_count"] for e in data["entries"].values())
    total_entries += ec
    print(f"  {stype:<10} {data['label']:<14} {ec:>6}개 {total_qa:>10,}건")
print("-" * 50)
print(f"  {'합계':<24} {total_entries:>6}개")

# ── 상위 법률 출력 ─────────────────────────────────────────
print(f"\n상위 15개 법률 (law 타입, QA 빈도순):")
law_entries = cache.get("law", {}).get("entries", {})
sorted_laws = sorted(law_entries.items(), key=lambda x: -x[1]["qa_count"])
for i, (law, info) in enumerate(sorted_laws[:15], 1):
    arts = len(info["key_articles"])
    kws = ", ".join(info["keywords"][:3])
    print(f"  {i:2}. {law}: {info['qa_count']:,}건, 조문 {arts}개, 키워드: {kws}")
