#!/usr/bin/env python3
"""
Lawmadi OS 모니터링 오케스트레이터

모든 모니터링 컴포넌트 통합 실행.
- 정기 점검 루프
- 시뮬레이션 포함 심층 점검
- 결과 저장 및 알림
"""
import os
import sys
import json
import time
import signal
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from monitoring.health_monitor import HealthMonitor
from monitoring.log_analyzer import LogAnalyzer
from monitoring.alert_system import AlertSystem
from monitoring.auto_recovery import AutoRecovery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LawmadiOS.Monitor")


def load_config(config_path: str = None) -> Dict[str, Any]:
    """설정 파일 로드"""
    if config_path is None:
        config_path = os.path.join(PROJECT_ROOT, "monitoring", "monitoring_config.json")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"설정 파일 미발견: {config_path}, 기본값 사용")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """기본 설정"""
    return {
        "lawmadi_api": os.getenv("LAWMADI_OS_API_URL", "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"),
        "interval_seconds": 300,
        "timeout_seconds": 10,
        "alert_threshold": {
            "api_response_time": 3.0,
            "error_rate_percent": 5.0,
            "memory_usage_percent": 85.0,
            "cpu_usage_percent": 90.0,
        },
        "alerts": {
            "slack_webhook": "",
            "discord_webhook": "",
            "log_dir": "monitoring/logs",
        },
        "recovery": {
            "auto_restart": True,
            "max_retry": 3,
            "retry_delay": 10,
        },
        "simulation": {
            "enabled": True,
            "count": 5,
            "delay_between": 5.0,
            "scenarios": [
                {"query": "부당해고 구제 방법", "category": "labor"},
                {"query": "전세 보증금 반환", "category": "lease"},
                {"query": "서연아 전세 분쟁 전략 알려줘", "category": "clevel"},
                {"query": "사기죄 고소장 작성 방법", "category": "criminal"},
                {"query": "양도소득세 비과세 요건", "category": "tax"},
            ],
        },
    }


