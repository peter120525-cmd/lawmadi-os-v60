"""
Lawmadi OS v60 — 순수 유틸리티 함수.
외부 API 의존 없는 데이터 추출·정규화·검증 헬퍼.
main.py에서 분리됨 (Item 7).
"""
import re
import json
import uuid
import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("LawmadiOS.Helpers")


# ---------------------------------------------------------------------------
# 시간·ID 유틸
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """한국 시간(KST, UTC+9) 기준 ISO 형식 반환"""
    utc_now = datetime.datetime.utcnow()
    kst_now = utc_now + datetime.timedelta(hours=9)
    return kst_now.replace(microsecond=0).isoformat() + "+09:00"


def _trace_id() -> str:
    """요청별 고유 추적 ID"""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 질의 분류 헬퍼
# ---------------------------------------------------------------------------

def _is_low_signal(query: str) -> bool:
    q = (query or "").strip()
    if len(q) < 3:
        return True
    # 정확 일치
    low = {"테스트", "test", "안녕", "hello", "hi", "ㅎ", "ㅋㅋ", "ㅇㅇ"}
    if q.lower() in low:
        return True
    # 인사 패턴 (시작어 매칭)
    greetings = ["안녕하세요", "반갑습니다", "반가워요", "하이요", "헬로",
                 "처음 뵙겠습니다", "좋은 아침", "좋은 저녁", "수고하세요"]
    return any(q.startswith(g) for g in greetings)


# ---------------------------------------------------------------------------
# JSON 안전 추출 (brace-counting)
# ---------------------------------------------------------------------------

def _safe_extract_json(text: str) -> Optional[Dict[str, Any]]:
    """중첩 JSON을 안전하게 추출하는 brace-counting 파서.

    기존 ``re.search(r'\\{[^{}]+\\}', ...)`` 는 중첩 중괄호가 있으면 실패한다.
    여기서는 첫 번째 ``{`` 를 찾은 뒤 depth 카운팅으로 매칭되는 ``}`` 를 찾아
    올바른 JSON 조각을 추출한다.
    """
    stripped = text.strip()
    if "```" in stripped:
        m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', stripped)
        if m:
            stripped = m.group(1).strip()

    start = stripped.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


# ---------------------------------------------------------------------------
# DRF 응답 데이터 추출
# ---------------------------------------------------------------------------

def _extract_best_dict_list(obj: Any) -> List[Dict[str, Any]]:
    candidates = []
    def walk(o: Any):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            if o and all(isinstance(x, dict) for x in o):
                candidates.append(o)
            for v in o:
                walk(v)
    walk(obj)
    if not candidates:
        return []

    best_list, max_score = [], -1
    score_keys = ["판례일련번호", "법령ID", "사건번호", "caseNo", "lawId", "MST", "법령명", "조문내용"]

    for cand in candidates:
        current_score = 0
        sample = cand[0] if cand else {}
        for k in sample.keys():
            if any(sk in k for sk in score_keys):
                current_score += 1
        if current_score > max_score:
            max_score = current_score
            best_list = cand

    return best_list if best_list else (candidates[0] if candidates else [])


def _collect_texts_by_keys(obj: Any, wanted_keys: List[str]) -> List[str]:
    out: List[str] = []
    def walk(o: Any):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in wanted_keys and isinstance(v, str) and v.strip():
                    out.append(v.strip())
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


def _dedup_keep_order(texts: List[str]) -> List[str]:
    seen, out = set(), []
    for t in texts:
        key = t.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


# ---------------------------------------------------------------------------
# Gemini 응답 텍스트 추출·정규화
# ---------------------------------------------------------------------------

def _safe_extract_gemini_text(response) -> str:
    """Gemini 응답에서 안전하게 텍스트 추출 (빈 응답 방지 강화)"""
    # 1차: response.text 직접 접근
    try:
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
    except Exception as e:
        logger.warning(f"⚠️ Gemini response.text 추출 실패: {e}")

    # 2차: candidates → parts 순회하여 텍스트 추출
    try:
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                texts = []
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        texts.append(part.text.strip())
                if texts:
                    return "\n".join(texts)
            logger.warning(f"⚠️ Gemini 빈 응답: finish_reason={finish_reason}")
    except (AttributeError, IndexError, TypeError) as e:
        logger.warning(f"⚠️ Gemini candidates 추출 실패: {e}")

    return ""


def _remove_think_blocks(text: str) -> str:
    """Gemini <think>...</think> 내부 추론 블록 제거"""
    text = re.sub(r'<think>[\s\S]*?</think>', '', text)
    text = re.sub(r'^think\n(?:[A-Za-z*].*\n)*', '', text)
    text = text.lstrip('\n')
    return text


def _remove_markdown_headers(text: str) -> str:
    """마크다운 # 헤더를 볼드(**) 텍스트로 변환"""
    lines = text.split('\n')
    result = []
    for line in lines:
        m = re.match(r'^(#{1,4})\s+(.+)$', line)
        if m:
            content = m.group(2).strip()
            result.append(f'**{content}**')
        else:
            result.append(line)
    return '\n'.join(result)


def _remove_markdown_tables(text: str) -> str:
    """마크다운 표 형식을 글머리 기호 형식으로 변환"""
    lines = text.split('\n')
    result = []
    in_table = False
    table_headers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and line.endswith('|'):
            if re.match(r'^\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|$', line):
                i += 1
                in_table = True
                continue
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if not in_table:
                table_headers = cells
                in_table = True
            else:
                if len(cells) >= 2:
                    title = cells[0].replace('**', '').strip()
                    description = ' - '.join(cells[1:]).strip()
                    result.append(f"• **{title}** - {description}")
                elif len(cells) == 1:
                    result.append(f"• {cells[0]}")
        else:
            in_table = False
            table_headers = []
            result.append(lines[i])
        i += 1
    return '\n'.join(result)
