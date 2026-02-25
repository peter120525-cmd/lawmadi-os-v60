"""리더별 복합 질문 테스트 - 배치 3 (6 리더 × 3 = 18건 일반 + 6건 전문가)
L05 연우(의료법), L06 벼리(손해배상), L20 찬솔(조세·금융),
L31 로운(행정법), L35 마루(헌법), L42 하람(저작권)
"""
import asyncio
import aiohttp
import json
import time
import re

BASE_URL = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"
ADMIN_KEY = "eGjMr9jAKKNzwfLjzlTmyPo5HVklyZ1BlrzJ_139jDw"

GENERAL_TESTS = [
    # L05 연우 (의료법)
    {"id": "L05-Q1", "leader_expect": "연우", "domain": "의료",
     "q": "수술 후 합병증이 발생했는데 의사의 설명의무 위반을 이유로 손해배상을 청구하려 합니다. 의료과실 입증 책임, 설명의무 위반의 법적 기준, 인과관계 추정 법리를 설명해주세요."},
    {"id": "L05-Q2", "leader_expect": "연우", "domain": "의료",
     "q": "성형수술 부작용으로 재수술이 필요합니다. 의료분쟁조정 신청 절차, 감정 비용, 조정 불성립 시 소송 전환 방법을 알려주세요."},
    {"id": "L05-Q3", "leader_expect": "연우", "domain": "의료",
     "q": "병원에서 오진으로 치료 시기를 놓쳤습니다. 진단 지연에 따른 기회 상실 손해배상의 법적 근거와 판례, 손해액 산정 방법을 설명해주세요."},

    # L06 벼리 (손해배상)
    {"id": "L06-Q1", "leader_expect": "벼리", "domain": "손해배상",
     "q": "아파트 누수로 아래층 천장과 가전제품이 파손되었습니다. 공동주택 하자에 따른 손해배상 청구 절차, 시공사와 관리주체의 책임 범위를 알려주세요."},
    {"id": "L06-Q2", "leader_expect": "벼리", "domain": "손해배상",
     "q": "반려견이 산책 중 다른 강아지를 물어 치료비가 발생했습니다. 동물 소유자의 손해배상 책임, 과실상계, 위자료 산정 기준을 설명해주세요."},
    {"id": "L06-Q3", "leader_expect": "벼리", "domain": "손해배상",
     "q": "공사장 소음과 진동으로 건물에 균열이 생겼습니다. 생활방해에 따른 손해배상, 유지청구(금지청구), 환경영향평가 미이행의 법적 효과를 알려주세요."},

    # L20 찬솔 (조세·금융)
    {"id": "L20-Q1", "leader_expect": "찬솔", "domain": "조세",
     "q": "상속받은 부동산을 양도할 때 양도소득세 계산 방법과 장기보유특별공제 요건, 1세대 1주택 비과세 특례를 설명해주세요."},
    {"id": "L20-Q2", "leader_expect": "찬솔", "domain": "조세",
     "q": "세무조사를 받게 되었습니다. 세무조사 대상 선정 기준, 납세자 권리, 조사 불복 절차(이의신청, 심사청구, 심판청구)를 알려주세요."},
    {"id": "L20-Q3", "leader_expect": "찬솔", "domain": "조세",
     "q": "사업자인데 부가가치세 매입세액 공제가 부인되었습니다. 매입세액 공제 요건, 사실과 다른 세금계산서의 처리, 가산세 면제 사유를 설명해주세요."},

    # L31 로운 (행정법)
    {"id": "L31-Q1", "leader_expect": "로운", "domain": "행정",
     "q": "건축허가 신청이 반려되었습니다. 행정처분의 위법성 판단 기준, 행정심판과 행정소송의 차이, 집행정지 신청 방법을 알려주세요."},
    {"id": "L31-Q2", "leader_expect": "로운", "domain": "행정",
     "q": "국가 도로 공사로 소유 토지가 수용됩니다. 토지보상법상 보상금 산정 기준, 이의재결 절차, 보상금 증감 소송 절차를 설명해주세요."},
    {"id": "L31-Q3", "leader_expect": "로운", "domain": "행정",
     "q": "영업정지 처분을 받았는데 과도하다고 생각합니다. 재량행위의 일탈·남용 판단 기준, 비례원칙 위반, 처분취소소송의 소익 요건을 알려주세요."},

    # L35 마루 (헌법)
    {"id": "L35-Q1", "leader_expect": "마루", "domain": "헌법",
     "q": "법률이 기본권을 침해한다고 생각합니다. 헌법소원심판 청구 요건(보충성, 자기관련성, 직접성, 현재성), 청구기간, 절차를 설명해주세요."},
    {"id": "L35-Q2", "leader_expect": "마루", "domain": "헌법",
     "q": "행정기관이 개인정보를 과도하게 수집합니다. 헌법상 개인정보자기결정권의 내용, 과잉금지원칙에 따른 심사 기준, 위헌심판 가능성을 알려주세요."},
    {"id": "L35-Q3", "leader_expect": "마루", "domain": "헌법",
     "q": "특정 직업에 대한 자격 제한이 직업선택의 자유를 침해하는 것 아닌가요? 직업의 자유 제한의 3단계 심사 기준과 헌법재판소 판례를 설명해주세요."},

    # L42 하람 (저작권)
    {"id": "L42-Q1", "leader_expect": "하람", "domain": "저작권",
     "q": "유튜브에 올린 영상에 배경음악을 사용했는데 저작권 경고를 받았습니다. 저작권법상 공정이용 판단 기준, 음악 저작물의 이용허락 절차, KOMCA 사용료 체계를 설명해주세요."},
    {"id": "L42-Q2", "leader_expect": "하람", "domain": "저작권",
     "q": "회사에서 직원이 만든 소프트웨어 프로그램의 저작권은 누구에게 있나요? 업무상 저작물과 컴퓨터프로그램 보호법상 특례, 직원 퇴사 후 권리관계를 설명해주세요."},
    {"id": "L42-Q3", "leader_expect": "하람", "domain": "저작권",
     "q": "온라인에서 무단 복제된 전자책이 유통되고 있습니다. 저작권 침해 신고 절차, 온라인서비스제공자의 책임, 손해배상 산정 방법을 알려주세요."},
]

