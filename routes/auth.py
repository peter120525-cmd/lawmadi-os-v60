"""
Lawmadi OS v60 — Auth routes.
JWT 토큰 발급 엔드포인트.
"""
import os
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("LawmadiOS.Auth")
limiter = Limiter(key_func=get_remote_address)


class TokenRequest(BaseModel):
    api_key: str
    role: str = "admin"
    user_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


@router.post("/token", response_model=TokenResponse)
@limiter.limit("5/minute")
async def create_token(request: Request, req: TokenRequest):
    """API 키를 검증하고 JWT 액세스 토큰을 발급."""
    internal_key = os.getenv("INTERNAL_API_KEY", "").strip()
    mcp_key = os.getenv("MCP_API_KEY", "").strip()
    valid_keys = [k for k in [internal_key, mcp_key] if k]

    if not valid_keys:
        raise HTTPException(status_code=500, detail="No API keys configured")

    if not any(hmac.compare_digest(req.api_key, k) for k in valid_keys):
        logger.warning("[Auth] Token request with invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    user_id = req.user_id or "api-client"
    try:
        token = create_access_token(user_id=user_id, role=req.role, expires_hours=24)
    except ValueError as e:
        logger.warning(f"[Auth] Token creation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid token request parameters")

    return TokenResponse(access_token=token, token_type="bearer", expires_in=86400)
