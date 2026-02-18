#!/usr/bin/env python3
"""
Lawmadi OS — 100가지 실제 사용자 시뮬레이션
각 시나리오별 응답 라우팅, leader, specialty, 응답 품질 검증
"""

import requests
import json
import time
import sys
from datetime import datetime

API_URL = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/ask"
HEALTH_URL = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app/health"

# ═══════════════════════════════════════════════════════
# 100가지 시뮬레이션 시나리오
# ═══════════════════════════════════════════════════════
SCENARIOS = [
    # ── 카테고리 1: Low Signal (5개) ──
    {"id": 1, "query": "ㅎㅇ", "category": "low_signal", "expect_leader": "유나"},
    {"id": 2, "query": "테스트", "category": "low_signal", "expect_leader": "유나"},
    {"id": 3, "query": "hello", "category": "low_signal", "expect_leader": "유나"},
    {"id": 4, "query": "ㅋㅋ", "category": "low_signal", "expect_leader": "유나"},
    {"id": 5, "query": "hi", "category": "low_signal", "expect_leader": "유나"},

    # ── 카테고리 2: 도메인 미탐지 / 일반 질문 → 유나(CCO) (10개) ──
    {"id": 6, "query": "오늘 날씨가 어때?", "category": "general", "expect_leader": "유나"},
    {"id": 7, "query": "맛있는 파스타 레시피 알려줘", "category": "general", "expect_leader": "유나"},
    {"id": 8, "query": "좋은 아침이에요", "category": "general", "expect_leader": "유나"},
    {"id": 9, "query": "스트레스 받을 때 어떻게 해야 하나요?", "category": "general", "expect_leader": "유나"},
    {"id": 10, "query": "영어 공부 잘하는 방법이 뭐야?", "category": "general", "expect_leader": "유나"},
    {"id": 11, "query": "요즘 인기있는 드라마 추천해줘", "category": "general", "expect_leader": "유나"},
    {"id": 12, "query": "주말에 뭐 하면 좋을까?", "category": "general", "expect_leader": "유나"},
    {"id": 13, "query": "취업 면접 준비 어떻게 하나요?", "category": "general", "expect_leader": "유나"},
    {"id": 14, "query": "감사합니다 잘 이해했어요", "category": "general", "expect_leader": "유나"},
    {"id": 15, "query": "이 시스템은 어떤 서비스인가요?", "category": "general", "expect_leader": "유나"},

    # ── 카테고리 3: C-Level 이름 호출 (6개) ──
    {"id": 16, "query": "서연아 전세 분쟁 전략 알려줘", "category": "clevel_name", "expect_leader": "서연"},
    {"id": 17, "query": "지유야 이 시스템 보안은 안전해?", "category": "clevel_name", "expect_leader": "지유"},
    {"id": 18, "query": "유나야 법률 상담 어떻게 시작해?", "category": "clevel_name", "expect_leader": "유나"},
    {"id": 19, "query": "서연아 소송 전략 수립해줘", "category": "clevel_name", "expect_leader": "서연"},
    {"id": 20, "query": "지유야 AI 기반 법률 검색 정확도는?", "category": "clevel_name", "expect_leader": "지유"},
    {"id": 21, "query": "유나야 첫 상담이라 긴장되는데 도와줘", "category": "clevel_name", "expect_leader": "유나"},

    # ── 카테고리 4: 리더 이름 호출 (10개) ──
    {"id": 22, "query": "휘율아 계약서 검토 좀 해줘", "category": "leader_name", "expect_leader": "휘율"},
    {"id": 23, "query": "무결아 사기죄 성립 요건이 뭐야?", "category": "leader_name", "expect_leader": "무결"},
    {"id": 24, "query": "산들아 이혼 재산분할 어떻게 해?", "category": "leader_name", "expect_leader": "산들"},
    {"id": 25, "query": "담우야 부당해고 구제 방법 알려줘", "category": "leader_name", "expect_leader": "담우"},
    {"id": 26, "query": "온유야 전세 보증금 못 받으면?", "category": "leader_name", "expect_leader": "온유"},
    {"id": 27, "query": "찬솔아 양도소득세 계산 해줘", "category": "leader_name", "expect_leader": "찬솔"},
    {"id": 28, "query": "로운아 행정처분 취소 소송 방법", "category": "leader_name", "expect_leader": "로운"},
    {"id": 29, "query": "한빛아 AI 윤리 가이드라인 설명해줘", "category": "leader_name", "expect_leader": "한빛"},
    {"id": 30, "query": "세움아 유언장 작성 방법 알려줘", "category": "leader_name", "expect_leader": "세움"},
    {"id": 31, "query": "보늬야 부동산 매매 계약 주의사항", "category": "leader_name", "expect_leader": "보늬"},

    # ── 카테고리 5: 민사법 (L01) (5개) ──
    {"id": 32, "query": "친구에게 빌려준 돈 500만원을 안 갚아요. 차용증은 없는데 카톡 대화만 있어요.", "category": "civil", "expect_leader": None},
    {"id": 33, "query": "계약 해지 통보를 받았는데 위약금을 물어야 하나요?", "category": "civil", "expect_leader": None},
    {"id": 34, "query": "손해배상 청구 소멸시효는 얼마인가요?", "category": "civil", "expect_leader": None},
    {"id": 35, "query": "부당이득 반환 청구 소송 절차를 알려주세요", "category": "civil", "expect_leader": None},
    {"id": 36, "query": "민사소송 비용은 얼마나 드나요?", "category": "civil", "expect_leader": None},

    # ── 카테고리 6: 부동산법 (L02) (5개) ──
    {"id": 37, "query": "아파트 등기부등본 확인할 때 뭘 봐야 해요?", "category": "real_estate", "expect_leader": None},
    {"id": 38, "query": "부동산 매매 계약 후 잔금일에 매도인이 안 나타나면?", "category": "real_estate", "expect_leader": None},
    {"id": 39, "query": "공동 소유 토지 분할 방법이 궁금합니다", "category": "real_estate", "expect_leader": None},
    {"id": 40, "query": "건물 지분 매매 시 주의사항", "category": "real_estate", "expect_leader": None},
    {"id": 41, "query": "부동산 소유권이전등기 셀프 가능한가요?", "category": "real_estate", "expect_leader": None},

    # ── 카테고리 7: 형사법 (L22) (5개) ──
    {"id": 42, "query": "사기죄 고소장 작성 방법을 알려주세요", "category": "criminal", "expect_leader": None},
    {"id": 43, "query": "횡령죄와 배임죄의 차이가 뭔가요?", "category": "criminal", "expect_leader": None},
    {"id": 44, "query": "폭행으로 고소당했는데 처벌 수위가 어떻게 되나요?", "category": "criminal", "expect_leader": None},
    {"id": 45, "query": "절도죄 초범인데 합의하면 기소유예 될까요?", "category": "criminal", "expect_leader": None},
    {"id": 46, "query": "검찰 수사 중인데 변호사 선임 시기는?", "category": "criminal", "expect_leader": None},

    # ── 카테고리 8: 노동법 (L30) (5개) ──
    {"id": 47, "query": "갑자기 해고 통보를 받았습니다. 부당해고 맞나요?", "category": "labor", "expect_leader": None},
    {"id": 48, "query": "퇴직금 계산 방법이 궁금합니다. 3년 6개월 근무했어요.", "category": "labor", "expect_leader": None},
    {"id": 49, "query": "회사가 야근 수당을 안 줍니다. 어떻게 청구하나요?", "category": "labor", "expect_leader": None},
    {"id": 50, "query": "근로계약서를 안 썼는데 문제가 되나요?", "category": "labor", "expect_leader": None},
    {"id": 51, "query": "노동조합 가입했다고 불이익을 받고 있어요", "category": "labor", "expect_leader": None},

    # ── 카테고리 9: 이혼/가족법 (L41) (5개) ──
    {"id": 52, "query": "협의이혼 절차와 기간이 궁금합니다", "category": "family", "expect_leader": None},
    {"id": 53, "query": "양육권은 보통 누구에게 가나요?", "category": "family", "expect_leader": None},
    {"id": 54, "query": "이혼 시 재산분할 비율은 어떻게 되나요?", "category": "family", "expect_leader": None},
    {"id": 55, "query": "배우자의 외도로 위자료 청구 가능한가요?", "category": "family", "expect_leader": None},
    {"id": 56, "query": "친권과 양육권의 차이가 뭔가요?", "category": "family", "expect_leader": None},

    # ── 카테고리 10: 임대차 (L08) (5개) ──
    {"id": 57, "query": "전세 보증금 3억인데 집주인이 안 돌려줘요", "category": "lease", "expect_leader": None},
    {"id": 58, "query": "월세 밀렸을 때 바로 쫓겨나나요?", "category": "lease", "expect_leader": None},
    {"id": 59, "query": "임대차 계약 갱신 거절 사유가 뭔가요?", "category": "lease", "expect_leader": None},
    {"id": 60, "query": "전세사기 피해를 당했습니다. 어떻게 해야 하나요?", "category": "lease", "expect_leader": None},
    {"id": 61, "query": "임차인의 권리를 보호받으려면 어떤 조치를 해야 하나요?", "category": "lease", "expect_leader": None},

    # ── 카테고리 11: 상속/신탁 (L57) (4개) ──
    {"id": 62, "query": "아버지가 돌아가셨는데 상속 포기 방법이 궁금합니다", "category": "inheritance", "expect_leader": None},
    {"id": 63, "query": "유언장 없이 돌아가셨는데 상속 순위는 어떻게 되나요?", "category": "inheritance", "expect_leader": None},
    {"id": 64, "query": "상속세 신고 기한과 세율이 궁금합니다", "category": "inheritance", "expect_leader": None},
    {"id": 65, "query": "명의신탁 부동산 문제가 있어요. 증여세 내야 하나요?", "category": "inheritance", "expect_leader": None},

    # ── 카테고리 12: 교통사고 (L07) (3개) ──
    {"id": 66, "query": "교통사고 났는데 상대방 과실이 100%입니다. 보상 절차는?", "category": "traffic", "expect_leader": None},
    {"id": 67, "query": "음주운전 사고 처벌 수위가 어떻게 되나요?", "category": "traffic", "expect_leader": None},
    {"id": 68, "query": "자동차 보험으로 처리 안 되는 경우는 언제인가요?", "category": "traffic", "expect_leader": None},

    # ── 카테고리 13: 지식재산권 (L26) (3개) ──
    {"id": 69, "query": "특허 출원 절차와 비용이 궁금합니다", "category": "ip", "expect_leader": None},
    {"id": 70, "query": "상표권 침해로 내 브랜드를 도용당했어요", "category": "ip", "expect_leader": None},
    {"id": 71, "query": "저작권 침해 신고 방법을 알려주세요", "category": "ip", "expect_leader": None},

    # ── 카테고리 14: IT/보안 (L21) (3개) ──
    {"id": 72, "query": "해킹 피해를 당했는데 법적 대응 방법은?", "category": "it_security", "expect_leader": None},
    {"id": 73, "query": "개인정보 유출 사고 시 기업의 법적 책임은?", "category": "it_security", "expect_leader": None},
    {"id": 74, "query": "사이버 명예훼손 고소 가능한가요?", "category": "it_security", "expect_leader": None},

    # ── 카테고리 15: 조세/금융 (L20) (3개) ──
    {"id": 75, "query": "양도소득세 비과세 요건이 궁금합니다", "category": "tax", "expect_leader": None},
    {"id": 76, "query": "종합소득세 신고를 안 했는데 가산세는 얼마인가요?", "category": "tax", "expect_leader": None},
    {"id": 77, "query": "세금 체납하면 어떤 불이익이 있나요?", "category": "tax", "expect_leader": None},

    # ── 카테고리 16: 행정법 (L31) (3개) ──
    {"id": 78, "query": "영업정지 행정처분 받았는데 취소 소송 가능한가요?", "category": "admin", "expect_leader": None},
    {"id": 79, "query": "건축 허가 거부 처분에 불복하고 싶습니다", "category": "admin", "expect_leader": None},
    {"id": 80, "query": "과태료 이의신청 방법을 알려주세요", "category": "admin", "expect_leader": None},

    # ── 카테고리 17: 소비자 (L38) (3개) ──
    {"id": 81, "query": "인터넷 쇼핑 환불 거부당했어요. 소비자 보호법 적용되나요?", "category": "consumer", "expect_leader": None},
    {"id": 82, "query": "하자 있는 제품 교환 거부 시 대응 방법", "category": "consumer", "expect_leader": None},
    {"id": 83, "query": "약관의 불공정한 조항은 무효라고 들었는데 맞나요?", "category": "consumer", "expect_leader": None},

    # ── 카테고리 18: 의료법 (L05) (3개) ──
    {"id": 84, "query": "수술 후 부작용이 생겼는데 의료과실인가요?", "category": "medical", "expect_leader": None},
    {"id": 85, "query": "의사의 설명의무 위반으로 소송 가능한가요?", "category": "medical", "expect_leader": None},
    {"id": 86, "query": "병원에서 환자 동의 없이 수술 범위를 확대했어요", "category": "medical", "expect_leader": None},

    # ── 카테고리 19: 헌법 (L35) (2개) ──
    {"id": 87, "query": "기본권 침해로 헌법소원 가능한가요?", "category": "constitution", "expect_leader": None},
    {"id": 88, "query": "위헌법률심판 절차를 알려주세요", "category": "constitution", "expect_leader": None},

    # ── 카테고리 20: 환경법 (L27) (2개) ──
    {"id": 89, "query": "공장 폐기물 불법투기 신고 방법", "category": "environment", "expect_leader": None},
    {"id": 90, "query": "환경오염 피해 손해배상 청구 가능한가요?", "category": "environment", "expect_leader": None},

    # ── 카테고리 21: 복합 법률 사안 (5개) ──
    {"id": 91, "query": "아버지 명의로 된 아파트에 살고 있는데, 아버지가 돌아가시고 형제들이 상속 분쟁 중입니다. 저는 전세계약서가 있어요.", "category": "complex", "expect_leader": None},
    {"id": 92, "query": "회사에서 해고당한 후 실업급여를 받고 있는데, 전 직장에서 횡령 혐의로 고소했습니다.", "category": "complex", "expect_leader": None},
    {"id": 93, "query": "이혼 소송 중인데 배우자가 공동재산인 부동산을 몰래 팔려고 합니다. 가처분 신청 가능한가요?", "category": "complex", "expect_leader": None},
    {"id": 94, "query": "교통사고로 입원했는데 산재처리가 안 된다고 합니다. 출퇴근 중 사고예요.", "category": "complex", "expect_leader": None},
    {"id": 95, "query": "프리랜서인데 클라이언트가 계약금만 받고 잠수탔어요. 사기인가요 민사인가요?", "category": "complex", "expect_leader": None},

    # ── 카테고리 22: 긴 상세 질문 (3개) ──
    {"id": 96, "query": "2024년 3월에 강남구 아파트를 전세 3억에 계약했습니다. 계약기간은 2년이고 2026년 3월에 만기입니다. 그런데 최근 집주인이 갑자기 집을 팔겠다고 하면서 2개월 뒤에 나가달라고 합니다. 대항력과 우선변제권은 갖추고 있고, 확정일자도 받았습니다. 어떻게 대응해야 하나요?", "category": "detailed", "expect_leader": None},
    {"id": 97, "query": "저는 5년간 일한 회사에서 구조조정을 이유로 해고 통보를 받았습니다. 하지만 저만 해고되었고 제 업무는 다른 직원이 맡게 되었습니다. 해고 예고도 없었고 해고사유서도 받지 못했습니다. 부당해고 구제신청을 하고 싶은데 절차와 기간을 알려주세요.", "category": "detailed", "expect_leader": None},
    {"id": 98, "query": "어머니께서 치매 진단을 받으셨는데, 삼촌이 어머니 명의의 부동산을 자기 앞으로 이전하려고 합니다. 어머니는 이미 의사결정능력이 없는 상태입니다. 성년후견 제도를 이용해서 막을 수 있나요?", "category": "detailed", "expect_leader": None},

    # ── 카테고리 23: 엣지 케이스 (2개) ──
    {"id": 99, "query": "법률 문제는 아닌데요, 그냥 궁금한 게 있어서요. 이 시스템이 무료인 이유가 뭔가요?", "category": "edge", "expect_leader": "유나"},
    {"id": 100, "query": "제가 지금 너무 힘들고 걱정이 많아요. 법적으로 도움받을 수 있는 게 뭐가 있을까요?", "category": "edge", "expect_leader": "유나"},
]


