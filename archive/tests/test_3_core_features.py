#!/usr/bin/env python3
"""
3가지 핵심 기능 통합 테스트
1. 법령 검색
2. 판례 검색
3. 사건 절차 및 해결 방법 문의
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"

def print_header(title, emoji="📋"):
    print("\n" + "=" * 100)
    print(f"{emoji} {title}")
    print("=" * 100)

def print_result(test_name, success, details=""):
    status = "✅ 성공" if success else "❌ 실패"
    print(f"\n{status} - {test_name}")
    if details:
        print(f"   {details}")

def test_health():
    """헬스 체크"""
    print_header("0. 서버 헬스 체크", "🏥")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 서버 정상 작동")
            print(f"   버전: {data.get('version', 'N/A')}")
            print(f"   상태: {data.get('status', 'N/A')}")
            return True
        else:
            print(f"❌ 헬스 체크 실패: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        return False

def test_1_law_search():
    """테스트 1: 법령 검색"""
    print_header("테스트 1: 법령 검색", "📜")

    test_cases = [
        {
            "name": "민법 제1조 검색",
            "query": "민법 제1조",
            "expected_keywords": ["민법", "신의성실", "권리", "의무"]
        },
        {
            "name": "주택임대차보호법 검색",
            "query": "주택임대차보호법 대항력",
            "expected_keywords": ["임대차", "대항력", "전입신고", "주택"]
        },
        {
            "name": "근로기준법 검색",
            "query": "근로기준법 해고",
            "expected_keywords": ["근로", "해고", "정당한", "사유"]
        }
    ]

    results = []

    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}] {test_case['name']}")
        print(f"   질문: {test_case['query']}")

        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/ask",
                json={"query": test_case['query']},
                timeout=60
            )
            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                answer = data.get('response', '')
                leader = data.get('leader', 'Unknown')

                # 키워드 검증
                found_keywords = [kw for kw in test_case['expected_keywords'] if kw in answer]
                success = len(found_keywords) >= 2  # 최소 2개 키워드 포함

                print(f"   응답 시간: {elapsed:.1f}초")
                print(f"   담당 리더: {leader}")
                print(f"   찾은 키워드: {found_keywords}")
                print(f"   응답 길이: {len(answer)}자")

                if success:
                    print(f"   ✅ 법령 검색 성공")
                    # 응답 샘플 출력
                    sample = answer[:200].replace('\n', ' ')
                    print(f"   응답 샘플: {sample}...")
                else:
                    print(f"   ⚠️ 키워드 부족 (기대: {test_case['expected_keywords']})")

                results.append({
                    "test": test_case['name'],
                    "success": success,
                    "elapsed": elapsed,
                    "leader": leader
                })
            else:
                print(f"   ❌ HTTP {response.status_code}")
                results.append({"test": test_case['name'], "success": False})

        except Exception as e:
            print(f"   ❌ 오류: {e}")
            results.append({"test": test_case['name'], "success": False})

        time.sleep(2)  # API 부하 방지

    # 결과 요약
    success_count = sum(1 for r in results if r.get('success'))
    print(f"\n{'─' * 100}")
    print(f"테스트 1 결과: {success_count}/{len(test_cases)} 성공")
    return results

def test_2_precedent_search():
    """테스트 2: 판례 검색"""
    print_header("테스트 2: 판례 검색", "⚖️")

    test_cases = [
        {
            "name": "임대차 판례 검색",
            "query": "임대차 보증금 반환 관련 판례 알려줘",
            "expected_keywords": ["대법원", "판결", "보증금", "반환"]
        },
        {
            "name": "교통사고 판례 검색",
            "query": "음주운전 교통사고 판례",
            "expected_keywords": ["교통사고", "음주", "판례", "형"]
        }
    ]

    results = []

    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}] {test_case['name']}")
        print(f"   질문: {test_case['query']}")

        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/ask",
                json={"query": test_case['query']},
                timeout=60
            )
            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                answer = data.get('response', '')
                leader = data.get('leader', 'Unknown')
                swarm_mode = data.get('swarm_mode', False)

                # 판례 관련 키워드 검증
                found_keywords = [kw for kw in test_case['expected_keywords'] if kw in answer]
                has_precedent = any(word in answer for word in ['판례', '판결', '대법원', '고등법원'])
                success = len(found_keywords) >= 2 and has_precedent

                print(f"   응답 시간: {elapsed:.1f}초")
                print(f"   담당 리더: {leader}")
                print(f"   Swarm 모드: {swarm_mode}")
                print(f"   판례 언급: {'✅' if has_precedent else '❌'}")
                print(f"   찾은 키워드: {found_keywords}")

                if success:
                    print(f"   ✅ 판례 검색 성공")
                    sample = answer[:200].replace('\n', ' ')
                    print(f"   응답 샘플: {sample}...")
                else:
                    print(f"   ⚠️ 판례 정보 부족")

                results.append({
                    "test": test_case['name'],
                    "success": success,
                    "elapsed": elapsed,
                    "leader": leader,
                    "swarm_mode": swarm_mode
                })
            else:
                print(f"   ❌ HTTP {response.status_code}")
                results.append({"test": test_case['name'], "success": False})

        except Exception as e:
            print(f"   ❌ 오류: {e}")
            results.append({"test": test_case['name'], "success": False})

        time.sleep(2)

    success_count = sum(1 for r in results if r.get('success'))
    print(f"\n{'─' * 100}")
    print(f"테스트 2 결과: {success_count}/{len(test_cases)} 성공")
    return results

def test_3_case_procedure():
    """테스트 3: 사건 절차 및 해결 방법 문의"""
    print_header("테스트 3: 사건 절차 및 해결 방법 문의", "🔍")

    test_cases = [
        {
            "name": "임대차 분쟁 절차",
            "query": "전세금을 안 돌려줘요. 어떻게 해야 하나요?",
            "expected_elements": {
                "상황정리": ["보증금", "임대차", "반환"],
                "법률근거": ["주택임대차보호법", "민법", "법"],
                "행동순서": ["내용증명", "신청", "소송", "절차", "단계"]
            }
        },
        {
            "name": "교통사고 처리 절차",
            "query": "교통사고를 당했는데 상대방이 보험 처리를 안 하려고 해요. 어떻게 해야 하나요?",
            "expected_elements": {
                "상황정리": ["교통사고", "피해", "보험"],
                "법률근거": ["자동차손해배상보장법", "민법", "법"],
                "행동순서": ["경찰", "보험", "신고", "청구", "절차"]
            }
        },
        {
            "name": "부당해고 대응",
            "query": "회사에서 갑자기 해고당했어요. 정당한 사유도 없이요. 어떻게 대응해야 하나요?",
            "expected_elements": {
                "상황정리": ["해고", "부당", "근로"],
                "법률근거": ["근로기준법", "법"],
                "행동순서": ["노동청", "신청", "구제", "절차"]
            }
        }
    ]

    results = []

    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}] {test_case['name']}")
        print(f"   질문: {test_case['query']}")

        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/ask",
                json={"query": test_case['query']},
                timeout=90  # 복잡한 질문이므로 타임아웃 증가
            )
            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                answer = data.get('response', '')
                leader = data.get('leader', 'Unknown')
                swarm_mode = data.get('swarm_mode', False)

                # 3가지 핵심 요소 검증
                scores = {}
                for element_name, keywords in test_case['expected_elements'].items():
                    found = sum(1 for kw in keywords if kw in answer)
                    scores[element_name] = found >= 1  # 최소 1개 이상

                success = sum(scores.values()) >= 2  # 3가지 중 최소 2가지 포함

                print(f"   응답 시간: {elapsed:.1f}초")
                print(f"   담당 리더: {leader}")
                print(f"   Swarm 모드: {swarm_mode}")
                print(f"   핵심 요소 검증:")
                print(f"      상황정리: {'✅' if scores['상황정리'] else '❌'}")
                print(f"      법률근거: {'✅' if scores['법률근거'] else '❌'}")
                print(f"      행동순서: {'✅' if scores['행동순서'] else '❌'}")

                if success:
                    print(f"   ✅ 사건 절차 안내 성공")
                    # 5단계 구조 확인
                    has_structure = any(marker in answer for marker in ['###', '##', '1.', '2.', '3.'])
                    if has_structure:
                        print(f"   ✅ 구조화된 응답 제공")

                    sample = answer[:300].replace('\n', ' ')
                    print(f"   응답 샘플: {sample}...")
                else:
                    print(f"   ⚠️ 필수 요소 부족")

                results.append({
                    "test": test_case['name'],
                    "success": success,
                    "elapsed": elapsed,
                    "leader": leader,
                    "swarm_mode": swarm_mode,
                    "scores": scores
                })
            else:
                print(f"   ❌ HTTP {response.status_code}")
                results.append({"test": test_case['name'], "success": False})

        except Exception as e:
            print(f"   ❌ 오류: {e}")
            results.append({"test": test_case['name'], "success": False})

        time.sleep(2)

    success_count = sum(1 for r in results if r.get('success'))
    print(f"\n{'─' * 100}")
    print(f"테스트 3 결과: {success_count}/{len(test_cases)} 성공")
    return results

def generate_report(results_1, results_2, results_3):
    """종합 리포트 생성"""
    print_header("📊 종합 테스트 결과", "🎯")

    all_results = results_1 + results_2 + results_3
    total_tests = len(all_results)
    total_success = sum(1 for r in all_results if r.get('success'))
    success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0

    print(f"\n총 테스트: {total_tests}건")
    print(f"성공: {total_success}건")
    print(f"실패: {total_tests - total_success}건")
    print(f"성공률: {success_rate:.1f}%")

    print(f"\n{'─' * 100}")
    print(f"세부 결과:")
    print(f"  테스트 1 (법령 검색): {sum(1 for r in results_1 if r.get('success'))}/{len(results_1)} 성공")
    print(f"  테스트 2 (판례 검색): {sum(1 for r in results_2 if r.get('success'))}/{len(results_2)} 성공")
    print(f"  테스트 3 (사건 절차): {sum(1 for r in results_3 if r.get('success'))}/{len(results_3)} 성공")

    # 평균 응답 시간
    elapsed_times = [r.get('elapsed', 0) for r in all_results if r.get('elapsed')]
    if elapsed_times:
        avg_elapsed = sum(elapsed_times) / len(elapsed_times)
        print(f"\n평균 응답 시간: {avg_elapsed:.1f}초")
        print(f"최소 응답 시간: {min(elapsed_times):.1f}초")
        print(f"최대 응답 시간: {max(elapsed_times):.1f}초")

    # Swarm 모드 활성화율
    swarm_results = [r for r in all_results if 'swarm_mode' in r]
    if swarm_results:
        swarm_count = sum(1 for r in swarm_results if r.get('swarm_mode'))
        swarm_rate = (swarm_count / len(swarm_results) * 100) if swarm_results else 0
        print(f"\nSwarm 모드 활성화율: {swarm_rate:.1f}% ({swarm_count}/{len(swarm_results)})")

    print(f"\n{'─' * 100}")

    if success_rate >= 80:
        print("🎉 전체 평가: 우수 (80% 이상)")
    elif success_rate >= 60:
        print("✅ 전체 평가: 양호 (60% 이상)")
    elif success_rate >= 40:
        print("⚠️ 전체 평가: 보통 (40% 이상)")
    else:
        print("❌ 전체 평가: 개선 필요 (40% 미만)")

def main():
    print("\n" + "🧪" * 50)
    print("   Lawmadi OS 핵심 기능 통합 테스트")
    print(f"   시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🧪" * 50)

    # 헬스 체크
    if not test_health():
        print("\n❌ 서버가 실행되지 않았습니다. 테스트를 중단합니다.")
        return

    # 3가지 테스트 실행
    results_1 = test_1_law_search()
    results_2 = test_2_precedent_search()
    results_3 = test_3_case_procedure()

    # 종합 리포트
    generate_report(results_1, results_2, results_3)

    print("\n" + "=" * 100)
    print(f"✅ 테스트 완료 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100 + "\n")

if __name__ == "__main__":
    main()
