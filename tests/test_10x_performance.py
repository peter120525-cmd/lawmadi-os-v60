#!/usr/bin/env python3
"""홈페이지 예시 질문 10회 반복 — 성능 및 품질 테스트"""
import asyncio, aiohttp, json, time, os, statistics

BASE = os.getenv('LAWMADI_OS_API_URL', 'https://lawmadi-os-v60-938146962157.asia-northeast3.run.app')
ADMIN_KEY = os.getenv('ADMIN_KEY', '')
ROUNDS = 10

LEGAL_QUESTIONS = [
    ("전세분쟁", "2년 전인 2024년 3월에 전세 계약을 했습니다. 보증금은 3억원이고, 2026년 3월이 만기입니다. 그런데 집주인이 갑자기 집을 팔겠다고 하면서 2개월 뒤에 나가달라고 합니다.", "온유"),
    ("부동산", "아버지께서 2020년 1월에 제 명의로 아파트를 구입하셨습니다. 실제 돈은 아버지가 내셨고, 저는 그냥 명의만 빌려드린 것입니다. 그런데 지금 제 빚 때문에 경매가 진행 중입니다.", "보늬"),
    ("노동문제", "회사에서 갑자기 해고 통보를 받았습니다. 제가 3번이나 지각을 했다는 이유인데, 사실 그 날들은 모두 지하철 고장 때문이었습니다.", "담우"),
    ("이혼·양육", "남편과 이혼을 준비하고 있습니다. 아이가 7살인데, 양육권과 재산분할은 어떻게 진행되나요? 남편 명의의 아파트와 공동 대출이 있습니다.", "산들"),
    ("상속분쟁", "아버지가 돌아가시면서 유언장 없이 아파트 1채와 예금 2억원을 남기셨습니다. 형제가 3명인데, 큰형이 혼자 다 가져가겠다고 합니다.", "세움"),
    ("교통사고", "지난주 교차로에서 교통사고가 났습니다. 상대방이 신호위반이었는데, 보험사에서 저한테도 과실 30%를 주장하고 있습니다.", "하늬"),
    ("사기·횡령", "지인에게 사업자금으로 5천만원을 빌려줬는데, 알고 보니 처음부터 갚을 생각이 없었던 것 같습니다. 차용증은 있지만 공증은 안 했습니다.", "무결"),
    ("명예훼손", "전 직장 동료가 SNS에 저에 대한 허위사실을 올려서 퇴사까지 하게 되었습니다. 게시글 캡처는 해두었는데 어떻게 대응해야 하나요?", "미소"),
    ("의료사고", "어머니가 간단한 수술을 받았는데 의료진 실수로 합병증이 생겨 재수술을 받아야 합니다. 병원에서는 불가항력이라고 하는데 손해배상 청구가 가능한가요?", "연우"),
]

NON_LEGAL = [
    ("날씨", "오늘 서울 날씨가 어때요?", "유나"),
    ("요리", "파스타 맛있게 만드는 방법 알려주세요", "유나"),
    ("여행", "일본 여행 추천 코스는?", "유나"),
]

ALL_QUESTIONS = LEGAL_QUESTIONS + NON_LEGAL

# 결과 저장: {label: [{round, latency_ms, length, leader, matched, error}]}
results = {q[0]: [] for q in ALL_QUESTIONS}


async def call_ask(session, label, query, expected_leader, round_num):
    start = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        headers = {'X-Admin-Key': ADMIN_KEY} if ADMIN_KEY else {}
        async with session.post(
            f'{BASE}/ask',
            json={'query': query, 'history': []},
            timeout=timeout,
            headers=headers,
        ) as r:
            ms = int((time.time() - start) * 1000)
            body = await r.json()
            leader = body.get('leader', '')
            text = body.get('response', '')
            length = len(text)
            leaders = [n.strip() for n in leader.split(',')]
            matched = expected_leader in leaders
            has_law_ref = any(kw in text for kw in ['제', '조', '법', '판례', '대법원'])
            return {
                'round': round_num,
                'latency_ms': ms,
                'length': length,
                'leader': leader,
                'matched': matched,
                'has_law_ref': has_law_ref,
                'error': None,
                'status': r.status,
            }
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        return {
            'round': round_num,
            'latency_ms': ms,
            'length': 0,
            'leader': '',
            'matched': False,
            'has_law_ref': False,
            'error': str(e),
            'status': 0,
        }


