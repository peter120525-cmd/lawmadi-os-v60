"""
Gemini model auto-fallback chain for Cloud Functions proxy.

Ported from core/model_fallback.py.
Cloud Functions instance-scoped (state resets on cold start).

Usage:
    from model_fallback import get_model, on_quota_error, is_quota_error
"""
import os
import time
import logging
import threading

logger = logging.getLogger("LawmadiProxy.ModelFallback")

# Model chain (priority order)
MODEL_CHAIN = [
    os.getenv("GEMINI_MODEL_1", "gemini-2.5-flash"),
    os.getenv("GEMINI_MODEL_2", "gemini-2.5-pro"),
    os.getenv("GEMINI_MODEL_3", "gemini-2.5-flash-lite"),
]

_lock = threading.Lock()
_current_index = 0
_downgrade_time: float = 0
_UPGRADE_INTERVAL = int(os.getenv("MODEL_UPGRADE_INTERVAL", "3600"))


def get_model() -> str:
    """Return current active model name. Auto-upgrades after interval."""
    global _current_index, _downgrade_time
    with _lock:
        if _current_index > 0 and time.time() - _downgrade_time >= _UPGRADE_INTERVAL:
            prev = MODEL_CHAIN[_current_index]
            _current_index = 0
            _downgrade_time = 0
            logger.info(f"[ModelFallback] upgrade: {MODEL_CHAIN[0]} (prev: {prev})")
        return MODEL_CHAIN[_current_index]


def on_quota_error() -> str:
    """Switch to next model on 429/ResourceExhausted. Returns new model name."""
    global _current_index, _downgrade_time
    with _lock:
        if _current_index < len(MODEL_CHAIN) - 1:
            prev = MODEL_CHAIN[_current_index]
            _current_index += 1
            _downgrade_time = time.time()
            new_model = MODEL_CHAIN[_current_index]
            logger.warning(f"[ModelFallback] downgrade: {prev} -> {new_model}")
            return new_model
        return MODEL_CHAIN[_current_index]


def is_quota_error(e: Exception) -> bool:
    """Detect 429/ResourceExhausted errors."""
    err_msg = str(e).lower()
    return any(kw in err_msg for kw in [
        "429", "resource_exhausted", "resourceexhausted",
        "quota", "rate_limit", "rate limit",
    ])
