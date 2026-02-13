#!/usr/bin/env python3
"""
법령용어 (SSOT #10) 완전 테스트
Phase 3 완료 검증
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

    # 법령용어 검색
    test_queries = ["계약", "민법", "불법행위"]

    for query in test_queries:
        print(f"\n[법령용어 검색] query={query}")
        result = drf.search_legal_term(query)

        if result:
            print(f"✅ 성공: {len(str(result))} bytes")
            if isinstance(result, dict):
                print(f"   응답 키: {list(result.keys())}")
                if "LsTrmService" in result:
                    term_data = result["LsTrmService"]
                    print(f"   용어명: {term_data.get('법령용어명_한글', 'N/A')}")
                    print(f"   한자명: {term_data.get('법령용어명_한자', 'N/A')}")
                    definition = term_data.get('법령용어정의', '')
                    if definition:
                        print(f"   정의: {definition[:100]}...")
        else:
            print("⚠️  결과 없음")

    return True

def test_service_level():
    """SearchService 레벨 테스트"""
    print("\n" + "="*60)
    print("2. SearchService 레벨 테스트")
    print("="*60)

    svc = SearchService()
    if not svc.ready:
        print("❌ SearchService 초기화 실패")
        return False

    print("\n[법령용어] search_legal_term()")
    result = svc.search_legal_term("계약")

    if result:
        print(f"✅ 성공: {len(str(result))} bytes")
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

    print("\n[법령용어] search_legal_term_drf()")
    result = main.search_legal_term_drf("계약")

    if result["result"] == "FOUND":
        print(f"✅ 성공: {result['result']}")
        print(f"   출처: {result.get('source', 'N/A')}")
        print(f"   내용 미리보기:")
        content = result.get('content', '')
        print(f"   {content[:200]}")
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
        "search_ordinance_drf",
        "search_legal_term_drf",  # 새로 추가
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
    print("🔍 법령용어 (SSOT #10) 완전 테스트\n")

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
        print("\n🎉 Phase 3 구현 완료! 법령용어 SSOT 활성화됨")
        print("\n현재 활성화된 SSOT:")
        print("  1. 현행법령 (law)")
        print("  2. 행정규칙 (admrul)")
        print("  4. 자치법규 (ordin)")
        print("  5. 판례 (prec)")
        print("  6. 헌재결정례 (prec)")
        print("  7. 법령해석례 (expc)")
        print(" 10. 법령용어 (lstrm) ← NEW!")
        print("\n총 7개 SSOT 활성화 (10개 중 70%)")
    else:
        print("\n⚠️ 일부 테스트 실패")

if __name__ == "__main__":
    main_test()
