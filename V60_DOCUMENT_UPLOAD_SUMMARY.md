# Lawmadi OS v60 - 문서 업로드 및 법률 분석 기능

**구현 완료일:** 2026-02-13
**버전:** v60.0.0
**핵심 기능:** 사용자 문서/이미지 업로드 → AI 법률 분석

---

## 📋 구현 내용

### 1. 데이터베이스 스키마

**파일:** `scripts/migrate_v60_documents.sql`

#### uploaded_documents 테이블
```sql
- id (SERIAL PRIMARY KEY)
- filename (VARCHAR 500) - 원본 파일명
- file_path (VARCHAR 1000) - 서버 저장 경로
- file_type (VARCHAR 50) - MIME 타입
- file_size (INTEGER) - 파일 크기 (bytes)
- file_hash (VARCHAR 64) - SHA-256 해시 (중복 방지)
- user_ip (VARCHAR 45) - 업로드 사용자 IP
- status (VARCHAR 20) - pending/processing/completed/failed
- analysis_result (TEXT) - 분석 결과 JSON
- analysis_summary (TEXT) - 분석 요약
- legal_category (VARCHAR 100) - 법률 카테고리
- risk_level (VARCHAR 20) - low/medium/high/critical
- gemini_model (VARCHAR 50) - 사용된 Gemini 모델
- uploaded_at (TIMESTAMP) - 업로드 시각
- analyzed_at (TIMESTAMP) - 분석 완료 시각
- expires_at (TIMESTAMP) - 만료 시각 (기본 7일 후)
```

**인덱스:**
- status, uploaded_at, user_ip, legal_category, expires_at

**자동 정리 함수:**
- `cleanup_expired_documents()` - 만료된 문서 자동 삭제

**통계 뷰:**
- `document_upload_stats` - 일별 업로드 통계

---

### 2. 백엔드 API 엔드포인트

**파일:** `main.py`

#### POST /upload
사용자 문서/이미지 업로드

**지원 파일:**
- 이미지: `.jpg`, `.jpeg`, `.png`, `.webp`
- 문서: `.pdf`

**파일 제한:**
- 최대 크기: 10MB
- 중복 방지: SHA-256 해시

**응답:**
```json
{
  "ok": true,
  "file_id": "abc12345",
  "filename": "contract.pdf",
  "file_size": 123456,
  "file_hash": "sha256...",
  "analysis_url": "/analyze-document/abc12345"
}
```

#### POST /analyze-document/{file_id}
업로드된 문서 법률 분석

**쿼리 파라미터:**
- `analysis_type`: general | contract | risk_assessment

**분석 기능:**
1. **이미지 분석** (Gemini Vision)
   - 계약서 OCR 및 조항 분석
   - 법률적 쟁점 추출
   - 위험도 평가

2. **PDF 분석** (PyPDF2 + Gemini)
   - 텍스트 추출
   - 법률적 검토
   - 권고사항 제시

**응답:**
```json
{
  "ok": true,
  "file_id": "abc12345",
  "filename": "contract.pdf",
  "analysis": {
    "summary": "계약서 요약",
    "document_type": "임대차계약서",
    "legal_issues": ["법률적 쟁점 1", "법률적 쟁점 2"],
    "risk_level": "medium",
    "recommendations": ["권고사항 1", "권고사항 2"],
    "legal_category": "민사",
    "key_points": ["핵심 내용"]
  }
}
```

---

### 3. 프론트엔드 UI

**파일:** `frontend/public/index.html`

#### 업로드 버튼
- 녹색 아이콘 버튼 (업로드 아이콘)
- 입력창 왼쪽에 배치
- 파일 선택 시 미리보기 표시

#### 파일 미리보기
- 파일명, 파일 크기 표시
- 제거 버튼 (X)
- 녹색 테두리

#### 분석 결과 표시
- 문서 요약
- 법률 분야
- 위험도 (🟢🟡🟠🔴)
- 법률적 쟁점
- 권고사항
- 핵심 내용

---

## 🛠️ 기술 스택

### 백엔드
- **FastAPI**: 파일 업로드 처리 (`UploadFile`, `File`)
- **python-multipart**: 멀티파트 폼 데이터 처리
- **PyPDF2**: PDF 텍스트 추출
- **Gemini Vision**: 이미지 OCR 및 분석
- **PostgreSQL**: 파일 메타데이터 및 분석 결과 저장

