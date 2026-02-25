"""
Gemini 모델 자동 전환 체인: Pro → Flash → Flash-lite.

429/ResourceExhausted 에러 감지 시 자동으로 다음 모델로 전환.
일정 시간(1시간) 경과 후 상위 모델로 복귀 시도.

사용법:
    from core.model_fallback import get_model, on_quota_error, generate_with_fallback
"""
import os
import time
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger("LawmadiOS.ModelFallback")

# ─── 모델 체인 (우선순위 순) ───
MODEL_CHAIN = [
    os.getenv("GEMINI_MODEL_1", "gemini-2.5-pro"),
    os.getenv("GEMINI_MODEL_2", "gemini-2.5-flash"),
    os.getenv("GEMINI_MODEL_3", "gemini-2.5-flash-lite"),
]

# ─── 상태 관리 ───
_lock = threading.Lock()
_current_index = 0
_downgrade_time: float = 0
_UPGRADE_INTERVAL = int(os.getenv("MODEL_UPGRADE_INTERVAL", "3600"))  # 기본 1시간


def get_model() -> str:
    """현재 활성 모델명 반환. 다운그레이드 후 일정 시간 경과 시 자동 업그레이드."""
    global _current_index, _downgrade_time
    with _lock:
        if _current_index > 0 and time.time() - _downgrade_time >= _UPGRADE_INTERVAL:
            prev = MODEL_CHAIN[_current_index]
            _current_index = 0
            _downgrade_time = 0
            logger.info(f"[ModelFallback] ⬆️ 상위 모델 복귀: {MODEL_CHAIN[0]} (이전: {prev})")
        return MODEL_CHAIN[_current_index]


def on_quota_error() -> str:
    """429/ResourceExhausted 발생 시 호출 → 다음 모델로 전환. 새 모델명 반환."""
    global _current_index, _downgrade_time
    with _lock:
        if _current_index < len(MODEL_CHAIN) - 1:
            prev = MODEL_CHAIN[_current_index]
            _current_index += 1
            _downgrade_time = time.time()
            new_model = MODEL_CHAIN[_current_index]
            logger.warning(f"[ModelFallback] ⬇️ 모델 전환: {prev} → {new_model} (할당량 초과)")
            return new_model
        return MODEL_CHAIN[_current_index]


def is_quota_error(e: Exception) -> bool:
    """429/ResourceExhausted 에러 여부 판별."""
    err_msg = str(e).lower()
    return any(kw in err_msg for kw in [
        "429", "resource_exhausted", "resourceexhausted",
        "quota", "rate_limit", "rate limit",
    ])


def get_status() -> dict:
    """현재 모델 상태 (health/diagnostics용)."""
    with _lock:
        return {
            "current_model": MODEL_CHAIN[_current_index],
            "model_chain": MODEL_CHAIN,
            "current_tier": _current_index,
            "is_downgraded": _current_index > 0,
            "downgrade_time": _downgrade_time if _downgrade_time else None,
            "upgrade_interval_sec": _UPGRADE_INTERVAL,
        }


def generate_with_fallback(genai_client: Any, contents: Any,
                           config: Any = None, **kwargs) -> Any:
    """generate_content + 자동 모델 전환 래퍼.

    429 에러 발생 시 다음 모델로 전환하여 재시도.
    최대 len(MODEL_CHAIN)회 시도.
    """
    last_error: Optional[Exception] = None
    for attempt in range(len(MODEL_CHAIN)):
        model = get_model()
        try:
            resp = genai_client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
                **kwargs,
            )
            return resp
        except Exception as e:
            last_error = e
            if is_quota_error(e) and attempt < len(MODEL_CHAIN) - 1:
                on_quota_error()
                logger.warning(
                    f"[ModelFallback] Retry #{attempt+2} with {get_model()} "
                    f"(이전 모델 {model} 할당량 초과)"
                )
                continue
            raise
    raise last_error  # 모든 모델 실패
