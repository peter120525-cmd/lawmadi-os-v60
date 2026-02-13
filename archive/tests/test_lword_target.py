#!/usr/bin/env python3
"""
법령용어 Target 조사
lawSearch.do에서 lword target 테스트
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_lword_variations():
    """다양한 법령용어 관련 target 테스트"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        sys.exit(1)

    url = "https://www.law.go.kr/DRF/lawSearch.do"

    # 테스트할 target 목록
    targets = [
        ("lword", "법령용어", "민법"),
        ("word", "용어", "민법"),
        ("term", "용어2", "민법"),
        ("lterm", "법령용어2", "민법"),
        ("dict", "사전", "민법"),
        ("lawword", "법령단어", "민법"),
        ("lawterm", "법령용어3", "민법"),
        ("glossary", "용어집", "민법"),
    ]

    results = {}

    for target, name, query in targets:
        print(f"\n{'='*60}")
        print(f"테스트: target={target} ({name})")
        print(f"{'='*60}")

        params = {
            "OC": api_key,
            "target": target,
            "type": "JSON",
            "query": query
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            content_type = response.headers.get("Content-Type", "")

            print(f"HTTP Status: {response.status_code}")
            print(f"Content-Type: {content_type}")

            if response.status_code == 200 and "json" in content_type.lower():
                data = response.json()
                # 유효한 응답인지 확인
                if data and len(str(data)) > 50:
                    print(f"✅ JSON 응답 성공")
                    print(f"   응답 키: {list(data.keys())}")

                    for key, value in data.items():
                        if isinstance(value, dict):
                            print(f"   {key} 하위 키: {list(value.keys())[:10]}")
                            if "totalCnt" in value:
                                print(f"      검색 결과: {value.get('totalCnt')}건")

                    results[target] = {"success": True, "data": data}
                else:
                    print(f"⚠️  빈 응답")
                    results[target] = {"success": False}
            else:
                print(f"❌ 미지원")
                results[target] = {"success": False}

        except Exception as e:
            print(f"❌ 오류: {e}")
            results[target] = {"success": False}

    # 요약
    print(f"\n\n{'='*60}")
    print("📊 법령용어 Target 조사 결과")
    print(f"{'='*60}")

    working = [t for t, info in results.items() if info.get("success")]

    if working:
        print(f"\n✅ 작동하는 target: {len(working)}개")
        for target in working:
            print(f"   - {target}")
    else:
        print(f"\n❌ 작동하는 target 없음")
        print("\n💡 결론:")
        print("   - lawSearch.do에서 법령용어 target 미지원")
        print("   - lawService.do 엔드포인트도 404 반환")
        print("   - 법령용어는 별도 API 또는 다른 방식 필요")

if __name__ == "__main__":
    test_lword_variations()
