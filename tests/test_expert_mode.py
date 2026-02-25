"""전문가용 답변(expert mode) 테스트 — 12 리더 × 1문항 = 12건
엔드포인트: /ask-expert
기준: 최소 4,000자, 판례 인용 3건+, 법률 검토서 수준
"""
import asyncio
import aiohttp
import json
import time
import re

BASE_URL = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"
ADMIN_KEY = "eGjMr9jAKKNzwfLjzlTmyPo5HVklyZ1BlrzJ_139jDw"

TESTS = [
    # Batch 1 리더들
    {"id": "E-L02", "leader_expect": "보늬", "domain": "부동산",
     "q": "재개발 구역 내 빌라를 매수했는데, 조합원 자격을 얻으려면 어떤 요건을 충족해야 하나요? 분양권 전매 제한과 투기과열지구 규제도 함께 설명해주세요."},
    {"id": "E-L14", "leader_expect": "다솜", "domain": "회사·M&A",
     "q": "소수 주주로서 대표이사의 배임행위에 대해 주주대표소송을 제기하려 합니다. 소송 요건, 절차, 비용 부담은 어떻게 되나요?"},
    {"id": "E-L22", "leader_expect": "무결", "domain": "형사",
     "q": "음주운전 교통사고 후 도주했다가 다음 날 자수했습니다. 도로교통법상 음주운전, 특정범죄가중처벌법상 도주치상이 모두 적용되나요? 예상 형량은?"},
    {"id": "E-L34", "leader_expect": "지누", "domain": "개인정보",
     "q": "온라인 쇼핑몰에서 10만 건의 개인정보가 유출되었습니다. 개인정보보호법상 통지의무, 과징금 기준, 그리고 피해자 집단소송 절차를 설명해주세요."},
    {"id": "E-L43", "leader_expect": "해나", "domain": "산업재해",
     "q": "건설현장에서 안전난간 미설치로 추락사고가 발생했습니다. 산업안전보건법상 사업주 처벌 기준과 중대재해처벌법 적용 요건을 설명해주세요."},
    {"id": "E-L57", "leader_expect": "세움", "domain": "상속·신탁",
     "q": "아버지가 유언으로 전 재산을 장남에게만 남겼습니다. 나머지 자녀들의 유류분 반환청구권과 특별수익 공제 계산 방법을 알려주세요."},

    # Batch 2 리더들
    {"id": "E-L01", "leader_expect": "휘율", "domain": "민사",
     "q": "친구에게 5천만원을 빌려줬는데 차용증만 있고 공증은 안 받았습니다. 변제기가 지났는데도 갚지 않아 소송을 하려 합니다. 지급명령과 민사소송의 차이, 소멸시효, 가압류 절차를 알려주세요."},
    {"id": "E-L07", "leader_expect": "하늬", "domain": "교통사고",
     "q": "교차로에서 신호위반 차량에 의해 교통사고가 발생했습니다. 과실비율 산정 기준, 보험회사 합의금과 법원 판결금의 차이, 후유장해 등급 판정 절차를 설명해주세요."},
    {"id": "E-L08", "leader_expect": "온유", "domain": "임대차",
     "q": "전세 계약이 만료되었는데 집주인이 보증금을 돌려주지 않습니다. 임차권등기명령, 보증금반환소송, 그리고 주택임대차보호법상 대항력과 우선변제권의 요건을 알려주세요."},
    {"id": "E-L26", "leader_expect": "루다", "domain": "지식재산",
     "q": "경쟁사가 우리 회사 등록 상표와 유사한 상표를 사용하고 있습니다. 상표권 침해 판단 기준, 침해금지 가처분 신청, 손해배상 청구 절차를 알려주세요."},
    {"id": "E-L30", "leader_expect": "담우", "domain": "노동",
     "q": "회사에서 정리해고를 통보받았습니다. 근로기준법상 정당한 정리해고 요건 4가지, 해고예고수당, 부당해고 구제신청 절차를 알려주세요."},
    {"id": "E-L41", "leader_expect": "산들", "domain": "이혼·가족",
     "q": "협의이혼을 진행 중인데 배우자가 재산분할에 동의하지 않습니다. 협의이혼과 재판이혼의 차이, 재산분할 비율 산정 기준, 위자료 청구 조건을 알려주세요."},
]