class MonitorOrchestrator:
    """전체 모니터링 오케스트레이션"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.health = HealthMonitor(config)
        self.analyzer = LogAnalyzer(config)
        self.alert = AlertSystem(config)
        self.recovery = AutoRecovery(config)
        self.running = True
        self.run_count = 0

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        """Graceful shutdown"""
        logger.info("🛑 모니터링 종료 신호 수신")
        self.running = False

    def run_check(self, include_simulation: bool = False) -> Dict[str, Any]:
        """단일 점검 실행"""
        self.run_count += 1
        start = time.time()
        logger.info(f"{'=' * 50}")
        logger.info(f"🔍 점검 #{self.run_count} 시작 ({datetime.now().strftime('%H:%M:%S')})")

        result = {
            "check_number": self.run_count,
            "timestamp": datetime.now().isoformat(),
            "health": [],
            "anomalies": [],
            "recovery": [],
            "simulation": None,
        }

        # 1. 헬스체크
        logger.info("[1/4] 헬스체크 실행...")
        health_results = self.health.check_all()
        result["health"] = [
            {"component": h.component, "status": h.status, "latency_ms": h.latency_ms, "message": h.message}
            for h in health_results
        ]

        for h in health_results:
            icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(h.status, "❓")
            lat = f" ({h.latency_ms:.0f}ms)" if h.latency_ms > 0 else ""
            logger.info(f"  {icon} {h.component}: {h.message}{lat}")

        # 2. 이상 탐지 (health 메트릭 기반)
        logger.info("[2/4] 이상 탐지...")
        all_anomalies = []

        # /health 응답에서 메트릭 분석
        try:
            r = requests.get(f"{self.config['lawmadi_api']}/health", timeout=10)
            if r.status_code == 200:
                health_anomalies = self.analyzer.analyze_health_metrics(r.json())
                all_anomalies.extend(health_anomalies)
        except Exception:
            pass

        # FAIL 상태 컴포넌트 → 이상 등록
        for h in health_results:
            if h.status == "FAIL":
                from monitoring.log_analyzer import LogAnomaly
                all_anomalies.append(LogAnomaly(
                    severity="CRITICAL" if h.component in ("FastAPI", "Gemini API") else "HIGH",
                    pattern=f"component_fail_{h.component.lower().replace(' ', '_')}",
                    count=1,
                    message=f"{h.component} 장애: {h.message}",
                ))

        # 3. 시뮬레이션 (포함 시)
        if include_simulation:
            logger.info("[3/4] 시뮬레이션 실행...")
            sim_results = self._run_simulation()
            result["simulation"] = sim_results

            sim_anomalies = self.analyzer.analyze_simulation_results(sim_results.get("results", []))
            all_anomalies.extend(sim_anomalies)

            sim_pass = sim_results.get("pass_count", 0)
            sim_total = sim_results.get("total", 0)
            logger.info(f"  시뮬레이션: {sim_pass}/{sim_total} 성공")
        else:
            logger.info("[3/4] 시뮬레이션 스킵 (빠른 점검)")

        result["anomalies"] = [
            {"severity": a.severity, "pattern": a.pattern, "count": a.count, "message": a.message}
            for a in all_anomalies
        ]

        # 4. 자동 복구 (이상 발견 시)
        if all_anomalies:
            logger.info(f"[4/4] 자동 복구 시도 ({len(all_anomalies)}건 이상 감지)...")
            recovery_attempts = self.recovery.attempt_recovery(all_anomalies)
            result["recovery"] = [
                {"target": a.target, "action": a.action, "success": a.success, "message": a.message}
                for a in recovery_attempts
            ]

            for a in recovery_attempts:
                icon = "✅" if a.success else "❌"
                logger.info(f"  {icon} [{a.target}] {a.action}: {a.message}")

            # 알림 발송
            alert_msg = self.alert.generate_alert(all_anomalies, health_results)
            if alert_msg:
                self.alert.send_alert(alert_msg, all_anomalies)
        else:
            logger.info("[4/4] 이상 없음 — 복구/알림 스킵")

        duration = (time.time() - start) * 1000
        summary = self.analyzer.get_summary(all_anomalies)
        result["duration_ms"] = round(duration, 1)
        result["overall_status"] = summary["overall_status"]

        status_icon = {"OK": "✅", "MEDIUM": "🟡", "HIGH": "⚠️", "CRITICAL": "🚨"}.get(summary["overall_status"], "❓")
        logger.info(f"{status_icon} 점검 #{self.run_count} 완료: {summary['overall_status']} ({duration:.0f}ms)")
        logger.info(f"{'=' * 50}")

        return result

    def _run_simulation(self) -> Dict[str, Any]:
        """시뮬레이션 실행"""
        sim_config = self.config.get("simulation", {})
        scenarios = sim_config.get("scenarios", [])
        delay = sim_config.get("delay_between", 5.0)
        api_url = f"{self.config['lawmadi_api']}/ask"

        results = []
        pass_count = 0

        for i, scenario in enumerate(scenarios):
            query = scenario["query"]
            start = time.time()
            try:
                r = requests.post(api_url, json={"query": query}, timeout=60)
                latency = time.time() - start
                status_code = r.status_code

                if status_code == 200:
                    data = r.json()
                    resp_len = len(data.get("response", ""))
                    leader = data.get("leader", "?")
                    api_status = data.get("status", "")
                    passed = api_status == "SUCCESS" and resp_len >= 50
                else:
                    data = {}
                    resp_len = 0
                    leader = "N/A"
                    passed = False

            except Exception as e:
                latency = time.time() - start
                status_code = 0
                resp_len = 0
                leader = "N/A"
                passed = False

            if passed:
                pass_count += 1

            icon = "✅" if passed else "❌"
            logger.info(f"  {icon} #{i+1} [{scenario['category']}] 리더:{leader} {latency:.1f}s {resp_len}자")

            results.append({
                "id": i + 1,
                "query": query[:50],
                "category": scenario["category"],
                "status_code": status_code,
                "latency": round(latency, 1),
                "response_length": resp_len,
                "leader": leader,
                "pass": passed,
            })

            if i < len(scenarios) - 1:
                time.sleep(delay)

        return {
            "total": len(scenarios),
            "pass_count": pass_count,
            "fail_count": len(scenarios) - pass_count,
            "results": results,
        }

    def run_loop(self):
        """정기 점검 루프"""
        interval = self.config.get("interval_seconds", 300)
        logger.info(f"🚀 Lawmadi OS 모니터링 시작 (간격: {interval}초)")

        check_count = 0
        while self.running:
            check_count += 1
            # 매 3번째 점검에 시뮬레이션 포함
            include_sim = (check_count % 3 == 1)
            self.run_check(include_simulation=include_sim)

            if self.running:
                logger.info(f"⏳ 다음 점검까지 {interval}초 대기...")
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)

        logger.info("🛑 모니터링 종료")


def main():
    """메인 실행"""
    import argparse

    parser = argparse.ArgumentParser(description="Lawmadi OS 모니터링 시스템")
    parser.add_argument("--once", action="store_true", help="1회 점검 후 종료")
    parser.add_argument("--sim", action="store_true", help="시뮬레이션 포함")
    parser.add_argument("--config", type=str, help="설정 파일 경로")
    parser.add_argument("--interval", type=int, help="점검 간격 (초)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.interval:
        config["interval_seconds"] = args.interval

    orchestrator = MonitorOrchestrator(config)

    if args.once:
        result = orchestrator.run_check(include_simulation=args.sim)
        # 결과 JSON 저장
        output_path = os.path.join(PROJECT_ROOT, "monitoring", "logs", "last_check.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"결과 저장: {output_path}")

        sys.exit(0 if result["overall_status"] == "OK" else 1)
    else:
        orchestrator.run_loop()


if __name__ == "__main__":
    main()
