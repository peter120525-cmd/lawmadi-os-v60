#!/usr/bin/env python3
"""
외국인 수요 높은 법령 영문 번역 추가 수집 → data/elaw_cache.json에 병합.

기존 elaw_cache.json(114개)에 없는 법령 중 외국인이 자주 필요로 하는 법령을 선별하여
DRF elaw API에서 영문 전문을 조회하고 캐시에 추가.

사용법:
    python scripts/fetch_elaw_extra.py
    python scripts/fetch_elaw_extra.py --dry-run   # API 호출 없이 목록만 확인
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "elaw_cache.json")
OC = "choepeter"
BASE_URL = "https://www.law.go.kr/DRF"

# ─── 외국인 수요 높은 추가 법령 목록 ──────────────────────────────
# 기존 114개에 없는 법령 중 외국인 거주·취업·투자·사업·비자·가족 관련
EXTRA_LAWS = [
    # 출입국·비자·체류
    "출입국관리법 시행령",
    "출입국관리법 시행규칙",
    "재외동포의 출입국과 법적 지위에 관한 법률",
    "재외동포의 출입국과 법적 지위에 관한 법률 시행령",
    "외국인근로자의 고용 등에 관한 법률",
    "외국인근로자의 고용 등에 관한 법률 시행령",
    "국적법 시행령",
    "국적법 시행규칙",
    "난민법 시행령",
    "여권법",
    "여권법 시행령",

    # 외국인 투자·사업
    "외국인투자 촉진법 시행령",
    "외국환거래법",
    "외국환거래법 시행령",
    "외국법자문사법",
    "자유무역지역의 지정 및 운영에 관한 법률",

    # 고용·노동 (외국인 근로 관련)
    "근로기준법 시행령",
    "최저임금법",
    "최저임금법 시행령",
    "고용보험법",
    "고용보험법 시행령",
    "파견근로자 보호 등에 관한 법률",
    "직업안정법",
    "남녀고용평등과 일·가정 양립 지원에 관한 법률",
    "산업안전보건법 시행령",
    "산업재해보상보험법 시행령",

    # 주거·부동산
    "주택임대차보호법 시행령",
    "공인중개사법 시행령",
    "부동산 거래신고 등에 관한 법률",
    "외국인토지법",

    # 세금
    "소득세법 시행령",
    "부가가치세법",
    "부가가치세법 시행령",
    "법인세법",
    "법인세법 시행령",
    "국세기본법 시행령",
    "조세특례제한법",
    "국제조세조정에 관한 법률",

    # 가족·혼인
    "가족관계의 등록 등에 관한 법률",
    "다문화가족지원법 시행령",
    "아동복지법",
    "입양특례법",

    # 운전·교통
    "도로교통법 시행령",
    "자동차관리법",
    "자동차손해배상 보장법",

    # 건강·보험
    "국민건강보험법 시행령",
    "의료법 시행규칙",
    "감염병의 예방 및 관리에 관한 법률",
    "약사법 시행령",

    # 교육
    "초·중등교육법",
    "고등교육법",
    "학원의 설립·운영 및 과외교습에 관한 법률",
    "재외국민의 교육지원 등에 관한 법률",

    # 사업·창업
    "상법 시행령",
    "벤처기업육성에 관한 특별조치법 시행령",
    "중소기업기본법 시행령",
    "중소기업 인력지원 특별법",
    "소상공인 보호 및 지원에 관한 법률",

    # 지식재산
    "특허법 시행령",
    "상표법 시행령",
    "저작권법 시행령",

    # 형사·인권
    "형사소송법 시행규칙",
    "범죄피해자 보호법",
    "가정폭력범죄의 처벌 등에 관한 특례법",
    "스토킹범죄의 처벌 등에 관한 법률",

    # 소비자·전자상거래
    "전자상거래 등에서의 소비자보호에 관한 법률",
    "할부거래에 관한 법률",
    "방문판매 등에 관한 법률",

    # 금융
    "은행법",
    "자본시장과 금융투자업에 관한 법률",

    # 기타 실용
    "주민등록법",
    "가축전염병 예방법",
    "동물보호법",
    "식품안전기본법",
    "공중위생관리법",
]


def search_elaw(law_name_kr: str) -> dict | None:
    params = urllib.parse.urlencode({
        "OC": OC, "target": "elaw", "type": "JSON",
        "display": "10", "query": law_name_kr,
    })
    url = f"{BASE_URL}/lawSearch.do?{params}"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "LawmadiOS/1.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  WARN: search failed for '{law_name_kr}': {e}")
        return None

    def strip_html(s):
        return re.sub(r'<[^>]+>', '', s).strip()

    law_search = data.get("LawSearch", {})
    laws = law_search.get("law", [])
    if isinstance(laws, dict):
        laws = [laws]

    for law in laws:
        kr_name = strip_html(law.get("법령명한글", ""))
        if kr_name == law_name_kr or (law_name_kr in kr_name and len(kr_name) - len(law_name_kr) <= 4):
            return {
                "mst": str(law.get("MST", law.get("법령일련번호", ""))),
                "name_en": law.get("법령명영문", ""),
                "name_kr": kr_name,
            }
    return None


def fetch_elaw_articles(mst: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "OC": OC, "target": "elaw", "MST": mst, "type": "JSON",
    })
    url = f"{BASE_URL}/lawService.do?{params}"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "LawmadiOS/1.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  WARN: article fetch failed for MST={mst}: {e}")
        return []

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
    if jo.get("joYn") == "N":
        return "", ""
    jo_no = str(jo.get("joNo", "")).strip()
    num_match = re.search(r'\d+', jo_no)
    if num_match:
        jo_no = str(int(num_match.group()))
    text = jo.get("joCts", "").strip()
    return jo_no, text


def main():
    dry_run = "--dry-run" in sys.argv

    # 기존 캐시 로드
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {}

    existing = set(cache.keys())
    # 이미 캐시에 있는 법령 제외
    todo = [law for law in EXTRA_LAWS if law not in existing]

    print(f"=== 외국인 수요 법령 영문 추가 수집 ===")
    print(f"기존 캐시: {len(existing)}개")
    print(f"추가 대상: {len(todo)}개 (중복 제외)")

    if dry_run:
        print("\n[dry-run] 추가 대상 목록:")
        for i, law in enumerate(todo, 1):
            print(f"  {i}. {law}")
        return

    added = 0
    skipped = []
    no_en = []

    for i, law_name in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] {law_name}")

        # 1. elaw 검색
        info = search_elaw(law_name)
        if not info or not info["mst"]:
            print(f"  SKIP: elaw 미등록")
            skipped.append(law_name)
            continue

        if not info["name_en"]:
            print(f"  SKIP: 영문 번역 없음 (MST={info['mst']})")
            no_en.append(law_name)
            continue

        print(f"  Found: {info['name_en']} (MST={info['mst']})")
        time.sleep(0.5)

        # 2. 전체 조문 조회
        jo_list = fetch_elaw_articles(info["mst"])
        if not jo_list:
            print(f"  SKIP: 조문 없음")
            skipped.append(law_name)
            continue

        # 3. 모든 조문 캐시 (주요 조문이 아닌 전체)
        articles_en = {}
        for jo in jo_list:
            jo_no, text = extract_article_text(jo)
            if jo_no and text:
                articles_en[jo_no] = text

        if not articles_en:
            print(f"  SKIP: 영문 조문 없음 ({len(jo_list)} items)")
            skipped.append(law_name)
            continue

        cache[law_name] = {
            "mst": info["mst"],
            "name_en": info["name_en"],
            "articles": articles_en,
        }
        added += 1
        print(f"  Cached: {len(articles_en)} articles")
        time.sleep(0.5)

    # 4. 저장
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n=== 완료 ===")
    print(f"추가: {added}개")
    print(f"elaw 미등록: {len(skipped)}개 → {skipped}")
    print(f"영문 번역 없음: {len(no_en)}개 → {no_en}")
    print(f"총 캐시: {len(cache)}개 법령")


if __name__ == "__main__":
    main()
