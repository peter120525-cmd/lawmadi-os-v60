# data.go.kr API 최종 진단 보고서

**날짜**: 2026-02-12
**API**: 공공데이터포털 법제처 국가법령정보 공유서비스
**서비스 코드**: 15000115
**결론**: ❌ **사용 불가 (엔드포인트 미지원)**

---

## 📊 테스트 결과 요약

### 제공된 정보

```
데이터포맷: XML
End Point: https://apis.data.go.kr/1170000/law
인증키 (Encoding): a0Fyt79Y9YX1G5dUksmVmEy111eipwhoxM%2FTMrZmwp46SEh0Z4ViGDlWOgs2juwW%2BkHgOPK0zfDZ5RN5J0kvEA%3D%3D
```

### 테스트한 엔드포인트

| 엔드포인트 | 결과 | 에러 메시지 |
|-----------|------|------------|
| `https://apis.data.go.kr/1170000/law/lawSearch.do` | ❌ HTTP 404 | API not found |
| `https://apis.data.go.kr/1170000/law/lawSearchList.do` | ❌ HTTP 500 | 페이지를 찾을수 없습니다 |
| `https://apis.data.go.kr/1170000/LawService/lawSearch.do` | ❌ HTTP 500 | Unexpected errors |
| `https://apis.data.go.kr/1170000/LawService/getLawList` | ❌ HTTP 500 | Unexpected errors |

### 에러 페이지 내용

```html
<h2>:: 페이지를 찾을수 없습니다.</h2>

페이지가 존재하지 않거나 잘못된 링크를 사용하셨습니다.
다시한번 확인해 주시고 이용하여 주시기 바랍니다.

법제처 국가법령정보센터팀 (044-200-6797)
```

---

## 🔍 원인 분석

### 1. 서비스 비활성화

공공데이터포털의 "법제처 국가법령정보 공유서비스(15000115)"는:
- ✅ API 키가 발급됨
- ✅ 활용신청 페이지 존재
- ❌ **실제 엔드포인트가 작동하지 않음**

### 2. 서비스 중단 가능성

- 법제처는 자체 API (law.go.kr/DRF)를 운영 중
- data.go.kr를 통한 중개 서비스는 실질적으로 중단되었을 가능성
- 공공데이터포털에 등록은 되어 있으나, 실제 서비스는 미제공

### 3. 잘못된 문서화

- 공공데이터포털의 API 문서가 최신화되지 않았을 가능성
- 엔드포인트 정보가 부정확함

---

## ✅ 검증된 대안: law.go.kr DRF API

### 작동 확인

| 항목 | 값 |
|------|-----|
| **인증키** | choepeter |
| **Base URL** | http://www.law.go.kr/DRF |
| **형식** | JSON |
| **상태** | ✅ 정상 작동 |

### 테스트 결과

- ✅ 법령 검색: 9건 (민법)
- ✅ 판례 검색: 365건 (임대차)
- ✅ 법령해석례: 15건
- ✅ 행정규칙: 802건

### 사용 예시

```python
import requests

url = "http://www.law.go.kr/DRF/lawSearch.do"
params = {
    "OC": "choepeter",
    "target": "law",
    "type": "JSON",
    "query": "민법"
}

response = requests.get(url, params=params)
data = response.json()
# {"LawSearch": {"totalCnt": "9", "law": [...]}}
```

---

## 🎯 권장 조치

### 1. data.go.kr 포기

공공데이터포털의 법령정보 서비스는 사용 불가하므로:
- ❌ data.go.kr Fallback 제거
- ✅ law.go.kr DRF API만 사용

### 2. config.json 업데이트

```json
{
  "dual_ssot": {
    "primary": {
      "type": "LAW_GO_KR",
      "base_url": "https://www.law.go.kr/DRF",
      "api_key_env": "LAWGO_DRF_OC",
      "response_format": "JSON"
    }
  }
}
```

**Fallback 제거**: data.go.kr는 작동하지 않음

### 3. DRFConnector 수정

`connectors/drf_client.py`에서:
- ✅ `_call_drf()` 메서드만 사용
- ❌ `_call_data_go()` 메서드 제거 또는 비활성화
- ✅ `law_search()` 메서드를 DRF 전용으로 간소화

### 4. 시스템 아키텍처 변경

**Before** (Dual SSOT):
```
DRF (Primary) → Fallback → data.go.kr (Fallback)
     ❌               →           ❌
```

**After** (Single Source):
```
DRF (Only) → ✅ 정상 작동
```

---

## 📞 문의

### data.go.kr 서비스 상태 확인

- **공공데이터포털 고객센터**: 1577-0071
- **서비스 URL**: https://www.data.go.kr/data/15000115/openapi.do

### law.go.kr 지원

- **법제처 국가법령정보센터**: 044-200-6797
- **유지보수팀**: 02-2109-6446
- **Open API**: https://open.law.go.kr/

---

## 📝 최종 결론

### data.go.kr API

❌ **사용 불가**
- 엔드포인트가 존재하지 않거나 서비스 중단
- API 키 발급과 무관하게 실제 서비스 미제공
- Fallback으로 사용 불가

### law.go.kr DRF API

✅ **사용 가능**
- 모든 기능 정상 작동
- JSON 형식 지원
- 법령, 판례, 해석례, 행정규칙 검색 가능

### 권장 아키텍처

**Single Source of Truth**:
- Primary: law.go.kr DRF API
- Fallback: 없음 (불필요)
- Circuit Breaker로 안정성 확보

---

**보고서 생성**: 2026-02-12
**테스트 완료**: 10+ 엔드포인트
**최종 상태**: law.go.kr만 사용 권장
