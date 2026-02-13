#!/usr/bin/env python3
"""헌재결정례 확인 - 판례 내에서 필터링"""
import requests
import json

OC = "choepeter"

print("=" * 70)
print("🧪 헌법재판소 결정례 검색")
print("=" * 70)

# 헌재 관련 키워드로 판례 검색
keywords = ["위헌", "헌법재판소", "기본권침해", "위헌법률심판"]

for keyword in keywords:
    print(f"\n{'='*70}")
    print(f"🔍 키워드: '{keyword}'")
    print(f"{'='*70}")

    url = "http://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": OC,
        "target": "prec",
        "type": "JSON",
        "query": keyword,
        "display": 5
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200 and 'json' in response.headers.get('Content-Type', ''):
            data = response.json()
            prec_search = data.get("PrecSearch", {})
            total = prec_search.get("totalCnt", "0")
            precs = prec_search.get("prec", [])

            print(f"총 {total}건 발견")

            if precs:
                print(f"\n📚 상위 결과:")
                constitutional_count = 0

                for i, prec in enumerate(precs, 1):
                    case_name = prec.get("판례명", "N/A")
                    court = prec.get("법원명", "N/A")
                    case_num = prec.get("사건번호", "N/A")
                    date = prec.get("선고일자", "N/A")

                    # 헌법재판소 판례인지 확인
                    is_constitutional = "헌법" in court or "헌재" in court or "헌법" in case_name

                    marker = "⭐" if is_constitutional else "  "
                    print(f"\n{marker}[{i}] {case_name[:80]}")
                    print(f"   법원: {court}")
                    print(f"   사건번호: {case_num}")
                    print(f"   선고일: {date}")

                    if is_constitutional:
                        constitutional_count += 1

                if constitutional_count > 0:
                    print(f"\n✅ 헌법재판소 결정례: {constitutional_count}건")
            else:
                print("검색 결과 없음")

    except Exception as e:
        print(f"❌ 오류: {e}")

print("\n" + "=" * 70)
print("💡 결론:")
print("=" * 70)
print("헌법재판소 결정례는 target=prec (판례)에 포함되어 있습니다.")
print("법원명이나 판례명에 '헌법재판소' 또는 '헌재'가 포함된 항목을 필터링하여 사용하세요.")
print("=" * 70)
