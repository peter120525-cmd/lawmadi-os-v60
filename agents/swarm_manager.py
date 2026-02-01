import json
from typing import List, Dict, Any, Tuple


class SwarmManager:
    """
    [L2] 스웜 엔진: 60인 리더 클러스터 관리
    - config의 leader_registry와 composite_recipes를 소스로 사용
    - 키워드 조합 → 레시피 매칭 → 가중치 기반 리더 선출
    - max_leaders 상한 준수 + CORE 리더 fallback
    - ZERO_INFERENCE 원칙을 시스템 프롬프트에 강제
    """
    def __init__(self, config: Dict[str, Any]):
        self.min_leaders: int = config.get("min_active_leaders", 1)
        self.max_leaders: int = config.get("max_active_leaders", 4)
        self.core_leaders: List[str] = config.get("core_leaders", ["L22", "L35", "L60"])
        self.leader_registry: Dict[str, Any] = config.get("leader_registry", {})
        self.recipes: List[Dict[str, Any]] = config.get("composite_recipes", [])

        # 단일 키워드 → 리더 매핑 (config의 leader_registry와 정확히 대응)
        # 이 매핑은 composite_recipes에 포함되지 않는 단순 단일키워드 사건용
        self._single_keyword_map: Dict[str, str] = {
            # 민사법 계열
            "계약": "L01", "손해배상": "L06", "의료": "L05",
            # 부동산법 계열
            "부동산": "L02", "건설": "L03", "재개발": "L04",
            # 임대차 계열 (단일키워드만 — 복합은 LEASE_DEPOSIT_AUCTION 레시피)
            "임대차": "L08", "전세": "L08", "월세": "L08",
            # 채권/추심
            "추심": "L11", "채권": "L11",
            # 상사법
            "회사": "L14", "스타트업": "L15",
            # 보험
            "보험": "L16",
            # 형사법
            "사기": "L22", "폭행": "L22", "고소": "L22",
            # 노동법
            "해고": "L30", "임금": "L30", "노동": "L30",
            # IT/보안
            "해킹": "L21", "개인정보": "L34", "사이버": "L21",
            # 행정법
            "행정": "L31", "공정거래": "L32",
            # 지식재산
            "특허": "L26", "저작권": "L42",
        }

    # ── 메인 선출 엔트리포인트 ──────────────────────────────────────────────
    def select_leaders(self, user_query: str) -> Tuple[List[str], str]:
        """
        반환: (선출된 리더 ID 리스트, 적용된 레시피 ID)
        레시피 매칭 실패 시 단일키워드 매핑 사용 → 둘 다 실패 시 CORE fallback
        """
        lower_query = user_query.lower()

        # 1. Composite Recipe 매칭 시도 (우선순위 내림차순)
        recipe_match = self._match_recipe(lower_query)
        if recipe_match:
            leaders, recipe_id = recipe_match
            return leaders, recipe_id

        # 2. 단일 키워드 매핑
        single_leaders = self._match_single_keywords(lower_query)
        if single_leaders:
            # max_leaders 상한 적용
            capped = single_leaders[:self.max_leaders]
            return capped, "SINGLE_KEYWORD"

        # 3. Fallback: CORE 리더 중 L01(민사) + L22(형사) 배정
        print("   → 적합한 레시피/키워드 미감지. CORE 기본 리더 배정.")
        return ["L01", "L22"], "CORE_FALLBACK"

    # ── Recipe 매칭 ───────────────────────────────────────────────────────
    def _match_recipe(self, query: str) -> tuple:
        """
        composite_recipes를 priority 내림차순으로 순회
        conditions.all_of: 모든 그룹에서 최소 1개 키워드가 매칭되어야 함
        """
        # 레시피를 priority 내림차순으로 정렬
        sorted_recipes = sorted(self.recipes, key=lambda r: r.get("priority", 0), reverse=True)

        for recipe in sorted_recipes:
            conditions = recipe.get("conditions", {})
            all_of = conditions.get("all_of", [])

            all_groups_matched = True
            for group in all_of:
                any_keywords = group.get("any", [])
                if not any(kw in query for kw in any_keywords):
                    all_groups_matched = False
                    break

            if all_groups_matched:
                # 레시피 매칭 성공 — 가중치 기반 리더 정렬
                leaders_def = recipe.get("leaders", [])
                # 가중치 내림차순 정렬 후 max_leaders 상한 적용
                sorted_leaders = sorted(leaders_def, key=lambda l: l.get("weight", 0), reverse=True)
                leader_ids = [l["id"] for l in sorted_leaders[:self.max_leaders]]

                # CORE 리더 포함 보장 (collision_policy: CORE 리더 1명은 항상 포함)
                leader_ids = self._ensure_core_leader(leader_ids)

                return leader_ids, recipe["id"]

        return None  # 매칭 실패

    # ── 단일 키워드 매핑 ─────────────────────────────────────────────────
    def _match_single_keywords(self, query: str) -> List[str]:
        """키워드 하나씩 매칭하여 리더 수집 (중복 제거, 가중치 없음)"""
        matched = []
        seen = set()
        for keyword, leader_id in self._single_keyword_map.items():
            if keyword in query and leader_id not in seen:
                matched.append(leader_id)
                seen.add(leader_id)
        return matched

    # ── CORE 리더 포함 보장 ─────────────────────────────────────────────
    def _ensure_core_leader(self, leaders: List[str]) -> List[str]:
        """
        recipe_collision_policy: CORE 리더 1명은 항상 포함
        이미 포함되어 있으면 유지, 없으면 가장 낮은 우선순위 리더를 대체
        """
        has_core = any(l in self.core_leaders for l in leaders)
        if has_core:
            return leaders

        # CORE 리더 중 L60(시스템 총괄)을 기본 포함
        if len(leaders) >= self.max_leaders:
            leaders[-1] = "L60"  # 마지막 리더를 CORE로 교체
        else:
            leaders.append("L60")
        return leaders

    # ── 최종 답변 생성 (LLM 프롬프트 조립) ────────────────────────────────
    def generate_legal_advice(self, query: str, context: Dict, leaders: List[str]) -> str:
        """
        LLM에게 전달할 프롬프트 조립
        ZERO_INFERENCE 원칙 강제: DRF 제공 데이터 외 법률 내용 생성 금지
        """
        # 선출된 리더의 페르소나 정보 수집
        personas = []
        for lid in leaders:
            info = self.leader_registry.get(lid, {})
            if info:
                personas.append(f"{info.get('name', lid)} ({info.get('specialty', '미정의')})")

        persona_str = ", ".join(personas) if personas else "기본 법률 비서"

        # DRF 제공 콘텐츠만 참조 가능한 형태로 정리
        drf_content = context.get("content", [])
        drf_status = context.get("status", "Unknown")

        system_prompt = f"""
[Lawmadi OS — ZERO_INFERENCE 모드]

당신은 다음 전문가 페르소나로 답변하는 법률 비서입니다: {persona_str}

━━━ 핵심 제약조건 (반드시 준수) ━━━
1. 모든 법률 근거는 아래 [DRF 검증 데이터]에만 근거해야 합니다.
2. DRF 데이터에 포함되지 않는 법률, 판례, 사건번호를 스스로 생성하거나 추론하면 안 됩니다.
3. 확실하지 않은 내용은 "DRF 데이터에 해당 정보가 포함되지 않았습니다"로 명시해야 합니다.
4. 법적 효력을 보장하는 표현을 사용하면 안 됩니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[DRF 검증 상태]: {drf_status}
[DRF 검증 데이터]:
{json.dumps(drf_content, ensure_ascii=False, indent=2)}

[사용자 질문]: {query}

위의 DRF 데이터를 근거로, 사용자 질문에 답변하십시오.
"""
        # 실제 환경에서는 여기서 LLM API 호출
        # response = llm_client.call(system_prompt)
        # return response

        return (
            f"[시스템 메시지] {len(leaders)}명의 전문가 노드({persona_str})가 "
            f"분석을 마쳤습니다.\n"
            f"[DRF 상태] {drf_status} | 참조 데이터 수: {len(drf_content)}건\n"
            f"[프롬프트 준비 완료 — LLM API 연결 시 실제 답변 생성됨]"
        )
