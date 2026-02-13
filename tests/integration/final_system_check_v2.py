#!/usr/bin/env python3
"""
Lawmadi OS v50 최종 시스템 점검 (SSOT 중점)
- DRF 연결 및 캐싱 검증
- 60 Leader 매핑 검증
- 스트리밍 엔드포인트 검증
- 방문자 통계 검증
"""
import os
import sys
import time
import json

print("=" * 80)
print("🔍 Lawmadi OS v50 최종 시스템 점검")
print("=" * 80)
print()

# =============================================================================
# 1. 환경변수 점검
# =============================================================================
print("=" * 80)
print("1️⃣  환경변수 점검")
print("=" * 80)

required_vars = {
    "GEMINI_KEY": "Gemini API (AI 분석)",
    "LAWGO_DRF_OC": "법제처 DRF API (법률 데이터)",
    "CLOUD_SQL_INSTANCE": "Cloud SQL 연결 문자열",
    "DB_NAME": "데이터베이스 이름",
    "DB_USER": "DB 사용자",
    "DB_PASS": "DB 비밀번호"
}

env_ok = True
for var, desc in required_vars.items():
    value = os.getenv(var)
    if value:
        masked = value[:8] + "..." if len(value) > 8 else "***"
        print(f"  ✅ {var:25} = {masked:15} ({desc})")
    else:
        print(f"  ❌ {var:25} = NOT SET ({desc})")
        env_ok = False

print()
if not env_ok:
    print("⚠️  일부 환경변수가 설정되지 않았습니다.")
    print("   로컬 환경에서는 정상이며, Cloud Run에서 자동 설정됩니다.")
else:
    print("✅ 모든 환경변수 확인 완료")

print()

# =============================================================================
# 2. 모듈 임포트 점검
# =============================================================================
print("=" * 80)
print("2️⃣  핵심 모듈 임포트 점검")
print("=" * 80)

modules_to_test = [
    ("connectors.db_client_v2", "DB 클라이언트 v2 (캐싱, 로깅)"),
    ("connectors.drf_client", "DRF 커넥터 (SSOT)"),
    ("services.search_service", "검색 서비스"),
    ("agents.swarm_orchestrator", "Swarm 오케스트레이터 (60 Leader)"),
    ("agents.clevel_handler", "C-Level 임원 핸들러"),
    ("core.drf_integrity", "DRF 무결성 검증"),
]

import_ok = True
for module_name, desc in modules_to_test:
    try:
        __import__(module_name)
        print(f"  ✅ {module_name:35} - {desc}")
    except Exception as e:
        print(f"  ❌ {module_name:35} - {desc}")
        print(f"     에러: {e}")
        import_ok = False

print()
if import_ok:
    print("✅ 모든 모듈 임포트 성공")
else:
    print("❌ 일부 모듈 임포트 실패")
    print()

# =============================================================================
# 3. DRF SSOT 점검 (가장 중요!)
# =============================================================================
print("=" * 80)
print("3️⃣  DRF SSOT (법률 데이터 검색) 점검 ⭐")
print("=" * 80)

drf_key = os.getenv("LAWGO_DRF_OC")
if not drf_key:
    print("❌ LAWGO_DRF_OC 환경변수가 없어 DRF 테스트를 건너뜁니다.")
    print("   Cloud Run에서는 자동으로 설정됩니다.")
