import re
import time
import hashlib
import enum
import logging
import threading
import unicodedata
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger("LawmadiOS.Security")

# ─── [IT 기술: LMD-CONST 헌법 이벤트 정의] ──────────────────────────────────────────
class ConstitutionEvent(enum.Enum):
    """
    Lawmadi OS의 핵심 보안 및 무결성 정책 이벤트를 정의합니다.
    시스템 가동 중 발생하는 모든 예외는 이 이벤트 규격에 따라 트래킹됩니다.
    """
    LMD_CONST_001 = "LLM_LAW_PRECEDENT_SEARCH_ATTEMPT" # 법령/판례 탐색 시도
    LMD_CONST_005 = "CACHE_INTEGRITY_VIOLATION"      # 캐시 무결성 위반 (SHA-256 불일치)
    LMD_CONST_007A = "API_UNAVAILABLE_WITH_VERIFIED_CACHE" # API 장애 시 검증된 캐시 사용
    LMD_CONST_007B = "API_UNAVAILABLE_NO_CACHE"      # API 장애 및 캐시 부재 (Fail-Closed)


# ─── [IT 기술: 스테이트 머신 기반 Circuit Breaker] ────────────────────────────────────
class CBState(enum.Enum):
    """서킷 브레이커의 인프라 가동 상태 정의"""
    CLOSED = "CLOSED"       # 정상 운영 (트래픽 통과)
    OPEN = "OPEN"           # 장애 차단 (트래픽 전면 차단)
    HALF_OPEN = "HALF_OPEN" # 복구 시도 (제한된 트래픽 허용)


class CircuitBreaker:
    """
    [L0: INFRA_RESILIENCE] Per-provider Circuit Breaker
    외부 API(DRF 등) 공급자의 장애가 전체 커널로 전파되는 것을 차단하는 스테이트 머신입니다.
    """
    def __init__(self, provider_name: str, config: Dict[str, Any]):
        self.provider_name = provider_name
        self.failure_threshold: int = config.get("failure_threshold", 5)
        self.reset_timeout_ms: int = config.get("reset_timeout_ms", 30000)
        self.half_open_max_calls: int = config.get("half_open_max_calls", 3)

    # 상태 관리 변수 (IT 기술: 인메모리 상태 제어)
        self.state = CBState.CLOSED
        self.failure_count = 0
        self.half_open_call_count = 0
        self.opened_at: float = 0.0
        self._lock = threading.Lock()

    # ── [IT 기술: 상태 전이 로직 (State Transition)] ────────────────────────────────
    def _transition_to_open(self):
        self.state = CBState.OPEN
        self.opened_at = time.time()
        self.half_open_call_count = 0
        logger.warning(f"[CB:{self.provider_name}] CLOSED → OPEN (failures={self.failure_count})")

    def _transition_to_half_open(self):
        self.state = CBState.HALF_OPEN
        self.half_open_call_count = 0
        logger.info(f"[CB:{self.provider_name}] OPEN → HALF_OPEN (reset_timeout 경과)")

    def _transition_to_closed(self):
        self.state = CBState.CLOSED
        self.failure_count = 0
        self.half_open_call_count = 0
        logger.info(f"[CB:{self.provider_name}] HALF_OPEN → CLOSED (복구 완료)")

    # ── [IT 기술: 가용성 판정 (Flow Control)] ───────────────────────────────────────
    def is_allowed(self) -> bool:
        """현재 상태에 따라 외부 API 호출 허용 여부를 결정론적으로 반환합니다."""
        with self._lock:
            if self.state == CBState.CLOSED:
                return True

            if self.state == CBState.OPEN:
                elapsed_ms = (time.time() - self.opened_at) * 1000
                if elapsed_ms >= self.reset_timeout_ms:
                    self._transition_to_half_open()
                    return True
                return False

            if self.state == CBState.HALF_OPEN:
                if self.half_open_call_count < self.half_open_max_calls:
                    self.half_open_call_count += 1
                    return True
                return False

        return False

    # ── [IT 기술: 피드백 루프 (Feedback Loop)] ───────────────────────────────────────
    def record_success(self):
        """호출 성공 시 상태를 리셋하거나 HALF_OPEN에서 복구합니다."""
        with self._lock:
            if self.state == CBState.HALF_OPEN:
                self._transition_to_closed()
            else:
                self.failure_count = 0

    def record_failure(self):
        """호출 실패 시 카운트를 증가시키고 임계값 도달 시 서킷을 개방합니다."""
        with self._lock:
            self.failure_count += 1
            if self.state == CBState.CLOSED and self.failure_count >= self.failure_threshold:
                self._transition_to_open()
            elif self.state == CBState.HALF_OPEN:
                # 복구 시도 중 실패 시 즉시 재차단 (Fail-Fast 정책)
                self.state = CBState.OPEN
                self.opened_at = time.time()
                logger.warning(f"[CB:{self.provider_name}] HALF_OPEN → OPEN (복구 실패)")

    def get_state(self) -> str:
        return self.state.value