EXPERT_TESTS = [
    {"id": "X-L05", "leader_expect": "연우", "domain": "의료",
     "q": "수술 후 합병증이 발생했는데 의사의 설명의무 위반을 이유로 손해배상을 청구하려 합니다. 의료과실 입증 책임, 설명의무 위반의 법적 기준, 인과관계 추정 법리를 설명해주세요."},
    {"id": "X-L06", "leader_expect": "벼리", "domain": "손해배상",
     "q": "아파트 누수로 아래층 천장과 가전제품이 파손되었습니다. 공동주택 하자에 따른 손해배상 청구 절차, 시공사와 관리주체의 책임 범위를 알려주세요."},
    {"id": "X-L20", "leader_expect": "찬솔", "domain": "조세",
     "q": "상속받은 부동산을 양도할 때 양도소득세 계산 방법과 장기보유특별공제 요건, 1세대 1주택 비과세 특례를 설명해주세요."},
    {"id": "X-L31", "leader_expect": "로운", "domain": "행정",
     "q": "건축허가 신청이 반려되었습니다. 행정처분의 위법성 판단 기준, 행정심판과 행정소송의 차이, 집행정지 신청 방법을 알려주세요."},
    {"id": "X-L35", "leader_expect": "마루", "domain": "헌법",
     "q": "법률이 기본권을 침해한다고 생각합니다. 헌법소원심판 청구 요건(보충성, 자기관련성, 직접성, 현재성), 청구기간, 절차를 설명해주세요."},
    {"id": "X-L42", "leader_expect": "하람", "domain": "저작권",
     "q": "유튜브에 올린 영상에 배경음악을 사용했는데 저작권 경고를 받았습니다. 저작권법상 공정이용 판단 기준, 음악 저작물의 이용허락 절차, KOMCA 사용료 체계를 설명해주세요."},
]


