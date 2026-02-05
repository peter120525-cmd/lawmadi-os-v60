from connectors.db_driver_adapter import create_connection
import os
import json
import hashlib
import queue
import threading
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from google.cloud.sql.connector import Connector
# L5 무결성 검증기 도입 (서명 규격 동기화 목적)
from connectors.validator import LawmadiValidator



# [IT 기술: 시스템 표준 로깅 설정]
logger = logging.getLogger("LawmadiOS.DBClient")
validator = LawmadiValidator()

# ─── [L0] 싱글턴 커넥터 및 커넥션 풀 아키텍처 ──────────────────────────────────
_connector: Optional[Connector] = None
_pool: Optional[queue.Queue] = None
_pool_lock = threading.Lock()
_MIN_CONN = 2
_MAX_CONN = 10
_ENV_VERSION = 'v50.2.3-HARDENED'

def _env(name: str) -> Optional[str]:
    v = os.getenv(name)
    return v.strip() if v else None

def _db_enabled() -> bool:
    """[IT 기술: Fail-Soft] 필수 환경 변수 부재 시 시스템 중단 없이 DB 기능만 비활성화"""
    if _env("DB_DISABLED") == "1":
        return False
    required = ["CLOUD_SQL_INSTANCE", "DB_USER", "DB_PASS", "DB_NAME"]
    return all(_env(k) for k in required)

def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector

    connector = _get_connector()
    return connector.connect(
        _env("CLOUD_SQL_INSTANCE"),
        "pg8000",
        user=_env("DB_USER"),
        password=_env("DB_PASS"),
        dbname=_env("DB"),
    )

def _get_pool() -> queue.Queue:
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool
        _pool = queue.Queue(maxsize=_MAX_CONN)

        if not _db_enabled():
            logger.warning("⚠️ [DB] 인프라 설정 미비로 커넥션 풀 초기화를 스킵합니다.")
            return _pool

        try:
            for _ in range(_MIN_CONN):
                _pool.put(create_connection())
            logger.info(f"✅ [DB] Cloud SQL 커넥션 풀 초기화 완료 (Version: {_ENV_VERSION})")
        except Exception as e:
            logger.error(f"🚨 [DB] 커넥션 풀 생성 중 치명적 오류: {e}")

    return _pool

def get_connection():
    pool = _get_pool()
    if not _db_enabled():
        raise RuntimeError("DB 인프라가 비활성 상태입니다.")

    try:
        # 풀에서 커넥션을 획득하되, 비어있으면 즉시 새로 생성
        conn = pool.get_nowait()
    except queue.Empty:
        conn = create_connection()
    return conn

def release_connection(conn):
    pool = _get_pool()
    try:
        try:
            conn.rollback()
        except:
            pass
        pool.put_nowait(conn)
    except queue.Full:
        try:
            conn.close()
        except:
            pass

def init_tables():
    """[IT 기술: Schema Migration] 앱 부팅 시 테이블 무결성 확인 및 생성"""
    if not _db_enabled():
        return

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        # LMD-CONST-005 준수를 위한 캐시 테이블 정의
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS drf_cache (
                cache_key       VARCHAR(255) PRIMARY KEY,
                content         JSONB        NOT NULL,
                signature       VARCHAR(64)  NOT NULL,
                created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT '{_ENV_VERSION}'
            );
        """)

        # API 트래픽 제어를 위한 레이트 리밋 테이블 정의
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS rate_limit_tracker (
                provider        VARCHAR(100) PRIMARY KEY,
                call_count      INTEGER      NOT NULL DEFAULT 0,
                window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
                window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT '{_ENV_VERSION}'
            );
        """)

        conn.commit()
        logger.info("✅ [DB] 핵심 데이터 테이블 초기화 성공")
    except Exception as e:
        logger.error(f"❌ [DB] 테이블 초기화 실패: {e}")
        raise
    finally:
        if cur: cur.close()
        release_connection(conn)

from .db_client_v2 import add_audit_log
