"""
Gemini 모델 자동 전환 체인: 2.5-Flash → 2.5-Flash-lite + 429 재시도.

429/ResourceExhausted 에러 감지 시 지수 백오프로 재시도.

사용법:
    from core.model_fallback import get_model, on_quota_error, generate_with_fallback
"""
import asyncio
import os
import time
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger("LawmadiOS.ModelFallback")

# ─── 모델 체인 (리전에서 사용 가능한 모델만) ───
MODEL_CHAIN = [
    os.getenv("GEMINI_MODEL_1", "gemini-2.5-flash"),
    os.getenv("GEMINI_MODEL_2", "gemini-2.5-flash-lite"),
]

# ─── 상태 관리 ───
_lock = threading.Lock()
_current_index = 0
_downgrade_time: float = 0
_UPGRADE_INTERVAL = int(os.getenv("MODEL_UPGRADE_INTERVAL", "3600"))  # 기본 1시간
_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
_RETRY_BASE_SEC = float(os.getenv("GEMINI_RETRY_BASE_SEC", "2.0"))


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


def is_model_unavailable(e: Exception) -> bool:
    """404/모델 미지원 에러 여부 판별 (리전 미배포 등)."""
    err_msg = str(e).lower()
    return any(kw in err_msg for kw in [
        "404", "not_found", "not found",
        "was not found", "does not have access",
        "model is not available", "model_not_found",
    ])


def is_retryable_model_error(e: Exception) -> bool:
    """할당량 초과 OR 모델 미지원 → 다음 모델로 전환해야 하는 에러."""
    return is_quota_error(e) or is_model_unavailable(e)


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
    """generate_content + 429 지수 백오프 재시도 래퍼.

    429 에러 발생 시 지수 백오프(2, 4, 8초)로 재시도.
    최대 _MAX_RETRIES회 재시도.
    """
    model = get_model()
    last_error: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
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
            if is_quota_error(e) and attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SEC * (2 ** attempt)
                logger.warning(
                    f"[ModelFallback] 429 재시도 #{attempt+1}/{_MAX_RETRIES} "
                    f"({wait:.1f}초 대기, model={model})"
                )
                time.sleep(wait)
                continue
            if is_model_unavailable(e):
                on_quota_error()
            raise
    raise last_error


async def generate_with_fallback_async(genai_client: Any, contents: Any,
                                       config: Any = None, **kwargs) -> Any:
    """비동기 generate_content + 429 지수 백오프 재시도 래퍼.

    sync SDK 호출을 asyncio.to_thread()로 감싸 이벤트 루프 블로킹 방지.
    """
    model = get_model()
    last_error: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = await asyncio.to_thread(
                genai_client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
                **kwargs,
            )
            return resp
        except Exception as e:
            last_error = e
            if is_quota_error(e) and attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SEC * (2 ** attempt)
                logger.warning(
                    f"[ModelFallback] 429 async 재시도 #{attempt+1}/{_MAX_RETRIES} "
                    f"({wait:.1f}초 대기, model={model})"
                )
                await asyncio.sleep(wait)
                continue
            if is_model_unavailable(e):
                on_quota_error()
            raise
    raise last_error
