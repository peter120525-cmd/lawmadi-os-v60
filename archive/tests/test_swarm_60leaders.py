#!/usr/bin/env python3
"""
Lawmadi OS 60 Leader Swarm 테스트

Chapter 3 검증:
- 여러 Leader가 동시에 문제 분석
- 각 전문 분야의 사고 방식 적용
- 결과 조합하여 최종 판단 흐름 구성
"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

print("=" * 80)
print("🐝 Lawmadi OS 60 Leader Swarm 검증")
print("=" * 80)
print()
print("Chapter 3: 60 Leader 구조 탄생")
print("- 역할 기반 설계")
print("- 판단 로직 분산")
print("- 여러 Leader 동시 분석")
print("- 결과 조합 → 최종 판단 흐름")
print()
print("=" * 80)

# 환경변수 설정
os.environ["LAWGO_DRF_OC"] = "choepeter"
os.environ["SOFT_MODE"] = "true"
os.environ["DB_DISABLED"] = "1"
os.environ["SWARM_ENABLED"] = "true"  # Swarm 활성화
os.environ["SWARM_MAX_LEADERS"] = "3"  # 최대 3명 리더
os.environ["USE_SWARM"] = "true"  # SwarmOrchestrator 사용

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

try:
    from main import app, startup

    # Startup
    print("\n🔄 시스템 초기화 중...")
    asyncio.run(startup())
    print("✅ 초기화 완료\n")

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Health check
    print("=" * 80)
    print("[1] Health Check")
    print("=" * 80)

    response = client.get("/health")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 시스템 상태: {data.get('status')}")

        diag = data.get('diagnostics', {})
        modules = diag.get('modules', {})

        print(f"\n🔧 핵심 모듈 상태:")
        for key, value in modules.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key}: {value}")

        # SwarmOrchestrator 확인
        if modules.get("swarm_orchestrator"):
            print(f"\n🐝 SwarmOrchestrator: 활성화됨")
        else:
            print(f"\n⚠️  SwarmOrchestrator: 비활성화됨")

    # 2. 복합 법률 사안 테스트 (Chapter 3 검증)
    print("\n" + "=" * 80)
    print("[2] 복합 법률 사안 테스트 (60 Leader Swarm)")
    print("=" * 80)

    # 이 사안은 여러 법률 영역이 교차함:
    # - 명의신탁 (L57: 상속·신탁)
    # - 임대차 (L08: 임대차)
    # - 경매 (L10: 민사집행, L12: 등기·경매)
    # - 손해배상/부당이득 (L01: 민사법, L06: 손해배상)

    complex_query = """
    아버지께서 2020년 1월에 제 명의로 아파트를 구입하셨습니다.
    실제 돈은 아버지가 내셨고, 저는 그냥 명의만 빌려드린 것입니다.

    그런데 2022년 3월에 제가 그 아파트를 임대를 주었고,
    세입자가 2024년 3월까지 2년 계약으로 보증금 2억을 주고 들어왔습니다.

    문제는 제가 2023년 6월에 사업 실패로 빚이 생겼고,
    채권자가 2024년 1월에 그 아파트에 대해 가압류를 걸었습니다.

    지금 2026년 2월인데, 경매가 진행 중이라고 연락이 왔습니다.
    """

    print(f"\n📖 복합 사안:")
    print(complex_query.strip())

    print(f"\n🎯 예상 관련 법률 영역:")
    print(f"   - 명의신탁 (L57: 상속·신탁 - 세움)")
    print(f"   - 임대차 (L08: 임대차 - 온유)")
    print(f"   - 민사집행 (L10: 민사집행 - 결휘)")
    print(f"   - 등기·경매 (L12: 등기·경매 - 아슬)")
    print(f"   - 민사법 (L01: 민사법 - 휘율)")

    print(f"\n⏳ Swarm 분석 시작...")

    response = client.post("/ask", json={"query": complex_query.strip()})

    if response.status_code == 200:
        data = response.json()

        print(f"\n✅ Swarm 분석 완료!")
        print(f"\n📊 분석 결과:")
        print(f"   - Leader: {data.get('leader')}")
        print(f"   - Swarm Mode: {data.get('swarm_mode', False)}")
        print(f"   - Status: {data.get('status')}")
        print(f"   - Latency: {data.get('latency_ms', 0) / 1000:.1f}초")

        full_response = data.get('response', '')

        # 응답 구조 검증
        print(f"\n🔍 응답 구조 분석:")

        structure_checks = {
            "5단계 구조": {
                "1. 요약": "1. 요약" in full_response or "Quick Insight" in full_response,
                "2. 법률 근거": "2. 📚" in full_response or "법률 근거" in full_response,
                "3. 시간축 분석": "3. 🕐" in full_response or "시간축" in full_response,
                "4. 절차 안내": "4. 절차" in full_response or "Action Plan" in full_response,
                "5. 참고 정보": "5. 🔍" in full_response or "참고" in full_response,
            },
            "법률 영역 탐지": {
                "명의신탁": "명의신탁" in full_response,
                "임대차": "임대차" in full_response or "전세" in full_response or "월세" in full_response,
                "경매": "경매" in full_response,
                "민사집행": "민사집행" in full_response or "배당" in full_response,
                "부동산": "부동산" in full_response,
            },
            "다중 관점 분석": {
                "복합 사안 언급": "복합" in full_response or "여러" in full_response or "다양한" in full_response,
                "전문 분야별": "분야" in full_response or "전문" in full_response,
                "종합 판단": "종합" in full_response or "통합" in full_response,
            }
        }

        for category, checks in structure_checks.items():
            print(f"\n   📌 {category}:")
            passed = 0
            total = len(checks)

            for item, result in checks.items():
                status = "✅" if result else "❌"
                print(f"      {status} {item}")
                if result:
                    passed += 1

            score = (passed / total) * 100
            print(f"      📈 {category} 점수: {score:.0f}% ({passed}/{total})")

        # 응답 미리보기
        print(f"\n💬 응답 내용 미리보기:")
        print(f"{'─' * 80}")
        lines = full_response.split('\n')
        for line in lines[:30]:
            if line.strip():
                print(f"   {line[:80]}")
        if len(lines) > 30:
            print(f"   ... ({len(lines) - 30}줄 더 있음)")
        print(f"{'─' * 80}")

        # 법 연결 품질 검증 (Chapter 3의 핵심 목표)
        print(f"\n🎯 Chapter 3 목표 검증:")

        expected_laws = [
            "부동산 실권리자명의 등기에 관한 법률",
            "주택임대차보호법",
            "민사집행법",
            "민법",
        ]

        laws_found = sum(1 for law in expected_laws if law in full_response)
        law_coverage = (laws_found / len(expected_laws)) * 100

        print(f"\n   📚 법령 연결 품질:")
        for law in expected_laws:
            found = law in full_response
            status = "✅" if found else "❌"
            print(f"      {status} {law}")

        print(f"\n   📈 법령 연결도: {law_coverage:.0f}% ({laws_found}/{len(expected_laws)})")

        # 최종 평가
        print(f"\n" + "=" * 80)
        print(f"🎯 Chapter 3 구현 평가")
        print(f"=" * 80)

        swarm_mode = data.get('swarm_mode', False)
        multi_leader = "," in data.get('leader', '')

        criteria = {
            "Swarm 모드 활성화": swarm_mode or multi_leader,
            "여러 법률 영역 탐지": laws_found >= 3,
            "5단계 구조 유지": structure_checks["5단계 구조"]["1. 요약"],
            "복합 사안 인식": structure_checks["다중 관점 분석"]["복합 사안 언급"],
        }

        print(f"\n✅ 구현 검증:")
        for criterion, passed in criteria.items():
            status = "✅" if passed else "⚠️ "
            print(f"   {status} {criterion}")

        all_passed = all(criteria.values())
        if all_passed:
            print(f"\n🎉 Chapter 3의 60 Leader 구조가 성공적으로 구현되었습니다!")
        else:
            print(f"\n⚠️  일부 기능이 보완이 필요합니다.")

        print(f"\n📈 예상 개선 효과:")
        print(f"   - 법 연결: 50% → {law_coverage:.0f}%")
        if law_coverage >= 75:
            print(f"   - 등급: C → B+ 또는 A")

    else:
        print(f"\n❌ 응답 실패: HTTP {response.status_code}")
        print(f"   {response.text[:500]}")

    print("\n" + "=" * 80)
    print("✅ 테스트 완료!")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ 테스트 실패: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
