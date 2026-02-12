import logging
from connectors.validator import LawmadiValidator
from typing import Optional, Dict, Any
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

