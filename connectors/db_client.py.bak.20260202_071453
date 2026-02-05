import os
import json
import hashlib
import queue
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from google.cloud.sql.connector import Connector

# ─── 싱글턴 커넥터 및 커넥션 풀 ─────────────────────────────────────────────
_connector: Optional[Connector] = None
_pool: Optional[queue.Queue] = None
_pool_lock = threading.Lock()
_MIN_CONN = 2
_MAX_CONN = 10


def _env(name: str) -> Optional[str]:
    v = os.getenv(name)
    return v.strip() if v else None


def _db_enabled() -> bool:
    # DB를 끄고 싶으면 DB_DISABLED=1 같은 플래그로 제어 가능
    if _env("DB_DISABLED") == "1":
        return False
    # 필수 4종이 있어야 DB를 켬 (없으면 fail-soft로 DB disabled)
    required = ["CLOUD_SQL_INSTANCE", "DB_USER", "DB_PASS", "DB_NAME"]
    return all(_env(k) for k in required)


def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector


def _create_connection():
    """
    Cloud SQL Connector로 새 커넥션 생성 (pg8000 사용)
    """
    if not _db_enabled():
        raise RuntimeError("DB disabled (missing env vars or DB_DISABLED=1)")

    connector = _get_connector()
    return connector.connect(
        _env("CLOUD_SQL_INSTANCE"),
        "pg8000",
        user=_env("DB_USER"),
        password=_env("DB_PASS"),
        dbname=_env("DB_NAME"),
    )


def _get_pool() -> queue.Queue:
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool
        _pool = queue.Queue(maxsize=_MAX_CONN)

        # DB가 비활성화면 풀을 만들되 커넥션은 생성하지 않음 (fail-soft)
        if not _db_enabled():
            print("⚠️ [DB] init_tables skipped (DB disabled)")
            return _pool

        for _ in range(_MIN_CONN):
            _pool.put(_create_connection())
        print("✅ [DB] Cloud SQL 커넥션 풀 초기화 완료")

    return _pool


def get_connection():
    pool = _get_pool()

    if not _db_enabled():
        raise RuntimeError("DB disabled")

    try:
        conn = pool.get_nowait()
    except queue.Empty:
        conn = _create_connection()

    # pg8000 connection has .close() but not always .closed like psycopg2
    return conn


def release_connection(conn):
    pool = _get_pool()
    try:
        try:
            conn.rollback()
        except Exception:
            pass
        pool.put_nowait(conn)
    except queue.Full:
        try:
            conn.close()
        except Exception:
            pass


def close_all():
    global _pool, _connector
    if _pool:
        while not _pool.empty():
            try:
                conn = _pool.get_nowait()
                try:
                    conn.close()
                except Exception:
                    pass
            except queue.Empty:
                break
        _pool = None
    if _connector:
        _connector.close()
        _connector = None


def init_tables():
    """
    앱 부팅 시 테이블 생성.
    DB 비활성화면 조용히 skip.
    """
    if not _db_enabled():
        print("⚠️ [DB] init_tables skipped (DB disabled)")
        return

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS drf_cache (
                cache_key       VARCHAR(255) PRIMARY KEY,
                content         JSONB        NOT NULL,
                signature       VARCHAR(64)  NOT NULL,
                created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT 'v50.2.3'
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_tracker (
                provider        VARCHAR(100) PRIMARY KEY,
                call_count      INTEGER      NOT NULL DEFAULT 0,
                window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
                window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT 'v50.2.3'
            );
        """)

        conn.commit()
        print("✅ [DB] 테이블 초기화 완료 (drf_cache, rate_limit_tracker)")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"❌ [DB] 테이블 초기화 실패: {e}")
        raise
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        release_connection(conn)
