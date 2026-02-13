#!/usr/bin/env python3
"""DRFConnector 클래스 테스트 (JSON 형식)"""
import sys
import os
sys.path.insert(0, '/workspaces/lawmadi-os-v50')

from connectors.drf_client import DRFConnector
import json

print("=" * 70)
print("🧪 DRFConnector 클래스 테스트 (JSON 형식)")
print("=" * 70)

# 환경변수 확인
oc = os.getenv("LAWGO_DRF_OC")
print(f"LAWGO_DRF_OC: {oc if oc else '❌ 미설정'}\n")

# DRFConnector 초기화 (JSON 형식)
connector = DRFConnector(response_format="JSON")

print(f"✓ DRFConnector 초기화 완료")
print(f"  - drf_key: {connector.drf_key[:20]}..." if connector.drf_key else "  - drf_key: None")
print(f"  - response_format: {connector.response_format}")
print(f"  - timeout_sec: {connector.timeout_sec}\n")

# 법령 검색 테스트
queries = ["민법", "임대차", "형법"]

for query in queries:
    print(f"\n{'='*70}")
    print(f"🔍 검색: '{query}'")
    print(f"{'='*70}")

    try:
        result = connector.law_search(query)

        if result:
            print(f"✅ 검색 성공!")

            # JSON 결과 처리
            if isinstance(result, dict):
                law_search = result.get("LawSearch", {})
                total = law_search.get("totalCnt", "0")
                laws = law_search.get("law", [])

                print(f"  - 총 {total}건 발견")

                if laws and isinstance(laws, list):
                    print(f"\n  📚 검색 결과 (상위 3개):")
                    for i, law in enumerate(laws[:3], 1):
                        law_name = law.get("법령명한글", "N/A")
                        law_type = law.get("법령구분명", "N/A")
                        dept = law.get("소관부처명", "N/A")
                        mst = law.get("법령일련번호", "N/A")
                        print(f"  {i}. {law_name} ({law_type}) - {dept} [MST: {mst}]")
            else:
                print(f"  ⚠️  XML 형식 응답 (예상치 못함)")

        else:
            print(f"❌ 검색 실패 - 결과 없음")

    except Exception as e:
        print(f"❌ 예외 발생: {type(e).__name__}: {e}")

print("\n" + "=" * 70)
print("✅ DRFConnector 테스트 완료")
print("=" * 70)