def score_expert(answer):
    scores = {}
    length = len(answer)
    scores["length"] = 3 if length >= 6000 else (2 if length >= 4000 else (1 if length >= 2000 else 0))
    law_refs = re.findall(r'제\s?\d+조(?:의\d+)?', answer)
    ref_count = len(set(law_refs))
    scores["law_refs"] = 3 if ref_count >= 8 else (2 if ref_count >= 5 else (1 if ref_count >= 2 else 0))
    prec_pats = [r'\d{4}[다나가마카타파라바사아자차하두누구무부수우주추후그드스으](?:합)?\d{2,6}',
                 r'대법원\s*\d{4}\s*\.\s*\d+\s*\.\s*\d+', r'선고\s*\d{4}']
    pc = sum(len(re.findall(p, answer)) for p in prec_pats)
    scores["precedents"] = 3 if pc >= 3 else (2 if pc >= 1 else (1 if "판례" in answer else 0))
    sects = re.findall(r'(?:^|\n)\s*(?:#{1,3}\s|[①②③④⑤⑥]|\d+\.\s|\*\*[^*]+\*\*)', answer)
    scores["structure"] = 3 if len(sects) >= 8 else (2 if len(sects) >= 5 else (1 if len(sects) >= 2 else 0))
    et = sum(1 for t in ["반대","소수설","다수설","견해","판시","실무","관할","구비서류","소요기간","비용","절차","검토"] if t in answer)
    scores["expert_depth"] = 3 if et >= 5 else (2 if et >= 3 else (1 if et >= 1 else 0))
    scores["total"] = sum(scores.values())
    scores["ref_count"] = ref_count
    scores["precedent_count"] = pc
    return scores


async def run_test(session, test, mode="general"):
    endpoint = "/ask" if mode == "general" else "/ask-expert"
    payload = {"query": test["q"]}
    headers = {"Content-Type": "application/json", "X-Admin-Key": ADMIN_KEY}
    start = time.time()
    try:
        async with session.post(f"{BASE_URL}{endpoint}", json=payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=180)) as resp:
            elapsed = round(time.time() - start, 1)
            if resp.status == 200:
                data = await resp.json()
                answer = data.get("response", "") or data.get("answer", "") or ""
                status = data.get("status", "UNKNOWN")
                leader = data.get("leader", "N/A")
                leader_name = leader.get("name", "N/A") if isinstance(leader, dict) else str(leader)
                quality = score_expert(answer)
                return {
                    "id": test["id"], "domain": test["domain"], "mode": mode,
                    "leader_expect": test["leader_expect"], "leader_actual": leader_name,
                    "leader_match": "O" if test["leader_expect"] in str(leader_name) else "X",
                    "status": status, "time": f"{elapsed}s", "length": len(answer),
                    "quality": quality,
                    "preview": answer[:180].replace("\n", " "),
                }
            else:
                text = await resp.text()
                return {"id": test["id"], "domain": test["domain"], "mode": mode,
                        "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                        "leader_match": "-", "status": f"HTTP_{resp.status}",
                        "time": f"{elapsed}s", "length": 0, "quality": {"total": 0},
                        "preview": text[:100]}
    except asyncio.TimeoutError:
        return {"id": test["id"], "domain": test["domain"], "mode": mode,
                "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                "leader_match": "-", "status": "TIMEOUT",
                "time": "180s", "length": 0, "quality": {"total": 0}, "preview": ""}
    except Exception as e:
        return {"id": test["id"], "domain": test["domain"], "mode": mode,
                "leader_expect": test["leader_expect"], "leader_actual": "N/A",
                "leader_match": "-", "status": "ERROR",
                "time": f"{round(time.time()-start,1)}s", "length": 0,
                "quality": {"total": 0}, "preview": str(e)[:100]}


