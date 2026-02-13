#!/usr/bin/env python3
"""
SSOT Phase 1 통합 테스트
5개 SSOT 데이터 소스 검증
"""
import os
import sys
import json
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connectors.drf_client import DRFConnector
from services.search_service import SearchService

def test_ssot(name, method, query):
    """SSOT 개별 테스트"""
    print(f"\n{'='*60}")
    print(f"테스트: {name}")
    print(f"쿼리: {query}")
    print(f"{'='*60}")

    try:
        result = method(query)
        if result:
            print(f"✅ 성공: {len(str(result))} bytes")
            # 응답 구조 출력 (간략)
            if isinstance(result, dict):
                print(f"   응답 키: {list(result.keys())}")
                # 첫 번째 depth 탐색
                for key, value in result.items():
                    if isinstance(value, dict):
                        print(f"   {key} 하위 키: {list(value.keys())}")
                    elif isinstance(value, list):
                        print(f"   {key} 리스트 길이: {len(value)}")
        else:
            print("⚠️  결과 없음 (NO_DATA)")
        return True
    except Exception as e:
        print(f"❌ 실패: {e}")
        return False

def main():
    print("🔍 SSOT Phase 1 통합 테스트 시작\n")

    # DRFConnector 초기화
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    drf = DRFConnector(api_key=api_key)

    # 테스트 케이스
    tests = [
        ("SSOT #1: 현행법령", lambda q: drf.search_by_target(q, target="law"), "민법"),
        ("SSOT #2: 행정규칙", lambda q: drf.search_by_target(q, target="admrul"), "공무원 복무규정"),
        ("SSOT #5: 판례", lambda q: drf.search_by_target(q, target="prec"), "손해배상"),
        ("SSOT #6: 헌재결정례", lambda q: drf.search_by_target(q, target="prec"), "헌법재판소 재산권"),
        ("SSOT #7: 법령해석례", lambda q: drf.search_by_target(q, target="expc"), "행정절차법 해석"),
    ]

    success_count = 0
    for name, method, query in tests:
        if test_ssot(name, method, query):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"테스트 완료: {success_count}/{len(tests)} 성공")
    print(f"{'='*60}\n")

    # SearchService 통합 테스트
    print("\n" + "="*60)
    print("SearchService 통합 테스트")
    print("="*60)

    svc = SearchService()
    if not svc.ready:
        print("⚠️  SearchService 초기화 실패")
        return

    service_tests = [
        ("행정규칙 (SearchService)", lambda: svc.search_admrul("공무원 복무규정")),
        ("법령해석례 (SearchService)", lambda: svc.search_expc("행정절차법 해석")),
        ("헌재결정례 (SearchService)", lambda: svc.search_constitutional("재산권 침해")),
    ]

    for name, method in service_tests:
        print(f"\n{name}:")
        try:
            result = method()
            if result:
                print(f"  ✅ 성공: {len(str(result))} bytes")
            else:
                print("  ⚠️  결과 없음")
        except Exception as e:
            print(f"  ❌ 실패: {e}")

if __name__ == "__main__":
    main()