async def run_round(round_num):
    connector = aiohttp.TCPConnector(limit=2, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        for label, query, expected in ALL_QUESTIONS:
            r = await call_ask(session, label, query, expected, round_num)
            results[label].append(r)

            icon = '✅' if r['matched'] else '❌'
            err = f" ERROR:{r['error'][:40]}" if r['error'] else ''
            print(
                f"  R{round_num:02d} {icon} [{label:6s}] "
                f"{r['latency_ms']/1000:5.1f}s  {r['length']:4d}자  "
                f"리더={r['leader'][:15]}{err}",
                flush=True,
            )
            await asyncio.sleep(1.5)


def print_summary():
    print(f"\n{'=' * 80}")
    print(f"  📊 10회 반복 테스트 종합 결과")
    print(f"{'=' * 80}")

    # 질문별 상세
    print(f"\n{'━' * 80}")
    print(f"  {'질문':8s} {'매칭률':>8s} {'평균응답':>8s} {'P50':>7s} {'P95':>7s} "
          f"{'평균길이':>8s} {'길이편차':>8s} {'법률참조':>8s} {'에러':>5s}")
    print(f"{'━' * 80}")

    total_match = 0
    total_count = 0
    all_latencies = []
    all_lengths = []
    legal_match = 0
    legal_count = 0
    non_legal_match = 0
    non_legal_count = 0

    for label, query, expected in ALL_QUESTIONS:
        data = results[label]
        ok = [d for d in data if not d['error']]
        errors = [d for d in data if d['error']]

        if not ok:
            print(f"  {label:8s}  모든 요청 실패 ({len(errors)} errors)")
            continue

        latencies = [d['latency_ms'] for d in ok]
        lengths = [d['length'] for d in ok]
        matches = sum(1 for d in ok if d['matched'])
        law_refs = sum(1 for d in ok if d['has_law_ref'])

        avg_lat = statistics.mean(latencies)
        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else latencies[-1]
        avg_len = statistics.mean(lengths)
        std_len = statistics.stdev(lengths) if len(lengths) >= 2 else 0

        is_legal = label not in ('날씨', '요리', '여행')

        total_match += matches
        total_count += len(ok)
        all_latencies.extend(latencies)
        all_lengths.extend(lengths)

        if is_legal:
            legal_match += matches
            legal_count += len(ok)
        else:
            non_legal_match += matches
            non_legal_count += len(ok)

        match_pct = f"{matches}/{len(ok)}"
        print(
            f"  {label:8s} {match_pct:>8s} "
            f"{avg_lat/1000:7.1f}s {p50/1000:6.1f}s {p95/1000:6.1f}s "
            f"{avg_len:7.0f}자 {std_len:7.0f}자 "
            f"{law_refs:>5d}/{len(ok):d}  "
            f"{len(errors):>3d}"
        )

    # 종합 통계
    print(f"\n{'=' * 80}")
    print(f"  📈 종합 통계")
    print(f"{'=' * 80}")

    if all_latencies:
        print(f"  총 요청 수       : {total_count}건 (에러 제외)")
        print(f"  전체 리더 매칭률 : {total_match}/{total_count} ({total_match/total_count*100:.1f}%)")
        if legal_count:
            print(f"  법률 리더 매칭률 : {legal_match}/{legal_count} ({legal_match/legal_count*100:.1f}%)")
        if non_legal_count:
            print(f"  비법률 매칭률    : {non_legal_match}/{non_legal_count} ({non_legal_match/non_legal_count*100:.1f}%)")
        print()
        print(f"  응답 시간 (전체)")
        print(f"    평균 : {statistics.mean(all_latencies)/1000:.1f}s")
        print(f"    P50  : {statistics.median(all_latencies)/1000:.1f}s")
        p95_all = sorted(all_latencies)[int(len(all_latencies) * 0.95)]
        print(f"    P95  : {p95_all/1000:.1f}s")
        print(f"    최소 : {min(all_latencies)/1000:.1f}s")
        print(f"    최대 : {max(all_latencies)/1000:.1f}s")
        print()
        print(f"  응답 길이 (전체)")
        print(f"    평균 : {statistics.mean(all_lengths):.0f}자")
        if len(all_lengths) >= 2:
            print(f"    표준편차: {statistics.stdev(all_lengths):.0f}자")
        print(f"    최소 : {min(all_lengths)}자")
        print(f"    최대 : {max(all_lengths)}자")

    # 품질 등급
    print(f"\n{'=' * 80}")
    print(f"  🏆 품질 등급 판정")
    print(f"{'=' * 80}")

    if all_latencies and total_count:
        match_rate = total_match / total_count * 100
        avg_lat_s = statistics.mean(all_latencies) / 1000
        error_rate = (ROUNDS * len(ALL_QUESTIONS) - total_count) / (ROUNDS * len(ALL_QUESTIONS)) * 100

        scores = []
        # 매칭 점수 (40점)
        if match_rate >= 90: scores.append(('리더 매칭', 40, 'A+'))
        elif match_rate >= 80: scores.append(('리더 매칭', 35, 'A'))
        elif match_rate >= 70: scores.append(('리더 매칭', 30, 'B+'))
        elif match_rate >= 60: scores.append(('리더 매칭', 25, 'B'))
        else: scores.append(('리더 매칭', 15, 'C'))

        # 응답 시간 점수 (30점)
        if avg_lat_s <= 5: scores.append(('응답 속도', 30, 'A+'))
        elif avg_lat_s <= 10: scores.append(('응답 속도', 25, 'A'))
        elif avg_lat_s <= 15: scores.append(('응답 속도', 20, 'B'))
        elif avg_lat_s <= 20: scores.append(('응답 속도', 15, 'C'))
        else: scores.append(('응답 속도', 10, 'D'))

        # 안정성 점수 (30점)
        if error_rate == 0: scores.append(('안정성', 30, 'A+'))
        elif error_rate <= 2: scores.append(('안정성', 25, 'A'))
        elif error_rate <= 5: scores.append(('안정성', 20, 'B'))
        elif error_rate <= 10: scores.append(('안정성', 15, 'C'))
        else: scores.append(('안정성', 10, 'D'))

        total_score = sum(s[1] for s in scores)
        for name, score, grade in scores:
            print(f"  {name:12s}: {score:2d}점 ({grade})")
        print(f"  {'─' * 30}")
        print(f"  {'종합':12s}: {total_score}/100점", end='')
        if total_score >= 90: print(' 🏆 S등급')
        elif total_score >= 80: print(' 🥇 A등급')
        elif total_score >= 70: print(' 🥈 B등급')
        elif total_score >= 60: print(' 🥉 C등급')
        else: print(' ⚠️ D등급 (개선 필요)')

    print(f"\n{'=' * 80}")


async def main():
    print(f"{'=' * 80}")
    print(f"  Lawmadi OS v60 — 홈페이지 예시 질문 10회 반복 성능/품질 테스트")
    print(f"  대상: {BASE}")
    print(f"  질문: 법률 {len(LEGAL_QUESTIONS)}개 + 비법률 {len(NON_LEGAL)}개 = {len(ALL_QUESTIONS)}개")
    print(f"  반복: {ROUNDS}회 (총 {ROUNDS * len(ALL_QUESTIONS)}건)")
    print(f"{'=' * 80}")

    if not ADMIN_KEY:
        print(f"\n  ⚠️  ADMIN_KEY 미설정: Rate Limit에 걸릴 수 있습니다.")
        print(f"     사용법: ADMIN_KEY=<MCP_API_KEY> python tests/test_10x_performance.py\n")

    for r in range(1, ROUNDS + 1):
        print(f"\n{'─' * 80}")
        print(f"  🔄 Round {r}/{ROUNDS}")
        print(f"{'─' * 80}")
        await run_round(r)

    print_summary()

    # JSON 결과 저장
    out_path = os.path.join(os.path.dirname(__file__), 'test_10x_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 상세 결과 저장: {out_path}")


if __name__ == '__main__':
    asyncio.run(main())
