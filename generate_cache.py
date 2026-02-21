#!/usr/bin/env python3
"""
63명 리더 대표 질문으로 response_cache.json 생성
사용법: python3 generate_cache.py [API_URL]
"""
import json, sys, time, os, requests

API_URL = sys.argv[1] if len(sys.argv) > 1 else os.getenv("LAWMADI_OS_API_URL", "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# 63명 대표 질문 (CSO, CTO, CCO + L01~L60)
QUESTIONS = {
    "CSO": "Lawmadi OS의 전략적 방향과 법률 AI 시스템의 발전 비전에 대해 알려주세요.",
    "CTO": "Lawmadi OS의 기술 아키텍처와 AI 무결성 검증 시스템은 어떻게 구성되어 있나요?",
    "CCO": "Lawmadi OS는 어떤 서비스인가요? 사용 방법을 알려주세요.",
    "L01": "친구에게 돈을 빌려줬는데 갚지 않고 있습니다. 차용증은 있지만 공증은 안 했는데 소송으로 받을 수 있나요?",
    "L02": "아버지께서 2020년 1월에 제 명의로 아파트를 구입하셨습니다. 실제 돈은 아버지가 내셨고, 저는 그냥 명의만 빌려드린 것입니다. 그런데 지금 제 빚 때문에 경매가 진행 중입니다.",
    "L03": "건설 공사 중 하도급 업체가 대금을 받지 못해 공사가 중단되었습니다. 원청에 직접 청구가 가능한가요?",
    "L04": "우리 아파트가 재건축 추진 중인데 조합원 자격과 분담금 문제로 분쟁이 있습니다. 어떻게 해야 하나요?",
    "L05": "어머니가 간단한 수술을 받았는데 의료진 실수로 합병증이 생겨 재수술을 받아야 합니다. 병원에서는 불가항력이라고 하는데 손해배상 청구가 가능한가요?",
    "L06": "도로 위의 포트홀 때문에 차가 파손되고 부상을 입었습니다. 국가를 상대로 손해배상 청구가 가능한가요?",
    "L07": "지난주 교차로에서 교통사고가 났습니다. 상대방이 신호위반이었는데, 보험사에서 저한테도 과실 30%를 주장하고 있습니다.",
    "L08": "2년 전인 2024년 3월에 전세 계약을 했습니다. 보증금은 3억원이고, 2026년 3월이 만기입니다. 그런데 집주인이 갑자기 집을 팔겠다고 하면서 2개월 뒤에 나가달라고 합니다.",
    "L09": "정부 조달 입찰에서 부정행위로 탈락 처리되었는데 이의신청을 하고 싶습니다. 절차가 어떻게 되나요?",
    "L10": "소송에서 이겨서 판결문을 받았는데 상대방이 돈을 안 갚고 있습니다. 강제집행 절차가 어떻게 되나요?",
    "L11": "채권추심 업체에서 밤낮으로 전화와 문자를 보내고 직장까지 찾아옵니다. 이게 합법인가요?",
    "L12": "법원 경매로 나온 아파트를 낙찰받으려고 합니다. 주의할 점과 절차가 어떻게 되나요?",
    "L13": "거래처에서 약속어음을 발행해줬는데 만기에 부도가 났습니다. 어떻게 대응해야 하나요?",
    "L14": "친구와 공동으로 카페를 운영하려고 합니다. 투자 비율은 6:4인데 법인 설립과 동업 계약서 작성 시 주의할 점이 무엇인가요?",
    "L15": "스타트업을 창업하려는데 주식회사와 유한회사 중 어떤 것이 유리한가요? 투자 유치를 고려하고 있습니다.",
    "L16": "카드빚과 대출이 합쳐서 8천만원 정도 됩니다. 월급은 250만원인데 최소 생활비를 제외하면 도저히 갚을 수가 없습니다. 개인회생이나 파산 중 어떤 게 유리한가요?",
    "L17": "해외 바이어와 물품 수출 계약을 체결했는데 대금을 지급하지 않고 있습니다. 국제 분쟁 해결 방법이 있나요?",
    "L18": "태양광 발전 사업을 시작하려고 합니다. 인허가 절차와 관련 법률 규제가 궁금합니다.",
    "L19": "해상 운송 중 화물이 파손되었습니다. 선박 회사에 손해배상을 청구할 수 있나요?",
    "L20": "양도소득세를 신고했는데 세무서에서 추가 세금을 부과했습니다. 부당하다고 생각하는데 어떻게 해야 하나요?",
    "L21": "회사 서버가 해킹당해서 고객 정보가 유출되었습니다. 법적 대응 절차와 손해배상 책임이 궁금합니다.",
    "L22": "지인에게 사업자금으로 5천만원을 빌려줬는데, 알고 보니 처음부터 갚을 생각이 없었던 것 같습니다. 차용증은 있지만 공증은 안 했습니다.",
    "L23": "연예인 매니지먼트 계약을 했는데 소속사가 불공정한 조건을 강요하고 있습니다. 계약 해지가 가능한가요?",
    "L24": "국세청의 세금 부과 처분이 부당하다고 생각합니다. 조세심판원에 불복 청구를 하고 싶은데 절차가 어떻게 되나요?",
    "L25": "군복무 중 상관에게 폭행을 당했습니다. 군사법원에 고소하려면 어떻게 해야 하나요?",
    "L26": "제가 블로그에 올린 사진을 어떤 업체가 허락 없이 광고에 사용하고 있습니다. 워터마크도 지웠는데 어떻게 대응해야 하나요?",
    "L27": "공장 근처에서 악취와 소음 피해를 받고 있습니다. 환경 오염으로 인한 손해배상 청구가 가능한가요?",
    "L28": "수입품에 대해 관세가 과다하게 부과된 것 같습니다. 관세 불복 절차가 어떻게 되나요?",
    "L29": "온라인 게임에서 아이템을 사기당했습니다. 현금 거래였는데 법적으로 보호받을 수 있나요?",
    "L30": "회사에서 갑자기 해고 통보를 받았습니다. 제가 3번이나 지각을 했다는 이유인데, 사실 그 날들은 모두 지하철 고장 때문이었습니다.",
    "L31": "영업허가 취소 처분을 받았습니다. 행정 소송으로 다투고 싶은데 절차가 어떻게 되나요?",
    "L32": "대기업이 납품 단가를 일방적으로 인하하고 있습니다. 공정거래법 위반 아닌가요?",
    "L33": "민간 우주 발사체 사업에 참여하려고 합니다. 우주항공 관련 법률 규제가 궁금합니다.",
    "L34": "회사에서 직원들의 개인정보를 동의 없이 외부에 제공한 것 같습니다. 어떻게 대응해야 하나요?",
    "L35": "법률이 헌법에 위반된다고 생각합니다. 헌법소원 청구 절차가 어떻게 되나요?",
    "L36": "문화재 보호구역 내에 건물을 증축하고 싶은데 허가를 받을 수 있을까요?",
    "L37": "16세 아이가 학교에서 폭행 사건에 연루되었습니다. 소년법에 따른 처분 절차가 궁금합니다.",
    "L38": "인터넷으로 구매한 제품이 불량인데 판매자가 환불을 거부하고 있습니다. 소비자보호법에 따라 어떻게 해야 하나요?",
    "L39": "통신사에서 약정 없이 요금제를 변경했습니다. 정보통신 관련 법률 위반 아닌가요?",
    "L40": "직장에서 성별을 이유로 승진에서 탈락했습니다. 차별 구제 신청이 가능한가요?",
    "L41": "남편과 이혼을 준비하고 있습니다. 아이가 7살인데, 양육권과 재산분할은 어떻게 진행되나요? 남편 명의의 아파트와 공동 대출이 있습니다.",
    "L42": "유튜브에 올린 제 음악을 다른 사람이 무단으로 사용하고 있습니다. 저작권 침해로 대응할 수 있나요?",
    "L43": "공사 현장에서 작업 중 추락 사고로 부상을 입었습니다. 산업재해 보상과 회사 책임이 궁금합니다.",
    "L44": "기초생활수급자 자격이 박탈되었습니다. 이의신청을 하고 싶은데 절차가 어떻게 되나요?",
    "L45": "학교에서 아이가 집단 따돌림을 당하고 있습니다. 학교폭력 대응 절차가 어떻게 되나요?",
    "L46": "국민연금 수령액이 예상보다 적게 나왔습니다. 재산정 신청이 가능한가요?",
    "L47": "새로운 기술 기반 서비스를 출시하려는데 규제 샌드박스 신청이 가능한가요? 절차가 궁금합니다.",
    "L48": "예술인으로 활동하며 전시회를 열었는데 주최 측이 작품 사용료를 지급하지 않습니다.",
    "L49": "식당에서 식중독에 걸렸습니다. 식품위생법에 따라 영업정지와 손해배상을 청구할 수 있나요?",
    "L50": "결혼이민자인데 남편의 가정폭력으로 이혼을 원합니다. 체류자격과 법적 보호가 궁금합니다.",
    "L51": "사찰 부지에 대한 소유권 분쟁이 있습니다. 종교법인의 재산 처분 절차가 궁금합니다.",
    "L52": "전 직장 동료가 SNS에 저에 대한 허위사실을 올려서 퇴사까지 하게 되었습니다. 게시글 캡처는 해두었는데 어떻게 대응해야 하나요?",
    "L53": "농지를 매입했는데 농지취득자격증명이 취소될 위기에 있습니다. 어떻게 해야 하나요?",
    "L54": "양식장에서 적조 피해를 입었습니다. 국가 보상이나 손해배상 청구가 가능한가요?",
    "L55": "연구 성과에 대한 특허 귀속 분쟁이 발생했습니다. 직무발명 보상 청구가 가능한가요?",
    "L56": "장애인 자녀의 특수학교 입학이 거부되었습니다. 교육권 침해로 구제받을 수 있나요?",
    "L57": "아버지가 돌아가시면서 유언장 없이 아파트 1채와 예금 2억원을 남기셨습니다. 형제가 3명인데, 큰형이 혼자 다 가져가겠다고 합니다.",
    "L58": "스포츠 대회에서 심판의 오심으로 메달을 빼앗겼습니다. 법적 구제 방법이 있나요?",
    "L59": "AI가 생성한 콘텐츠의 저작권은 누구에게 있나요? AI 학습 데이터 사용의 법적 문제가 궁금합니다.",
    "L60": "법률 문제가 있는데 어떤 분야의 전문가에게 상담해야 할지 모르겠습니다.",
}

def call_api(query: str) -> dict:
    """API 호출하여 응답 받기"""
    try:
        headers = {"Content-Type": "application/json"}
        if ADMIN_KEY:
            headers["X-Admin-Key"] = ADMIN_KEY
        resp = requests.post(
            f"{API_URL}/ask",
            json={"query": query, "lang": "ko"},
            headers=headers,
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    cache = {}
    total = len(QUESTIONS)
    success = 0
    fail = 0

    print(f"🚀 {total}개 대표 질문으로 response_cache.json 생성 시작\n")

    for i, (leader_id, question) in enumerate(QUESTIONS.items(), 1):
        print(f"[{i}/{total}] {leader_id}: {question[:40]}...")

        result = call_api(question)
        if result and result.get("status") == "SUCCESS":
            cache[leader_id] = {
                "query": question,
                "leader": result.get("leader", ""),
                "leader_specialty": result.get("leader_specialty", ""),
                "response": result.get("response", ""),
                "tier": result.get("tier", 1),
                "ssot_sources": result.get("ssot_sources", []),
                "meta": result.get("meta", {}),
            }
            actual_leader = result.get("leader", "?")
            print(f"  ✅ → {actual_leader} ({result.get('leader_specialty', '?')}) [{result.get('latency_ms', 0)}ms]")
            success += 1
        else:
            print(f"  ❌ 실패")
            fail += 1

        # Rate limit 방지
        if i < total:
            time.sleep(2)

    # 저장
    with open("response_cache.json", "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 완료: {success}/{total} 성공, {fail} 실패")
    print(f"📦 response_cache.json 저장 완료 ({len(cache)} entries)")

    # 매칭 정확도 리포트
    print(f"\n📊 리더 매칭 리포트:")
    correct = 0
    wrong = []
    for lid, entry in cache.items():
        expected_name = None
        # leaders.json에서 기대 리더 이름 조회
        if lid in ("CSO", "CTO", "CCO"):
            expected_name = {"CSO": "서연", "CTO": "지유", "CCO": "유나"}.get(lid)
        else:
            # leader_registry에서 조회
            try:
                with open("leaders.json", "r") as f:
                    reg = json.load(f)
                leader_reg = reg.get("swarm_engine_config", {}).get("leader_registry", {})
                expected_name = leader_reg.get(lid, {}).get("name")
            except:
                pass

        actual = entry.get("leader", "?")
        if expected_name and expected_name in actual:
            correct += 1
            print(f"  ✅ {lid}: {expected_name} → {actual}")
        else:
            wrong.append(lid)
            print(f"  ❌ {lid}: 기대={expected_name} 실제={actual}")

    print(f"\n정확도: {correct}/{len(cache)} ({correct*100//max(len(cache),1)}%)")
    if wrong:
        print(f"오매칭: {', '.join(wrong)}")


if __name__ == "__main__":
    main()