def score_expert(answer: str) -> dict:
    """전문가용 답변 품질 상세 평가"""
    scores = {}

    # 1. 길이 (4000자 이상 목표)
    length = len(answer)
    if length >= 6000:
        scores["length"] = 3
    elif length >= 4000:
        scores["length"] = 2
    elif length >= 2000:
        scores["length"] = 1
    else:
        scores["length"] = 0

    # 2. 법조문 인용 (제X조 패턴)
    law_refs = re.findall(r'제\s?\d+조(?:의\d+)?', answer)
    ref_count = len(set(law_refs))
    if ref_count >= 8:
        scores["law_refs"] = 3
    elif ref_count >= 5:
        scores["law_refs"] = 2
    elif ref_count >= 2:
        scores["law_refs"] = 1
    else:
        scores["law_refs"] = 0

    # 3. 판례 인용 (대법원, 선고, 판결 등)
    precedent_patterns = [
        r'\d{4}[다나]\d+',          # 2020다12345
        r'대법원\s*\d{4}\s*\.\s*\d+\s*\.\s*\d+',  # 대법원 2020. 1. 1.
        r'선고\s*\d{4}',            # 선고 2020
        r'\d{4}[가-힣]{1,3}\d+',     # 2020가합12345
    ]
    precedent_count = 0
    for p in precedent_patterns:
        precedent_count += len(re.findall(p, answer))
    if precedent_count >= 3:
        scores["precedents"] = 3
    elif precedent_count >= 1:
        scores["precedents"] = 2
    elif "판례" in answer or "판결" in answer:
        scores["precedents"] = 1
    else:
        scores["precedents"] = 0

    # 4. 구조화 (섹션 수)
    section_markers = re.findall(r'(?:^|\n)\s*(?:#{1,3}\s|[①②③④⑤⑥]|\d+\.\s|\*\*[^*]+\*\*)', answer)
    if len(section_markers) >= 8:
        scores["structure"] = 3
    elif len(section_markers) >= 5:
        scores["structure"] = 2
    elif len(section_markers) >= 2:
        scores["structure"] = 1
    else:
        scores["structure"] = 0

    # 5. 전문가 지표 (반대견해, 소수설, 실무절차 등)
    expert_terms = 0
    for term in ["반대", "소수설", "다수설", "견해", "판시", "취지", "실무",
                 "관할", "구비서류", "소요기간", "비용", "절차", "검토"]:
        if term in answer:
            expert_terms += 1
    if expert_terms >= 5:
        scores["expert_depth"] = 3
    elif expert_terms >= 3:
        scores["expert_depth"] = 2
    elif expert_terms >= 1:
        scores["expert_depth"] = 1
    else:
        scores["expert_depth"] = 0

    scores["total"] = sum(scores.values())  # max 15
    scores["ref_count"] = ref_count
    scores["precedent_count"] = precedent_count
    return scores


