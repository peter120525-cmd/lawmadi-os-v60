#!/usr/bin/env python3
"""
데이터베이스 점검 및 진단 도구
- DB 연결 상태 확인
- 테이블 구조 분석
- 데이터 통계 조회
"""
import os
import sys
from datetime import datetime, timedelta

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

from connectors.db_client_v2 import execute

def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def check_db_connection():
    """DB 연결 상태 확인"""
    print_header("1. 데이터베이스 연결 상태")

    db_disabled = os.getenv("DB_DISABLED", "0")
    if db_disabled == "1":
        print("❌ DB_DISABLED=1 (데이터베이스 비활성화됨)")
        return False

    # 필수 환경변수 확인
    required = ["CLOUD_SQL_INSTANCE", "DB_USER", "DB_PASS", "DB_NAME"]
    missing = [k for k in required if not os.getenv(k)]

    if missing:
        print(f"❌ 필수 환경변수 누락: {', '.join(missing)}")
        return False

    # 간단한 쿼리로 연결 테스트
    result = execute("SELECT 1 as test", fetch="one")
    if result.get("ok"):
        print("✅ 데이터베이스 연결 성공")
        print(f"   - Instance: {os.getenv('CLOUD_SQL_INSTANCE')}")
        print(f"   - Database: {os.getenv('DB_NAME')}")
        print(f"   - User: {os.getenv('DB_USER')}")
        return True
    else:
        print(f"❌ 데이터베이스 연결 실패: {result.get('error')}")
        return False

def check_tables():
    """테이블 목록 및 구조 확인"""
    print_header("2. 테이블 구조 분석")

    # PostgreSQL 테이블 목록 조회
    result = execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """, fetch="all")

    if not result.get("ok"):
        print(f"❌ 테이블 조회 실패: {result.get('error')}")
        return

    tables = result.get("data", [])
    if not tables:
        print("⚠️  생성된 테이블 없음")
        return

    print(f"\n📊 총 {len(tables)}개 테이블:")
    for row in tables:
        table_name = row[0]
        print(f"   - {table_name}")

        # 각 테이블의 컬럼 정보
        col_result = execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, params=(table_name,), fetch="all")

        if col_result.get("ok"):
            cols = col_result.get("data", [])
            for col in cols:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"      • {col[0]}: {col[1]} {nullable}")

def analyze_chat_history():
    """chat_history 데이터 분석 (메인 로그)"""
    print_header("3. 사용자 로그 분석 (chat_history)")

    # chat_history 테이블 존재 확인
    check = execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'chat_history'
        )
    """, fetch="one")

    if not check.get("ok") or not check.get("data")[0]:
        print("⚠️  chat_history 테이블이 존재하지 않습니다.")
        return

    # 총 로그 수
    result = execute("SELECT COUNT(*) FROM chat_history", fetch="one")
    if result.get("ok"):
        total = result.get("data")[0]
        print(f"\n📝 총 로그 수: {total:,}건")

    # 최근 24시간 로그
    result = execute("""
        SELECT COUNT(*) FROM chat_history
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    """, fetch="one")
    if result.get("ok"):
        recent = result.get("data")[0]
        print(f"📅 최근 24시간: {recent:,}건")

    # Swarm 모드 비율
    result = execute("""
        SELECT
            COUNT(CASE WHEN swarm_mode = TRUE THEN 1 END) as swarm_count,
            COUNT(*) as total_count
        FROM chat_history
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """, fetch="one")
    if result.get("ok") and result.get("data"):
        swarm, total = result.get("data")
        swarm_rate = (swarm / total * 100) if total > 0 else 0
        print(f"🐝 Swarm 모드 사용률 (최근 7일): {swarm_rate:.1f}% ({swarm}/{total})")

    # 리더별 호출 통계
    print("\n👥 리더별 호출 통계 (상위 10개):")
    result = execute("""
        SELECT
            leader_code,
            COUNT(*) as call_count,
            AVG(latency_ms) as avg_latency,
            COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count
        FROM chat_history
        GROUP BY leader_code
        ORDER BY call_count DESC
        LIMIT 10
    """, fetch="all")

    if result.get("ok"):
        rows = result.get("data", [])
        if rows:
            print(f"\n{'리더':<30} {'호출수':<10} {'평균응답':<12} {'성공률':<10}")
            print("-" * 70)
            for row in rows:
                leader, count, avg_lat, success = row
                success_rate = (success / count * 100) if count > 0 else 0
                avg_lat_val = avg_lat if avg_lat else 0
                print(f"{leader:<30} {count:<10} {avg_lat_val:<12.1f}ms {success_rate:<10.1f}%")
        else:
            print("   (데이터 없음)")

    # 질문 유형별 통계
    print("\n📊 질문 유형별 통계:")
    result = execute("""
        SELECT
            query_category,
            COUNT(*) as count
        FROM chat_history
        WHERE query_category IS NOT NULL
        GROUP BY query_category
        ORDER BY count DESC
        LIMIT 10
    """, fetch="all")

    if result.get("ok"):
        rows = result.get("data", [])
        if rows:
            print(f"\n{'유형':<20} {'건수':<10}")
            print("-" * 35)
            for row in rows:
                category, count = row
                print(f"{category:<20} {count:<10}")
        else:
            print("   (데이터 없음)")

    # 최근 질문 샘플 (10개)
    print("\n💬 최근 질문 샘플:")
    result = execute("""
        SELECT
            created_at,
            LEFT(user_query, 60) as query_preview,
            leader_code,
            query_category,
            status
        FROM chat_history
        ORDER BY created_at DESC
        LIMIT 10
    """, fetch="all")

    if result.get("ok"):
        rows = result.get("data", [])
        for idx, row in enumerate(rows, 1):
            created, query, leader, category, status = row
            status_icon = "✅" if status == "success" else "❌"
            category_tag = f"[{category}]" if category else ""
            print(f"\n{idx}. {status_icon} {category_tag} [{leader}] {created}")
            print(f"   {query}...")

