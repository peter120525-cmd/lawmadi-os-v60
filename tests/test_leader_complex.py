"""리더별 복잡한 질문 3개씩 테스트 (6 리더 × 3 = 18건)"""
import asyncio
import aiohttp
import json
import os
import time
import sys

BASE_URL = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"
ADMIN_KEY = os.getenv("TEST_ADMIN_KEY", "")

TESTS = [
    # L02 보늬 (부동산법)
    {"id": "L02-Q1", "leader_expect": "보늬", "domain": "부동산",
     "q": "재개발 구역 내 빌라를 매수했는데, 조합원 자격을 얻으려면 어떤 요건을 충족해야 하나요? 분양권 전매 제한과 투기과열지구 규제도 함께 설명해주세요."},
    {"id": "L02-Q2", "leader_expect": "보늬", "domain": "부동산",
     "q": "분양권을 전매하려 합니다. 양도소득세와 취득세가 각각 어떻게 부과되며, 비과세 혜택을 받을 수 있는 조건은 무엇인가요?"},
    {"id": "L02-Q3", "leader_expect": "보늬", "domain": "부동산",
     "q": "부부 공동명의 아파트에 근저당이 설정되어 있는데, 이혼 시 재산분할과 근저당 처리는 어떻게 되나요? 대출 승계 절차도 알려주세요."},

    # L14 다솜 (회사·M&A)
    {"id": "L14-Q1", "leader_expect": "다솜", "domain": "회사·M&A",
     "q": "소수 주주로서 대표이사의 배임행위에 대해 주주대표소송을 제기하려 합니다. 소송 요건, 절차, 비용 부담은 어떻게 되나요?"},
    {"id": "L14-Q2", "leader_expect": "다솜", "domain": "회사·M&A",
     "q": "상장회사 합병 시 반대주주의 주식매수청구권 행사 절차와 매수가격 산정 방법을 설명해주세요. 합병비율 불공정 시 구제수단도 알려주세요."},
    {"id": "L14-Q3", "leader_expect": "다솜", "domain": "회사·M&A",
     "q": "이사가 회사 기회를 유용하여 자기 회사를 설립한 경우, 충실의무 위반으로 손해배상을 청구하려면 어떤 절차를 거쳐야 하나요?"},

    # L22 무결 (형사법)
    {"id": "L22-Q1", "leader_expect": "무결", "domain": "형사",
     "q": "보이스피싱 조직에서 현금 수거책으로 일하다 적발되었습니다. 사기죄 공동정범과 방조범의 양형 차이, 그리고 자수 시 감형 가능성을 알려주세요."},
    {"id": "L22-Q2", "leader_expect": "무결", "domain": "형사",
     "q": "음주운전 교통사고 후 도주했다가 다음 날 자수했습니다. 도로교통법상 음주운전, 특정범죄가중처벌법상 도주치상이 모두 적용되나요? 예상 형량은?"},
    {"id": "L22-Q3", "leader_expect": "무결", "domain": "형사",
     "q": "회사 자금 5억원을 개인 용도로 사용한 업무상횡령 혐의를 받고 있습니다. 전액 반환하면 양형에 어떤 영향이 있나요? 배임과 횡령의 차이도 설명해주세요."},

    # L34 지누 (개인정보보호)
    {"id": "L34-Q1", "leader_expect": "지누", "domain": "개인정보",
     "q": "회사에서 CCTV에 AI 안면인식 기능을 도입하려 합니다. 개인정보보호법상 생체정보 처리 동의 요건과 CCTV 설치 관련 법적 제한사항을 알려주세요."},
    {"id": "L34-Q2", "leader_expect": "지누", "domain": "개인정보",
     "q": "온라인 쇼핑몰에서 10만 건의 개인정보가 유출되었습니다. 개인정보보호법상 통지의무, 과징금 기준, 그리고 피해자 집단소송 절차를 설명해주세요."},
    {"id": "L34-Q3", "leader_expect": "지누", "domain": "개인정보",
     "q": "한국 기업이 해외 클라우드 서버에 고객 개인정보를 저장하려 합니다. 개인정보 국외이전 동의 요건과 적정성 결정 제도, EU GDPR과의 차이점을 알려주세요."},

    # L43 해나 (산업재해)
    {"id": "L43-Q1", "leader_expect": "해나", "domain": "산업재해",
     "q": "건설현장에서 안전난간 미설치로 추락사고가 발생했습니다. 산업안전보건법상 사업주 처벌 기준과 중대재해처벌법 적용 요건을 설명해주세요."},
    {"id": "L43-Q2", "leader_expect": "해나", "domain": "산업재해",
     "q": "직장 내 괴롭힘으로 우울증과 공황장애가 발생했습니다. 산업재해로 인정받기 위한 요건과 절차, 그리고 회사에 대한 손해배상 청구 방법을 알려주세요."},
    {"id": "L43-Q3", "leader_expect": "해나", "domain": "산업재해",
     "q": "야간 교대근무를 10년간 하다가 뇌출혈이 발생했습니다. 업무상 질병으로 인정받을 수 있나요? 과로사 산재 인정 기준과 보상 내용을 설명해주세요."},

    # L57 세움 (상속·신탁)
    {"id": "L57-Q1", "leader_expect": "세움", "domain": "상속·신탁",
     "q": "아버지가 유언으로 전 재산을 장남에게만 남겼습니다. 나머지 자녀들의 유류분 반환청구권과 특별수익 공제 계산 방법을 알려주세요."},
    {"id": "L57-Q2", "leader_expect": "세움", "domain": "상속·신탁",
     "q": "상속을 포기했는데 나중에 피상속인의 숨겨진 채무가 발견되었습니다. 상속포기 효력, 한정승인과의 차이, 그리고 채권자의 사해행위 취소 가능성을 설명해주세요."},
    {"id": "L57-Q3", "leader_expect": "세움", "domain": "상속·신탁",
     "q": "치매 부모님의 성년후견인으로 선임되었습니다. 후견인의 권한 범위, 재산관리 의무, 그리고 부동산 처분 시 법원 허가 절차를 알려주세요."},
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
            "leader_match": "-", "status": f"ERROR",
            "time": f"{round(time.time()-start,1)}s", "length": 0, "quality": 0,
            "preview": str(e)[:100],
        }


