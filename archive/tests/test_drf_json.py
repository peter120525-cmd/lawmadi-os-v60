#!/usr/bin/env python3
"""law.go.kr DRF API 테스트 - JSON 형식"""
import requests
import json

OC = "choepeter"

print("=" * 70)
print("🧪 law.go.kr DRF API 연결 테스트 (JSON)")
print("=" * 70)
print(f"인증키(OC): {OC}")
print(f"응답 형식: JSON")
print()

# JSON 형식으로 테스트
test_cases = [
    {
        "name": "법령 검색 - lawSearch.do (JSON)",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "law",
            "type": "JSON",
            "query": "민법",
            "display": 5
        }
    },
    {
        "name": "현행법령 목록 - lawSearch.do (JSON)",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "law",
            "type": "JSON",
            "query": "임대차",
            "display": 3
        }
    },
    {
        "name": "현행법령 본문 - lawService.do (JSON)",
        "url": "http://www.law.go.kr/DRF/lawService.do",
        "params": {
            "OC": OC,
            "target": "law",
            "type": "JSON",
            "MST": "138967"  # 민법
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
    print(f"Params: {test['params']}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')
        size = len(response.text)

        print(f"\n📊 응답 정보:")
        print(f"   Status: {status}")
        print(f"   Content-Type: {content_type}")
        print(f"   Size: {size:,} bytes")

        if status == 200:
            # JSON 파싱 시도
            if 'json' in content_type.lower() or response.text.strip().startswith('{'):
                try:
                    data = response.json()
                    print(f"\n✅ JSON 파싱 성공!")

                    # 구조 확인
                    print(f"\n📄 JSON 구조:")
                    for key in list(data.keys())[:10]:
                        value = data[key]
                        if isinstance(value, (list, dict)):
                            print(f"   - {key}: {type(value).__name__} ({len(value)} items)")
                        else:
                            val_str = str(value)[:50]
                            print(f"   - {key}: {val_str}")

                    # 에러 확인
                    if 'error' in data or 'errorCode' in data:
                        print(f"\n⚠️  API 에러 응답:")
                        print(f"   {json.dumps(data, indent=2, ensure_ascii=False)[:300]}")
                        results.append({"test": test['name'], "status": "error", "data": data})
                    else:
                        # 성공
                        print(f"\n✅ 정상 응답!")

                        # 검색 결과 확인
                        total = data.get('totalCnt', data.get('total', 0))
                        print(f"   검색 결과: {total}건")

                        # 법령 목록 미리보기
                        laws = data.get('law', data.get('LawSearch', data.get('laws', [])))
                        if laws and isinstance(laws, list) and len(laws) > 0:
                            print(f"\n📚 첫 번째 법령:")
                            first = laws[0]
                            for key, val in list(first.items())[:5]:
                                print(f"   - {key}: {str(val)[:100]}")

                        success_count += 1
                        results.append({"test": test['name'], "status": "success", "total": total})

                except json.JSONDecodeError as e:
                    print(f"\n❌ JSON 파싱 실패: {e}")
                    print(f"\n응답 미리보기:")
                    print(response.text[:500])
                    results.append({"test": test['name'], "status": "json_error", "error": str(e)})

            # HTML 에러 페이지
            elif 'html' in content_type.lower():
                print(f"\n❌ HTML 에러 페이지 반환됨")

                # 에러 메시지 추출
                if '미신청' in response.text:
                    print(f"   → 법령종류 미신청 또는 JSON 형식 미체크")
                elif '사용자인증' in response.text:
                    print(f"   → 인증 실패")
                elif '목록/본문' in response.text:
                    print(f"   → 목록/본문 접근 권한 없음")

                print(f"\n에러 내용:")
                # h2 태그 추출 시도
                import re
                h2_match = re.search(r'<h2>(.*?)</h2>', response.text)
                if h2_match:
                    print(f"   {h2_match.group(1)}")

                results.append({"test": test['name'], "status": "html_error"})
            else:
                print(f"\n⚠️  예상치 못한 Content-Type")
                print(f"응답 미리보기:")
                print(response.text[:300])
                results.append({"test": test['name'], "status": "unknown_type"})
        else:
            print(f"\n❌ HTTP {status} 에러")
            print(f"응답: {response.text[:300]}")
            results.append({"test": test['name'], "status": f"http_{status}"})

    except requests.exceptions.Timeout:
        print(f"\n❌ 타임아웃 (10초 초과)")
        results.append({"test": test['name'], "status": "timeout"})
    except Exception as e:
        print(f"\n❌ 예외 발생: {type(e).__name__}: {e}")
        results.append({"test": test['name'], "status": "exception", "error": str(e)})

# 최종 결과
print("\n" + "=" * 70)
print("📊 최종 결과")
print("=" * 70)
print(f"성공: {success_count}/{len(test_cases)}")
print(f"실패: {len(test_cases) - success_count}/{len(test_cases)}")

if success_count > 0:
    print("\n✅ law.go.kr DRF API (JSON) 연결 성공!")
    print(f"\n인증 정보:")
    print(f"   - OC: {OC}")
    print(f"   - 형식: JSON")
    print(f"   - 상태: 정상 작동")

    print(f"\n💡 다음 단계:")
    print(f"   1. .env 파일에 LAWGO_DRF_OC={OC} 추가")
    print(f"   2. connectors/drf_client.py 업데이트 (JSON 지원)")
    print(f"   3. config.json에서 type: JSON으로 설정")
elif success_count == 0:
    print("\n❌ 모든 테스트 실패")
    print("\n📋 결과 상세:")
    for result in results:
        status = result.get('status', 'unknown')
        print(f"   - {result['test']}: {status}")

    print("\n💡 조치 사항:")
    print("   1. open.law.go.kr 재접속")
    print("   2. [OPEN API] → [OPEN API 신청]")
    print("   3. 등록된 API에서 다음 확인:")
    print("      - ✅ '목록' 체크 (lawSearch)")
    print("      - ✅ '본문' 체크 (lawService)")
    print("      - ✅ 'JSON' 형식 체크")
    print("      - ✅ '법령' 종류 체크")
    print("   4. 저장 후 10-30분 대기")

print("=" * 70)

# 결과를 파일로 저장
with open('drf_test_results.json', 'w', encoding='utf-8') as f:
    json.dump({
        'timestamp': '2026-02-12',
        'oc': OC,
        'format': 'JSON',
        'success_count': success_count,
        'total_tests': len(test_cases),
        'results': results
    }, f, indent=2, ensure_ascii=False)

print(f"\n💾 결과 저장: drf_test_results.json")
