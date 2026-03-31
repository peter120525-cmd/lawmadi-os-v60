import logging
from connectors.validator import LawmadiValidator
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import json
from .db_client import (
    _db_enabled,
    get_connection,
    release_connection,
    logger,
    validator
)

# ⚠️ SYNC: main.py:85의 OS_VERSION과 동기화 필요
_ENV_VERSION = "v60.0.0"


def execute(query: str, params=None, fetch="all"):
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
 
    if conn is None:
       return {"ok": False, "error": "DB_CONN_FAIL"}

    cur = None


    try:
        cur = conn.cursor()
        cur.execute(query, params or ())

        if fetch == "one":
            data = cur.fetchone()
        elif fetch == "all":
            data = cur.fetchall()
        else:
            data = None
        conn.commit()

        return {"ok": True, "data": data}

    except Exception as e:
        logger.error(f"⚠️ [DB] execute 실패: {e}")
        return {"ok": False, "error": "database_error"}

    finally:
        if cur: cur.close()
        if conn:
           release_connection(conn)

# =====================================================
# 🛡️ DRF Cache Interface (LMD-CONST-005 강화 버전)
# =====================================================

def cache_get(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    [IT 기술: Integrity Validation] 
    DB에서 캐시를 읽어올 때 반드시 서명 검증을 수행하여 데이터 오염을 차단합니다.
    """
    
    if not _db_enabled(): return None

    conn = get_connection()
    if conn is None:
        return None

    cur = None
    try:
        cur = conn.cursor()
        # 만료되지 않은 데이터와 서명을 함께 조회
        cur.execute(
            "SELECT content, signature FROM drf_cache WHERE cache_key = %s AND expires_at > NOW()",
            (cache_key,)
        )
        row = cur.fetchone()
        
        if row:
            content_data, stored_signature = row
            # L5 Validator를 통한 무결성 검증 (데이터 위변조 방지)
            if validator.verify_signature(content_data, stored_signature):
                return content_data
            else:
                logger.critical(f"🚨 [DB] 무결성 위반 감지: {cache_key} 캐시 폐기")
        return None

    except Exception as e:
        logger.warning(f"⚠️ [DB] cache_get 장애 복구 모드 작동: {e}")
        return None
    finally:
        if cur:
            cur.close()

        if conn:
            release_connection(conn)


def cache_set(cache_key: str, content: Dict[str, Any], ttl_seconds: int = 3600):
    """
    [IT 기술: Secure Serialization]
    Validator와 동일한 서명 규격(ensure_ascii=False)을 적용하여 캐시를 저장합니다.
    """
    if not _db_enabled(): return

    conn = get_connection()
    cur = None
    try:
        # Validator의 로직을 사용하여 일관된 서명 생성
        signature = validator.generate_signature(content)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        cur = conn.cursor()
        # UPSERT 로직: 기존 키가 있으면 업데이트하여 중복 방지
        cur.execute(
            """
            INSERT INTO drf_cache (cache_key, content, signature, expires_at, env_version)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (cache_key)
            DO UPDATE SET 
                content = EXCLUDED.content, 
                signature = EXCLUDED.signature, 
                expires_at = EXCLUDED.expires_at,
                created_at = NOW();
            """,
            (cache_key, json.dumps(content, ensure_ascii=False), signature, expires_at, _ENV_VERSION)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"⚠️ [DB] cache_set 저장 실패: {e}")
    finally:
         if cur:
            cur.close()

         if conn:
             release_connection(conn)


# =====================================================
# 🚦 Rate Limit Interface (Atomic Update 강화 버전)
# =====================================================

def rate_limit_check(provider: str, limit: int) -> bool:
    """호출 가능 여부 확인 (Fail-soft 설계)"""
    if not _db_enabled(): return True

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT call_count, window_end FROM rate_limit_tracker WHERE provider = %s",
            (provider,)
        )
        row = cur.fetchone()

        if not row: return True

        call_count, window_end = row
        # 윈도우가 만료되었으면 새 카운트 허용
        if window_end <= datetime.now(timezone.utc):
            return True

        return call_count < limit
    except Exception as e:
        logger.warning(f"⚠️ [DB] rate_limit_check 스킵: {e}")
        return True
    finally:
        if cur:
           cur.close()

        if conn:
           release_connection(conn)

def rate_limit_hit(provider: str, window_seconds: int = 60):
    """
    [IT 기술: Atomic Incrementor]
    윈도우 만료 시 카운트를 리셋하고, 아닐 시 1을 증가시키는 원자적 UPSERT를 수행합니다.
    """
    if not _db_enabled(): return

    conn = get_connection()
    cur = None
    try:
        now = datetime.now(timezone.utc)
        new_window_end = now + timedelta(seconds=window_seconds)

        cur = conn.cursor()
        # SQL 수준에서 윈도우 교체 및 카운트 증가를 한 번에 처리 (Race Condition 방어)
        cur.execute(
            """
            INSERT INTO rate_limit_tracker (provider, call_count, window_start, window_end, env_version)
            VALUES (%s, 1, %s, %s, %s)
            ON CONFLICT (provider)
            DO UPDATE SET
                call_count = CASE
                    WHEN rate_limit_tracker.window_end <= EXCLUDED.window_start THEN 1
                    ELSE rate_limit_tracker.call_count + 1
                END,
                window_start = CASE
                    WHEN rate_limit_tracker.window_end <= EXCLUDED.window_start THEN EXCLUDED.window_start
                    ELSE rate_limit_tracker.window_start
                END,
                window_end = CASE
                    WHEN rate_limit_tracker.window_end <= EXCLUDED.window_start THEN EXCLUDED.window_end
                    ELSE rate_limit_tracker.window_end
                END;
            """,
            (provider, now, new_window_end, _ENV_VERSION)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"⚠️ [DB] rate_limit_hit 업데이트 실패: {e}")
    finally:
        if cur: cur.close()
        if conn:
           release_connection(conn)
def rate_limit_check_and_hit(provider: str, limit: int, window_seconds: int = 60) -> bool:
    """
    원자적 rate limit 체크+기록 (TOCTOU 방지).
    한도 내이면 카운트 증가 후 True, 초과면 증가 없이 False 반환.
    """
    if not _db_enabled():
        return True

    conn = get_connection()
    cur = None
    try:
        now = datetime.now(timezone.utc)
        new_window_end = now + timedelta(seconds=window_seconds)

        cur = conn.cursor()
        # 단일 쿼리로 체크+증가를 원자적으로 수행
        # 항상 count+1 → RETURNING에서 count <= limit 판정
        cur.execute(
            """
            INSERT INTO rate_limit_tracker (provider, call_count, window_start, window_end, env_version)
            VALUES (%s, 1, %s, %s, %s)
            ON CONFLICT (provider)
            DO UPDATE SET
                call_count = CASE
                    WHEN rate_limit_tracker.window_end <= %s THEN 1
                    ELSE rate_limit_tracker.call_count + 1
                END,
                window_start = CASE
                    WHEN rate_limit_tracker.window_end <= %s THEN %s
                    ELSE rate_limit_tracker.window_start
                END,
                window_end = CASE
                    WHEN rate_limit_tracker.window_end <= %s THEN %s
                    ELSE rate_limit_tracker.window_end
                END
            RETURNING call_count, (call_count <= %s) AS allowed;
            """,
            (provider, now, new_window_end, _ENV_VERSION,
             now, now, now, now, new_window_end, limit)
        )
        row = cur.fetchone()
        conn.commit()
        if row:
            return bool(row[1])  # allowed
        return True
    except Exception as e:
        logger.warning(f"⚠️ [DB] rate_limit_check_and_hit 실패 (fail-soft): {e}")
        return True
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def add_audit_log(
    query: str,
    response: str,
    leader: str,
    status: str,
    latency_ms: int
):
    """
    [Lawmadi Audit Trail 인터페이스]
    Fail-soft 설계
    """
    if not _db_enabled():
        return

    conn = get_connection()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                query TEXT,
                response TEXT,
                leader VARCHAR(50),
                status VARCHAR(20),
                latency_ms INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                env_version VARCHAR(50)
            )
        """)

        # Truncate query/response to prevent unbounded storage growth
        _MAX_AUDIT_QUERY = 2000
        _MAX_AUDIT_RESPONSE = 10000
        truncated_query = query[:_MAX_AUDIT_QUERY] if query else ""
        truncated_response = response[:_MAX_AUDIT_RESPONSE] if response else ""

        cur.execute("""
            INSERT INTO audit_logs
            (query, response, leader, status, latency_ms, env_version)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            truncated_query,
            truncated_response,
            leader,
            status,
            latency_ms,
            _ENV_VERSION
        ))

        conn.commit()

    except Exception as e:
        logger.warning(f"⚠️ [Audit] 기록 실패: {e}")
    finally:
        if cur: cur.close()
        if conn:
          release_connection(conn)


# =====================================================
# 💬 Chat History Table
# =====================================================

def init_chat_history_table():
    """채팅 기록 테이블 초기화"""
    if not _db_enabled():
        return

    conn = None
    cur = None
    try:
        conn = get_connection()
        if conn is None:
            logger.warning("⚠️ [ChatHistory] DB 연결 실패로 테이블 초기화 스킵")
            return
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(64),
                user_query TEXT,
                ai_response TEXT,
                leader_code VARCHAR(50),
                status VARCHAR(20),
                latency_ms INTEGER,
                visitor_id VARCHAR(64),
                swarm_mode BOOLEAN DEFAULT FALSE,
                leaders_used TEXT,
                query_category VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                env_version VARCHAR(50)
            )
        """)
        conn.commit()
        logger.info("✅ [ChatHistory] 테이블 초기화 완료")
    except Exception as e:
        logger.error(f"⚠️ [ChatHistory] 테이블 생성 실패: {e}")
        raise
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


