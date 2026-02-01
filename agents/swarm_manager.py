import json
import random
from typing import List, Dict, Any

class SwarmManager:
    """
    [L2] 스웜 엔진: 60인 가상 전문가 노드 관리 및 협업 레시피 제어
    """
    def __init__(self, cluster_size: int = 60):
        self.cluster_size = cluster_size
        # 전문가 도메인 맵핑 (기술 표준)
        self.expert_nodes = {
            "L01-L10": "민사(Civil)",
            "L11-L20": "형사(Criminal)",
            "L21-L30": "가사/행정(Family/Admin)",
            "L31-L40": "IT/보안/지식재산(Tech/IP)",
            "L41-L50": "근로/노동(Labor)",
            "L51-L60": "부동산/경매(Real Estate)"
        }
        self.active_leaders = []

    def select_leaders(self, user_query: str) -> List[str]:
        """
        질의 키워드를 분석하여 60개 노드 중 최적의 전문가 그룹(Leaders)을 선출합니다.
        """
        selected_leaders = []
        
        # IT 기술적 키워드 매칭 로직 (예시)
        mapping = {
            "돈": "L01", "계약": "L01", "손해": "L05",    # 민사
            "사기": "L11", "폭행": "L15", "고소": "L20",    # 형사
            "해고": "L41", "임금": "L45",                 # 노동
            "전세": "L51", "경매": "L55", "매매": "L58",    # 부동산
            "해킹": "L31", "개인정보": "L35"               # IT보안
        }

        for keyword, leader_id in mapping.items():
            if keyword in user_query:
                selected_leaders.append(leader_id)

        # 선출된 리더가 없을 경우 기본 리더 배정
        if not selected_leaders:
            selected_leaders = ["L01", "L11"] # 기본 민사/형사 배정
            
        self.active_leaders = list(set(selected_leaders))
        return self.active_leaders

    def generate_collaboration_recipe(self, leaders: List[str]) -> str:
        """
        선출된 리더들이 협업할 '레시피(프롬프트 구조)'를 생성합니다.
        """
        recipe = f"현재 활성화된 리더 노드: {', '.join(leaders)}\n"
        recipe += "협업 방식: 다각도 분석 및 법령 교차 검증 적용\n"
        return recipe

    def generate_legal_advice(self, query: str, context: Dict, leaders: List[str]) -> str:
        """
        최종적으로 LLM에게 전달할 전문가 페르소나와 데이터를 통합합니다.
        """
        recipe = self.generate_collaboration_recipe(leaders)
        
        # IT 시스템 관점에서의 프롬프트 엔지니어링 레이어
        system_prompt = f"""
        [Lawmadi OS System Prompt]
        당신은 {recipe}에 기반하여 답변하는 법률 비서입니다.
        참조 데이터(DRF): {json.dumps(context, ensure_ascii=False)}
        
        선출된 리더의 관점에서 사용자의 질문 '{query}'에 대해 
        가장 최신의 법령과 판례를 근거로 답변하십시오.
        """
        
        # 실제 환경에서는 여기서 LLM API를 호출합니다.
        return f"[시스템 메시지] {len(leaders)}명의 전문가 노드가 분석을 마쳤습니다. 답변을 생성합니다..."