async def main():
    print("=" * 70)
    print("리더별 복잡한 질문 테스트 (6 리더 × 3 = 18건)")
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
    # Run 3 concurrent tests at a time (per leader batch)
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(TESTS), 3):
            batch = TESTS[i:i+3]
            leader_id = batch[0]["id"].split("-")[0]
            print(f"\n--- {leader_id} {batch[0]['leader_expect']}({batch[0]['domain']}) ---")
            tasks = [run_test(session, t) for t in batch]
            batch_results = await asyncio.gather(*tasks)
            for r in batch_results:
                results.append(r)
                match_mark = r["leader_match"]
                print(f"  [{r['id']}] 리더:{r['leader_actual']}({match_mark}) | "
                      f"상태:{r['status']} | {r['time']} | "
                      f"{r['length']}자 | 품질:{r['quality']}")
            # Small delay between leader batches
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

    # Per-leader summary
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

    # Failures detail
    failures = [r for r in results if r["status"] != "SUCCESS"]
    if failures:
        print(f"\n실패 상세 ({len(failures)}건):")
        for r in failures:
            print(f"  [{r['id']}] {r['status']} - {r['preview'][:80]}")

    # Save results
    with open("/data/data/com.termux/files/home/lawmadi-os-v60/tests/test_leader_complex_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n결과 저장: tests/test_leader_complex_results.json")


if __name__ == "__main__":
    asyncio.run(main())
