import os
import json
import logging
import datetime
import re
import hashlib
from typing import Any, List, Dict, Optional
import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# [IT 기술: 프로젝트 내부 계층형 모듈 임포트]
from core.security import SafetyGuard, CircuitBreaker
from connectors.drf_client import DRFConnector
from core.law_selector import LawSelector 
from connectors import db_client # [L6] 불변 감사 로그 및 영속성 레이어

# [IT 기술: 환경 설정 및 고가용성 로깅 계층]
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LawmadiOS.Kernel")

app = FastAPI(title="Lawmadi OS", version="v50.2.3-HARDENED")

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

RUNTIME = {}

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
    "L60": {"name": "마디 통합 리더", "aliases": ["마디", "리더", "분석기"], "role": "시스템 기본 법리 분석 노드"}
}

# =========================================================
# 🛠️ [ROBUST HELPERS] 데이터 정밀 추출 및 정규화 계층
# =========================================================

def _extract_best_dict_list(obj: Any) -> List[Dict[str, Any]]:
    """[IT 기술: Data Normalization] API 응답 객체에서 점수 기반으로 가장 유효한 데이터 리스트를 추출합니다."""
    candidates = []
    def walk(o: Any):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            if o and all(isinstance(x, dict) for x in o): candidates.append(o)
            for v in o: walk(v)
    walk(obj)
    if not candidates: return []
    
    best_list, max_score = [], -1
    score_keys = ["판례일련번호", "법령ID", "사건번호", "caseNo", "lawId", "MST", "법령명", "조문내용"]
    
    for cand in candidates:
        current_score = 0
        sample = cand[0] if cand else {}
        for k in sample.keys():
            if any(sk in k for sk in score_keys): current_score += 1
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
            for v in o: walk(v)
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
    """[IT 기술: Output Guardrail] 답변 송출 직전, 헌법(LMD-CONST) 원칙 준수 여부를 최종 검증합니다."""
    if len(response_text) < 10: return False
    # 페르소나 무결성: 변호사 사칭 금지 및 리더 정체성 고수
    if "변호사입니다" in response_text or "변호사로서" in response_text:
        return False
    return True

# =========================================================
# 🛠️ [L3 SHORT_SYNC] Gemini 전용 지능형 도구 (Law & Precedent)
# =========================================================

def search_law_drf(query: str):
    """[SSOT] 실시간 법령 정보를 검색합니다."""
    logger.info(f"🛠️ [L3 Strike] 법령 검색 호출: '{query}'")
    try:
        drf_inst = RUNTIME.get("drf")
        selector = RUNTIME.get("selector")
        if not drf_inst: return {"result": "ERROR", "message": "DRF 커넥터 미초기화."}
        
        raw_result = drf_inst.fetch_verified_law(query)
        if raw_result.get("status") != "VERIFIED":
            return {"result": "NO_DATA", "message": "관련 법령을 찾을 수 없습니다."}

        candidates = _extract_best_dict_list(raw_result)
        if selector and len(candidates) > 1:
            best_law = selector.select_best_law(query, candidates)
            if best_law:
                return {"result": "FOUND", "content": best_law.get("content", ""), "source": "국가법령정보센터"}

        return {"result": "FOUND", "content": raw_result.get("content", ""), "source": "국가법령정보센터"}
    except Exception as e:
        return {"result": "ERROR", "message": str(e)}

def search_precedents_drf(query: str):
    """[SSOT_PRECEDENT] 국가법령정보센터의 실시간 판례 데이터를 검색합니다."""
    logger.info(f"🛠️ [L3 Strike] 판례 검색 호출: '{query}'")
    try:
        drf_inst = RUNTIME.get("drf")
        if not drf_inst: return {"result": "ERROR", "message": "DRF 커넥터 미초기화."}

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

law_tools = [search_law_drf, search_precedents_drf]

# =========================================================
# 📜 [L0 CONSTITUTION] 표준 응답 규격 및 절대 원칙
# =========================================================
SYSTEM_INSTRUCTION_BASE = f"""
당신은 대한민국 법률 AI 'Lawmadi OS v50.2.3-HARDENED'의 [L2 Swarm Intelligence Cluster]입니다.
할당된 전문가 리더 페르소나를 완벽히 연기하며, 반드시 아래 **5단계 표준 응답 구조**로 답변하십시오.

--- [표준 응답 5단계 구조] ---
1. 요약 (Quick Insight): 친절한 비서 톤으로 사안의 핵심 법적 성격 규정 및 가장 시급한 조치 안내.
2. 📚 법률 근거 (Verified Evidence): `search_law_drf` 또는 `search_precedents_drf` 도구를 통해 실시간 검증된 데이터(조문 원문, 사건번호)만 표시.
3. 🕐 시간축 분석 (Timeline Analysis): 사건 발생 시점과 법령 시행 시점을 대조하여 ASCII_TIMELINE_V2 형식으로 시각화.
4. 절차 안내 (Action Plan): 사용자가 지금 당장 해야 할 1~3단계 로드맵 제시.
5. 🔍 참고 정보 (Additional Context): 전문가 상담 임계점 안내 및 법적 효력 보장 불가 표준 면책 공고.

--- [6대 절대 원칙] ---
1. SSOT_FACT_ONLY: 모든 답변은 실시간 검색된 데이터 내에서만 생성하세요.
2. ZERO_INFERENCE: 데이터에 없는 내용을 지어내지 마세요.
3. FAIL_CLOSED: 도구 오류나 데이터 부재 시 "확인 불가"를 보고하세요.
4. IDENTITY: 당신은 '리더'이며 결코 '변호사'가 아닙니다.
"""

