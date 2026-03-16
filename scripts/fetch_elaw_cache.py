#!/usr/bin/env python3
"""
DRF elaw API에서 LAW_BOOST 법령의 영문 번역을 조회하여 data/elaw_cache.json을 생성.

사용법:
    python scripts/fetch_elaw_cache.py

DRF elaw API:
    - 검색: lawSearch.do?OC=choepeter&target=elaw&type=JSON&query={법령명}
    - 본문: lawService.do?OC=choepeter&target=elaw&MST={mst}&type=JSON
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# pipeline.py에서 _LEADER_LAW_BOOST 파싱
PIPELINE_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "pipeline.py")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "elaw_cache.json")

OC = "choepeter"
BASE_URL = "https://www.law.go.kr/DRF"
SEARCH_URL = f"{BASE_URL}/lawSearch.do"
SERVICE_URL = f"{BASE_URL}/lawService.do"

# 법령명 → 조문번호 리스트 추출
LAW_ARTICLE_RE = re.compile(
    r'([가-힣][가-힣\s·\-]*(?:법|시행령|규칙|협약|특별법|특례법|기본법|촉진법))\s*제(\d+)조'
)


def parse_law_articles_from_pipeline():
    """pipeline.py의 _LEADER_LAW_BOOST에서 법령명→조문번호 매핑 추출."""
    with open(PIPELINE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # _LEADER_LAW_BOOST = { ... } 블록 추출
    start = content.find("_LEADER_LAW_BOOST = {")
    if start == -1:
        print("ERROR: _LEADER_LAW_BOOST not found in pipeline.py")
        sys.exit(1)

    # 법령명 → set of article numbers
    law_articles: dict[str, set[str]] = {}
    for match in LAW_ARTICLE_RE.finditer(content[start:]):
        law_name = match.group(1).strip()
        art_num = match.group(2)
        law_articles.setdefault(law_name, set()).add(art_num)

    return law_articles


def search_elaw(law_name_kr: str) -> dict | None:
    """elaw API로 영문 법령 검색 → MST + 영문명 반환."""
    params = urllib.parse.urlencode({
        "OC": OC,
        "target": "elaw",
        "type": "JSON",
        "display": "10",
        "query": law_name_kr,
    })
    url = f"{SEARCH_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  WARN: search failed for '{law_name_kr}': {e}")
        return None

    # 응답 구조: {"LawSearch": {"law": [...]}} or {"LawSearch": {"law": {...}}}
    law_search = data.get("LawSearch", {})
    laws = law_search.get("law", [])
    if isinstance(laws, dict):
        laws = [laws]
    if not laws:
        return None

    # HTML 태그 제거 후 정확 매칭
    def strip_html(s):
        return re.sub(r'<[^>]+>', '', s).strip()

    def _make_result(law, kr_name):
        return {
            "mst": str(law.get("MST", law.get("법령일련번호", ""))),
            "name_en": strip_html(law.get("법령명영문", "")),
            "name_kr": kr_name,
        }

    # 1차: 정확 매칭 (현행 우선)
    for law in laws:
        kr_name = strip_html(law.get("법령명한글", ""))
        if kr_name == law_name_kr:
            return _make_result(law, kr_name)

    # 2차: 부분 매칭 (법령명 포함, 길이 차이 4자 이내)
    for law in laws:
        kr_name = strip_html(law.get("법령명한글", ""))
        if law_name_kr in kr_name and len(kr_name) - len(law_name_kr) <= 4:
            return _make_result(law, kr_name)

    return None


def fetch_elaw_articles(mst: str) -> list[dict]:
    """elaw API로 영문 조문 전체 조회."""
    params = urllib.parse.urlencode({
        "OC": OC,
        "target": "elaw",
        "MST": mst,
        "type": "JSON",
    })
    url = f"{SERVICE_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  WARN: article fetch failed for MST={mst}: {e}")
        return []

    # elaw API 응답: {"Law": {"JoSection": {"Jo": [...]}}}
    law_data = data.get("Law", data)
    jo_section = law_data.get("JoSection", {})
    if isinstance(jo_section, dict):
        jo_list = jo_section.get("Jo", [])
    elif isinstance(jo_section, list):
        jo_list = jo_section
    else:
        jo_list = []

    if isinstance(jo_list, dict):
        jo_list = [jo_list]

    return jo_list


def extract_article_text(jo: dict) -> tuple[str, str]:
    """조문 dict에서 (조문번호, 조문텍스트) 추출."""
    # elaw: joNo="0015" → "15", joYn="Y" means actual article
    if jo.get("joYn") == "N":
        return "", ""  # chapter/section header, skip

    jo_no = str(jo.get("joNo", "")).strip()
    # 조문번호에서 숫자만 추출 (leading zeros 제거)
    num_match = re.search(r'\d+', jo_no)
    if num_match:
        jo_no = str(int(num_match.group()))  # "0015" → "15"

    # elaw: joCts = full article text, joTtl = title
    text = jo.get("joCts", "").strip()

    return jo_no, text


def main():
    print("=== DRF elaw Cache Builder ===")
    law_articles = parse_law_articles_from_pipeline()
    print(f"Found {len(law_articles)} unique laws in LAW_BOOST")

    cache: dict[str, dict] = {}
    skipped = []
    fetched = 0

    for law_name, needed_articles in sorted(law_articles.items()):
        print(f"\n[{law_name}] needed articles: {sorted(needed_articles, key=int)}")

        # 1. 검색
        info = search_elaw(law_name)
        if not info or not info["mst"]:
            print(f"  SKIP: not found in elaw")
            skipped.append(law_name)
            continue

        if not info["name_en"]:
            print(f"  SKIP: no English translation (MST={info['mst']})")
            skipped.append(law_name)
            continue

        print(f"  Found: {info['name_en']} (MST={info['mst']})")

        # 2. 조문 조회
        time.sleep(0.5)  # rate limiting
        jo_list = fetch_elaw_articles(info["mst"])
        if not jo_list:
            print(f"  SKIP: no articles returned")
            skipped.append(law_name)
            continue

        # 3. 필요한 조문만 추출
        articles_en: dict[str, str] = {}
        for jo in jo_list:
            jo_no, text = extract_article_text(jo)
            if jo_no in needed_articles and text:
                articles_en[jo_no] = text

        if not articles_en:
            print(f"  SKIP: no matching articles found in {len(jo_list)} items")
            skipped.append(law_name)
            continue

        cache[law_name] = {
            "mst": info["mst"],
            "name_en": info["name_en"],
            "articles": articles_en,
        }
        fetched += 1
        found = sorted(articles_en.keys(), key=int)
        missing = sorted(needed_articles - set(articles_en.keys()), key=int)
        print(f"  Cached {len(articles_en)} articles: {found}")
        if missing:
            print(f"  Missing: {missing}")

        time.sleep(0.5)  # rate limiting

    # 4. 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n=== Done ===")
    print(f"Cached: {fetched} laws")
    print(f"Skipped: {len(skipped)} laws")
    if skipped:
        print(f"Skipped laws: {skipped}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
