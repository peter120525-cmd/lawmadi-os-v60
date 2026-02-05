import re
import time
import enum
import threading
from typing import List, Dict, Any

class CBState(enum.Enum):
    CLOSED, OPEN, HALF_OPEN = "CLOSED", "OPEN", "HALF_OPEN"

class CircuitBreaker:
    def __init__(self, provider_name: str, config: Dict[str, Any]):
        self.provider_name = provider_name
        self.failure_threshold = config.get("failure_threshold", 5)
        self.reset_timeout_ms = config.get("reset_timeout_ms", 30000)
        self.state, self.failure_count, self.opened_at = CBState.CLOSED, 0, 0.0
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        with self._lock:
            if self.state == CBState.CLOSED: return True
            if self.state == CBState.OPEN:
                if (time.time() - self.opened_at) * 1000 >= self.reset_timeout_ms:
                    self.state = CBState.HALF_OPEN
                    return True
                return False
            return True

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state, self.opened_at = CBState.OPEN, time.time()

    def record_success(self):
        with self._lock:
            self.state, self.failure_count = CBState.CLOSED, 0

class SafetyGuard:
    def __init__(self, policy: bool, restricted_keywords: List[str], safety_config: Dict[str, Any]):
        self.enabled = policy
        self.crisis_keywords = safety_config.get("trigger_keywords", [])
        self.malicious_pattern = re.compile(r"(system_prompt|api_key|password)", re.IGNORECASE)

    def check(self, user_input: str):
        if not self.enabled: return True
        if self.malicious_pattern.search(user_input): return False
        if any(k in user_input for k in self.crisis_keywords): return "CRISIS"
        return True