async def main():
    print("=" * 75)
    print("배치 3: 일반(18건) + 전문가(6건) = 24건")
    print("L05 연우, L06 벼리, L20 찬솔, L31 로운, L35 마루, L42 하람")
    print("=" * 75)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                h = await resp.json()
                print(f"서버: {h['status']} | 버전: {h['os_version']}")
        except Exception as e:
            print(f"서버 연결 실패: {e}"); return

    # ── 일반 모드 18건 ──
    print("\n" + "=" * 75)
    print("[ 일반 모드 — 18건 ]")
    print("=" * 75)
    gen_results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(GENERAL_TESTS), 3):
            batch = GENERAL_TESTS[i:i+3]
            lid = batch[0]["id"].split("-")[0]
            print(f"\n--- {lid} {batch[0]['leader_expect']}({batch[0]['domain']}) ---")
            tasks = [run_test(session, t, "general") for t in batch]
            results = await asyncio.gather(*tasks)
            for r in results:
                gen_results.append(r)
                q = r["quality"]
                print(f"  [{r['id']}] {r['leader_actual']}({r['leader_match']}) | "
                      f"{r['status']} | {r['time']} | {r['length']}자 | "
                      f"법조문:{q.get('ref_count',0)} 판례:{q.get('precedent_count',0)}")
            if i + 3 < len(GENERAL_TESTS):
                await asyncio.sleep(1)

    # ── 전문가 모드 6건 ──
    print("\n" + "=" * 75)
    print("[ 전문가 모드 — 6건 ]")
    print("=" * 75)
    exp_results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(EXPERT_TESTS), 2):
            batch = EXPERT_TESTS[i:i+2]
            ids = ", ".join(t["id"] for t in batch)
            print(f"\n--- {ids} ---")
            tasks = [run_test(session, t, "expert") for t in batch]
            results = await asyncio.gather(*tasks)
            for r in results:
                exp_results.append(r)
                q = r["quality"]
                meets = "O" if r["length"] >= 4000 else "X"
                print(f"  [{r['id']}] {r['leader_actual']}({r['domain']}) | "
                      f"{r['status']} | {r['time']} | {r['length']}자(≥4K:{meets}) | "
                      f"법조문:{q.get('ref_count',0)} 판례:{q.get('precedent_count',0)} | 품질:{q.get('total',0)}/15")
            if i + 2 < len(EXPERT_TESTS):
                await asyncio.sleep(1)

    # ── 종합 ──
    all_results = gen_results + exp_results
    print("\n" + "=" * 75)
    print("종합 결과")
    print("=" * 75)

    g_total = len(gen_results)
    g_ok = sum(1 for r in gen_results if r["status"] == "SUCCESS")
    g_fc = sum(1 for r in gen_results if r["status"] == "FAIL_CLOSED")
    g_match = sum(1 for r in gen_results if r["leader_match"] == "O")
    g_len = sum(r["length"] for r in gen_results) / g_total if g_total else 0

    e_total = len(exp_results)
    e_ok = sum(1 for r in exp_results if r["status"] == "SUCCESS")
    e_fc = sum(1 for r in exp_results if r["status"] == "FAIL_CLOSED")
    e_4k = sum(1 for r in exp_results if r["length"] >= 4000)
    e_len = sum(r["length"] for r in exp_results) / e_total if e_total else 0
    e_qual = sum(r["quality"].get("total", 0) for r in exp_results) / e_total if e_total else 0

    print(f"\n  일반 모드 ({g_total}건):")
    print(f"    SUCCESS: {g_ok}/{g_total} | FAIL_CLOSED: {g_fc}")
    print(f"    리더 매칭: {g_match}/{g_total} | 평균 길이: {g_len:.0f}자")

    print(f"\n  전문가 모드 ({e_total}건):")
    print(f"    SUCCESS: {e_ok}/{e_total} | FAIL_CLOSED: {e_fc}")
    print(f"    ≥4,000자: {e_4k}/{e_total} | 평균 길이: {e_len:.0f}자 | 품질: {e_qual:.1f}/15")

    # 리더별 상세
    print(f"\n리더별 상세 (일반 모드):")
    print(f"  {'ID':<8} {'리더':<6} {'도메인':<8} {'성공':<6} {'매칭':<6} {'평균길이'}")
    print("  " + "-" * 50)
    for i in range(0, len(gen_results), 3):
        b = gen_results[i:i+3]
        lid = b[0]["id"].split("-")[0]
        ok = sum(1 for r in b if r["status"] == "SUCCESS")
        m = sum(1 for r in b if r["leader_match"] == "O")
        l = sum(r["length"] for r in b) / 3
        print(f"  {lid:<8} {b[0]['leader_actual']:<6} {b[0]['domain']:<8} {ok}/3    {m}/3    {l:.0f}자")

    # 실패 상세
    failures = [r for r in all_results if r["status"] not in ("SUCCESS",)]
    if failures:
        print(f"\n실패 ({len(failures)}건):")
        for r in failures:
            print(f"  [{r['id']}] {r['mode']} {r['status']} - {r['preview'][:80]}")

    short_expert = [r for r in exp_results if r["length"] < 4000 and r["status"] == "SUCCESS"]
    if short_expert:
        print(f"\n전문가 4,000자 미달 ({len(short_expert)}건):")
        for r in short_expert:
            print(f"  [{r['id']}] {r['length']}자 - {r['leader_actual']}({r['domain']})")

    with open("/data/data/com.termux/files/home/lawmadi-os-v60/tests/test_batch3_results.json", "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("\n결과 저장: tests/test_batch3_results.json")


if __name__ == "__main__":
    asyncio.run(main())
