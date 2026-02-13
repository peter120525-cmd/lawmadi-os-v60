#!/usr/bin/env python3
"""
실제 배포된 시스템 테스트
- Cloud Run 엔드포인트로 실제 질문 전송
"""
import requests
import json
import time

API_URL = "https://lawmadi-os-v50-938146962157.asia-northeast3.run.app/ask"

def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_question(title, question, expected_mode="단일 Leader 또는 Swarm"):
    """질문 테스트"""
    print_header(title)
    print(f"\n📝 질문: {question}\n")
    print("⏳ 분석 중...\n")

    start_time = time.time()

    try:
        response = requests.post(
            API_URL,
            json={"query": question},
            timeout=120
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()

            print("✅ 응답 성공!")
            print(f"\n📊 메타 정보:")
            print(f"   - Leader: {data.get('leader', 'Unknown')}")
            print(f"   - Status: {data.get('status', 'Unknown')}")
            print(f"   - Latency: {data.get('latency_ms', 0) / 1000:.1f}초 (실제: {elapsed:.1f}초)")
            print(f"   - Swarm Mode: {data.get('swarm_mode', False)}")
            print(f"   - Trace ID: {data.get('trace_id', 'N/A')}")

            # 응답 내용
            full_response = data.get('response', '')
            lines = full_response.split('\n')

            print(f"\n💬 응답 미리보기 (처음 30줄):")
            print("─" * 80)
            for i, line in enumerate(lines[:30], 1):
                if line.strip():
                    print(f"{i:3}. {line[:75]}")

            if len(lines) > 30:
                print(f"\n... (총 {len(lines)}줄 중 30줄만 표시)")

            print("─" * 80)

            # 5단계 구조 확인
            print(f"\n🔍 5단계 구조 검증:")
            stages = [
                "1. 요약 (Quick Insight)",
                "2. 📚 법률 근거",
                "3. 🕐 시간축 분석",
                "4. 절차 안내",
                "5. 🔍 참고 정보"
            ]

            for stage in stages:
                if stage in full_response:
                    print(f"   ✅ {stage}")
                else:
                    print(f"   ❌ {stage}")

            return True

        else:
            print(f"❌ 응답 실패: HTTP {response.status_code}")
            print(f"   {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"⏰ 타임아웃 (120초 초과)")
        print(f"   실제 경과 시간: {elapsed:.1f}초")
        return False

    except Exception as e:
        print(f"❌ 에러: {type(e).__name__}: {e}")
        return False

def main():
    print("\n" + "🧪" * 40)
    print("   실제 배포 시스템 테스트")
    print("🧪" * 40)

    # 테스트 1: 간단한 임대차 질문 (단일 Leader 예상)
    test_question(
        "테스트 1: 간단한 임대차 질문",
        "전세 계약이 만기인데 집주인이 보증금을 안 돌려줍니다. 어떻게 해야 하나요?"
    )

    time.sleep(2)

    # 테스트 2: 복합 법률 사안 (Swarm 모드 예상)
    test_question(
        "테스트 2: 복합 법률 사안 (Swarm 예상)",
        "아버지 명의로 아파트를 샀는데 제 이름으로 등기했습니다. 그런데 제 빚 때문에 경매가 진행 중이고, 전세 보증금도 돌려줘야 합니다."
    )

    time.sleep(2)

    # 테스트 3: C-Level 호출 (지유 CTO)
    test_question(
        "테스트 3: C-Level 호출 (지유 CTO)",
        "지유님, 법률 데이터베이스 시스템을 설계할 때 무결성을 어떻게 보장하나요?"
    )

    print("\n" + "=" * 80)
    print("✅ 테스트 완료!")
    print("=" * 80)

if __name__ == "__main__":
    main()
