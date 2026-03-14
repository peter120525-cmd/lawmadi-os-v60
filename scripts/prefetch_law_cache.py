#!/usr/bin/env python3
"""
LAW_BOOST에 등장하는 모든 법률의 DRF lawService 응답을 사전 캐시.
결과를 data/law_service_cache.json에 저장 → GCS 업로드용.

Usage:
    python scripts/prefetch_law_cache.py
    gsutil cp data/law_service_cache.json gs://lawmadi-media/cache/law_service_cache.json
"""
import json, os, re, sys, time, hashlib, random
import requests

DRF_KEY = "choepeter"
SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
TIMEOUT = 30  # law.go.kr 대용량 법률용 넉넉한 타임아웃
RETRY = 3
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "law_service_cache.json")

def extract_laws_from_pipeline():
    """pipeline.py의 LAW_BOOST에서 법률명 추출"""
    pipeline_path = os.path.join(os.path.dirname(__file__), "..", "core", "pipeline.py")
    with open(pipeline_path, "r", encoding="utf-8") as f:
        content = f.read()
    laws = set()
    for m in re.finditer(r'[•]\s*([\w\s가-힣]+?)\s+제\d+', content):
        law_name = m.group(1).strip()
        if law_name and len(law_name) >= 2:
            laws.add(law_name)
    return sorted(laws)


def search_mst(session, law_name):
    """lawSearch.do로 법령일련번호(MST) 조회"""
    params = {"OC": DRF_KEY, "target": "law", "type": "JSON", "query": law_name}
    data = None
    for attempt in range(RETRY):
        try:
            r = session.get(SEARCH_URL, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json()
                break
        except Exception as e:
            if attempt < RETRY - 1:
                wait = (2 ** attempt) * 1.0 + random.uniform(0, 0.5)
                print(f"  search 재시도 {attempt+1}/{RETRY}: {e}")
                time.sleep(wait)
    if not data:
        return None
    law_list = data.get("LawSearch", {}).get("law", [])
    if isinstance(law_list, dict):
        law_list = [law_list]
    # 정확 일치
    for law in law_list:
        if law.get("법령명한글", "") == law_name:
            return law.get("법령일련번호")
    # 시작 일치 + 법률
    for law in law_list:
        name = law.get("법령명한글", "")
        if name.startswith(law_name) and law.get("법령구분명") == "법률":
            return law.get("법령일련번호")
    # 포함 일치
    for law in law_list:
        name = law.get("법령명한글", "")
        if law_name in name and law.get("법령구분명") == "법률":
            return law.get("법령일련번호")
    return None


def fetch_law_service(session, mst):
    """lawService.do로 조문 상세 조회 (재시도 포함)"""
    params = {"OC": DRF_KEY, "target": "law", "MST": mst, "type": "JSON"}
    for attempt in range(RETRY):
        try:
            r = session.get(SERVICE_URL, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            if attempt < RETRY - 1:
                wait = (2 ** attempt) * 1.0 + random.uniform(0, 0.5)
                print(f"    재시도 {attempt+1}/{RETRY}: {e}")
                time.sleep(wait)
    return None


def count_articles(data):
    """조문 수 카운트"""
    try:
        arts = data.get("법령", {}).get("조문", {}).get("조문단위", [])
        if isinstance(arts, list):
            return len(arts)
    except Exception:
        pass
    return 0


def main():
    laws = extract_laws_from_pipeline()
    print(f"LAW_BOOST 법률 {len(laws)}개 발견\n")

    # 기존 캐시 로드
    cache = {}
    if os.path.exists(OUTPUT):
        with open(OUTPUT, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"기존 캐시 {len(cache)}개 로드\n")

    session = requests.Session()
    session.headers["User-Agent"] = "LawmadiOS/1.0"

    success = 0
    fail = 0
    skip = 0

    for i, law_name in enumerate(laws):
        key = hashlib.md5(law_name.encode("utf-8")).hexdigest()

        # 이미 캐시에 있고 조문 수가 3건 이상이면 스킵
        if key in cache:
            existing = cache[key]
            arts = count_articles(existing.get("data", {}))
            if arts >= 3:
                skip += 1
                continue

        print(f"[{i+1}/{len(laws)}] {law_name} ...", end=" ", flush=True)

        # Step 1: MST 조회
        mst = search_mst(session, law_name)
        if not mst:
            print(f"MST 미발견 ✗")
            fail += 1
            continue

        # Step 2: lawService 조회
        data = fetch_law_service(session, mst)
        if not data:
            print(f"MST={mst} fetch 실패 ✗")
            fail += 1
            continue

        arts = count_articles(data)
        cache[key] = {
            "law_name": law_name,
            "mst": mst,
            "data": data,
            "article_count": arts,
            "cached_at": time.time(),
        }
        success += 1
        print(f"MST={mst}, {arts}건 ✓")

        # rate limit 방지
        time.sleep(0.3)

        # 매 10건 중간 저장
        if success % 10 == 0:
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)

    # 최종 저장
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    total_arts = sum(count_articles(v.get("data", {})) for v in cache.values())
    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024

    print(f"\n{'='*50}")
    print(f"완료: 성공 {success}, 실패 {fail}, 스킵 {skip}")
    print(f"캐시: {len(cache)}개 법률, {total_arts}건 조문")
    print(f"파일: {OUTPUT} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
