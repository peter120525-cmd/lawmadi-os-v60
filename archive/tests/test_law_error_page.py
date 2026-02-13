#!/usr/bin/env python3
"""law.go.kr 에러 페이지 내용 확인"""
import requests

url = "http://www.law.go.kr/DRF/lawSearch.do"
params = {
    "target": "law",
    "type": "XML",
    "query": "민법"
}

print("=" * 70)
print("🔍 law.go.kr 응답 내용 확인")
print("=" * 70)

response = requests.get(url, params=params, timeout=10)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"\n📄 전체 응답:\n")
print(response.text)
print("\n" + "=" * 70)
