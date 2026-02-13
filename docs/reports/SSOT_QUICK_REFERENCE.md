# SSOT Phase 1 빠른 참조 가이드

## 🚀 빠른 시작

### 1. 테스트 실행
```bash
# DRF API 레벨 테스트
python test_ssot_phase1.py

# Tool 함수 레벨 테스트
python test_ssot_tools.py

# 캐시 검증
python verify_cache.py
```

### 2. 새로운 SSOT 사용하기

#### Python 코드에서
```python
from connectors.drf_client import DRFConnector

drf = DRFConnector(api_key="your_api_key")

# 행정규칙 검색
result = drf.search_by_target("공무원 복무규정", target="admrul")

# 법령해석례 검색
result = drf.search_by_target("행정절차법 해석", target="expc")

# 헌재결정례 검색 (판례 target 사용)
result = drf.search_by_target("재산권 침해", target="prec")
```

#### SearchService에서
```python
from services.search_service import SearchService

svc = SearchService()

# 행정규칙
admrul_result = svc.search_admrul("공무원 복무규정")

# 법령해석례
expc_result = svc.search_expc("행정절차법 해석")

# 헌재결정례
const_result = svc.search_constitutional("재산권 침해")
```

#### Gemini Tool에서 (main.py)
```python
# Tool 함수가 자동으로 RUNTIME에서 서비스 가져옴
result = search_admrul_drf("공무원 복무규정")
result = search_expc_drf("행정절차법 해석")
result = search_constitutional_drf("재산권 침해")
```

---

## 📋 SSOT 매핑 테이블

| SSOT | 이름 | Target | Response Key | Items Key | 상태 |
|------|------|--------|--------------|-----------|------|
| #1 | 현행법령 | law | LawSearch | law | ✅ 활성 |
| #2 | 행정규칙 | admrul | AdmRulSearch | admrul | ✅ 활성 |
| #5 | 판례 | prec | PrecSearch | prec | ✅ 활성 |
| #6 | 헌재결정례 | prec | PrecSearch | prec | ✅ 활성 |
| #7 | 법령해석례 | expc | Expc | - | ✅ 활성 |
| #3 | 학칙공단 | edulaw | - | - | 🔄 Phase 2 |
| #4 | 자치법규 | adrule | - | - | 🔄 Phase 2 |
| #8 | 행정심판례 | adprec | - | - | 🔄 Phase 2 |
| #9 | 조약 | treaty | - | - | 🔄 Phase 2 |
| #10 | 법령용어 | lword | - | - | 🔄 Phase 3 |

---

## 🛠️ Tool 함수 목록

### 기존 (Phase 0)
1. `search_law_drf(query)` - 현행법령 검색
2. `search_precedents_drf(query)` - 판례 검색

### 신규 (Phase 1)
3. `search_admrul_drf(query)` - 행정규칙 검색
4. `search_expc_drf(query)` - 법령해석례 검색
5. `search_constitutional_drf(query)` - 헌재결정례 검색

**모든 tool 함수는 다음 형식으로 응답:**
```python
{
    "result": "FOUND" | "NO_DATA" | "ERROR",
    "content": {...},  # result=FOUND일 때만
    "source": "국가법령정보센터(...)",
    "message": "..."  # result=ERROR일 때만
}
```

---

## 🔍 캐시 구조

### 캐시 키 형식
```
drf:v2:{target}:{md5_hash_of_query}
```

### 예시
- `drf:v2:law:5d41402abc4b2a76b9719d911017c592` (query="민법", target="law")
- `drf:v2:admrul:5d41402abc4b2a76b9719d911017c592` (query="민법", target="admrul")

**동일 쿼리라도 target이 다르면 별도 캐시 항목**

### TTL
- **기본값:** 3600초 (1시간)
- **설정 위치:** `drf_client.py` line ~154

---

## 🐛 트러블슈팅

### 문제: "DRF unexpected Content-Type: text/html"
**원인:** Target 파라미터가 DRF API에서 지원되지 않음
**해결:**
1. config.json에서 해당 SSOT `enabled: false` 설정
2. DRF API 문서에서 올바른 target 값 확인

### 문제: "SearchService not ready"
**원인:** LAWGO_DRF_OC 환경변수 미설정
**해결:**
```bash
export LAWGO_DRF_OC="your_api_key"
```

### 문제: 캐시 미작동
**원인:** DB 연결 실패 또는 db_client_v2 import 오류
**해결:**
1. 로그 확인: `⚠️ DRF 캐싱 비활성화`
2. DB 연결 상태 확인
3. connectors/db_client_v2.py 파일 존재 확인

---

## 📊 로그 메시지 가이드

### 정상 동작
```
🎯 [Cache HIT] target=admrul, query=공무원 복무규정
[DualSSOT] SUCCESS via DRF-1 (target=admrul)
💾 [Cache SET] drf:v2:admrul:a1b2c3... (TTL: 1h)
🛠️ [L3 Strike] 행정규칙 검색 호출: '공무원 복무규정'
```

### 오류 상황
```
⚠️ SearchService not ready (admrul)
⚠️ search_admrul failed: DRF not available
[DualSSOT] All attempts failed for target=admrul
```

---

## 🔗 관련 파일

### 구현 파일
- `config.json` - SSOT 레지스트리
- `connectors/drf_client.py` - DRF API 클라이언트
- `services/search_service.py` - 검색 서비스 Facade
- `main.py` - Gemini Tool 함수 및 /ask 엔드포인트

### 테스트 파일
- `test_ssot_phase1.py` - DRF API 레벨 통합 테스트
- `test_ssot_tools.py` - Tool 함수 레벨 통합 테스트
- `verify_cache.py` - 캐시 검증 테스트

### 문서 파일
- `SSOT_PHASE1_IMPLEMENTATION_REPORT.md` - 상세 구현 보고서
- `SSOT_QUICK_REFERENCE.md` - 빠른 참조 가이드 (현재 파일)
- `claude.md` (Line 498-545) - SSOT 10개 원본 정의

---

## 📞 다음 단계

### Phase 2 준비
1. DRF API 문서에서 다음 target 조사:
   - `edulaw` (학칙공단)
   - `adrule` (자치법규)
   - `adprec` (행정심판례)
   - `treaty` (조약)

2. 각 target별 테스트 요청:
```bash
curl "https://www.law.go.kr/DRF/lawSearch.do?OC=YOUR_KEY&target=edulaw&type=JSON&query=테스트"
```

3. HTML 에러 페이지 반환 시:
   - 다른 target 값 시도
   - DRF API 공식 문서 재확인

### Phase 3 준비
1. lawService.do 엔드포인트 조사
2. 법령일련번호 획득 방법 연구
3. 별도 connector 메서드 설계

---

**마지막 업데이트:** 2026-02-13
**버전:** Lawmadi OS v50.3.0-FINAL
