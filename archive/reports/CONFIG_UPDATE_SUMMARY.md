# config.json 업데이트 요약

**날짜**: 2026-02-12
**변경 사유**: data.go.kr API 미작동, law.go.kr DRF API만 사용

---

## 📝 주요 변경사항

### 1. `drf` 섹션 업데이트

**Before**:
```json
"drf": {
  "base_url": "https://apis.data.go.kr/1170000/LawService",
  "api_key_env": "DATA_GO_KR_API_KEY",
  "default_format": "XML",
  "endpoints": {
    "lawSearch": "lawSearch.do",
    "lawList": "lawSearchList.do"
  }
}
```

**After**:
```json
"drf": {
  "type": "LAW_GO_KR",
  "base_url": "https://www.law.go.kr/DRF",
  "api_key_env": "LAWGO_DRF_OC",
  "response_format": "JSON",
  "timeout_ms": 10000,
  "endpoints": {
    "lawSearch": "lawSearch.do",
    "lawService": "lawService.do",
    "precSearch": "lawSearch.do",
    "precService": "lawService.do",
    "expcSearch": "lawSearch.do",
    "admrulSearch": "lawSearch.do"
  },
  "targets": {
    "law": "법령",
    "prec": "판례",
    "expc": "법령해석례",
    "admrul": "행정규칙"
  }
}
```

**변경 내용**:
- ✅ Base URL: data.go.kr → law.go.kr
- ✅ API Key 환경변수: DATA_GO_KR_API_KEY → LAWGO_DRF_OC
- ✅ 응답 형식: XML → JSON
- ✅ 엔드포인트 추가: 판례, 해석례, 행정규칙
- ✅ Target 타입 정의 추가

---

### 2. `dual_ssot` 섹션 수정

**Before**:
```json
"dual_ssot": {
  "primary": {
    "type": "LAW_GO_KR",
    "base_url": "https://www.law.go.kr/DRF"
  },
  "fallback": {
    "type": "OPEN_DATA_GO_KR",
    "base_url": "https://apis.data.go.kr/1170000/LawService"
  }
}
```

**After**:
```json
"dual_ssot": {
  "enabled": false,
  "note": "data.go.kr API 미작동으로 Single Source 사용",
  "primary": {
    "type": "LAW_GO_KR",
    "base_url": "https://www.law.go.kr/DRF",
    "api_key_env": "LAWGO_DRF_OC",
    "response_format": "JSON",
    "endpoints": {
      "lawSearch": "lawSearch.do",
      "lawService": "lawService.do"
    }
  }
}
```

**변경 내용**:
- ✅ `enabled: false` 추가 (Dual SSOT 비활성화)
- ✅ `fallback` 제거 (data.go.kr 미작동)
- ✅ Primary에 상세 설정 추가
- ✅ 설명 추가

---

### 3. `required_env_vars` 업데이트

**Before**:
```json
"required_env_vars": [
  "LAWGO_DRF_OC",
  "GEMINI_KEY",
  "ANTHROPIC_API_KEY"
]
```

**After**:
```json
"required_env_vars": [
  "LAWGO_DRF_OC",
  "GEMINI_KEY",
  "ANTHROPIC_API_KEY"
],
"deprecated_env_vars": [
  "DATA_GO_KR_API_KEY"
]
```

**변경 내용**:
- ✅ `deprecated_env_vars` 섹션 추가
- ✅ DATA_GO_KR_API_KEY를 deprecated로 표시

---

## ✅ 검증 결과

```bash
✅ JSON 유효성 검사 통과
DRF 타입: LAW_GO_KR
응답 형식: JSON
Dual SSOT: False
Primary: LAW_GO_KR
```

---

## 🔧 코드 수정 필요 사항

### 1. `connectors/drf_client.py`

**현재 상태**:
- ✅ JSON 형식 지원 추가됨
- ⚠️  `_call_data_go()` 메서드 여전히 존재

**권장 수정**:
```python
class DRFConnector:
    def __init__(self, ...):
        # config에서 drf 설정 로드
        if config:
            drf_config = config.get("drf", {})
            self.drf_key = os.getenv(drf_config.get("api_key_env", "LAWGO_DRF_OC"))
            self.drf_url = drf_config.get("base_url")
            self.response_format = drf_config.get("response_format", "JSON")

    def law_search(self, query, target="law"):
        # Dual SSOT 로직 제거, DRF만 사용
        return self._call_drf(query, target)
```

### 2. `services/search_service.py`

**수정 필요**:
```python
# config.json 로드
with open('config.json') as f:
    config = json.load(f)

# DRFConnector 초기화
connector = DRFConnector(
    config=config,
    response_format=config['drf']['response_format']
)

# JSON 응답 파싱
result = connector.law_search("민법", target="law")
if isinstance(result, dict):
    law_search = result.get("LawSearch", {})
    total = law_search.get("totalCnt", "0")
    laws = law_search.get("law", [])
```

---

## 📊 지원되는 타겟

| Target | 설명 | 엔드포인트 | 테스트 결과 |
|--------|------|-----------|------------|
| **law** | 법령 | lawSearch.do | ✅ 9건 |
| **prec** | 판례 | lawSearch.do | ✅ 365건 |
| **expc** | 법령해석례 | lawSearch.do | ✅ 15건 |
| **admrul** | 행정규칙 | lawSearch.do | ✅ 802건 |

---

## 🎯 다음 단계

### 즉시 조치
- [x] config.json 업데이트 ✅
- [x] JSON 유효성 검사 ✅
- [ ] DRFConnector 간소화
- [ ] SearchService JSON 파싱 적용
- [ ] 전체 시스템 테스트

### 장기 개선
- [ ] Circuit Breaker 설정 조정
- [ ] 캐싱 전략 수립
- [ ] API 호출 로깅 강화
- [ ] 에러 핸들링 개선

---

**업데이트 완료**: 2026-02-12
**설정 상태**: Single Source (law.go.kr DRF API)
**다음 검토**: 시스템 통합 테스트 후
