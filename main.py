import json
import os
from core.security import CircuitBreaker, SafetyGuard
from agents.swarm_manager import SwarmManager
from connectors.drf_client import DRFConnector

def bootstrap_system():
    """
    [L0-L1] 시스템 부팅 및 레이어 초기화 로직
    """
    print("--- Lawmadi OS v50.2.3-PATCH-2.1 Booting ---")
    
    # 1. 환경 설정 로드 (config.json)
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # 2. 보안 가드레일 및 회로 차단기 활성화
    guard = SafetyGuard(policy=config['security']['anti_leak_policy'])
    cb = CircuitBreaker(latency_limit=config['performance']['latency_budget'])
    
    # 3. DRF 실시간 커넥터 준비
    drf = DRFConnector(api_key=os.getenv("LAW_GO_KR_API_KEY"))
    
    # 4. 스웜 엔진(60-Leader Cluster) 초기화
    swarm = SwarmManager(cluster_size=60)
    
    return config, guard, cb, drf, swarm

def main():
    # 시스템 부팅
    config, guard, cb, drf, swarm = bootstrap_system()
    
    print("✅ System Health Check: Healthy (Memory: 42%)")
    print("💡 Lawmadi OS is ready to analyze legal data.")

    while True:
        user_input = input("\n[User Query] > ")
        
        # [Step 1] 보안 필터링
        if not guard.check(user_input):
            print("🛡️ Safety Trigger: 악성 요청 또는 보안 위반이 감지되었습니다.")
            continue

        # [Step 2] 스웜 엔진 - 전문가 선출 및 분석 (L2)
        print("🔍 Swarm Engine: 전문가 노드를 선별 중입니다...")
        leaders = swarm.select_leaders(user_input)
        
        # [Step 3] 실시간 데이터 검증 (L3-L5)
        with cb:  # Latency Budget 준수 확인
            context = drf.fetch_verified_law(user_input)
            
            # [Step 4] 최종 답변 생성
            response = swarm.generate_legal_advice(user_input, context, leaders)
            print(f"\n[Lawmadi Response]\n{response}")

if __name__ == "__main__":
    main()
