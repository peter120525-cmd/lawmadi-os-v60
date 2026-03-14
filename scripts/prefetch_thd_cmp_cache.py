#!/usr/bin/env python3
"""
리더별 전문분야 법률의 3단비교(위임조문) 캐시 생성.
법률 → 시행령 위임 관계 + 시행령/시행규칙 서식 정보를 함께 수집.

결과: data/thd_cmp_cache.json
"""
import json, os, sys, time, random, re, hashlib
import requests

DRF_KEY = "choepeter"
SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
RETRY = 3
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "thd_cmp_cache.json")


def fetch_retry(session, url, params, timeout=25):
    for attempt in range(RETRY):
        try:
            r = session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            if attempt < RETRY - 1:
                wait = (2 ** attempt) * 1.0 + random.uniform(0, 0.5)
                time.sleep(wait)
    return None


def fetch_thd_cmp(session, mst):
    """3단비교 위임조문 조회"""
    data = fetch_retry(session, SERVICE_URL, {
        "OC": DRF_KEY, "target": "thdCmp", "MST": mst, "knd": "2", "type": "JSON"
    })
    if not data:
        return []
    root = data.get("LspttnThdCmpLawXService", {}).get("위임조문삼단비교", {})
    items = root.get("법률조문", [])
    if isinstance(items, dict):
        items = [items]
    delegations = []
    for it in items:
        content = it.get("조내용", "")
        if any(kw in content for kw in ["대통령령", "시행령", "시행규칙", "총리령", "부령"]):
            delegations.append({
                "num": it.get("조번호", ""),
                "title": it.get("조제목", ""),
                "content": content[:600],
            })
    return delegations


def find_mst(session, name):
    data = fetch_retry(session, SEARCH_URL, {
        "OC": DRF_KEY, "target": "law", "type": "JSON", "query": name
    }, timeout=20)
    if not data:
        return None
    law_list = data.get("LawSearch", {}).get("law", [])
    if isinstance(law_list, dict):
        law_list = [law_list]
    for law in law_list:
        if law.get("법령명한글", "") == name:
            return law.get("법령일련번호")
    # fallback: 시작 일치 + 법률
    for law in law_list:
        n = law.get("법령명한글", "")
        if n.startswith(name) and law.get("법령구분명") in ("법률", "대통령령", "총리령"):
            return law.get("법령일련번호")
    return None


def fetch_decree_forms(session, law_name):
    """시행령/시행규칙 서식 조회"""
    result = {"decree": None, "rule": None}

    for suffix, key in [("시행령", "decree"), ("시행규칙", "rule")]:
        target_name = f"{law_name} {suffix}"
        mst = find_mst(session, target_name)
        if not mst:
            continue
        data = fetch_retry(session, SERVICE_URL, {
            "OC": DRF_KEY, "target": "law", "MST": mst, "type": "JSON"
        }, timeout=30)
        if not data:
            continue

        items = data.get("법령", {}).get("별표", {}).get("별표단위", [])
        if isinstance(items, dict):
            items = [items]

        forms = []
        tables = []
        for it in items:
            title = it.get("별표제목", "")
            if "삭제" in title:
                continue
            entry = {
                "title": title,
                "kind": it.get("별표구분", ""),
                "pdf_link": it.get("별표서식PDF파일링크", ""),
            }
            if entry["kind"] == "서식":
                forms.append(entry)
            else:
                tables.append(entry)

        if forms or tables:
            result[key] = {
                "name": target_name,
                "mst": mst,
                "forms": forms,
                "tables": tables,
            }
    return result


def main():
    # Load leader-law mapping
    mapping_path = os.path.join(os.path.dirname(__file__), "..", "data", "_leader_law_mst.json")
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    leader_laws = mapping["leader_laws"]
    mst_map = mapping["mst_map"]

    # Load existing cache
    cache = {}
    if os.path.exists(OUTPUT):
        with open(OUTPUT, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"기존 캐시 {len(cache)}개 로드\n")

    session = requests.Session()
    session.headers["User-Agent"] = "LawmadiOS/1.0"

    # Collect unique laws to process
    all_laws = sorted(mst_map.keys())
    todo = [l for l in all_laws if l not in cache]
    print(f"전체 법률: {len(all_laws)}개, 처리 대상: {len(todo)}개\n")

    success = 0
    for i, law_name in enumerate(todo):
        mst = mst_map[law_name]
        print(f"[{i+1}/{len(todo)}] {law_name} (MST={mst})", flush=True)

        entry = {"law_name": law_name, "mst": mst, "cached_at": time.time()}

        # 1) 3단비교 위임조문
        print(f"  3단비교 ...", end=" ", flush=True)
        delegations = fetch_thd_cmp(session, mst)
        entry["delegations"] = delegations
        print(f"{len(delegations)}건")
        time.sleep(0.3)

        # 2) 시행령/시행규칙 서식
        print(f"  시행령/시행규칙 서식 ...", end=" ", flush=True)
        df = fetch_decree_forms(session, law_name)
        if df["decree"]:
            d = df["decree"]
            entry["decree"] = d
            print(f"시행령(별표 {len(d['tables'])}, 서식 {len(d['forms'])})", end=" ")
        if df["rule"]:
            r = df["rule"]
            entry["rule"] = r
            print(f"시행규칙(별표 {len(r['tables'])}, 서식 {len(r['forms'])})", end=" ")
        if not df["decree"] and not df["rule"]:
            print("없음", end="")
        print()

        cache[law_name] = entry
        success += 1

        # 중간 저장 (10건마다)
        if success % 10 == 0:
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            print(f"  [중간저장 {success}건]")

        time.sleep(0.3)

    # 최종 저장
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    total_del = sum(len(v.get("delegations", [])) for v in cache.values())
    total_forms = sum(
        len(v.get("rule", {}).get("forms", [])) + len(v.get("decree", {}).get("forms", []))
        for v in cache.values()
    )
    total_tables = sum(
        len(v.get("rule", {}).get("tables", [])) + len(v.get("decree", {}).get("tables", []))
        for v in cache.values()
    )

    # Leader summary
    print(f"\n{'='*50}")
    print(f"완료: {len(cache)}개 법률")
    print(f"  위임조문(3단비교): {total_del}건")
    print(f"  서식: {total_forms}건")
    print(f"  별표: {total_tables}건")
    print(f"  파일: {OUTPUT} ({size_mb:.1f}MB)")

    # Leader별 요약
    print(f"\n리더별 커버리지:")
    for lid in sorted(leader_laws.keys(), key=lambda x: int(x[1:])):
        laws = leader_laws[lid]
        cached = [l for l in laws if l in cache]
        dels = sum(len(cache[l].get("delegations", [])) for l in cached)
        forms = sum(
            len(cache[l].get("rule", {}).get("forms", [])) +
            len(cache[l].get("decree", {}).get("forms", []))
            for l in cached
        )
        if dels > 0 or forms > 0:
            print(f"  {lid}: 법률 {len(cached)}/{len(laws)}, 위임 {dels}건, 서식 {forms}건")


if __name__ == "__main__":
    main()
