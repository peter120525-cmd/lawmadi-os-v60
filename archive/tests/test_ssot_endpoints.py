#!/usr/bin/env python3
"""
SSOT Phase 1 엔드포인트 테스트
/ask 엔드포인트를 통한 Gemini Tool 자동 선택 검증
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_endpoint(test_name, query, expected_tool):
    """엔드포인트 테스트"""
    print(f"\n{'='*70}")
    print(f"테스트: {test_name}")
    print(f"쿼리: {query}")
    print(f"예상 Tool: {expected_tool}")
    print(f"{'='*70}")

    try:
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"query": query},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 응답 성공 (status: {response.status_code})")

            # 응답 구조 출력
            if "answer" in data:
                answer = data["answer"]
                print(f"\n응답 길이: {len(answer)} chars")
                print(f"응답 미리보기: {answer[:200]}...")

                # Tool 사용 여부 확인
                if expected_tool:
                    if expected_tool in answer or any(keyword in answer for keyword in ["행정규칙", "법령해석례", "헌재결정례", "판례", "법령"]):
                        print(f"✅ 예상 데이터 소스 확인됨")
                    else:
                        print(f"⚠️  예상 데이터 소스 확인 안 됨")
            else:
                print(f"⚠️  'answer' 키 없음: {list(data.keys())}")

            return True
        else:
            print(f"❌ HTTP 오류: {response.status_code}")
            print(f"응답: {response.text[:300]}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ 서버 연결 실패 - 서버가 실행 중인지 확인하세요")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

def main():
    print("🔍 SSOT Phase 1 엔드포인트 테스트 시작\n")
    print(f"서버 URL: {BASE_URL}")

    # Health check
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ 서버 연결 성공 (status: {response.status_code})\n")
    except:
        print("❌ 서버 연결 실패 - main.py를 먼저 실행하세요")
        print("   실행 방법: python main.py\n")
        return

    # 테스트 케이스
    tests = [
        ("SSOT #2: 행정규칙 자동 선택", "공무원 복무규정에서 연차휴가는 어떻게 규정되어 있나요?", "행정규칙"),
        ("SSOT #7: 법령해석례 자동 선택", "행정절차법 제21조의 해석례를 알려주세요", "법령해석례"),
        ("SSOT #6: 헌재결정례 자동 선택", "재산권 침해와 관련된 헌법재판소 결정례를 찾아주세요", "헌재결정례"),
    ]

    success_count = 0
    for test_name, query, expected_tool in tests:
        if test_endpoint(test_name, query, expected_tool):
            success_count += 1
        time.sleep(2)  # Rate limiting

    print(f"\n{'='*70}")
    print(f"엔드포인트 테스트 완료: {success_count}/{len(tests)} 성공")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
