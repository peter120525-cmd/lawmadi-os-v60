import os
import json
import logging
import datetime
import re
import hashlib
from typing import Any, List, Dict

import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# (선택) SearchService를 실제로 쓸 때만 enable
try:
    from services.search_service import SearchService
except Exception:
    SearchService = None  # type: ignore

# [IT 기술: 프로젝트 내부 계층형 모듈 임포트]
from core.security import SafetyGuard  # CircuitBreaker 미사용이면 제거 가능
from connectors.drf_client import DRFConnector
from core.law_selector import LawSelector
from connectors import db_client  # [L6] 불변 감사 로그 및 영속성 레이어

# [IT 기술: 환경 설정 및 고가용성 로깅 계층]
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LawmadiOS.Kernel")

app = FastAPI(title="Lawmadi OS", version="v50.2.3-HARDENED")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lawmadi.com",
        "https://www.lawmadi.com"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNTIME: Dict[str, Any] = {}

# =========================================================
# 🐝 [L2 SWARM DATA] 63인의 전문가 리더 및 임원 명부 (Hot-Swap 규격)
# =========================================================
DEFAULT_LEADER_REGISTRY = {
    "C01": {"name": "Lawmadi 이사회 의장 (회장님)", "aliases": ["회장", "의장", "보스", "회장님", "의장님", "의장님 호출"], "role": "시스템 총괄 정책 결정자"},
    "L08": {"name": "부동산 전문 리더", "aliases": ["부동산", "집주인", "보증금", "임대차", "부동산리더"], "role": "임대차 및 물권법 권위자"},
    "L22": {"name": "형사 특별 수사 리더", "aliases": ["형사", "검사", "고소", "형사리더", "사기"], "role": "형법 및 특경법 전문가"},
    "L15": {"name": "인사노무 전략 리더", "aliases": ["노무", "노동", "해고", "노무사", "인사"], "role": "근로기준법 및 노사관계 전문가"},
    "L21": {"name": "IT/IP 기술 리더", "aliases": ["AI", "특허", "저작권", "기술", "개인정보"], "role": "변리사 기반 지식재산권 에이전트"},
    "L33": {"name": "우주항공 법무 임원", "aliases": ["우주", "위성", "궤도", "항공"], "role": "미래 우주법 전략가"},
    "L60": {"name": "마디 통합 리더", "aliases": ["마디", "리더", "분석기"], "role": "시스템 기본 법리 분석 노드"},
}

# =========================================================
# 🧾 [AUDIT] Best-effort audit wrapper (DB가 죽어도 API는 죽지 않게)
# =========================================================
def _audit(event_type: str, payload: dict) -> None:
    try:
        db_client.add_audit_log(
            query=payload.get("query", ""),
            response=payload.get("response_sha256", ""),
            leader=payload.get("leader", "SYSTEM"),
            status=payload.get("status", event_type),
            latency_ms=payload.get("latency_ms", 0),
        )
    except Exception as e:
        logger.warning(f"[AUDIT] logging failed: {e}")

# =========================================================
# 🛠️ [ROBUST HELPERS] 데이터 정밀 추출 및 정규화 계층
# =========================================================
def _is_low_signal(query: str) -> bool:
    q = (query or "").strip()
    if len(q) < 3:
        return True
    low = {"테스트", "test", "안녕", "hello", "hi", "ㅎ", "ㅋㅋ", "ㅇㅇ"}
    return q.lower() in low

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

# =========================================================
# 🛡️ [L6 GOVERNANCE] 헌법 준수 루프 (Constitutional Loop)
# =========================================================
def validate_constitutional_compliance(response_text: str) -> bool:
    if not response_text or len(response_text.strip()) < 10:
        return False

    t = response_text

    # 1) 변호사 사칭 금지
    if "변호사입니다" in t or "변호사로서" in t:
        return False

    # 2) placeholder 날짜/타임라인 금지
    banned_patterns = [
        r"\b2024-MM-DD\b",
        r"\bYYYY-MM-DD\b",
        r"\bHH:MM:SS\b",
        r"ASCII_TIMELINE_V2\(SYSTEM_CORE_CHECK\)",
    ]
    for p in banned_patterns:
        if re.search(p, t):
            return False

    # 3) 근거 없는 상태 단정 차단
    banned_phrases = [
        "Ready and Verified",
        "완벽하게 작동",
        "모듈이 모두 활성화",
        "즉각적인 접근이 가능",
    ]
    if any(x in t for x in banned_phrases):
        return False

    return True

