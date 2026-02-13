#!/usr/bin/env python3
"""
응답 검증 시스템 테스트
Claude API를 사용한 SSOT 준수 검증
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines.response_verifier import get_verifier
from connectors import db_client_v2

def test_verifier_initialization():
    """검증기 초기화 테스트"""
    print("\n" + "="*70)
    print("1. 검증기 초기화 테스트")
    print("="*70)

    verifier = get_verifier()

    if verifier.enabled:
        print("✅ Claude API 연결 성공")
        print(f"   API Key: {verifier.api_key[:20]}...")
    else:
        print("⚠️ Claude API 비활성화 (ANTHROPIC_API_KEY 미설정)")

    return verifier.enabled


def test_verification_table():
    """DB 테이블 생성 테스트"""
    print("\n" + "="*70)
    print("2. DB 테이블 생성 테스트")
    print("="*70)

    try:
        db_client_v2.init_verification_table()
        print("✅ response_verification 테이블 생성 완료")
        return True
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False


def test_pass_case():
    """PASS 케이스: DRF API를 제대로 사용한 응답"""
    print("\n" + "="*70)
    print("3. PASS 케이스 테스트")
    print("="*70)

    verifier = get_verifier()
    if not verifier.enabled:
        print("⚠️ Claude API 비활성화로 테스트 스킵")
        return None

    user_query = "민법 제750조 손해배상 규정을 알려주세요"
    gemini_response = """
[법률 전문가 답변]

1. 요약 (Quick Insight):
민법 제750조는 불법행위에 대한 손해배상책임을 규정합니다.

2. 📚 법률 근거 (Verified Evidence):
**민법 제750조 (불법행위의 내용)**
고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는 그 손해를 배상할 책임이 있다.

출처: 국가법령정보센터(현행법령)

3. 🕐 시간축 분석:
시간 정보 부족으로 생략합니다.

4. 절차 안내:
불법행위 손해배상 청구 시 입증해야 할 요소:
- 가해자의 고의 또는 과실
- 위법행위의 존재
- 손해 발생
- 인과관계

5. 🔍 참고 정보:
민법상 불법행위 손해배상은 3년의 소멸시효가 있습니다.
"""

    tools_used = [
        {"name": "search_law_drf", "args": {"query": "민법 제750조"}}
    ]

    tool_results = [
        {
            "result": "FOUND",
            "source": "국가법령정보센터(현행법령)",
            "content": "민법 제750조 (불법행위의 내용) 고의 또는 과실로 인한..."
        }
    ]

    result = verifier.verify_response(
        user_query=user_query,
        gemini_response=gemini_response,
        tools_used=tools_used,
        tool_results=tool_results
    )

    print(f"검증 결과: {result['result']}")
    print(f"SSOT 점수: {result['ssot_compliance_score']}/100")
    print(f"피드백: {result['feedback']}")
    print(f"이슈: {result['issues']}")

    return result['result'] == "PASS"


def test_fail_case():
    """FAIL 케이스: DRF API 없이 환각한 응답"""
    print("\n" + "="*70)
    print("4. FAIL 케이스 테스트")
    print("="*70)

    verifier = get_verifier()
    if not verifier.enabled:
        print("⚠️ Claude API 비활성화로 테스트 스킵")
        return None

    user_query = "민법 제999조에 대해 알려주세요"
    gemini_response = """
[법률 전문가 답변]

1. 요약 (Quick Insight):
민법 제999조는 계약 해지 시 손해배상 규정입니다.

2. 📚 법률 근거 (Verified Evidence):
민법 제999조에 따르면 계약 당사자는 일방적으로 계약을 해지할 수 있으며...

3. 절차 안내:
계약 해지 통지서를 내용증명으로 발송하세요.
"""

    # Tool을 호출하지 않음!
    tools_used = []
    tool_results = []

    result = verifier.verify_response(
        user_query=user_query,
        gemini_response=gemini_response,
        tools_used=tools_used,
        tool_results=tool_results
    )

    print(f"검증 결과: {result['result']}")
    print(f"SSOT 점수: {result['ssot_compliance_score']}/100")
    print(f"피드백: {result['feedback']}")
    print(f"이슈: {result['issues']}")

    return result['result'] == "FAIL"


def test_warning_case():
    """WARNING 케이스: Tool은 사용했지만 일부 불명확"""
    print("\n" + "="*70)
    print("5. WARNING 케이스 테스트")
    print("="*70)

    verifier = get_verifier()
    if not verifier.enabled:
        print("⚠️ Claude API 비활성화로 테스트 스킵")
        return None

    user_query = "임대차보호법에 대해 알려주세요"
    gemini_response = """
