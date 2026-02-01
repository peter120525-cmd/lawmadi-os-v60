"""
[L3] Cloud SQL 연결 및 캐시·Rate Limit 관리
config.data_sync_connectors 참조

테이블:
  drf_cache        — DRF 응답 캐시 + SHA-256 서명
  rate_limit_tracker — Per-provider API 호출 횟수 추적
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from google.cloud.sql.connector import Connector
import psycopg2
import psycopg2.pool


# ─── 싱글턴 커넥터 및 커넥션 풀 ─────────────────────────────────────────────
_connector: Optional[Connector] = None
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """커넥션 풀 초기화 (한 번만)"""
    global _pool
    if _pool is not None:
        return _pool

    connector = _get_connector()

    def _creator():
        return connector.connect(
            os.environ["CLOUD_SQL_INSTANCE"],
            "psycopg2",
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            dbname=os.environ["DB_NAME"],
        )

    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        creator=_creator
    )
    print("✅ [DB] Cloud SQL 커넥션 풀 초기화 완료")
    return _pool


def get_connection():
    """풀에서 커넥션 하나를 빌린다"""
    return _get_pool().getconn()


def release_connection(conn):
    """빌린 커넥션을 풀에 반환"""
    _get_pool().putconn(conn)


def close_all():
    """앱 종료 시 호출 — 풀과 커넥터 정리"""
    global _pool, _connector
    if _pool:
        _pool.closeall()
        _pool = None
    if _connector:
        _connector.close()
        _connector = None


# ─── 테이블 초기화 ───────────────────────────────────────────────────────────
def init_tables():
    """앱 부팅 시 테이블이 없으면 생성 (IF NOT EXISTS)"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executescript = None  # psycopg2는 execute로 여러 문 가능하지 않음

        # drf_cache 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS drf_cache (
                cache_key       VARCHAR(255) PRIMARY KEY,
                content         JSONB        NOT NULL,
                signature       VARCHAR(64)  NOT NULL,
                created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT '50.1.3-GA-HARDENED'
            );
        """)

        # rate_limit_tracker 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_tracker (
                provider        VARCHAR(100) PRIMARY KEY,
                call_count      INTEGER      NOT NULL DEFAULT 0,
                window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
                window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT '50.1.3-GA-HARDENED'
            );
        """)

        conn.commit()
        print("✅ [DB] 테이블 초기화 완료 (drf_cache, rate_limit_tracker)")
    except Exception as e:
        conn.rollback()
        print(f"❌ [DB] 테이블 초기화 실패: {e}")
        raise
    finally:
        cur.close()
        release_connection(conn)


# ─── drf_cache CRUD ──────────────────────────────────────────────────────────
def cache_get(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    캐시 조회 — 만료된 것은 자동 제외
    반환: {"content": ..., "signature": ..., "created_at": ...} 또는 None
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT content, signature, created_at
            FROM drf_cache
            WHERE cache_key = %s AND expires_at > NOW();
        """, (cache_key,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "content": row[0],       # JSONB → dict 자동 변환
            "signature": row[1],
            "created_at": row[2]
        }
    except Exception as e:
        print(f"❌ [DB] cache_get 실패: {e}")
        return None
    finally:
        cur.close()
        release_connection(conn)


def cache_set(cache_key: str, content: Any, signature: str, ttl_days: int = 30):
    """캐시 저장 또는 업데이트 (UPSERT)"""
    conn = get_connection()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ttl_days)

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO drf_cache (cache_key, content, signature, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET
                content    = EXCLUDED.content,
                signature  = EXCLUDED.signature,
                created_at = EXCLUDED.created_at,
                expires_at = EXCLUDED.expires_at;
        """, (cache_key, json.dumps(content, ensure_ascii=False), signature, now, expires_at))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ [DB] cache_set 실패: {e}")
    finally:
        cur.close()
        release_connection(conn)


def cache_verify_signature(cache_key: str) -> bool:
    """
    캐시 무결성 검증 (LMD-CONST-005)
    저장된 content를 다시 해싱하여 signature와 비교
    불일치 시 해당 캐시 삭제
    """
    row = cache_get(cache_key)
    if row is None:
        return False

    content_str = json.dumps(row["content"], sort_keys=True, ensure_ascii=False)
    computed = hashlib.sha256(content_str.encode()).hexdigest()

    if computed != row["signature"]:
        print(f"🚨 [LMD-CONST-005] CACHE_INTEGRITY_VIOLATION: {cache_key}")
        cache_delete(cache_key)
        return False
    return True


def cache_delete(cache_key: str):
    """캐시 단일 항목 삭제"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM drf_cache WHERE cache_key = %s;", (cache_key,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ [DB] cache_delete 실패: {e}")
    finally:
        cur.close()
        release_connection(conn)


# ─── rate_limit_tracker ──────────────────────────────────────────────────────
def rate_limit_check(provider: str, rpm_limit: int) -> bool:
    """
    현재 1분 윈도우 내 호출 횟수가 rpm_limit 미만이면 True (호출 가능)
    윈도우가 만료되면 카운트 리셋
    """
    conn = get_connection()
    now = datetime.now(timezone.utc)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT call_count, window_start, window_end
            FROM rate_limit_tracker
            WHERE provider = %s;
        """, (provider,))
        row = cur.fetchone()

        if row is None:
            # 초기화: 새 윈도우 생성
            cur.execute("""
                INSERT INTO rate_limit_tracker (provider, call_count, window_start, window_end)
                VALUES (%s, 1, %s, %s);
            """, (provider, now, now + timedelta(minutes=1)))
            conn.commit()
            return True

        call_count, window_start, window_end = row

        if now > window_end:
            # 윈도우 만료 → 리셋
            cur.execute("""
                UPDATE rate_limit_tracker
                SET call_count = 1, window_start = %s, window_end = %s
                WHERE provider = %s;
            """, (now, now + timedelta(minutes=1), provider))
            conn.commit()
            return True

        if call_count < rpm_limit:
            # 카운트 증가
            cur.execute("""
                UPDATE rate_limit_tracker
                SET call_count = call_count + 1
                WHERE provider = %s;
            """, (provider,))
            conn.commit()
            return True

        # rpm_limit 초과
        return False

    except Exception as e:
        print(f"❌ [DB] rate_limit_check 실패: {e}")
        return False  # fail-closed
    finally:
        cur.close()
        release_connection(conn)