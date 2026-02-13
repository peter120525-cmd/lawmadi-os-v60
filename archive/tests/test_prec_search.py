#!/usr/bin/env python3
"""law.go.kr DRF API - 판례 및 헌재결정례 검색 테스트"""
import requests
import json

OC = "choepeter"

print("=" * 70)
print("🧪 law.go.kr DRF API - 판례/헌재결정례 검색 테스트")
print("=" * 70)
print(f"인증키(OC): {OC}\n")

# 테스트 케이스
test_cases = [
    {
        "name": "판례 검색 - 임대차",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "prec",  # 판례
            "type": "JSON",
            "query": "임대차",
            "display": 5
        }
    },
    {
        "name": "판례 검색 - 손해배상",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "prec",
            "type": "JSON",
            "query": "손해배상",
            "display": 5
        }
    },
    {
        "name": "판례 검색 - 명의신탁",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "prec",
            "type": "JSON",
            "query": "명의신탁",
            "display": 3
        }
    },
    {
        "name": "대법원 판례 상세 조회",
        "url": "http://www.law.go.kr/DRF/lawService.do",
        "params": {
            "OC": OC,
            "target": "prec",
            "type": "JSON",
            "ID": "11729"  # 판례일련번호 예시
        }
    }
]

success_count = 0
results = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*70}")
    print(f"[테스트 {i}/{len(test_cases)}] {test['name']}")
    print(f"{'='*70}")
    print(f"URL: {test['url']}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')
        size = len(response.text)

        print(f"\n📊 응답 정보:")
        print(f"   Status: {status}")
        print(f"   Content-Type: {content_type}")
        print(f"   Size: {size:,} bytes")

        if status == 200 and 'json' in content_type.lower():
            data = response.json()
            print(f"✅ JSON 파싱 성공")

            # PrecSearch 또는 Prec 키 확인
            prec_search = data.get("PrecSearch") or data.get("판례") or data.get("prec")

            if prec_search:
                if isinstance(prec_search, dict):
                    total = prec_search.get("totalCnt", "0")
                    precs = prec_search.get("prec", [])
                    result_msg = prec_search.get("resultMsg", "N/A")
                    result_code = prec_search.get("resultCode", "N/A")

                    print(f"\n✅ 검색 성공!")
                    print(f"   - ResultCode: {result_code}")
                    print(f"   - ResultMsg: {result_msg}")
                    print(f"   - 총 {total}건 발견")

                    if precs and isinstance(precs, list):
                        print(f"\n📚 판례 목록 (상위 {min(len(precs), 3)}개):")
                        for j, prec in enumerate(precs[:3], 1):
                            case_name = prec.get("판례명", prec.get("사건명", "N/A"))
                            case_num = prec.get("판례일련번호", prec.get("사건번호", "N/A"))
                            court = prec.get("법원명", prec.get("판시사항", "N/A"))[:50]
                            date = prec.get("선고일자", "N/A")

                            print(f"\n   [{j}] {case_name}")
                            print(f"       사건번호: {case_num}")
                            print(f"       법원: {court}")
                            print(f"       선고일: {date}")

                        success_count += 1
                        results.append({
                            "test": test['name'],
                            "status": "success",
                            "total": total
                        })
                    else:
                        print(f"\n⚠️  판례 목록이 비어있습니다.")
                        results.append({
                            "test": test['name'],
                            "status": "no_results"
                        })
                else:
                    # 단일 판례 상세 조회
                    print(f"\n✅ 판례 상세 조회 성공!")
                    print(f"\n📄 JSON 구조:")
                    for key in list(data.keys())[:10]:
                        val = str(data[key])[:100]
                        print(f"   - {key}: {val}")

                    success_count += 1
                    results.append({
                        "test": test['name'],
                        "status": "success"
                    })
            else:
                # 데이터 구조 확인
                print(f"\n📄 응답 구조:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
                results.append({
                    "test": test['name'],
                    "status": "unexpected_structure"
                })

        elif 'html' in content_type.lower():
            print(f"\n❌ HTML 에러 페이지")

            if '미신청' in response.text:
                print(f"   → '판례' 종류가 신청되지 않았습니다.")
                print(f"   → open.law.go.kr에서 '판례' 체크 필요")
            elif '사용자인증' in response.text:
                print(f"   → 인증 실패")

            results.append({
                "test": test['name'],
                "status": "html_error"
            })

        else:
            print(f"\n❌ HTTP {status}")
            print(f"응답: {response.text[:300]}")
            results.append({
                "test": test['name'],
                "status": f"http_{status}"
            })

    except requests.exceptions.Timeout:
        print(f"\n❌ 타임아웃")
        results.append({"test": test['name'], "status": "timeout"})
    except Exception as e:
        print(f"\n❌ 예외: {type(e).__name__}: {e}")
        results.append({"test": test['name'], "status": "exception"})

# 최종 결과
print("\n" + "=" * 70)
print("📊 최종 결과")
print("=" * 70)
print(f"성공: {success_count}/{len(test_cases)}")
print(f"실패: {len(test_cases) - success_count}/{len(test_cases)}")

if success_count > 0:
    print("\n✅ 판례 검색 API 정상 작동!")
    print("\n💡 확인된 기능:")
    print("   - 판례 검색 (target=prec)")
    print("   - JSON 형식 응답")
    print("   - 검색 결과 파싱")
elif success_count == 0:
    print("\n❌ 판례 검색 실패")
    print("\n📋 실패 상세:")
    for result in results:
        print(f"   - {result['test']}: {result.get('status', 'unknown')}")

    print("\n💡 조치 필요:")
    print("   1. open.law.go.kr 접속")
    print("   2. [OPEN API] → [OPEN API 신청]")
    print("   3. 등록된 API 선택")
    print("   4. '판례' 종류 체크")
    print("   5. '헌재결정례' 종류 체크")
    print("   6. 저장 후 10-30분 대기")

print("=" * 70)

# 결과 저장
with open('prec_test_results.json', 'w', encoding='utf-8') as f:
    json.dump({
        'timestamp': '2026-02-12',
        'oc': OC,
        'target': 'prec',
        'format': 'JSON',
        'success_count': success_count,
        'total_tests': len(test_cases),
        'results': results
    }, f, indent=2, ensure_ascii=False)

print(f"\n💾 결과 저장: prec_test_results.json")