[법률 전문가 답변]

1. 요약:
주택임대차보호법은 임차인을 보호합니다.

2. 법률 근거:
주택임대차보호법 제3조에 따르면 대항력이 발생하며, 일반적으로 전세권자보다 우선합니다.

출처: 국가법령정보센터

3. 절차 안내:
전입신고와 확정일자를 받으세요.
"""

    tools_used = [
        {"name": "search_law_drf", "args": {"query": "주택임대차보호법"}}
    ]

    tool_results = [
        {
            "result": "FOUND",
            "source": "국가법령정보센터(현행법령)",
            "content": "주택임대차보호법 제3조 (대항력 등) ..."
        }
    ]

    result = verifier.verify_response(
        user_query=user_query,
        gemini_response=gemini_response,
        tools_used=tools_used,
        tool_results=tool_results
    )

    print(f"검증 결과: {result['result']}")
    print(f"SSOT 점수: {result['ssot_compliance_score']}/100")
    print(f"피드백: {result['feedback']}")
    print(f"이슈: {result['issues']}")

    return result['result'] in ["WARNING", "PASS"]


def test_db_save():
    """DB 저장 테스트"""
    print("\n" + "="*70)
    print("6. DB 저장 테스트")
    print("="*70)

    try:
        save_result = db_client_v2.save_verification_result(
            session_id="test-session-001",
            user_query="테스트 질문",
            gemini_response="테스트 응답",
            tools_used=[{"name": "search_law_drf", "args": {}}],
            tool_results=[{"result": "FOUND"}],
            verification_result="PASS",
            ssot_compliance_score=95,
            issues_found=[],
            claude_feedback="정상 응답"
        )

        if save_result.get("ok"):
            print(f"✅ 검증 결과 저장 성공 (ID: {save_result.get('verification_id')})")
            return True
        else:
            print(f"❌ 저장 실패: {save_result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ DB 저장 실패: {e}")
        return False


def test_stats():
    """통계 조회 테스트"""
    print("\n" + "="*70)
    print("7. 통계 조회 테스트")
    print("="*70)

    try:
        stats = db_client_v2.get_verification_statistics(days=7)

        if stats.get("ok"):
            print(f"✅ 통계 조회 성공")
            print(f"   기간: 최근 {stats.get('period_days')}일")
            print(f"   총 검증: {stats.get('total_verifications')}건")
            print(f"   PASS: {stats.get('pass_count')}건")
            print(f"   WARNING: {stats.get('warning_count')}건")
            print(f"   FAIL: {stats.get('fail_count')}건")
            print(f"   평균 점수: {stats.get('avg_score')}/100")
            print(f"   통과율: {stats.get('pass_rate')}%")
            return True
        else:
            print(f"❌ 통계 조회 실패: {stats.get('error')}")
            return False

    except Exception as e:
        print(f"❌ 통계 조회 실패: {e}")
        return False


def main():
    """메인 테스트 실행"""
    print("\n" + "🛡️ 응답 검증 시스템 통합 테스트")
    print("="*70)

    results = []

    # 1. 초기화 테스트
    results.append(("초기화", test_verifier_initialization()))

    # 2. DB 테이블 생성
    results.append(("DB 테이블", test_verification_table()))

    # 3-5. 검증 케이스
    results.append(("PASS 케이스", test_pass_case()))
    results.append(("FAIL 케이스", test_fail_case()))
    results.append(("WARNING 케이스", test_warning_case()))

    # 6-7. DB 저장 및 통계
    results.append(("DB 저장", test_db_save()))
    results.append(("통계 조회", test_stats()))

    # 최종 결과
    print("\n" + "="*70)
    print("📊 최종 결과")
    print("="*70)

    success_count = 0
    total_count = 0

    for name, result in results:
        if result is None:
            status = "⏭️ SKIP"
        elif result:
            status = "✅ PASS"
            success_count += 1
            total_count += 1
        else:
            status = "❌ FAIL"
            total_count += 1

        print(f"{status} {name}")

    if total_count > 0:
        pass_rate = (success_count / total_count) * 100
        print(f"\n성공률: {success_count}/{total_count} ({pass_rate:.1f}%)")

        if success_count == total_count:
            print("\n🎉 모든 테스트 통과!")
            print("✅ 응답 검증 시스템 정상 작동")
        else:
            print("\n⚠️ 일부 테스트 실패")
    else:
        print("\n⚠️ 실행 가능한 테스트 없음 (API 키 확인 필요)")

    print()


if __name__ == "__main__":
    main()
