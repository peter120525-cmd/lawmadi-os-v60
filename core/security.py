import re
import time
from typing import List

class SafetyGuard:
    """
    [L0] 사용자 입력 필터링 및 보안 정책 집행 엔진
    """
    def __init__(self, policy: bool, restricted_keywords: List[str]):
        self.enabled = policy
        self.restricted_keywords = restricted_keywords
        self.malicious_pattern = re.compile(r"(system_prompt|api_key|password|db_config)", re.IGNORECASE)

    def check(self, user_input: str) -> bool:
        """
        사용자 입력의 유해성 및 보안 위반 여부를 검사합니다.
        """
        if not self.enabled:
            return True

        # 1. 시스템 내부 변수 접근 시도 차단 (Anti-Leak)
        if self.malicious_pattern.search(user_input):
            return False

        # 2. config.json에 정의된 금지 키워드 검사
        for word in self.restricted_keywords:
            if word in user_input.lower():
                return False

        # 3. SQL Injection 및 명령행 주입 방지 (기초 패턴)
        if any(char in user_input for char in [";", "--", "DROP TABLE"]):
            return False

        return True

class CircuitBreaker:
    """
    [L0] 시스템 과부하 방지 및 지연 시간 관리 (Latency Budget 제어)
    """
    def __init__(self, latency_limit: int):
        self.latency_limit = latency_limit / 1000.0  # ms to seconds
        self.start_time = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if duration > self.latency_limit:
            # IT 기술적으로 'Fail-Closed' 원칙 적용
            print(f"⚠️ Circuit Breaker Triggered: Latency {duration:.2f}s exceeded limit.")
            # 지연 시간이 너무 길면 예외를 발생시켜 시스템 보호 가능
            return False
        return True

def verify_checksum(data: str, signature: str) -> bool:
    """
    [L1] 데이터 무결성 검증 (SHA-256)
    """
    import hashlib
    computed_hash = hashlib.sha256(data.encode()).hexdigest()
    return computed_hash == signature
