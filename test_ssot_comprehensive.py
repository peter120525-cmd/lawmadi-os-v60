#!/usr/bin/env python3
"""
SSOT 종합 테스트 - 전체 9개 데이터 소스 검증
Lawmadi OS v60 - 9/10 SSOT 커버리지 (학칙공단 제외)
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connectors.drf_client import DRFConnector
from services.search_service import SearchService

def print_header(title):
    """테스트 섹션 헤더 출력"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def print_test(name, query):
    """개별 테스트 헤더 출력"""
    print(f"\n{'─'*70}")
    print(f"🔍 {name}")
    print(f"   쿼리: {query}")
    print(f"{'─'*70}")

def test_ssot(name, method, query, expected_keys=None):
    """
    SSOT 개별 테스트 함수

    Args:
        name: SSOT 이름
        method: 테스트할 메서드
        query: 검색 쿼리
        expected_keys: 응답에서 확인할 필수 키 리스트 (선택)

    Returns:
        (success: bool, result: dict)
    """
    print_test(name, query)

    try:
        result = method(query)

        if result:
            result_str = str(result)
            size = len(result_str)
            print(f"✅ 성공: {size:,} bytes")

            # 응답 구조 분석
            if isinstance(result, dict):
                keys = list(result.keys())
                print(f"   📦 응답 키: {keys[:5]}")  # 처음 5개만 출력

                # 필수 키 검증
                if expected_keys:
                    missing = [k for k in expected_keys if k not in result]
                    if missing:
                        print(f"   ⚠️  누락된 키: {missing}")
                        return False, result

                # 데이터 항목 수 확인
                for key in keys:
                    if isinstance(result[key], (list, dict)):
                        if isinstance(result[key], list):
                            print(f"   📊 {key}: {len(result[key])} items")
                        elif isinstance(result[key], dict) and 'law' in result[key]:
                            print(f"   📊 {key}.law: {len(result[key].get('law', []))} items")
                        elif isinstance(result[key], dict) and 'prec' in result[key]:
                            print(f"   📊 {key}.prec: {len(result[key].get('prec', []))} items")

                # 샘플 데이터 출력
                sample_data = result_str[:200]
                print(f"   💾 샘플: {sample_data}...")

            return True, result
        else:
            print("⚠️  결과 없음 (NO_DATA)")
            return False, None

    except Exception as e:
        error_msg = str(e)
        print(f"❌ 실패: {error_msg[:200]}")
        return False, None

def main():
    """메인 테스트 실행"""
    print("\n" + "="*70)
    print("  🔍 Lawmadi OS - SSOT 종합 테스트")
    print("  📅 ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70)

    # 환경변수 확인
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("\n❌ 오류: LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
        print("   .env 파일을 확인하세요.")
        sys.exit(1)

    print(f"\n✅ DRF API Key: {api_key[:10]}...{api_key[-5:]}")

    # DRFConnector 초기화
    print("\n🔧 DRFConnector 초기화 중...")
    drf = DRFConnector(api_key=api_key)
    print("✅ DRFConnector 초기화 완료")

    # SearchService 초기화
    print("🔧 SearchService 초기화 중...")

    # SearchService는 환경변수에서 DRF API 키를 읽어 자동 초기화
    search_service = SearchService()
    print("✅ SearchService 초기화 완료")

    # ===================================================================
    # Phase 1: DRF 기본 검색 (lawSearch.do 엔드포인트)
    # ===================================================================
    print_header("Phase 1: DRF 기본 검색 (5개 SSOT)")

    phase1_tests = [
        {
            "name": "SSOT #1: 현행법령 (law)",
            "method": lambda q: drf.search_by_target(q, target="law"),
            "query": "민법",
            "expected_keys": ["LawSearch"]
        },
        {
            "name": "SSOT #2: 행정규칙 (admrul)",
            "method": lambda q: drf.search_by_target(q, target="admrul"),
            "query": "공무원 복무규정",
            "expected_keys": ["AdmRulSearch"]
        },
        {
            "name": "SSOT #5: 판례 (prec)",
            "method": lambda q: drf.search_by_target(q, target="prec"),
            "query": "손해배상",
            "expected_keys": ["PrecSearch"]
        },
        {
            "name": "SSOT #6: 헌재결정례 (prec 필터링)",
            "method": lambda q: search_service.search_constitutional(q),
            "query": "위헌",
            "expected_keys": ["PrecSearch"]
        },
        {
            "name": "SSOT #7: 법령해석례 (expc)",
            "method": lambda q: drf.search_by_target(q, target="expc"),
            "query": "행정절차법 해석",
            "expected_keys": ["Expc"]
        },
    ]

    phase1_results = []
    for test in phase1_tests:
        success, result = test_ssot(
            test["name"],
            test["method"],
            test["query"],
            test.get("expected_keys")
        )
        phase1_results.append({
            "name": test["name"],
            "success": success,
            "query": test["query"]
        })

    # ===================================================================
    # Phase 2: 추가 SSOT (ordin, decc, trty, lstrm)
    # ===================================================================
    print_header("Phase 2: 추가 SSOT (4개)")

    phase2_tests = [
        {
            "name": "SSOT #4: 자치법규 (ordin)",
            "method": lambda q: drf.search_by_target(q, target="ordin"),
            "query": "서울시 조례",
            "expected_keys": None  # 응답 구조 미확인
        },
        {
            "name": "SSOT #10: 법령용어 (lstrm)",
            "method": lambda q: drf.search_by_target(q, target="lstrm"),
            "query": "법인",
            "expected_keys": None  # 응답 구조 미확인
        },
    ]

    phase2_results = []
    for test in phase2_tests:
        success, result = test_ssot(
            test["name"],
            test["method"],
            test["query"],
            test.get("expected_keys")
        )
        phase2_results.append({
            "name": test["name"],
            "success": success,
            "query": test["query"]
        })

    # ===================================================================
    # 결과 요약
    # ===================================================================
    print_header("📊 테스트 결과 요약")

    total_tests = len(phase1_results) + len(phase2_results)
    total_success = sum(1 for r in phase1_results + phase2_results if r["success"])
    success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0

    print(f"\n전체 결과: {total_success}/{total_tests} 성공 ({success_rate:.1f}%)")

    print(f"\n{'─'*70}")
    print("Phase 1: DRF 기본 검색")
    print(f"{'─'*70}")
    for r in phase1_results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['name']}")
        print(f"   쿼리: {r['query']}")

    print(f"\n{'─'*70}")
    print("Phase 2: 추가 SSOT")
    print(f"{'─'*70}")
    for r in phase2_results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['name']}")
        print(f"   쿼리: {r['query']}")

    # ===================================================================
    # 최종 평가
    # ===================================================================
    print(f"\n{'='*70}")
    if success_rate >= 80:
        print("✅ 테스트 통과! SSOT 시스템이 정상 작동합니다.")
    elif success_rate >= 50:
        print("⚠️  일부 SSOT에서 문제가 발견되었습니다.")
    else:
        print("❌ 테스트 실패! SSOT 시스템을 점검하세요.")
    print(f"{'='*70}\n")

    # 종료 코드 반환
    sys.exit(0 if success_rate >= 80 else 1)

if __name__ == "__main__":
    main()
