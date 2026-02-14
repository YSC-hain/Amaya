from __future__ import annotations

import asyncio
import hmac
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import (
    ADMIN_AUTH_TOKEN,
    ADMIN_LOG_FILE,
    ENABLE_QQ_NAPCAT,
    ENABLE_TELEGRAM_BOT_POLLING,
    WEBHOOK_SHARED_SECRET,
)
from core.amaya import require_amaya
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from logger import logger
from metrics import runtime_metrics
from pydantic import BaseModel, Field

import storage.db_config as db_config
from .store import (
    append_jsonl,
    fetch_all,
    fetch_one,
    filter_logs,
    sanitize_source,
    tail_lines,
)

_TEMPLATE_DIR = Path(__file__).with_name("templates")


@dataclass
class RuntimeControl:
    shutdown_event: asyncio.Event
    restart_event: asyncio.Event
    started_at: float


class ShutdownRequest(BaseModel):
    reason: str = Field(default="manual")


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


@lru_cache(maxsize=2)
def _load_template(name: str) -> str:
    path = _TEMPLATE_DIR / name
    return path.read_text(encoding="utf-8")


def login_page_html() -> str:
    return _load_template("login.html")


def dashboard_html() -> str:
    return _load_template("dashboard.html")


def create_app(control: RuntimeControl) -> FastAPI:
    app = FastAPI(title="Amaya Admin API", version="1.2.0")
    if ENABLE_QQ_NAPCAT:
        from channels.qq_onebot_ws import register_fastapi_routes as register_napcatqq_routes

        register_napcatqq_routes(app)
        logger.info("已挂载 NapCatQQ OneBot 反向 WS 路由")

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
                (SELECT COUNT(*) FROM messages) AS messages,
                (SELECT COUNT(*) FROM reminders) AS reminders,
                (SELECT COUNT(*) FROM memory_groups) AS memory_groups,
                (SELECT COUNT(*) FROM memory_points) AS memory_points
            """
        )
        return {"counts": row or {}}

    @app.get("/api/v1/metrics")
    async def get_metrics(request: Request) -> dict[str, Any]:
        await require_admin_auth(request)

        telegram_status = {
            "enabled": ENABLE_TELEGRAM_BOT_POLLING,
            "connected": False,
            "active_typing": 0,
        }
        if ENABLE_TELEGRAM_BOT_POLLING:
            try:
                from channels.telegram_polling import get_status as get_telegram_status

                telegram_status.update(get_telegram_status())
            except Exception as e:
                logger.warning(f"读取 Telegram 状态失败: {e}")

        napcatqq_status = {
            "enabled": ENABLE_QQ_NAPCAT,
            "connected": False,
            "pending_calls": 0,
        }
        if ENABLE_QQ_NAPCAT:
            try:
                from channels.qq_onebot_ws import get_status as get_napcatqq_status

                napcatqq_status.update(get_napcatqq_status())
            except Exception as e:
                logger.warning(f"读取 NapCatQQ 状态失败: {e}")

        reminder_status = {"running": False, "last_check_at_epoch": None}
        try:
            from world.reminder import get_status as get_reminder_status

            reminder_status.update(get_reminder_status())
        except Exception as e:
            logger.warning(f"读取 Reminder 状态失败: {e}")

        amaya_status = {
            "configured": False,
            "thinking": False,
            "unsent_queue": 0,
            "buffered_segments": 0,
            "new_message_pending": False,
        }
        try:
            amaya = require_amaya()
            amaya_status["configured"] = True
            amaya_status.update(amaya.get_status())
        except Exception:
            pass

        return {
            "runtime": runtime_metrics.snapshot(),
            "components": {
                "db": {"connected": db_config.conn is not None},
                "telegram": telegram_status,
                "napcatqq": napcatqq_status,
                "reminder": reminder_status,
                "amaya": amaya_status,
            },
            "active_tasks": len(asyncio.all_tasks()),
        }

    @app.get("/api/v1/messages")
    async def get_messages(
        request: Request,
        q: str | None = None,
        role: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        where_clauses: list[str] = []
        params: list[Any] = []

        if q:
            where_clauses.append("content LIKE ?")
            params.append(f"%{q}%")

        if role:
            where_clauses.append("role = ?")
            params.append(role)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        total_row = await fetch_one(
            f"SELECT COUNT(*) AS total FROM messages {where_sql}",
            tuple(params),
        )
        total = int((total_row or {}).get("total", 0))

        query_params = [*params, limit, offset]
        items = await fetch_all(
            (
                "SELECT message_id, channel, role, content, created_at_utc "
                f"FROM messages {where_sql} "
                "ORDER BY message_id DESC LIMIT ? OFFSET ?"
            ),
            tuple(query_params),
        )

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "q": q,
            "role": role,
            "total": total,
        }

    @app.get("/api/v1/reminders")
    async def get_reminders(
        request: Request,
        status: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        where_clauses: list[str] = []
        params: list[Any] = []

        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if q:
            where_clauses.append("title LIKE ?")
            params.append(f"%{q}%")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        total_row = await fetch_one(
            f"SELECT COUNT(*) AS total FROM reminders {where_sql}",
            tuple(params),
        )
        total = int((total_row or {}).get("total", 0))

        sql = (
            "SELECT reminder_id, title, remind_at_min_utc, prompt, status, next_action_at_min_utc, created_at_utc, updated_at_utc "
            f"FROM reminders {where_sql} ORDER BY reminder_id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        items = await fetch_all(sql, tuple(params))

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "status": status,
            "q": q,
            "total": total,
        }

    @app.get("/api/v1/memory/groups")
    async def get_memory_groups(
        request: Request,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        await require_admin_auth(request)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        where_sql = ""
        params: list[Any] = []
        if q:
            where_sql = "WHERE title LIKE ?"
            params.append(f"%{q}%")

        total_row = await fetch_one(
            f"SELECT COUNT(*) AS total FROM memory_groups {where_sql}",
            tuple(params),
        )
        total = int((total_row or {}).get("total", 0))

        query_params = [*params, limit, offset]

        items = await fetch_all(
            (
                "SELECT memory_group_id, title, created_at_utc, updated_at_utc "
                f"FROM memory_groups {where_sql} "
                "ORDER BY memory_group_id DESC LIMIT ? OFFSET ?"
            ),
            tuple(query_params),
        )

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "q": q,
            "total": total,
        }

    @app.get("/api/v1/memory/points")
    async def get_memory_points(
        request: Request,
        memory_group_id: int | None = None,
        q: str | None = None,
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
        if q:
            where_clauses.append("(anchor LIKE ? OR content LIKE ?)")
            params.append(f"%{q}%")
            params.append(f"%{q}%")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        total_row = await fetch_one(
            f"SELECT COUNT(*) AS total FROM memory_points {where_sql}",
            tuple(params),
        )
        total = int((total_row or {}).get("total", 0))

        sql = (
            "SELECT memory_point_id, memory_group_id, anchor, content, memory_type, weight, created_at_utc, updated_at_utc "
            f"FROM memory_points {where_sql} ORDER BY memory_point_id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        items = await fetch_all(sql, tuple(params))

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "memory_group_id": memory_group_id,
            "q": q,
            "total": total,
        }

    @app.get("/api/v1/logs")
    async def get_logs(
        request: Request,
        lines: int = 200,
        level: str | None = None,
        levels: str | None = None,
        q: str | None = None,
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
        level_list: list[str] = []
        if levels:
            level_list.extend([part.strip() for part in levels.split(",") if part.strip()])
        if level:
            level_list.append(level)

        filtered = filter_logs(raw_lines, levels=level_list, keyword=q)
        return {
            "stream": stream,
            "level": level,
            "levels": level_list,
            "q": q,
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
