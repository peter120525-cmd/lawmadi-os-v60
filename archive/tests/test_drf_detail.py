#!/usr/bin/env python3
"""law.go.kr DRF API 상세 응답 확인"""
import requests
import json

OC = "choepeter"

print("🔍 DRF API 상세 응답 분석\n")

# 법령 검색 테스트
url = "http://www.law.go.kr/DRF/lawSearch.do"
params = {
    "OC": OC,
    "target": "law",
    "type": "JSON",
    "query": "민법"
}

print(f"요청 URL: {url}")
print(f"파라미터: {params}\n")

response = requests.get(url, params=params, timeout=10)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"Size: {len(response.text)} bytes\n")

print("=" * 70)
print("전체 응답 (JSON):")
print("=" * 70)

try:
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
except:
    print("JSON 파싱 실패")
    print(response.text)
