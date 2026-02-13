#!/usr/bin/env python3
"""main.py startup 테스트"""
import sys
import os
import asyncio

# 환경변수 확인
print("=" * 70)
print("🧪 main.py Startup 테스트")
print("=" * 70)

# 환경변수 출력
env_vars = [
    ("LAWGO_DRF_OC", os.getenv("LAWGO_DRF_OC", "")),
    ("GEMINI_KEY", os.getenv("GEMINI_KEY", "")),
    ("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
]

print("\n📋 환경변수 상태:")
for name, value in env_vars:
    if value:
        print(f"  ✅ {name}: {value[:20]}..." if len(value) > 20 else f"  ✅ {name}: 설정됨")
    else:
        print(f"  ❌ {name}: 미설정")

print("\n" + "=" * 70)
print("🚀 FastAPI 앱 Import 시도")
print("=" * 70)

try:
    sys.path.insert(0, '/workspaces/lawmadi-os-v50')

    # main 모듈 import
    import main

    print("✅ main.py import 성공")
    print(f"   - OS Version: {main.OS_VERSION}")
    print(f"   - App Title: {main.app.title}")

    # startup 이벤트 수동 실행
    print("\n" + "=" * 70)
    print("🔄 Startup 이벤트 실행")
    print("=" * 70)

    async def run_startup():
        await main.startup()

    asyncio.run(run_startup())

    print("\n✅ Startup 완료!")

    # RUNTIME 상태 확인
    print("\n" + "=" * 70)
    print("📊 RUNTIME 상태")
    print("=" * 70)

    runtime_keys = [
        "config",
        "drf",
        "selector",
        "guard",
        "search_service",
        "swarm"
    ]

    for key in runtime_keys:
        value = main.RUNTIME.get(key)
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {type(value).__name__ if value else 'None'}")

    # DRF 연결 테스트
    if main.RUNTIME.get("drf"):
        print("\n" + "=" * 70)
        print("🔍 DRF 연결 테스트")
        print("=" * 70)

        drf = main.RUNTIME["drf"]
        print(f"  DRF Key: {drf.drf_key[:20]}...")
        print(f"  Response Format: {drf.response_format}")
        print(f"  Timeout: {drf.timeout_sec}s")

        try:
            result = drf.law_search("민법")
            if result:
                print(f"  ✅ 법령 검색 성공!")
                if isinstance(result, dict):
                    law_search = result.get("LawSearch", {})
                    total = law_search.get("totalCnt", "0")
                    print(f"     총 {total}건 발견")
            else:
                print(f"  ⚠️  검색 결과 없음")
        except Exception as e:
            print(f"  ❌ DRF 테스트 실패: {e}")

    print("\n" + "=" * 70)
    print("✅ main.py 테스트 완료!")
    print("=" * 70)

except ImportError as e:
    print(f"❌ Import 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

except Exception as e:
    print(f"❌ 예외 발생: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
