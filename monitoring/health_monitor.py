#!/usr/bin/env python3
"""
Lawmadi OS 실시간 헬스체크 시스템

FastAPI, Gemini API, DRF(법제처), DB, Swarm Leader 상태를 포괄 점검.
"""
import os
import time
import logging
import psutil
import requests
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("LawmadiOS.Monitor.Health")


@dataclass
class HealthResult:
    component: str
    status: str  # "OK", "WARN", "FAIL"
    latency_ms: float = 0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """Lawmadi OS 전체 컴포넌트 헬스체크"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_url = config.get("lawmadi_api", os.getenv("LAWMADI_OS_API_URL", "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"))
        self.drf_oc = os.getenv("LAWGO_DRF_OC", "")
        self.thresholds = config.get("alert_threshold", {})
        self.timeout = config.get("timeout_seconds", 10)

    def check_all(self) -> List[HealthResult]:
        """모든 컴포넌트 점검 실행"""
        results = []
        results.append(self.check_fastapi())
        results.append(self.check_gemini())
        results.append(self.check_drf())
        results.append(self.check_system_resources())
        results.append(self.check_swarm_leaders())
        return results

    def check_fastapi(self) -> HealthResult:
        """FastAPI 서버 상태 확인"""
        url = f"{self.api_url}/health"
        try:
            start = time.time()
            r = requests.get(url, timeout=self.timeout)
            latency = (time.time() - start) * 1000

            if r.status_code == 200:
                data = r.json()
                modules = data.get("diagnostics", {}).get("modules", {})
                metrics = data.get("diagnostics", {}).get("metrics", {})
                return HealthResult(
                    component="FastAPI",
                    status="OK",
                    latency_ms=round(latency, 1),
                    message=f"v{data.get('os_version', '?')} online",
                    details={
                        "modules": modules,
                        "requests": metrics.get("requests", 0),
                        "errors": metrics.get("errors", 0),
                        "avg_latency_ms": metrics.get("avg_latency_ms", 0),
                    }
                )
            else:
                return HealthResult("FastAPI", "FAIL", round(latency, 1), f"HTTP {r.status_code}")
        except requests.Timeout:
            return HealthResult("FastAPI", "FAIL", 0, f"TIMEOUT ({self.timeout}s)")
        except Exception as e:
            return HealthResult("FastAPI", "FAIL", 0, str(e))

    def check_gemini(self) -> HealthResult:
        """Gemini API 연결 상태 (FastAPI /health에서 확인)"""
        url = f"{self.api_url}/health"
        try:
            r = requests.get(url, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                modules = data.get("diagnostics", {}).get("modules", {})
                gemini_ok = modules.get("gemini_key", False)
                return HealthResult(
                    component="Gemini API",
                    status="OK" if gemini_ok else "FAIL",
                    message="API Key 설정됨" if gemini_ok else "API Key 미설정",
                    details={"gemini_key": gemini_ok}
                )
            return HealthResult("Gemini API", "WARN", 0, f"Health 엔드포인트 HTTP {r.status_code}")
        except Exception as e:
            return HealthResult("Gemini API", "FAIL", 0, str(e))

    def check_drf(self) -> HealthResult:
        """DRF(법제처) API 연결 상태"""
        if not self.drf_oc:
            return HealthResult("DRF(법제처)", "WARN", 0, "LAWGO_DRF_OC 미설정 (로컬 환경)")

        url = "https://www.law.go.kr/DRF/lawSearch.do"
        params = {"OC": self.drf_oc, "target": "law", "type": "JSON", "query": "민법"}
        try:
            start = time.time()
            r = requests.get(url, params=params, timeout=8)
            latency = (time.time() - start) * 1000

            ct = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "json" in ct.lower():
                data = r.json()
                return HealthResult(
                    component="DRF(법제처)",
                    status="OK",
                    latency_ms=round(latency, 1),
                    message="법령 검색 정상",
                    details={"total_cnt": str(data.get("LawSearch", {}).get("totalCnt", "?"))}
                )
            else:
                return HealthResult("DRF(법제처)", "FAIL", round(latency, 1),
                                    f"HTTP {r.status_code}, CT={ct[:30]}")
        except requests.Timeout:
            return HealthResult("DRF(법제처)", "FAIL", 0, "TIMEOUT (8s)")
        except Exception as e:
            return HealthResult("DRF(법제처)", "FAIL", 0, str(e))

    def check_system_resources(self) -> HealthResult:
        """시스템 리소스 (CPU, 메모리)"""
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)

        mem_threshold = self.thresholds.get("memory_usage_percent", 85.0)
        cpu_threshold = self.thresholds.get("cpu_usage_percent", 90.0)

        issues = []
        if mem.percent > mem_threshold:
            issues.append(f"메모리 {mem.percent}% > {mem_threshold}%")
        if cpu > cpu_threshold:
            issues.append(f"CPU {cpu}% > {cpu_threshold}%")

        status = "FAIL" if issues else ("WARN" if mem.percent > 70 or cpu > 70 else "OK")

        return HealthResult(
            component="시스템 리소스",
            status=status,
            message="; ".join(issues) if issues else "정상",
            details={
                "memory_percent": mem.percent,
                "memory_used_gb": round(mem.used / (1024**3), 1),
                "memory_total_gb": round(mem.total / (1024**3), 1),
                "cpu_percent": cpu,
            }
        )

    def check_swarm_leaders(self) -> HealthResult:
        """Swarm Leader 로딩 상태 (FastAPI /health에서 확인)"""
        url = f"{self.api_url}/health"
        try:
            r = requests.get(url, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                modules = data.get("diagnostics", {}).get("modules", {})
                swarm_ok = modules.get("swarm_orchestrator", False)
                return HealthResult(
                    component="Swarm Leaders",
                    status="OK" if swarm_ok else "WARN",
                    message="60명 리더 로드됨" if swarm_ok else "SwarmOrchestrator 미로드",
                    details={"swarm_orchestrator": swarm_ok, "swarm": modules.get("swarm", False)}
                )
            return HealthResult("Swarm Leaders", "WARN", 0, f"HTTP {r.status_code}")
        except Exception as e:
            return HealthResult("Swarm Leaders", "FAIL", 0, str(e))

    def check_ask_endpoint(self, query: str = "민법 제750조") -> HealthResult:
        """/ask 엔드포인트 실제 응답 테스트"""
        url = f"{self.api_url}/ask"
        try:
            start = time.time()
            r = requests.post(url, json={"query": query}, timeout=60)
            latency = (time.time() - start) * 1000

            if r.status_code == 200:
                data = r.json()
                resp_len = len(data.get("response", ""))
                api_status = data.get("status", "")
                leader = data.get("leader", "?")

                threshold = self.thresholds.get("api_response_time", 3.0) * 1000
                slow = latency > threshold

                return HealthResult(
                    component="/ask 엔드포인트",
                    status="WARN" if slow else "OK",
                    latency_ms=round(latency, 1),
                    message=f"리더: {leader}, {resp_len}자" + (f" (느림: {latency:.0f}ms)" if slow else ""),
                    details={"leader": leader, "response_length": resp_len, "api_status": api_status}
                )
            elif r.status_code == 429:
                return HealthResult("/ask 엔드포인트", "WARN", 0, "Rate limited (429)")
            else:
                return HealthResult("/ask 엔드포인트", "FAIL", 0, f"HTTP {r.status_code}")
        except requests.Timeout:
            return HealthResult("/ask 엔드포인트", "FAIL", 0, "TIMEOUT (60s)")
        except Exception as e:
            return HealthResult("/ask 엔드포인트", "FAIL", 0, str(e))
