#!/usr/bin/env python3
"""
build_law_cache_v2.py — law_cache.json 확장 스크립트
all_qa_dataset_v40.jsonl (85,909건)에서:
  a) 키워드 확장 (동의어/약칭 추가)
  b) 핵심조문 원문 TOP3 (key_article_texts)
  c) 판례요지 30건 (key_precedents)
  d) 대표 Q&A TOP3 (key_qa)
"""

import json
import re
import os
from collections import Counter, defaultdict
from typing import Dict, List, Any

# ── 경로 설정 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(SCRIPT_DIR, "law_cache.json")
DATASET_PATH = os.path.expanduser("~/LawmadiLM/data/processed/all_qa_dataset_v40.jsonl")

# ── 약칭 → 정식명 매핑 (동의어 확장용) ──
ABBREVIATION_MAP = {
    "근기법": "근로기준법",
    "주임법": "주택임대차보호법",
    "상임법": "상가건물임대차보호법",
    "민소법": "민사소송법",
    "형소법": "형사소송법",
    "민집법": "민사집행법",
    "산안법": "산업안전보건법",
    "산재법": "산업재해보상보험법",
    "남녀고용법": "남녀고용평등과 일·가정 양립 지원에 관한 법률",
    "파견법": "파견근로자보호 등에 관한 법률",
    "최저임금법": "최저임금법",
    "노조법": "노동조합 및 노동관계조정법",
    "개인정보법": "개인정보 보호법",
    "정보통신망법": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    "전세": "주택임대차보호법",
    "월세": "주택임대차보호법",
    "보증금": "주택임대차보호법",
    "퇴직금": "근로기준법",
    "해고": "근로기준법",
    "임금체불": "근로기준법",
    "상속포기": "민법",
    "이혼": "민법",
    "위자료": "민법",
    "양육권": "민법",
    "사기": "형법",
    "폭행": "형법",
    "명예훼손": "형법",
    "모욕": "형법",
    "횡령": "형법",
    "배임": "형법",
    "강제집행": "민사집행법",
    "가압류": "민사집행법",
    "소액사건": "소액사건심판법",
    "지급명령": "민사소송법",
    "내용증명": "민법",
    "손해배상": "민법",
    "채권추심": "채권의 공정한 추심에 관한 법률",
    "개인회생": "채무자 회생 및 파산에 관한 법률",
    "파산": "채무자 회생 및 파산에 관한 법률",
}


def load_existing_cache() -> Dict[str, Any]:
    """기존 law_cache.json 로드"""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_dataset() -> List[Dict]:
    """all_qa_dataset_v40.jsonl 전체 파싱"""
    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"  Dataset loaded: {len(records)} records")
    return records


def extract_law_name_from_text(text: str) -> List[str]:
    """텍스트에서 'OO법' 패턴 추출"""
    return re.findall(r'[가-힣]+법', text)


def expand_keywords(cache: Dict, records: List[Dict]) -> Dict:
    """a) 키워드 확장: 데이터셋 instruction에서 법률별 키워드 추출 + 약칭 추가"""
    # 법률명 → instruction 키워드 수집
    law_keywords: Dict[str, Counter] = defaultdict(Counter)

    for rec in records:
        instruction = rec.get("instruction", "")
        output = rec.get("output", "")
        combined = instruction + " " + output

        # 법률명 추출
        law_names = extract_law_name_from_text(combined)
        tokens = re.findall(r'[가-힣]{2,6}', instruction)

        for law_name in law_names:
            for token in tokens:
                if token != law_name and len(token) >= 2:
                    law_keywords[law_name][token] += 1

    # 기존 캐시에 키워드 추가
    for stype, type_data in cache.items():
        entries = type_data.get("entries", {})
        for law_name, law_info in entries.items():
            existing_kws = set(law_info.get("keywords", []))

            # 데이터셋에서 추출한 키워드 상위 30개 추가
            new_kws = law_keywords.get(law_name, Counter())
            top_new = [kw for kw, _ in new_kws.most_common(30) if kw not in existing_kws]
            law_info["keywords"] = list(existing_kws) + top_new[:20]

    # 약칭 키워드도 인덱스에 추가
    for stype, type_data in cache.items():
        entries = type_data.get("entries", {})
        for abbr, full_name in ABBREVIATION_MAP.items():
            if full_name in entries:
                kws = entries[full_name].get("keywords", [])
                if abbr not in kws:
                    kws.append(abbr)
                entries[full_name]["keywords"] = kws

    return cache


def add_key_article_texts(cache: Dict, records: List[Dict]) -> Dict:
    """b) 핵심조문 원문 TOP3: output에서 조문 원문 추출"""
    # 법률명 → 조문 원문 수집
    law_articles: Dict[str, Counter] = defaultdict(Counter)

    for rec in records:
        output = rec.get("output", "")
        # 패턴: "제N조(제목) 본문..." 또는 "제N조 본문..."
        matches = re.findall(
            r'(제\d+조(?:의\d+)?(?:\([^)]+\))?\s*.{10,200}?)(?:\n|$)',
            output
        )
        # 어떤 법률의 조문인지 추출
        law_names = extract_law_name_from_text(output)
        primary_law = law_names[0] if law_names else None

        if primary_law and matches:
            for m in matches[:3]:
                article_text = m.strip()
                if len(article_text) > 15:
                    law_articles[primary_law][article_text] += 1

    # 캐시에 key_article_texts 추가
    for stype, type_data in cache.items():
        entries = type_data.get("entries", {})
        for law_name, law_info in entries.items():
            texts = law_articles.get(law_name, Counter())
            top3 = [text for text, _ in texts.most_common(3)]
            if top3:
                law_info["key_article_texts"] = top3

    return cache


