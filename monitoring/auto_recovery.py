#!/usr/bin/env python3
"""
Lawmadi OS 자동 복구 시스템

경미한 문제 자동 해결, 복구 이력 기록, 실패 시 에스컬레이션.
"""
import os
import time
import logging
import requests
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("LawmadiOS.Monitor.Recovery")


@dataclass
class RecoveryAttempt:
    target: str
    action: str
    success: bool
    message: str
    timestamp: str = ""
    duration_ms: float = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AutoRecovery:
    """경미한 문제 자동 복구"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        recovery_config = config.get("recovery", {})
        self.max_retry = recovery_config.get("max_retry", 3)
        self.retry_delay = recovery_config.get("retry_delay", 10)
        self.auto_restart = recovery_config.get("auto_restart", True)
        self.api_url = config.get("lawmadi_api", os.getenv("LAWMADI_OS_API_URL", "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"))
        self.history: List[RecoveryAttempt] = []

    def attempt_recovery(self, anomalies: List) -> List[RecoveryAttempt]:
        """이상 징후에 대한 자동 복구 시도"""
        attempts = []

        for anomaly in anomalies:
            pattern = anomaly.pattern

            if pattern == "api_timeout":
                attempts.extend(self._recover_api_connection())
            elif pattern in ("drf_failure", "module_down_drf"):
                attempts.extend(self._recover_drf())
            elif pattern == "rate_limit" or pattern == "rate_limit_burst":
                attempts.append(self._handle_rate_limit())
            elif pattern == "high_latency" or pattern == "high_avg_latency":
                attempts.append(self._warmup_instance())

        self.history.extend(attempts)
        return attempts

    def _recover_api_connection(self) -> List[RecoveryAttempt]:
        """API 연결 재시도"""
        attempts = []

        for i in range(1, self.max_retry + 1):
            logger.info(f"🔄 API 재연결 시도 ({i}/{self.max_retry})")
            start = time.time()

            try:
                r = requests.get(f"{self.api_url}/health", timeout=15)
                duration = (time.time() - start) * 1000

                if r.status_code == 200:
                    attempt = RecoveryAttempt(
                        target="FastAPI",
                        action=f"재연결 시도 ({i}/{self.max_retry})",
                        success=True,
                        message=f"연결 복구 성공 ({duration:.0f}ms)",
                        duration_ms=duration,
                    )
                    attempts.append(attempt)
                    logger.info(f"✅ API 연결 복구 성공")
                    return attempts
                else:
                    attempts.append(RecoveryAttempt(
                        target="FastAPI",
                        action=f"재연결 시도 ({i}/{self.max_retry})",
                        success=False,
                        message=f"HTTP {r.status_code}",
                        duration_ms=duration,
                    ))
            except Exception as e:
                duration = (time.time() - start) * 1000
                attempts.append(RecoveryAttempt(
                    target="FastAPI",
                    action=f"재연결 시도 ({i}/{self.max_retry})",
                    success=False,
                    message=str(e)[:100],
                    duration_ms=duration,
                ))

            if i < self.max_retry:
                time.sleep(self.retry_delay)

        return attempts

    def _recover_drf(self) -> List[RecoveryAttempt]:
        """DRF(법제처) API 연결 복구"""
        attempts = []
        drf_oc = os.getenv("LAWGO_DRF_OC", "")

        if not drf_oc:
            attempts.append(RecoveryAttempt(
                target="DRF",
                action="키 확인",
                success=False,
                message="LAWGO_DRF_OC 미설정 — 복구 불가",
            ))
            return attempts

        url = "https://www.law.go.kr/DRF/lawSearch.do"
        params = {"OC": drf_oc, "target": "law", "type": "JSON", "query": "민법"}

        for i in range(1, min(self.max_retry, 2) + 1):
            start = time.time()
            try:
                r = requests.get(url, params=params, timeout=10)
                duration = (time.time() - start) * 1000

                if r.status_code == 200 and "json" in r.headers.get("Content-Type", "").lower():
                    attempts.append(RecoveryAttempt(
                        target="DRF",
                        action=f"재연결 시도 ({i})",
                        success=True,
                        message=f"DRF 연결 복구 ({duration:.0f}ms)",
                        duration_ms=duration,
                    ))
                    return attempts
                else:
                    attempts.append(RecoveryAttempt(
                        target="DRF",
                        action=f"재연결 시도 ({i})",
                        success=False,
                        message=f"HTTP {r.status_code}",
                        duration_ms=duration,
                    ))
            except Exception as e:
                duration = (time.time() - start) * 1000
                attempts.append(RecoveryAttempt(
                    target="DRF",
                    action=f"재연결 시도 ({i})",
                    success=False,
                    message=str(e)[:100],
                    duration_ms=duration,
                ))

            if i < self.max_retry:
                time.sleep(5)

        return attempts

    def _handle_rate_limit(self) -> RecoveryAttempt:
        """Rate limit 대응: 대기 후 재시도"""
        logger.info("⏳ Rate limit 감지 — 60초 대기")
        time.sleep(5)  # 모니터링 중에는 짧은 대기
        return RecoveryAttempt(
            target="Rate Limit",
            action="쿨다운 대기",
            success=True,
            message="5초 대기 완료 (다음 점검 시 재확인)",
        )

    def _warmup_instance(self) -> RecoveryAttempt:
        """Cold start 방지: 워밍업 요청"""
        start = time.time()
        try:
            r = requests.get(f"{self.api_url}/health", timeout=15)
            duration = (time.time() - start) * 1000
            return RecoveryAttempt(
                target="Cloud Run",
                action="인스턴스 워밍업",
                success=r.status_code == 200,
                message=f"워밍업 {'성공' if r.status_code == 200 else '실패'} ({duration:.0f}ms)",
                duration_ms=duration,
            )
        except Exception as e:
            return RecoveryAttempt(
                target="Cloud Run",
                action="인스턴스 워밍업",
                success=False,
                message=str(e)[:100],
            )

    def get_recovery_summary(self) -> Dict[str, Any]:
        """복구 이력 요약"""
        total = len(self.history)
        success = sum(1 for a in self.history if a.success)
        return {
            "total_attempts": total,
            "successful": success,
            "failed": total - success,
            "success_rate": f"{(success/total*100):.0f}%" if total > 0 else "N/A",
            "recent": [
                {
                    "target": a.target,
                    "action": a.action,
                    "success": a.success,
                    "message": a.message,
                    "timestamp": a.timestamp,
                }
                for a in self.history[-5:]
            ],
        }
