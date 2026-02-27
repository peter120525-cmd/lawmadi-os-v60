"""
Lawmadi OS v60 — 리더 협의(Deliberation) & 인수인계(Handoff) 시스템.

CSO 서연이 주재하는 리더 회의 과정을 사용자에게 채팅 형식으로 보여주고,
이후 질문에서는 리더 간 인수인계 과정도 표시.
"""
import json
import logging
import asyncio
from typing import Dict, List, Optional

from core.model_fallback import get_model, on_quota_error, is_quota_error

logger = logging.getLogger("LawmadiOS.Deliberation")

# 협의 타임아웃 (초)
_DELIBERATION_TIMEOUT = 5
_HANDOFF_TIMEOUT = 5


def should_deliberate(
    query: str,
    is_legal: bool,
    is_first_question: bool,
    current_leader: Optional[str],
    new_leader_name: str,
    is_name_call: bool,
) -> str:
    """
    협의/인수인계 필요 여부 판단.

    Returns:
        "full"    — 첫 질문, CSO 주재 리더 회의
        "handoff" — 기존 리더 → 새 리더 인수인계
        "none"    — 회의 없이 바로 진행
    """
    # 비법률 질문 → 회의 없음
    if not is_legal:
        return "none"

    # 이름 직접 호출 → 회의 없음
    if is_name_call:
        return "none"

    # 첫 질문 (current_leader 없음) → 풀 회의
    if is_first_question or not current_leader:
        return "full"

    # 같은 리더가 계속 → 회의 없음
    if current_leader == new_leader_name:
        return "none"

    # 다른 리더로 변경 → 인수인계
    return "handoff"


async def generate_deliberation(
    gc,
    query: str,
    leaders: List[Dict],
    lang: str = "",
) -> Optional[List[Dict]]:
    """
    CSO 서연 주재 리더 회의 대화 스크립트 생성 (Gemini Flash 1회 호출).

    Args:
        gc: Gemini client
        query: 사용자 질문
        leaders: 후보 리더 목록 [{"name": ..., "specialty": ...}, ...]
        lang: 언어 코드

    Returns:
        대화 턴 리스트 또는 None (실패 시)
        [
          {"speaker": "서연", "role": "CSO", "text": "...", "is_final": False},
          {"speaker": "온유", "role": "임대차", "text": "...", "is_final": False},
          ...
          {"speaker": "서연", "role": "CSO", "text": "...리더 지명...", "is_final": True},
        ]
    """
    if not gc or not leaders:
        return None

    leader_list_str = ", ".join(
        f"{l['name']}({l['specialty']})" for l in leaders[:3]
    )

    prompt = (
        f"당신은 Lawmadi OS의 CSO 서연입니다. "
        f"사용자의 법률 질문에 대해 어떤 리더가 담당할지 회의를 진행합니다.\n\n"
        f"사용자 질문: {query[:500]}\n"
        f"참석 리더: {leader_list_str}\n\n"
        f"아래 규칙을 따라 JSON 배열로 회의 대화를 생성하세요:\n"
        f"1. 서연(CSO)이 먼저 질문을 요약하고 관련 리더들에게 의견을 구합니다\n"
        f"2. 각 리더가 짧게(1~2문장) 자기 분야 관점에서 의견을 말합니다\n"
        f"3. 서연이 최종 담당 리더를 지명합니다 (is_final: true)\n"
        f"4. 총 3~5턴, 각 턴 50자 이내\n"
        f"5. 존댓말, 따뜻하고 전문적인 톤\n\n"
        f"JSON 형식 (반드시 이 형식만 출력):\n"
        f'[{{"speaker":"서연","role":"CSO","text":"...","is_final":false}},'
        f'{{"speaker":"리더명","role":"전문분야","text":"...","is_final":false}},'
        f'{{"speaker":"서연","role":"CSO","text":"...님이 담당하시겠습니다","is_final":true}}]'
    )

    try:
        from google.genai import types as genai_types

        model_name = get_model()

        for _attempt in range(2):
            try:
                resp = gc.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=600,
                        temperature=0.7,
                    ),
                )
                break
            except Exception as e:
                if is_quota_error(e) and _attempt < 1:
                    on_quota_error()
                    continue
                raise

        raw = (resp.text or "").strip()

        # JSON 추출 (코드블록 감싸진 경우 대응)
        if "```" in raw:
            import re
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()

        turns = json.loads(raw)
        if not isinstance(turns, list) or len(turns) < 2:
            logger.warning(f"[Deliberation] 유효하지 않은 턴 수: {len(turns) if isinstance(turns, list) else 'not list'}")
            return None

        # 필드 검증
        validated = []
        for t in turns[:5]:
            if isinstance(t, dict) and "speaker" in t and "text" in t:
                validated.append({
                    "speaker": str(t["speaker"]),
                    "role": str(t.get("role", "")),
                    "text": str(t["text"])[:100],
                    "is_final": bool(t.get("is_final", False)),
                })
        if not validated:
            return None

        logger.info(f"[Deliberation] {len(validated)}턴 생성 완료")
        return validated

    except asyncio.TimeoutError:
        logger.warning("[Deliberation] 타임아웃 — 스킵")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"[Deliberation] JSON 파싱 실패: {e}")
        return None
    except Exception as e:
        logger.warning(f"[Deliberation] 생성 실패: {type(e).__name__}: {e}")
        return None


