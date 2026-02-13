-- ==========================================
-- Lawmadi OS v60 - 문서 업로드 기능
-- 데이터베이스 마이그레이션 스크립트
-- ==========================================
-- 작성일: 2026-02-13
-- 목적: 사용자 문서/이미지 업로드 및 법률 분석 기능

-- 1. uploaded_documents 테이블 생성
CREATE TABLE IF NOT EXISTS uploaded_documents (
    id SERIAL PRIMARY KEY,

    -- 파일 메타데이터
    filename VARCHAR(500) NOT NULL,                -- 원본 파일명
    file_path VARCHAR(1000) NOT NULL,              -- 서버 저장 경로
    file_type VARCHAR(50) NOT NULL,                -- MIME 타입 (image/jpeg, application/pdf 등)
    file_size INTEGER NOT NULL,                    -- 파일 크기 (bytes)
    file_hash VARCHAR(64) NOT NULL,                -- SHA-256 해시 (중복 방지)

    -- 사용자 정보
    user_ip VARCHAR(45),                           -- 업로드 사용자 IP (IPv6 지원)
    user_session VARCHAR(100),                     -- 세션 ID (선택적)

    -- 분석 상태
    status VARCHAR(20) DEFAULT 'pending',          -- pending, processing, completed, failed
    analysis_result TEXT,                          -- 분석 결과 (JSON 또는 Markdown)
    analysis_summary TEXT,                         -- 분석 요약 (간략한 텍스트)

    -- 법률 분류
    legal_category VARCHAR(100),                   -- 법률 카테고리 (민사, 형사, 행정 등)
    risk_level VARCHAR(20),                        -- 위험도 (low, medium, high, critical)

    -- Gemini 메타데이터
    gemini_model VARCHAR(50),                      -- 사용된 Gemini 모델 (gemini-2.0-flash-exp 등)
    prompt_tokens INTEGER,                         -- 프롬프트 토큰 수
    completion_tokens INTEGER,                     -- 완료 토큰 수

    -- 타임스탬프
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 업로드 시각
    analyzed_at TIMESTAMP,                           -- 분석 완료 시각
    expires_at TIMESTAMP,                            -- 만료 시각 (자동 삭제 기준)

    -- 인덱스
    CONSTRAINT unique_file_hash UNIQUE (file_hash)
);

-- 2. 인덱스 생성 (쿼리 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_uploaded_documents_status
    ON uploaded_documents(status);

CREATE INDEX IF NOT EXISTS idx_uploaded_documents_uploaded_at
    ON uploaded_documents(uploaded_at DESC);

CREATE INDEX IF NOT EXISTS idx_uploaded_documents_user_ip
    ON uploaded_documents(user_ip);

CREATE INDEX IF NOT EXISTS idx_uploaded_documents_legal_category
    ON uploaded_documents(legal_category);

CREATE INDEX IF NOT EXISTS idx_uploaded_documents_expires_at
    ON uploaded_documents(expires_at);

-- 3. 자동 삭제 함수 (만료된 문서 정리)
CREATE OR REPLACE FUNCTION cleanup_expired_documents()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM uploaded_documents
    WHERE expires_at < CURRENT_TIMESTAMP
    RETURNING COUNT(*) INTO deleted_count;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 4. 통계 뷰 (관리자용)
CREATE OR REPLACE VIEW document_upload_stats AS
SELECT
    DATE(uploaded_at) AS upload_date,
    COUNT(*) AS total_uploads,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) AS completed_count,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_count,
    ROUND(AVG(file_size) / 1024.0, 2) AS avg_file_size_kb,
    legal_category,
    risk_level
FROM uploaded_documents
WHERE uploaded_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(uploaded_at), legal_category, risk_level
ORDER BY upload_date DESC;

-- 5. 코멘트 추가
COMMENT ON TABLE uploaded_documents IS 'v60 사용자 문서 업로드 및 법률 분석 테이블';
COMMENT ON COLUMN uploaded_documents.file_hash IS '중복 업로드 방지용 SHA-256 해시';
COMMENT ON COLUMN uploaded_documents.status IS 'pending: 대기중, processing: 분석중, completed: 완료, failed: 실패';
COMMENT ON COLUMN uploaded_documents.risk_level IS '법률 위험도: low, medium, high, critical';
COMMENT ON COLUMN uploaded_documents.expires_at IS '자동 삭제 기준 시각 (기본 7일 후)';

-- 완료 메시지
DO $$
BEGIN
    RAISE NOTICE '✅ Lawmadi OS v60 문서 업로드 테이블 마이그레이션 완료';
END $$;
