#!/usr/bin/env python3
"""
Phase 3: lawService.do 엔드포인트 조사
법령용어 검색 방법 연구
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_lawservice(params_desc, **params):
    """lawService.do 엔드포인트 테스트"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        sys.exit(1)

    url = "https://www.law.go.kr/DRF/lawService.do"

    # 기본 파라미터
    request_params = {
        "OC": api_key,
        "type": "JSON",
    }
    request_params.update(params)

    print(f"\n{'='*70}")
    print(f"테스트: {params_desc}")
    print(f"파라미터: {params}")
    print(f"{'='*70}")

    try:
        response = requests.get(url, params=request_params, timeout=10)

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
                        # resultCode, resultMsg 확인
                        if "resultCode" in value:
                            print(f"      resultCode: {value.get('resultCode')}")
                        if "resultMsg" in value:
                            print(f"      resultMsg: {value.get('resultMsg')}")
                        if "totalCnt" in value:
                            print(f"      totalCnt: {value.get('totalCnt')}건")
                    elif isinstance(value, list):
                        print(f"   {key} 리스트 길이: {len(value)}")
                        if value and len(value) > 0:
                            print(f"      첫 항목 키: {list(value[0].keys()) if isinstance(value[0], dict) else 'N/A'}")

                # 내용 미리보기
                print(f"\n   전체 응답 크기: {len(str(data))} bytes")

                return True

            except Exception as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"   응답 미리보기: {response.text[:500]}")
                return False

        else:
            print(f"⚠️  비-JSON 응답")
            print(f"   응답 미리보기: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ 요청 실패: {e}")
        return False

def main():
    print("🔍 Phase 3: lawService.do 엔드포인트 조사\n")

    # 다양한 파라미터 조합 테스트
    tests = [
        # 1. 법령일련번호로 조회 (민법 예시: 법령ID를 알고 있다고 가정)
        ("법령 상세 조회 (MST)", {"MST": "000001"}),
        ("법령 상세 조회 (법령ID)", {"법령ID": "000001"}),

        # 2. 법령용어 검색 시도
        ("법령용어 검색 (target=lword)", {"target": "lword", "query": "민법"}),
        ("법령용어 검색 (type=lword)", {"type": "JSON", "query": "민법"}),

        # 3. 조문 내용 검색
        ("조문 검색", {"MST": "001", "section": "1"}),

        # 4. 법령 일련번호 + 법령용어 조합
        ("법령번호+용어", {"MST": "001", "target": "lword"}),

        # 5. 다른 가능한 파라미터들
        ("ID 파라미터", {"ID": "001"}),
        ("lawId 파라미터", {"lawId": "001"}),
    ]

    results = {}

    for desc, params in tests:
        success = test_lawservice(desc, **params)
        results[desc] = success

    # 결과 요약
    print(f"\n\n{'='*70}")
    print("📊 테스트 결과 요약")
    print(f"{'='*70}\n")

    working = [desc for desc, success in results.items() if success]
    failed = [desc for desc, success in results.items() if not success]

    print(f"✅ 성공: {len(working)}개")
    for desc in working:
        print(f"   - {desc}")

    print(f"\n❌ 실패: {len(failed)}개")
    for desc in failed:
        print(f"   - {desc}")

    print("\n" + "="*70)

    # lawSearch.do와 비교
    print("\n💡 참고: lawSearch.do는 검색 엔드포인트")
    print("   lawService.do는 상세 조회 엔드포인트일 가능성")
    print("   법령용어는 lawSearch.do의 target일 수도 있음")

if __name__ == "__main__":
    main()
