"""홈페이지 12개 예시 질문 → 리더 매칭 점검"""
import requests, json, time, sys

API = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"

EXAMPLES = [
    ("전세분쟁", "2년 전인 2024년 3월에 전세 계약을 했습니다. 보증금은 3억원이고, 2026년 3월이 만기입니다. 그런데 집주인이 갑자기 집을 팔겠다고 하면서 2개월 뒤에 나가달라고 합니다.", "L08", "온유"),
    ("부동산", "아버지께서 2020년 1월에 제 명의로 아파트를 구입하셨습니다. 실제 돈은 아버지가 내셨고, 저는 그냥 명의만 빌려드린 것입니다. 그런데 지금 제 빚 때문에 경매가 진행 중입니다.", "L02", "보늬"),
    ("노동문제", "회사에서 갑자기 해고 통보를 받았습니다. 제가 3번이나 지각을 했다는 이유인데, 사실 그 날들은 모두 지하철 고장 때문이었습니다.", "L30", "담우"),
    ("이혼·양육", "남편과 이혼을 준비하고 있습니다. 아이가 7살인데, 양육권과 재산분할은 어떻게 진행되나요? 남편 명의의 아파트와 공동 대출이 있습니다.", "L41", "산들"),
    ("상속분쟁", "아버지가 돌아가시면서 유언장 없이 아파트 1채와 예금 2억원을 남기셨습니다. 형제가 3명인데, 큰형이 혼자 다 가져가겠다고 합니다.", "L57", "세움"),
    ("교통사고", "지난주 교차로에서 교통사고가 났습니다. 상대방이 신호위반이었는데, 보험사에서 저한테도 과실 30%를 주장하고 있습니다.", "L07", "하늬"),
    ("사기·횡령", "지인에게 사업자금으로 5천만원을 빌려줬는데, 알고 보니 처음부터 갚을 생각이 없었던 것 같습니다. 차용증은 있지만 공증은 안 했습니다.", "L22", "무결"),
    ("명예훼손", "전 직장 동료가 SNS에 저에 대한 허위사실을 올려서 퇴사까지 하게 되었습니다. 게시글 캡처는 해두었는데 어떻게 대응해야 하나요?", "L52", "미소"),
    ("의료사고", "어머니가 간단한 수술을 받았는데 의료진 실수로 합병증이 생겨 재수술을 받아야 합니다. 병원에서는 불가항력이라고 하는데 손해배상 청구가 가능한가요?", "L05", "연우"),
    ("개인회생", "카드빚과 대출이 합쳐서 8천만원 정도 됩니다. 월급은 250만원인데 최소 생활비를 제외하면 도저히 갚을 수가 없습니다. 개인회생이나 파산 중 어떤 게 유리한가요?", "L11", "오름"),
    ("저작권", "제가 블로그에 올린 사진을 어떤 업체가 허락 없이 광고에 사용하고 있습니다. 워터마크도 지웠는데 어떻게 대응해야 하나요?", "L42", "하람"),
    ("창업·법인", "친구와 공동으로 카페를 운영하려고 합니다. 투자 비율은 6:4인데 법인 설립과 동업 계약서 작성 시 주의할 점이 무엇인가요?", "L15", "별하"),
]

results = []
for i, (cat, question, expected_id, expected_name) in enumerate(EXAMPLES):
    t0 = time.time()
    try:
        r = requests.post(f"{API}/ask", json={"query": question}, timeout=120)
        data = r.json()
        status = data.get("status", "")
        leader = data.get("leader_name", data.get("leader", ""))
        leader_id = data.get("leader_id", "")
        elapsed = time.time() - t0

        match = "O" if (expected_id in str(leader_id) or expected_name in str(leader)) else "X"
        results.append({
            "cat": cat, "expected": f"{expected_id}({expected_name})",
            "actual_id": leader_id, "actual_name": leader,
            "match": match, "status": status, "elapsed": f"{elapsed:.1f}s"
        })

        print(f"[{i+1:02d}] {match} {cat:8s} | 기대:{expected_id}({expected_name}) → 실제:{leader_id}({leader}) | {status} | {elapsed:.1f}s")
        sys.stdout.flush()
    except Exception as e:
        print(f"[{i+1:02d}] ERROR {cat}: {e}")
        results.append({"cat": cat, "expected": f"{expected_id}({expected_name})", "error": str(e)})

    time.sleep(1)

ok = sum(1 for r in results if r.get("match") == "O")
fail = sum(1 for r in results if r.get("match") == "X")
err = sum(1 for r in results if "error" in r)
print(f"\n=== 결과 요약 ===")
print(f"정상 매칭: {ok}/12")
print(f"불일치: {fail}/12")
print(f"에러: {err}/12")

if fail > 0:
    print(f"\n--- 불일치 목록 ---")
    for r in results:
        if r.get("match") == "X":
            print(f"  {r['cat']}: 기대 {r['expected']} → 실제 {r['actual_id']}({r['actual_name']})")
