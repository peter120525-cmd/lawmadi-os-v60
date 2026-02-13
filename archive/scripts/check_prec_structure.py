#!/usr/bin/env python3
"""판례 JSON 응답 구조 확인"""
import requests
import json

OC = "choepeter"

url = "http://www.law.go.kr/DRF/lawSearch.do"
params = {
    "OC": OC,
    "target": "prec",
    "type": "JSON",
    "query": "위헌법률심판",
    "display": 2
}

print("=" * 70)
print("🔍 판례 JSON 응답 구조 분석")
print("=" * 70)

response = requests.get(url, params=params, timeout=10)

if response.status_code == 200:
    data = response.json()

    print("\n📄 전체 JSON 응답:\n")
    print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n" + "=" * 70)