async def run_test(session, test):
    """Run a single expert test."""
    payload = {"query": test["q"]}
    headers = {
        "Content-Type": "application/json",
        "X-Admin-Key": ADMIN_KEY,
    }
    start = time.time()
    try:
        async with session.post(
            f"{BASE_URL}/ask-expert",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as resp:
            elapsed = round(time.time() - start, 1)
            if resp.status == 200:
                data = await resp.json()
                answer = data.get("response", "") or data.get("answer", "") or ""
                status = data.get("status", "UNKNOWN")
                leader = data.get("leader", "N/A")
                leader_name = leader.get("name", "N/A") if isinstance(leader, dict) else str(leader)
                quality = score_expert(answer)

                return {
                    "id": test["id"],
                    "domain": test["domain"],
                    "leader_expect": test["leader_expect"],
                    "leader_actual": leader_name,
                    "leader_match": "O" if test["leader_expect"] in str(leader_name) else "-",
                    "status": status,
                    "time": f"{elapsed}s",
                    "length": len(answer),
                    "quality": quality,
                    "preview": answer[:200].replace("\n", " "),
                }
            elif resp.status == 429:
                return {
                    "id": test["id"], "domain": test["domain"],
                    "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                    "leader_match": "-", "status": "RATE_LIMITED",
                    "time": f"{elapsed}s", "length": 0, "quality": {"total": 0},
                    "preview": "",
                }
            else:
                text = await resp.text()
                return {
                    "id": test["id"], "domain": test["domain"],
                    "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                    "leader_match": "-", "status": f"HTTP_{resp.status}",
                    "time": f"{elapsed}s", "length": 0, "quality": {"total": 0},
                    "preview": text[:150],
                }
    except asyncio.TimeoutError:
        return {
            "id": test["id"], "domain": test["domain"],
            "leader_expect": test["leader_expect"], "leader_actual": "N/A",
            "leader_match": "-", "status": "TIMEOUT",
            "time": "180s", "length": 0, "quality": {"total": 0}, "preview": "",
        }
    except Exception as e:
        return {
            "id": test["id"], "domain": test["domain"],
            "leader_expect": test["leader_expect"], "leader_actual": "N/A",
            "leader_match": "-", "status": "ERROR",
            "time": f"{round(time.time()-start,1)}s", "length": 0,
            "quality": {"total": 0}, "preview": str(e)[:150],
        }


async def main():
    print("=" * 75)
    print("전문가용 답변(Expert Mode) 테스트 — 12 리더 × 1문항")
    print("엔드포인트: /ask-expert | 기준: 4,000자+, 판례 3건+")
    print("=" * 75)

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
    # 2개씩 동시 실행 (expert는 응답이 길어서 부하 관리)
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(TESTS), 2):
            batch = TESTS[i:i+2]
            ids = ", ".join(t["id"] for t in batch)
            print(f"\n--- 테스트: {ids} ---")
            tasks = [run_test(session, t) for t in batch]
            batch_results = await asyncio.gather(*tasks)
            for r in batch_results:
                results.append(r)
                q = r["quality"]
                meets_min = "O" if r["length"] >= 4000 else "X"
                print(f"  [{r['id']}] {r['leader_actual']}({r['domain']}) | "
                      f"{r['status']} | {r['time']} | {r['length']}자(≥4K:{meets_min}) | "
                      f"법조문:{q.get('ref_count',0)} 판례:{q.get('precedent_count',0)} | "
                      f"품질:{q.get('total',0)}/15")
            if i + 2 < len(TESTS):
                await asyncio.sleep(1)

    # Summary
    print("\n" + "=" * 75)
    print("종합 결과")
    print("=" * 75)

    total = len(results)
    success = sum(1 for r in results if r["status"] == "SUCCESS")
    fail_closed = sum(1 for r in results if r["status"] == "FAIL_CLOSED")
    meets_4k = sum(1 for r in results if r["length"] >= 4000)
    meets_6k = sum(1 for r in results if r["length"] >= 6000)
    avg_length = sum(r["length"] for r in results) / total if total else 0
    avg_quality = sum(r["quality"].get("total", 0) for r in results) / total if total else 0

    print(f"  총 테스트: {total}건")
    print(f"  SUCCESS: {success}/{total}")
    print(f"  FAIL_CLOSED: {fail_closed}/{total}")
    print(f"  ≥4,000자 달성: {meets_4k}/{total} ({meets_4k/total*100:.0f}%)")
    print(f"  ≥6,000자 달성: {meets_6k}/{total} ({meets_6k/total*100:.0f}%)")
    print(f"  평균 답변 길이: {avg_length:.0f}자")
    print(f"  평균 품질: {avg_quality:.1f}/15")

    # Detail table
    print(f"\n상세 결과:")
    print(f"  {'ID':<8} {'리더':<6} {'도메인':<10} {'길이':<8} {'법조문':<6} {'판례':<5} {'구조':<5} {'전문':<5} {'총점'}")
    print("  " + "-" * 70)
    for r in results:
        q = r["quality"]
        mark = "✓" if r["length"] >= 4000 else "✗"
        print(f"  {r['id']:<8} {r['leader_actual']:<6} {r['domain']:<10} "
              f"{r['length']:<6}{mark}  {q.get('law_refs',0)}/3   "
              f"{q.get('precedents',0)}/3  {q.get('structure',0)}/3  "
              f"{q.get('expert_depth',0)}/3  {q.get('total',0)}/15")

    # Failures
    failures = [r for r in results if r["status"] != "SUCCESS"]
    if failures:
        print(f"\n실패 ({len(failures)}건):")
        for r in failures:
            print(f"  [{r['id']}] {r['status']} - {r['preview'][:80]}")

    # Under 4K
    under_4k = [r for r in results if r["length"] < 4000 and r["status"] == "SUCCESS"]
    if under_4k:
        print(f"\n4,000자 미달 ({len(under_4k)}건):")
        for r in under_4k:
            print(f"  [{r['id']}] {r['length']}자 - {r['leader_actual']}({r['domain']})")

    # Save results
    with open("/data/data/com.termux/files/home/lawmadi-os-v60/tests/test_expert_mode_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n결과 저장: tests/test_expert_mode_results.json")


if __name__ == "__main__":
    asyncio.run(main())