# =====================================================
# 📊 Visitor Tracking System
# =====================================================

def init_visitor_stats_table():
    """방문자 통계 테이블 초기화"""
    if not _db_enabled():
        return

    conn = None
    cur = None
    try:
        conn = get_connection()
        if conn is None:
            logger.warning("⚠️ [Visitor] DB 연결 실패로 테이블 초기화 스킵")
            return
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS visitor_stats (
                id SERIAL PRIMARY KEY,
                visitor_id VARCHAR(64) UNIQUE NOT NULL,
                first_visit TIMESTAMPTZ DEFAULT NOW(),
                last_visit TIMESTAMPTZ DEFAULT NOW(),
                visit_count INTEGER DEFAULT 1,
                env_version VARCHAR(50)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_visitors (
                visit_date DATE PRIMARY KEY,
                unique_visitors INTEGER DEFAULT 0,
                total_visits INTEGER DEFAULT 0,
                env_version VARCHAR(50)
            )
        """)

        conn.commit()
        logger.info("✅ [Visitor] 통계 테이블 초기화 완료")
    except Exception as e:
        logger.error(f"⚠️ [Visitor] 테이블 생성 실패: {e}")
        raise
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def init_admin_tables():
    """Admin 비즈니스 메트릭 테이블 초기화 (lawyer_inquiries, feedback)"""
    if not _db_enabled():
        return

    conn = None
    cur = None
    try:
        conn = get_connection()
        if conn is None:
            logger.warning("⚠️ [Admin] DB 연결 실패로 테이블 초기화 스킵")
            return
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS lawyer_inquiries (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                phone VARCHAR(30),
                query_summary TEXT,
                leader VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                trace_id VARCHAR(64),
                rating VARCHAR(10),
                comment TEXT,
                query TEXT,
                leader VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        conn.commit()
        logger.info("✅ [Admin] lawyer_inquiries, feedback 테이블 초기화 완료")
    except Exception as e:
        logger.error(f"⚠️ [Admin] 테이블 생성 실패: {e}")
        raise
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def init_all_tables(max_retries=3, retry_delay=2.0):
    """
    모든 DB 테이블을 순차 초기화 (개별 재시도 포함).
    각 init 함수가 실패 시 지수 백오프로 재시도합니다.
    """
    import time as _time
    from .db_client import init_tables as _init_core

    from routes.paddle import init_paddle_tables

    _table_inits = [
        ("core", _init_core),
        ("chat_history", init_chat_history_table),
        ("visitor_stats", init_visitor_stats_table),
        ("admin", init_admin_tables),
        ("verification", init_verification_table),
        ("frontend_logs", init_frontend_logs_table),
        ("endpoint_logs", init_endpoint_logs_table),
        ("paddle", init_paddle_tables),
    ]

    failed = []
    for name, fn in _table_inits:
        for attempt in range(1, max_retries + 1):
            try:
                fn()
                break
            except Exception as e:
                if attempt < max_retries:
                    delay = retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"⚠️ [init_all_tables] {name} 실패 (시도 {attempt}/{max_retries}), "
                        f"{delay:.1f}초 후 재시도: {e}"
                    )
                    _time.sleep(delay)
                else:
                    logger.error(f"❌ [init_all_tables] {name} 최종 실패 ({max_retries}회): {e}")
                    failed.append(name)

    if failed:
        logger.error(f"❌ [init_all_tables] 실패 테이블: {failed}")
    else:
        logger.info("✅ [init_all_tables] 전체 테이블 초기화 완료")

    return failed


def record_visit(visitor_id: str) -> Dict[str, Any]:
    """
    방문 기록
    - visitor_id: 브라우저 fingerprint 또는 UUID
    - 신규 방문자인지 여부를 반환
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = None
    cur = None
    try:
        conn = get_connection()
        if conn is None:
            return {"ok": False, "error": "DB_CONN_FAIL"}
        cur = conn.cursor()
        now = datetime.now(timezone.utc)
        today = now.date()

        # 1. visitor_stats 업데이트 (UPSERT)
        cur.execute("""
            INSERT INTO visitor_stats (visitor_id, first_visit, last_visit, visit_count, env_version)
            VALUES (%s, %s, %s, 1, %s)
            ON CONFLICT (visitor_id)
            DO UPDATE SET
                last_visit = EXCLUDED.last_visit,
                visit_count = visitor_stats.visit_count + 1
            RETURNING (xmax = 0) AS is_new_visitor
        """, (visitor_id, now, now, _ENV_VERSION))

        result = cur.fetchone()
        is_new_visitor = result[0] if result else False

        # 2. daily_visitors 업데이트
        cur.execute("""
            INSERT INTO daily_visitors (visit_date, unique_visitors, total_visits, env_version)
            VALUES (%s, %s, 1, %s)
            ON CONFLICT (visit_date)
            DO UPDATE SET
                unique_visitors = daily_visitors.unique_visitors + %s,
                total_visits = daily_visitors.total_visits + 1
        """, (today, 1 if is_new_visitor else 0, _ENV_VERSION, 1 if is_new_visitor else 0))

        conn.commit()
        return {"ok": True, "is_new_visitor": is_new_visitor}

    except Exception as e:
        logger.error(f"⚠️ [Visitor] 기록 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def save_chat_history(
    user_query: str,
    ai_response: str,
    leader: str,
    status: str,
    latency_ms: int,
    visitor_id: Optional[str] = None,
    swarm_mode: bool = False,
    leaders_used: Optional[List[str]] = None,
    query_category: Optional[str] = None,
    user_email: Optional[str] = None,
    query_type: Optional[str] = None,
    is_admin: bool = False
) -> Dict[str, Any]:
    """
    채팅 기록 저장.
    - query_type: "general"(일반), "expert"(전문가), "leader_chat"(리더 채팅)
    - user_email: 로그인 사용자만 저장, 비로그인 시 None
    - is_admin: 관리자 테스트 여부 (True면 통계에서 제외 가능)
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        # chat_history 테이블에 새 컬럼 추가 (없으면)
        try:
            cur.execute("""
                ALTER TABLE chat_history
                ADD COLUMN IF NOT EXISTS status VARCHAR(20),
                ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
                ADD COLUMN IF NOT EXISTS visitor_id VARCHAR(64),
                ADD COLUMN IF NOT EXISTS swarm_mode BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS leaders_used TEXT,
                ADD COLUMN IF NOT EXISTS query_category VARCHAR(50),
                ADD COLUMN IF NOT EXISTS env_version VARCHAR(50),
                ADD COLUMN IF NOT EXISTS user_email VARCHAR(255),
                ADD COLUMN IF NOT EXISTS query_type VARCHAR(20),
                ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
        except Exception:
            conn.rollback()  # 트랜잭션 abort 상태 해소

        # 데이터 삽입
        leaders_str = ",".join(leaders_used) if leaders_used else leader

        cur.execute("""
            INSERT INTO chat_history (
                user_id, user_query, ai_response, leader_code,
                status, latency_ms, visitor_id, swarm_mode,
                leaders_used, query_category, user_email, query_type, is_admin, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            visitor_id or "anonymous",
            user_query,
            ai_response[:5000],
            leader,
            status,
            latency_ms,
            visitor_id,
            swarm_mode,
            leaders_str,
            query_category,
            user_email,
            query_type or "general",
            is_admin
        ))

        conn.commit()
        return {"ok": True}

    except Exception as e:
        logger.error(f"⚠️ [ChatHistory] 저장 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def classify_query_category(query: str) -> str:
    """
    질문 자동 분류
    - 키워드 기반 카테고리 분류
    """
    query_lower = query.lower()

    categories = {
        "임대차": ["전세", "월세", "임대", "임차", "보증금", "집주인"],
        "민사": ["손해배상", "계약", "채권", "채무", "소송", "민사"],
        "형사": ["고소", "고발", "형사", "범죄", "처벌", "벌금"],
        "가족법": ["이혼", "양육", "상속", "유언", "가족", "혼인"],
        "부동산": ["부동산", "매매", "등기", "아파트", "토지"],
        "노동": ["해고", "노동", "임금", "퇴직", "산재", "근로"],
        "행정": ["행정", "인허가", "과태료", "행정처분"],
        "지식재산": ["특허", "상표", "저작권", "지식재산"],
        "회사법": ["회사", "법인", "주주", "이사", "기업"],
        "세금": ["세금", "국세", "지방세", "증여세", "상속세"],
    }

    for category, keywords in categories.items():
        if any(kw in query_lower for kw in keywords):
            return category

    return "기타"


def get_leader_statistics(days: int = 30) -> Dict[str, Any]:
    """
    리더별 통계 조회
    - days: 최근 N일 데이터
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        # 리더별 호출 통계
        cur.execute("""
            SELECT
                leader_code,
                COUNT(*) as total_calls,
                AVG(latency_ms) as avg_latency,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count
            FROM chat_history
            WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)
            GROUP BY leader_code
            ORDER BY total_calls DESC
            LIMIT 20
        """, (days,))

        leaders = []
        for row in cur.fetchall():
            leader, total, avg_lat, success = row
            leaders.append({
                "leader": leader,
                "total_calls": total,
                "avg_latency_ms": round(avg_lat, 1) if avg_lat else 0,
                "success_count": success,
                "success_rate": round(success / total * 100, 1) if total > 0 else 0
            })

        return {
            "ok": True,
            "leaders": leaders,
            "period_days": days
        }

    except Exception as e:
        logger.error(f"⚠️ [LeaderStats] 조회 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def get_query_category_statistics(days: int = 30) -> Dict[str, Any]:
    """
    질문 유형별 통계
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT
                query_category,
                COUNT(*) as count
            FROM chat_history
            WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)
                AND query_category IS NOT NULL
            GROUP BY query_category
            ORDER BY count DESC
        """, (days,))

        categories = []
        for row in cur.fetchall():
            category, count = row
            categories.append({
                "category": category,
                "count": count
            })

        return {
            "ok": True,
            "categories": categories,
            "period_days": days
        }

    except Exception as e:
        logger.error(f"⚠️ [CategoryStats] 조회 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def get_leader_query_samples(leader_code: str, limit: int = 10) -> Dict[str, Any]:
    """
    특정 리더가 받은 질문 샘플
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT
                created_at,
                user_query,
                query_category,
                status,
                latency_ms
            FROM chat_history
            WHERE leader_code = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (leader_code, limit))

        queries = []
        for row in cur.fetchall():
            created, query, category, status, latency = row
            queries.append({
                "timestamp": created.isoformat() if created else None,
                "query": query[:200],  # 200자 미리보기
                "category": category,
                "status": status,
                "latency_ms": latency
            })

        return {
            "ok": True,
            "leader": leader_code,
            "queries": queries
        }

    except Exception as e:
        logger.error(f"⚠️ [LeaderQueries] 조회 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


# =====================================================
# 📋 Chat Usage Logs (Admin)
# =====================================================

def get_chat_usage_logs(
    days: int = 7,
    leader: Optional[str] = None,
    status: Optional[str] = None,
    query_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    exclude_admin: bool = False,
) -> Dict[str, Any]:
    """
    리더 채팅 이용 로그 조회 (Admin).
    - 일자별/리더별/상태별 필터링
    - exclude_admin=True: 관리자 테스트 제외
    - 최근 질의 목록 + 요약 통계
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        # ── 1) 개별 로그 조회 ──
        where = ["created_at >= NOW() - MAKE_INTERVAL(days => %s)"]
        params: list = [days]

        if leader:
            where.append("leader_code = %s")
            params.append(leader)
        if status:
            where.append("status = %s")
            params.append(status)
        if query_type:
            where.append("query_type = %s")
            params.append(query_type)
        if exclude_admin:
            where.append("(is_admin IS NULL OR is_admin = FALSE)")

        where_sql = " AND ".join(where)

        cur.execute(f"""
            SELECT id, created_at, visitor_id, user_query, ai_response,
                   leader_code, leaders_used, status, latency_ms,
                   query_category, swarm_mode, user_email, query_type,
                   COALESCE(is_admin, FALSE) as is_admin
            FROM chat_history
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])

        logs = []
        for row in cur.fetchall():
            (rid, created, visitor, query, response, ldr, leaders_used,
             st, latency, category, swarm, email, qtype, admin_flag) = row
            logs.append({
                "id": rid,
                "timestamp": created.isoformat() if created else None,
                "visitor_id": visitor[:12] if visitor else None,
                "user_email": email,
                "query_type": qtype or "general",
                "is_admin": bool(admin_flag),
                "query": query[:500] if query else "",
                "response": response[:3000] if response else "",
                "leader": ldr,
                "leaders_used": leaders_used,
                "status": st,
                "latency_ms": latency,
                "category": category,
                "swarm_mode": swarm,
                "response_length": len(response) if response else 0,
            })

        # ── 2) 요약 통계 ──
        cur.execute(f"""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT visitor_id) as unique_visitors,
                COUNT(DISTINCT user_email) FILTER (WHERE user_email IS NOT NULL) as logged_in_users,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COUNT(*) FILTER (WHERE status = 'success') as success_count,
                COUNT(*) FILTER (WHERE status = 'error' OR status = 'FAIL_CLOSED') as fail_count
            FROM chat_history
            WHERE {where_sql}
        """, params)

        summary_row = cur.fetchone()
        total, visitors, logged_in, avg_lat, success, fail = summary_row

        # ── 3) 리더별 분포 ──
        cur.execute(f"""
            SELECT leader_code, COUNT(*) as cnt
            FROM chat_history
            WHERE {where_sql}
            GROUP BY leader_code
            ORDER BY cnt DESC
            LIMIT 20
        """, params)

        leader_dist = []
        for ldr, cnt in cur.fetchall():
            leader_dist.append({"leader": ldr, "count": cnt})

        # ── 4) 시간대별 분포 ──
        cur.execute(f"""
            SELECT EXTRACT(HOUR FROM created_at AT TIME ZONE 'Asia/Seoul') as hour_kst,
                   COUNT(*) as cnt
            FROM chat_history
            WHERE {where_sql}
            GROUP BY hour_kst
            ORDER BY hour_kst
        """, params)

        hourly_dist = []
        for hour, cnt in cur.fetchall():
            hourly_dist.append({"hour_kst": int(hour), "count": cnt})

        # ── 5) 일별 분포 ──
        cur.execute(f"""
            SELECT DATE(created_at AT TIME ZONE 'Asia/Seoul') as day_kst,
                   COUNT(*) as cnt
            FROM chat_history
            WHERE {where_sql}
            GROUP BY day_kst
            ORDER BY day_kst
        """, params)

        daily_dist = []
        for day, cnt in cur.fetchall():
            daily_dist.append({"date": day.isoformat() if day else None, "count": cnt})

        # ── 6) 사용자별 요약 (IP/이메일별 채팅횟수, 주요 리더) ──
        cur.execute(f"""
            SELECT
                COALESCE(user_email, LEFT(visitor_id, 12)) as user_key,
                user_email,
                LEFT(visitor_id, 12) as ip_hash,
                COUNT(*) as chat_count,
                STRING_AGG(DISTINCT leader_code, ', ' ORDER BY leader_code) as leaders,
                MAX(created_at) as last_active
            FROM chat_history
            WHERE {where_sql}
            GROUP BY user_key, user_email, ip_hash
            ORDER BY chat_count DESC
            LIMIT 50
        """, params)

        user_stats = []
        for row in cur.fetchall():
            ukey, email, ip_hash, chat_cnt, ldrs, last_act = row
            user_stats.append({
                "user": email or ip_hash,
                "email": email,
                "ip_hash": ip_hash,
                "chat_count": chat_cnt,
                "leaders_used": ldrs,
                "last_active": last_act.isoformat() if last_act else None,
            })

        return {
            "ok": True,
            "period_days": days,
            "summary": {
                "total_queries": total or 0,
                "unique_visitors": visitors or 0,
                "logged_in_users": logged_in or 0,
                "avg_latency_ms": round(float(avg_lat or 0), 1),
                "success_count": success or 0,
                "fail_count": fail or 0,
                "success_rate": round((success or 0) / max(total or 1, 1) * 100, 1),
            },
            "user_stats": user_stats,
            "leader_distribution": leader_dist,
            "hourly_distribution": hourly_dist,
            "daily_distribution": daily_dist,
            "logs": logs,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"⚠️ [ChatUsageLogs] 조회 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


# =====================================================
# 🛡️ Response Verification System
# =====================================================

def init_verification_table():
    """응답 검증 테이블 초기화"""
    if not _db_enabled():
        return

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS response_verification (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64),
                user_query TEXT NOT NULL,
                gemini_response TEXT NOT NULL,
                tools_used JSONB,
                tool_results JSONB,
                verification_result VARCHAR(20),
                ssot_compliance_score INTEGER,
                issues_found JSONB,
                verification_feedback TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                env_version VARCHAR(50)
            )
        """)

        # 인덱스 생성 (성능 최적화)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_verification_result
            ON response_verification(verification_result)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_verification_score
            ON response_verification(ssot_compliance_score)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_verification_created
            ON response_verification(created_at DESC)
        """)

        # 기존 claude_feedback 컬럼 → verification_feedback 마이그레이션
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'response_verification' AND column_name = 'claude_feedback'
                ) THEN
                    ALTER TABLE response_verification RENAME COLUMN claude_feedback TO verification_feedback;
                END IF;
            END $$;
        """)

        conn.commit()
        logger.info("✅ [Verification] 테이블 초기화 완료")
    except Exception as e:
        logger.error(f"⚠️ [Verification] 테이블 생성 실패: {e}")
        raise
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def save_verification_result(
    session_id: str,
    user_query: str,
    gemini_response: str,
    tools_used: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    verification_result: str,
    ssot_compliance_score: int,
    issues_found: List[str],
    verification_feedback: str
) -> Dict[str, Any]:
    """
    검증 결과 저장

    Args:
        session_id: 세션 ID
        user_query: 사용자 질문
        gemini_response: Gemini 응답
        tools_used: 사용된 tool 함수 목록
        tool_results: tool 실행 결과
        verification_result: PASS/WARNING/FAIL/ERROR
        ssot_compliance_score: SSOT 준수 점수 (0-100)
        issues_found: 발견된 문제점 목록
        verification_feedback: Claude의 피드백
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO response_verification (
                session_id, user_query, gemini_response,
                tools_used, tool_results,
                verification_result, ssot_compliance_score,
                issues_found, verification_feedback,
                env_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            session_id,
            user_query[:5000],  # 길이 제한
            gemini_response[:10000],
            json.dumps(tools_used, ensure_ascii=False),
            json.dumps(tool_results, ensure_ascii=False),
            verification_result,
            ssot_compliance_score,
            json.dumps(issues_found, ensure_ascii=False),
            verification_feedback[:2000],
            _ENV_VERSION
        ))

        verification_id = cur.fetchone()[0]
        conn.commit()

        logger.info(f"✅ [Verification] 검증 결과 저장 완료 (ID: {verification_id}, 결과: {verification_result}, 점수: {ssot_compliance_score})")
        return {"ok": True, "verification_id": verification_id}

    except Exception as e:
        logger.error(f"⚠️ [Verification] 저장 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def get_verification_statistics(days: int = 7) -> Dict[str, Any]:
    """
    검증 통계 조회

    Args:
        days: 최근 N일 데이터

    Returns:
        {
            "total_verifications": int,
            "pass_count": int,
            "warning_count": int,
            "fail_count": int,
            "avg_score": float,
            "recent_failures": [...]
        }
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        # 전체 통계
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN verification_result = 'PASS' THEN 1 END) as pass_count,
                COUNT(CASE WHEN verification_result = 'WARNING' THEN 1 END) as warning_count,
                COUNT(CASE WHEN verification_result = 'FAIL' THEN 1 END) as fail_count,
                AVG(ssot_compliance_score) as avg_score
            FROM response_verification
            WHERE created_at >= NOW() - INTERVAL %s
        """, (f"{int(days)} days",))

        stats = cur.fetchone()
        total, pass_cnt, warn_cnt, fail_cnt, avg_score = stats

        # 최근 실패 케이스
        cur.execute("""
            SELECT
                created_at,
                user_query,
                verification_result,
                ssot_compliance_score,
                issues_found,
                verification_feedback
            FROM response_verification
            WHERE verification_result IN ('FAIL', 'WARNING')
                AND created_at >= NOW() - INTERVAL %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (f"{int(days)} days",))

        recent_failures = []
        for row in cur.fetchall():
            created, query, result, score, issues, feedback = row
            recent_failures.append({
                "timestamp": created.isoformat() if created else None,
                "query": query[:100],
                "result": result,
                "score": score,
                "issues": json.loads(issues) if issues else [],
                "feedback": feedback[:200]
            })

        return {
            "ok": True,
            "period_days": days,
            "total_verifications": total or 0,
            "pass_count": pass_cnt or 0,
            "warning_count": warn_cnt or 0,
            "fail_count": fail_cnt or 0,
            "avg_score": round(avg_score, 1) if avg_score else 0,
            "pass_rate": round((pass_cnt or 0) / total * 100, 1) if total > 0 else 0,
            "recent_failures": recent_failures
        }

    except Exception as e:
        logger.error(f"⚠️ [VerificationStats] 조회 실패: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def get_visitor_stats() -> Dict[str, Any]:
    """
    방문자 통계 조회
    - today_visitors: 오늘 방문자 수
    - total_visitors: 총 누적 방문자 수
    """
    if not _db_enabled():
        return {
            "ok": False,
            "today_visitors": 0,
            "total_visitors": 0,
            "error": "DB_DISABLED"
        }

    conn = None
    cur = None
    try:
        conn = get_connection()
        if conn is None:
            return {"ok": False, "today_visitors": 0, "total_visitors": 0, "error": "DB_CONN_FAIL"}
        cur = conn.cursor()
        today = datetime.now(timezone.utc).date()

        # 오늘 방문자 수
        cur.execute("""
            SELECT unique_visitors, total_visits
            FROM daily_visitors
            WHERE visit_date = %s
        """, (today,))
        today_row = cur.fetchone()
        today_visitors = today_row[0] if today_row else 0
        today_visits = today_row[1] if today_row else 0

        # 총 누적 방문자 수
        cur.execute("SELECT COUNT(*) FROM visitor_stats")
        total_row = cur.fetchone()
        total_visitors = total_row[0] if total_row else 0

        # 총 누적 방문 횟수
        cur.execute("SELECT SUM(visit_count) FROM visitor_stats")
        total_visits_row = cur.fetchone()
        total_visits = total_visits_row[0] if total_visits_row and total_visits_row[0] else 0

        return {
            "ok": True,
            "today_visitors": today_visitors,
            "today_visits": today_visits,
            "total_visitors": total_visitors,
            "total_visits": total_visits
        }

    except Exception as e:
        logger.error(f"⚠️ [Visitor] 통계 조회 실패: {e}")
        return {
            "ok": False,
            "today_visitors": 0,
            "total_visitors": 0,
            "error": str(e)
        }
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


# =====================================================
# 📊 Admin Business Metrics (Phase 5)
# =====================================================

def get_dashboard_metrics(days: int = 7) -> dict:
    """DAU, 일/주/월 쿼리 수, 평균 latency, 에러율, 상위 법률 카테고리
    관리자 테스트(is_admin=TRUE) 쿼리는 통계에서 자동 제외.
    """
    admin_filter = "AND (is_admin IS NULL OR is_admin = FALSE)"
    try:
        # Daily active users
        dau_result = execute(
            f"""SELECT COUNT(DISTINCT visitor_id) as dau
               FROM chat_history
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s) {admin_filter}""",
            (days,), fetch="one"
        )
        dau = dau_result.get("data", [0])[0] if dau_result.get("ok") else 0

        # Query counts
        query_result = execute(
            f"""SELECT
                COUNT(*) as total_queries,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') as daily_queries,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as weekly_queries,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as monthly_queries,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COUNT(*) FILTER (WHERE status = 'error') as error_count
               FROM chat_history
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s) {admin_filter}""",
            (days,), fetch="one"
        )

        # Top categories
        cat_result = execute(
            f"""SELECT query_category, COUNT(*) as cnt
               FROM chat_history
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s) AND query_category IS NOT NULL
                     {admin_filter}
               GROUP BY query_category
               ORDER BY cnt DESC
               LIMIT 10""",
            (days,), fetch="all"
        )

        data = query_result.get("data", [0]*6) if query_result.get("ok") else [0]*6
        categories = []
        if cat_result.get("ok") and cat_result.get("data"):
            categories = [{"category": r[0], "count": r[1]} for r in cat_result["data"]]

        total = data[0] or 1
        return {
            "ok": True,
            "period_days": days,
            "dau": dau,
            "daily_queries": data[1] or 0,
            "weekly_queries": data[2] or 0,
            "monthly_queries": data[3] or 0,
            "avg_latency_ms": round(float(data[4] or 0), 1),
            "error_rate": round(float(data[5] or 0) / total * 100, 2),
            "top_categories": categories,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_conversion_metrics(days: int = 30) -> dict:
    """총 쿼리 수, 변호사 문의 수, 피드백 수, 전환율 (관리자 테스트 제외)"""
    try:
        q_result = execute(
            "SELECT COUNT(*) FROM chat_history WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s) AND (is_admin IS NULL OR is_admin = FALSE)",
            (days,), fetch="one"
        )
        li_result = execute(
            "SELECT COUNT(*) FROM lawyer_inquiries WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)",
            (days,), fetch="one"
        )
        fb_result = execute(
            "SELECT COUNT(*) FROM feedback WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)",
            (days,), fetch="one"
        )

        total_queries = q_result.get("data", [0])[0] if q_result.get("ok") else 0
        lawyer_inquiries = li_result.get("data", [0])[0] if li_result.get("ok") else 0
        feedback_count = fb_result.get("data", [0])[0] if fb_result.get("ok") else 0

        conversion_rate = round(lawyer_inquiries / max(total_queries, 1) * 100, 2)

        return {
            "ok": True,
            "period_days": days,
            "total_queries": total_queries or 0,
            "lawyer_inquiries": lawyer_inquiries or 0,
            "feedback_count": feedback_count or 0,
            "conversion_rate": conversion_rate,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_retention_metrics() -> dict:
    """재방문율, 평균 방문 횟수, 사용자 분포"""
    try:
        result = execute(
            """SELECT
                visitor_id,
                COUNT(*) as visit_count
               FROM chat_history
               WHERE visitor_id IS NOT NULL
                 AND created_at >= NOW() - INTERVAL '30 days'
               GROUP BY visitor_id""",
            fetch="all"
        )

        if not result.get("ok") or not result.get("data"):
            return {"ok": True, "total_users": 0, "returning_users": 0, "return_rate": 0,
                    "avg_visits": 0, "distribution": {"one_time": 0, "light": 0, "heavy": 0}}

        rows = result["data"]
        total_users = len(rows)
        returning = sum(1 for r in rows if r[1] > 1)
        total_visits = sum(r[1] for r in rows)

        one_time = sum(1 for r in rows if r[1] == 1)
        light = sum(1 for r in rows if 2 <= r[1] <= 5)
        heavy = sum(1 for r in rows if r[1] > 5)

        return {
            "ok": True,
            "total_users": total_users,
            "returning_users": returning,
            "return_rate": round(returning / max(total_users, 1) * 100, 2),
            "avg_visits": round(total_visits / max(total_users, 1), 1),
            "distribution": {"one_time": one_time, "light_2_5": light, "heavy_5_plus": heavy},
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_feedback_summary(days: int = 30) -> dict:
    """총 피드백, 긍정/부정 비율, 리더별 분포"""
    try:
        total_result = execute(
            """SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE rating = 'up') as positive,
                COUNT(*) FILTER (WHERE rating = 'down') as negative
               FROM feedback
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)""",
            (days,), fetch="one"
        )

        leader_result = execute(
            """SELECT leader, rating, COUNT(*) as cnt
               FROM feedback
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s) AND leader IS NOT NULL
               GROUP BY leader, rating
               ORDER BY cnt DESC""",
            (days,), fetch="all"
        )

        data = total_result.get("data", [0, 0, 0]) if total_result.get("ok") else [0, 0, 0]
        total = data[0] or 0
        positive = data[1] or 0
        negative = data[2] or 0

        leader_dist = {}
        if leader_result.get("ok") and leader_result.get("data"):
            for row in leader_result["data"]:
                leader = row[0]
                if leader not in leader_dist:
                    leader_dist[leader] = {"up": 0, "down": 0}
                leader_dist[leader][row[1]] = row[2]

        return {
            "ok": True,
            "period_days": days,
            "total_feedback": total,
            "positive": positive,
            "negative": negative,
            "positive_rate": round(positive / max(total, 1) * 100, 1),
            "leader_distribution": leader_dist,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_cost_estimate(days: int = 7) -> dict:
    """Gemini API 호출 수, 추정 비용"""
    try:
        result = execute(
            """SELECT COUNT(*) as total_calls
               FROM chat_history
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)""",
            (days,), fetch="one"
        )

        total_calls = result.get("data", [0])[0] if result.get("ok") else 0
        total_calls = total_calls or 0

        # Gemini Flash 기준 호출당 평균 비용
        gemini_cost_per_call = 0.002  # ~$0.002 per Gemini Flash call

        return {
            "ok": True,
            "period_days": days,
            "total_api_calls": total_calls,
            "gemini_calls": total_calls,
            "estimated_cost_usd": round(total_calls * gemini_cost_per_call, 2),
            "cost_breakdown": {
                "gemini": round(total_calls * gemini_cost_per_call, 2),
            },
            "note": "Estimated based on average token usage. Actual costs may vary.",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def save_lawyer_inquiry(name: str, phone: str, query_summary: str, leader: str, status: str = "pending") -> dict:
    """변호사 문의를 DB에 저장"""
    try:
        result = execute(
            """INSERT INTO lawyer_inquiries (name, phone, query_summary, leader, status)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id""",
            (name, phone, query_summary, leader, status),
            fetch="one"
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def save_feedback(trace_id: str, rating: str, query: str, leader: str, comment: str = "") -> dict:
    """피드백을 DB에 저장"""
    try:
        result = execute(
            """INSERT INTO feedback (trace_id, rating, query, leader, comment)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id""",
            (trace_id, rating, query, leader, comment),
            fetch="one"
        )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =============================================================
# Frontend Error & Performance Logging (신규)
# =============================================================

def init_frontend_logs_table():
    """프론트엔드 에러/성능 로그 테이블 생성"""
    try:
        execute(f"""
            CREATE TABLE IF NOT EXISTS frontend_errors (
                id SERIAL PRIMARY KEY,
                visitor_id VARCHAR(64),
                message TEXT,
                source VARCHAR(200),
                lineno INTEGER DEFAULT 0,
                colno INTEGER DEFAULT 0,
                stack TEXT,
                url VARCHAR(500),
                user_agent VARCHAR(300),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                env_version VARCHAR(50) DEFAULT '{_ENV_VERSION}'
            )
        """, fetch="none")

        execute(f"""
            CREATE TABLE IF NOT EXISTS frontend_perf (
                id SERIAL PRIMARY KEY,
                visitor_id VARCHAR(64),
                lcp_ms REAL,
                fid_ms REAL,
                cls_score REAL,
                ttfb_ms REAL,
                dom_load_ms REAL,
                full_load_ms REAL,
                url VARCHAR(500),
                user_agent VARCHAR(300),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                env_version VARCHAR(50) DEFAULT '{_ENV_VERSION}'
            )
        """, fetch="none")

        # 인덱스
        execute("CREATE INDEX IF NOT EXISTS idx_fe_errors_created ON frontend_errors(created_at)", fetch="none")
        execute("CREATE INDEX IF NOT EXISTS idx_fe_perf_created ON frontend_perf(created_at)", fetch="none")

        logger.info("✅ [DB] frontend_errors + frontend_perf 테이블 초기화 완료")
    except Exception as e:
        logger.warning(f"⚠️ [DB] frontend logs 테이블 생성 실패: {e}")
        raise


def save_frontend_error(
    visitor_id: str, message: str, source: str,
    lineno: int, colno: int, stack: str, url: str, user_agent: str
) -> dict:
    """프론트엔드 JS 에러 저장"""
    try:
        return execute(
            """INSERT INTO frontend_errors
               (visitor_id, message, source, lineno, colno, stack, url, user_agent)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (visitor_id, message, source, lineno, colno, stack, url, user_agent),
            fetch="one"
        )
    except Exception as e:
        logger.warning(f"⚠️ [DB] frontend error 저장 실패: {e}")
        return {"ok": False, "error": str(e)}


def save_frontend_perf(
    visitor_id: str, lcp_ms=None, fid_ms=None, cls_score=None,
    ttfb_ms=None, dom_load_ms=None, full_load_ms=None,
    url: str = "", user_agent: str = ""
) -> dict:
    """프론트엔드 성능 메트릭 저장"""
    try:
        return execute(
            """INSERT INTO frontend_perf
               (visitor_id, lcp_ms, fid_ms, cls_score, ttfb_ms, dom_load_ms, full_load_ms, url, user_agent)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (visitor_id, lcp_ms, fid_ms, cls_score, ttfb_ms, dom_load_ms, full_load_ms, url, user_agent),
            fetch="one"
        )
    except Exception as e:
        logger.warning(f"⚠️ [DB] frontend perf 저장 실패: {e}")
        return {"ok": False, "error": str(e)}


def get_frontend_errors(limit: int = 50) -> dict:
    """최근 프론트엔드 에러 조회"""
    try:
        result = execute(
            """SELECT id, visitor_id, message, source, lineno, colno, url, created_at
               FROM frontend_errors
               ORDER BY created_at DESC
               LIMIT %s""",
            (limit,), fetch="all"
        )
        if isinstance(result, dict) and not result.get("ok", True):
            return result
        rows = result if isinstance(result, list) else []
        return {
            "ok": True,
            "count": len(rows),
            "errors": [
                {
                    "id": r[0], "visitor_id": r[1], "message": r[2],
                    "source": r[3], "lineno": r[4], "colno": r[5],
                    "url": r[6], "created_at": str(r[7])
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"[DB] frontend errors 조회 실패: {e}")
        return {"ok": False, "error": str(e)}


def get_frontend_perf_stats(limit: int = 100) -> dict:
    """프론트엔드 성능 통계 (최근 N건 평균 + 개별)"""
    try:
        # 평균값
        avg_result = execute(
            """SELECT
                 AVG(lcp_ms) as avg_lcp,
                 AVG(fid_ms) as avg_fid,
                 AVG(cls_score) as avg_cls,
                 AVG(ttfb_ms) as avg_ttfb,
                 AVG(dom_load_ms) as avg_dom_load,
                 AVG(full_load_ms) as avg_full_load,
                 COUNT(*) as total
               FROM frontend_perf
               WHERE created_at > NOW() - INTERVAL '7 days'""",
            fetch="one"
        )
        if isinstance(avg_result, dict) and not avg_result.get("ok", True):
            return avg_result

        # 직접 tuple인 경우
        if isinstance(avg_result, (tuple, list)):
            averages = {
                "avg_lcp_ms": round(avg_result[0] or 0, 1),
                "avg_fid_ms": round(avg_result[1] or 0, 1),
                "avg_cls": round(avg_result[2] or 0, 3),
                "avg_ttfb_ms": round(avg_result[3] or 0, 1),
                "avg_dom_load_ms": round(avg_result[4] or 0, 1),
                "avg_full_load_ms": round(avg_result[5] or 0, 1),
                "total_samples": avg_result[6] or 0,
            }
        else:
            averages = {}

        return {"ok": True, "averages": averages}
    except Exception as e:
        logger.error(f"[DB] frontend perf 통계 조회 실패: {e}")
        return {"ok": False, "error": str(e)}


# =====================================================
# 📋 Endpoint Logs (전체 API 요청 기록)
# =====================================================

def init_endpoint_logs_table():
    """endpoint_logs 테이블 생성."""
    try:
        execute(f"""
            CREATE TABLE IF NOT EXISTS endpoint_logs (
                id SERIAL PRIMARY KEY,
                method VARCHAR(10),
                path VARCHAR(500),
                status_code INTEGER,
                latency_ms INTEGER,
                ip_hash VARCHAR(12),
                user_agent VARCHAR(200),
                visitor_id VARCHAR(64),
                user_email VARCHAR(200),
                query_params TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """, fetch="none")
        execute("CREATE INDEX IF NOT EXISTS idx_ep_logs_created ON endpoint_logs(created_at)", fetch="none")
        execute("CREATE INDEX IF NOT EXISTS idx_ep_logs_path_created ON endpoint_logs(path, created_at)", fetch="none")
        logger.info("✅ [DB] endpoint_logs 테이블 초기화 완료")
    except Exception as e:
        logger.warning(f"⚠️ [DB] endpoint_logs 테이블 생성 실패: {e}")
        raise


def save_endpoint_log(
    method: str, path: str, status_code: int, latency_ms: int,
    ip_hash: str, user_agent: str, visitor_id: str = "",
    user_email: str = "", query_params: str = ""
):
    """엔드포인트 요청 로그 저장 (fail-soft)."""
    try:
        execute(
            """INSERT INTO endpoint_logs
               (method, path, status_code, latency_ms, ip_hash, user_agent, visitor_id, user_email, query_params)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                method[:10], path[:500], status_code, latency_ms,
                ip_hash[:12], user_agent[:200],
                visitor_id[:64], user_email[:200], query_params[:1000]
            ),
            fetch="none"
        )
    except Exception as e:
        logger.warning(f"⚠️ [DB] endpoint log 저장 실패: {e}")


def get_endpoint_logs(
    days: int = 7, path_filter: str = None,
    status_filter: int = None, limit: int = 100
) -> dict:
    """엔드포인트 로그 조회 + 집계 통계."""
    try:
        # 집계 통계
        summary_result = execute(
            """SELECT
                COUNT(*) as total,
                COUNT(DISTINCT ip_hash) as unique_ips,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COUNT(*) FILTER (WHERE status_code >= 400) as error_count
               FROM endpoint_logs
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)""",
            (days,), fetch="one"
        )

        # 경로별 집계
        path_result = execute(
            """SELECT path, method, COUNT(*) as cnt,
                      COALESCE(AVG(latency_ms), 0) as avg_lat,
                      COUNT(*) FILTER (WHERE status_code >= 400) as errors
               FROM endpoint_logs
               WHERE created_at >= NOW() - MAKE_INTERVAL(days => %s)
               GROUP BY path, method
               ORDER BY cnt DESC
               LIMIT 50""",
            (days,), fetch="all"
        )

        # 개별 로그
        where = ["created_at >= NOW() - MAKE_INTERVAL(days => %s)"]
        params: list = [days]
        if path_filter:
            where.append("path LIKE %s")
            params.append(f"%{path_filter}%")
        if status_filter:
            where.append("status_code = %s")
            params.append(status_filter)
        params.append(limit)

        logs_result = execute(
            f"""SELECT id, method, path, status_code, latency_ms,
                       ip_hash, user_agent, visitor_id, user_email,
                       query_params, created_at
               FROM endpoint_logs
               WHERE {' AND '.join(where)}
               ORDER BY created_at DESC
               LIMIT %s""",
            tuple(params), fetch="all"
        )

        summary_data = summary_result.get("data") if isinstance(summary_result, dict) else summary_result
        path_data = path_result.get("data") if isinstance(path_result, dict) else path_result
        logs_data = logs_result.get("data") if isinstance(logs_result, dict) else logs_result

        summary = {}
        if summary_data:
            row = summary_data
            summary = {
                "total_requests": row[0] or 0,
                "unique_ips": row[1] or 0,
                "avg_latency_ms": round(float(row[2] or 0), 1),
                "error_count": row[3] or 0,
            }

        paths = []
        if path_data:
            for r in path_data:
                paths.append({
                    "path": r[0], "method": r[1], "count": r[2],
                    "avg_latency_ms": round(float(r[3] or 0), 1),
                    "errors": r[4] or 0,
                })

        logs = []
        if logs_data:
            for r in logs_data:
                logs.append({
                    "id": r[0], "method": r[1], "path": r[2],
                    "status_code": r[3], "latency_ms": r[4],
                    "ip_hash": r[5], "user_agent": r[6][:60] if r[6] else "",
                    "visitor_id": r[7], "user_email": r[8],
                    "query_params": r[9], "created_at": str(r[10]),
                })

        return {
            "ok": True, "period_days": days,
            "summary": summary, "by_path": paths, "logs": logs,
        }
    except Exception as e:
        logger.error(f"[DB] endpoint logs 조회 실패: {e}")
        return {"ok": False, "error": str(e)}
