"""
Lawmadi OS v60 — Enhanced Metrics Collector

중앙 집중 메트릭 수집기:
- 응답 시간 백분위 (p50, p95, p99)
- 엔드포인트별 / 리더별 메트릭
- 캐시 적중률
- 에러 분류별 카운트
- 라우팅 방식별 통계
"""
import time
import threading
import logging
from collections import deque, Counter
from typing import Dict, Any, Optional

logger = logging.getLogger("LawmadiOS.Metrics")

# 최근 N건의 요청 지연 시간을 유지 (슬라이딩 윈도우)
_MAX_LATENCY_WINDOW = 500

_lock = threading.Lock()

# ── 글로벌 카운터 ──
_counters: Dict[str, int] = {
    "requests_total": 0,
    "errors_total": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "greeting_requests": 0,
    "non_legal_requests": 0,
    "crisis_requests": 0,
    "blocked_requests": 0,
    "fail_closed_requests": 0,
    "rate_limited_requests": 0,
    "slow_requests": 0,       # > 10s
}

# ── 지연 시간 히스토그램 (전체) ──
_latencies: deque = deque(maxlen=_MAX_LATENCY_WINDOW)

# ── 엔드포인트별 메트릭 ──
_endpoint_metrics: Dict[str, Dict[str, Any]] = {}

# ── 리더별 메트릭 ──
_leader_metrics: Dict[str, Dict[str, Any]] = {}

# ── 라우팅 방식별 카운트 ──
_routing_methods: Counter = Counter()
# keys: "nlu", "keyword", "name", "gemini", "ssot_override", "fallback_cco"

# ── 에러 분류별 카운트 ──
_error_categories: Counter = Counter()
# keys: "gemini_api", "drf_api", "timeout", "rate_limit", "db", "validation", "internal"

# ── 파이프라인 스테이지별 지연 ──
_stage_latencies: Dict[str, deque] = {
    "classify": deque(maxlen=200),
    "rag": deque(maxlen=200),
    "lawmadilm": deque(maxlen=200),
    "gemini": deque(maxlen=200),
    "drf_verify": deque(maxlen=200),
    "total": deque(maxlen=200),
}

# ── Verifier 결과 카운트 ──
_verifier_results: Counter = Counter()
# keys: "PASS", "WARNING", "FAIL", "ERROR", "SKIP"


def _percentile(data: deque, pct: float) -> int:
    """정렬된 deque에서 백분위 값 계산"""
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def _ensure_endpoint(endpoint: str) -> Dict[str, Any]:
    if endpoint not in _endpoint_metrics:
        _endpoint_metrics[endpoint] = {
            "requests": 0,
            "errors": 0,
            "latencies": deque(maxlen=200),
        }
    return _endpoint_metrics[endpoint]


def _ensure_leader(leader: str) -> Dict[str, Any]:
    if leader not in _leader_metrics:
        _leader_metrics[leader] = {
            "requests": 0,
            "errors": 0,
            "latencies": deque(maxlen=100),
        }
    return _leader_metrics[leader]


# ══════════════════════════════════════════
# PUBLIC API — 메트릭 기록
# ══════════════════════════════════════════

def record_request(
    endpoint: str,
    latency_ms: int,
    leader: str = "",
    routing_method: str = "",
    status: str = "SUCCESS",
    is_cache_hit: bool = False,
    error_category: str = "",
    stage_timings: Optional[Dict[str, int]] = None,
    verifier_result: str = "",
):
    """요청 완료 시 메트릭 기록 (thread-safe)"""
    with _lock:
        _counters["requests_total"] += 1
        _latencies.append(latency_ms)

        # 엔드포인트별
        ep = _ensure_endpoint(endpoint)
        ep["requests"] += 1
        ep["latencies"].append(latency_ms)

        # 리더별
        if leader:
            ld = _ensure_leader(leader)
            ld["requests"] += 1
            ld["latencies"].append(latency_ms)

        # 캐시
        if is_cache_hit:
            _counters["cache_hits"] += 1
        else:
            _counters["cache_misses"] += 1

        # 라우팅
        if routing_method:
            _routing_methods[routing_method] += 1

        # 느린 요청
        if latency_ms > 10000:
            _counters["slow_requests"] += 1

        # 에러
        if status == "ERROR":
            _counters["errors_total"] += 1
            ep["errors"] += 1
            if leader:
                _ensure_leader(leader)["errors"] += 1
            if error_category:
                _error_categories[error_category] += 1

        # 스테이지별 지연
        if stage_timings:
            for stage, ms in stage_timings.items():
                if stage in _stage_latencies:
                    _stage_latencies[stage].append(ms)

        # Verifier 결과
        if verifier_result:
            _verifier_results[verifier_result] += 1


def record_event(event_type: str):
    """단순 이벤트 카운터 기록"""
    with _lock:
        if event_type in _counters:
            _counters[event_type] += 1


def record_error(error_category: str):
    """에러 분류별 카운트 기록"""
    with _lock:
        _counters["errors_total"] += 1
        _error_categories[error_category] += 1


# ══════════════════════════════════════════
# PUBLIC API — 메트릭 조회
# ══════════════════════════════════════════

def get_summary() -> Dict[str, Any]:
    """전체 메트릭 요약 반환"""
    with _lock:
        total = _counters["requests_total"]
        hits = _counters["cache_hits"]
        misses = _counters["cache_misses"]
        cache_total = hits + misses

        return {
            "counters": dict(_counters),
            "latency": {
                "p50": _percentile(_latencies, 50),
                "p95": _percentile(_latencies, 95),
                "p99": _percentile(_latencies, 99),
                "samples": len(_latencies),
            },
            "cache": {
                "hits": hits,
                "misses": misses,
                "hit_rate": round(hits / cache_total * 100, 1) if cache_total > 0 else 0,
            },
            "routing_methods": dict(_routing_methods),
            "error_categories": dict(_error_categories),
            "verifier_results": dict(_verifier_results),
            "stage_latencies": {
                stage: {
                    "p50": _percentile(d, 50),
                    "p95": _percentile(d, 95),
                    "samples": len(d),
                }
                for stage, d in _stage_latencies.items()
            },
        }


def get_endpoint_metrics() -> Dict[str, Any]:
    """엔드포인트별 메트릭 반환"""
    with _lock:
        result = {}
        for ep, data in _endpoint_metrics.items():
            result[ep] = {
                "requests": data["requests"],
                "errors": data["errors"],
                "error_rate": round(data["errors"] / max(data["requests"], 1) * 100, 1),
                "latency_p50": _percentile(data["latencies"], 50),
                "latency_p95": _percentile(data["latencies"], 95),
                "latency_p99": _percentile(data["latencies"], 99),
            }
        return result


def get_leader_metrics() -> Dict[str, Any]:
    """리더별 메트릭 반환"""
    with _lock:
        result = {}
        for ld, data in _leader_metrics.items():
            result[ld] = {
                "requests": data["requests"],
                "errors": data["errors"],
                "latency_p50": _percentile(data["latencies"], 50),
                "latency_p95": _percentile(data["latencies"], 95),
            }
        # 요청 수 내림차순 정렬
        return dict(sorted(result.items(), key=lambda x: x[1]["requests"], reverse=True))