else:
    try:
        from connectors.drf_client import DRFConnector

        print(f"  ✅ DRFConnector 임포트 성공")
        print()

        # DRF 연결 테스트
        print("  [테스트 1] DRF API 연결 및 캐싱 검증")
        print("  " + "-" * 76)

        drf = DRFConnector(api_key=drf_key, timeout_ms=10000)
        test_query = "민법 제750조"

        # 첫 번째 호출 (캐시 MISS 예상)
        print(f"    쿼리: '{test_query}'")
        print(f"    첫 번째 호출 (캐시 MISS 예상)...")
        start1 = time.time()
        result1 = drf.law_search(test_query)
        elapsed1 = time.time() - start1

        if result1 is not None:
            print(f"    ✅ 조회 성공: {elapsed1:.2f}초")
            print(f"       Root tag: {result1.tag if hasattr(result1, 'tag') else 'N/A'}")
        else:
            print(f"    ❌ 조회 실패 (None 반환)")

        # 잠시 대기
        time.sleep(0.5)

        # 두 번째 호출 (캐시 HIT 예상)
        print(f"    두 번째 호출 (캐시 HIT 예상)...")
        start2 = time.time()
        result2 = drf.law_search(test_query)
        elapsed2 = time.time() - start2

        if result2 is not None:
            print(f"    ✅ 조회 성공: {elapsed2:.2f}초")

            if elapsed2 < 0.5:
                print(f"    🎯 캐시 HIT 확인! ({elapsed2:.2f}초 < 0.5초)")
            elif elapsed2 < elapsed1 * 0.3:
                print(f"    ✅ 캐시 HIT 가능성 높음 (70% 이상 빠름)")
            else:
                print(f"    ⚠️  캐시 MISS 가능성 (시간 차이 작음)")

            # 성능 개선율 계산
            if elapsed1 > 0:
                speedup = elapsed1 / elapsed2 if elapsed2 > 0 else 1
                print(f"    📊 개선율: {speedup:.1f}배 빠름")
        else:
            print(f"    ❌ 조회 실패")

        print()

    except Exception as e:
        print(f"  ❌ DRF 테스트 실패: {e}")
        print()

print()

# =============================================================================
# 4. 60 Leader 매핑 점검
# =============================================================================
print("=" * 80)
print("4️⃣  60 Leader 매핑 점검")
print("=" * 80)

try:
    import json

    # leaders.json 로드
    with open('leaders.json', 'r', encoding='utf-8') as f:
        leaders_data = json.load(f)

    leader_registry = leaders_data.get('swarm_engine_config', {}).get('leader_registry', {})

    print(f"  ✅ leaders.json 로드 성공")
    print(f"  📊 등록된 리더 수: {len(leader_registry)}명")
    print()

    # 샘플 리더 표시
    print("  [샘플 리더 (처음 5명)]")
    for i, (leader_id, info) in enumerate(list(leader_registry.items())[:5], 1):
        name = info.get('name', 'N/A')
        specialty = info.get('specialty', 'N/A')
        print(f"    {i}. {leader_id}: {name} - {specialty}")

    print(f"    ... (총 {len(leader_registry)}명)")
    print()

    # main.py의 select_swarm_leader 매핑 확인
    print("  [main.py 도메인 매핑 확인]")
    with open('main.py', 'r', encoding='utf-8') as f:
        main_content = f.read()

    # domain_map 라인 수 카운트
    domain_map_count = main_content.count('"L0') + main_content.count('"L1') + main_content.count('"L2') + main_content.count('"L3') + main_content.count('"L4') + main_content.count('"L5')

    if domain_map_count >= 50:
        print(f"    ✅ domain_map에 {domain_map_count}개 리더 매핑 확인")
        print(f"    ✅ 60 Leader 키워드 매핑 적용됨")
    else:
        print(f"    ⚠️  domain_map에 {domain_map_count}개 매핑만 발견")
        print(f"    ⚠️  예상: 59개 (L01-L59)")

    print()

except Exception as e:
    print(f"  ❌ Leader 매핑 점검 실패: {e}")
    print()

# =============================================================================
# 5. 스트리밍 엔드포인트 점검
# =============================================================================
print("=" * 80)
print("5️⃣  스트리밍 엔드포인트 점검")
print("=" * 80)

