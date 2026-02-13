#!/bin/bash
# 법령 API 인증키 설정 스크립트

echo "=========================================="
echo "법령 API 인증키 설정 도구"
echo "=========================================="
echo ""

# 현재 설정 확인
echo "📋 현재 설정:"
echo "-------------------------------------------"
if [ -f .env ]; then
    echo "LAWGO_DRF_OC: $(grep LAWGO_DRF_OC .env | cut -d'=' -f2)"
else
    echo "⚠️  .env 파일이 없습니다."
fi
echo ""

# 안내 메시지
echo "🔑 law.go.kr 인증키 발급 방법:"
echo "-------------------------------------------"
echo "1. 브라우저에서 https://open.law.go.kr/ 접속"
echo "2. 우측 상단 [회원가입] 또는 [로그인]"
echo "3. 로그인 후 상단 메뉴 [Open API] → [인증키 발급]"
echo "4. 신청 정보 입력:"
echo "   - 활용 분야: 법률 상담 서비스"
echo "   - 시스템명: Lawmadi OS"
echo "   - 예상 트래픽: 1000건/일"
echo "5. 신청 완료 후 마이페이지에서 인증키 확인"
echo ""
echo "⏱️  발급 시간: 즉시 또는 승인 후 (보통 1-2시간 이내)"
echo ""

# 사용자 입력 받기
read -p "✅ 인증키를 발급받으셨습니까? (y/n): " got_key

if [ "$got_key" != "y" ] && [ "$got_key" != "Y" ]; then
    echo ""
    echo "📌 인증키를 발급받은 후 다시 실행해주세요."
    echo "   실행 명령: bash setup_law_api_keys.sh"
    exit 0
fi

echo ""
echo "🔐 인증키 입력:"
echo "-------------------------------------------"
read -p "law.go.kr 인증키를 입력하세요: " lawgo_key

if [ -z "$lawgo_key" ]; then
    echo "❌ 인증키가 입력되지 않았습니다."
    exit 1
fi

# .env 파일 백업
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 기존 .env 파일 백업 완료"
fi

# .env 파일 업데이트
if grep -q "LAWGO_DRF_OC=" .env 2>/dev/null; then
    # 기존 값 업데이트
    sed -i "s/^LAWGO_DRF_OC=.*/LAWGO_DRF_OC=$lawgo_key/" .env
    echo "✅ .env 파일 업데이트 완료"
else
    # 새로운 라인 추가
    echo "LAWGO_DRF_OC=$lawgo_key" >> .env
    echo "✅ .env 파일에 인증키 추가 완료"
fi

echo ""
echo "🧪 연결 테스트 중..."
echo "-------------------------------------------"

# 환경변수 로드
export $(grep LAWGO_DRF_OC .env | xargs)

# 테스트 스크립트 생성 및 실행
cat > /tmp/test_lawgo_api.py << 'EOF'
import requests
import os
import sys

api_key = os.getenv("LAWGO_DRF_OC")
if not api_key:
    print("❌ 환경변수 LAWGO_DRF_OC가 설정되지 않았습니다.")
    sys.exit(1)

# 법령 검색 테스트
url = "https://open.law.go.kr/LSO/nsmLawService.do"
params = {
    "OC": api_key,
    "target": "law",
    "type": "XML",
    "mstSeq": "1"  # 민법
}

try:
    response = requests.get(url, params=params, timeout=10)

    if response.status_code == 200:
        content = response.text

        # 에러 체크
        if "사용자인증에 실패하였습니다" in content:
            print("❌ 인증 실패: 인증키가 올바르지 않거나 승인되지 않았습니다.")
            print("   - 마이페이지에서 인증키를 다시 확인해주세요.")
            print("   - 신청 후 승인 대기 중일 수 있습니다 (1-2시간 소요)")
            sys.exit(1)
        elif "<?xml" in content and "<law>" in content:
            print("✅ law.go.kr API 연결 성공!")
            print(f"   인증키: {api_key[:10]}***")
            print("   응답: 정상 (XML 데이터 수신)")
            sys.exit(0)
        else:
            print("⚠️  응답을 받았으나 예상과 다릅니다.")
            print(f"   응답 시작: {content[:200]}")
            sys.exit(1)
    else:
        print(f"❌ HTTP {response.status_code} 오류")
        sys.exit(1)

except Exception as e:
    print(f"❌ 연결 오류: {e}")
    sys.exit(1)
EOF

python /tmp/test_lawgo_api.py
test_result=$?

echo ""
if [ $test_result -eq 0 ]; then
    echo "=========================================="
    echo "🎉 설정 완료!"
    echo "=========================================="
    echo ""
    echo "다음 단계:"
    echo "1. 서버 재시작 (환경변수 적용)"
    echo "   pkill -f 'python main.py'"
    echo "   python main.py &"
    echo ""
    echo "2. 법령 검색 테스트"
    echo "   curl -X POST http://localhost:8080/ask \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"query\": \"민법 제1조\"}'"
else
    echo "=========================================="
    echo "⚠️  설정이 완료되었으나 테스트 실패"
    echo "=========================================="
    echo ""
    echo "문제 해결:"
    echo "1. law.go.kr 마이페이지에서 인증키 재확인"
    echo "2. 승인 상태 확인 (신청 후 1-2시간 소요 가능)"
    echo "3. 인증키 복사 시 앞뒤 공백 제거 확인"
    echo ""
    echo "재시도: bash setup_law_api_keys.sh"
fi

echo ""
