"""
Lawmadi ADK — 리더 협의(Deliberation) & 인수인계(Handoff) FunctionTool.

CSO 서연 주재 3턴 리더 회의 + 리더 간 인수인계 대화를 생성.
ADK Agent가 classify_query → get_leader_context 후 호출.

core/deliberation.py를 ADK FunctionTool 형태로 이식.
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger("LawmadiADK.Deliberation")

# ---------------------------------------------------------------------------
# Leader name/profile loading
# ---------------------------------------------------------------------------

_NAME_TO_ID: Dict[str, str] = {}
_LEADER_PROFILES: Dict = {}


def _load_profiles() -> Dict:
    """leader_profiles.json 로드 (캐시)."""
    global _LEADER_PROFILES
    if _LEADER_PROFILES:
        return _LEADER_PROFILES
    try:
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "leader_profiles.json",
        )
        with open(path, "r", encoding="utf-8") as f:
            _LEADER_PROFILES = json.load(f)
    except Exception as e:
        logger.warning(f"프로필 로드 실패: {e}")
        _LEADER_PROFILES = {}
    return _LEADER_PROFILES


def _load_name_to_id() -> Dict[str, str]:
    """이름→ID 역매핑 구축."""
    global _NAME_TO_ID
    if _NAME_TO_ID:
        return _NAME_TO_ID
    try:
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "leaders.json",
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for lid, info in data.get("core_registry", {}).items():
            name = info.get("name", "")
            if name:
                _NAME_TO_ID[name] = lid
        registry = data.get("swarm_engine_config", {}).get("leader_registry", {})
        for lid, info in registry.items():
            name = info.get("name", "")
            if name:
                _NAME_TO_ID[name] = lid
    except Exception as e:
        logger.warning(f"leaders.json 로드 실패: {e}")
    return _NAME_TO_ID


def _name_to_id(name: str) -> str:
    mapping = _load_name_to_id()
    return mapping.get(name, "")


def _build_persona(leader_id: str) -> str:
    """리더 프로필에서 간략 페르소나 생성."""
    profiles = _load_profiles()
    p = profiles.get(leader_id)
    if not p:
        return ""
    parts = []
    if p.get("hero"):
        parts.append(f"신조: {p['hero']}")
    identity = p.get("identity", {})
    if identity.get("what"):
        parts.append(f"역할: {identity['what']}")
    if identity.get("why"):
        parts.append(f"사명: {identity['why']}")
    if p.get("philosophy"):
        parts.append(f"철학: {p['philosophy']}")
    return "\n".join(parts) if parts else ""


def _build_cso_persona() -> str:
    profiles = _load_profiles()
    p = profiles.get("CSO")
    if not p:
        return "CSO 서연: Lawmadi OS 전략 총괄. 리더 회의를 주재합니다."
    parts = []
    if p.get("hero"):
        parts.append(f"신조: {p['hero']}")
    identity = p.get("identity", {})
    if identity.get("what"):
        parts.append(f"역할: {identity['what']}")
    if p.get("philosophy"):
        parts.append(f"철학: {p['philosophy']}")
    return "CSO 서연\n" + "\n".join(parts) if parts else "CSO 서연: 전략 총괄"


# ---------------------------------------------------------------------------
# Related leaders selection
# ---------------------------------------------------------------------------

_DOMAIN_NEIGHBORS: Dict[str, List[str]] = {
    "L01": ["L06", "L10"],    # 민사 → 손해배상, 민사집행
    "L02": ["L04", "L08"],    # 부동산 → 재개발, 임대차
    "L03": ["L02", "L09"],    # 건설 → 부동산, 국가계약
    "L04": ["L02", "L03"],    # 재개발 → 부동산, 건설
    "L05": ["L06", "L43"],    # 의료 → 손해배상, 산재
    "L06": ["L01", "L07"],    # 손해배상 → 민사, 교통사고
    "L07": ["L06", "L16"],    # 교통사고 → 손해배상, 보험
    "L08": ["L02", "L01"],    # 임대차 → 부동산, 민사
    "L11": ["L01", "L22"],    # 채권추심 → 민사, 형사
    "L22": ["L37", "L25"],    # 형사 → 학폭, 군형법
    "L30": ["L43", "L41"],    # 노동 → 산재, 가사
    "L38": ["L06", "L01"],    # 소비자 → 손해배상, 민사
    "L41": ["L57", "L22"],    # 가사 → 상속, 형사
    "L42": ["L26", "L52"],    # 저작권 → 지재권, 미디어
    "L43": ["L30", "L05"],    # 산재 → 노동, 의료
    "L57": ["L41", "L20"],    # 상속 → 가사, 세금
}


def _get_related_leaders(leader_id: str) -> List[str]:
    """협의에 참여할 인접 리더 2명 반환."""
    neighbors = _DOMAIN_NEIGHBORS.get(leader_id, [])
    if len(neighbors) >= 2:
        return neighbors[:2]
    if len(neighbors) == 1:
        return neighbors + ["L60"]
    return ["L01", "L60"]


# ---------------------------------------------------------------------------
# Deliberation generation (sync, for ADK FunctionTool)
# ---------------------------------------------------------------------------

def generate_deliberation(
    query: str,
    leader_id: str,
    leader_name: str,
) -> dict:
    """CSO 서연 주재 3턴 리더 협의를 생성합니다.

    질문의 법적 성격을 파악하고, 담당 리더와 인접 분야 리더가
    짧은 의견을 교환하는 형태의 협의 과정을 만듭니다.

    Args:
        query: 사용자의 법률 질문.
        leader_id: classify_query로 결정된 담당 리더 ID (예: "L08").
        leader_name: 담당 리더 이름 (예: "온유").

    Returns:
        dict with keys:
            - deliberation: list[dict] — 3턴 협의 대화
              각 dict: {"speaker": str, "speaker_id": str, "message": str, "turn": int}
            - participants: list[str] — 참석 리더 ID 목록
            - assigned_leader: str — 최종 담당 리더 ID
    """
    related = _get_related_leaders(leader_id)
    participants = [leader_id] + related

    profiles = _load_profiles()

    # 리더 이름 조회
    def _get_name(lid: str) -> str:
        p = profiles.get(lid, {})
        return p.get("name", lid)

    # 리더 전문 분야 조회
    def _get_domain(lid: str) -> str:
        p = profiles.get(lid, {})
        identity = p.get("identity", {})
        return identity.get("what", "법률 전문가")

    assigned_name = leader_name or _get_name(leader_id)
    r1_name = _get_name(related[0]) if related else ""
    r2_name = _get_name(related[1]) if len(related) > 1 else ""

    r1_domain = _get_domain(related[0]) if related else ""
    r2_domain = _get_domain(related[1]) if len(related) > 1 else ""
    assigned_domain = _get_domain(leader_id)

    short_query = query[:100] + ("..." if len(query) > 100 else "")

    # Turn 1: CSO 서연 — 질문 소개 + 담당 리더 지명
    turn1 = {
        "speaker": "서연",
        "speaker_id": "CSO",
        "message": (
            f"이 질문을 검토해봅시다. \"{short_query}\" "
            f"{assigned_name} 리더님, {assigned_domain}으로서 이 사안을 맡아주시겠어요?"
        ),
        "turn": 1,
    }

    # Turn 2: 담당 리더 — 수락 + 핵심 접근 방향
    turn2 = {
        "speaker": assigned_name,
        "speaker_id": leader_id,
        "message": (
            f"네, 제가 맡겠습니다. "
            f"이 사안은 {assigned_domain} 관점에서 관련 법률과 판례를 "
            f"확인하고, 실질적인 해결 방안을 안내해 드리겠습니다."
        ),
        "turn": 2,
    }

    # Turn 3: 인접 리더 의견 + CSO 마무리
    if r1_name and r2_name:
        turn3 = {
            "speaker": "서연",
            "speaker_id": "CSO",
            "message": (
                f"{r1_name} 리더님({r1_domain})과 "
                f"{r2_name} 리더님({r2_domain})도 "
                f"관련 부분이 있으면 보충 부탁드립니다. "
                f"{assigned_name} 리더님, 진행해 주세요."
            ),
            "turn": 3,
        }
    else:
        turn3 = {
            "speaker": "서연",
            "speaker_id": "CSO",
            "message": f"{assigned_name} 리더님, 진행해 주세요.",
            "turn": 3,
        }

    return {
        "deliberation": [turn1, turn2, turn3],
        "participants": participants,
        "assigned_leader": leader_id,
    }


# ---------------------------------------------------------------------------
# Handoff generation (sync, for ADK FunctionTool)
# ---------------------------------------------------------------------------

def generate_handoff(
    query: str,
    previous_leader_id: str,
    previous_leader_name: str,
    new_leader_id: str,
    new_leader_name: str,
) -> dict:
    """리더 간 인수인계 대화를 생성합니다.

    사용자 질문이 다른 법률 분야로 전환될 때, 이전 리더가
    새 리더에게 맥락을 전달하는 과정을 보여줍니다.

    Args:
        query: 사용자의 새 질문.
        previous_leader_id: 이전 담당 리더 ID.
        previous_leader_name: 이전 담당 리더 이름.
        new_leader_id: 새 담당 리더 ID.
        new_leader_name: 새 담당 리더 이름.

    Returns:
        dict with keys:
            - handoff: list[dict] — 2턴 인수인계 대화
              각 dict: {"speaker": str, "speaker_id": str, "message": str, "turn": int}
            - from_leader: str — 이전 리더 ID
            - to_leader: str — 새 리더 ID
    """
    profiles = _load_profiles()

    def _get_domain(lid: str) -> str:
        p = profiles.get(lid, {})
        return p.get("identity", {}).get("what", "법률 전문가")

    prev_domain = _get_domain(previous_leader_id)
    new_domain = _get_domain(new_leader_id)
    short_query = query[:80] + ("..." if len(query) > 80 else "")

    turn1 = {
        "speaker": previous_leader_name,
        "speaker_id": previous_leader_id,
        "message": (
            f"이 질문은 {new_domain} 분야이므로 "
            f"{new_leader_name} 리더님께 인수인계 드리겠습니다. "
            f"\"{short_query}\""
        ),
        "turn": 1,
    }

    turn2 = {
        "speaker": new_leader_name,
        "speaker_id": new_leader_id,
        "message": (
            f"네, 인수인계 받았습니다. "
            f"{new_domain}으로서 이 사안을 검토하겠습니다. "
            f"{previous_leader_name} 리더님, 감사합니다."
        ),
        "turn": 2,
    }

    return {
        "handoff": [turn1, turn2],
        "from_leader": previous_leader_id,
        "to_leader": new_leader_id,
    }
