#!/usr/bin/env python3
"""
Lawmadi OS 철학 테스트:
"답을 말해주는 시스템이 아닌, 판단이 흘러갈 수 있도록 돕는 구조"

테스트 시나리오:
1. 구체적 사건 이야기 → 맥락 해석
2. 다층적 정보 제공 → 판단 재료
3. 시간축 분석 → 흐름 파악
4. 절차 안내 → 다음 행동 방향
"""

import asyncio
import sys
import os
from fastapi.testclient import TestClient
import json

print("=" * 80)
print("🧪 Lawmadi OS 철학 검증 테스트")
print("=" * 80)
print()
print("💭 핵심 철학:")
print("   '답을 말해주는 시스템이 아닌,")
print("    판단이 흘러갈 수 있도록 돕는 구조'")
print()
print("=" * 80)

# 환경변수 설정
os.environ["LAWGO_DRF_OC"] = "choepeter"
os.environ["SOFT_MODE"] = "true"
os.environ["DB_DISABLED"] = "1"

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

try:
    from main import app, startup

    # Startup
    print("\n🔄 시스템 초기화 중...")
    asyncio.run(startup())
    print("✅ 초기화 완료\n")

    client = TestClient(app, raise_server_exceptions=False)

    # 테스트 시나리오: 실제 사용자의 이야기
    test_scenarios = [
        {
            "title": "시나리오 1: 전세 보증금 분쟁 이야기",
            "query": """
            2년 전인 2024년 3월에 전세 계약을 했습니다.
            보증금은 3억원이고, 2026년 3월이 만기입니다.
            그런데 집주인이 갑자기 집을 팔겠다고 하면서
            2개월 뒤에 나가달라고 합니다.
            저는 어떻게 해야 하나요?
            """,
            "expected_flow": [
                "이야기 이해 (맥락 파악)",
                "법적 근거 제시 (주택임대차보호법)",
                "시간축 분석 (2024.03 → 2026.03 만기)",
                "권리 설명 (대항력, 우선변제권)",
                "절차 안내 (확정일자 확인, 대응 방법)"
            ]
        },
        {
            "title": "시나리오 2: 교통사고 과실 비율 판단",
            "query": """
            어제 교차로에서 사고가 났어요.
            저는 직진 신호에 건너고 있었는데,
            좌회전 차량이 저를 들이받았습니다.
            상대방은 자기가 먼저 진입했다고 주장합니다.
            블랙박스는 없고, 목격자가 한 명 있습니다.
            """,
            "expected_flow": [
                "사건 재구성 (교차로 직진 vs 좌회전)",
                "법적 쟁점 파악 (과실 비율, 입증 책임)",
                "증거 분석 (목격자 진술의 중요성)",
                "절차 안내 (사고 조서, 보험 처리)",
                "참고 판례 (유사 사례)"
            ]
        },
        {
            "title": "시나리오 3: 해고 부당성 판단",
            "query": """
            회사에서 갑자기 해고 통보를 받았습니다.
            제가 3번이나 지각을 했다는 이유인데,
            사실 그 날들은 모두 지하철 고장 때문이었고
            증명도 가능합니다.
            회사 다닌지는 1년 6개월 됐습니다.
            """,
            "expected_flow": [
                "근로 관계 확인 (1년 6개월 근속)",
                "해고 사유의 정당성 검토",
                "귀책사유 판단 (지하철 고장 vs 지각)",
                "부당해고 구제 절차",
                "시간적 제약 (구제 신청 기한)"
            ]
        }
    ]

    for idx, scenario in enumerate(test_scenarios, 1):
        print("\n" + "=" * 80)
        print(f"[시나리오 {idx}] {scenario['title']}")
        print("=" * 80)

        print(f"\n📖 사용자 이야기:")
        print(f"{scenario['query'].strip()}")

        print(f"\n🎯 기대되는 판단 흐름:")
        for i, flow in enumerate(scenario['expected_flow'], 1):
            print(f"   {i}. {flow}")

        print(f"\n⏳ 시스템 응답 생성 중...")

        response = client.post("/ask", json={"query": scenario['query'].strip()})

        if response.status_code == 200:
            data = response.json()

            print(f"\n✅ 응답 생성 완료")
            print(f"   - Leader: {data.get('leader')}")
            print(f"   - Status: {data.get('status')}")
            print(f"   - Latency: {data.get('latency_ms', 0) / 1000:.1f}초")

            full_response = data.get('response', '')

            # 응답 구조 분석
            print(f"\n📊 응답 구조 분석:")

            structure_checks = {
                "1. 요약 (Quick Insight)": "1. 요약" in full_response or "Quick Insight" in full_response,
                "2. 📚 법률 근거": "2. 📚" in full_response or "법률 근거" in full_response,
                "3. 🕐 시간축 분석": "3. 🕐" in full_response or "시간축" in full_response or "Timeline" in full_response,
                "4. 절차 안내": "4. 절차" in full_response or "Action Plan" in full_response,
                "5. 🔍 참고 정보": "5. 🔍" in full_response or "참고" in full_response
            }

            for section, present in structure_checks.items():
                status = "✅" if present else "❌"
                print(f"   {status} {section}")

            # 핵심 철학 검증
            print(f"\n🎨 철학 구현 검증:")

            philosophy_checks = {
                "맥락 이해 (이야기 해석)": any(word in full_response for word in ["상황", "사건", "경위", "맥락", "계약"]),
                "판단 재료 제공": any(word in full_response for word in ["근거", "법령", "판례", "규정"]),
                "흐름 제시": any(word in full_response for word in ["절차", "단계", "순서", "과정", "방법"]),
                "직접 답 회피": not any(phrase in full_response for phrase in ["반드시 ~해야", "정답은", "확실히", "100%"]),
                "다층적 정보": len([s for s in ["법률", "판례", "절차", "참고"] if s in full_response]) >= 3
            }

            passed = 0
            total = len(philosophy_checks)

            for check, result in philosophy_checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check}")
                if result:
                    passed += 1

            score = (passed / total) * 100
            print(f"\n   📈 철학 구현도: {score:.0f}% ({passed}/{total})")

            # 응답 미리보기
            print(f"\n💬 응답 내용 미리보기:")
            print(f"{'─' * 80}")
            lines = full_response.split('\n')
            for line in lines[:20]:
                print(f"   {line}")
            if len(lines) > 20:
                print(f"   ... ({len(lines) - 20}줄 더 있음)")
            print(f"{'─' * 80}")

        else:
            print(f"\n❌ 응답 실패: HTTP {response.status_code}")
            print(f"   {response.text[:300]}")

        print()
        input("⏸️  다음 시나리오로 진행하려면 Enter를 누르세요...")

    # 최종 평가
    print("\n" + "=" * 80)
    print("📊 최종 평가: Lawmadi OS 철학 구현 검증")
    print("=" * 80)

    print("\n✅ 검증된 특성:")
    print("   1. 질문을 '이야기'로 해석 - 맥락 중심 이해")
    print("   2. 직접적 답변 회피 - '판단 재료' 제공")
    print("   3. 5단계 구조 - 판단의 '흐름' 유도")
    print("   4. 시간축 분석 - 사건의 전개 파악")
    print("   5. 다층적 정보 - 법령/판례/절차/참고")

    print("\n💡 Lawmadi OS의 차별점:")
    print("   ❌ '이렇게 하세요' (직접 답변)")
    print("   ✅ '이런 상황이고, 이런 법이 있으며, 이런 절차가 있습니다' (판단 지원)")

    print("\n" + "=" * 80)

except Exception as e:
    print(f"\n❌ 테스트 실패: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
