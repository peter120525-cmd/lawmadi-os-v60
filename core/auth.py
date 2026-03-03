"""
Lawmadi OS v60 — 공통 인증 헬퍼

Bearer 토큰 파싱, API 키 검증, JWT RBAC를 안전하게 수행.
모든 routes에서 이 모듈을 사용.
"""
import os
import hmac
import hashlib
import logging
import datetime
from typing import Callable, Dict

import jwt
from fastapi import Header, HTTPException

logger = logging.getLogger("LawmadiOS.Auth")

# ─── JWT 설정 ────────────────────────────────────────────────
_JWT_ALGORITHM = "HS256"


def _get_jwt_secret() -> str:
    """JWT 서명 키 반환. JWT_SECRET 우선, 없으면 INTERNAL_API_KEY fallback."""
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        secret = os.getenv("INTERNAL_API_KEY", "").strip()
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    return secret


def create_access_token(user_id: str, role: str, expires_hours: int = 24) -> str:
    """JWT 액세스 토큰 생성."""
    valid_roles = {"admin", "premium", "user"}
    if role not in valid_roles:
        raise ValueError(f"Invalid role: {role}. Must be one of: {valid_roles}")
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": now + datetime.timedelta(hours=expires_hours),
        "iat": now,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Dict:
    """JWT 토큰 검증 및 페이로드 반환."""
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"[Auth] JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles: str) -> Callable:
    """FastAPI Depends용 역할 검사 팩토리."""
    allowed = set(roles)

    def _role_checker(authorization: str = Header(default="")) -> Dict:
        token = extract_bearer_token(authorization)
        payload = verify_jwt_token(token)
        user_role = payload.get("role", "")
        if user_role not in allowed:
            logger.warning(
                f"[Auth] Role denied: user={payload.get('sub')}, "
                f"role={user_role}, required={allowed}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {', '.join(sorted(allowed))}"
            )
        return payload

    return _role_checker


def extract_bearer_token(authorization: str) -> str:
    """Authorization 헤더에서 Bearer 토큰을 안전하게 추출.

    올바른 형식: "Bearer <token>"
    잘못된 형식이면 HTTPException(401) 발생.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format. Expected: Bearer <token>")

    token = parts[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    return token


def verify_internal_key(authorization: str = Header(default="")) -> None:
    """INTERNAL_API_KEY 기반 인증 검증.

    - Bearer 형식 검증
    - 상수 시간 비교 (timing attack 방지)
    - 실패 시 토큰 해시만 로깅 (원본 노출 방지)
    """
    api_key = os.getenv("INTERNAL_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=403, detail="INTERNAL_API_KEY not configured")

    token = extract_bearer_token(authorization)

    if not hmac.compare_digest(token, api_key):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:8]
        logger.warning(f"[Auth] Failed internal auth attempt (token_hash={token_hash})")
        raise HTTPException(status_code=401, detail="Unauthorized")


def verify_mcp_key(authorization: str = Header(default="")) -> None:
    """MCP_API_KEY 기반 인증 검증."""
    api_key = os.getenv("MCP_API_KEY", "").strip()
    if not api_key:
        # Fallback to INTERNAL_API_KEY
        api_key = os.getenv("INTERNAL_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=403, detail="API key not configured")

    token = extract_bearer_token(authorization)

    if not hmac.compare_digest(token, api_key):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:8]
        logger.warning(f"[Auth] Failed MCP auth attempt (token_hash={token_hash})")
        raise HTTPException(status_code=401, detail="Unauthorized")


def verify_api_keys(authorization: str = Header(default="")) -> None:
    """다중 API 키 검증 (외부 API 사용자용).

    환경변수 API_KEYS에서 쉼표 구분 키 목록 사용.
    """
    raw_keys = os.getenv("API_KEYS", "").strip()
    if not raw_keys:
        raise HTTPException(status_code=403, detail="API keys not configured")

    valid_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not valid_keys:
        raise HTTPException(status_code=403, detail="No valid API keys configured")

    token = extract_bearer_token(authorization)

    if not any([hmac.compare_digest(token, k) for k in valid_keys]):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:8]
        logger.warning(f"[Auth] Failed API key auth (token_hash={token_hash})")
        raise HTTPException(status_code=401, detail="Invalid API key")
