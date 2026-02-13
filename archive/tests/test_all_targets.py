#!/usr/bin/env python3
"""law.go.kr DRF API - 모든 target 타입 테스트"""
import requests
import json

OC = "choepeter"

print("=" * 70)
print("🧪 law.go.kr DRF API - 전체 타겟 테스트")
print("=" * 70)

# 가능한 모든 target
targets = [
    ("law", "법령", "민법"),
    ("prec", "판례", "임대차"),
    ("expc", "법령해석례", "행정절차법"),
    ("admrul", "행정규칙", "공무원"),
    ("anar", "자치법규", "조례"),
    ("jooyak", "조약", "협정"),
]

results = []

for target, description, query in targets:
    print(f"\n{'='*70}")
    print(f"📌 {description} (target={target})")
    print(f"   검색어: '{query}'")
    print(f"{'='*70}")

    url = "http://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": OC,
        "target": target,
        "type": "JSON",
        "query": query,
        "display": 3
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')
        size = len(response.text)

        print(f"Status: {status} | Size: {size} bytes")

        if status == 200:
            if 'json' in content_type.lower():
                data = response.json()

                # 첫 번째 키 확인
                if data:
                    first_key = list(data.keys())[0]
                    first_value = data[first_key]

                    if isinstance(first_value, dict):
                        total = first_value.get("totalCnt", "0")
                        result_code = first_value.get("resultCode", "N/A")
                        result_msg = first_value.get("resultMsg", "N/A")

                        print(f"✅ 응답 성공")
                        print(f"   - 응답 키: {first_key}")
                        print(f"   - 총 건수: {total}")
                        print(f"   - ResultCode: {result_code}")
                        print(f"   - ResultMsg: {result_msg}")

                        # 항목 키 찾기
                        items_key = None
                        for key in first_value.keys():
                            if isinstance(first_value[key], list):
                                items_key = key
                                break

                        if items_key and first_value[items_key]:
                            items = first_value[items_key]
                            print(f"   - 항목 수: {len(items)}개")

                            if items:
                                print(f"\n   📄 첫 번째 항목:")
                                first_item = items[0]
                                for k, v in list(first_item.items())[:5]:
                                    print(f"      {k}: {str(v)[:80]}")

                            results.append({
                                "target": target,
                                "description": description,
                                "status": "success",
                                "total": total,
                                "response_key": first_key,
                                "items_key": items_key
                            })
                        else:
                            results.append({
                                "target": target,
                                "description": description,
                                "status": "no_items",
                                "total": total
                            })
                    else:
                        print(f"   응답: {str(first_value)[:200]}")
                        results.append({
                            "target": target,
                            "description": description,
                            "status": "unexpected_format"
                        })
                else:
                    print(f"   빈 응답")
                    results.append({
                        "target": target,
                        "description": description,
                        "status": "empty"
                    })

            elif 'html' in content_type.lower():
                print(f"❌ HTML 에러 페이지")
                if '미신청' in response.text:
                    print(f"   → '{description}' 미신청")
                    results.append({
                        "target": target,
                        "description": description,
                        "status": "not_subscribed"
                    })
                else:
                    results.append({
                        "target": target,
                        "description": description,
                        "status": "html_error"
                    })
            else:
                print(f"⚠️  알 수 없는 Content-Type: {content_type}")
                results.append({
                    "target": target,
                    "description": description,
                    "status": "unknown_type"
                })
        else:
            print(f"❌ HTTP {status}")
            results.append({
                "target": target,
                "description": description,
                "status": f"http_{status}"
            })

    except Exception as e:
        print(f"❌ 예외: {type(e).__name__}: {e}")
        results.append({
            "target": target,
            "description": description,
            "status": "exception",
            "error": str(e)
        })

# 최종 요약
print("\n" + "=" * 70)
print("📊 전체 타겟 테스트 결과")
print("=" * 70)

print("\n✅ 작동하는 타겟:")
for r in results:
    if r.get('status') == 'success':
        print(f"   ✓ {r['target']:10s} - {r['description']:15s} - {r['total']}건")

print("\n⚠️  미신청 타겟:")
for r in results:
    if r.get('status') == 'not_subscribed':
        print(f"   ✗ {r['target']:10s} - {r['description']:15s}")

print("\n❌ 작동 안 함:")
for r in results:
    if r.get('status') not in ['success', 'not_subscribed']:
        print(f"   ✗ {r['target']:10s} - {r['description']:15s} - {r['status']}")

print("\n" + "=" * 70)

# 결과 저장
with open('all_targets_test.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("💾 결과 저장: all_targets_test.json")
