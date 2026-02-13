# 🔑 법령 API 인증키 발급 가이드

**작성일**: 2026-02-13
**대상**: law.go.kr Open API

---

## 📋 발급 절차 (10분 소요)

### 1단계: law.go.kr 회원가입/로그인

```
🌐 접속: https://open.law.go.kr/
```

1. 우측 상단 **[회원가입]** 클릭
   - 이미 계정이 있다면 **[로그인]**

2. 회원가입 정보 입력
   - 이메일 주소
   - 비밀번호
   - 이름
   - 연락처

3. 이메일 인증 완료

---

### 2단계: Open API 인증키 신청

1. 로그인 후 상단 메뉴 **[Open API]** → **[인증키 발급]** 클릭

2. 신청 정보 입력:

   | 항목 | 입력 내용 |
   |------|----------|
   | **활용 분야** | 법률 상담 서비스 |
   | **시스템명** | Lawmadi OS |
   | **예상 트래픽** | 1,000건/일 |
   | **활용 목적** | AI 기반 법률 자문 시스템 구축 |

3. **[신청하기]** 버튼 클릭

4. 신청 완료 메시지 확인

---

### 3단계: 인증키 확인

1. 상단 메뉴 **[마이페이지]** 클릭

2. **[나의 인증키]** 또는 **[API 관리]** 섹션 확인

3. 인증키 복사
   - 형식: 영문/숫자 조합 (예: `abc123def456`)
   - ⚠️ **공백이 포함되지 않도록** 주의

4. 승인 상태 확인
   - **즉시 발급**: 대부분 즉시 사용 가능
   - **승인 대기**: 1-2시간 소요 (영업일 기준)

---

## 🔧 인증키 설정

### 방법 1: 자동 설정 스크립트 (권장)

```bash
cd /workspaces/lawmadi-os-v50
bash setup_law_api_keys.sh
```

스크립트 실행 후:
1. 발급받은 인증키 입력
2. 자동으로 `.env` 파일 업데이트
3. 연결 테스트 자동 실행

---

### 방법 2: 수동 설정

```bash
# 1. .env 파일 편집
nano .env

# 2. 다음 라인 수정 (또는 추가)
LAWGO_DRF_OC="여기에_발급받은_인증키_입력"

# 3. 저장 후 종료
# Ctrl+O, Enter, Ctrl+X

# 4. 환경변수 로드
source .env

# 5. 확인
echo $LAWGO_DRF_OC
```

---

## 🧪 연결 테스트

### 테스트 1: 직접 API 호출

```bash
curl "https://open.law.go.kr/LSO/nsmLawService.do?OC=YOUR_KEY&target=law&type=XML&mstSeq=1" | head -20
```

**성공 시**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<law>
  <법령ID>000001</법령ID>
  <법령명한글>민법</법령명한글>
  ...
</law>
```

**실패 시**:
```xml
<error>사용자인증에 실패하였습니다</error>
```

---

### 테스트 2: Lawmadi OS 통합 테스트

```bash
# 서버 재시작 (환경변수 적용)
pkill -f "python main.py"
python main.py &

# 법령 검색 테스트
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "민법 제1조"}'
```

**성공 시**: 법령 조문이 포함된 상세한 답변 반환

---

## 🔍 문제 해결

### 문제 1: "사용자인증에 실패하였습니다"

**원인**:
- 인증키가 잘못됨
- 인증키 복사 시 공백 포함
- 승인 대기 중

**해결**:
1. 마이페이지에서 인증키 재확인
2. 복사 시 앞뒤 공백 제거
3. 승인 상태 확인 (1-2시간 대기)
4. 재신청 고려

---

### 문제 2: 연결 타임아웃

**원인**:
- 네트워크 문제
- law.go.kr 서버 점검

**해결**:
```bash
# 네트워크 확인
ping open.law.go.kr

# 서버 상태 확인
curl -I https://open.law.go.kr/
```

---

### 문제 3: 트래픽 제한

**증상**: "일일 한도 초과" 오류

**해결**:
1. 마이페이지에서 현재 사용량 확인
2. 트래픽 증량 신청
   - [Open API] → [트래픽 증량 신청]
   - 사유: 서비스 확대

---

## 📞 지원

### law.go.kr 고객센터
- **전화**: 044-200-6560
- **이메일**: law@moleg.go.kr
- **운영 시간**: 평일 09:00-18:00

### Lawmadi OS 관련
- **GitHub Issues**: https://github.com/your-repo/lawmadi-os/issues
- **문서**: QUICK_FIX_GUIDE.md

---

## 📌 참고 정보

### API 사용량 모니터링

```bash
# DB에서 DRF 호출 통계 확인
python -c "
from connectors.db_client_v2 import execute
result = execute('''
    SELECT COUNT(*) as total_calls,
           DATE(created_at) as call_date
    FROM drf_cache
    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY DATE(created_at)
    ORDER BY call_date DESC
''', fetch='all')
print(result)
"
```

### 캐싱 설정

법령 API 호출을 줄이기 위해 캐싱 활성화:

```bash
# .env 파일
ENABLE_DB_CACHE=true  # DRF 응답 캐싱 활성화
```

캐시 유효 기간: 7일 (법령은 자주 변경되지 않음)

---

**마지막 업데이트**: 2026-02-13
**다음 리뷰**: 인증키 발급 완료 후
