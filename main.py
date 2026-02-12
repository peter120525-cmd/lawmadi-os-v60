"""
Lawmadi OS v50.2.4-HARDENED — Patched Kernel
Based on v50.2.3-HARDENED original main.py

[패치 내역 — 원본 대비 변경사항]
🔴 감사 #2.1  .env.cloudrun 시크릿 노출 → .env.example로 교체 (파일 수준)
🔴 감사 #2.2  CORS allow_origins=["*"] → 도메인 제한
🔴 감사 #2.3  DRF OC 기본값 "choepeter" 하드코딩 → 환경변수 필수
🟡 감사 #3.2  _audit() 시그니처 → db_client_v2.add_audit_log 실제 시그니처 정합
🟡 감사 #3.6  버전 문자열 통일 → OS_VERSION 상수화
🟡 원본버그   DRFConnector(config) → DRFConnector(api_key=...) 실제 시그니처
🟡 원본버그   SearchService(config) → SearchService() 실제 시그니처 (인자 없음)
🟡 원본버그   svc.get_best_law_verified() → svc.search_law() 실제 메서드명
🟡 원본버그   /ask 내 중복 DRF law_search 호출 제거
🟡 원본버그   들여쓰기 오류 (if drf_connector: 블록) 수정
🟡 원본버그   guard.check() 결과에서 CRISIS 처리 누락 → 추가
🟢 ULTRA     Trace ID 도입 (요청별 UUID)
🟢 ULTRA     /metrics, /diagnostics 엔드포인트 추가
🟢 ULTRA     optional_import 패턴 (부팅 실패 방지)
🟢 ULTRA     Rolling average latency 추적
🟢 ULTRA     Global exception handler 추가
🟢 감사 #4.1  GEMINI_MODEL 환경변수화
🟢 감사 #4.2  SOFT_MODE 기본값 true로 변경
"""

# =============================================================
# CORE IMPORTS
# =============================================================

import os
import sys
import json
import uuid
import time
import logging
import datetime
import re
import hashlib
import traceback
from typing import Any, List, Dict, Optional, Union
from importlib import import_module

import google.generativeai as genai
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# =============================================================
# FAIL-SOFT OPTIONAL IMPORT [ULTRA]
# 원본은 hard import로 모듈 하나 깨지면 서버 전체 부팅 실패.
# optional_import로 변경하여 개별 모듈 실패 시에도 서버 기동 가능.
# =============================================================

def optional_import(module_path: str, attr: Optional[str] = None) -> Optional[Any]:
    """모듈 로딩 실패 시 None 반환. 서버 부팅을 절대 중단시키지 않음."""
    try:
        module = import_module(module_path)
        return getattr(module, attr) if attr else module
    except Exception as e:
        logging.warning(f"[IMPORT FAIL-SOFT] {module_path} -> {e}")
        return None

# 원본 hard import → fail-soft로 교체
timeline_analyze = optional_import("engines.temporal_v2", "timeline_analyze")
SwarmManager = optional_import("agents.swarm_manager", "SwarmManager")
SwarmOrchestrator = optional_import("agents.swarm_orchestrator", "SwarmOrchestrator")
CLevelHandler = optional_import("agents.clevel_handler", "CLevelHandler")
SearchService = optional_import("services.search_service", "SearchService")
SafetyGuard = optional_import("core.security", "SafetyGuard")
DRFConnector = optional_import("connectors.drf_client", "DRFConnector")
LawSelector = optional_import("core.law_selector", "LawSelector")
db_client = optional_import("connectors.db_client")

# =============================================================
# BOOTSTRAP
# =============================================================

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LawmadiOS.Kernel")

# [감사 #3.6] 버전 단일 소스
OS_VERSION = "v50.2.4-HARDENED"

app = FastAPI(title="Lawmadi OS", version=OS_VERSION)

