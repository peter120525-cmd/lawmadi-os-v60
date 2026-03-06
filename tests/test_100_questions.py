"""100가지 법률질문 종합 테스트 — 답변 내용, 리더 매칭, 답변 질 평가"""
import asyncio
import aiohttp
import json
import os
import time
import sys

BASE_URL = "http://localhost:8080"
ADMIN_KEY = os.getenv("TEST_ADMIN_KEY", "")  # rate limit bypass

# 100가지 법률질문 (20개 카테고리 × 5개씩)
QUESTIONS = [
    # ── 1. 민법 / 계약 (5) ──
    {"q": "임대차 계약서 없이 구두로 계약했는데 법적 효력이 있나요?", "category": "민법/계약"},
    {"q": "전세 보증금을 돌려주지 않으면 어떻게 해야 하나요?", "category": "민법/계약"},
    {"q": "계약 해지 시 위약금은 어떻게 산정하나요?", "category": "민법/계약"},
    {"q": "미성년자가 체결한 계약은 유효한가요?", "category": "민법/계약"},
    {"q": "보증인의 책임 범위는 어디까지인가요?", "category": "민법/계약"},

    # ── 2. 부동산 (5) ──
    {"q": "부동산 매매 시 등기를 하지 않으면 소유권이 이전되지 않나요?", "category": "부동산"},
    {"q": "전세권 설정과 확정일자의 차이는 무엇인가요?", "category": "부동산"},
    {"q": "재건축 아파트 분양권 전매 제한 규정이 어떻게 되나요?", "category": "부동산"},
    {"q": "토지 경계 분쟁이 발생하면 어떻게 해결하나요?", "category": "부동산"},
    {"q": "임대인이 건물을 매도했을 때 임차인의 권리는?", "category": "부동산"},

    # ── 3. 형법 / 범죄 (5) ──
    {"q": "폭행죄와 상해죄의 차이는 무엇인가요?", "category": "형법"},
    {"q": "사기죄 성립 요건은 무엇인가요?", "category": "형법"},
    {"q": "명예훼손과 모욕죄의 차이점은?", "category": "형법"},
    {"q": "정당방위가 인정되는 조건은 무엇인가요?", "category": "형법"},
    {"q": "절도죄와 횡령죄는 어떻게 다른가요?", "category": "형법"},

    # ── 4. 노동법 (5) ──
    {"q": "부당해고를 당했을 때 구제 절차는?", "category": "노동법"},
    {"q": "퇴직금 계산 방법을 알려주세요.", "category": "노동법"},
    {"q": "연차 유급휴가 발생 기준이 어떻게 되나요?", "category": "노동법"},
    {"q": "최저임금 위반 시 처벌은 어떻게 되나요?", "category": "노동법"},
    {"q": "직장 내 괴롭힘 신고 절차는?", "category": "노동법"},

    # ── 5. 가족법 / 이혼 (5) ──
    {"q": "협의이혼 절차와 소요 기간은?", "category": "가족법"},
    {"q": "양육권과 친권의 차이는 무엇인가요?", "category": "가족법"},
    {"q": "재산분할 비율은 어떻게 결정되나요?", "category": "가족법"},
    {"q": "위자료 청구 가능한 사유와 금액 기준은?", "category": "가족법"},
    {"q": "사실혼 관계에서의 법적 보호는?", "category": "가족법"},

    # ── 6. 상속 (5) ──
    {"q": "법정 상속 순위와 상속 비율은?", "category": "상속"},
    {"q": "유류분 반환 청구는 어떻게 하나요?", "category": "상속"},
    {"q": "상속 포기와 한정승인의 차이는?", "category": "상속"},
    {"q": "유언장의 법적 요건은 무엇인가요?", "category": "상속"},
    {"q": "상속세 기본 공제 한도는 얼마인가요?", "category": "상속"},

    # ── 7. 교통/손해배상 (5) ──
    {"q": "교통사고 과실 비율은 어떻게 결정되나요?", "category": "교통/손해배상"},
    {"q": "음주운전 처벌 기준과 벌금은?", "category": "교통/손해배상"},
    {"q": "뺑소니 사고 피해자 보상 절차는?", "category": "교통/손해배상"},
    {"q": "자동차 보험 분쟁 해결 방법은?", "category": "교통/손해배상"},
    {"q": "교통사고 합의금 적정 수준은?", "category": "교통/손해배상"},

    # ── 8. 소비자/전자상거래 (5) ──
    {"q": "인터넷 쇼핑몰 환불 규정은 어떻게 되나요?", "category": "소비자"},
    {"q": "청약철회 가능 기간은 며칠인가요?", "category": "소비자"},
    {"q": "불량 제품 교환 및 배상 청구 방법은?", "category": "소비자"},
    {"q": "헬스장 중도 해지 시 환불 기준은?", "category": "소비자"},
    {"q": "온라인 사기 피해를 당했을 때 대처 방법은?", "category": "소비자"},

    # ── 9. 회사법/상법 (5) ──
    {"q": "1인 법인 설립 절차와 비용은?", "category": "회사법"},
    {"q": "주주총회 소집 절차와 의결 요건은?", "category": "회사법"},
    {"q": "이사의 충실의무와 경업금지의무는?", "category": "회사법"},
    {"q": "법인 대표이사의 연대책임 범위는?", "category": "회사법"},
    {"q": "소규모 합병 절차와 요건은?", "category": "회사법"},

    # ── 10. 세법 (5) ──
    {"q": "종합소득세 신고 기간과 세율은?", "category": "세법"},
    {"q": "양도소득세 비과세 요건은 무엇인가요?", "category": "세법"},
    {"q": "부가가치세 환급 절차는?", "category": "세법"},
    {"q": "증여세 면제 한도와 신고 방법은?", "category": "세법"},
    {"q": "프리랜서 세금 신고 방법은?", "category": "세법"},

    # ── 11. 지식재산권 (5) ──
    {"q": "특허 출원 절차와 소요 기간은?", "category": "지식재산"},
    {"q": "저작권 침해 시 손해배상 청구 방법은?", "category": "지식재산"},
    {"q": "상표 등록 거절 사유와 대응 방법은?", "category": "지식재산"},
    {"q": "영업비밀 침해 시 법적 구제수단은?", "category": "지식재산"},
    {"q": "디자인 특허와 실용신안의 차이는?", "category": "지식재산"},

    # ── 12. 행정법 (5) ──
    {"q": "행정심판 청구 기간과 절차는?", "category": "행정법"},
    {"q": "건축허가 취소에 대한 불복 방법은?", "category": "행정법"},
    {"q": "영업정지 처분에 대한 구제수단은?", "category": "행정법"},
    {"q": "정보공개 청구 거부 시 대응 방법은?", "category": "행정법"},
    {"q": "과징금 부과 처분에 대한 이의신청은?", "category": "행정법"},

    # ── 13. 개인정보/IT (5) ──
    {"q": "개인정보 유출 시 피해 보상 방법은?", "category": "개인정보/IT"},
    {"q": "CCTV 설치 시 법적 요건은 무엇인가요?", "category": "개인정보/IT"},
    {"q": "사이버 명예훼손 신고 절차는?", "category": "개인정보/IT"},
    {"q": "개인정보 삭제 요청권(잊힐 권리)은?", "category": "개인정보/IT"},
    {"q": "회사가 직원 이메일을 감시하는 것은 합법인가요?", "category": "개인정보/IT"},

    # ── 14. 의료/의료사고 (5) ──
    {"q": "의료사고 소송 절차와 입증 책임은?", "category": "의료"},
    {"q": "의료 과실에 대한 손해배상 범위는?", "category": "의료"},
    {"q": "환자의 동의권과 설명의무 위반 시 책임은?", "category": "의료"},
    {"q": "성형수술 부작용 시 법적 대응 방법은?", "category": "의료"},
    {"q": "의료분쟁조정 제도는 어떻게 이용하나요?", "category": "의료"},

    # ── 15. 군사/병역 (5) ──
    {"q": "병역 면제 사유와 절차는?", "category": "군사/병역"},
    {"q": "군 복무 중 인권 침해 시 구제 방법은?", "category": "군사/병역"},
    {"q": "대체복무제 신청 자격과 절차는?", "category": "군사/병역"},
    {"q": "예비군 훈련 불참 시 처벌은?", "category": "군사/병역"},
    {"q": "군 영창 제도는 어떻게 바뀌었나요?", "category": "군사/병역"},

    # ── 16. 환경법 (5) ──
    {"q": "층간소음 분쟁 해결 절차는?", "category": "환경법"},
    {"q": "공장 소음·진동 피해 배상 청구 방법은?", "category": "환경법"},
    {"q": "불법 폐기물 투기 신고와 처벌은?", "category": "환경법"},
    {"q": "환경영향평가 대상 사업 기준은?", "category": "환경법"},
    {"q": "미세먼지 관련 국가 배상 소송 가능성은?", "category": "환경법"},

    # ── 17. 금융/채무 (5) ──
    {"q": "개인회생 신청 자격과 절차는?", "category": "금융/채무"},
    {"q": "신용회복위원회 채무조정 절차는?", "category": "금융/채무"},
    {"q": "불법 사채 이자 제한과 대응 방법은?", "category": "금융/채무"},
    {"q": "보이스피싱 피해 환급 절차는?", "category": "금융/채무"},
    {"q": "소멸시효가 완성된 채무도 갚아야 하나요?", "category": "금융/채무"},

    # ── 18. 국제법/이민 (5) ──
    {"q": "외국인 근로자의 노동법 보호 범위는?", "category": "국제법"},
    {"q": "국제결혼 이혼 시 관할법원은?", "category": "국제법"},
    {"q": "영주권자의 병역 의무는 어떻게 되나요?", "category": "국제법"},
    {"q": "해외 직구 시 관세와 통관 규정은?", "category": "국제법"},
    {"q": "난민 신청 절차와 인정 기준은?", "category": "국제법"},

    # ── 19. 헌법/기본권 (5) ──
    {"q": "집회 및 시위의 자유 제한 기준은?", "category": "헌법"},
    {"q": "헌법소원 심판 청구 요건은?", "category": "헌법"},
    {"q": "양심적 병역거부의 헌법적 근거는?", "category": "헌법"},
    {"q": "표현의 자유와 혐오표현 규제의 한계는?", "category": "헌법"},
    {"q": "국가긴급권 발동 요건과 한계는?", "category": "헌법"},

    # ── 20. 기타 실생활 (5) ──
    {"q": "반려동물이 이웃을 물었을 때 법적 책임은?", "category": "기타"},
    {"q": "학교폭력 가해자 처벌과 피해자 보호 절차는?", "category": "기타"},
    {"q": "아르바이트생도 4대보험 가입이 필수인가요?", "category": "기타"},
    {"q": "공동구매 사기 피해 시 법적 대응은?", "category": "기타"},
    {"q": "묘지 이전 분쟁 해결 방법은?", "category": "기타"},
]


