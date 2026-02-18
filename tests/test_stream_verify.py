#!/usr/bin/env python3
"""이전 실패 질문 스트리밍 재검증"""
import asyncio, aiohttp, json, time

BASE = 'https://lawmadi-os-v60-938146962157.asia-northeast3.run.app'

test_queries = [
    ('정상#01', '이혼 절차가 궁금합니다'),
    ('법률#10', '행정소송법상 취소소송 제기 요건은?'),
    ('비정상#05', "'; DROP TABLE users; --"),
    ('정상#09', '임대차 계약 갱신권이 뭔가요?'),
    ('법률#07', '채권자취소권의 행사 요건은?'),
]

async def test_stream(session, label, query):
    start = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=180)
        async with session.post(f'{BASE}/ask-stream',
            json={'query': query, 'history': []}, timeout=timeout) as r:
            if r.status != 200:
                return f'  ❌ [{label}] HTTP {r.status}'
            text = ''
            leader = ''
            events = []
            ms_first = 0
            async for line_bytes in r.content:
                line = line_bytes.decode('utf-8', errors='replace').strip()
                if line.startswith('event: '):
                    evt = line[7:]
                    if evt not in events:
                        events.append(evt)
                elif line.startswith('data: '):
                    try:
                        p = json.loads(line[6:])
                        if events and events[-1] == 'chunk':
                            if not ms_first:
                                ms_first = int((time.time()-start)*1000)
                            text += p.get('text','')
                        elif events and events[-1] == 'done':
                            leader = p.get('leader','')
                            if p.get('full_text'):
                                text = p['full_text']
                        elif events and events[-1] == 'error':
                            ms = int((time.time()-start)*1000)
                            msg = p.get('message','')[:60]
                            return f'  ❌ [{label}] STREAM_ERROR {ms/1000:.1f}s | {msg}'
                    except json.JSONDecodeError:
                        pass

            ms = int((time.time()-start)*1000)
            if text.strip():
                return f'  ✅ [{label}] SUCCESS {ms/1000:.1f}s (첫청크 {ms_first/1000:.1f}s) {len(text)}자 leader={leader[:15]} events={events}'
            else:
                return f'  ⚠️  [{label}] EMPTY {ms/1000:.1f}s events={events}'
    except asyncio.TimeoutError:
        return f'  ⏰ [{label}] TIMEOUT'
    except Exception as e:
        return f'  ❌ [{label}] {e}'

async def main():
    print('━' * 60)
    print('  스트리밍 수정 검증 (이전 실패 질문 재테스트)')
    print('━' * 60)
    connector = aiohttp.TCPConnector(limit=2, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        for label, q in test_queries:
            result = await test_stream(session, label, q)
            print(result)
            await asyncio.sleep(3)

if __name__ == '__main__':
    asyncio.run(main())
