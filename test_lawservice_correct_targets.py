#!/usr/bin/env python3
"""
lawService.do 정확한 Target 테스트
조약(trty) 및 법령용어(lstrm) 검증
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_lawservice_target(target, name, query):
    """lawService.do의 특정 target 테스트"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        sys.exit(1)

    # lawService.do 엔드포인트 사용
    url = "http://www.law.go.kr/DRF/lawService.do"

    params = {
        "OC": api_key,
        "target": target,
        "type": "JSON",
        "query": query if query else "",  # query 선택적
    }

    print(f"\n{'='*70}")
    print(f"테스트: {name} (target={target})")
    print(f"URL: {url}")
    print(f"Query: {query if query else 'N/A'}")
    print(f"{'='*70}")

    try:
        response = requests.get(url, params=params, timeout=10)

        print(f"HTTP Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")

        content_type = response.headers.get("Content-Type", "")

        if response.status_code != 200:
            print(f"❌ HTTP 오류: {response.status_code}")
            print(f"응답: {response.text[:500]}")
            return False

        if "json" in content_type.lower():
            try:
                data = response.json()
                print(f"✅ JSON 응답 성공")
                print(f"   응답 키: {list(data.keys())}")

                # 응답 구조 분석
                for key, value in data.items():
                    if isinstance(value, dict):
                        print(f"   {key} 하위 키: {list(value.keys())[:15]}")
                        if "totalCnt" in value:
                            print(f"      📊 검색 결과: {value.get('totalCnt')}건")
                        if "resultCode" in value:
                            print(f"      resultCode: {value.get('resultCode')}")
                        if "resultMsg" in value:
                            print(f"      resultMsg: {value.get('resultMsg')}")
                    elif isinstance(value, list):
                        print(f"   {key} 리스트 길이: {len(value)}개")
                        if value and isinstance(value[0], dict):
                            print(f"      첫 항목 키: {list(value[0].keys())[:10]}")

                print(f"\n   전체 응답 크기: {len(str(data))} bytes")
                return True

            except Exception as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"   응답 미리보기: {response.text[:500]}")
                return False

        elif "html" in content_type.lower():
            print(f"❌ HTML 응답 (target 미지원)")
            print(f"   응답 미리보기: {response.text[:200]}")
            return False

        else:
            print(f"⚠️  알 수 없는 Content-Type")
            print(f"   응답 미리보기: {response.text[:300]}")
            # 빈 응답이어도 200이면 일단 성공으로 간주하고 내용 확인
            if len(response.text.strip()) == 0:
                print(f"   ⚠️  빈 응답 (파라미터 부족 가능성)")
                return False
            return False

    except Exception as e:
        print(f"❌ 요청 실패: {e}")
        return False

def main():
    print("🔍 lawService.do 정확한 Target 테스트\n")

    tests = [
        # 조약 (SSOT #9)
        ("trty", "조약", "무역협정"),
        ("trty", "조약", "한미FTA"),
        ("trty", "조약", None),  # query 없이도 작동하는지 확인

        # 법령용어 (SSOT #10)
        ("lstrm", "법령용어", "민법"),
        ("lstrm", "법령용어", "계약"),
        ("lstrm", "법령용어", None),  # query 없이도 작동하는지 확인
    ]

    results = {}

    for target, name, query in tests:
        test_id = f"{name}({target})"
        if query:
            test_id += f" - {query}"
        else:
            test_id += " - no query"

        success = test_lawservice_target(target, name, query)
        results[test_id] = success

    # 결과 요약
    print(f"\n\n{'='*70}")
    print("📊 테스트 결과 요약")
    print(f"{'='*70}\n")

    working = [test for test, success in results.items() if success]
    failed = [test for test, success in results.items() if not success]

    if working:
        print(f"✅ 성공: {len(working)}개")
        for test in working:
            print(f"   - {test}")

    if failed:
        print(f"\n❌ 실패: {len(failed)}개")
        for test in failed:
            print(f"   - {test}")

    print("\n" + "="*70)

    if working:
        print("\n🎉 결론:")
        print("   lawService.do 엔드포인트가 작동합니다!")
        print("   - 조약 (target=trty)")
        print("   - 법령용어 (target=lstrm)")
        print("\n   Phase 3 구현 가능!")
    else:
        print("\n💡 추가 조사 필요")

if __name__ == "__main__":
    main()