# =========================================================
# 🛠️ [L3 SHORT_SYNC] Gemini 전용 지능형 도구 (Law & Precedent)
# =========================================================
def search_law_drf(query: str):
    logger.info(f"🛠️ [L3 Strike] 법령 검색 호출: '{query}'")
    try:
        svc = RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        return svc.get_best_law_verified(query)
    except Exception as e:
        return {"result": "ERROR", "message": str(e)}

def search_precedents_drf(query: str):
    logger.info(f"🛠️ [L3 Strike] 판례 검색 호출: '{query}'")
    try:
        drf_inst = RUNTIME.get("drf")
        if not drf_inst:
            return {"result": "ERROR", "message": "DRF 커넥터 미초기화."}

        raw_result = drf_inst.fetch_precedents(query)
        items = _extract_best_dict_list(raw_result)
        if not items:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 판례가 없습니다."}

        summary_list = []
        for it in items[:3]:
            title = it.get("사건명", "제목 없음")
            case_no = it.get("사건번호", "번호 없음")
            content_keys = ["판시사항", "판결요지", "이유"]
            texts = _collect_texts_by_keys(it, content_keys)
            summary = "\n".join(_dedup_keep_order(texts))[:1000]
            summary_list.append(f"【사건명: {title} ({case_no})】\n{summary}")

        combined_content = "\n\n".join(summary_list)
        return {"result": "FOUND", "content": combined_content, "source": "국가법령정보센터(판례)"}
    except Exception as e:
        logger.error(f"🛠️ 판례 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}

# =========================================================
# 📜 [L0 CONSTITUTION] 표준 응답 규격 및 절대 원칙
# =========================================================
SYSTEM_INSTRUCTION_BASE = f"""
당신은 대한민국 법률 AI 'Lawmadi OS v50.2.3-HARDENED'의 [L2 Swarm Intelligence Cluster]입니다.
할당된 전문가 리더 페르소나를 완벽히 연기하며, 반드시 아래 **5단계 표준 응답 구조**로 답변하십시오.

--- [표준 응답 5단계 구조] ---
1. 요약 (Quick Insight)
2. 📚 법률 근거 (Verified Evidence): `search_law_drf` 또는 `search_precedents_drf`로 실시간 검증된 데이터만 표시.
3. 🕐 시간축 분석 (Timeline Analysis): 사용자 제공 날짜 또는 now_utc만 사용. 불명확하면 "시간 정보 부족으로 생략".
4. 절차 안내 (Action Plan)
5. 🔍 참고 정보 (Additional Context)

--- [6대 절대 원칙] ---
1. SSOT_FACT_ONLY
2. ZERO_INFERENCE
3. FAIL_CLOSED
4. IDENTITY: 변호사 아님
5. TIMELINE_RULE: now_utc 외 임의 날짜 금지
"""

# =========================================================
# 🐝 [L2 SWARM] 리더 라우팅
# =========================================================
def select_swarm_leader(query: str, leaders: Dict) -> Dict:
    registry = leaders if leaders else DEFAULT_LEADER_REGISTRY

    for leader_id, info in registry.items():
        if any(alias in query for alias in info.get("aliases", [])):
            logger.info(f"🎯 [L2 Hot-Swap] '{info['name']}' 노드 명시적 호출 감지")
            return info

    domain_map = {
        "REAL_ESTATE": (["전세", "월세", "임대", "보증금", "매매", "등기"], "L08"),
        "CRIMINAL": (["고소", "처벌", "사기", "횡령", "판례", "형사"], "L22"),
        "LABOR": (["해고", "임금", "퇴직금", "근로", "수당"], "L15"),
        "TECH": (["AI", "데이터", "개인정보", "해킹", "저작권"], "L21"),
        "SPACE": (["위성", "발사체", "궤도", "우주항공"], "L33"),
    }

    for domain, (keywords, leader_id) in domain_map.items():
        if any(k in query for k in keywords):
            logger.info(f"🎯 [L2] {domain} 도메인 감지 -> {leader_id} 리더 자동 배정")
            return registry.get(leader_id, registry["L60"])

    return registry["L60"]

# =========================================================
# ⚙️ [CONFIG] load
# =========================================================
def load_integrated_config():
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# =========================================================
# ⚙️ [INFRA] startup
# =========================================================
@app.on_event("startup")
async def startup():
    soft_mode = (os.getenv("SOFT_MODE", "false").lower() == "true")
    db_disabled = (os.getenv("DB_DISABLED", "0") == "1")

    # DB init (보호)
    if db_disabled:
        logger.warning("🟡 DB_DISABLED=1 -> skip init_tables")
    else:
        try:
            db_client.init_tables()
        except Exception as e:
            logger.warning(f"🟡 DB init_tables failed: {e}")
            if not soft_mode:
                raise

    config = load_integrated_config()

    # Gemini key configure
    if os.getenv("GEMINI_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_KEY"))
    else:
        logger.warning("⚠️ GEMINI_KEY 누락: LLM 추론은 요청 시 FAIL_CLOSED 처리됩니다.")

    # DRF
    drf_conn = DRFConnector(
        api_key=os.getenv("LAWGO_DRF_OC", "choepeter"),
        endpoints={
            "lawSearch": "http://www.law.go.kr/DRF/lawSearch.do",
            "lawService": "http://www.law.go.kr/DRF/lawService.do",
            "precSearch": "http://www.law.go.kr/DRF/lawSearch.do",
        },
    )

    # (선택) SearchService 활성화 플래그
    search_service = None
    if os.getenv("ENABLE_SEARCH_SERVICE", "false").lower() == "true" and SearchService is not None:
        try:
            search_service = SearchService()
            logger.info("✅ SearchService enabled")
        except Exception as e:
            logger.warning(f"🟡 SearchService init failed: {e}")
            # soft_mode면 그냥 진행

    RUNTIME.update(
        {
            "config": config,
            "drf": drf_conn,
            "selector": LawSelector(),
            "guard": SafetyGuard(policy=True, restricted_keywords=[], safety_config={}),
            "search_service": search_service,
        }
    )

    logger.info("✅ Lawmadi Swarm Kernel v50.2.3-HARDENED Online")

