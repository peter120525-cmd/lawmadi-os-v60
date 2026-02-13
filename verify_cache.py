#!/usr/bin/env python3
"""
캐시 검증 스크립트
Target별 독립 캐시 키 작동 확인
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connectors.drf_client import DRFConnector

def test_cache():
    print("🔍 캐시 검증 테스트\n")

    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    drf = DRFConnector(api_key=api_key)

    # 동일 쿼리, 다른 target으로 2번씩 호출
    tests = [
        ("law", "민법"),
        ("admrul", "민법"),  # 같은 쿼리, 다른 target
        ("law", "민법"),     # 캐시 HIT 확인
        ("admrul", "민법"),  # 캐시 HIT 확인
    ]

    print("테스트 시나리오:")
    print("1. target=law, query=민법 (Cache MISS)")
    print("2. target=admrul, query=민법 (Cache MISS)")
    print("3. target=law, query=민법 (Cache HIT 예상)")
    print("4. target=admrul, query=민법 (Cache HIT 예상)\n")
    print("="*60)

    for i, (target, query) in enumerate(tests, 1):
        print(f"\n[{i}] target={target}, query={query}")
        result = drf.search_by_target(query, target=target)
        if result:
            print(f"    ✅ 응답 성공: {len(str(result))} bytes")
        else:
            print(f"    ⚠️  응답 없음")

    print("\n" + "="*60)
    print("✅ 캐시 검증 완료")
    print("\n로그에서 다음을 확인하세요:")
    print("  - [Cache MISS] 첫 번째 호출시")
    print("  - [Cache HIT] 두 번째 호출시")
    print("  - target별 독립적인 캐시 키 사용")

if __name__ == "__main__":
    test_cache()
