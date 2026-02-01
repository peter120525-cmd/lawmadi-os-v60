import json
import os
import signal
import psutil
from core.security import CircuitBreaker, SafetyGuard
from agents.swarm_manager import SwarmManager
from connectors.drf_client import DRFConnector
from connectors import db_client


def _validate_env(config: dict):
    """
    [HALT_BOOTSTRAP] 필수 환경변수 검증
    누락 시 즉시 종료
    """
    required = config.get("required_env_vars", [])
    for var in required:
        value = os.getenv(var)
        if not value or value.strip() == "":
            raise SystemExit(
                f"[HALT_BOOTSTRAP] 필수 환경변수 '{var}'이 누락되거나 비어있습니다. "
                f"부팅을 중단합니다."
            )
    print(f"✅ [ENV] 필수 환경변수 {len(required)}개 검증 완료")


def _get_health_status() -> dict:
    """실시간 시스템 리소스 상태 측정"""
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    return {
        "memory_percent": mem.percent,
        "cpu_percent": cpu,
        "status": "Healthy" if mem.percent < 75 and cpu < 90 else "Warning"
    }


def _shutdown_handler(signum, frame):
    """종료 시그널 수신 시 DB 연결 정리"""
    print("\n🔄 [Shutdown] 연결 정리 중...")
    db_client.close_all()
    print("✅ [Shutdown] 완료")
    exit(0)


def bootstrap_system():
    """
    [L0-L1] 시스템 부팅 및 레이어 초기화
    순서: ENV 검증 → config → DB 초기화 → 보안 → 커넥터 → 스웜
    """
    # 종료 시그널 핸들러 등록
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    # 0. config 로드
    with open('config.json', 'r') as f:
        config = json.load(f)

    version = config["system_metadata"]["os_version"]
    print(f"--- Lawmadi OS {version} Booting ---")

    # 1. ENV 검증 (HALT_BOOTSTRAP)
    _validate_env(config)

    # 2. Cloud SQL 초기화
    print("🔄 [DB] Cloud SQL 연결 및 테이블 초기화...")
    db_client.init_tables()

    # 3. 보안 가드레일
    security_cfg = config["security_layer"]
    guard = SafetyGuard(
        policy=security_cfg["anti_leak_policy"],
        restricted_keywords=security_cfg["restricted_keywords"],
        safety_config=security_cfg["safety"]
    )

    # 4. Per-provider Circuit Breaker
    cb_configs = config["network_security"]["circuit_breaker"]["per_provider"]
    circuit_breakers = {
        provider: CircuitBreaker(provider_name=provider, config=cb_configs[provider])
        for provider in cb_configs
    }

    # 5. DRF 커넥터
    drf_cfg = config["data_sync_connectors"]
    drf = DRFConnector(
        api_key=os.getenv("LAWGO_DRF_OC"),
        timeout_ms=drf_cfg["request_timeout_ms"],
        endpoints=drf_cfg["drf_endpoints"],
        cb=circuit_breakers.get("LAW_GO_KR_DRF"),
        api_failure_policy=drf_cfg["api_failure_policy"]
    )

    # 6. 스웜 엔진
    swarm = SwarmManager(config=config["swarm_engine_config"])

    return config, guard, circuit_breakers, drf, swarm


def main():
    config, guard, circuit_breakers, drf, swarm = bootstrap_system()

    # 실시간 health check
    health = _get_health_status()
    print(f"✅ System Health: {health['status']} "
          f"(Memory: {health['memory_percent']}%, CPU: {health['cpu_percent']}%)")
    print("💡 Lawmadi OS is ready to analyze legal data.\n")

    while True:
        user_input = input("[User Query] > ").strip()
        if not user_input:
            continue

        # [Step 1] 보안 필터링 + Crisis
        check_result = guard.check(user_input)

        if check_result is False:
            continue

        if check_result == "CRISIS":
            guard.handle_crisis()
            continue

        # [Step 2] Swarm — 레시피 매칭 및 리더 선출
        print("\n🔍 Swarm Engine: 전문가 노드를 선별 중입니다...")
        leaders, recipe_id = swarm.select_leaders(user_input)
        print(f"   → 선출된 리더: {leaders} (레시피: {recipe_id})")

        # [Step 3] DRF 검증 (캐시 → API 순차)
        print("📡 DRF: 법률 근거를 검증 중이에요…")
        context = drf.fetch_verified_law(user_input)

        if context.get("status") == "FAIL_CLOSED":
            print(f"\n🛡️ {context.get('message', 'DRF 검증 실패.')}")
            continue

        # [Step 4] 답변 생성
        response = swarm.generate_legal_advice(user_input, context, leaders)
        print(f"\n[Lawmadi Response]\n{response}")


if __name__ == "__main__":
    main()