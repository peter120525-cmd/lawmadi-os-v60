import re
import time
import hashlib
import enum
import threading
from typing import List, Dict, Any, Optional


# ─── Constitution Event Types ───────────────────────────────────────────────
class ConstitutionEvent(enum.Enum):
    LMD_CONST_001 = "LLM_LAW_PRECEDENT_SEARCH_ATTEMPT"
    LMD_CONST_005 = "CACHE_INTEGRITY_VIOLATION"
    LMD_CONST_007A = "API_UNAVAILABLE_WITH_VERIFIED_CACHE"
    LMD_CONST_007B = "API_UNAVAILABLE_NO_CACHE"


# ─── Circuit Breaker State Machine ──────────────────────────────────────────
class CBState(enum.Enum):
    CLOSED = "CLOSED"       # 정상 운영
    OPEN = "OPEN"           # 차단 중 (실패 임계값 초과)
    HALF_OPEN = "HALF_OPEN" # 복구 시도 중


class CircuitBreaker:
    """
    [L0] Per-provider Circuit Breaker — CLOSED → OPEN → HALF_OPEN 상태 전이
    config.network_security.circuit_breaker.per_provider 참조
    """
    def __init__(self, provider_name: str, config: Dict[str, Any]):
        self.provider_name = provider_name
        self.failure_threshold: int = config.get("failure_threshold", 5)
        self.reset_timeout_ms: int = config.get("reset_timeout_ms", 30000)
        self.half_open_max_calls: int = config.get("half_open_max_calls", 3)

        # 상태
        self.state = CBState.CLOSED
        self.failure_count = 0
        self.half_open_call_count = 0
        self.opened_at: float = 0.0
        self._lock = threading.Lock()

    # ── 상태 전이 ─────────────────────────────────────────────────────────
    def _transition_to_open(self):
        self.state = CBState.OPEN
        self.opened_at = time.time()
        self.half_open_call_count = 0
        print(f"🔴 [CB:{self.provider_name}] CLOSED → OPEN (failures={self.failure_count})")

    def _transition_to_half_open(self):
        self.state = CBState.HALF_OPEN
        self.half_open_call_count = 0
        print(f"🟡 [CB:{self.provider_name}] OPEN → HALF_OPEN (reset_timeout 경과)")

    def _transition_to_closed(self):
        self.state = CBState.CLOSED
        self.failure_count = 0
        self.half_open_call_count = 0
        print(f"🟢 [CB:{self.provider_name}] HALF_OPEN → CLOSED (복구 완료)")

    # ── 호출 가능 여부 판정 ───────────────────────────────────────────────
    def is_allowed(self) -> bool:
        """호출 가능하면 True, OPEN 차단 중이면 False"""
        with self._lock:
            if self.state == CBState.CLOSED:
                return True

            if self.state == CBState.OPEN:
                elapsed_ms = (time.time() - self.opened_at) * 1000
                if elapsed_ms >= self.reset_timeout_ms:
                    self._transition_to_half_open()
                    return True  # HALF_OPEN으로 전이 후 시도 허용
                return False  # 아직 차단 중

            if self.state == CBState.HALF_OPEN:
                if self.half_open_call_count < self.half_open_max_calls:
                    self.half_open_call_count += 1
                    return True
                return False  # HALF_OPEN 허용 횟수 초과

        return False

    # ── 결과 피드백 ───────────────────────────────────────────────────────
    def record_success(self):
        with self._lock:
            if self.state == CBState.HALF_OPEN:
                self._transition_to_closed()
            else:
                self.failure_count = 0  # CLOSED 상태에서 성공 시 카운트 초기화

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            if self.state == CBState.CLOSED and self.failure_count >= self.failure_threshold:
                self._transition_to_open()
            elif self.state == CBState.HALF_OPEN:
                # HALF_OPEN에서 실패하면 다시 OPEN
                self.state = CBState.OPEN
                self.opened_at = time.time()
                print(f"🔴 [CB:{self.provider_name}] HALF_OPEN → OPEN (복구 실패)")

    def get_state(self) -> str:
        return self.state.value