def add_key_precedents(cache: Dict, records: List[Dict]) -> Dict:
    """c) 판례요지 30건: 판례 관련 Q&A에서 추출"""
    # 판례 패턴 추출
    precedent_pattern = re.compile(
        r'((?:대법원|헌법재판소|서울고등법원|서울중앙지방법원)[\s]*'
        r'\d{4}[\s.]*\d{1,2}[\s.]*\d{1,2}[\s.]*'
        r'(?:선고|결정)?[\s]*\d{2,4}[가-힣]+\d+[\s]*(?:판결|결정|전원합의체)?)'
    )
    # 법률명 → 판례요지 수집
    law_precedents: Dict[str, list] = defaultdict(list)

    for rec in records:
        output = rec.get("output", "")
        prec_matches = precedent_pattern.findall(output)

        if prec_matches:
            law_names = extract_law_name_from_text(output)
            primary_law = law_names[0] if law_names else None
            if primary_law:
                for pm in prec_matches:
                    pm = pm.strip()
                    if pm and pm not in law_precedents[primary_law]:
                        law_precedents[primary_law].append(pm)

    # 캐시에 key_precedents 추가 (최대 30건)
    for stype, type_data in cache.items():
        entries = type_data.get("entries", {})
        for law_name, law_info in entries.items():
            precs = law_precedents.get(law_name, [])
            if precs:
                law_info["key_precedents"] = precs[:30]

    return cache


def add_key_qa(cache: Dict, records: List[Dict]) -> Dict:
    """d) 대표 Q&A TOP3: 법률별 빈도 기준 대표 3건"""
    # 법률명 → Q&A 수집
    law_qa: Dict[str, list] = defaultdict(list)

    for rec in records:
        instruction = rec.get("instruction", "")
        output = rec.get("output", "")
        law_names = extract_law_name_from_text(instruction + " " + output)
        primary_law = law_names[0] if law_names else None

        if primary_law and len(instruction) > 10 and len(output) > 20:
            law_qa[primary_law].append({
                "q": instruction[:150],
                "a": output[:200],
            })

    # 캐시에 key_qa 추가 (각 법률 TOP3)
    for stype, type_data in cache.items():
        entries = type_data.get("entries", {})
        for law_name, law_info in entries.items():
            qas = law_qa.get(law_name, [])
            if qas:
                # 다양성을 위해 간격을 두고 선택
                step = max(1, len(qas) // 3)
                selected = []
                for i in range(0, len(qas), step):
                    if len(selected) >= 3:
                        break
                    selected.append(qas[i])
                law_info["key_qa"] = selected

    return cache


def count_stats(cache: Dict) -> Dict[str, int]:
    """통계 계산"""
    total_entries = 0
    total_keywords = 0
    total_articles = 0
    total_precedents = 0
    total_qa = 0

    for stype, type_data in cache.items():
        entries = type_data.get("entries", {})
        total_entries += len(entries)
        for law_name, law_info in entries.items():
            total_keywords += len(law_info.get("keywords", []))
            total_articles += len(law_info.get("key_article_texts", []))
            total_precedents += len(law_info.get("key_precedents", []))
            total_qa += len(law_info.get("key_qa", []))

    return {
        "entries": total_entries,
        "keywords": total_keywords,
        "key_article_texts": total_articles,
        "key_precedents": total_precedents,
        "key_qa": total_qa,
    }


def main():
    print("=" * 60)
    print("law_cache.json v2 확장 빌드")
    print("=" * 60)

    # 1. 기존 캐시 로드
    print("\n[1/5] 기존 law_cache.json 로드...")
    cache = load_existing_cache()
    before_stats = count_stats(cache)
    print(f"  Before: {before_stats}")

    # 2. 데이터셋 로드
    print("\n[2/5] all_qa_dataset_v40.jsonl 파싱...")
    records = parse_dataset()

    # 3. 키워드 확장
    print("\n[3/5] 키워드 확장 (동의어/약칭 추가)...")
    cache = expand_keywords(cache, records)

    # 4. 핵심조문 원문 추가
    print("\n[4/5] 핵심조문 원문 + 판례요지 + 대표 Q&A 추가...")
    cache = add_key_article_texts(cache, records)
    cache = add_key_precedents(cache, records)
    cache = add_key_qa(cache, records)

    # 5. 저장
    print("\n[5/5] law_cache.json 저장...")
    after_stats = count_stats(cache)
    print(f"  After: {after_stats}")

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(CACHE_PATH) / (1024 * 1024)
    print(f"\n  Saved: {CACHE_PATH} ({file_size:.1f} MB)")
    print(f"  Keywords: {before_stats['keywords']} → {after_stats['keywords']}")
    print(f"  Article texts: {before_stats['key_article_texts']} → {after_stats['key_article_texts']}")
    print(f"  Precedents: {before_stats['key_precedents']} → {after_stats['key_precedents']}")
    print(f"  Q&A: {before_stats['key_qa']} → {after_stats['key_qa']}")
    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
