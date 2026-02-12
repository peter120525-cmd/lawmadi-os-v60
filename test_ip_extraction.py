#!/usr/bin/env python3
"""
IP 주소 추출 테스트
- 다양한 헤더 시나리오 테스트
"""
import sys
sys.path.insert(0, '/workspaces/lawmadi-os-v50')

from fastapi import Request
from fastapi.testclient import TestClient
from main import app, _get_client_ip

def test_ip_extraction():
    """IP 추출 함수 테스트"""
    print("=" * 80)
    print("🔍 IP 주소 추출 테스트")
    print("=" * 80)

    client = TestClient(app)

    # 시나리오 1: X-Forwarded-For 헤더
    print("\n1️⃣ X-Forwarded-For 헤더 테스트")
    response = client.get("/health", headers={
        "X-Forwarded-For": "203.0.113.195, 198.51.100.178"
    })
    print(f"   헤더: X-Forwarded-For: 203.0.113.195, 198.51.100.178")
    print(f"   예상: 203.0.113.195 (첫 번째 IP)")

    # 시나리오 2: X-Real-IP 헤더
    print("\n2️⃣ X-Real-IP 헤더 테스트")
    response = client.get("/health", headers={
        "X-Real-IP": "198.51.100.50"
    })
    print(f"   헤더: X-Real-IP: 198.51.100.50")
    print(f"   예상: 198.51.100.50")

    # 시나리오 3: 직접 연결 (헤더 없음)
    print("\n3️⃣ 직접 연결 테스트 (헤더 없음)")
    response = client.get("/health")
    print(f"   헤더: (없음)")
    print(f"   예상: testclient (테스트 환경)")

    print("\n" + "=" * 80)

    # 실제 /api/visit 엔드포인트 테스트
    print("\n🧪 /api/visit 엔드포인트 테스트")
    print("=" * 80)

    print("\n✅ 테스트 1: X-Forwarded-For 사용")
    response = client.post("/api/visit",
        json={},
        headers={"X-Forwarded-For": "1.2.3.4"}
    )
    print(f"   상태 코드: {response.status_code}")
    result = response.json()
    print(f"   응답: {result}")

    print("\n✅ 테스트 2: X-Real-IP 사용")
    response = client.post("/api/visit",
        json={},
        headers={"X-Real-IP": "5.6.7.8"}
    )
    print(f"   상태 코드: {response.status_code}")
    result = response.json()
    print(f"   응답: {result}")

    print("\n" + "=" * 80)
    print("✅ IP 추출 테스트 완료!")
    print("=" * 80)

if __name__ == "__main__":
    test_ip_extraction()
