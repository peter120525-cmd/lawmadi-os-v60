#!/usr/bin/env python3
"""
행정심판례 LM 파라미터 테스트
LM = Law Match/Law Name (추정)
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

print("🔍 행정심판례 LM 파라미터 테스트\n")
print("="*70)

# 테스트 1: LM 파라미터만 사용 (ID 없이)
print("\n1️⃣ LM 파라미터만 사용 (키워드 검색 가능성)")
print("="*70)

test_keywords = [
    "과징금",
    "과징금 부과처분 취소청구",
    "영업정지",
    "행정처분",
    "취소청구"
]

for keyword in test_keywords:
    print(f"\n키워드: {keyword}")
    print("─"*70)

    params = {
        "OC": api_key,
        "target": "decc",
        "LM": keyword,
        "type": "JSON"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            data_size = len(json.dumps(data, ensure_ascii=False))
            print(f"✅ 응답 성공: {data_size} bytes")

            if data_size > 100:
                print(f"   응답 키: {list(data.keys())}")

                # 상세 확인
                if "PrecService" in data:
                    prec = data["PrecService"]
                    case_name = prec.get("사건명", "N/A")
                    case_no = prec.get("사건번호", "N/A")
                    print(f"   사건명: {case_name}")
                    print(f"   사건번호: {case_no}")
                elif "Law" in data:
                    print(f"   메시지: {data['Law']}")
            else:
                print(f"   응답: {data}")
        else:
            print(f"❌ HTTP {response.status_code}")

    except Exception as e:
        print(f"❌ 오류: {e}")

# 테스트 2: 사용자 제공 URL (ID + LM 함께)
print("\n\n2️⃣ ID + LM 함께 사용 (사용자 제공 예시)")
print("="*70)

params = {
    "OC": api_key,
    "target": "decc",
    "ID": "245011",
    "LM": "과징금 부과처분 취소청구",
    "type": "JSON"
}

try:
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        data_size = len(json.dumps(data, ensure_ascii=False))
        print(f"✅ 응답 성공: {data_size} bytes")
        print(f"   응답 키: {list(data.keys())}")

        if "PrecService" in data:
            prec = data["PrecService"]
            print(f"\n   📄 상세 정보:")
            print(f"   사건명: {prec.get('사건명', 'N/A')}")
            print(f"   사건번호: {prec.get('사건번호', 'N/A')}")
            print(f"   피청구인: {prec.get('피청구인', 'N/A')}")
            print(f"   주문: {prec.get('주문', 'N/A')[:100]}...")
except Exception as e:
    print(f"❌ 오류: {e}")

# 테스트 3: ID만 사용 vs LM만 사용 비교
print("\n\n3️⃣ 파라미터 조합 비교")
print("="*70)

test_cases = [
    {"name": "ID만", "params": {"ID": "223311"}},
    {"name": "LM만", "params": {"LM": "국가유공자"}},
    {"name": "ID+LM", "params": {"ID": "223311", "LM": "국가유공자"}},
]

for test in test_cases:
    print(f"\n{test['name']}: {test['params']}")

    params = {
        "OC": api_key,
        "target": "decc",
        "type": "JSON"
    }
    params.update(test['params'])

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        data_size = len(json.dumps(data, ensure_ascii=False))

        if data_size > 100:
            print(f"  ✅ {data_size} bytes - 데이터 있음")
            if "PrecService" in data:
                print(f"     사건명: {data['PrecService'].get('사건명', 'N/A')}")
        else:
            print(f"  ⚠️ {data_size} bytes - {data}")

    except Exception as e:
        print(f"  ❌ 오류: {e}")

print("\n" + "="*70)
print("결론:")
print("  LM 파라미터로 키워드 검색이 가능한지 확인!")
print("="*70 + "\n")
