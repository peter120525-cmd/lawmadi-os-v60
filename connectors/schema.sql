-- Lawmadi OS v60.0.0 Database Schema
-- Cloud SQL (PostgreSQL 18) - lawmadi-db:asia-northeast3:lawmadi-db-v1

-- DRF 캐시 테이블 (LMD-CONST-005 무결성 서명 포함)
CREATE TABLE IF NOT EXISTS drf_cache (
    cache_key       VARCHAR(255) PRIMARY KEY,
    content         JSONB        NOT NULL,
    signature       VARCHAR(64)  NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    env_version     VARCHAR(50)  NOT NULL DEFAULT 'v60.0.0'
);

-- API 트래픽 제어 레이트 리밋 테이블
CREATE TABLE IF NOT EXISTS rate_limit_tracker (
    provider        VARCHAR(100) PRIMARY KEY,
    call_count      INTEGER      NOT NULL DEFAULT 0,
    window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
    env_version     VARCHAR(50)  NOT NULL DEFAULT 'v60.0.0'
);

-- 감사 로그 테이블
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL    PRIMARY KEY,
    event_type      VARCHAR(100) NOT NULL,
    event_data      JSONB,
    user_id         VARCHAR(255),
    ip_address      VARCHAR(45),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    env_version     VARCHAR(50)  NOT NULL DEFAULT 'v60.0.0'
);

-- 사용자 세션 테이블
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id      VARCHAR(255) PRIMARY KEY,
    user_fingerprint VARCHAR(255),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_active     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    query_count     INTEGER      NOT NULL DEFAULT 0,
    env_version     VARCHAR(50)  NOT NULL DEFAULT 'v60.0.0'
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_drf_cache_expires ON drf_cache (expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_event ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions (last_active);
