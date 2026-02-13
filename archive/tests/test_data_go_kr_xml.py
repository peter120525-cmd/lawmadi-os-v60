#!/usr/bin/env python3
"""data.go.kr API 테스트 - XML 형식"""
import requests
import xml.etree.ElementTree as ET
from urllib.parse import unquote

# 인증키 (Encoding)
encoded_key = "a0Fyt79Y9YX1G5dUksmVmEy111eipwhoxM%2FTMrZmwp46SEh0Z4ViGDlWOgs2juwW%2BkHgOPK0zfDZ5RN5J0kvEA%3D%3D"
decoded_key = unquote(encoded_key)

print("=" * 70)
print("🧪 data.go.kr API 테스트 (XML 형식)")
print("=" * 70)
print(f"Encoded Key: {encoded_key[:50]}...")
print(f"Decoded Key: {decoded_key[:50]}...")
print()

# 엔드포인트 테스트
base_url = "https://apis.data.go.kr/1170000/law"

test_cases = [
    {
        "name": "법령 검색 - lawSearch.do (인코딩 키)",
        "url": f"{base_url}/lawSearch.do",
        "params": {
            "serviceKey": encoded_key,
            "target": "law",
            "type": "XML",
            "query": "민법"
        }
    },
    {
        "name": "법령 검색 - lawSearch.do (디코딩 키)",
        "url": f"{base_url}/lawSearch.do",
        "params": {
            "serviceKey": decoded_key,
            "target": "law",
            "type": "XML",
            "query": "민법"
        }
    },
    {
        "name": "법령 목록 - lawSearchList.do (인코딩 키)",
        "url": f"{base_url}/lawSearchList.do",
        "params": {
            "serviceKey": encoded_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "법령 목록 - lawSearchList.do (디코딩 키)",
        "url": f"{base_url}/lawSearchList.do",
        "params": {
            "serviceKey": decoded_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "법령 검색 - ServiceKey 대문자 (인코딩)",
        "url": f"{base_url}/lawSearch.do",
        "params": {
            "ServiceKey": encoded_key,
            "target": "law",
            "type": "XML",
            "query": "민법"
        }
    }
]

success_count = 0

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

        if status == 200:
            # XML 파싱 시도
            if 'xml' in content_type.lower() or response.text.strip().startswith('<?xml'):
                try:
                    root = ET.fromstring(response.text)
                    print(f"\n✅ XML 파싱 성공!")
                    print(f"   Root tag: <{root.tag}>")

                    # 에러 확인
                    error_code = root.findtext('.//errMsg') or root.findtext('.//returnAuthMsg')
                    if error_code:
                        print(f"\n⚠️  에러 메시지: {error_code}")
                    else:
                        # 성공적인 응답
                        total = root.findtext('.//totalCnt') or root.findtext('.//totalCount')
                        print(f"\n✅ 정상 응답!")
                        if total:
                            print(f"   총 건수: {total}")

                        # 첫 번째 항목 출력
                        items = root.findall('.//*')
                        if items:
                            print(f"\n📄 응답 구조 (상위 10개 태그):")
                            for item in items[:10]:
                                text = (item.text or '').strip()[:50]
                                print(f"   - <{item.tag}>: {text}")

                        success_count += 1

                except ET.ParseError as e:
                    print(f"\n❌ XML 파싱 실패: {e}")
                    print(f"\n응답 미리보기:")
                    print(response.text[:500])

            # 일반 텍스트 응답
            elif 'text/plain' in content_type:
                print(f"\n⚠️  Plain text 응답:")
                print(f"   {response.text[:200]}")

            # HTML 에러 페이지
            elif 'html' in content_type.lower():
                print(f"\n❌ HTML 에러 페이지")
                print(f"   응답: {response.text[:200]}")

            else:
                print(f"\n⚠️  예상치 못한 Content-Type")
                print(f"   응답: {response.text[:300]}")

        else:
            print(f"\n❌ HTTP {status}")
            print(f"   응답: {response.text[:300]}")

    except requests.exceptions.Timeout:
        print(f"\n❌ 타임아웃 (10초 초과)")
    except Exception as e:
        print(f"\n❌ 예외: {type(e).__name__}: {e}")

# 최종 결과
print("\n" + "=" * 70)
print("📊 최종 결과")
print("=" * 70)
print(f"성공: {success_count}/{len(test_cases)}")

if success_count > 0:
    print("\n✅ data.go.kr API 연결 성공!")
    print("\n💡 사용 가능한 설정:")
    print(f"   - Base URL: {base_url}")
    print(f"   - ServiceKey: (인코딩 또는 디코딩)")
    print(f"   - Format: XML")
else:
    print("\n❌ 모든 테스트 실패")
    print("\n📋 확인 사항:")
    print("   1. 활용신청 승인 상태")
    print("   2. 트래픽 할당 여부")
    print("   3. API 키 유효성")

print("=" * 70)
