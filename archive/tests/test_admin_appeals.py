#!/usr/bin/env python3
"""
행정심판례 (SSOT #8) 테스트
target=decc 검증
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_admin_appeals():
    """행정심판례 검색 테스트"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        sys.exit(1)

    url = "http://www.law.go.kr/DRF/lawService.do"

    test_queries = [
        "행정심판",
        "행정처분",
        "취소청구",
        None  # query 없이도 작동하는지 확인
    ]

    print("🔍 행정심판례 (SSOT #8) 테스트\n")

    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"Query: {query if query else 'N/A'}")
        print(f"{'='*70}")

        params = {
            "OC": api_key,
            "target": "decc",
            "type": "JSON",
        }
        if query:
            params["query"] = query

        try:
            response = requests.get(url, params=params, timeout=10)

            print(f"HTTP Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")

                if "json" in content_type.lower():
                    data = response.json()
                    print(f"✅ JSON 응답 성공")
                    print(f"   응답 크기: {len(str(data))} bytes")
                    print(f"   응답 키: {list(data.keys())}")

                    # 응답 구조 분석
                    for key, value in data.items():
                        if isinstance(value, dict):
                            print(f"   {key} 하위 키: {list(value.keys())[:15]}")
                            if "totalCnt" in value:
                                print(f"      📊 검색 결과: {value.get('totalCnt')}건")
                            if "resultCode" in value:
                                print(f"      resultCode: {value.get('resultCode')}")
                        elif isinstance(value, list):
                            print(f"   {key} 리스트 길이: {len(value)}개")
                            if value and isinstance(value[0], dict):
                                print(f"      첫 항목 키: {list(value[0].keys())[:10]}")
                else:
                    print(f"⚠️  비-JSON 응답")
                    print(f"   응답: {response.text[:200]}")
            else:
                print(f"❌ HTTP 오류: {response.status_code}")
                print(f"   응답: {response.text[:200]}")

        except Exception as e:
            print(f"❌ 요청 실패: {e}")

    print(f"\n{'='*70}")
    print("결론:")
    print("  target=decc가 작동하면 즉시 구현 가능!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    test_admin_appeals()
