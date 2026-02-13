#!/usr/bin/env python3
"""data.go.kr API 파라미터 대소문자 변형 테스트"""
import os
import requests
from urllib.parse import unquote

api_key = os.getenv("DATA_GO_KR_API_KEY")
decoded_key = unquote(api_key)

print("=" * 70)
print("🧪 data.go.kr API 파라미터 변형 테스트")
print("=" * 70)
print(f"Encoded Key: {api_key[:40]}...")
print(f"Decoded Key: {decoded_key[:40]}...")
print()

# 다양한 파라미터 조합
test_cases = [
    {
        "name": "serviceKey (소문자, 인코딩)",
        "url": "http://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "serviceKey": api_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "serviceKey (소문자, 디코딩)",
        "url": "http://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "serviceKey": decoded_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "ServiceKey (대문자, 인코딩)",
        "url": "http://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "ServiceKey": api_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "ServiceKey (대문자, 디코딩)",
        "url": "http://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "ServiceKey": decoded_key,
            "target": "law",
            "type": "XML"
        }
    }
]

success = False

for i, test in enumerate(test_cases, 1):
    print(f"\n[테스트 {i}] {test['name']}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')

        print(f"Status: {status} | Content-Type: {content_type}")

        if status == 200:
            print(f"✅ 성공!")
            print(f"\n📄 응답 ({len(response.text)} bytes):")
            print(response.text[:500])
            success = True
            break
        elif status == 401 or "SERVICE_KEY" in response.text:
            print(f"⚠️  인증 오류 - API 키 문제")
            print(f"응답: {response.text[:200]}")
        else:
            print(f"❌ 실패 (HTTP {status})")
            if len(response.text) < 200:
                print(f"응답: {response.text}")

    except Exception as e:
        print(f"❌ 예외: {e}")

print("\n" + "=" * 70)

if success:
    print("✅ data.go.kr API 연결 성공!")
else:
    print("❌ 모든 테스트 실패")
    print("\n🔍 진단:")
    print("   - API 키는 발급되었으나 서비스 활성화가 안 된 것으로 보입니다.")
    print("   - data.go.kr 마이페이지에서 다음을 확인하세요:")
    print("     1. '법제처 국가법령정보 공유서비스(15000115)' 활용신청 상태")
    print("     2. 승인 여부 및 트래픽 할당")
    print("     3. API 키가 해당 서비스에 등록되었는지")

print("=" * 70)
