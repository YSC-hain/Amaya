from __future__ import annotations

import asyncio
import hmac
import time
from pathlib import Path
from typing import Any

from config.settings import ADMIN_LOG_FILE, ENABLE_QQ_NAPCAT, WEBHOOK_SHARED_SECRET
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from logger import logger

import storage.db_config as db_config
from .auth import require_admin_auth
from .schemas import RuntimeControl, ShutdownRequest
from .store import (
    append_jsonl,
    fetch_all,
    fetch_one,
    filter_log_by_level,
    sanitize_source,
    tail_lines,
)
from .ui import dashboard_html, login_page_html


def create_app(control: RuntimeControl) -> FastAPI:
    app = FastAPI(title="Amaya Admin API", version="1.2.0")
    if ENABLE_QQ_NAPCAT:
        from channels.qq_onebot_ws import register_fastapi_routes as register_qq_routes

        register_qq_routes(app)
        logger.info("已挂载 QQ/NapCat OneBot 反向 WS 路由")

    def health_payload() -> dict[str, Any]:
        return {
            "status": "ok",
            "now_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "uptime_seconds": max(0.0, time.time() - control.started_at),
            "db_connected": db_config.conn is not None,
            "shutdown_requested": control.shutdown_event.is_set(),
            "restart_requested": control.restart_event.is_set(),
        }

    @app.get("/", include_in_schema=False)
    async def home() -> RedirectResponse:
        return RedirectResponse(url="/admin")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, Any]:
        return health_payload()

    @app.get("/healthy", include_in_schema=False)
    async def healthy() -> dict[str, Any]:
        return health_payload()

    @app.get("/api/v1/health")
    async def api_health() -> dict[str, Any]:
        return health_payload()

    @app.get("/admin/login", include_in_schema=False)
    async def admin_login_page() -> HTMLResponse:
        return HTMLResponse(login_page_html())

    @app.get("/admin", include_in_schema=False)
    async def admin_page() -> HTMLResponse:
        return HTMLResponse(dashboard_html())

    @app.get("/api/v1/auth/check")
    async def auth_check(request: Request) -> dict[str, bool]:
        await require_admin_auth(request)
        return {"ok": True}

    @app.get("/api/v1/overview")
    async def get_overview(request: Request) -> dict[str, Any]:
        await require_admin_auth(request)
        row = await fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM users) AS users,
                (SELECT COUNT(*) FROM messages) AS messages,
                (SELECT COUNT(*) FROM reminders) AS reminders,
                (SELECT COUNT(*) FROM memory_groups) AS memory_groups,
                (SELECT COUNT(*) FROM memory_points) AS memory_points
            """
        )
        return {"counts": row or {}}

    @app.get("/api/v1/users")
    async def get_users(request: Request, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        items = await fetch_all(
            """
            SELECT user_id, user_name, timezone, email, telegram_user_id, qq_user_id, last_active_utc, created_at_utc, updated_at_utc
            FROM users
            ORDER BY user_id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return {"items": items, "limit": limit, "offset": offset}

    @app.get("/api/v1/messages")
    async def get_messages(
        request: Request,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        if user_id is None:
            items = await fetch_all(
                """
                SELECT message_id, user_id, channel, role, content, created_at_utc
                FROM messages
                ORDER BY message_id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        else:
            items = await fetch_all(
                """
                SELECT message_id, user_id, channel, role, content, created_at_utc
                FROM messages
                WHERE user_id = ?
                ORDER BY message_id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )

        return {"items": items, "limit": limit, "offset": offset, "user_id": user_id}

    @app.get("/api/v1/reminders")
    async def get_reminders(
        request: Request,
        user_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        where_clauses: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if status:
            where_clauses.append("status = ?")
            params.append(status)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = (
            "SELECT reminder_id, user_id, title, remind_at_min_utc, prompt, status, next_action_at_min_utc, created_at_utc, updated_at_utc "
            f"FROM reminders {where_sql} ORDER BY reminder_id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        items = await fetch_all(sql, tuple(params))

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "user_id": user_id,
            "status": status,
        }

    @app.get("/api/v1/memory/groups")
    async def get_memory_groups(
        request: Request,
        user_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        if user_id is None:
            items = await fetch_all(
                """
                SELECT memory_group_id, user_id, title, created_at_utc, updated_at_utc
                FROM memory_groups
                ORDER BY memory_group_id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        else:
            items = await fetch_all(
                """
                SELECT memory_group_id, user_id, title, created_at_utc, updated_at_utc
                FROM memory_groups
                WHERE user_id = ?
                ORDER BY memory_group_id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )

        return {"items": items, "limit": limit, "offset": offset, "user_id": user_id}

    @app.get("/api/v1/memory/points")
    async def get_memory_points(
        request: Request,
        memory_group_id: int | None = None,
        user_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        where_clauses: list[str] = []
        params: list[Any] = []
        if memory_group_id is not None:
            where_clauses.append("memory_group_id = ?")
            params.append(memory_group_id)
        if user_id is not None:
            where_clauses.append("user_id = ?")
            params.append(user_id)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = (
            "SELECT memory_point_id, user_id, memory_group_id, anchor, content, memory_type, weight, created_at_utc, updated_at_utc "
            f"FROM memory_points {where_sql} ORDER BY memory_point_id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        items = await fetch_all(sql, tuple(params))

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "memory_group_id": memory_group_id,
            "user_id": user_id,
        }

    @app.get("/api/v1/logs")
    async def get_logs(
        request: Request,
        lines: int = 200,
        level: str | None = None,
        stream: str = "main",
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        lines = max(1, min(lines, 5000))

        base_path = Path(ADMIN_LOG_FILE)
        if stream == "error":
            target_path = base_path.with_name(f"{base_path.stem}_error{base_path.suffix}")
        else:
            target_path = base_path

        raw_lines = tail_lines(target_path, lines)
        filtered = filter_log_by_level(raw_lines, level)
        return {
            "stream": stream,
            "level": level,
            "file": str(target_path),
            "lines": filtered,
        }

    @app.post("/api/v1/webhooks/{source}")
    async def ingest_webhook(source: str, request: Request) -> dict[str, Any]:
        safe_source = sanitize_source(source)

        if WEBHOOK_SHARED_SECRET:
            incoming = request.headers.get("X-Amaya-Webhook-Secret", "")
            if not hmac.compare_digest(incoming, WEBHOOK_SHARED_SECRET):
                raise HTTPException(status_code=401, detail="Webhook 鉴权失败")
        else:
            await require_admin_auth(request)

        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Webhook payload 必须为 JSON")

        now_epoch = int(time.time())
        record = {
            "source": safe_source,
            "received_at_epoch": now_epoch,
            "received_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch)),
            "payload": payload,
        }

        target_path = Path("data") / "webhooks" / f"{safe_source}.jsonl"
        await asyncio.to_thread(append_jsonl, target_path, record)
        logger.info(f"收到 Webhook: source={safe_source}")

        return {"ok": True, "message": "Webhook 已接收", "source": safe_source}

    @app.post("/api/v1/admin/restart")
    async def admin_restart(payload: ShutdownRequest, request: Request) -> dict[str, Any]:
        auth_info = await require_admin_auth(request)
        logger.warning(f"收到远程重启请求: by={auth_info['user']}, reason={payload.reason}")
        control.restart_event.set()
        control.shutdown_event.set()
        return {"ok": True, "action": "restart", "reason": payload.reason}

    @app.post("/api/v1/admin/shutdown")
    async def admin_shutdown(payload: ShutdownRequest, request: Request) -> dict[str, Any]:
        auth_info = await require_admin_auth(request)
        logger.warning(f"收到远程关闭请求: by={auth_info['user']}, reason={payload.reason}")
        control.shutdown_event.set()
        return {"ok": True, "action": "shutdown", "reason": payload.reason}

    return app
