"""리더별 복잡한 질문 3개씩 테스트 - 배치 2 (6 리더 × 3 = 18건)
L01 휘율(민사법), L07 하늬(교통사고), L08 온유(임대차),
L26 루다(지식재산권), L30 담우(노동법), L41 산들(이혼·가족)
"""
import asyncio
import aiohttp
import json
import os
import time

BASE_URL = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"
ADMIN_KEY = os.getenv("TEST_ADMIN_KEY", "")

TESTS = [
    # L01 휘율 (민사법)
    {"id": "L01-Q1", "leader_expect": "휘율", "domain": "민사",
     "q": "친구에게 5천만원을 빌려줬는데 차용증만 있고 공증은 안 받았습니다. 변제기가 지났는데도 갚지 않아 소송을 하려 합니다. 지급명령과 민사소송의 차이, 소멸시효, 가압류 절차를 알려주세요."},
    {"id": "L01-Q2", "leader_expect": "휘율", "domain": "민사",
     "q": "아파트 층간소음으로 아래층 주민과 분쟁 중입니다. 민사조정 절차, 손해배상 청구 가능성, 그리고 층간소음 관련 환경분쟁조정위원회 신청 방법을 설명해주세요."},
    {"id": "L01-Q3", "leader_expect": "휘율", "domain": "민사",
     "q": "온라인에서 중고 명품을 구매했는데 가품이었습니다. 판매자에게 매매계약 취소, 대금반환, 손해배상을 청구하려 합니다. 전자상거래법상 청약철회와 민법상 하자담보책임의 차이를 알려주세요."},

    # L07 하늬 (교통사고)
    {"id": "L07-Q1", "leader_expect": "하늬", "domain": "교통사고",
     "q": "교차로에서 신호위반 차량에 의해 교통사고가 발생했습니다. 과실비율 산정 기준, 보험회사 합의금과 법원 판결금의 차이, 후유장해 등급 판정 절차를 설명해주세요."},
    {"id": "L07-Q2", "leader_expect": "하늬", "domain": "교통사고",
     "q": "자전거 도로에서 전동킥보드와 충돌하여 골절상을 입었습니다. 개인형 이동장치(PM) 사고 시 과실비율, 보험 적용 여부, 손해배상 청구 방법을 알려주세요."},
    {"id": "L07-Q3", "leader_expect": "하늬", "domain": "교통사고",
     "q": "택시를 타고 가다가 택시 기사의 과실로 교통사고가 나서 입원했습니다. 운송인의 손해배상 책임, 자동차보험과 공제조합 보상 절차, 그리고 위자료 산정 기준을 설명해주세요."},

    # L08 온유 (임대차)
    {"id": "L08-Q1", "leader_expect": "온유", "domain": "임대차",
     "q": "전세 계약이 만료되었는데 집주인이 보증금을 돌려주지 않습니다. 임차권등기명령, 보증금반환소송, 그리고 주택임대차보호법상 대항력과 우선변제권의 요건을 알려주세요."},
    {"id": "L08-Q2", "leader_expect": "온유", "domain": "임대차",
     "q": "상가 임대차 계약에서 권리금 회수 기회를 보호받을 수 있나요? 상가건물임대차보호법상 권리금 보호 요건, 임대인의 방해 금지 의무, 손해배상 청구 절차를 설명해주세요."},
    {"id": "L08-Q3", "leader_expect": "온유", "domain": "임대차",
     "q": "월세를 3개월 연체했더니 집주인이 계약 해지 통보를 보냈습니다. 임대차보호법상 차임 연체 해지 요건, 명도소송 절차, 그리고 임차인의 대항 방법을 알려주세요."},

    # L26 루다 (지식재산권)
    {"id": "L26-Q1", "leader_expect": "루다", "domain": "지식재산",
     "q": "스타트업에서 개발한 AI 알고리즘을 특허출원하려 합니다. 소프트웨어 발명의 특허 요건, 청구항 작성 방법, 그리고 직무발명 보상 관련 법률을 설명해주세요."},
    {"id": "L26-Q2", "leader_expect": "루다", "domain": "지식재산",
     "q": "경쟁사가 우리 회사 등록 상표와 유사한 상표를 사용하고 있습니다. 상표권 침해 판단 기준, 침해금지 가처분 신청, 손해배상 청구 절차를 알려주세요."},
    {"id": "L26-Q3", "leader_expect": "루다", "domain": "지식재산",
     "q": "디자인 전공 프리랜서인데 납품한 로고 디자인을 의뢰인이 계약 범위를 넘어 다른 곳에도 사용하고 있습니다. 저작권법상 업무상 저작물과 프리랜서 저작물의 차이, 저작재산권 양도와 이용허락의 차이를 설명해주세요."},

    # L30 담우 (노동법)
    {"id": "L30-Q1", "leader_expect": "담우", "domain": "노동",
     "q": "회사에서 정리해고를 통보받았습니다. 근로기준법상 정당한 정리해고 요건 4가지, 해고예고수당, 부당해고 구제신청 절차를 알려주세요."},
    {"id": "L30-Q2", "leader_expect": "담우", "domain": "노동",
     "q": "퇴직금을 계산했는데 회사가 제시한 금액이 너무 적습니다. 퇴직금 산정 기준, 평균임금 계산 방법, 그리고 미지급 퇴직금에 대한 지연이자와 체불임금 진정 절차를 설명해주세요."},
    {"id": "L30-Q3", "leader_expect": "담우", "domain": "노동",
     "q": "택배 기사로 일하는데 특수고용직이라 4대 보험 가입이 안 됩니다. 근로자성 판단 기준, 플랫폼 노동자 보호법, 산재보험 특례 적용 요건을 설명해주세요."},

    # L41 산들 (이혼·가족)
    {"id": "L41-Q1", "leader_expect": "산들", "domain": "이혼·가족",
     "q": "협의이혼을 진행 중인데 배우자가 재산분할에 동의하지 않습니다. 협의이혼과 재판이혼의 차이, 재산분할 비율 산정 기준, 위자료 청구 조건을 알려주세요."},
    {"id": "L41-Q2", "leader_expect": "산들", "domain": "이혼·가족",
     "q": "이혼 후 양육권과 면접교섭권 분쟁이 있습니다. 친권자 지정 기준, 양육비 산정표, 면접교섭권 불이행 시 이행강제금 절차를 설명해주세요."},
    {"id": "L41-Q3", "leader_expect": "산들", "domain": "이혼·가족",
     "q": "배우자의 외도 증거를 확보하여 이혼소송을 하려 합니다. 유책배우자의 이혼청구 제한, 부정행위 증거의 적법한 수집 방법, 상간자에 대한 위자료 청구 가능성을 알려주세요."},
]


