#!/usr/bin/env python3
"""
Lawmadi OS Actionable Alert 생성기

이상 징후별 구체적인 조치 방안 자동 생성 + 다중 채널 알림.
"""
import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("LawmadiOS.Monitor.Alert")


# 이상 패턴별 자동 조치 방안 매핑
ACTION_PLANS = {
    "model_deprecated": {
        "title": "Gemini 모델 폐기/미지원",
        "actions": [
            "1. DEFAULT_GEMINI_MODEL 상수 확인: main.py line 101",
            "2. Google AI Studio에서 최신 모델 확인: https://ai.google.dev/gemini-api/docs/models",
            "3. 모델명 업데이트 후 배포: git push → GitHub Actions 자동 배포",
            "4. 임시 조치: GEMINI_MODEL 환경변수를 Cloud Run에서 직접 변경",
        ],
    },
    "api_timeout": {
        "title": "API 타임아웃",
        "actions": [
            "1. Cloud Run 콘솔에서 인스턴스 상태 확인",
            "2. Gemini API 상태 확인: https://status.cloud.google.com",
            "3. DRF_TIMEOUT_MS 환경변수 증가 고려 (현재 5000ms)",
            "4. Cloud Run timeout 설정 확인 (현재 300s)",
        ],
    },
    "rate_limit": {
        "title": "Rate Limit 초과",
        "actions": [
            "1. 현재 설정: 15회/분 (/ask 엔드포인트)",
            "2. 정상적인 트래픽 급증인지 확인",
            "3. 필요시 main.py @limiter.limit 값 조정",
            "4. Cloud Run max-instances 증가 고려 (현재 10)",
        ],
    },
    "auth_failure": {
        "title": "인증/권한 실패",
        "actions": [
            "1. GCP Secret Manager에서 API 키 만료 확인",
            "2. GEMINI_KEY, ANTHROPIC_API_KEY 유효성 검증",
            "3. MCP_API_KEY Bearer 토큰 확인",
            "4. Cloud Run IAM 권한 확인",
        ],
    },
    "drf_failure": {
        "title": "DRF(법제처) API 연결 실패",
        "actions": [
            "1. 법제처 API 상태 확인: https://www.law.go.kr",
            "2. LAWGO_DRF_OC 키 유효성 확인",
            "3. DRF SSOT는 Fail-Soft로 동작 → 서비스 중단 없음",
            "4. data.go.kr 백업 API 활성화 여부 확인",
        ],
    },
    "oom": {
        "title": "메모리 부족 (OOM)",
        "actions": [
            "1. Cloud Run 메모리 설정 확인 (현재 2Gi)",
            "2. 메모리 누수 원인 조사: 캐시 크기, 대화 히스토리",
            "3. Cloud Run 메모리 증가: --memory 4Gi",
            "4. 인스턴스 재시작: gcloud run services update --no-traffic 후 복구",
        ],
    },
    "error_rate": {
        "title": "높은 에러율",
        "actions": [
            "1. Cloud Run 로그 확인: gcloud logging read",
            "2. 최근 배포 변경 사항 확인",
            "3. 에러 패턴 분석 (Gemini 모델 이슈 vs DRF 이슈)",
            "4. 필요시 이전 버전으로 롤백",
        ],
    },
    "simulation_fail_rate": {
        "title": "시뮬레이션 실패율 높음",
        "actions": [
            "1. 실패한 시나리오 카테고리 확인",
            "2. Rate limit 관련 실패인지 확인 (429)",
            "3. Gemini 모델 응답 품질 저하 여부 확인",
            "4. Swarm Orchestrator 리더 라우팅 검증",
        ],
    },
    "module_down_gemini_key": {
        "title": "Gemini API Key 미설정",
        "actions": [
            "1. GCP Secret Manager에서 GEMINI_KEY 확인",
            "2. deploy.yml --set-secrets 설정 확인",
            "3. 수동 설정: gcloud run services update --set-secrets",
        ],
    },
    "module_down_drf": {
        "title": "DRF 커넥터 미로드",
        "actions": [
            "1. LAWGO_DRF_OC 환경변수 확인",
            "2. DRF API 엔드포인트 가용성 확인",
            "3. Fail-Soft: 서비스는 계속 동작, SSOT 기능만 제한",
        ],
    },
    "module_down_swarm_orchestrator": {
        "title": "Swarm Orchestrator 미로드",
        "actions": [
            "1. leaders.json 파일 무결성 확인",
            "2. SwarmOrchestrator 초기화 로그 확인",
            "3. Fallback: 단일 리더 모드로 동작 중",
        ],
    },
}


