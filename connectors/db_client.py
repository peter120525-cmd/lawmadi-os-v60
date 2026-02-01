import os
import queue
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from google.cloud.sql.connector import Connector

# =========================
# GA OPERATION MODE
# - DB is OPTIONAL (FAIL-SOFT)
# - If env missing or DB error → disable DB features only
# =========================

_connector: Optional[Connector] = None
_pool: Optional[queue.Queue] = None

_MIN_CONN = 2
_MAX_CONN = 10


def _db_enabled() -> bool:
    required = ("CLOUD_SQL_INSTANCE", "DB_USER", "DB_PASS", "DB_NAME")
    return all(os.getenv(k) for k in required)


def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector


def _create_connection():
    if not _db_enabled():
        raise RuntimeError("DB disabled (missing envs)")

    connector = _get_connector()
    return connector.connect(
        os.environ["CLOUD_SQL_INSTANCE"],
        "pg8000",
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        dbname=os.environ["DB_NAME"],
    )


def _get_pool() -> queue.Queue:
    global _pool
    if _pool is None:
        _pool = queue.Queue(maxsize=_MAX_CONN)
        for _ in range(_MIN_CONN):
            try:
                _pool.put(_create_connection())
            except Exception:
                break
    return _pool


def get_connection():
    if not _db_enabled():
        raise RuntimeError("DB disabled")
    pool = _get_pool()
    try:
        return pool.get_nowait()
    except queue.Empty:
        return _create_connection()


def release_connection(conn):
    if not _db_enabled():
        return
    try:
        _get_pool().put_nowait(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def close_all():
    if not _db_enabled():
        return
    global _pool, _connector
    if _pool:
        while not _pool.empty():
            try:
                conn = _pool.get_nowait()
                conn.close()
            except Exception:
                pass
        _pool = None
    if _connector:
        _connector.close()
        _connector = None


def init_tables():
    if not _db_enabled():
        print("⚠️ [DB] init_tables skipped (DB disabled)")
        return

    conn = get_connection()
    try:
        cur = conn.cursor()
        with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r") as f:
            cur.execute(f.read())
        conn.commit()
        print("✅ [DB] schema ensured")
    finally:
        release_connection(conn)


# ===== Cache / Rate Limit (FAIL-SOFT) =====

def cache_get(cache_key: str) -> Optional[Dict[str, Any]]:
    if not _db_enabled():
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT content, signature FROM cache WHERE cache_key=%s",
            (cache_key,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"content": row[0], "signature": row[1]}
    finally:
        release_connection(conn)


def cache_set(cache_key: str, content: Any, signature: str, ttl_days: int = 30):
    if not _db_enabled():
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO cache(cache_key, content, signature, created_at)
            VALUES(%s, %s, %s, %s)
            ON CONFLICT (cache_key)
            DO UPDATE SET content=EXCLUDED.content,
                          signature=EXCLUDED.signature,
                          created_at=EXCLUDED.created_at
            """,
            (cache_key, content, signature, datetime.now(timezone.utc)),
        )
        conn.commit()
    finally:
        release_connection(conn)


def rate_limit_check(provider: str, rpm_limit: int) -> bool:
    if not _db_enabled():
        return True
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = datetime.now(timezone.utc)
        window_start = now.replace(second=0, microsecond=0)
        cur.execute(
            """
            SELECT COUNT(*) FROM rate_limit
            WHERE provider=%s AND created_at >= %s
            """,
            (provider, window_start),
        )
        count = cur.fetchone()[0]
        return count < rpm_limit
    finally:
        release_connection(conn)