async def run_test(session, test):
    """Run a single test."""
    payload = {"query": test["q"]}
    headers = {
        "Content-Type": "application/json",
        "X-Admin-Key": ADMIN_KEY,
    }
    start = time.time()
    try:
        async with session.post(
            f"{BASE_URL}/ask",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            elapsed = round(time.time() - start, 1)
            if resp.status == 200:
                data = await resp.json()
                answer = data.get("response", "") or data.get("answer", "") or ""
                status = data.get("status", "UNKNOWN")
                leader = data.get("leader", "N/A")
                leader_name = leader.get("name", "N/A") if isinstance(leader, dict) else str(leader)
                leader_specialty = data.get("leader_specialty", "")
                # Quality score
                score = 0
                if len(answer) > 500:
                    score += 1
                if len(answer) > 1500:
                    score += 1
                if "제" in answer and "조" in answer:
                    score += 1
                if any(m in answer for m in ["##", "**", "1.", "①", "가."]):
                    score += 1
                if len(answer) > 2500:
                    score += 1

                return {
                    "id": test["id"],
                    "domain": test["domain"],
                    "leader_expect": test["leader_expect"],
                    "leader_actual": leader_name,
                    "leader_match": "O" if test["leader_expect"] in str(leader_name) else "X",
                    "status": status,
                    "time": f"{elapsed}s",
                    "length": len(answer),
                    "quality": score,
                    "preview": answer[:150].replace("\n", " "),
                }
            elif resp.status == 429:
                return {
                    "id": test["id"], "domain": test["domain"],
                    "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                    "leader_match": "-", "status": "RATE_LIMITED",
                    "time": f"{elapsed}s", "length": 0, "quality": 0, "preview": "",
                }
            else:
                text = await resp.text()
                return {
                    "id": test["id"], "domain": test["domain"],
                    "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                    "leader_match": "-", "status": f"HTTP_{resp.status}",
                    "time": f"{elapsed}s", "length": 0, "quality": 0,
                    "preview": text[:100],
                }
    except asyncio.TimeoutError:
        return {
            "id": test["id"], "domain": test["domain"],
            "leader_expect": test["leader_expect"], "leader_actual": "N/A",
            "leader_match": "-", "status": "TIMEOUT",
            "time": "120s", "length": 0, "quality": 0, "preview": "",
        }
    except Exception as e:
        return {
            "id": test["id"], "domain": test["domain"],
            "leader_expect": test["leader_expect"], "leader_actual": "N/A",
            "leader_match": "-", "status": "ERROR",
            "time": f"{round(time.time()-start,1)}s", "length": 0, "quality": 0,
            "preview": str(e)[:100],
        }


async def main():
    print("=" * 70)
    print("리더별 복잡한 질문 테스트 - 배치 2 (6 리더 × 3 = 18건)")
    print("L01 휘율, L07 하늬, L08 온유, L26 루다, L30 담우, L41 산들")
    print("=" * 70)

    # Health check
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                health = await resp.json()
                print(f"서버: {health['status']} | 버전: {health['os_version']}")
        except Exception as e:
            print(f"서버 연결 실패: {e}")
            return

    results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(TESTS), 3):
            batch = TESTS[i:i+3]
            leader_id = batch[0]["id"].split("-")[0]
            print(f"\n--- {leader_id} {batch[0]['leader_expect']}({batch[0]['domain']}) ---")
            tasks = [run_test(session, t) for t in batch]
            batch_results = await asyncio.gather(*tasks)
            for r in batch_results:
                results.append(r)
                print(f"  [{r['id']}] 리더:{r['leader_actual']}({r['leader_match']}) | "
                      f"상태:{r['status']} | {r['time']} | "
                      f"{r['length']}자 | 품질:{r['quality']}")
            if i + 3 < len(TESTS):
                await asyncio.sleep(1)

    # Summary
    print("\n" + "=" * 70)
    print("종합 결과")
    print("=" * 70)

    total = len(results)
    success = sum(1 for r in results if r["status"] == "SUCCESS")
    fail_closed = sum(1 for r in results if r["status"] == "FAIL_CLOSED")
    other_fail = sum(1 for r in results if r["status"] not in ("SUCCESS", "FAIL_CLOSED"))
    match_ok = sum(1 for r in results if r["leader_match"] == "O")
    avg_quality = sum(r["quality"] for r in results) / total if total else 0
    avg_length = sum(r["length"] for r in results) / total if total else 0

    print(f"  총 테스트: {total}건")
    print(f"  SUCCESS: {success}/{total} ({success/total*100:.0f}%)")
    print(f"  FAIL_CLOSED: {fail_closed}/{total}")
    print(f"  기타 실패: {other_fail}/{total}")
    print(f"  리더 매칭: {match_ok}/{total} ({match_ok/total*100:.0f}%)")
    print(f"  평균 품질: {avg_quality:.1f}/5")
    print(f"  평균 답변 길이: {avg_length:.0f}자")

    print("\n리더별 상세:")
    print(f"  {'ID':<8} {'리더':<6} {'도메인':<10} {'성공':<6} {'매칭':<6} {'품질':<6} {'평균길이'}")
    print("  " + "-" * 60)
    for i in range(0, len(results), 3):
        batch = results[i:i+3]
        lid = batch[0]["id"].split("-")[0]
        leader = batch[0]["leader_actual"]
        domain = batch[0]["domain"]
        ok = sum(1 for r in batch if r["status"] == "SUCCESS")
        match = sum(1 for r in batch if r["leader_match"] == "O")
        q = sum(r["quality"] for r in batch) / 3
        l = sum(r["length"] for r in batch) / 3
        print(f"  {lid:<8} {leader:<6} {domain:<10} {ok}/3    {match}/3    {q:.1f}    {l:.0f}자")

    failures = [r for r in results if r["status"] != "SUCCESS"]
    if failures:
        print(f"\n실패 상세 ({len(failures)}건):")
        for r in failures:
            print(f"  [{r['id']}] {r['status']} - 리더:{r['leader_actual']} - {r['preview'][:80]}")

    # Save results
    with open("/data/data/com.termux/files/home/lawmadi-os-v60/tests/test_leader_complex_batch2_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n결과 저장: tests/test_leader_complex_batch2_results.json")


if __name__ == "__main__":
    asyncio.run(main())
