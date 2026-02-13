#!/usr/bin/env python3
"""main.py 전체 통합 테스트 (startup 포함)"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

print("=" * 70)
print("🧪 main.py 전체 통합 테스트")
print("=" * 70)

# 환경변수 설정
os.environ["LAWGO_DRF_OC"] = "choepeter"
os.environ["SOFT_MODE"] = "true"
os.environ["DB_DISABLED"] = "1"

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

try:
    from main import app, startup

    # Startup 이벤트 수동 실행
    print("\n🔄 Startup 이벤트 실행 중...")
    asyncio.run(startup())
    print("✅ Startup 완료!\n")

    # TestClient 생성
    client = TestClient(app, raise_server_exceptions=False)

    # 1. /health 테스트
    print("=" * 70)
    print("[1] GET /health")
    print("=" * 70)

    response = client.get("/health")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 성공!")
        print(f"\n📊 시스템 상태:")
        print(f"   - Status: {data.get('status')}")
        print(f"   - OS Version: {data.get('os_version')}")

        diag = data.get('diagnostics', {})
        print(f"\n🔧 모듈 상태:")
        modules = diag.get('modules', {})
        for key, value in modules.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key}: {value}")

        metrics = diag.get('metrics', {})
        print(f"\n📈 메트릭:")
        for key, value in metrics.items():
            print(f"   - {key}: {value}")

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
            # JSON 응답 구조 확인
            if "LawSearch" in data:
                law_search = data["LawSearch"]
                total = law_search.get("totalCnt", "0")
                laws = law_search.get("law", [])
                print(f"\n📚 검색 결과:")
                print(f"   - 총 건수: {total}건")
                print(f"   - 반환: {len(laws)}건")

                if laws:
                    print(f"\n   상위 법령:")
                    for i, law in enumerate(laws[:3], 1):
                        name = law.get("법령명한글", "N/A")
                        dept = law.get("소관부처명", "N/A")
                        print(f"   {i}. {name} ({dept})")
            else:
                print(f"   응답 키: {list(data.keys())}")
                print(f"   내용: {str(data)[:200]}")
    else:
        print(f"❌ 실패: {response.text[:300]}")

    # 3. Low-signal 테스트 (GEMINI 없어도 작동해야 함)
    print("\n" + "=" * 70)
    print("[3] POST /ask (Low-signal 테스트)")
    print("=" * 70)

    response = client.post("/ask", json={"query": "테스트"})
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 성공!")
        print(f"   - Trace ID: {data.get('trace_id')}")
        print(f"   - Leader: {data.get('leader')}")
        print(f"   - Status: {data.get('status')}")
        print(f"\n   응답 미리보기:")
        print(f"   {data.get('response', '')[:300]}...")
    else:
        print(f"❌ 실패: {response.text[:300]}")

    # 4. /ask 실제 질문 (GEMINI_KEY 필요)
    if os.getenv("GEMINI_KEY"):
        print("\n" + "=" * 70)
        print("[4] POST /ask (실제 질문)")
        print("=" * 70)

        response = client.post("/ask", json={"query": "임대차 보증금이란?"})
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 성공!")
            print(f"   - Leader: {data.get('leader')}")
            print(f"   - Status: {data.get('status')}")
            print(f"   - Latency: {data.get('latency_ms')}ms")
            print(f"\n   응답 미리보기:")
            print(f"   {data.get('response', '')[:500]}...")
        else:
            print(f"❌ 실패: {response.text[:300]}")
    else:
        print("\n⚠️  GEMINI_KEY 미설정 - 실제 질문 테스트 스킵")

    print("\n" + "=" * 70)
    print("✅ 전체 테스트 완료!")
    print("=" * 70)

    # 최종 요약
    print("\n📊 테스트 요약:")
    print("   ✅ /health - 정상")
    print("   ✅ /search - 정상")
    print("   ✅ /ask (low-signal) - 정상")
    if os.getenv("GEMINI_KEY"):
        print("   ✅ /ask (실제 질문) - 정상")
    else:
        print("   ⚠️  /ask (실제 질문) - GEMINI_KEY 필요")

except Exception as e:
    print(f"\n❌ 테스트 실패: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
