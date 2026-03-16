from connectors.db_driver_adapter import create_connection
import os
import re
import json
import hashlib
import queue
import threading
import logging
import time
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
_ENV_VERSION = 'v60.0.0'
_CONN_MAX_LIFETIME = 600  # 커넥션 최대 수명 10분 (Cloud SQL idle timeout 대응)
_conn_created: dict = {}  # id(conn) → creation timestamp

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
                conn = create_connection()
                _conn_created[id(conn)] = time.monotonic()
                _pool.put(conn)
            logger.info(f"✅ [DB] Cloud SQL 커넥션 풀 초기화 완료 (Version: {_ENV_VERSION})")
        except Exception as e:
            logger.error(f"🚨 [DB] 커넥션 풀 생성 중 치명적 오류: {e}")

    return _pool

_conn_semaphore = threading.Semaphore(_MAX_CONN)

def _is_conn_alive(conn) -> bool:
    """커넥션 헬스체크: SELECT 1로 활성 여부 확인."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return True
    except Exception:
        return False

def _is_conn_expired(conn) -> bool:
    """커넥션 수명 초과 여부 확인 (Cloud SQL idle timeout 대응)."""
    created = _conn_created.get(id(conn))
    if created is None:
        return True  # 추적 안 되는 커넥션은 만료 처리
    return (time.monotonic() - created) > _CONN_MAX_LIFETIME

def _create_tracked_connection():
    """커넥션 생성 + 수명 추적 등록."""
    conn = create_connection()
    _conn_created[id(conn)] = time.monotonic()
    return conn

def _discard_connection(conn):
    """만료/불량 커넥션 정리."""
    _conn_created.pop(id(conn), None)
    try:
        conn.close()
    except Exception:
        pass

def get_connection():
    pool = _get_pool()
    if not _db_enabled():
        raise RuntimeError("DB 인프라가 비활성 상태입니다.")

    if not _conn_semaphore.acquire(timeout=10):
        raise RuntimeError("DB 커넥션 한도 초과 (동시 접속 제한)")

    try:
        # 풀에서 건강한 커넥션을 찾을 때까지 시도
        while True:
            try:
                conn = pool.get_nowait()
            except queue.Empty:
                break
            # 수명 초과 또는 죽은 커넥션 → 폐기 후 재시도
            if _is_conn_expired(conn) or not _is_conn_alive(conn):
                logger.info("[DB] 만료/불량 커넥션 폐기, 신규 생성")
                _discard_connection(conn)
                continue
            return conn
        # 풀에 사용 가능한 커넥션 없음 → 신규 생성
        conn = _create_tracked_connection()
    except Exception:
        _conn_semaphore.release()
        raise
    return conn

def release_connection(conn):
    pool = _get_pool()
    try:
        # 수명 초과 커넥션은 반납 대신 폐기
        if _is_conn_expired(conn):
            _discard_connection(conn)
            return
        try:
            conn.rollback()
        except Exception:
            # rollback 실패 → 커넥션 불량, 폐기
            _discard_connection(conn)
            return
        pool.put_nowait(conn)
    except queue.Full:
        _discard_connection(conn)
    finally:
        _conn_semaphore.release()

def init_tables():
    """[IT 기술: Schema Migration] 앱 부팅 시 테이블 무결성 확인 및 생성"""
    if not _db_enabled():
        return

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        # LMD-CONST-005 준수를 위한 캐시 테이블 정의
        # DDL DEFAULT — 상수 assert로 안전성 보장 (f-string 제거)
        assert re.fullmatch(r'v\d+\.\d+\.\d+', _ENV_VERSION), f"Invalid version: {_ENV_VERSION}"
        cur.execute("""
            CREATE TABLE IF NOT EXISTS drf_cache (
                cache_key       VARCHAR(255) PRIMARY KEY,
                content         JSONB        NOT NULL,
                signature       VARCHAR(64)  NOT NULL,
                created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT 'v60.0.0'
            );
        """)

        # API 트래픽 제어를 위한 레이트 리밋 테이블 정의
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_tracker (
                provider        VARCHAR(100) PRIMARY KEY,
                call_count      INTEGER      NOT NULL DEFAULT 0,
                window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
                window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
                env_version     VARCHAR(50)  NOT NULL DEFAULT 'v60.0.0'
            );
        """)

        # IP 블랙리스트 영구 저장 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ip_blacklist (
                ip_hash         VARCHAR(64)  PRIMARY KEY,
                ip_addr         VARCHAR(45)  NOT NULL,
                expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
                reason          TEXT         NOT NULL DEFAULT '',
                created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
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
