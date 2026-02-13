#!/usr/bin/env python3
"""main.py HTTP 엔드포인트 테스트"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

print("=" * 70)
print("🧪 main.py HTTP 엔드포인트 테스트")
print("=" * 70)

# 환경변수 설정
os.environ["LAWGO_DRF_OC"] = "choepeter"
os.environ["SOFT_MODE"] = "true"
os.environ["DB_DISABLED"] = "1"

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

try:
    from main import app

    # TestClient 생성
    client = TestClient(app)

    print("\n✅ TestClient 생성 완료")

    # 1. /health 테스트
    print("\n" + "=" * 70)
    print("[1] GET /health")
    print("=" * 70)

    response = client.get("/health")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 성공!")
        print(f"   - Status: {data.get('status')}")
        print(f"   - OS Version: {data.get('os_version')}")
        print(f"   - Diagnostics:")

        diag = data.get('diagnostics', {})
        modules = diag.get('modules', {})
        for key, value in modules.items():
            status = "✅" if value else "❌"
            print(f"      {status} {key}: {value}")
    else:
        print(f"❌ 실패: {response.status_code}")
        print(response.text)

    # 2. /search 테스트
    print("\n" + "=" * 70)
    print("[2] GET /search?q=민법")
    print("=" * 70)

    response = client.get("/search", params={"q": "민법", "limit": 3})
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 성공!")
        if isinstance(data, dict):
            print(f"   응답 구조: {list(data.keys())}")
    else:
        print(f"❌ 실패: {response.status_code}")
        print(response.text[:500])

    # 3. /ask 테스트 (GEMINI_KEY 없으면 FAIL_CLOSED 예상)
    print("\n" + "=" * 70)
    print("[3] POST /ask")
    print("=" * 70)

    if os.getenv("GEMINI_KEY"):
        response = client.post("/ask", json={"query": "임대차 계약이란?"})
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 성공!")
            print(f"   - Trace ID: {data.get('trace_id')}")
            print(f"   - Leader: {data.get('leader')}")
            print(f"   - Status: {data.get('status')}")
            print(f"   - Response: {data.get('response', '')[:200]}...")
        else:
            print(f"❌ 실패: {response.status_code}")
            print(response.text[:500])
    else:
        print("⚠️  GEMINI_KEY 미설정 - FAIL_CLOSED 예상")
        response = client.post("/ask", json={"query": "테스트"})
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Response: {data.get('response', '')[:200]}")

    print("\n" + "=" * 70)
    print("✅ 엔드포인트 테스트 완료!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 테스트 실패: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
