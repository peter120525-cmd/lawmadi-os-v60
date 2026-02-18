#!/usr/bin/env python3
"""
Lawmadi OS 로그 분석 엔진

실시간 에러 로그 파싱, 패턴 기반 이상 징후 탐지, 통계 생성.
"""
import re
import logging
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger("LawmadiOS.Monitor.LogAnalyzer")


@dataclass
class LogAnomaly:
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    pattern: str
    count: int
    message: str
    first_seen: str = ""
    last_seen: str = ""
    sample: str = ""


class LogAnalyzer:
    """Cloud Run 로그 및 /health 메트릭 기반 이상 탐지"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config.get("alert_threshold", {})
        self.error_history: List[Dict] = []
        self.anomaly_patterns = {
            "model_deprecated": {
                "pattern": r"no longer available|model.*deprecated|404.*model",
                "severity": "CRITICAL",
                "message": "Gemini 모델 폐기/미지원 감지",
            },
            "api_timeout": {
                "pattern": r"TIMEOUT|timeout|TimeoutError|ReadTimeout",
                "severity": "HIGH",
                "message": "API 타임아웃 발생",
            },
            "rate_limit": {
                "pattern": r"429|Rate.?Limit|Too Many Requests",
                "severity": "MEDIUM",
                "message": "Rate limit 초과",
            },
            "auth_failure": {
                "pattern": r"401|403|Unauthorized|Forbidden|AUTH",
                "severity": "HIGH",
                "message": "인증/권한 실패",
            },
            "drf_failure": {
                "pattern": r"DRF.*fail|법제처.*실패|SSOT.*비가용",
                "severity": "HIGH",
                "message": "DRF(법제처) API 연결 실패",
            },
            "oom": {
                "pattern": r"MemoryError|OOM|out.?of.?memory",
                "severity": "CRITICAL",
                "message": "메모리 부족 (OOM)",
            },
        }

    def analyze_health_metrics(self, health_data: Dict) -> List[LogAnomaly]:
        """헬스체크 메트릭에서 이상 탐지"""
        anomalies = []
        metrics = health_data.get("diagnostics", {}).get("metrics", {})

        # 에러율 분석
        total_reqs = metrics.get("requests", 0)
        total_errs = metrics.get("errors", 0)
        error_rate_threshold = self.thresholds.get("error_rate_percent", 5.0)

        if total_reqs > 0:
            error_rate = (total_errs / total_reqs) * 100
            if error_rate > error_rate_threshold:
                anomalies.append(LogAnomaly(
                    severity="HIGH",
                    pattern="error_rate",
                    count=total_errs,
                    message=f"에러율 {error_rate:.1f}% > 임계값 {error_rate_threshold}% (요청 {total_reqs}건 중 {total_errs}건 실패)",
                ))

        # 평균 레이턴시 분석
        avg_latency = metrics.get("avg_latency_ms", 0)
        latency_threshold = self.thresholds.get("api_response_time", 3.0) * 1000
        if avg_latency > latency_threshold:
            anomalies.append(LogAnomaly(
                severity="MEDIUM",
                pattern="high_latency",
                count=1,
                message=f"평균 응답시간 {avg_latency:.0f}ms > 임계값 {latency_threshold:.0f}ms",
            ))

        # 모듈 상태 분석
        modules = health_data.get("diagnostics", {}).get("modules", {})
        critical_modules = ["drf", "gemini_key", "swarm_orchestrator"]
        for mod in critical_modules:
            if not modules.get(mod, False):
                anomalies.append(LogAnomaly(
                    severity="CRITICAL" if mod == "gemini_key" else "HIGH",
                    pattern=f"module_down_{mod}",
                    count=1,
                    message=f"핵심 모듈 비활성: {mod}",
                ))

        return anomalies

    def analyze_text_log(self, log_text: str) -> List[LogAnomaly]:
        """텍스트 로그에서 패턴 기반 이상 탐지"""
        anomalies = []

        for name, pattern_config in self.anomaly_patterns.items():
            regex = pattern_config["pattern"]
            matches = re.findall(regex, log_text, re.IGNORECASE)
            if matches:
                anomalies.append(LogAnomaly(
                    severity=pattern_config["severity"],
                    pattern=name,
                    count=len(matches),
                    message=pattern_config["message"],
                    sample=matches[0][:100] if matches else "",
                ))

        return anomalies

    def analyze_simulation_results(self, results: List[Dict]) -> List[LogAnomaly]:
        """시뮬레이션 결과에서 이상 탐지"""
        anomalies = []

        total = len(results)
        if total == 0:
            return anomalies

        fails = [r for r in results if not r.get("pass", True)]
        fail_rate = len(fails) / total * 100

        if fail_rate > 20:
            anomalies.append(LogAnomaly(
                severity="CRITICAL",
                pattern="simulation_fail_rate",
                count=len(fails),
                message=f"시뮬레이션 실패율 {fail_rate:.0f}% ({len(fails)}/{total}건)",
            ))
        elif fail_rate > 0:
            anomalies.append(LogAnomaly(
                severity="MEDIUM",
                pattern="simulation_fail_rate",
                count=len(fails),
                message=f"시뮬레이션 일부 실패 {fail_rate:.0f}% ({len(fails)}/{total}건)",
            ))

        # HTTP 429 집중 발생 체크
        rate_limited = [r for r in fails if r.get("status_code") == 429]
        if len(rate_limited) > 3:
            anomalies.append(LogAnomaly(
                severity="HIGH",
                pattern="rate_limit_burst",
                count=len(rate_limited),
                message=f"Rate limit 집중 발생 ({len(rate_limited)}건)",
            ))

        # 평균 레이턴시
        latencies = [r.get("latency", 0) for r in results if r.get("latency", 0) > 0]
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            if avg_lat > 10:
                anomalies.append(LogAnomaly(
                    severity="HIGH",
                    pattern="high_avg_latency",
                    count=1,
                    message=f"시뮬레이션 평균 응답 {avg_lat:.1f}초 (임계값 10초)",
                ))

        return anomalies

    def get_summary(self, anomalies: List[LogAnomaly]) -> Dict[str, Any]:
        """이상 탐지 결과 요약"""
        severity_counts = Counter(a.severity for a in anomalies)
        return {
            "total_anomalies": len(anomalies),
            "critical": severity_counts.get("CRITICAL", 0),
            "high": severity_counts.get("HIGH", 0),
            "medium": severity_counts.get("MEDIUM", 0),
            "low": severity_counts.get("LOW", 0),
            "overall_status": (
                "CRITICAL" if severity_counts.get("CRITICAL", 0) > 0
                else "HIGH" if severity_counts.get("HIGH", 0) > 0
                else "MEDIUM" if severity_counts.get("MEDIUM", 0) > 0
                else "OK"
            ),
        }