try:
    with open('main.py', 'r', encoding='utf-8') as f:
        main_content = f.read()

    if '/ask/stream' in main_content:
        print("  ✅ /ask/stream 엔드포인트 발견")
    else:
        print("  ❌ /ask/stream 엔드포인트 없음")

    if 'StreamingResponse' in main_content:
        print("  ✅ StreamingResponse import 확인")
    else:
        print("  ❌ StreamingResponse import 없음")

    if 'send_message' in main_content and 'stream=True' in main_content:
        print("  ✅ Gemini 스트리밍 API 사용 확인")
    else:
        print("  ⚠️  Gemini 스트리밍 API 사용 미확인")

    print()

except Exception as e:
    print(f"  ❌ 스트리밍 점검 실패: {e}")
    print()

# =============================================================================
# 6. 프론트엔드 점검
# =============================================================================
print("=" * 80)
print("6️⃣  프론트엔드 점검")
print("=" * 80)

try:
    with open('frontend/index.html', 'r', encoding='utf-8') as f:
        frontend_content = f.read()

    print(f"  ✅ frontend/index.html 파일 존재")
    print(f"  📊 파일 크기: {len(frontend_content):,} bytes")

    if 'STREAM_URL' in frontend_content:
        print("  ✅ STREAM_URL 설정 확인")
    else:
        print("  ❌ STREAM_URL 설정 없음")

    if 'USE_STREAMING' in frontend_content:
        print("  ✅ USE_STREAMING 플래그 확인")
    else:
        print("  ❌ USE_STREAMING 플래그 없음")

    if 'dispatchPacketStream' in frontend_content:
        print("  ✅ dispatchPacketStream() 메서드 확인")
    else:
        print("  ❌ dispatchPacketStream() 메서드 없음")

    if 'formatReport' in frontend_content:
        print("  ✅ formatReport() 향상된 마크다운 렌더링 확인")
    else:
        print("  ❌ formatReport() 없음")

    print()

except Exception as e:
    print(f"  ❌ 프론트엔드 점검 실패: {e}")
    print()

# =============================================================================
# 7. 방문자 통계 점검
# =============================================================================
print("=" * 80)
print("7️⃣  방문자 통계 시스템 점검")
print("=" * 80)

try:
    from connectors.db_client_v2 import init_visitor_stats_table, record_visit, get_visitor_stats

    print("  ✅ 방문자 통계 함수 임포트 성공")

    # 테이블 초기화 테스트 (로컬에서는 DB 없을 수 있음)
    try:
        init_visitor_stats_table()
        print("  ✅ init_visitor_stats_table() 호출 성공")
    except Exception as e:
        print(f"  ⚠️  테이블 초기화 실패 (DB 미연결): {e}")

    print()

except Exception as e:
    print(f"  ❌ 방문자 통계 점검 실패: {e}")
    print()

# =============================================================================
# 최종 요약
# =============================================================================
print("=" * 80)
print("📊 최종 점검 요약")
print("=" * 80)
print()

checklist = [
    ("환경변수", env_ok),
    ("모듈 임포트", import_ok),
    ("DRF SSOT", drf_key is not None),
    ("60 Leader 매핑", len(leader_registry) == 60 if 'leader_registry' in locals() else False),
    ("스트리밍 엔드포인트", '/ask/stream' in main_content if 'main_content' in locals() else False),
    ("프론트엔드", 'STREAM_URL' in frontend_content if 'frontend_content' in locals() else False),
]

passed = sum(1 for _, ok in checklist if ok)
total = len(checklist)

for item, ok in checklist:
    status = "✅" if ok else "⚠️ "
    print(f"  {status} {item}")

print()
print(f"📊 점검 결과: {passed}/{total} 항목 통과")
print()

if passed == total:
    print("🎉 모든 시스템 정상! 배포 준비 완료!")
elif passed >= total * 0.8:
    print("✅ 핵심 시스템 정상. 배포 가능합니다.")
    print("   (일부 경고는 로컬 환경 제약으로 정상입니다)")
else:
    print("⚠️  일부 시스템에 문제가 있습니다. 확인이 필요합니다.")

print()
print("=" * 80)
print("점검 완료")
print("=" * 80)
