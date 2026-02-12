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

_ENV_VERSION = "v50.2.4-HARDENED"


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
            conn.commit()
            data = None

        return {"ok": True, "data": data}

    except Exception as e:
        logger.error(f"⚠️ [DB] execute 실패: {e}")
        return {"ok": False, "error": str(e)}

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
            f"""
            INSERT INTO rate_limit_tracker (provider, call_count, window_start, window_end, env_version)
            VALUES (%s, 1, %s, %s, '{_ENV_VERSION}')
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
            (provider, now, new_window_end)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"⚠️ [DB] rate_limit_hit 업데이트 실패: {e}")
    finally:
        if cur: cur.close()
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

        cur.execute("""
            INSERT INTO audit_logs
            (query, response, leader, status, latency_ms, env_version)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            query,
            response,
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
# 📊 Visitor Tracking System
# =====================================================

def init_visitor_stats_table():
    """방문자 통계 테이블 초기화"""
    if not _db_enabled():
        return

    conn = get_connection()
    cur = None
    try:
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
    finally:
        if cur: cur.close()
        if conn: release_connection(conn)


def record_visit(visitor_id: str) -> Dict[str, Any]:
    """
    방문 기록
    - visitor_id: 브라우저 fingerprint 또는 UUID
    - 신규 방문자인지 여부를 반환
    """
    if not _db_enabled():
        return {"ok": False, "error": "DB_DISABLED"}

    conn = get_connection()
    cur = None
    try:
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
    query_category: Optional[str] = None
) -> Dict[str, Any]:
    """
    채팅 기록 저장 (개선된 버전)
    - 기존 chat_history 테이블 활용
    - 추가 정보: visitor_id, swarm_mode, leaders_used, query_category
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
                ADD COLUMN IF NOT EXISTS env_version VARCHAR(50)
            """)
        except Exception:
            pass  # 컬럼이 이미 있으면 무시

        # 데이터 삽입
        leaders_str = ",".join(leaders_used) if leaders_used else leader

        cur.execute("""
            INSERT INTO chat_history (
                user_id, user_query, ai_response, leader_code,
                status, latency_ms, visitor_id, swarm_mode,
                leaders_used, query_category, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            visitor_id or "anonymous",
            user_query,
            ai_response[:5000],  # 응답이 너무 길면 5000자로 제한
            leader,
            status,
            latency_ms,
            visitor_id,
            swarm_mode,
            leaders_str,
            query_category
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
            WHERE created_at >= NOW() - INTERVAL '%s days'
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
            WHERE created_at >= NOW() - INTERVAL '%s days'
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

    conn = get_connection()
    cur = None
    try:
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

