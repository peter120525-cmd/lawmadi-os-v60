#!/usr/bin/env python3
"""예시 질문 9개 → 리더 매칭 + 응답 길이 검증"""
import asyncio, aiohttp, json, time, os

BASE = os.getenv('LAWMADI_OS_API_URL', 'https://lawmadi-os-v60-938146962157.asia-northeast3.run.app')
ADMIN_KEY = os.getenv('ADMIN_KEY', '')

# 예시 질문 → 기대 리더
EXAMPLES = [
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

# 비법률 질문 3개 (500자 제한 검증)
NON_LEGAL = [
    ("날씨", "오늘 서울 날씨가 어때요?", "유나"),
    ("요리", "파스타 맛있게 만드는 방법 알려주세요", "유나"),
    ("여행", "일본 여행 추천 코스는?", "유나"),
]

async def test_query(session, label, query, expected_leader):
    start = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        headers = {'X-Admin-Key': ADMIN_KEY} if ADMIN_KEY else {}
        async with session.post(f'{BASE}/ask', json={'query': query, 'history': []}, timeout=timeout, headers=headers) as r:
            ms = int((time.time() - start) * 1000)
            body = await r.json()
            leader = body.get('leader', '')
            text = body.get('response', '')
            length = len(text)

            # 리더 매칭 확인
            leaders = [n.strip() for n in leader.split(',')]
            matched = expected_leader in leaders
            icon = '✅' if matched else '❌'

            return f'  {icon} [{label:6s}] {ms/1000:5.1f}s {length:4d}자 리더={leader:20s} 기대={expected_leader:5s} {query[:40]}', matched, length
    except Exception as e:
        return f'  ❌ [{label:6s}] ERROR: {e}', False, 0

async def main():
    print('=' * 70)
    print('  예시 질문 리더 매칭 + 응답 길이 검증')
    print(f'  대상: {BASE}')
    print('=' * 70)

    connector = aiohttp.TCPConnector(limit=2, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 법률 예시 질문
        print(f'\n{"━" * 70}')
        print(f'  법률 예시 질문 (9건) — 기대: 전문 리더 매칭, ~2000자')
        print(f'{"━" * 70}')

        legal_ok = 0
        legal_lens = []
        for label, q, expected in EXAMPLES:
            result, matched, length = await test_query(session, label, q, expected)
            print(result, flush=True)
            if matched: legal_ok += 1
            legal_lens.append(length)
            await asyncio.sleep(2)

        # 비법률 질문
        print(f'\n{"━" * 70}')
        print(f'  비법률 질문 (3건) — 기대: 유나(CCO), ~500자')
        print(f'{"━" * 70}')

        non_ok = 0
        non_lens = []
        for label, q, expected in NON_LEGAL:
            result, matched, length = await test_query(session, label, q, expected)
            print(result, flush=True)
            if matched: non_ok += 1
            non_lens.append(length)
            await asyncio.sleep(2)

        # 요약
        print(f'\n{"=" * 70}')
        print(f'  📊 결과 요약')
        print(f'{"=" * 70}')
        print(f'  법률 리더 매칭: {legal_ok}/9 {"✅" if legal_ok >= 7 else "⚠️"}')
        print(f'  법률 평균 글자수: {int(sum(legal_lens)/max(len(legal_lens),1))}자 (목표: ~2000자)')
        print(f'  비법률 리더 매칭: {non_ok}/3 {"✅" if non_ok == 3 else "⚠️"}')
        print(f'  비법률 평균 글자수: {int(sum(non_lens)/max(len(non_lens),1))}자 (목표: ~500자)')

if __name__ == '__main__':
    asyncio.run(main())