### 프론트엔드
- **FormData API**: 파일 업로드
- **Material Symbols**: 아이콘
- **Fetch API**: 비동기 파일 전송

---

## 📊 워크플로우

```
1. 사용자가 파일 선택 (JPG/PNG/PDF)
   ↓
2. 프론트엔드에서 파일 미리보기 표시
   ↓
3. 전송 버튼 클릭
   ↓
4. POST /upload → 파일 서버에 저장 (uploads/)
   ↓
5. POST /analyze-document/{file_id} → Gemini Vision/Flash 분석
   ↓
6. 분석 결과 DB 저장 + 프론트엔드 표시
   ↓
7. 7일 후 자동 삭제 (만료 시각)
```

---

## 🔒 보안 고려사항

1. **파일 크기 제한**: 10MB (DoS 방지)
2. **파일 타입 검증**: 허용된 확장자만 업로드
3. **SHA-256 해시**: 중복 업로드 방지 및 무결성 검증
4. **사용자 IP 기록**: 악용 추적 가능
5. **자동 만료**: 7일 후 자동 삭제 (스토리지 관리)
6. **파일명 안전화**: `{hash[:8]}_{원본파일명}` 형식

---

## 📁 파일 저장 구조

```
uploads/
├── abc12345_contract.pdf          # {파일해시[:8]}_{원본파일명}
├── def67890_receipt.jpg
└── ghi11121_agreement.png
```

---

## 🧪 테스트 방법

### 로컬 테스트

1. **서버 시작**
   ```bash
   uvicorn main:app --reload --port 8080
   ```

2. **브라우저 접속**
   ```
   http://localhost:8080
   ```

3. **파일 업로드**
   - 업로드 버튼 (녹색 아이콘) 클릭
   - 이미지 또는 PDF 선택
   - 전송 버튼 클릭

4. **분석 결과 확인**
   - 문서 요약, 법률적 쟁점, 권고사항 등 표시

### API 직접 테스트

#### 파일 업로드
```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@contract.pdf"
```

#### 문서 분석
```bash
curl -X POST http://localhost:8080/analyze-document/abc12345?analysis_type=contract
```

---

## 📝 DB 마이그레이션 실행

### Python 스크립트 사용
```bash
python scripts/run_migration.py
```

### SQL 직접 실행 (PostgreSQL 설치 시)
```bash
psql $DATABASE_URL -f scripts/migrate_v60_documents.sql
```

**주의:** 현재 개발 환경에서는 DB가 비활성화되어 있을 수 있습니다.
프로덕션 배포 시 환경변수 `DATABASE_URL` 설정 후 마이그레이션 실행 필요.

---

## 🚀 배포 체크리스트

- [x] 데이터베이스 스키마 작성
- [x] 백엔드 API 구현
- [x] 프론트엔드 UI 추가
- [x] 의존성 업데이트 (requirements.txt)
- [x] uploads/ 폴더 생성
- [ ] DB 마이그레이션 실행 (프로덕션)
- [ ] 파일 업로드 테스트 (로컬)
- [ ] 문서 분석 테스트 (Gemini Vision)
- [ ] 프로덕션 배포 (Cloud Run)
- [ ] Firebase Hosting 업데이트

---

## 🎯 v60.1.0 향후 개선 사항

1. **파일 저장소 확장**
   - Google Cloud Storage 연동
   - S3 호환 스토리지 지원

2. **OCR 정확도 향상**
   - Google Vision API 통합
   - 다국어 문서 지원

3. **분석 기능 고도화**
   - 계약서 조항별 위험도 점수
   - 유사 판례 자동 검색
   - 법률 용어 자동 설명

4. **사용자 경험 개선**
   - 드래그 앤 드롭 업로드
   - 실시간 분석 진행률 표시
   - 분석 결과 PDF 다운로드

5. **관리 기능**
   - 관리자 대시보드 (업로드 통계)
   - 악용 방지 (IP별 업로드 제한)

---

**버전:** v60.0.0
**작성자:** Claude Code
**최종 업데이트:** 2026-02-13