# =========================================================
# 🐝 [L2 SWARM] 지능형 전문가 리더 라우팅 (Semantic & Alias Dispatch)
# =========================================================

def select_swarm_leader(query: str, leaders: Dict) -> Dict:
    """[IT 기술: Semantic Leader Hot-Swap] 이름 호출 또는 도메인을 분석하여 최적의 리더 노드를 선출합니다."""
    registry = leaders if leaders else DEFAULT_LEADER_REGISTRY
    
    # 1. [이름/직함 호출 감지] - 최우선 순위
    for leader_id, info in registry.items():
        if any(alias in query for alias in info.get("aliases", [])):
            logger.info(f"🎯 [L2 Hot-Swap] '{info['name']}' 노드 명시적 호출 감지")
            return info

    # 2. [도메인 자동 분류] - 차순위
    domain_map = {
        "REAL_ESTATE": (["전세", "월세", "임대", "보증금", "매매", "등기"], "L08"),
        "CRIMINAL": (["고소", "처벌", "사기", "횡령", "판례", "형사"], "L22"),
        "LABOR": (["해고", "임금", "퇴직금", "근로", "수당"], "L15"),
        "TECH": (["AI", "데이터", "개인정보", "해킹", "저작권"], "L21"),
        "SPACE": (["위성", "발사체", "궤도", "우주항공"], "L33")
    }

    for domain, (keywords, leader_id) in domain_map.items():
        if any(k in query for k in keywords):
            logger.info(f"🎯 [L2] {domain} 도메인 감지 -> {leader_id} 리더 자동 배정")
            return registry.get(leader_id, registry["L60"])
    
    return registry["L60"]

# =========================================================
# ⚙️ [INFRA] 시스템 부팅 및 초기화 파이프라인
# =========================================================

@app.on_event("startup")
async def startup():
    db_client.init_tables()
    config = load_integrated_config()
    if os.getenv("GEMINI_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_KEY"))
    
    drf_conn = DRFConnector(
        api_key=os.getenv("LAWGO_DRF_OC", "choepeter"),
        endpoints={
            "lawSearch": "https://www.law.go.kr/DRF/lawSearch.do",
            "lawService": "https://www.law.go.kr/DRF/lawService.do",
            "precSearch": "https://www.law.go.kr/DRF/precSearch.do"
        }
    )
    
    RUNTIME.update({
        "config": config,
        "drf": drf_conn,
        "selector": LawSelector(),
        "guard": SafetyGuard(policy=True, restricted_keywords=[], safety_config={})
    })
    logger.info("✅ Lawmadi Swarm Kernel v50.2.3-HARDENED Online")

@app.get("/health")
async def health():
    return {
        "status": "online", "os_version": "v50.2.3",
        "diagnostics": {"l5_ready": bool(RUNTIME.get("selector")), "drf_node": bool(RUNTIME.get("drf"))}
    }

@app.post("/ask")
async def ask(req: Request):
    start_time = datetime.datetime.now()
    try:
        data = await req.json()
        query = data.get("query", "")
        config = RUNTIME.get("config", {})
        
        # 1. [L5 Security] 패킷 검사
        if not RUNTIME["guard"].check(query):
            return {"response": "🚫 보안 정책에 의해 차단되었습니다.", "status": "BLOCKED"}

        # 2. [L2 Swarm] 지능형 리더 핫스왑 선출
        leader_registry = config.get("leader_registry", DEFAULT_LEADER_REGISTRY)
        leader = select_swarm_leader(query, leader_registry)
        
        # 3. [L3/L5 Inference] 리더 페르소나 주입 및 엔진 가동
        # IT 기술: gemini-2.5-flash-preview-09-2025 모델의 자동 함수 호출 활용
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025",
            tools=law_tools,
            system_instruction=f"{SYSTEM_INSTRUCTION_BASE}\n현재 당신은 '{leader['name']}({leader['role']})' 노드입니다. 반드시 [{leader['name']} 답변]으로 시작하세요."
        )
        
        chat = model.start_chat(enable_automatic_function_calling=True)
        resp = chat.send_message(f"사용자 질문: {query}")
        final_text = resp.text

        # 4. [L6 Governance] 헌법 준수 최종 확인
        if not validate_constitutional_compliance(final_text):
            logger.warning("🚨 [L6] 헌법 준수 루프 위반 감지")
            return {"response": "⚠️ 시스템 무결성 정책에 의해 답변이 제한되었습니다.", "status": "FAIL_CLOSED"}

        # 5. [L6 Audit] 불변 감사 로그 기록
        db_client.add_audit_log(
            query=query,
            response=final_text,
            leader=leader.get('name'),
            status="SUCCESS",
            latency_ms=(datetime.datetime.now() - start_time).total_seconds() * 1000
        )
        
        return {"response": final_text, "leader": leader.get("name"), "status": "SUCCESS"}
        
    except Exception as e:
        logger.error(f"💥 커널 에러: {e}")
        return {"response": f"⚠️ 시스템 장애가 발생했습니다. (Ref: {datetime.datetime.now().strftime('%H%M%S')})", "status": "ERROR"}

def load_integrated_config():
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)