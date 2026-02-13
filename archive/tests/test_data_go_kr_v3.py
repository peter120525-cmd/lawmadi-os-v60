#!/usr/bin/env python3
"""data.go.kr API 올바른 엔드포인트로 테스트"""
import os
import requests

api_key = os.getenv("DATA_GO_KR_API_KEY")

print("=" * 70)
print("🧪 data.go.kr 법령정보 API 테스트 (올바른 엔드포인트)")
print("=" * 70)
print(f"API Key: {api_key[:30]}...")
print()

# 올바른 엔드포인트
test_cases = [
    {
        "name": "법령정보 목록 조회 (lawSearchList)",
        "url": "http://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "ServiceKey": api_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "법령정보 목록 조회 (HTTPS)",
        "url": "https://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "ServiceKey": api_key,
            "target": "law",
            "type": "XML"
        }
    },
    {
        "name": "법령정보 검색 (query 포함)",
        "url": "http://apis.data.go.kr/1170000/law/lawSearchList.do",
        "params": {
            "ServiceKey": api_key,
            "target": "law",
            "type": "XML",
            "query": "민법"
        }
    }
]

success = False

for i, test in enumerate(test_cases, 1):
    print(f"\n[테스트 {i}] {test['name']}")
    print(f"URL: {test['url']}")
    print(f"Params: {test['params']}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"✓ Size: {len(response.text)} bytes")

        if response.status_code == 200:
            print(f"✅ 성공!")
            print(f"\n📄 응답 미리보기:")
            print(response.text[:500])
            success = True
            break
        else:
            print(f"❌ 실패 - HTTP {response.status_code}")
            print(f"응답: {response.text[:300]}")

    except Exception as e:
        print(f"❌ 예외: {e}")

print("\n" + "=" * 70)
if success:
    print("✅ data.go.kr API 연결 성공!")
else:
    print("❌ 모든 테스트 실패")
    print("\n💡 확인 사항:")
    print("   1. API 키가 승인되었는지 확인 (data.go.kr 마이페이지)")
    print("   2. '법제처 국가법령정보 공유서비스' 활용신청 완료 확인")
    print("   3. API 키 활성화까지 1-2시간 소요될 수 있음")
print("=" * 70)