# [감사 #2.2] CORS 도메인 제한 (원본: allow_origins=["*"])
# 개발 환경에서 localhost 필요 시 CORS_EXTRA_ORIGINS 환경변수로 추가
_cors_origins = [
    "https://lawmadi.com",
    "https://www.lawmadi.com",
    "https://lawmadi-os.web.app",
    "https://lawmadi-db.web.app",  # Firebase Hosting (current)
]
_extra_cors = os.getenv("CORS_EXTRA_ORIGINS", "")
if _extra_cors:
    _cors_origins.extend([o.strip() for o in _extra_cors.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

RUNTIME: Dict[str, Any] = {}

# [ULTRA] 런타임 메트릭
METRICS: Dict[str, Any] = {
    "requests": 0,
    "errors": 0,
    "avg_latency_ms": 0,
    "boot_time": None,
}

# =============================================================
# 🐝 [L2 SWARM DATA] Leader Registry (Hot-Swap JSON SSOT)
# =============================================================
try:
    with open("leaders.json", "r", encoding="utf-8") as f:
        LEADER_REGISTRY = json.load(f)
    logger.info("✅ Leader registry loaded")
except Exception as e:
    logger.warning(f"leaders.json load failed: {e}")
    LEADER_REGISTRY = {}

# =============================================================
# UTILITIES [ULTRA 추가]
# =============================================================

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""

def _get_client_ip(request: Request) -> str:
    """
    클라이언트 IP 주소 추출
    - X-Forwarded-For 헤더 우선 (프록시/로드밸런서 고려)
    - 없으면 request.client.host 사용
    """
    # X-Forwarded-For 헤더 확인 (프록시 환경)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # 여러 IP가 있을 경우 첫 번째가 실제 클라이언트 IP
        return forwarded.split(",")[0].strip()

    # X-Real-IP 헤더 확인
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 직접 연결
    if request.client and request.client.host:
        return request.client.host

    return "unknown"

def _now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _trace_id() -> str:
    """[ULTRA] 요청별 고유 추적 ID"""
    return str(uuid.uuid4())

# =============================================================
# 🧾 [AUDIT] Best-effort audit wrapper
# [감사 #3.2] db_client_v2.add_audit_log 실제 시그니처에 맞춤:
#   add_audit_log(query, response, leader, status, latency_ms)
# =============================================================

def _audit(event_type: str, payload: dict) -> None:
    try:
        if not db_client:
            return
        fn = getattr(db_client, "add_audit_log", None)
        if not fn:
            return
        fn(
            query=str(payload.get("query", ""))[:2000],
            response=str(payload.get("response_sha256", ""))[:500],
            leader=str(payload.get("leader", "SYSTEM"))[:50],
            status=str(payload.get("status", event_type))[:20],
            latency_ms=int(payload.get("latency_ms", 0)),
        )
    except Exception as e:
        logger.warning(f"[AUDIT] logging failed: {e}")

# =============================================================
# 🛠️ [ROBUST HELPERS] 데이터 정밀 추출 및 정규화 계층
# =============================================================

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

# =============================================================
# 🛡️ [L6 GOVERNANCE] 헌법 준수 루프 (Constitutional Loop)
# =============================================================

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

# =============================================================
# 🛠️ [L3 SHORT_SYNC] Gemini 전용 지능형 도구 (Law & Precedent)
# [원본버그 수정] svc.get_best_law_verified() → svc.search_law()
#   (SearchService에 get_best_law_verified 메서드 없음)
# =============================================================

def search_law_drf(query: str) -> Dict[str, Any]:
    logger.info(f"🛠️ [L3 Strike] 법령 검색 호출: '{query}'")
    try:
        svc = RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_law(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 법령이 없습니다."}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(법령)"}
    except Exception as e:
        return {"result": "ERROR", "message": str(e)}

def search_precedents_drf(query: str) -> Dict[str, Any]:
    logger.info(f"🛠️ [L3 Strike] 판례 검색 호출: '{query}'")
    try:
        drf_inst = RUNTIME.get("drf")
        if not drf_inst:
            return {"result": "ERROR", "message": "DRF 커넥터 미초기화."}

        raw_result = drf_inst.law_search(query)
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

# =============================================================
# 📜 [L0 CONSTITUTION] 표준 응답 규격 및 절대 원칙
# =============================================================

SYSTEM_INSTRUCTION_BASE = f"""
당신은 대한민국 법률 AI 'Lawmadi OS {OS_VERSION}'의 [L2 Swarm Intelligence Cluster]입니다.
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

# =============================================================
# 🐝 [L2 SWARM] 리더 라우팅
# =============================================================

def select_swarm_leader(query: str, leaders: Dict) -> Dict:
    registry = leaders if leaders else LEADER_REGISTRY

    # 1) 별칭 명시적 매칭
    for leader_id, info in registry.items():
        if any(alias in query for alias in info.get("aliases", [])):
            logger.info(f"🎯 [L2 Hot-Swap] '{info['name']}' 노드 명시적 호출 감지")
            return info

    # 2) 도메인 키워드 매칭 (전체 60 Leader 매핑)
    domain_map = {
        # L01-L10
        "L01_CIVIL":        (["민법", "계약", "채권", "채무", "손해배상", "불법행위", "소유권", "물권", "용익물권", "담보물권"], "L01"),
        "L02_PROPERTY":     (["부동산법", "토지", "건물", "분양", "등기소", "소유권이전"], "L02"),
        "L03_CONSTRUCTION": (["건설법", "건축", "공사", "하자", "시공", "설계", "건축허가", "착공"], "L03"),
        "L04_REDEVEL":      (["재개발", "재건축", "정비사업", "조합", "분담금", "관리처분"], "L04"),
        "L05_MEDICAL":      (["의료법", "의료사고", "의료과오", "병원", "진료", "의사", "환자", "의료분쟁"], "L05"),
        "L06_DAMAGES":      (["손해배상", "위자료", "배상금", "과실", "책임", "보상"], "L06"),
        "L07_TRAFFIC":      (["교통사고", "자동차", "운전", "사고", "충돌", "보험금", "과실비율"], "L07"),
        "L08_LEASE":        (["임대차", "전세", "월세", "보증금", "임대", "임차", "계약갱신", "대항력"], "L08"),
        "L09_GOVCONTRACT":  (["국가계약", "조달", "입찰", "낙찰", "공사계약", "물품계약"], "L09"),
        "L10_EXECUTION":    (["민사집행", "강제집행", "배당", "압류", "가압류", "경매", "집행권원"], "L10"),

        # L11-L20
        "L11_COLLECTION":   (["채권추심", "추심", "채권", "변제", "독촉", "지급명령"], "L11"),
        "L12_AUCTION":      (["등기", "경매", "공매", "낙찰", "명도", "유찰"], "L12"),
        "L13_COMMERCIAL":   (["상사법", "상법", "상거래", "어음", "수표", "상인"], "L13"),
        "L14_CORP_MA":      (["회사법", "M&A", "인수합병", "주식양도", "법인", "이사회", "주주총회"], "L14"),
        "L15_STARTUP":      (["스타트업", "벤처", "투자계약", "스톡옵션", "엔젤", "시드"], "L15"),
        "L16_INSURANCE":    (["보험", "보험금", "보험계약", "피보험자", "보험사고", "면책"], "L16"),
        "L17_INTL_TRADE":   (["국제거래", "수출", "수입", "무역", "중재", "국제계약"], "L17"),
        "L18_ENERGY":       (["에너지", "자원", "전력", "가스", "석유", "신재생"], "L18"),
        "L19_MARINE_AIR":   (["해상", "항공", "선박", "항공기", "운송", "해운"], "L19"),
        "L20_TAX_FIN":      (["조세", "금융", "세금", "국세", "지방세", "은행", "금융거래"], "L20"),

        # L21-L30
        "L21_IT_SEC":       (["IT", "보안", "정보보호", "해킹", "사이버", "네트워크", "시스템"], "L21"),
        "L22_CRIMINAL":     (["형사", "형법", "고소", "고발", "처벌", "사기", "횡령", "배임", "폭행"], "L22"),
        "L23_ENTERTAIN":    (["엔터테인먼트", "연예", "연예인", "매니지먼트", "방송"], "L23"),
        "L24_TAX_APPEAL":   (["조세불복", "조세심판", "세무조사", "부과처분", "경정청구"], "L24"),
        "L25_MILITARY":     (["군형법", "군대", "군인", "병역", "군사법원", "영창"], "L25"),
        "L26_IP":           (["지식재산권", "특허", "상표", "디자인", "저작권", "영업비밀"], "L26"),
        "L27_ENVIRON":      (["환경법", "환경오염", "대기", "수질", "토양", "폐기물"], "L27"),
        "L28_CUSTOMS":      (["무역", "관세", "통관", "수입신고", "FTA"], "L28"),
        "L29_GAME":         (["게임", "콘텐츠", "게임물", "등급분류", "아이템"], "L29"),
        "L30_LABOR":        (["노동법", "근로", "해고", "임금", "퇴직금", "수당", "노동조합"], "L30"),

        # L31-L40
        "L31_ADMIN":        (["행정법", "행정", "인허가", "과태료", "행정처분", "영업정지", "행정소송"], "L31"),
        "L32_FAIRTRADE":    (["공정거래", "독점", "담합", "불공정거래", "시장지배적지위"], "L32"),
        "L33_SPACE":        (["우주항공", "위성", "발사체", "궤도", "항공우주"], "L33"),
        "L34_PRIVACY":      (["개인정보", "개인정보보호", "정보주체", "유출", "GDPR"], "L34"),
        "L35_CONSTITUTION": (["헌법", "위헌", "헌법소원", "기본권", "헌법재판소"], "L35"),
        "L36_CULTURE":      (["문화", "종교", "문화재", "전통", "사찰", "교회"], "L36"),
        "L37_JUVENILE":     (["소년법", "청소년", "미성년자", "소년범", "보호처분"], "L37"),
        "L38_CONSUMER":     (["소비자", "소비자보호", "제조물책임", "환불", "약관"], "L38"),
        "L39_TELECOM":      (["정보통신", "통신", "전기통신", "방송통신"], "L39"),
        "L40_HUMAN_RIGHTS": (["인권", "차별", "평등", "인권침해"], "L40"),

        # L41-L50
        "L41_DIVORCE":      (["이혼", "가족", "양육권", "양육비", "친권", "면접교섭", "재산분할"], "L41"),
        "L42_COPYRIGHT":    (["저작권", "저작물", "저작자", "복제", "공연", "전송"], "L42"),
        "L43_INDUSTRIAL":   (["산업재해", "산재", "업무상재해", "요양급여", "장해급여"], "L43"),
        "L44_WELFARE":      (["사회복지", "복지", "사회보장", "기초생활", "복지시설"], "L44"),
        "L45_EDUCATION":    (["교육", "청소년", "학교", "학교폭력", "교육청", "학생"], "L45"),
        "L46_PENSION":      (["보험", "연금", "국민연금", "퇴직연금", "기금"], "L46"),
        "L47_VENTURE":      (["벤처", "신산업", "규제샌드박스", "신기술"], "L47"),
        "L48_ARTS":         (["문화예술", "예술", "예술인", "공연", "전시"], "L48"),
        "L49_FOOD":         (["식품", "보건", "식약처", "위생", "의약품"], "L49"),
        "L50_MULTICUL":     (["다문화", "이주", "외국인", "결혼이민", "난민"], "L50"),

        # L51-L60
        "L51_RELIGION":     (["종교", "전통", "사찰", "교회", "종단"], "L51"),
        "L52_MEDIA":        (["광고", "언론", "방송", "신문", "기자", "명예훼손"], "L52"),
        "L53_AGRI":         (["농림", "축산", "농업", "축산업", "농지", "가축"], "L53"),
        "L54_FISHERY":      (["해양", "수산", "어업", "어선", "수산물"], "L54"),
        "L55_SCIENCE":      (["과학기술", "연구개발", "R&D", "기술이전"], "L55"),
        "L56_DISABILITY":   (["장애인", "복지", "장애", "장애인권익"], "L56"),
        "L57_INHERITANCE":  (["상속", "신탁", "유산", "유언장", "상속포기", "한정승인", "신탁재산"], "L57"),
        "L58_SPORTS":       (["스포츠", "레저", "체육", "운동선수", "도핑"], "L58"),
        "L59_AI_ETHICS":    (["데이터", "AI윤리", "인공지능", "알고리즘", "빅데이터"], "L59"),
        # L60 마디는 fallback으로만 사용
    }

    # 키워드 매칭 (점수 기반 - 가장 많이 매칭된 도메인 선택)
    max_score = 0
    selected_leader = None

    for _, (keywords, leader_id) in domain_map.items():
        score = sum(1 for k in keywords if k in query)
        if score > max_score:
            max_score = score
            selected_leader = leader_id

    if max_score > 0 and selected_leader:
        logger.info(f"🎯 [L2] {selected_leader} 리더 자동 배정 (키워드 {max_score}개 매칭)")
        return registry.get(selected_leader, registry.get("L60", {"name": "마디 통합 리더", "role": "시스템 기본 분석"}))

    # 3) Fallback
    logger.warning(f"⚠️ [L2] 전문 리더 미매칭, L60 (마디 통합 리더) 사용")
    return registry.get("L60", {"name": "마디 통합 리더", "role": "시스템 기본 법리 분석 노드"})

# =============================================================
# ⚙️ [CONFIG] load
# =============================================================

def load_integrated_config() -> Dict[str, Any]:
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# =============================================================
# [ULTRA] DIAGNOSTICS SNAPSHOT
# =============================================================

def _diagnostic_snapshot() -> Dict[str, Any]:
    return {
        "timestamp": _now_iso(),
        "python": sys.version,
        "pid": os.getpid(),
        "os_version": OS_VERSION,
        "modules": {
            "drf": bool(RUNTIME.get("drf")),
            "selector": bool(RUNTIME.get("selector")),
            "guard": bool(RUNTIME.get("guard")),
            "search_service": bool(RUNTIME.get("search_service")),
            "swarm": bool(RUNTIME.get("swarm")),
            "swarm_orchestrator": bool(RUNTIME.get("swarm_orchestrator")),
            "clevel_handler": bool(RUNTIME.get("clevel_handler")),
            "db_client": bool(db_client),
            "gemini_key": bool(os.getenv("GEMINI_KEY")),
        },
        "metrics": METRICS,
    }

# =============================================================
# 🚀 STARTUP
# =============================================================

@app.on_event("startup")
async def startup():

    logger.info(f"🚀 Lawmadi OS {OS_VERSION} starting...")

    # [감사 #4.2] SOFT_MODE 기본값을 true로 변경 (Cloud Run 일시 장애 대비)
    soft_mode = os.getenv("SOFT_MODE", "true").lower() == "true"
    db_disabled = os.getenv("DB_DISABLED", "0") == "1"

    # --------------------------------------------------
    # 1️⃣ DB 초기화 (Fail-Soft)
    # --------------------------------------------------
    if not db_disabled:
        if db_client:
            try:
                init_fn = getattr(db_client, "init_tables", None)
                if init_fn:
                    init_fn()
                    logger.info("✅ DB init complete")

                # 방문자 통계 테이블 초기화
                db_client_v2 = optional_import("connectors.db_client_v2")
                if db_client_v2 and hasattr(db_client_v2, "init_visitor_stats_table"):
                    db_client_v2.init_visitor_stats_table()

            except Exception as e:
                logger.warning(f"🟡 DB init failed: {e}")
                if not soft_mode:
                    raise
        else:
            logger.warning("🟡 db_client module unavailable")

    # --------------------------------------------------
    # 2️⃣ Config 로드
    # --------------------------------------------------
    try:
        config = load_integrated_config()
        logger.info("✅ Config loaded")
    except Exception as e:
        logger.error(f"❌ Config load failed: {e}")
        if not soft_mode:
            raise
        config = {}

    # --------------------------------------------------
    # 3️⃣ SwarmManager (Fail-Soft)
    # --------------------------------------------------
    swarm = None
    if SwarmManager:
        try:
            swarm = SwarmManager(config)
            logger.info("✅ SwarmManager initialized")
        except Exception as e:
            logger.warning(f"🟡 SwarmManager degraded: {e}")

    # --------------------------------------------------
    # 3.5️⃣ SwarmOrchestrator (60 Leader 진정한 협업)
    # --------------------------------------------------
    swarm_orchestrator = None
    if SwarmOrchestrator:
        try:
            # leaders.json에서 로드된 leader_registry 사용
            # config.json의 swarm_engine_config가 있으면 그것을 사용, 없으면 별도 파일에서 로드
            leader_reg = config.get("swarm_engine_config", {}).get("leader_registry", {})

            # 별도 leaders.json 파일이 있는 경우 그것 우선 사용
            if os.path.exists("leaders.json"):
                try:
                    with open("leaders.json", "r", encoding="utf-8") as f:
                        leaders_data = json.load(f)
                        leader_reg = leaders_data.get("swarm_engine_config", {}).get("leader_registry", leader_reg)
                except Exception as e:
                    logger.warning(f"leaders.json 로드 실패: {e}")

            swarm_orchestrator = SwarmOrchestrator(leader_reg, config)
            logger.info(f"✅ SwarmOrchestrator initialized ({len(leader_reg)} leaders)")
        except Exception as e:
            logger.warning(f"🟡 SwarmOrchestrator degraded: {e}")

    # --------------------------------------------------
    # 3.6️⃣ CLevelHandler (C-Level 임원 호출)
    # --------------------------------------------------
    clevel_handler = None
    if CLevelHandler:
        try:
            # leaders.json에서 core_registry 로드
            core_reg = {}
            if os.path.exists("leaders.json"):
                try:
                    with open("leaders.json", "r", encoding="utf-8") as f:
                        leaders_data = json.load(f)
                        core_reg = leaders_data.get("core_registry", {})
                except Exception as e:
                    logger.warning(f"core_registry 로드 실패: {e}")

            clevel_handler = CLevelHandler(core_reg)
            logger.info(f"✅ CLevelHandler initialized ({len(core_reg)} executives)")
        except Exception as e:
            logger.warning(f"🟡 CLevelHandler degraded: {e}")

    # --------------------------------------------------
    # 4️⃣ Gemini 설정
    # [감사 #4.1] 모델명 환경변수화
    # --------------------------------------------------
    gemini_key = os.getenv("GEMINI_KEY")
    if gemini_key:
        genai.configure(api_key=gemini_key)
        logger.info("✅ Gemini configured")
    else:
        logger.warning("⚠️ GEMINI_KEY 누락 (FAIL_CLOSED)")

    # --------------------------------------------------
    # 5️⃣ DRF Connector (Fail-Soft)
    # [원본버그 수정] DRFConnector(config) → DRFConnector(api_key=...)
    #   실제 시그니처: __init__(self, api_key, timeout_ms, endpoints, ...)
    # [감사 #2.3] DRF OC 기본값 "choepeter" 하드코딩 제거
    # --------------------------------------------------
    drf_conn = None
    if DRFConnector:
        drf_oc = os.getenv("LAWGO_DRF_OC", "").strip()
        if drf_oc:
            try:
                drf_conn = DRFConnector(
                    api_key=drf_oc,
                    timeout_ms=int(os.getenv("DRF_TIMEOUT_MS", "5000")),
                )
                logger.info("✅ DRFConnector initialized")
            except Exception as e:
                logger.warning(f"🟡 DRFConnector degraded: {e}")
        else:
            logger.warning("⚠️ LAWGO_DRF_OC 미설정: DRF 비활성화")

    # --------------------------------------------------
    # 6️⃣ SearchService (DRF 기반)
    # [원본버그 수정] SearchService(config) → SearchService()
    #   실제 시그니처: __init__(self) — 인자 없음, 내부에서 DRF 직접 생성
    # --------------------------------------------------
    search_service = None
    if SearchService:
        try:
            search_service = SearchService()
            logger.info("✅ SearchService initialized")
        except Exception as e:
            logger.warning(f"🟡 SearchService degraded: {e}")

    # --------------------------------------------------
    # 7️⃣ SafetyGuard (Fail-Soft)
    # --------------------------------------------------
    guard = None
    if SafetyGuard:
        try:
            safety_config = config.get("security_layer", {}).get("safety", {})
            guard = SafetyGuard(
                policy=True,
                restricted_keywords=[],
                safety_config=safety_config,
            )
            logger.info("✅ SafetyGuard initialized")
        except Exception as e:
            logger.warning(f"🟡 SafetyGuard degraded: {e}")

    # --------------------------------------------------
    # 8️⃣ LawSelector (Fail-Soft)
    # --------------------------------------------------
    selector = None
    if LawSelector:
        try:
            selector = LawSelector()
        except Exception as e:
            logger.warning(f"🟡 LawSelector degraded: {e}")

    # --------------------------------------------------
    # 9️⃣ RUNTIME SSOT 등록
    # --------------------------------------------------
    RUNTIME.update({
        "config": config,
        "drf": drf_conn,
        "selector": selector,
        "guard": guard,
        "search_service": search_service,
        "swarm": swarm,
        "swarm_orchestrator": swarm_orchestrator,
        "clevel_handler": clevel_handler,
    })

    METRICS["boot_time"] = _now_iso()
    logger.info(f"✅ Lawmadi OS {OS_VERSION} Online")

# =============================================================
# 🏠 Frontend Serving (Homepage)
# =============================================================

# Static files (CSS, JS, images) - must be before root route
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def serve_homepage():
    """Root route - serve homepage"""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Lawmadi OS v50 API", "version": OS_VERSION, "frontend": "https://lawmadi-db.web.app"}

# =============================================================
# ✅ health
# =============================================================

@app.get("/health")
async def health():
    return {
        "status": "online",
        "os_version": OS_VERSION,
        "diagnostics": _diagnostic_snapshot(),
    }

# [ULTRA] 내부 전용 엔드포인트 인증
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

def _verify_internal_auth(authorization: str = Header(default="")) -> None:
    """내부 엔드포인트 접근 시 Bearer token 검증"""
    if not _INTERNAL_API_KEY:
        # 키 미설정 시 FAIL_CLOSED: 접근 차단
        raise HTTPException(status_code=403, detail="INTERNAL_API_KEY not configured")
    token = authorization.removeprefix("Bearer ").strip()
    if token != _INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# [ULTRA] 메트릭 엔드포인트 (인증 필수)
@app.get("/metrics")
async def metrics(authorization: str = Header(default="")):
    _verify_internal_auth(authorization)
    return METRICS

# [ULTRA] 진단 엔드포인트 (인증 필수)
@app.get("/diagnostics")
async def diagnostics(authorization: str = Header(default="")):
    _verify_internal_auth(authorization)
    return _diagnostic_snapshot()

# =============================================================
# 📊 Visitor Stats API
# =============================================================

@app.post("/api/visit")
async def record_visitor(req: Request):
    """
    방문 기록 API
    - IP 주소를 자동으로 추출하여 visitor_id로 사용
    - 신규 방문자 여부 반환
    """
    try:
        # IP 주소를 visitor_id로 사용
        visitor_id = _get_client_ip(req)

        if not visitor_id or visitor_id == "unknown":
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "Could not determine client IP"}
            )

        db_client = optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "record_visit"):
            result = db_client.record_visit(visitor_id)
            return result
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"⚠️ [API] /api/visit 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@app.get("/api/visitor-stats")
async def get_visitor_statistics():
    """
    방문자 통계 조회 API
    - today_visitors: 오늘 방문자 수
    - total_visitors: 총 누적 방문자 수
    """
    try:
        db_client = optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_visitor_stats"):
            stats = db_client.get_visitor_stats()
            return stats
        else:
            # DB 비활성화 시 기본값 반환
            return {
                "ok": True,
                "today_visitors": 0,
                "total_visitors": 0,
                "today_visits": 0,
                "total_visits": 0,
                "note": "DB disabled"
            }

    except Exception as e:
        logger.error(f"⚠️ [API] /api/visitor-stats 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "today_visitors": 0,
                "total_visitors": 0,
                "error": str(e)
            }
        )


@app.get("/api/admin/leader-stats")
async def get_leader_stats_api(days: int = 30, authorization: str = Header(default="")):
    """
    관리자 API: 리더별 통계
    - days: 최근 N일 (기본 30일)
    """
    _verify_internal_auth(authorization)

    try:
        db_client = optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_leader_statistics"):
            stats = db_client.get_leader_statistics(days)
            return stats
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"⚠️ [API] /api/admin/leader-stats 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@app.get("/api/admin/category-stats")
async def get_category_stats_api(days: int = 30, authorization: str = Header(default="")):
    """
    관리자 API: 질문 유형별 통계
    - days: 최근 N일 (기본 30일)
    """
    _verify_internal_auth(authorization)

    try:
        db_client = optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_query_category_statistics"):
            stats = db_client.get_query_category_statistics(days)
            return stats
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"⚠️ [API] /api/admin/category-stats 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@app.get("/api/admin/leader-queries/{leader_code}")
async def get_leader_queries_api(
    leader_code: str,
    limit: int = 10,
    authorization: str = Header(default="")
):
    """
    관리자 API: 특정 리더가 받은 질문 샘플
    - leader_code: 리더 코드 (예: "온유", "L08")
    - limit: 최대 개수 (기본 10)
    """
    _verify_internal_auth(authorization)

    try:
        db_client = optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_leader_query_samples"):
            samples = db_client.get_leader_query_samples(leader_code, limit)
            return samples
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"⚠️ [API] /api/admin/leader-queries 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )

# =============================================================
# ✅ ask (HARDENED + Dual SSOT Safe Mode)
# =============================================================

@app.post("/ask")
async def ask(req: Request):

    trace = _trace_id()  # [ULTRA]
    start_time = time.time()

    try:
        data = await req.json()
        query = (data.get("query", "") or "").strip()

        # IP 주소를 사용자 ID로 사용 (자동 추출)
        visitor_id = _get_client_ip(req)
        logger.info(f"🔍 Request from IP: {visitor_id}")

        config = RUNTIME.get("config", {})

        # -------------------------------------------------
        # 0) Low Signal 차단
        # -------------------------------------------------
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
                "- 사건 개요\n"
                "- 날짜/당사자/증빙\n"
                "- 원하는 결과\n\n"
                "5. 🔍 참고 정보:\n"
                "본 시스템은 법률 자문이 아닌 정보 제공 시스템입니다.\n"
            )
            _audit("ask_low_signal", {"query": query, "status": "SKIPPED", "latency_ms": 0})
            return {"trace_id": trace, "response": msg, "leader": "마디 통합 리더", "status": "SUCCESS"}

        # -------------------------------------------------
        # 0.5) Gemini 키 점검
        # -------------------------------------------------
        if not os.getenv("GEMINI_KEY"):
            _audit("ask_fail_closed", {"query": query, "status": "FAIL_CLOSED", "leader": "SYSTEM"})
            return {"trace_id": trace, "response": "⚠️ GEMINI_KEY 미설정으로 추론이 비활성화되었습니다.", "status": "FAIL_CLOSED"}

        # -------------------------------------------------
        # 1) Security Guard
        # [원본버그 수정] guard.check()가 "CRISIS"를 반환할 수 있으나
        #   원본은 `not guard.check(query)`로만 처리 → CRISIS 누락.
        #   "CRISIS" is truthy이므로 not "CRISIS" = False → 차단 안됨.
        #   그러나 위기 상황 전용 응답을 주지 못함. → 명시적 분기 추가.
        # -------------------------------------------------
        guard = RUNTIME.get("guard")
        if guard:
            check_result = guard.check(query)

            if check_result == "CRISIS":
                safety_config = config.get("security_layer", {}).get("safety", {})
                crisis_res = safety_config.get("crisis_resources", {})
                lines = ["🚨 당신의 안전이 가장 중요합니다.\n"]
                for label, number in crisis_res.items():
                    lines.append(f"  📞 {label}: {number}")
                lines.append("\n위 전문 기관으로 지금 바로 연락하세요.")
                _audit("ask_crisis", {"query": query, "status": "CRISIS", "leader": "SAFETY"})
                return {"trace_id": trace, "response": "\n".join(lines), "leader": "SAFETY", "status": "CRISIS"}

            if check_result is False:
                _audit("ask_blocked", {"query": query, "status": "BLOCKED", "leader": "GUARD"})
                return {"trace_id": trace, "response": "🚫 보안 정책에 의해 차단되었습니다.", "status": "BLOCKED"}

        # -------------------------------------------------
        # 2) C-Level 임원 호출 확인
        # -------------------------------------------------
        clevel = RUNTIME.get("clevel_handler")
        clevel_decision = None
        if clevel:
            clevel_decision = clevel.should_invoke_clevel(query)
            if clevel_decision.get("invoke"):
                logger.info(f"🎯 C-Level 호출: {clevel_decision.get('executive_id')} - {clevel_decision.get('reason')}")

        # -------------------------------------------------
        # 3) Dual SSOT 선점 점검 (DRF 살아있는지 확인)
        # [원본버그 수정] 중복 law_search 호출 제거, 들여쓰기 오류 수정
        # -------------------------------------------------
        drf_connector = RUNTIME.get("drf")
        ssot_available = False
        if drf_connector:
            try:
                test_result = drf_connector.law_search(query)
                ssot_available = bool(test_result)
            except Exception as e:
                logger.warning(f"[Pre-check] SSOT error: {e}")

        # -------------------------------------------------
        # 3) LLM Tool 설정 (SSOT 살아있을 때만 활성화)
        # [감사 #4.1] GEMINI_MODEL 환경변수화
        # -------------------------------------------------
        tools = []
        if ssot_available:
            tools = [search_law_drf, search_precedents_drf]

        now_utc = _now_iso()
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-09-2025")

        # -------------------------------------------------
        # 4) C-Level 직접 호출 처리
        # -------------------------------------------------
        if clevel_decision and clevel_decision.get("mode") == "direct":
            # C-Level 임원 직접 호출
            exec_id = clevel_decision.get("executive_id")
            logger.info(f"🎯 C-Level 직접 모드: {exec_id}")

            # C-Level 전용 시스템 지시
            clevel_instruction = clevel.get_clevel_system_instruction(exec_id, SYSTEM_INSTRUCTION_BASE)

            model = genai.GenerativeModel(
                model_name=model_name,
                tools=tools,
                system_instruction=clevel_instruction
            )

            chat = model.start_chat(enable_automatic_function_calling=True)
            resp = chat.send_message(
                f"now_utc={now_utc}\n"
                f"ssot_available={ssot_available}\n"
                f"사용자 질문: {query}"
            )

            final_text = (resp.text or "").strip()
            leader_name = clevel.executives.get(exec_id, {}).get("name", exec_id)
            swarm_mode = False

            logger.info(f"✅ C-Level 분석 완료: {leader_name}")

        # -------------------------------------------------
        # 5) SwarmOrchestrator 우선 사용 (60 Leader 협업)
        # -------------------------------------------------
        elif not (clevel_decision and clevel_decision.get("mode") == "direct"):
            orchestrator = RUNTIME.get("swarm_orchestrator")

            if orchestrator and os.getenv("USE_SWARM", "true").lower() == "true":
                # Swarm 모드: 진정한 다중 Leader 협업
                logger.info("🐝 SwarmOrchestrator 모드 활성화")

                try:
                    swarm_result = orchestrator.orchestrate(
                        query=query,
                        tools=tools,
                        system_instruction_base=SYSTEM_INSTRUCTION_BASE,
                        model_name=model_name,
                        force_single=False
                    )

                    final_text = swarm_result["response"]
                    leader_names = swarm_result.get("leaders", ["마디"])
                    leader_name = ", ".join(leader_names[:3]) + (f" 외 {len(leader_names)-3}명" if len(leader_names) > 3 else "")
                    swarm_mode = swarm_result.get("swarm_mode", False)

                    logger.info(f"✅ Swarm 분석 완료: {leader_name} ({swarm_result.get('leader_count', 1)}명 협업)")

                except Exception as e:
                    logger.error(f"❌ SwarmOrchestrator 실패, Fallback: {e}")
                    # Fallback to single leader
                    orchestrator = None

            if not orchestrator or os.getenv("USE_SWARM", "true").lower() != "true":
                # 기존 단일 Leader 모드 (Fallback)
                logger.info("🔄 단일 Leader 모드 (Fallback)")

                leader = select_swarm_leader(query, LEADER_REGISTRY)
                leader_name = leader['name']
                swarm_mode = False

                model = genai.GenerativeModel(
                    model_name=model_name,
                    tools=tools,
                    system_instruction=(
                        f"{SYSTEM_INSTRUCTION_BASE}\n"
                        f"현재 당신은 '{leader['name']}({leader['role']})' 노드입니다.\n"
                        f"반드시 [{leader['name']} 답변]으로 시작하세요."
                    ),
                )

                chat = model.start_chat(enable_automatic_function_calling=True)

                resp = chat.send_message(
                    f"now_utc={now_utc}\n"
                    f"ssot_available={ssot_available}\n"
                    f"사용자 질문: {query}"
                )

                final_text = (resp.text or "").strip()

        # -------------------------------------------------
        # 5) Governance 검증
        # -------------------------------------------------
        if not validate_constitutional_compliance(final_text):
            _audit("ask_fail_closed", {
                "query": query,
                "status": "GOVERNANCE",
                "leader": leader_name,
            })
            return {
                "trace_id": trace,
                "response": "⚠️ 시스템 무결성 정책에 의해 답변이 제한되었습니다.",
                "status": "FAIL_CLOSED",
            }

        latency_ms = int((time.time() - start_time) * 1000)

        # -------------------------------------------------
        # 6) Metrics [ULTRA]
        # -------------------------------------------------
        METRICS["requests"] += 1
        req_count = METRICS["requests"]
        prev_avg = METRICS["avg_latency_ms"]
        METRICS["avg_latency_ms"] = int(((prev_avg * (req_count - 1)) + latency_ms) / max(req_count, 1))

        # -------------------------------------------------
        # 7) Audit
        # -------------------------------------------------
        _audit("ask", {
            "query": query,
            "leader": leader_name,
            "status": "SUCCESS",
            "latency_ms": latency_ms,
            "response_sha256": _sha256(final_text),
            "swarm_mode": swarm_mode if 'swarm_mode' in locals() else False,
        })

        # -------------------------------------------------
        # 8) Chat History 저장 (사용자 로그 분석용)
        # -------------------------------------------------
        try:
            db_client_v2 = optional_import("connectors.db_client_v2")
            if db_client_v2 and hasattr(db_client_v2, "save_chat_history"):
                # 질문 유형 자동 분류
                query_category = db_client_v2.classify_query_category(query)

                # 리더 목록 (Swarm 모드인 경우)
                leaders_used = None
                if swarm_mode and 'leader_names' in locals():
                    leaders_used = leader_names

                # 저장
                db_client_v2.save_chat_history(
                    user_query=query,
                    ai_response=final_text,
                    leader=leader_name,
                    status="success",
                    latency_ms=latency_ms,
                    visitor_id=visitor_id,
                    swarm_mode=swarm_mode if 'swarm_mode' in locals() else False,
                    leaders_used=leaders_used,
                    query_category=query_category
                )
        except Exception as log_error:
            logger.warning(f"⚠️ [ChatHistory] 저장 실패 (무시): {log_error}")

        return {
            "trace_id": trace,
            "response": final_text,
            "leader": leader_name,
            "status": "SUCCESS",
            "latency_ms": latency_ms,
            "swarm_mode": swarm_mode if 'swarm_mode' in locals() else False,
        }

    except Exception as e:
        METRICS["errors"] += 1
        ref = datetime.datetime.now().strftime("%H%M%S")
        logger.error(f"💥 커널 에러 (trace={trace}, ref={ref}): {e}")
        logger.error(traceback.format_exc())
        _audit("ask_error", {"query": str(locals().get("query", "")), "status": "ERROR", "leader": "SYSTEM", "latency_ms": 0})
        return {"trace_id": trace, "response": f"⚠️ 시스템 장애가 발생했습니다. (Ref: {ref})", "status": "ERROR"}

# =============================================================
# ✅ search / trending (SearchService 없으면 ERROR)
# =============================================================

@app.get("/search")
async def search(q: str, limit: int = 10):
    svc = RUNTIME.get("search_service")
    if not svc:
        return {"status": "ERROR", "message": "SearchService not ready"}
    return svc.search_law(q)

@app.get("/trending")
async def trending(limit: int = 10):
    svc = RUNTIME.get("search_service")
    if not svc:
        return {"status": "ERROR", "message": "SearchService not ready"}
    # SearchService에 trending_laws가 없으므로 search_precedents로 대체
    return svc.search_precedents(limit)

# =============================================================
# [ULTRA] GLOBAL EXCEPTION HANDLER
# =============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    METRICS["errors"] += 1
    logger.error(f"[GLOBAL] {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "Kernel-Level Exception", "timestamp": _now_iso()},
    )

# =============================================================
# SHUTDOWN
# =============================================================

@app.on_event("shutdown")
async def shutdown():
    logger.info(f"🛑 Lawmadi OS {OS_VERSION} Shutdown")

# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)