def check_health():
    """서버 상태 확인"""
    try:
        r = requests.get(HEALTH_URL, timeout=10)
        data = r.json()
        print(f"  서버 상태: {data.get('status', 'UNKNOWN')}")
        print(f"  리더 수: {data.get('leaders_count', '?')}")
        return r.status_code == 200
    except Exception as e:
        print(f"  서버 연결 실패: {e}")
        return False


def send_query(query, timeout=60):
    """API 쿼리 전송"""
    try:
        r = requests.post(
            API_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        return r.status_code, r.json()
    except requests.exceptions.Timeout:
        return 408, {"error": "TIMEOUT"}
    except Exception as e:
        return 0, {"error": str(e)}


def analyze_result(scenario, status_code, data):
    """결과 분석"""
    result = {
        "id": scenario["id"],
        "query": scenario["query"][:50] + ("..." if len(scenario["query"]) > 50 else ""),
        "category": scenario["category"],
        "status_code": status_code,
        "pass": True,
        "issues": [],
    }

    # HTTP 상태 확인
    if status_code != 200:
        result["pass"] = False
        result["issues"].append(f"HTTP {status_code}")
        result["leader"] = "N/A"
        result["specialty"] = "N/A"
        result["response_len"] = 0
        return result

    # 응답 데이터 파싱
    response_text = data.get("response", "")
    leader = data.get("leader", "")
    specialty = data.get("leader_specialty", "")
    api_status = data.get("status", "")

    result["leader"] = leader
    result["specialty"] = specialty
    result["response_len"] = len(response_text)
    result["api_status"] = api_status

    # 1) API 상태 확인
    if api_status not in ("SUCCESS",):
        result["pass"] = False
        result["issues"].append(f"API status: {api_status}")

    # 2) 응답 길이 확인 (최소 50자)
    if len(response_text) < 50:
        result["pass"] = False
        result["issues"].append(f"응답 너무 짧음 ({len(response_text)}자)")

    # 3) leader_specialty 필드 존재 확인
    if "leader_specialty" not in data:
        result["issues"].append("leader_specialty 필드 없음")

    # 4) 기대 리더 확인 (expect_leader가 있는 경우)
    expect = scenario.get("expect_leader")
    if expect and expect not in leader:
        result["pass"] = False
        result["issues"].append(f"기대 리더={expect}, 실제={leader}")

    # 5) Low Signal 카테고리: 유나 응답 확인
    if scenario["category"] == "low_signal":
        if "유나" not in response_text and "유나" not in leader:
            result["issues"].append("Low Signal인데 유나 응답 아님")

    # 6) 응답에 마크다운 표가 있는지 확인
    if "| --- |" in response_text or "|---|" in response_text:
        result["issues"].append("마크다운 표 감지됨")

    return result


def main():
    print("=" * 70)
    print("  Lawmadi OS — 100가지 실제 사용자 시뮬레이션")
    print(f"  시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1) 서버 상태 확인
    print("\n[1/3] 서버 상태 확인...")
    if not check_health():
        print("  ❌ 서버가 응답하지 않습니다. 중단합니다.")
        sys.exit(1)
    print("  ✅ 서버 정상\n")

    # 2) 시뮬레이션 실행
    print(f"[2/3] 100개 시나리오 실행 중...\n")
    results = []
    pass_count = 0
    fail_count = 0
    total_latency = 0

    for i, scenario in enumerate(SCENARIOS):
        start = time.time()
        status_code, data = send_query(scenario["query"])
        latency = time.time() - start
        total_latency += latency

        result = analyze_result(scenario, status_code, data)
        result["latency"] = round(latency, 1)
        results.append(result)

        if result["pass"]:
            pass_count += 1
            icon = "✅"
        else:
            fail_count += 1
            icon = "❌"

        issues_str = f" [{', '.join(result['issues'])}]" if result["issues"] else ""
        print(f"  {icon} #{result['id']:>3} | {result['category']:<15} | 리더: {result.get('leader', 'N/A'):<12} | {result['latency']:>5.1f}s | {result['response_len']:>5}자{issues_str}")

        # Rate limit 방지 (15/minute = 4초 간격)
        if i < len(SCENARIOS) - 1:
            time.sleep(4.5)

    # 3) 종합 결과
    print("\n" + "=" * 70)
    print("  [3/3] 종합 결과")
    print("=" * 70)

    print(f"\n  총 시나리오: {len(SCENARIOS)}개")
    print(f"  ✅ 성공: {pass_count}개 ({pass_count/len(SCENARIOS)*100:.1f}%)")
    print(f"  ❌ 실패: {fail_count}개 ({fail_count/len(SCENARIOS)*100:.1f}%)")
    print(f"  평균 응답 시간: {total_latency/len(SCENARIOS):.1f}초")
    print(f"  총 소요 시간: {total_latency:.0f}초")

    # 카테고리별 통계
    print("\n  ── 카테고리별 성공률 ──")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "pass": 0, "fail": 0}
        categories[cat]["total"] += 1
        if r["pass"]:
            categories[cat]["pass"] += 1
        else:
            categories[cat]["fail"] += 1

    for cat, stats in sorted(categories.items()):
        rate = stats["pass"] / stats["total"] * 100
        bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10))
        print(f"  {cat:<18} {bar} {rate:>5.1f}% ({stats['pass']}/{stats['total']})")

    # 리더별 라우팅 통계
    print("\n  ── 리더별 라우팅 분포 ──")
    leader_counts = {}
    for r in results:
        leader = r.get("leader", "N/A")
        if leader not in leader_counts:
            leader_counts[leader] = 0
        leader_counts[leader] += 1

    for leader, count in sorted(leader_counts.items(), key=lambda x: -x[1])[:15]:
        bar = "█" * count
        print(f"  {leader:<20} {bar} ({count})")

    # 실패 케이스 상세
    failures = [r for r in results if not r["pass"]]
    if failures:
        print(f"\n  ── 실패 케이스 상세 ({len(failures)}건) ──")
        for f in failures:
            print(f"  #{f['id']:>3} [{f['category']}] {f['query']}")
            print(f"       리더: {f.get('leader', 'N/A')} | 이슈: {', '.join(f['issues'])}")

    # specialty 필드 확인
    has_specialty = sum(1 for r in results if r.get("specialty"))
    print(f"\n  ── leader_specialty 필드 ──")
    print(f"  응답에 포함: {has_specialty}/{len(SCENARIOS)} ({has_specialty/len(SCENARIOS)*100:.1f}%)")

    print(f"\n  완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 결과 JSON 저장
    with open("scripts/simulation_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(SCENARIOS),
            "pass": pass_count,
            "fail": fail_count,
            "avg_latency": round(total_latency / len(SCENARIOS), 1),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: scripts/simulation_results.json")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
