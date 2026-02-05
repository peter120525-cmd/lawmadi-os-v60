import os
class SwarmManager:
    def __init__(self, config: dict):
        self.mode = config.get("mode", "SINGLE")
        self.leader_registry = config.get("leader_registry", {})
        self.default_leaders = config.get("default_leaders", [])

    def select_leaders(self, user_input: str, law_domains=None):
        if law_domains is None:
            law_domains = []

        scores = {lid: 0 for lid in self.leader_registry}

        # 기본 리더 점수
        for lid in self.default_leaders:
            scores[lid] += 5

        # 🔥 Domain 가중치
        for lid, leader in self.leader_registry.items():
            domains = leader.get("domains", [])
            overlap = set(domains) & set(law_domains)
            if overlap:
                scores[lid] += 10 * len(overlap)

        # 최고 점수 리더 선택
        selected = sorted(scores, key=lambda x: scores[x], reverse=True)

        multi = os.getenv("SWARM_MULTI", "false").lower() == "true"
        topk = 3 if multi else 1
        recipe_id = "DOMAIN_WEIGHTED_MULTI" if multi else "DOMAIN_WEIGHTED_SELECTION"
        return selected[:topk], recipe_id