def analyze_visitor_stats():
    """방문자 통계 분석"""
    print_header("4. 방문자 통계 분석")

    # visitor_stats 테이블 존재 확인
    check = execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'visitor_stats'
        )
    """, fetch="one")

    if not check.get("ok") or not check.get("data")[0]:
        print("⚠️  visitor_stats 테이블이 존재하지 않습니다.")
        return

    # 총 방문자 수
    result = execute("SELECT COUNT(*) FROM visitor_stats", fetch="one")
    if result.get("ok"):
        total = result.get("data")[0]
        print(f"\n👥 총 방문자 수: {total:,}명")

    # 오늘 방문자
    result = execute("""
        SELECT unique_visitors, total_visits
        FROM daily_visitors
        WHERE visit_date = CURRENT_DATE
    """, fetch="one")

    if result.get("ok") and result.get("data"):
        unique, total = result.get("data")
        print(f"📅 오늘 방문자: {unique:,}명 (총 {total:,}회 방문)")
    else:
        print("📅 오늘 방문자: 0명")

    # 최근 7일 추이
    print("\n📈 최근 7일 방문자 추이:")
    result = execute("""
        SELECT
            visit_date,
            unique_visitors,
            total_visits
        FROM daily_visitors
        WHERE visit_date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY visit_date DESC
    """, fetch="all")

    if result.get("ok"):
        rows = result.get("data", [])
        if rows:
            print(f"\n{'날짜':<12} {'방문자':<10} {'방문횟수':<10}")
            print("-" * 35)
            for row in rows:
                date, unique, total = row
                print(f"{date} {unique:<10} {total:<10}")
        else:
            print("   (데이터 없음)")

def analyze_cache():
    """캐시 통계"""
    print_header("5. DRF 캐시 분석")

    # 총 캐시 항목
    result = execute("SELECT COUNT(*) FROM drf_cache", fetch="one")
    if result.get("ok"):
        total = result.get("data")[0]
        print(f"\n💾 총 캐시 항목: {total:,}개")

    # 만료된 항목
    result = execute("""
        SELECT COUNT(*) FROM drf_cache
        WHERE expires_at <= NOW()
    """, fetch="one")
    if result.get("ok"):
        expired = result.get("data")[0]
        print(f"⏰ 만료된 항목: {expired:,}개")

    # 유효한 항목
    result = execute("""
        SELECT COUNT(*) FROM drf_cache
        WHERE expires_at > NOW()
    """, fetch="one")
    if result.get("ok"):
        valid = result.get("data")[0]
        print(f"✅ 유효한 항목: {valid:,}개")

def main():
    print("\n" + "🔍" * 40)
    print("   Lawmadi OS 데이터베이스 진단 도구")
    print("🔍" * 40)

    # 1. 연결 확인
    if not check_db_connection():
        print("\n❌ 데이터베이스 연결 실패. 진단을 중단합니다.")
        sys.exit(1)

    # 2. 테이블 구조
    check_tables()

    # 3. chat_history 분석 (메인 로그)
    analyze_chat_history()

    # 4. 방문자 통계
    analyze_visitor_stats()

    # 5. 캐시 분석
    analyze_cache()

    print("\n" + "=" * 80)
    print("✅ 진단 완료")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