class AlertSystem:
    """다중 채널 알림 + 조치 방안 생성"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        alerts_config = config.get("alerts", {})
        self.slack_webhook = alerts_config.get("slack_webhook", "")
        self.discord_webhook = alerts_config.get("discord_webhook", "")
        self.log_dir = alerts_config.get("log_dir", "monitoring/logs")
        os.makedirs(self.log_dir, exist_ok=True)

    def generate_alert(self, anomalies: List, health_results: List = None) -> str:
        """이상 징후에 대한 구조화된 알림 메시지 생성"""
        if not anomalies:
            return ""

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")
        max_severity = "OK"
        for a in anomalies:
            if a.severity == "CRITICAL":
                max_severity = "CRITICAL"
                break
            elif a.severity == "HIGH" and max_severity != "CRITICAL":
                max_severity = "HIGH"
            elif a.severity == "MEDIUM" and max_severity not in ("CRITICAL", "HIGH"):
                max_severity = "MEDIUM"

        icon = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🟡", "OK": "✅"}.get(max_severity, "📋")

        lines = [
            f"{icon} [{max_severity}] Lawmadi OS Alert",
            "━" * 40,
            f"시간: {now}",
        ]

        for a in anomalies:
            sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(a.severity, "⚪")
            lines.append(f"\n{sev_icon} [{a.severity}] {a.message}")
            if a.count > 1:
                lines.append(f"   발생: {a.count}회")

            # 조치 방안
            plan = ACTION_PLANS.get(a.pattern, {})
            if plan:
                lines.append(f"\n📋 조치사항 ({plan['title']}):")
                for action in plan.get("actions", []):
                    lines.append(f"   {action}")

        # 시스템 상태 요약
        if health_results:
            lines.append(f"\n{'━' * 40}")
            lines.append("📊 현재 시스템 상태:")
            for hr in health_results:
                status_icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(hr.status, "❓")
                latency_str = f" ({hr.latency_ms:.0f}ms)" if hr.latency_ms > 0 else ""
                lines.append(f"   {status_icon} {hr.component}: {hr.message}{latency_str}")

        lines.append(f"{'━' * 40}")
        return "\n".join(lines)

    def send_alert(self, message: str, anomalies: List = None) -> Dict[str, bool]:
        """다중 채널로 알림 전송"""
        results = {}

        # 1. 로컬 파일 로그 (항상)
        results["file"] = self._write_log_file(message)

        # 2. Slack
        if self.slack_webhook:
            results["slack"] = self._send_slack(message)

        # 3. Discord
        if self.discord_webhook:
            results["discord"] = self._send_discord(message)

        # 4. 콘솔 출력
        print(message)

        return results

    def _write_log_file(self, message: str) -> bool:
        """로그 파일 저장"""
        try:
            filename = datetime.now().strftime("alert_%Y%m%d.log")
            filepath = os.path.join(self.log_dir, filename)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(message)
                f.write(f"\n{'=' * 50}\n")
            return True
        except Exception as e:
            logger.error(f"로그 파일 저장 실패: {e}")
            return False

    def _send_slack(self, message: str) -> bool:
        """Slack Webhook 전송"""
        try:
            payload = {"text": f"```\n{message}\n```"}
            r = requests.post(self.slack_webhook, json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Slack 알림 실패: {e}")
            return False

    def _send_discord(self, message: str) -> bool:
        """Discord Webhook 전송"""
        try:
            # Discord은 2000자 제한
            truncated = message[:1900] if len(message) > 1900 else message
            payload = {"content": f"```\n{truncated}\n```"}
            r = requests.post(self.discord_webhook, json=payload, timeout=10)
            return r.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Discord 알림 실패: {e}")
            return False