# ─── Safety Guard (위급 상황 감지 + Anti-Leak + 입력 필터링) ─────────────────
class SafetyGuard:
    """
    [L0] 사용자 입력 필터링, Anti-Leak 정책, 위급 상황(Crisis) 플로 관리
    config.security_layer 및 config.security_layer.safety 참조
    """
    def __init__(self, policy: bool, restricted_keywords: List[str], safety_config: Dict[str, Any]):
        self.enabled = policy
        self.restricted_keywords = restricted_keywords

        # Crisis 설정
        self.crisis_trigger_keywords: List[str] = safety_config.get("trigger_keywords", [])
        self.confirmation_question: str = safety_config.get("confirmation_question", "")
        self.confirmation_timeout_sec: int = safety_config.get("confirmation_timeout_sec", 30)
        self.crisis_resources: Dict[str, str] = safety_config.get("crisis_resources", {})

        # Anti-Leak: 시스템 내부 키/변수 접근 시도 차단
        self.malicious_pattern = re.compile(
            r"(system_prompt|api_key|password|db_config|GEMINI_KEY|DRF_OC|INTERNAL_SECRETS)",
            re.IGNORECASE
        )

    # ── 메인 검사 엔트리포인트 ────────────────────────────────────────────
    def check(self, user_input: str) -> bool:
        """
        returns False → 요청 차단 (main.py에서 continue)
        returns "CRISIS" → 위급 상황 플로 진입
        returns True → 정상 통과
        """
        if not self.enabled:
            return True

        # 1. Anti-Leak: 내부 자산 접근 시도 차단
        if self.malicious_pattern.search(user_input):
            print("🔒 [LMD-SECURITY-001] 보안 프로토콜에 따라 시스템 핵심 인증 자산 접근이 차단되었습니다.")
            return False

        # 2. 금지 키워드 검사
        lower_input = user_input.lower()
        for word in self.restricted_keywords:
            if word in lower_input:
                print(f"🛡️ [Security] 금지 키워드 감지: '{word}'")
                return False

        # 3. 주입 공격 방지 (SQL Injection, Command Injection 기본 패턴)
        injection_patterns = [";", "--", "DROP TABLE", "UNION SELECT", "'; --"]
        if any(p in user_input for p in injection_patterns):
            print("🛡️ [Security] 주입 공격 패턴이 감지되었습니다.")
            return False

        # 4. Crisis 트리거 키워드 감지
        if any(kw in lower_input for kw in self.crisis_trigger_keywords):
            return "CRISIS"  # 특수 반환값 → main.py에서 crisis 플로 처리

        return True

    # ── Crisis 플로 처리 ─────────────────────────────────────────────────
    def handle_crisis(self, get_user_response_fn=None) -> None:
        """
        위급 상황 플로:
        1. 확인 질문 출력
        2. 사용자 응답 대기 (timeout 내)
        3. YES → IMMEDIATE_CRISIS_MODE / NO → 컨텍스트 인식 유지 / TIMEOUT → CRISIS_MODE
        """
        print(f"\n⚠️ [Safety] {self.confirmation_question}")

        user_answer = ""
        if get_user_response_fn:
            # 실제 환경에서는 비동기 입력 또는 웹소켓 응답을 여기에 연결
            user_answer = get_user_response_fn(timeout=self.confirmation_timeout_sec)
        else:
            # CLI 환경 폴백
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError()

            try:
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(self.confirmation_timeout_sec)
                user_answer = input("[Crisis Confirmation] 예/아니오 > ").strip()
                signal.alarm(0)
            except (TimeoutError, EOFError):
                user_answer = ""  # timeout

        # 응답 처리
        if user_answer in ("예", "yes", "Y", "y"):
            self._activate_crisis_mode()
        elif user_answer in ("아니오", "no", "N", "n"):
            print("✅ [Safety] 안전 상황 확인됨. 대화를 계속합니다.")
            print("   (참고: 도움이 필요하시면 언제든지 말씀해 주세요.)")
        else:
            # TIMEOUT 또는 불명확 응답 → 기본적으로 crisis mode 진입
            print("⏱️ [Safety-TIMEOUT] 응답 시간이 초과되었습니다.")
            self._activate_crisis_mode()

    def _activate_crisis_mode(self):
        """즉시 위급 모드 — 모든 프로토콜 중단, 안전 리소스 출력"""
        print("\n" + "=" * 60)
        print("🚨 [IMMEDIATE CRISIS MODE]")
        print("=" * 60)
        print("지금 당신의 안전이 가장 중요합니다.")
        print()
        for label, number in self.crisis_resources.items():
            print(f"  📞 {number}")
        print()
        print("위의 연락처로 지금 바로 연락해 주세요.")
        print("당신은 혼자가 아닙니다.")
        print("=" * 60 + "\n")


# ─── 데이터 무결성 검증 (SHA-256) ────────────────────────────────────────────
def verify_checksum(data: str, expected_signature: str) -> bool:
    """
    [L1] 캐시/응답 데이터의 SHA-256 무결성 검증
    LMD-CONST-005 (CACHE_INTEGRITY_VIOLATION) 트리거와 연결됨
    """
    computed_hash = hashlib.sha256(data.encode()).hexdigest()
    return computed_hash == expected_signature