async def generate_handoff(
    gc,
    query: str,
    current_leader: Dict,
    new_leader: Dict,
    lang: str = "",
) -> Optional[List[Dict]]:
    """
    리더 간 인수인계 대화 생성 (Gemini Flash 1회 호출).

    Args:
        gc: Gemini client
        query: 사용자 질문
        current_leader: {"name": ..., "specialty": ...}
        new_leader: {"name": ..., "specialty": ...}
        lang: 언어 코드

    Returns:
        인수인계 턴 리스트 또는 None (실패 시)
        [
          {"speaker": "온유", "role": "임대차", "text": "이 질문은 형사법 관련이라..."},
          {"speaker": "무결", "role": "형사법", "text": "안녕하세요, 바로 도와드리겠습니다."},
        ]
    """
    if not gc or not current_leader or not new_leader:
        return None

    prompt = (
        f"Lawmadi OS 리더 인수인계 대화를 생성하세요.\n\n"
        f"사용자 질문: {query[:500]}\n"
        f"현재 리더: {current_leader['name']}({current_leader['specialty']})\n"
        f"새 리더: {new_leader['name']}({new_leader['specialty']})\n\n"
        f"규칙:\n"
        f"1. 현재 리더가 먼저 새 리더에게 인계 이유를 짧게 설명 (1~2문장, 50자 이내)\n"
        f"2. 새 리더가 사용자에게 인사하고 바로 돕겠다고 함 (1~2문장, 50자 이내)\n"
        f"3. 존댓말, 따뜻하고 전문적인 톤\n\n"
        f"JSON 형식 (반드시 이 형식만 출력):\n"
        f'[{{"speaker":"{current_leader["name"]}","role":"{current_leader["specialty"]}","text":"..."}}, '
        f'{{"speaker":"{new_leader["name"]}","role":"{new_leader["specialty"]}","text":"..."}}]'
    )

    try:
        from google.genai import types as genai_types

        model_name = get_model()

        for _attempt in range(2):
            try:
                resp = gc.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=300,
                        temperature=0.7,
                    ),
                )
                break
            except Exception as e:
                if is_quota_error(e) and _attempt < 1:
                    on_quota_error()
                    continue
                raise

        raw = (resp.text or "").strip()

        if "```" in raw:
            import re
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()

        turns = json.loads(raw)
        if not isinstance(turns, list) or len(turns) < 1:
            return None

        validated = []
        for t in turns[:2]:
            if isinstance(t, dict) and "speaker" in t and "text" in t:
                validated.append({
                    "speaker": str(t["speaker"]),
                    "role": str(t.get("role", "")),
                    "text": str(t["text"])[:100],
                })
        if not validated:
            return None

        logger.info(f"[Handoff] {current_leader['name']} → {new_leader['name']} ({len(validated)}턴)")
        return validated

    except asyncio.TimeoutError:
        logger.warning("[Handoff] 타임아웃 — 스킵")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"[Handoff] JSON 파싱 실패: {e}")
        return None
    except Exception as e:
        logger.warning(f"[Handoff] 생성 실패: {type(e).__name__}: {e}")
        return None
