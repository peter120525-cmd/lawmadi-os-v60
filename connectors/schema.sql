-- ============================================================
-- Lawmadi OS v50.1.3-GA-HARDENED — Cloud SQL 테이블 정의
-- Instance: lawmadi-db:asia-northeast3:lawmadi-db-v1
-- DB:       lawmadi-db-v1
-- User:     postgres
-- ============================================================

-- 1. DRF 응답 캐시 + 무결성 서명
--    TTL: 30일 (config.data_sync_connectors.cache_ttl_days)
--    서명: SHA-256 (LMD-CONST-005 무결성 검증과 연결)
CREATE TABLE IF NOT EXISTS drf_cache (
    cache_key       VARCHAR(255) PRIMARY KEY,
    content         JSONB        NOT NULL,
    signature       VARCHAR(64)  NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    env_version     VARCHAR(50)  NOT NULL DEFAULT '50.1.3-GA-HARDENED'
);

-- 만료된 캐시 조회 시 인덱스
CREATE INDEX IF NOT EXISTS idx_cache_expiry ON drf_cache (expires_at);


-- 2. Per-provider API 호출 횟수 추적 (Rate Limit)
--    config.data_sync_connectors.rate_limits 참조
--    LAW_GO_KR_DRF: 120 rpm
--    NOMINATIM:     1 rps
CREATE TABLE IF NOT EXISTS rate_limit_tracker (
    provider        VARCHAR(100) PRIMARY KEY,
    call_count      INTEGER      NOT NULL DEFAULT 0,
    window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
    env_version     VARCHAR(50)  NOT NULL DEFAULT '50.1.3-GA-HARDENED'
);