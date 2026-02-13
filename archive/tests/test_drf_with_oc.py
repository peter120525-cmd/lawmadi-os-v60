#!/usr/bin/env python3
"""law.go.kr DRF API 테스트 - OC: choepeter"""
import requests
import xml.etree.ElementTree as ET

OC = "choepeter"

print("=" * 70)
print("🧪 law.go.kr DRF API 연결 테스트")
print("=" * 70)
print(f"인증키(OC): {OC}")
print()

# 테스트 케이스
test_cases = [
    {
        "name": "법령 검색 - lawSearch.do",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "law",
            "type": "XML",
            "query": "민법"
        }
    },
    {
        "name": "현행법령 본문 - lawService.do (민법)",
        "url": "http://www.law.go.kr/DRF/lawService.do",
        "params": {
            "OC": OC,
            "target": "law",
            "type": "XML",
            "MST": "138967",  # 민법 법령일련번호
            "display": 5
        }
    },
    {
        "name": "판례 검색 - precSearch.do",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "OC": OC,
            "target": "prec",
            "type": "XML",
            "query": "임대차"
        }
    }
]

success_count = 0
failed_tests = []

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

        if status == 200 and 'xml' in content_type.lower():
            try:
                root = ET.fromstring(response.text)
                print(f"\n✅ XML 파싱 성공")
                print(f"   Root tag: <{root.tag}>")

                # 에러 확인
                error = root.find('.//error')
                if error is not None:
                    error_code = error.findtext('error_code', 'N/A')
                    error_msg = error.findtext('error_message', 'N/A')
                    print(f"\n⚠️  API 에러:")
                    print(f"   코드: {error_code}")
                    print(f"   메시지: {error_msg}")
                    failed_tests.append(f"{test['name']}: {error_msg}")
                else:
                    # 결과 개수 확인
                    total_count = root.findtext('.//totalCnt', '0')
                    print(f"\n✅ 정상 응답!")
                    print(f"   검색 결과: {total_count}건")

                    # 첫 번째 항목 미리보기
                    first_item = root.find('.//*[local-name()="law"]') or root.find('.//*[local-name()="prec"]')
                    if first_item is not None:
                        print(f"\n📄 첫 번째 결과:")
                        for child in list(first_item)[:5]:
                            text = child.text[:100] if child.text else '(empty)'
                            print(f"   - {child.tag}: {text}")

                    success_count += 1

            except ET.ParseError as e:
                print(f"\n❌ XML 파싱 실패: {e}")
                print(f"\n응답 미리보기:")
                print(response.text[:500])
                failed_tests.append(f"{test['name']}: XML 파싱 실패")
        else:
            print(f"\n❌ 응답 실패")
            if 'html' in content_type.lower():
                print(f"   HTML 에러 페이지 반환됨")
                # 에러 메시지 추출
                if '사용자인증' in response.text:
                    print(f"   → 인증 실패")
                    failed_tests.append(f"{test['name']}: 인증 실패")
            print(f"\n응답 미리보기:")
            print(response.text[:300])
            failed_tests.append(f"{test['name']}: HTTP {status}")

    except requests.exceptions.Timeout:
        print(f"\n❌ 타임아웃 (10초 초과)")
        failed_tests.append(f"{test['name']}: 타임아웃")
    except Exception as e:
        print(f"\n❌ 예외 발생: {e}")
        failed_tests.append(f"{test['name']}: {str(e)}")

# 최종 결과
print("\n" + "=" * 70)
print("📊 최종 결과")
print("=" * 70)
print(f"성공: {success_count}/{len(test_cases)}")
print(f"실패: {len(failed_tests)}/{len(test_cases)}")

if success_count > 0:
    print("\n✅ law.go.kr DRF API 연결 성공!")
    print(f"   인증키(OC): {OC} → 정상 작동")
    print("\n💡 다음 단계:")
    print("   1. .env 파일에 LAWGO_DRF_OC 추가")
    print("   2. connectors/drf_client.py에서 사용")
    print("   3. Dual SSOT Primary로 활용")
else:
    print("\n❌ 모든 테스트 실패")
    print("\n실패한 테스트:")
    for failed in failed_tests:
        print(f"   - {failed}")

print("=" * 70)
