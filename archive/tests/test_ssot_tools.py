#!/usr/bin/env python3
"""
SSOT Phase 1 Tool 함수 테스트
main.py의 새로운 tool 함수들을 직접 호출하여 검증
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Runtime 초기화를 위한 서비스 설정
from services.search_service import SearchService
from connectors.drf_client import DRFConnector

# main.py의 tool 함수들 import
import main

def init_runtime():
    """Runtime 초기화"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # SearchService 초기화
    search_service = SearchService()
    drf_connector = DRFConnector(api_key=api_key)

    # RUNTIME에 서비스 등록
    main.RUNTIME["search_service"] = search_service
    main.RUNTIME["drf"] = drf_connector

    print("✅ Runtime 초기화 완료\n")

def test_tool(name, tool_func, query):
    """Tool 함수 테스트"""
    print(f"\n{'='*60}")
    print(f"테스트: {name}")
    print(f"쿼리: {query}")
    print(f"{'='*60}")

    try:
        result = tool_func(query)

        if result["result"] == "FOUND":
            print(f"✅ 성공: {result['result']}")
            print(f"   출처: {result.get('source', 'N/A')}")
            print(f"   데이터 길이: {len(str(result.get('content', '')))} bytes")

            # 응답 구조 확인
            if isinstance(result.get('content'), dict):
                print(f"   응답 키: {list(result['content'].keys())}")
            return True
        elif result["result"] == "NO_DATA":
            print(f"⚠️  결과 없음: {result.get('message', 'N/A')}")
            return True  # NO_DATA도 정상 응답
        else:
            print(f"❌ 오류: {result.get('message', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def main_test():
    print("🔍 SSOT Phase 1 Tool 함수 테스트 시작\n")

    # Runtime 초기화
    init_runtime()

    # 테스트 케이스
    tests = [
        ("search_law_drf (기존)", main.search_law_drf, "민법"),
        ("search_precedents_drf (기존)", main.search_precedents_drf, "손해배상"),
        ("search_admrul_drf (신규)", main.search_admrul_drf, "공무원 복무규정"),
        ("search_expc_drf (신규)", main.search_expc_drf, "행정절차법 해석"),
        ("search_constitutional_drf (신규)", main.search_constitutional_drf, "재산권 침해"),
    ]

    success_count = 0
    for name, tool_func, query in tests:
        if test_tool(name, tool_func, query):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"테스트 완료: {success_count}/{len(tests)} 성공")
    print(f"{'='*60}\n")

    # Tools 리스트 검증
    print("\n" + "="*60)
    print("Tools 리스트 검증")
    print("="*60)

    expected_tools = [
        "search_law_drf",
        "search_precedents_drf",
        "search_admrul_drf",
        "search_expc_drf",
        "search_constitutional_drf"
    ]

    print(f"\n예상 tool 함수 수: {len(expected_tools)}")
    print(f"실제 정의된 함수들:")

    found_count = 0
    for tool_name in expected_tools:
        if hasattr(main, tool_name):
            print(f"  ✅ {tool_name}")
            found_count += 1
        else:
            print(f"  ❌ {tool_name} - 정의되지 않음")

    print(f"\n검증 결과: {found_count}/{len(expected_tools)} 함수 정의됨")

if __name__ == "__main__":
    main_test()