# ─── [IT 기술: 하이브리드 Safety Guard (Anti-Leak + Crisis Flow)] ───────────────────
class SafetyGuard:
    """
    [L0/L5: SECURITY_SHIELD] 세이프티 가드
    사용자 입력 필터링, 내부 자산 유출 방지(Anti-Leak), 위급 상황(Crisis) 대응을 통합 수행합니다.
    """
    def __init__(self, policy: bool, restricted_keywords: List[str], safety_config: Dict[str, Any]):
        self.enabled = policy
        self.restricted_keywords = restricted_keywords

        # Crisis 매니지먼트 설정
        self.crisis_trigger_keywords: List[str] = safety_config.get("trigger_keywords", [])
        self.confirmation_question: str = safety_config.get("confirmation_question", "")
        self.confirmation_timeout_sec: int = safety_config.get("confirmation_timeout_sec", 30)
        self.crisis_resources: Dict[str, str] = safety_config.get("crisis_resources", {})

        # Anti-Leak: 시스템 프롬프트 및 내부 핵심 자산 접근 패턴 (IT 보안 강화)
        self.malicious_pattern = re.compile(
            r"(system_prompt|api_key|password|db_config|GEMINI_KEY|DRF_OC|INTERNAL_SECRETS)",
            re.IGNORECASE
        )

        # LLM 프롬프트 인젝션 방어 패턴 (한국어/영어 확장)
        self.prompt_injection_patterns = re.compile(
            r"("
            r"ignore\s+(all\s+)?previous\s+instructions?"
            r"|ignore\s+(all\s+)?above"
            r"|disregard\s+(all\s+)?previous"
            r"|forget\s+(all\s+)?((your|the)\s+)?(previous\s+)?instructions?"
            r"|이전\s*(의|에)?\s*지시(사항)?를?\s*(무시|잊어|버려)"
            r"|위\s*내용을?\s*(무시|잊어|버려)"
            r"|시스템\s*프롬프트(를)?\s*(출력|보여|알려)"
            r"|print\s+(your\s+)?system\s+prompt"
            r"|show\s+(me\s+)?(your\s+)?instructions?"
            r"|what\s+are\s+your\s+instructions"
            r"|repeat\s+(your\s+)?(system|initial)\s+(prompt|instructions?)"
            r"|you\s+are\s+now\s+(a|an|my)"
            r"|pretend\s+(to\s+be|you\s+are)"
            r"|act\s+as\s+(if|a|an|my)"
            r"|역할을?\s*바꿔|역할\s*변경"
            r"|너는?\s*이제\s*(부터)?\s*(나의|내)"
            r"|DAN\s*모드|jailbreak"
            r"|do\s+anything\s+now"
            r"|developer\s+mode"
            r"|내부\s*구조(를)?\s*(알려|출력|보여)"
            r"|프롬프트(를)?\s*(공개|노출|출력)"
            r"|지시문(을)?\s*(무시|출력|보여)"
            r"|모든\s*제한(을)?\s*(해제|풀어|무시)"
            r")",
            re.IGNORECASE
        )

        # SQL Injection 확장 패턴 (20+ patterns)
        self.sql_injection_patterns = re.compile(
            r"("
            r"DROP\s+TABLE"
            r"|UNION\s+(ALL\s+)?SELECT"
            r"|';\s*--"
            r"|1\s*=\s*1"
            r"|OR\s+1\s*=\s*1"
            r"|AND\s+1\s*=\s*1"
            r"|INSERT\s+INTO"
            r"|DELETE\s+FROM"
            r"|UPDATE\s+\w+\s+SET"
            r"|ALTER\s+TABLE"
            r"|CREATE\s+TABLE"
            r"|EXEC(\s+|\s*\()"
            r"|EXECUTE(\s+|\s*\()"
            r"|xp_cmdshell"
            r"|LOAD_FILE\s*\("
            r"|INTO\s+OUTFILE"
            r"|INTO\s+DUMPFILE"
            r"|BENCHMARK\s*\("
            r"|SLEEP\s*\("
            r"|WAITFOR\s+DELAY"
            r"|CONCAT\s*\("
            r"|CHAR\s*\("
            r"|information_schema"
            r"|sys\.tables"
            r"|pg_catalog"
            r")",
            re.IGNORECASE
        )

        # XSS 패턴
        self.xss_patterns = re.compile(
            r"("
            r"<script[^>]*>"
            r"|</script>"
            r"|javascript\s*:"
            r"|on(error|load|click|mouseover|focus|blur)\s*="
            r"|<iframe[^>]*>"
            r"|<object[^>]*>"
            r"|<embed[^>]*>"
            r"|<svg[^>]*\s+on\w+\s*="
            r"|<img[^>]*\s+on\w+\s*="
            r"|document\.(cookie|write|location)"
            r"|window\.(location|open)"
            r"|eval\s*\("
            r"|alert\s*\("
            r"|prompt\s*\("
            r"|confirm\s*\("
            r"|String\.fromCharCode"
            r"|atob\s*\("
            r")",
            re.IGNORECASE
        )

    # ── [IT 기술: 다단계 패킷 검사 (Inspection)] ────────────────────────────────────
    def check(self, user_input: str) -> Union[bool, str]:
        """
        입력 패킷을 다각도로 분석하여 안전성을 판정합니다.
        - False: 보안 위협 감지로 인한 즉시 차단
        - "CRISIS": 위급 상황 모드 트리거
        - True: 검증 통과
        """
        if not self.enabled:
            return True

        if not user_input or not isinstance(user_input, str):
            return False

        # 0. Unicode NFKC 정규화 (동형문자 우회 방지)
        #    예: 'ＤＲＯＰＴＡＢＬＥʼ → 'DROPTABLE' (전각/반각/동형 통일)
        normalized_input = unicodedata.normalize("NFKC", user_input)

        # 1. Anti-Leak: 시스템 내부 기밀 정보 유출 시도 차단
        if self.malicious_pattern.search(normalized_input):
            logger.warning("[LMD-SECURITY-001] 보안 프로토콜에 따라 시스템 핵심 인증 자산 접근이 차단되었습니다.")
            return False

        # 2. 금지 키워드 필터링 (Blacklist)
        lower_input = normalized_input.lower()
        for word in self.restricted_keywords:
            if word in lower_input:
                logger.warning(f"[Security] 금지 키워드 감지: '{word}'")
                return False

        # 3. LLM 프롬프트 인젝션 방어 (Prompt Injection / Jailbreak)
        if self.prompt_injection_patterns.search(normalized_input):
            logger.warning("[LMD-SECURITY-002] 프롬프트 인젝션 시도가 차단되었습니다.")
            return False

        # 4. SQL Injection 방어 (확장 패턴)
        if self.sql_injection_patterns.search(normalized_input):
            logger.warning("[LMD-SECURITY-003] SQL 인젝션 패턴이 감지되어 차단되었습니다.")
            return False

        # 5. XSS 방어
        if self.xss_patterns.search(normalized_input):
            logger.warning("[LMD-SECURITY-004] XSS 패턴이 감지되어 차단되었습니다.")
            return False

        # 6. 위급 상황(Crisis) 트리거 감지
        if any(kw in lower_input for kw in self.crisis_trigger_keywords):
            return "CRISIS"

        return True

    # ── [IT 기술: Crisis Handling 인터페이스] ────────────────────────────────────────
    def handle_crisis(self, get_user_response_fn=None) -> None:
        """
        사용자의 안전을 최우선으로 하는 위급 상황 프로토콜을 가동합니다.
        IT 서비스 윤리와 기술적 가용성을 동시에 확보합니다.
        """
        logger.warning(f"[Safety] {self.confirmation_question}")

        if not get_user_response_fn:
             # 서버 환경(Cloud Run 등)에서는 Blocking 방지를 위해 즉시 안내 메시지 출력
             logger.info("[Server Mode] 인터랙티브 입력이 불가능하므로 안전 안내를 즉시 표시합니다.")
             self._activate_crisis_mode()
             return

        # 비동기 또는 특정 환경에서의 사용자 응답 수신
        user_answer = get_user_response_fn(timeout=self.confirmation_timeout_sec)

        if user_answer in ("예", "yes", "Y", "y"):
            self._activate_crisis_mode()
        elif user_answer in ("아니오", "no", "N", "n"):
            logger.info("[Safety] 안전 상황 확인됨. 법률 상담 대화를 계속합니다.")
        else:
            # 타임아웃 또는 모호한 응답 시 안전을 위해 Crisis 모드 진입
            logger.warning("[Safety-TIMEOUT] 응답 시간이 초과되어 안전 모드를 가동합니다.")
            self._activate_crisis_mode()

    def _activate_crisis_mode(self) -> None:
        """[IT 서비스 윤리] 즉시 위급 모드 가동 및 안전 리소스 로드"""
        resources = ", ".join(f"{label}: {number}" for label, number in self.crisis_resources.items())
        logger.critical(f"[IMMEDIATE CRISIS MODE] 위급 모드 가동. 리소스: {resources}")


# ─── [IT 기술: 데이터 무결성 검증 (SHA-256)] ──────────────────────────────────────
def verify_checksum(data: str, expected_signature: str) -> bool:
    """
    [L1: INTEGRITY_VALDIATOR]
    수신된 데이터 패킷 또는 캐시 자산의 SHA-256 지문을 대조합니다.
    LMD-CONST-005 정책을 실시간으로 강제하는 도구입니다.
    """
    computed_hash = hashlib.sha256(data.encode('utf-8')).hexdigest()
    return computed_hash == expected_signature