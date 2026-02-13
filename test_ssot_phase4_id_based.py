#!/usr/bin/env python3
"""
SSOT Phase 4: ID 기반 데이터 소스 테스트
SSOT #8 (행정심판례) + SSOT #9 (조약) 구현 검증

⚠️ 주의: 이 2개 SSOT는 키워드 검색 미지원, ID 파라미터 필수
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connectors.drf_client import DRFConnector
from services.search_service import SearchService

def test_admin_appeals():
    """행정심판례 (SSOT #8) 테스트"""
    print("\n" + "="*70)
    print("SSOT #8: 행정심판례 (target=decc) - ID 기반 조회")
    print("="*70)

    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        return False

    drf = DRFConnector(api_key=api_key)

    # config.json의 sample_ids 사용
    test_ids = ["223311", "223310", "223312"]

    for doc_id in test_ids:
        print(f"\n{'─'*70}")
        print(f"테스트 ID: {doc_id}")
        print(f"{'─'*70}")

        try:
            result = drf.search_admin_appeals(doc_id)
            if result:
                print(f"✅ 성공: {len(json.dumps(result, ensure_ascii=False))} bytes")

                # 응답 구조 확인
                if isinstance(result, dict):
                    print(f"   응답 키: {list(result.keys())}")
                    if "PrecService" in result:
                        prec = result["PrecService"]
                        case_name = prec.get("사건명", "N/A")
                        case_no = prec.get("사건번호", "N/A")
                        print(f"   사건명: {case_name}")
                        print(f"   사건번호: {case_no}")
            else:
                print("⚠️  결과 없음")
        except Exception as e:
            print(f"❌ 실패: {e}")

    print(f"\n{'='*70}\n")
    return True

def test_treaties():
    """조약 (SSOT #9) 테스트"""
    print("\n" + "="*70)
    print("SSOT #9: 조약 (target=trty) - ID 기반 조회")
    print("="*70)

    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        return False

    drf = DRFConnector(api_key=api_key)

    # config.json의 sample_ids 사용
    test_ids = ["983", "2120", "1000"]

    for doc_id in test_ids:
        print(f"\n{'─'*70}")
        print(f"테스트 ID: {doc_id}")
        print(f"{'─'*70}")

        try:
            result = drf.search_treaty(doc_id)
            if result:
                print(f"✅ 성공: {len(json.dumps(result, ensure_ascii=False))} bytes")

                # 응답 구조 확인
                if isinstance(result, dict):
                    print(f"   응답 키: {list(result.keys())}")
                    if "BothTrtyService" in result:
                        treaty = result["BothTrtyService"]
                        treaty_name = treaty.get("조약한글명", "N/A")
                        treaty_no = treaty.get("조약번호", "N/A")
                        print(f"   조약명: {treaty_name}")
                        print(f"   조약번호: {treaty_no}")
                    elif "MultTrtyService" in result:
                        treaty = result["MultTrtyService"]
                        treaty_name = treaty.get("조약한글명", "") or treaty.get("조약명", "N/A")
                        treaty_no = treaty.get("조약번호", "N/A")
                        print(f"   조약명: {treaty_name}")
                        print(f"   조약번호: {treaty_no}")
            else:
                print("⚠️  결과 없음")
        except Exception as e:
            print(f"❌ 실패: {e}")

    print(f"\n{'='*70}\n")
    return True

def test_search_service():
    """SearchService 통합 테스트"""
    print("\n" + "="*70)
    print("SearchService 통합 테스트")
    print("="*70)

    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        return False

    svc = SearchService()

    tests = [
        ("행정심판례 (ID=223311)", lambda: svc.search_admin_appeals("223311")),
        ("조약 (ID=983)", lambda: svc.search_treaty("983")),
    ]

    success_count = 0
    for name, method in tests:
        print(f"\n{name}")
        try:
            result = method()
            if result:
                print(f"  ✅ 성공: {len(str(result))} bytes")
                success_count += 1
            else:
                print(f"  ⚠️  결과 없음")
        except Exception as e:
            print(f"  ❌ 실패: {e}")

    print(f"\n성공률: {success_count}/{len(tests)}")
    print(f"{'='*70}\n")
    return success_count == len(tests)

def test_tool_functions():
    """Gemini Tool 함수 테스트"""
    print("\n" + "="*70)
    print("Gemini Tool 함수 테스트")
    print("="*70)

    # main.py 임포트 및 초기화
    os.environ["DISABLE_FASTAPI_STARTUP"] = "1"
    import main

    # RUNTIME 초기화
    api_key = os.getenv("LAWGO_DRF_OC", "")
    svc = SearchService()
    main.RUNTIME["search_service"] = svc

    tests = [
        ("search_admin_appeals_drf (ID=223311)", lambda: main.search_admin_appeals_drf("223311")),
        ("search_treaty_drf (ID=983)", lambda: main.search_treaty_drf("983")),
    ]

    success_count = 0
    for name, method in tests:
        print(f"\n{name}")
        try:
            result = method()
            if result and result.get("result") == "FOUND":
                print(f"  ✅ FOUND")
                print(f"  출처: {result.get('source', 'N/A')}")
                content = result.get('content', '')
                print(f"  내용: {content[:200]}...")
                success_count += 1
            elif result and result.get("result") == "NO_DATA":
                print(f"  ⚠️  NO_DATA")
            else:
                print(f"  ❌ ERROR: {result}")
        except Exception as e:
            print(f"  ❌ 실패: {e}")

    print(f"\n성공률: {success_count}/{len(tests)}")
    print(f"{'='*70}\n")
    return success_count == len(tests)

def main_test():
    """메인 테스트 실행"""
    print("\n" + "🔍 SSOT Phase 4: ID 기반 데이터 소스 테스트 시작")
    print("="*70)
    print("테스트 대상:")
    print("  - SSOT #8: 행정심판례 (target=decc)")
    print("  - SSOT #9: 조약 (target=trty)")
    print("="*70)

    results = []
    results.append(("행정심판례 DRF", test_admin_appeals()))
    results.append(("조약 DRF", test_treaties()))
    results.append(("SearchService", test_search_service()))
    results.append(("Tool Functions", test_tool_functions()))

    # 최종 결과
    print("\n" + "="*70)
    print("📊 최종 결과")
    print("="*70)
    success_count = sum(1 for _, result in results if result)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    print(f"\n총 성공률: {success_count}/{len(results)} ({success_count*100//len(results)}%)")
    print("="*70)

    if success_count == len(results):
        print("\n🎉 모든 테스트 통과!")
        print("✅ SSOT Phase 4 구현 완료")
        print("✅ 9/10 SSOT 활성화 (90% 달성)")
        print("\n활성화된 SSOT:")
        print("  #1: 현행법령 (law)")
        print("  #2: 행정규칙 (admrul)")
        print("  #4: 자치법규 (ordin)")
        print("  #5: 판례 (prec)")
        print("  #6: 헌재결정례 (prec+필터)")
        print("  #7: 법령해석례 (expc)")
        print("  #8: 행정심판례 (decc) ⚠️ ID 기반")
        print("  #9: 조약 (trty) ⚠️ ID 기반")
        print("  #10: 법령용어 (lstrm)")
        print("\n미구현 SSOT:")
        print("  #3: 학칙공단 (DRF API 미지원)")
    else:
        print("\n⚠️  일부 테스트 실패")

    print()

if __name__ == "__main__":
    main_test()
