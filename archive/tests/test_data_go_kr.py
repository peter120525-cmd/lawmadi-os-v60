#!/usr/bin/env python3
"""data.go.kr 연결 테스트 스크립트"""
import os
import sys
import requests
from datetime import datetime

def test_data_go_kr():
    """data.go.kr API 연결 테스트"""

    # API 키 확인
    api_key = os.getenv("DATA_GO_KR_API_KEY")
    if not api_key:
        print("❌ DATA_GO_KR_API_KEY 환경변수가 설정되지 않았습니다.")
        return False

    print(f"✓ API Key: {api_key[:20]}... (발견)")

    # 테스트 URL
    base_url = "https://apis.data.go.kr/1170000/LawService"
    endpoint = "lawSearch.do"
    test_url = f"{base_url}/{endpoint}"

    print(f"\n📡 테스트 URL: {test_url}")

    # 테스트 쿼리
    params = {
        "serviceKey": api_key,
        "query": "민법",
        "type": "XML",
        "display": 5
    }

    try:
        print(f"\n🔄 요청 중... (timeout: 10s)")
        response = requests.get(test_url, params=params, timeout=10)

        print(f"✓ HTTP Status: {response.status_code}")
        print(f"✓ Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"✓ Response Size: {len(response.text)} bytes")

        if response.status_code == 200:
            print("\n✅ data.go.kr 연결 성공!")

            # XML 응답 일부 출력
            content_preview = response.text[:500]
            print(f"\n📄 응답 미리보기:\n{content_preview}...")

            # 에러 메시지 확인
            if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in response.text:
                print("\n⚠️  API 키가 등록되지 않았거나 유효하지 않습니다.")
                return False
            elif "INVALID_REQUEST_PARAMETER_ERROR" in response.text:
                print("\n⚠️  요청 파라미터가 유효하지 않습니다.")
                return False

            return True
        else:
            print(f"\n❌ 연결 실패: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        print("\n❌ 타임아웃: 10초 내에 응답이 없습니다.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 연결 오류: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        return False

def test_law_go_kr():
    """law.go.kr DRF 연결 테스트 (Primary)"""

    api_key = os.getenv("LAWGO_DRF_OC")
    if not api_key:
        print("\n⚠️  LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
        return False

    print(f"\n\n🔵 law.go.kr DRF 테스트")
    print(f"✓ API Key: {api_key[:20]}... (발견)")

    test_url = "https://www.law.go.kr/DRF/lawSearch.do"
    print(f"📡 테스트 URL: {test_url}")

    params = {
        "OC": api_key,
        "target": "law",
        "type": "XML",
        "query": "민법"
    }

    try:
        print(f"\n🔄 요청 중... (timeout: 10s)")
        response = requests.get(test_url, params=params, timeout=10)

        print(f"✓ HTTP Status: {response.status_code}")
        print(f"✓ Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"✓ Response Size: {len(response.text)} bytes")

        if response.status_code == 200:
            print("\n✅ law.go.kr DRF 연결 성공!")
            content_preview = response.text[:500]
            print(f"\n📄 응답 미리보기:\n{content_preview}...")
            return True
        else:
            print(f"\n❌ 연결 실패: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 data.go.kr / law.go.kr 연결 테스트")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n🟢 data.go.kr 테스트 (Fallback)")
    data_go_result = test_data_go_kr()

    law_go_result = test_law_go_kr()

    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    print(f"data.go.kr (Fallback): {'✅ 성공' if data_go_result else '❌ 실패'}")
    print(f"law.go.kr (Primary):   {'✅ 성공' if law_go_result else '❌ 실패'}")

    if law_go_result or data_go_result:
        print("\n✅ 최소 하나의 API가 정상 작동합니다.")
        sys.exit(0)
    else:
        print("\n❌ 모든 API 연결에 실패했습니다.")
        sys.exit(1)
