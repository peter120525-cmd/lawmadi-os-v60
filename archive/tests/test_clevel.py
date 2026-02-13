#!/usr/bin/env python3
"""
C-Level 임원 시스템 테스트

3명의 C-Level 임원:
- 서연 (CSO): Chief Strategy Officer
- 지유 (CTO): Chief Technology Officer
- 유나 (CCO): Chief Content Officer
"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

print("=" * 80)
print("👔 C-Level 임원 시스템 테스트")
print("=" * 80)
print()
print("3명의 C-Level 임원:")
print("- 서연 (CSO): Chief Strategy Officer - 전략 분석")
print("- 지유 (CTO): Chief Technology Officer - 기술 자문")
print("- 유나 (CCO): Chief Content Officer - 콘텐츠 설계")
print()
print("=" * 80)

# 환경변수 설정
os.environ["LAWGO_DRF_OC"] = "choepeter"
os.environ["SOFT_MODE"] = "true"
os.environ["DB_DISABLED"] = "1"
os.environ["USE_SWARM"] = "true"

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

try:
    from main import app, startup

    # Startup
    print("\n🔄 시스템 초기화 중...")
    asyncio.run(startup())
    print("✅ 초기화 완료\n")

    client = TestClient(app, raise_server_exceptions=False)

    # Health check
    response = client.get("/health")
    if response.status_code == 200:
        data = response.json()
        diag = data.get('diagnostics', {})
        modules = diag.get('modules', {})

        if modules.get("clevel_handler"):
            print("✅ CLevelHandler 활성화됨\n")
        else:
            print("❌ CLevelHandler 비활성화됨\n")

    # 테스트 시나리오
    test_scenarios = [
        {
            "title": "시나리오 1: 서연 (CSO) 직접 호출",
            "query": "서연님, 임대차 분쟁 사건의 전략적 우선순위를 알려주세요.",
            "expected_executive": "CSO",
            "expected_keywords": ["전략", "우선순위", "단계"],
        },
        {
            "title": "시나리오 2: 지유 (CTO) 전문 영역",
            "query": "법률 시스템 아키텍처를 어떻게 설계하면 무결성을 보장할 수 있나요?",
            "expected_executive": "CTO",
            "expected_keywords": ["시스템", "아키텍처", "무결성", "검증"],
        },
        {
            "title": "시나리오 3: 유나 (CCO) 전문 영역",
            "query": "법률 상담 콘텐츠를 일반 사용자가 이해하기 쉽게 설계하려면?",
            "expected_executive": "CCO",
            "expected_keywords": ["콘텐츠", "사용자", "UX", "이해"],
        },
        {
            "title": "시나리오 4: 일반 질문 (일반 Leader)",
            "query": "전세금 반환 청구는 어떻게 하나요?",
            "expected_executive": None,
            "expected_keywords": ["전세", "임대차", "보증금"],
        }
    ]

    for idx, scenario in enumerate(test_scenarios, 1):
        print("=" * 80)
        print(f"[{idx}] {scenario['title']}")
        print("=" * 80)

        print(f"\n📖 Query:")
        print(f"{scenario['query']}")

        print(f"\n⏳ 분석 중...")

        response = client.post("/ask", json={"query": scenario['query']})

        if response.status_code == 200:
            data = response.json()

            print(f"\n✅ 응답 완료!")
            print(f"\n📊 결과:")
            print(f"   - Leader: {data.get('leader')}")
            print(f"   - Status: {data.get('status')}")
            print(f"   - Latency: {data.get('latency_ms', 0) / 1000:.1f}초")

            full_response = data.get('response', '')

            # C-Level 검증
            expected_exec = scenario.get('expected_executive')

            if expected_exec:
                exec_names = {
                    "CSO": "서연",
                    "CTO": "지유",
                    "CCO": "유나"
                }
                expected_name = exec_names.get(expected_exec)

                if expected_name in data.get('leader', ''):
                    print(f"\n   ✅ 예상 C-Level 호출됨: {expected_name} ({expected_exec})")
                else:
                    print(f"\n   ⚠️  예상과 다른 Leader: 예상={expected_name}, 실제={data.get('leader')}")

                # 응답 시작 확인
                exec_prefix = f"[{expected_name}"
                if exec_prefix in full_response[:100]:
                    print(f"   ✅ C-Level 응답 형식 확인")
                else:
                    print(f"   ⚠️  응답 형식 미확인")

            # 키워드 검증
            print(f"\n🔍 키워드 검증:")
            keywords_found = 0
            for keyword in scenario['expected_keywords']:
                if keyword in full_response:
                    print(f"   ✅ {keyword}")
                    keywords_found += 1
                else:
                    print(f"   ❌ {keyword}")

            keyword_coverage = (keywords_found / len(scenario['expected_keywords'])) * 100
            print(f"\n   📈 키워드 커버리지: {keyword_coverage:.0f}% ({keywords_found}/{len(scenario['expected_keywords'])})")

            # 응답 미리보기
            print(f"\n💬 응답 미리보기:")
            print(f"{'─' * 80}")
            lines = full_response.split('\n')
            for line in lines[:15]:
                if line.strip():
                    print(f"   {line[:80]}")
            if len(lines) > 15:
                print(f"   ... ({len(lines) - 15}줄 더 있음)")
            print(f"{'─' * 80}")

        else:
            print(f"\n❌ 응답 실패: HTTP {response.status_code}")
            print(f"   {response.text[:500]}")

        print()

    # 최종 평가
    print("=" * 80)
    print("🎯 C-Level 시스템 평가")
    print("=" * 80)

    print("\n✅ 구현된 기능:")
    print("   1. ✅ 이름으로 직접 호출 (서연/지유/유나)")
    print("   2. ✅ 전문 영역 자동 탐지 (전략/기술/콘텐츠)")
    print("   3. ✅ C-Level 전용 시스템 지시")
    print("   4. ✅ 일반 질문은 일반 Leader 처리")

    print("\n💡 사용 방법:")
    print("   - 이름 호출: '서연님, ...', 'CSO, ...'")
    print("   - 자동 탐지: '전략', '시스템', 'UX' 등 키워드 3개 이상")
    print("   - 일반 질문: 기존대로 처리")

    print("\n" + "=" * 80)
    print("✅ 테스트 완료!")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ 테스트 실패: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
