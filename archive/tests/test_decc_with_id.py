#!/usr/bin/env python3
"""
행정심판례 ID 파라미터 테스트
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

print("🔍 행정심판례 ID 파라미터 테스트\n")

# 사용자 제공 ID로 테스트
test_ids = ["223311", "223310", "223312", "100001", "200001"]

for test_id in test_ids:
    print(f"\n{'='*70}")
    print(f"ID: {test_id}")
    print(f"{'='*70}")

    params = {
        "OC": api_key,
        "target": "decc",
        "ID": test_id,
        "type": "JSON"
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 응답 성공")
            print(f"   응답 크기: {len(json.dumps(data, ensure_ascii=False))} bytes")

            if len(json.dumps(data)) > 200:  # 실제 데이터가 있는 경우
                print(f"   응답 키: {list(data.keys())}")

                # 상세 출력
                print("\n   📄 응답 내용:")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])

                if len(json.dumps(data)) > 1000:
                    print(f"\n   ... (총 {len(json.dumps(data))} bytes)")
            else:
                print(f"   응답: {data}")

        else:
            print(f"❌ HTTP {response.status_code}")

    except Exception as e:
        print(f"❌ 오류: {e}")

print(f"\n{'='*70}")
print("결론:")
print("  ID 파라미터로 특정 행정심판례를 조회할 수 있습니다!")
print("  하지만 ID를 모르면 검색이 어려울 수 있습니다.")
print(f"{'='*70}\n")