async def ask_question(session, idx, q_data):
    """Send a single question to /ask and collect results."""
    payload = {"query": q_data["q"], "leader": "auto"}
    headers = {"X-Admin-Key": ADMIN_KEY}  # bypass rate limit
    start = time.time()
    try:
        async with session.post(f"{BASE_URL}/ask", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=90)) as resp:
            elapsed = round(time.time() - start, 2)
            if resp.status == 200:
                data = await resp.json()
                answer = data.get("response", "") or data.get("answer", "") or ""
                leader = data.get("leader", "N/A")
                leader_name = leader.get("name", "N/A") if isinstance(leader, dict) else str(leader)
                leader_code = leader.get("leader_code", "N/A") if isinstance(leader, dict) else data.get("leader_code", "N/A")
                leader_specialty = data.get("leader_specialty", "")
                sources = data.get("ssot_sources", data.get("sources", []))
                laws = data.get("laws_cited", data.get("laws", []))
                quality = data.get("meta", data.get("quality", {}))
                tier = data.get("tier", "N/A")
                trace_id = data.get("trace_id", "")

                # Quality metrics
                answer_len = len(answer)
                has_law_ref = bool(laws) or "제" in answer and "조" in answer
                has_structured = any(marker in answer for marker in ["##", "**", "1.", "①", "가.", "- "])

                return {
                    "idx": idx + 1,
                    "question": q_data["q"],
                    "category": q_data["category"],
                    "status": "OK",
                    "leader_name": leader_name,
                    "leader_code": leader_code,
                    "leader_specialty": leader_specialty,
                    "tier": tier,
                    "answer_len": answer_len,
                    "has_law_ref": has_law_ref,
                    "has_structured": has_structured,
                    "source_count": len(sources) if sources else 0,
                    "law_count": len(laws) if laws else 0,
                    "elapsed": elapsed,
                    "answer_preview": answer[:200].replace("\n", " "),
                    "trace_id": trace_id,
                }
            elif resp.status == 429:
                return {
                    "idx": idx + 1, "question": q_data["q"], "category": q_data["category"],
                    "status": "RATE_LIMITED", "elapsed": elapsed,
                    "leader_name": "N/A", "leader_code": "N/A", "tier": "N/A",
                    "answer_len": 0, "has_law_ref": False, "has_structured": False,
                    "source_count": 0, "law_count": 0, "answer_preview": "",
                    "trace_id": "",
                }
            else:
                text = await resp.text()
                return {
                    "idx": idx + 1, "question": q_data["q"], "category": q_data["category"],
                    "status": f"HTTP_{resp.status}", "elapsed": elapsed,
                    "leader_name": "N/A", "leader_code": "N/A", "tier": "N/A",
                    "answer_len": 0, "has_law_ref": False, "has_structured": False,
                    "source_count": 0, "law_count": 0,
                    "answer_preview": text[:100],
                    "trace_id": "",
                }
    except asyncio.TimeoutError:
        return {
            "idx": idx + 1, "question": q_data["q"], "category": q_data["category"],
            "status": "TIMEOUT", "elapsed": 60.0,
            "leader_name": "N/A", "leader_code": "N/A", "tier": "N/A",
            "answer_len": 0, "has_law_ref": False, "has_structured": False,
            "source_count": 0, "law_count": 0, "answer_preview": "",
            "trace_id": "",
        }
    except Exception as e:
        return {
            "idx": idx + 1, "question": q_data["q"], "category": q_data["category"],
            "status": f"ERROR: {e}", "elapsed": round(time.time() - start, 2),
            "leader_name": "N/A", "leader_code": "N/A", "tier": "N/A",
            "answer_len": 0, "has_law_ref": False, "has_structured": False,
            "source_count": 0, "law_count": 0, "answer_preview": "",
            "trace_id": "",
        }