# =========================================================
# ✅ health
# =========================================================
@app.get("/health")
async def health():
    return {
        "status": "online",
        "os_version": "v50.2.3",
        "diagnostics": {
            "l5_ready": bool(RUNTIME.get("selector")),
            "drf_node": bool(RUNTIME.get("drf")),
            "search_service": bool(RUNTIME.get("search_service")),
            "db_disabled": (os.getenv("DB_DISABLED", "0") == "1"),
        },
    }

# =========================================================
# ✅ ask
# =========================================================
@app.post("/ask")
async def ask(req: Request):
    start_time = datetime.datetime.now()
    try:
        data = await req.json()
        query = (data.get("query", "") or "").strip()
        config = RUNTIME.get("config", {})

        # 0) Low-signal 입력은 LLM 호출 금지
        if _is_low_signal(query):
            msg = (
                "[마디 통합 리더 답변]\n\n"
                "1. 요약 (Quick Insight):\n"
                "서버는 정상 동작 중입니다. ✅ (테스트 입력 감지)\n\n"
                "2. 📚 법률 근거 (Verified Evidence):\n"
                "구체 사안이 없어 근거 검색을 수행하지 않았습니다.\n\n"
                "3. 🕐 시간축 분석 (Timeline Analysis):\n"
                "시간 정보 부족으로 생략합니다.\n\n"
                "4. 절차 안내 (Action Plan):\n"
                "- 사건 개요(무슨 일이 있었는지)\n"
                "- 날짜/당사자/증빙(계약서 등)\n"
                "- 원하는 결과(환급/고소/가처분 등)\n\n"
                "5. 🔍 참고 정보 (Additional Context):\n"
                "본 시스템은 법률 자문이 아닌 정보 제공/분석 보조입니다.\n"
            )
            _audit("ask_low_signal", {"query": query, "status": "SKIPPED", "latency_ms": 0})
            return {"response": msg, "leader": "마디 통합 리더", "status": "SUCCESS"}

        # 0.5) GEMINI_KEY 없으면 즉시 FAIL_CLOSED
        if not os.getenv("GEMINI_KEY"):
            _audit("ask_fail_closed", {"query": query, "reason": "missing_gemini_key"})
            return {"response": "⚠️ GEMINI_KEY 미설정으로 추론이 비활성화되었습니다.", "status": "FAIL_CLOSED"}

        # 1) Security
        guard = RUNTIME.get("guard")
        if guard and (not guard.check(query)):
            _audit("ask_blocked", {"query": query, "reason": "guard"})
            return {"response": "🚫 보안 정책에 의해 차단되었습니다.", "status": "BLOCKED"}

        # 2) Leader 선택
        leader_registry = config.get("leader_registry", DEFAULT_LEADER_REGISTRY)
        leader = select_swarm_leader(query, leader_registry)

        # 3) tools는 SearchService 준비 상태에 따라 조건부
        tools = [search_law_drf, search_precedents_drf]

        # 4) now_utc 주입
        now_utc = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025",
            tools=tools,
            system_instruction=(
                f"{SYSTEM_INSTRUCTION_BASE}\n"
                f"현재 당신은 '{leader['name']}({leader['role']})' 노드입니다. "
                f"반드시 [{leader['name']} 답변]으로 시작하세요."
            ),
        )

        chat = model.start_chat(enable_automatic_function_calling=True)
        resp = chat.send_message(f"now_utc={now_utc}\n사용자 질문: {query}")
        final_text = (resp.text or "").strip()

        # 5) Governance
        if not validate_constitutional_compliance(final_text):
            logger.warning("🚨 [L6] 헌법 준수 루프 위반 감지")
            _audit("ask_fail_closed", {"query": query, "reason": "governance_violation"})
            return {"response": "⚠️ 시스템 무결성 정책에 의해 답변이 제한되었습니다.", "status": "FAIL_CLOSED"}

        latency_ms = (datetime.datetime.now() - start_time).total_seconds() * 1000.0

        # 6) Audit
        _audit(
            "ask",
            {
                "query": query,
                "leader": leader.get("name"),
                "status": "SUCCESS",
                "latency_ms": latency_ms,
                "now_utc": now_utc,
                "response_sha256": hashlib.sha256(final_text.encode("utf-8")).hexdigest(),
            },
        )

        return {"response": final_text, "leader": leader.get("name"), "status": "SUCCESS"}

    except Exception as e:
        logger.error(f"💥 커널 에러: {e}")
        ref = datetime.datetime.now().strftime("%H%M%S")
        _audit("ask_error", {"ref": ref, "error": str(e)})
        return {"response": f"⚠️ 시스템 장애가 발생했습니다. (Ref: {ref})", "status": "ERROR"}

# =========================================================
# ✅ search / trending (SearchService 없으면 ERROR)
# =========================================================
@app.get("/search")
async def search(q: str, limit: int = 10):
    svc = RUNTIME.get("search_service")
    if not svc:
        return {"status": "ERROR", "message": "SearchService not ready"}
    return svc.integrated_search(q, limit=limit)

@app.get("/trending")
async def trending(limit: int = 10):
    svc = RUNTIME.get("search_service")
    if not svc:
        return {"status": "ERROR", "message": "SearchService not ready"}
    return svc.trending_laws(limit=limit)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
