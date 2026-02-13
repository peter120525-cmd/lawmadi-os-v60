#!/usr/bin/env python3
"""law.go.kr DRF API - 헌재결정례 검색 테스트"""
import requests
import json

OC = "choepeter"

print("=" * 70)
print("🧪 law.go.kr DRF API - 헌재결정례 검색 테스트")
print("=" * 70)
print(f"인증키(OC): {OC}\n")

# 다양한 target 시도
test_cases = [
    {
        "name": "헌재결정례 검색 - target=prec (판례와 동일)",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "prec",
            "type": "JSON",
            "query": "헌법재판소",
            "display": 5
        }
    },
    {
        "name": "헌재결정례 검색 - target=expc (추정)",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "expc",
            "type": "JSON",
            "query": "위헌",
            "display": 5
        }
    },
    {
        "name": "헌재결정례 검색 - target=conc (추정)",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "conc",
            "type": "JSON",
            "query": "기본권",
            "display": 5
        }
    },
    {
        "name": "판례 검색 - '헌법재판소' 키워드",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "prec",
            "type": "JSON",
            "query": "헌법재판소",
            "display": 5
        }
    }
]

success_count = 0
working_targets = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*70}")
    print(f"[테스트 {i}/{len(test_cases)}] {test['name']}")
    print(f"{'='*70}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')

        print(f"Status: {status} | Content-Type: {content_type}")

        if status == 200 and 'json' in content_type.lower():
            data = response.json()
            print(f"✅ JSON 응답")

            # 다양한 키 확인
            for key in data.keys():
                print(f"\n📄 응답 키: {key}")

                if isinstance(data[key], dict):
                    inner_data = data[key]
                    total = inner_data.get("totalCnt", inner_data.get("total", "0"))
                    items_key = None

                    # 항목 키 찾기
                    for possible_key in ["prec", "expc", "conc", "law", "items"]:
                        if possible_key in inner_data:
                            items_key = possible_key
                            break

                    if items_key:
                        items = inner_data[items_key]
                        print(f"   - 총 {total}건")
                        print(f"   - 항목 키: {items_key}")

                        if items and isinstance(items, list) and len(items) > 0:
                            print(f"\n✅ 검색 성공! ({len(items)}개 반환)")
                            print(f"\n📚 결과 미리보기:")

                            for j, item in enumerate(items[:2], 1):
                                print(f"\n   [{j}]")
                                for k, v in list(item.items())[:5]:
                                    val_str = str(v)[:100]
                                    print(f"      {k}: {val_str}")

                            success_count += 1
                            working_targets.append({
                                "target": test['params']['target'],
                                "query": test['params']['query'],
                                "total": total,
                                "items_key": items_key
                            })
                            break
                    else:
                        print(f"   - Total: {total}")
                        print(f"   - 구조: {list(inner_data.keys())}")
                else:
                    print(f"   Value: {str(data[key])[:200]}")

        elif 'html' in content_type.lower():
            print(f"❌ HTML 에러 페이지")
            if '미신청' in response.text:
                print(f"   → 해당 타겟({test['params']['target']}) 미신청")

        else:
            print(f"❌ HTTP {status}")

    except Exception as e:
        print(f"❌ 예외: {type(e).__name__}: {e}")

# 최종 결과
print("\n" + "=" * 70)
print("📊 최종 결과")
print("=" * 70)
print(f"성공: {success_count}/{len(test_cases)}")

if working_targets:
    print("\n✅ 작동하는 타겟:")
    for wt in working_targets:
        print(f"   - target={wt['target']}, query={wt['query']}")
        print(f"     → {wt['total']}건, items_key={wt['items_key']}")

print("\n💡 헌재결정례 검색 방법:")
print("   1. target=prec로 '헌법재판소' 키워드 검색")
print("   2. 또는 별도 target이 존재할 수 있음 (확인 필요)")
print("   3. open.law.go.kr API 문서 참조")

print("=" * 70)
