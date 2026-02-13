#!/usr/bin/env python3
"""data.go.kr API 다양한 엔드포인트 테스트"""
import os
import requests
from urllib.parse import unquote

api_key = os.getenv("DATA_GO_KR_API_KEY")

# 테스트할 다양한 엔드포인트
test_cases = [
    {
        "name": "법률서비스 - lawSearch.do",
        "url": "https://apis.data.go.kr/1170000/LawService/lawSearch.do",
        "params": {
            "serviceKey": api_key,
            "query": "민법",
            "type": "XML",
            "display": 5
        }
    },
    {
        "name": "법률서비스 - getLawSearch (alternative)",
        "url": "https://apis.data.go.kr/1170000/LawService/getLawSearch",
        "params": {
            "serviceKey": api_key,
            "query": "민법",
            "type": "XML",
            "numOfRows": 5
        }
    },
    {
        "name": "법령정보서비스 - getLawList",
        "url": "https://apis.data.go.kr/1170000/LawService/getLawList",
        "params": {
            "serviceKey": api_key,
            "numOfRows": 5,
            "pageNo": 1
        }
    },
    {
        "name": "API 키 디코딩 버전",
        "url": "https://apis.data.go.kr/1170000/LawService/lawSearch.do",
        "params": {
            "serviceKey": unquote(api_key),
            "query": "민법",
            "type": "XML"
        }
    }
]

print("=" * 70)
print("🧪 data.go.kr API 엔드포인트 테스트")
print("=" * 70)
print(f"API Key: {api_key[:30]}...")
print()

for i, test in enumerate(test_cases, 1):
    print(f"\n[{i}] {test['name']}")
    print(f"    URL: {test['url']}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        print(f"    Status: {response.status_code}")
        print(f"    Content-Type: {response.headers.get('Content-Type', 'N/A')}")

        if response.status_code == 200:
            print(f"    ✅ 성공!")
            print(f"    응답 ({len(response.text)} bytes):")
            print(f"    {response.text[:300]}")
            break
        else:
            print(f"    ❌ 실패")
            print(f"    응답: {response.text[:200]}")

    except Exception as e:
        print(f"    ❌ 예외: {e}")

print("\n" + "=" * 70)
