#!/usr/bin/env python3
"""
행정심판례 응답 상세 분석
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("LAWGO_DRF_OC", "")
if not api_key:
    print("❌ LAWGO_DRF_OC 환경변수 미설정")
    sys.exit(1)

url = "http://www.law.go.kr/DRF/lawService.do"
params = {
    "OC": api_key,
    "target": "decc",
    "type": "JSON",
    "query": "행정심판"
}

print("🔍 행정심판례 응답 상세 분석\n")

response = requests.get(url, params=params, timeout=10)
data = response.json()

print("전체 JSON 응답:")
print("="*60)
print(json.dumps(data, ensure_ascii=False, indent=2))
print("="*60)

print(f"\n응답 크기: {len(json.dumps(data))} bytes")
print(f"응답 구조: {data}")

# 다른 파라미터 조합 시도
print("\n\n다른 파라미터 조합 테스트:")
print("="*60)

additional_params = [
    {"MST": "001"},  # 법령일련번호
    {"ID": "001"},
    {"pageIndex": "1", "numOfRows": "10"},
    {"sort": "date"},
]

for extra in additional_params:
    test_params = {
        "OC": api_key,
        "target": "decc",
        "type": "JSON",
        "query": "행정심판"
    }
    test_params.update(extra)

    print(f"\n파라미터: {extra}")
    try:
        r = requests.get(url, params=test_params, timeout=10)
        result = r.json()
        print(f"  응답 크기: {len(json.dumps(result))} bytes")
        if len(json.dumps(result)) > 50:
            print(f"  응답 키: {list(result.keys())}")
    except Exception as e:
        print(f"  오류: {e}")

print("\n" + "="*60)
print("결론: target=decc는 작동하지만 데이터가 없거나")
print("      추가 파라미터가 필요할 수 있습니다.")
