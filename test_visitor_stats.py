#!/usr/bin/env python3
"""
방문자 통계 시스템 테스트
"""
import sys
import os

# DB 환경변수 확인
print("=" * 80)
print("환경변수 확인")
print("=" * 80)
print(f"DB_DISABLED: {os.getenv('DB_DISABLED', 'not set')}")
print(f"CLOUD_SQL_INSTANCE: {os.getenv('CLOUD_SQL_INSTANCE', 'not set')[:50]}...")
print(f"DB_NAME: {os.getenv('DB_NAME', 'not set')}")
print()

# DB 클라이언트 임포트 테스트
print("=" * 80)
print("DB 클라이언트 임포트 테스트")
print("=" * 80)

try:
    from connectors.db_client_v2 import (
        init_visitor_stats_table,
        record_visit,
        get_visitor_stats
    )
    print("✅ db_client_v2 임포트 성공")
except Exception as e:
    print(f"❌ db_client_v2 임포트 실패: {e}")
    sys.exit(1)

# 테이블 초기화
print()
print("=" * 80)
print("테이블 초기화")
print("=" * 80)
try:
    init_visitor_stats_table()
    print("✅ 테이블 초기화 완료")
except Exception as e:
    print(f"❌ 테이블 초기화 실패: {e}")

# 방문 기록 테스트
print()
print("=" * 80)
print("방문 기록 테스트")
print("=" * 80)
test_visitor_id = "192.168.1.100"
try:
    result = record_visit(test_visitor_id)
    print(f"✅ 방문 기록 결과: {result}")
except Exception as e:
    print(f"❌ 방문 기록 실패: {e}")

# 통계 조회 테스트
print()
print("=" * 80)
print("통계 조회 테스트")
print("=" * 80)
try:
    stats = get_visitor_stats()
    print(f"✅ 통계 조회 결과:")
    print(f"   - ok: {stats.get('ok')}")
    print(f"   - 오늘 방문자: {stats.get('today_visitors')}")
    print(f"   - 총 방문자: {stats.get('total_visitors')}")
    print(f"   - 오늘 방문 횟수: {stats.get('today_visits')}")
    print(f"   - 총 방문 횟수: {stats.get('total_visits')}")
except Exception as e:
    print(f"❌ 통계 조회 실패: {e}")

print()
print("=" * 80)
print("테스트 완료")
print("=" * 80)
