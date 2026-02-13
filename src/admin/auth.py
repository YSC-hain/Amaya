from __future__ import annotations

import hmac

from config.settings import ADMIN_AUTH_TOKEN
from fastapi import HTTPException, Request
from logger import logger

if not ADMIN_AUTH_TOKEN:
    logger.warning("未配置 ADMIN_AUTH_TOKEN，管理 API/Web 将不可访问")


def extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    token_header = request.headers.get("X-Amaya-Token", "").strip()
    return token_header or None


async def require_admin_auth(request: Request) -> dict[str, str]:
    if not ADMIN_AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="ADMIN_AUTH_TOKEN 未配置")

    token = extract_token(request)
    if token and hmac.compare_digest(token, ADMIN_AUTH_TOKEN):
        return {"auth": "token", "user": "admin-token"}

    raise HTTPException(status_code=401, detail="未授权")
