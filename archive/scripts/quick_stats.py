#!/usr/bin/env python3
"""빠른 사용자 및 리더 통계 조회"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/workspaces/lawmadi-os-v50')

from connectors.db_client_v2 import execute

print("\n" + "=" * 80)
print("📊 오늘의 통계 (Lawmadi OS)")
print("=" * 80)

# 1. 오늘 방문자 수
print("\n🌟 오늘의 사용자 현황")
print("-" * 80)

result = execute("""
    SELECT unique_visitors, total_visits
    FROM daily_visitors
    WHERE visit_date = CURRENT_DATE
""", fetch="one")

if result.get("ok") and result.get("data"):
    unique, total = result.get("data")
    print(f"✅ 오늘 방문자: {unique}명 (총 {total}회 방문)")
else:
    print("📅 오늘 방문자: 0명 (아직 방문 기록 없음)")

# 최근 24시간 질문 수
result = execute("""
    SELECT COUNT(*) FROM chat_history
    WHERE created_at >= NOW() - INTERVAL '24 hours'
""", fetch="one")

if result.get("ok"):
    count = result.get("data")[0]
    print(f"💬 최근 24시간 질문: {count}건")

# 총 누적
result = execute("SELECT COUNT(*) FROM chat_history", fetch="one")
if result.get("ok"):
    total = result.get("data")[0]
    print(f"📈 총 누적 질문: {total}건")

# 2. 리더별 호출 통계
print("\n🏆 가장 많이 호출된 리더 (전체 기간)")
print("-" * 80)

result = execute("""
    SELECT
        leader_code,
        COUNT(*) as call_count,
        AVG(latency_ms) as avg_latency,
        COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count
    FROM chat_history
    WHERE leader_code IS NOT NULL
    GROUP BY leader_code
    ORDER BY call_count DESC
    LIMIT 10
""", fetch="all")

if result.get("ok"):
    rows = result.get("data", [])
    if rows:
        print(f"\n{'순위':<6} {'리더 코드':<15} {'호출수':<10} {'평균응답':<12} {'성공률':<10}")
        print("-" * 70)
        for idx, row in enumerate(rows, 1):
            leader, count, avg_lat, success = row
            leader_str = leader if leader else "Unknown"
            success_rate = (success / count * 100) if count > 0 else 0
            avg_lat_val = avg_lat if avg_lat is not None else 0

            # 순위 이모지
            rank_emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."

            print(f"{rank_emoji:<6} {leader_str:<15} {count:<10} {avg_lat_val:<12.1f}ms {success_rate:<10.1f}%")
    else:
        print("   (데이터 없음)")

# 3. 최근 24시간 리더 통계
print("\n🔥 최근 24시간 리더 통계")
print("-" * 80)

result = execute("""
    SELECT
        leader_code,
        COUNT(*) as call_count
    FROM chat_history
    WHERE created_at >= NOW() - INTERVAL '24 hours'
        AND leader_code IS NOT NULL
    GROUP BY leader_code
    ORDER BY call_count DESC
    LIMIT 5
""", fetch="all")

if result.get("ok"):
    rows = result.get("data", [])
    if rows:
        print(f"\n{'리더 코드':<15} {'호출수':<10}")
        print("-" * 30)
        for row in rows:
            leader, count = row
            print(f"{leader:<15} {count:<10}")
    else:
        print("   (최근 24시간 데이터 없음)")

# 4. Swarm 모드 통계
print("\n🐝 Swarm 모드 현황")
print("-" * 80)

result = execute("""
    SELECT
        COUNT(CASE WHEN swarm_mode = TRUE THEN 1 END) as swarm_count,
        COUNT(*) as total_count
    FROM chat_history
    WHERE created_at >= NOW() - INTERVAL '24 hours'
""", fetch="one")

if result.get("ok") and result.get("data"):
    swarm, total = result.get("data")
    swarm_rate = (swarm / total * 100) if total > 0 else 0
    print(f"최근 24시간 Swarm 사용: {swarm}건 / {total}건 ({swarm_rate:.1f}%)")

# 5. 최근 질문 카테고리
print("\n📂 최근 24시간 질문 유형")
print("-" * 80)

result = execute("""
    SELECT
        query_category,
        COUNT(*) as count
    FROM chat_history
    WHERE created_at >= NOW() - INTERVAL '24 hours'
        AND query_category IS NOT NULL
    GROUP BY query_category
    ORDER BY count DESC
    LIMIT 5
""", fetch="all")

if result.get("ok"):
    rows = result.get("data", [])
    if rows:
        print(f"\n{'카테고리':<20} {'건수':<10}")
        print("-" * 35)
        for row in rows:
            category, count = row
            print(f"{category:<20} {count:<10}")
    else:
        print("   (카테고리 데이터 없음)")

print("\n" + "=" * 80)
print("✅ 통계 조회 완료")
print("=" * 80 + "\n")
