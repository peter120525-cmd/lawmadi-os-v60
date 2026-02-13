#!/usr/bin/env python3
"""
Phase 2 완료 테스트
SSOT #4: 자치법규 (ordin) 구현 검증
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connectors.drf_client import DRFConnector
from services.search_service import SearchService
import main

def test_drf_level():
    """DRF 클라이언트 레벨 테스트"""
    print("="*60)
    print("1. DRF 클라이언트 레벨 테스트")
    print("="*60)

    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        return False

    drf = DRFConnector(api_key=api_key)

    # 자치법규 검색
    print("\n[SSOT #4: 자치법규] target=ordin, query=주차장 조례")
    result = drf.search_by_target("주차장 조례", target="ordin")

    if result:
        print(f"✅ 성공: {len(str(result))} bytes")
        print(f"   응답 키: {list(result.keys())}")

        if "OrdinSearch" in result:
            ordin_data = result["OrdinSearch"]
            print(f"   OrdinSearch 키: {list(ordin_data.keys())}")
            print(f"   검색 결과: {ordin_data.get('totalCnt', 0)}건")
        return True
    else:
        print("❌ 실패: 응답 없음")
        return False

def test_service_level():
    """SearchService 레벨 테스트"""
    print("\n" + "="*60)
    print("2. SearchService 레벨 테스트")
    print("="*60)

    svc = SearchService()
    if not svc.ready:
        print("❌ SearchService 초기화 실패")
        return False

    print("\n[SSOT #4: 자치법규] search_ordinance()")
    result = svc.search_ordinance("주차장 조례")

    if result:
        print(f"✅ 성공: {len(str(result))} bytes")
        if isinstance(result, dict) and "OrdinSearch" in result:
            print(f"   검색 결과: {result['OrdinSearch'].get('totalCnt', 0)}건")
        return True
    else:
        print("❌ 실패: 응답 없음")
        return False

def test_tool_level():
    """Tool 함수 레벨 테스트"""
    print("\n" + "="*60)
    print("3. Tool 함수 레벨 테스트")
    print("="*60)

    # Runtime 초기화
    api_key = os.getenv("LAWGO_DRF_OC", "")
    svc = SearchService()
    drf = DRFConnector(api_key=api_key)

    main.RUNTIME["search_service"] = svc
    main.RUNTIME["drf"] = drf

    print("\n[SSOT #4: 자치법규] search_ordinance_drf()")
    result = main.search_ordinance_drf("주차장 조례")

    if result["result"] == "FOUND":
        print(f"✅ 성공: {result['result']}")
        print(f"   출처: {result.get('source', 'N/A')}")
        print(f"   데이터 길이: {len(str(result.get('content', '')))} bytes")
        return True
    else:
        print(f"❌ 실패: {result.get('message', 'Unknown error')}")
        return False

def test_tools_list():
    """Tools 리스트 검증"""
    print("\n" + "="*60)
    print("4. Tools 리스트 검증")
    print("="*60)

    expected_tools = [
        "search_law_drf",
        "search_precedents_drf",
        "search_admrul_drf",
        "search_expc_drf",
        "search_constitutional_drf",
        "search_ordinance_drf",  # 새로 추가
    ]

    print(f"\n예상 tool 함수 수: {len(expected_tools)}")
    found_count = 0

    for tool_name in expected_tools:
        if hasattr(main, tool_name):
            print(f"  ✅ {tool_name}")
            found_count += 1
        else:
            print(f"  ❌ {tool_name} - 정의되지 않음")

    print(f"\n검증 결과: {found_count}/{len(expected_tools)} 함수 정의됨")
    return found_count == len(expected_tools)

def main_test():
    print("🔍 Phase 2 완료 테스트\n")

    results = {
        "DRF 레벨": test_drf_level(),
        "Service 레벨": test_service_level(),
        "Tool 레벨": test_tool_level(),
        "Tools 리스트": test_tools_list(),
    }

    print("\n" + "="*60)
    print("📊 전체 테스트 결과")
    print("="*60)

    success_count = sum(results.values())
    total_count = len(results)

    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {name}")

    print(f"\n성공: {success_count}/{total_count}")

    if success_count == total_count:
        print("\n🎉 Phase 2 구현 완료! 자치법규 SSOT 활성화됨")
        print("\n현재 활성화된 SSOT:")
        print("  1. 현행법령 (law)")
        print("  2. 행정규칙 (admrul)")
        print("  4. 자치법규 (ordin) ← NEW!")
        print("  5. 판례 (prec)")
        print("  6. 헌재결정례 (prec)")
        print("  7. 법령해석례 (expc)")
        print("\n총 6개 SSOT 활성화 (10개 중 60%)")
    else:
        print("\n⚠️ 일부 테스트 실패")

if __name__ == "__main__":
    main_test()
