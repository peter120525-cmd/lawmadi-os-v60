#!/usr/bin/env python3
"""
Lawmadi OS 핵심 3대 기능 검증:
1. 상황 정리
2. 관련 법 연결
3. 가능한 행동을 시간의 순서로 배열
"""

import asyncio
import sys
import os
from fastapi.testclient import TestClient
import re

print("=" * 80)
print("🧪 Lawmadi OS 핵심 3대 기능 검증")
print("=" * 80)
print()
print("1️⃣  상황이 정리되고")
print("2️⃣  관련 법이 연결되고")
print("3️⃣  가능한 행동이 시간의 순서로 배열됩니다")
print()
print("=" * 80)

os.environ["LAWGO_DRF_OC"] = "choepeter"
os.environ["SOFT_MODE"] = "true"
os.environ["DB_DISABLED"] = "1"

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

try:
    from main import app, startup

    print("\n🔄 시스템 초기화...")
    asyncio.run(startup())
    print("✅ 초기화 완료\n")

    client = TestClient(app, raise_server_exceptions=False)

    # 복잡한 실제 사례: 다층적 법률 문제
    test_case = {
        "title": "복합 법률 사안: 임대차 + 명의신탁 + 경매",
        "query": """
        아버지께서 2020년 1월에 제 명의로 아파트를 구입하셨습니다.
        실제 돈은 아버지가 내셨고, 저는 그냥 명의만 빌려드린 것입니다.

        그런데 2022년 3월에 제가 그 아파트를 임대를 주었고,
        세입자가 2024년 3월까지 2년 계약으로 보증금 2억을 주고 들어왔습니다.

        문제는 제가 2023년 6월에 사업 실패로 빚이 생겼고,
        채권자가 2024년 1월에 그 아파트에 대해 가압류를 걸었습니다.

        지금 2026년 2월인데, 경매가 진행 중이라고 연락이 왔습니다.
        세입자는 자기 보증금을 돌려달라고 하고,
        아버지는 자기 돈으로 산 집이라며 명의신탁 반환을 요구하시고,
        저는 빚 때문에 어떻게 해야 할지 모르겠습니다.
        """,
        "expected_features": {
            "상황정리": [
                "명의신탁 관계 (2020.01)",
                "임대차 계약 (2022.03~2024.03)",
                "채무 발생 (2023.06)",
                "가압류 (2024.01)",
                "경매 진행 (2026.02 현재)",
                "다자간 이해관계 (아버지/명의자/세입자/채권자)"
            ],
            "법연결": [
                "부동산 실권리자명의 등기에 관한 법률",
                "주택임대차보호법",
                "민사집행법",
                "민법 (명의신탁, 임대차, 채권)",
                "우선변제권",
                "배당 순위"
            ],
            "시간순서": [
                "즉시: 경매 진행 상황 확인",
                "1주일: 배당요구 신청",
                "2주일: 확정일자/전입신고 확인",
                "경매기일 전: 이해관계인 회의",
                "배당기일: 배당 순위 확정",
                "사후: 명의신탁 해지/정산"
            ]
        }
    }

    print("\n" + "=" * 80)
    print(f"📋 테스트 사례: {test_case['title']}")
    print("=" * 80)

    print(f"\n📖 복합 사안:")
    print(test_case['query'].strip())

    print(f"\n⏳ 시스템 분석 중...")

    response = client.post("/ask", json={"query": test_case['query'].strip()})

    if response.status_code != 200:
        print(f"❌ 응답 실패: {response.status_code}")
        print(response.text[:500])
        sys.exit(1)

    data = response.json()
    full_response = data.get('response', '')

    print(f"\n✅ 응답 생성 완료")
    print(f"   - Leader: {data.get('leader')}")
    print(f"   - Latency: {data.get('latency_ms', 0) / 1000:.1f}초")

    # ========================================
    # 1️⃣ 상황 정리 검증
    # ========================================
    print("\n" + "=" * 80)
    print("1️⃣  상황 정리 검증")
    print("=" * 80)

    situation_keywords = test_case['expected_features']['상황정리']
    found_situations = []

    for keyword in situation_keywords:
        # 키워드의 핵심 부분 추출
        core = keyword.split('(')[0].strip() if '(' in keyword else keyword
        if core in full_response or any(word in full_response for word in core.split()):
            found_situations.append(keyword)

    print(f"\n📊 상황 요소 감지:")
    for situation in situation_keywords:
        status = "✅" if situation in ' '.join(found_situations) else "❌"
        print(f"   {status} {situation}")

    situation_score = (len(found_situations) / len(situation_keywords)) * 100
    print(f"\n   📈 상황 정리도: {situation_score:.0f}% ({len(found_situations)}/{len(situation_keywords)})")

    # 상황 정리 구조 분석
    print(f"\n🔍 상황 정리 구조 분석:")

    structure_patterns = {
        "시간순 나열": r'20\d{2}년?\s*\d{1,2}월',
        "이해관계자 식별": r'(아버지|세입자|채권자|명의자|임차인)',
        "법률관계 분류": r'(명의신탁|임대차|채무|가압류|경매)',
        "금액/수치 정리": r'\d+억|보증금|채무'
    }

    for pattern_name, pattern in structure_patterns.items():
        matches = re.findall(pattern, full_response)
        status = "✅" if matches else "❌"
        count = len(set(matches)) if matches else 0
        print(f"   {status} {pattern_name}: {count}개 감지")

    # ========================================
    # 2️⃣ 관련 법 연결 검증
    # ========================================
    print("\n" + "=" * 80)
    print("2️⃣  관련 법 연결 검증")
    print("=" * 80)

    law_keywords = test_case['expected_features']['법연결']
    found_laws = []

    for law in law_keywords:
        if law in full_response:
            found_laws.append(law)

    print(f"\n📚 법령 연결 현황:")
    for law in law_keywords:
        status = "✅" if law in found_laws else "❌"
        print(f"   {status} {law}")

    law_score = (len(found_laws) / len(law_keywords)) * 100
    print(f"\n   📈 법령 연결도: {law_score:.0f}% ({len(found_laws)}/{len(law_keywords)})")

    # 법 연결 구조 분석
    print(f"\n🔍 법 연결 구조 분석:")

    connection_patterns = {
        "법령 조항 명시": r'제\s*\d+조',
        "법률 효과 설명": r'(권리|의무|효력|요건)',
        "상황-법 매핑": r'경우|때|따라|의하여',
        "DRF 검증 근거": r'(국가법령|법제처|법률|법령)'
    }

    for pattern_name, pattern in connection_patterns.items():
        matches = re.findall(pattern, full_response)
        status = "✅" if matches else "❌"
        count = len(matches) if matches else 0
        print(f"   {status} {pattern_name}: {count}개")

    # ========================================
    # 3️⃣ 시간 순서 배열 검증
    # ========================================
    print("\n" + "=" * 80)
    print("3️⃣  시간 순서 배열 검증")
    print("=" * 80)

    timeline_keywords = test_case['expected_features']['시간순서']
    found_timeline = []

    for item in timeline_keywords:
        core = item.split(':')[1].strip() if ':' in item else item
        if any(word in full_response for word in core.split()):
            found_timeline.append(item)

    print(f"\n🕐 시간 순서 요소:")
    for item in timeline_keywords:
        status = "✅" if item in ' '.join(found_timeline) else "⚠️"
        print(f"   {status} {item}")

    timeline_score = (len(found_timeline) / len(timeline_keywords)) * 100
    print(f"\n   📈 시간 배열도: {timeline_score:.0f}% ({len(found_timeline)}/{len(timeline_keywords)})")

    # 시간 순서 구조 분석
    print(f"\n🔍 시간 배열 구조 분석:")

    timeline_patterns = {
        "절대 시간 표현": r'20\d{2}[년.-]\d{1,2}[월.-]\d{1,2}',
        "상대 시간 표현": r'(즉시|먼저|다음|이후|전|후|내)',
        "순서 표시": r'(1\.|2\.|3\.|①|②|③|첫째|둘째)',
        "기한 명시": r'(일\s*이내|개월\s*이내|까지|기한)',
        "단계 구분": r'(단계|절차|과정|순서)'
    }

    timeline_detected = 0
    for pattern_name, pattern in timeline_patterns.items():
        matches = re.findall(pattern, full_response)
        status = "✅" if matches else "❌"
        count = len(matches) if matches else 0
        print(f"   {status} {pattern_name}: {count}개")
        if matches:
            timeline_detected += 1

    # ========================================
    # 통합 검증
    # ========================================
    print("\n" + "=" * 80)
    print("📊 통합 기능 검증 결과")
    print("=" * 80)

    total_score = (situation_score + law_score + timeline_score) / 3

    print(f"\n📈 기능별 점수:")
    print(f"   1️⃣  상황 정리: {situation_score:.0f}%")
    print(f"   2️⃣  법 연결: {law_score:.0f}%")
    print(f"   3️⃣  시간 배열: {timeline_score:.0f}%")
    print(f"\n   🎯 종합 점수: {total_score:.0f}%")

    # 등급 판정
    if total_score >= 90:
        grade = "A+ (완벽 구현)"
        emoji = "🏆"
    elif total_score >= 80:
        grade = "A (우수)"
        emoji = "✅"
    elif total_score >= 70:
        grade = "B (양호)"
        emoji = "👍"
    else:
        grade = "C (개선 필요)"
        emoji = "⚠️"

    print(f"\n   {emoji} 평가: {grade}")

    # 응답 샘플 추출
    print("\n" + "=" * 80)
    print("💬 응답 내용 분석")
    print("=" * 80)

    # 섹션별 추출
    sections = {
        "요약": r'1\.\s*요약.*?(?=2\.|$)',
        "법률 근거": r'2\.\s*📚.*?(?=3\.|$)',
        "시간축": r'3\.\s*🕐.*?(?=4\.|$)',
        "절차": r'4\.\s*절차.*?(?=5\.|$)'
    }

    for section_name, pattern in sections.items():
        match = re.search(pattern, full_response, re.DOTALL)
        if match:
            content = match.group(0)
            lines = content.split('\n')[:10]  # 처음 10줄만
            print(f"\n📌 {section_name} 섹션 발췌:")
            for line in lines:
                if line.strip():
                    print(f"   {line.strip()[:80]}")

    # 최종 평가
    print("\n" + "=" * 80)
    print("🎯 최종 평가")
    print("=" * 80)

    evaluation = {
        "상황 정리": situation_score >= 70,
        "법 연결": law_score >= 70,
        "시간 배열": timeline_score >= 70,
        "통합 구현": total_score >= 80
    }

    print(f"\n✅ 핵심 기능 구현 여부:")
    for feature, passed in evaluation.items():
        status = "✅ 완료" if passed else "⚠️  보완 필요"
        print(f"   {status} {feature}")

    if all(evaluation.values()):
        print(f"\n🎉 Lawmadi OS의 3대 핵심 기능이 모두 구현되었습니다!")
    else:
        print(f"\n⚠️  일부 기능 보완이 필요합니다.")

    print("\n" + "=" * 80)

except Exception as e:
    print(f"\n❌ 테스트 실패: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
