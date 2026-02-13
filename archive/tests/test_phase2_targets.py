#!/usr/bin/env python3
"""
Phase 2: Target 조사 스크립트
DRF API에서 지원하는 target 값 확인
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_target(target, query="테스트"):
    """특정 target이 DRF API에서 작동하는지 테스트"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    url = "https://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": api_key,
        "target": target,
        "type": "JSON",
        "query": query
    }

    print(f"\n{'='*70}")
    print(f"테스트: target={target}, query={query}")
    print(f"{'='*70}")

    try:
        response = requests.get(url, params=params, timeout=10)

        print(f"HTTP Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")

        content_type = response.headers.get("Content-Type", "")

        if response.status_code != 200:
            print(f"❌ HTTP 오류: {response.status_code}")
            print(f"응답: {response.text[:300]}")
            return False

        if "json" in content_type.lower():
            try:
                data = response.json()
                print(f"✅ JSON 응답 성공")
                print(f"   응답 키: {list(data.keys())}")

                # 응답 구조 분석
                for key, value in data.items():
                    if isinstance(value, dict):
                        print(f"   {key} 하위 키: {list(value.keys())[:10]}")
                    elif isinstance(value, list):
                        print(f"   {key} 리스트 길이: {len(value)}")
                    else:
                        print(f"   {key}: {value}")

                # totalCnt 확인
                for key, value in data.items():
                    if isinstance(value, dict) and "totalCnt" in value:
                        print(f"\n   📊 검색 결과: {value.get('totalCnt', 0)}건")

                return True

            except Exception as e:
                print(f"❌ JSON 파싱 실패: {e}")
                return False

        elif "html" in content_type.lower():
            print(f"❌ HTML 응답 (target 미지원 가능성)")
            print(f"   응답 미리보기: {response.text[:200]}")
            return False

        else:
            print(f"⚠️  알 수 없는 Content-Type")
            print(f"   응답 미리보기: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ 요청 실패: {e}")
        return False

def main():
    print("🔍 Phase 2: Target 조사 시작\n")
    print("DRF API 지원 여부 확인 중...\n")

    # Phase 2 대상 target 목록
    targets = [
        ("edulaw", "학칙공단", "학칙"),
        ("adrule", "자치법규", "조례"),
        ("adprec", "행정심판례", "행정심판"),
        ("treaty", "조약", "조약"),
        # 추가 가능성 있는 target들
        ("ordin", "자치법규(대체)", "조례"),
        ("admprec", "행정심판례(대체)", "행정심판"),
    ]

    results = {}

    for target, name, query in targets:
        success = test_target(target, query)
        results[target] = {"name": name, "success": success}

    # 결과 요약
    print(f"\n\n{'='*70}")
    print("📊 테스트 결과 요약")
    print(f"{'='*70}\n")

    working = []
    failed = []

    for target, info in results.items():
        status = "✅ 작동" if info["success"] else "❌ 미지원"
        print(f"{status} | target={target:12} | {info['name']}")

        if info["success"]:
            working.append(target)
        else:
            failed.append(target)

    print(f"\n작동하는 target: {len(working)}개")
    print(f"미지원 target: {len(failed)}개")

    if working:
        print(f"\n✅ 구현 가능한 SSOT:")
        for target in working:
            print(f"   - {target} ({results[target]['name']})")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()
