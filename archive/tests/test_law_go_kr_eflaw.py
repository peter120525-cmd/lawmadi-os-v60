#!/usr/bin/env python3
"""law.go.kr 현행법령 본문 조회 API 테스트"""
import os
import requests
import xml.etree.ElementTree as ET

api_key = os.getenv("LAWGO_DRF_OC", "")

print("=" * 70)
print("🧪 law.go.kr 현행법령 본문 조회 API 테스트")
print("=" * 70)
print(f"LAWGO_DRF_OC: {'✅ 설정됨' if api_key else '❌ 미설정'}")
if api_key:
    print(f"API Key: {api_key[:30]}...")
print()

# 테스트 케이스
test_cases = [
    {
        "name": "인증키 없이 테스트 (공개 API 확인)",
        "url": "http://www.law.go.kr/DRF/lawService.do",
        "params": {
            "target": "eflaw",
            "type": "XML",
            "MST": "138967"  # 민법 법령일련번호 예시
        }
    },
    {
        "name": "lawSearch.do - 법령 검색",
        "url": "http://www.law.go.kr/DRF/lawSearch.do",
        "params": {
            "target": "law",
            "type": "XML",
            "query": "민법"
        }
    }
]

# LAWGO_DRF_OC가 있으면 인증키 포함 테스트 추가
if api_key:
    test_cases.extend([
        {
            "name": "인증키 포함 - lawService.do",
            "url": "http://www.law.go.kr/DRF/lawService.do",
            "params": {
                "OC": api_key,
                "target": "eflaw",
                "type": "XML",
                "MST": "138967"
            }
        },
        {
            "name": "인증키 포함 - lawSearch.do",
            "url": "http://www.law.go.kr/DRF/lawSearch.do",
            "params": {
                "OC": api_key,
                "target": "law",
                "type": "XML",
                "query": "민법"
            }
        }
    ])

success_count = 0

for i, test in enumerate(test_cases, 1):
    print(f"\n[테스트 {i}] {test['name']}")
    print(f"URL: {test['url']}")
    print(f"Params: {test['params']}")

    try:
        response = requests.get(test['url'], params=test['params'], timeout=10)
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'N/A')
        size = len(response.text)

        print(f"✓ Status: {status}")
        print(f"✓ Content-Type: {content_type}")
        print(f"✓ Size: {size} bytes")

        if status == 200:
            print(f"✅ 성공!")

            # XML 파싱 시도
            try:
                root = ET.fromstring(response.text)
                print(f"✓ XML 파싱 성공")
                print(f"✓ Root tag: {root.tag}")

                # 에러 코드 확인
                error_code = root.find('.//error_code')
                if error_code is not None:
                    print(f"⚠️  에러 코드: {error_code.text}")
                else:
                    print(f"✓ 정상 응답 (에러 코드 없음)")

                # 데이터 미리보기
                print(f"\n📄 XML 구조:")
                for child in list(root)[:3]:
                    print(f"   - {child.tag}: {child.text[:50] if child.text else '(empty)'}...")

                success_count += 1
            except ET.ParseError as e:
                print(f"⚠️  XML 파싱 실패: {e}")
                print(f"응답 미리보기: {response.text[:300]}")
        else:
            print(f"❌ 실패 (HTTP {status})")
            print(f"응답: {response.text[:300]}")

    except requests.exceptions.Timeout:
        print(f"❌ 타임아웃")
    except requests.exceptions.RequestException as e:
        print(f"❌ 연결 오류: {e}")
    except Exception as e:
        print(f"❌ 예외: {e}")

print("\n" + "=" * 70)
print(f"📊 결과: {success_count}/{len(test_cases)} 성공")

if success_count > 0:
    print("✅ law.go.kr API가 정상 작동합니다!")
    print("\n💡 다음 단계:")
    print("   1. connectors/drf_client.py의 DRFConnector 클래스 확인")
    print("   2. 성공한 엔드포인트를 사용하도록 설정 업데이트")
    if not api_key:
        print("   3. LAWGO_DRF_OC 환경변수 설정 (더 많은 기능 사용)")
else:
    print("❌ 모든 테스트 실패")
    print("\n💡 확인 사항:")
    print("   1. law.go.kr 서비스 상태 확인")
    print("   2. LAWGO_DRF_OC 인증키 발급 (https://open.law.go.kr/)")
    print("   3. 네트워크 연결 및 방화벽 설정")

print("=" * 70)