async def main():
    print("=" * 80)
    print("🧪 Lawmadi OS — 100가지 법률질문 종합 테스트")
    print("=" * 80)

    # Check server
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                health = await resp.json()
                print(f"서버 상태: {health['status']}")
                print(f"버전: {health['os_version']}")
                gemini = health.get("diagnostics", {}).get("modules", {}).get("gemini_key", False)
                print(f"Gemini: {'✅' if gemini else '❌'}")
                print()
        except Exception as e:
            print(f"❌ 서버 연결 실패: {e}")
            return

    results = []
    total_start = time.time()

    # Run in batches of 3 (avoid Gemini API overload)
    BATCH_SIZE = 3
    BATCH_DELAY = 1.0  # seconds between batches

    async with aiohttp.ClientSession() as session:
        for batch_start in range(0, len(QUESTIONS), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(QUESTIONS))
            batch = QUESTIONS[batch_start:batch_end]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(QUESTIONS) + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"[Batch {batch_num}/{total_batches}] Q{batch_start+1}~Q{batch_end} ...", end=" ", flush=True)

            tasks = [
                ask_question(session, batch_start + i, q_data)
                for i, q_data in enumerate(batch)
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            ok_count = sum(1 for r in batch_results if r["status"] == "OK")
            print(f"✅ {ok_count}/{len(batch_results)}")

            if batch_end < len(QUESTIONS):
                await asyncio.sleep(BATCH_DELAY)

    total_elapsed = round(time.time() - total_start, 1)

    # ── Analysis ──
    print("\n" + "=" * 80)
    print("📊 테스트 결과 분석")
    print("=" * 80)

    ok_results = [r for r in results if r["status"] == "OK"]
    rate_limited = [r for r in results if r["status"] == "RATE_LIMITED"]
    errors = [r for r in results if r["status"] not in ("OK", "RATE_LIMITED")]

    print(f"\n총 질문: {len(results)}")
    print(f"성공: {len(ok_results)} ({len(ok_results)*100//len(results)}%)")
    print(f"Rate Limited: {len(rate_limited)}")
    print(f"에러: {len(errors)}")
    print(f"총 소요 시간: {total_elapsed}s")
    if ok_results:
        avg_latency = round(sum(r["elapsed"] for r in ok_results) / len(ok_results), 2)
        print(f"평균 응답 시간: {avg_latency}s")

    # ── Leader Matching Analysis ──
    print(f"\n{'─' * 80}")
    print("🎯 리더 매칭 분석")
    print(f"{'─' * 80}")

    leader_counts = {}
    for r in ok_results:
        key = f"{r['leader_name']} ({r['leader_code']})"
        if key not in leader_counts:
            leader_counts[key] = {"count": 0, "categories": set()}
        leader_counts[key]["count"] += 1
        leader_counts[key]["categories"].add(r["category"])

    for leader, info in sorted(leader_counts.items(), key=lambda x: -x[1]["count"]):
        cats = ", ".join(sorted(info["categories"]))
        print(f"  {leader}: {info['count']}건 — [{cats}]")

    # ── Quality Analysis ──
    print(f"\n{'─' * 80}")
    print("📝 답변 품질 분석")
    print(f"{'─' * 80}")

    if ok_results:
        avg_len = round(sum(r["answer_len"] for r in ok_results) / len(ok_results))
        law_ref_count = sum(1 for r in ok_results if r["has_law_ref"])
        structured_count = sum(1 for r in ok_results if r["has_structured"])
        short_answers = [r for r in ok_results if r["answer_len"] < 100]
        long_answers = [r for r in ok_results if r["answer_len"] > 3000]

        print(f"평균 답변 길이: {avg_len}자")
        print(f"법령 참조 포함: {law_ref_count}/{len(ok_results)} ({law_ref_count*100//len(ok_results)}%)")
        print(f"구조화된 답변: {structured_count}/{len(ok_results)} ({structured_count*100//len(ok_results)}%)")
        print(f"짧은 답변 (<100자): {len(short_answers)}건")
        print(f"긴 답변 (>3000자): {len(long_answers)}건")

    # ── Category Breakdown ──
    print(f"\n{'─' * 80}")
    print("📂 카테고리별 성공률 및 품질")
    print(f"{'─' * 80}")
    print(f"{'카테고리':<16} {'성공':>4} {'법령참조':>8} {'구조화':>6} {'평균길이':>8} {'평균시간':>8}")
    print(f"{'─'*16} {'─'*4} {'─'*8} {'─'*6} {'─'*8} {'─'*8}")

    categories = sorted(set(r["category"] for r in results))
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_ok = [r for r in cat_results if r["status"] == "OK"]
        if cat_ok:
            law_pct = sum(1 for r in cat_ok if r["has_law_ref"]) * 100 // len(cat_ok)
            struct_pct = sum(1 for r in cat_ok if r["has_structured"]) * 100 // len(cat_ok)
            avg_l = round(sum(r["answer_len"] for r in cat_ok) / len(cat_ok))
            avg_t = round(sum(r["elapsed"] for r in cat_ok) / len(cat_ok), 1)
            print(f"{cat:<16} {len(cat_ok):>3}/5 {law_pct:>6}% {struct_pct:>5}% {avg_l:>7}자 {avg_t:>7}s")
        else:
            print(f"{cat:<16}   0/5      -      -        -        -")

    # ── Tier Distribution ──
    print(f"\n{'─' * 80}")
    print("🔄 Tier 분배")
    print(f"{'─' * 80}")
    tier_counts = {}
    for r in ok_results:
        t = str(r.get("tier", "N/A"))
        tier_counts[t] = tier_counts.get(t, 0) + 1
    for t, c in sorted(tier_counts.items()):
        print(f"  Tier {t}: {c}건 ({c*100//len(ok_results) if ok_results else 0}%)")

    # ── Error Details ──
    if errors:
        print(f"\n{'─' * 80}")
        print("❌ 에러 상세")
        print(f"{'─' * 80}")
        for r in errors:
            print(f"  Q{r['idx']}. [{r['category']}] {r['question'][:40]}...")
            print(f"      → {r['status']} ({r['elapsed']}s)")

    if rate_limited:
        print(f"\n{'─' * 80}")
        print("⏳ Rate Limited 질문 목록")
        print(f"{'─' * 80}")
        for r in rate_limited:
            print(f"  Q{r['idx']}. [{r['category']}] {r['question'][:50]}...")

    # ── Sample Answers (first 5 successful) ──
    print(f"\n{'─' * 80}")
    print("📋 답변 샘플 (성공 질문 중 카테고리별 1건씩)")
    print(f"{'─' * 80}")
    shown_cats = set()
    for r in ok_results:
        if r["category"] not in shown_cats and len(shown_cats) < 10:
            shown_cats.add(r["category"])
            print(f"\nQ{r['idx']}. [{r['category']}] {r['question']}")
            print(f"  리더: {r['leader_name']} | Tier: {r['tier']} | {r['answer_len']}자 | {r['elapsed']}s")
            print(f"  답변: {r['answer_preview']}...")
            print()

    # ── Save full results to JSON ──
    output_path = "/home/peter120525/Lawmadi-OS/tests/test_100_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 전체 결과 저장: {output_path}")

    # ── Final Summary ──
    print(f"\n{'=' * 80}")
    print("🏁 최종 요약")
    print(f"{'=' * 80}")
    if ok_results:
        quality_score = round(
            (len(ok_results) / len(results)) * 30 +  # 성공률 30%
            (law_ref_count / len(ok_results)) * 35 +  # 법령 참조 35%
            (structured_count / len(ok_results)) * 20 +  # 구조화 20%
            (min(avg_len, 2000) / 2000) * 15,  # 답변 충실도 15%
            1
        )
        print(f"종합 품질 점수: {quality_score}/100")
        print(f"  - 응답 성공률: {len(ok_results)*100//len(results)}% (가중치 30%)")
        print(f"  - 법령 참조율: {law_ref_count*100//len(ok_results)}% (가중치 35%)")
        print(f"  - 구조화 응답률: {structured_count*100//len(ok_results)}% (가중치 20%)")
        print(f"  - 답변 충실도: 평균 {avg_len}자 (가중치 15%)")


if __name__ == "__main__":
    asyncio.run(main())
