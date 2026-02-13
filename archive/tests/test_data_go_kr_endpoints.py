#!/usr/bin/env python3
"""data.go.kr 다양한 엔드포인트 시도"""
import requests
from urllib.parse import unquote

decoded_key = unquote("a0Fyt79Y9YX1G5dUksmVmEy111eipwhoxM%2FTMrZmwp46SEh0Z4ViGDlWOgs2juwW%2BkHgOPK0zfDZ5RN5J0kvEA%3D%3D")

print("=" * 70)
print("🧪 data.go.kr 엔드포인트 탐색")
print("=" * 70)

# 다양한 엔드포인트 조합
endpoints = [
    "https://apis.data.go.kr/1170000/law/lawSearchList.do",
    "https://apis.data.go.kr/1170000/LawService/lawSearchList.do",
    "https://apis.data.go.kr/1170000/LawService/getLawList",
    "https://apis.data.go.kr/1170000/law/getLawList",
    "http://apis.data.go.kr/1170000/law/lawSearchList.do",
]

for endpoint in endpoints:
    print(f"\n{'='*70}")
    print(f"🔗 {endpoint}")
    print(f"{'='*70}")

    params = {
        "serviceKey": decoded_key,
        "numOfRows": 5,
        "pageNo": 1
    }

    try:
        response = requests.get(endpoint, params=params, timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')
        size = len(response.text)

        print(f"Status: {status} | Type: {content_type} | Size: {size}")

        if status == 200:
            print(f"✅ 성공!")
            print(f"\n응답 미리보기:")
            print(response.text[:500])
            print("\n🎉 작동하는 엔드포인트 발견!")
            break
        elif status == 401:
            print(f"⚠️  인증 실패 (401 Unauthorized)")
        elif status == 404:
            print(f"❌ 엔드포인트 없음 (404 Not Found)")
        elif status == 500:
            print(f"⚠️  서버 오류 (500)")
            print(f"응답: {response.text[:200]}")
        else:
            print(f"❌ HTTP {status}")
            print(f"응답: {response.text[:200]}")

    except Exception as e:
        print(f"❌ 예외: {e}")

print("\n" + "=" * 70)
