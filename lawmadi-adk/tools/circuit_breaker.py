"""
Circuit Breaker for DRF API calls.

3-state pattern (CLOSED/OPEN/HALF_OPEN) to prevent cascading failures.
Based on agents/swarm_orchestrator.py GeminiCircuitBreaker.

Usage:
    from tools.circuit_breaker import drf_circuit_breaker

    if not drf_circuit_breaker.allow_request():
        return {"status": "error", "error_message": "DRF API temporarily unavailable"}
    try:
        result = call_drf_api(...)
        drf_circuit_breaker.record_success()
    except Exception:
        drf_circuit_breaker.record_failure()
        raise
"""

import logging
import threading
import time

logger = logging.getLogger("LawmadiADK.CircuitBreaker")


class CircuitBreaker:
    """3-state Circuit Breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.

    Args:
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait before transitioning OPEN -> HALF_OPEN.
        name: Display name for logging.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "CB",
    ):
        self._lock = threading.Lock()
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = "CLOSED"
        self._last_failure_time: float = 0.0
        self._name = name

    @property
    def state(self) -> str:
        with self._lock:
            if (
                self._state == "OPEN"
                and time.time() - self._last_failure_time >= self._recovery_timeout
            ):
                self._state = "HALF_OPEN"
                logger.info(
                    f"[{self._name}] OPEN -> HALF_OPEN "
                    f"(recovery timeout {self._recovery_timeout}s elapsed)"
                )
            return self._state

    def allow_request(self) -> bool:
        return self.state in ("CLOSED", "HALF_OPEN")

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state != "CLOSED":
                logger.info(f"[{self._name}] {self._state} -> CLOSED (success)")
                self._state = "CLOSED"

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                if self._state != "OPEN":
                    logger.warning(
                        f"[{self._name}] -> OPEN "
                        f"(failures={self._failure_count}/{self._failure_threshold}, "
                        f"recovery in {self._recovery_timeout}s)"
                    )
                self._state = "OPEN"


# Shared instance for DRF API calls (used by drf_tools.py + verify.py)
drf_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="DRF-CB",
)
