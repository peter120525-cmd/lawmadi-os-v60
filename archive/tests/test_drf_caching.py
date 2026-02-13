#!/usr/bin/env python3
"""
DRF 캐싱 기능 테스트
"""
import os
import time

print("=" * 80)
print("DRF 캐싱 테스트")
print("=" * 80)

# 환경변수 체크
drf_key = os.getenv("LAWGO_DRF_OC")
if not drf_key:
    print("❌ LAWGO_DRF_OC 환경변수가 설정되지 않았습니다.")
    print("   Cloud Run에서만 테스트 가능합니다.")
    exit(0)

print(f"✅ DRF API Key: {drf_key[:10]}...")
print()

# DRFConnector 임포트
try:
    from connectors.drf_client import DRFConnector
    print("✅ DRFConnector 임포트 성공")
except Exception as e:
    print(f"❌ 임포트 실패: {e}")
    exit(1)

# 테스트 쿼리
test_query = "민법 제750조"

# DRF 클라이언트 생성
drf = DRFConnector(api_key=drf_key)
print(f"✅ DRFConnector 초기화 완료")
print()

# 첫 번째 호출 (캐시 미스 예상)
print("=" * 80)
print(f"테스트 1: 첫 번째 호출 (캐시 MISS 예상)")
print("=" * 80)
start_time = time.time()
try:
    result1 = drf.law_search(test_query)
    elapsed1 = time.time() - start_time

    if result1 is not None:
        print(f"✅ 조회 성공: {elapsed1:.2f}초")
        # XML 루트 태그 확인
        print(f"   Root tag: {result1.tag if hasattr(result1, 'tag') else 'N/A'}")
    else:
        print(f"❌ 조회 실패 (None 반환)")
except Exception as e:
    elapsed1 = time.time() - start_time
    print(f"❌ 에러 발생: {e} ({elapsed1:.2f}초)")

print()

# 잠시 대기
time.sleep(1)

# 두 번째 호출 (캐시 HIT 예상)
print("=" * 80)
print(f"테스트 2: 두 번째 호출 (캐시 HIT 예상)")
print("=" * 80)
start_time = time.time()
try:
    result2 = drf.law_search(test_query)
    elapsed2 = time.time() - start_time

    if result2 is not None:
        print(f"✅ 조회 성공: {elapsed2:.2f}초")
        print(f"   Root tag: {result2.tag if hasattr(result2, 'tag') else 'N/A'}")

        # 속도 비교
        if elapsed1 > 0:
            speedup = elapsed1 / elapsed2
            print()
            print(f"📊 성능 비교:")
            print(f"   첫 번째: {elapsed1:.2f}초")
            print(f"   두 번째: {elapsed2:.2f}초")
            print(f"   개선율: {speedup:.1f}배 빠름")

            if elapsed2 < 0.5:
                print(f"   ✅ 캐시 HIT 확인! (0.5초 미만)")
            elif elapsed2 < elapsed1 * 0.3:
                print(f"   ✅ 캐시 HIT 가능성 높음 (70% 이상 빠름)")
            else:
                print(f"   ⚠️  캐시 MISS 가능성 (시간 차이 작음)")
    else:
        print(f"❌ 조회 실패 (None 반환)")
except Exception as e:
    elapsed2 = time.time() - start_time
    print(f"❌ 에러 발생: {e} ({elapsed2:.2f}초)")

print()
print("=" * 80)
print("테스트 완료")
print("=" * 80)
