from __future__ import annotations

import asyncio
import datetime
import hmac
import json
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from config.settings import (
    ALLOWED_QQ_USER_IDS,
    QQ_NAPCAT_ENABLE_GROUP,
    QQ_NAPCAT_SEND_TIMEOUT_SECONDS,
    QQ_NAPCAT_WS_PATH,
    QQ_NAPCAT_WS_TOKEN,
)
from datamodel import ChannelType, IncomingMessage, OutgoingMessage
from events import E, bus
from logger import logger
import storage.user


class _NapCatSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.send_lock = asyncio.Lock()

    async def send_json(self, payload: dict[str, Any]) -> None:
        async with self.send_lock:
            await self.websocket.send_text(json.dumps(payload, ensure_ascii=False))


_routes_registered = False
_active_session: _NapCatSession | None = None
_session_lock = asyncio.Lock()
_pending_echo: dict[str, asyncio.Future] = {}


def _extract_token(websocket: WebSocket) -> str:
    auth_header = websocket.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    if auth_header != "":
        return auth_header

    qs_token = websocket.query_params.get("access_token") or websocket.query_params.get("token")
    return (qs_token or "").strip()


def _is_authorized(websocket: WebSocket) -> bool:
    if QQ_NAPCAT_WS_TOKEN == "":
        return True
    incoming = _extract_token(websocket)
    return hmac.compare_digest(incoming, QQ_NAPCAT_WS_TOKEN)


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _extract_text_content(message: Any, raw_message: Any) -> str:
    if isinstance(message, str):
        return message.strip()

    if isinstance(message, list):
        parts: list[str] = []
        for segment in message:
            if not isinstance(segment, dict):
                continue
            if segment.get("type") != "text":
                continue
            data = segment.get("data")
            if isinstance(data, dict) and "text" in data:
                parts.append(str(data["text"]))
        merged = "".join(parts).strip()
        if merged:
            return merged

    if raw_message is None:
        return ""
    return str(raw_message).strip()


def _resolve_pending_response(payload: dict[str, Any]) -> None:
    echo = str(payload.get("echo", ""))
    if echo == "":
        return

    future = _pending_echo.get(echo)
    if future is None or future.done():
        return
    future.set_result(payload)


def _fail_all_pending(exc: Exception) -> None:
    for future in list(_pending_echo.values()):
        if not future.done():
            future.set_exception(exc)
    _pending_echo.clear()


async def _replace_active_session(session: _NapCatSession) -> None:
    global _active_session
    old: _NapCatSession | None = None
    async with _session_lock:
        old = _active_session
        _active_session = session

    if old is not None:
        try:
            await old.websocket.close(code=1012, reason="replaced")
        except Exception:
            pass


async def _detach_active_session(session: _NapCatSession) -> bool:
    global _active_session
    async with _session_lock:
        if _active_session is session:
            _active_session = None
            return True
    return False

async def _close_active_session(reason: str) -> None:
    global _active_session
    session: _NapCatSession | None = None
    async with _session_lock:
        session = _active_session
        _active_session = None

    if session is not None:
        try:
            await session.websocket.close(code=1001, reason=reason)
        except Exception:
            pass


async def _send_action(action: str, params: dict[str, Any]) -> dict[str, Any]:
    session = _active_session
    if session is None:
        raise RuntimeError("NapCat Reverse WS 未连接")

    echo = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _pending_echo[echo] = future

    try:
        await session.send_json({"action": action, "params": params, "echo": echo})
        response = await asyncio.wait_for(future, timeout=QQ_NAPCAT_SEND_TIMEOUT_SECONDS)
    finally:
        _pending_echo.pop(echo, None)

    if response.get("status") != "ok":
        raise RuntimeError(f"OneBot API 调用失败: action={action}, response={response}")
    return response


async def _safe_reject_private_user(qq_user_id: int) -> None:
    try:
        await _send_action(
            "send_private_msg",
            {
                "user_id": qq_user_id,
                "message": "您无权使用此 Bot。如有需要, 请联系管理员。",
            },
        )
    except Exception as e:
        logger.warning(f"发送 QQ 鉴权拒绝消息失败: user={qq_user_id}, error={e}")


async def _handle_message_event(payload: dict[str, Any]) -> None:
    message_type = str(payload.get("message_type", ""))
    if message_type not in ("private", "group"):
        return
    if message_type == "group" and not QQ_NAPCAT_ENABLE_GROUP:
        return

    qq_user_id = _to_int(payload.get("user_id"))
    if qq_user_id is None:
        return

    self_id = _to_int(payload.get("self_id"))
    if self_id is not None and qq_user_id == self_id:
        return

    if ALLOWED_QQ_USER_IDS != [] and qq_user_id not in ALLOWED_QQ_USER_IDS:
        logger.warning(f"QQ 用户 {qq_user_id} 未经允许访问 Bot")
        if message_type == "private":
            await _safe_reject_private_user(qq_user_id)
        return

    content = _extract_text_content(payload.get("message"), payload.get("raw_message"))
    if content == "":
        return

    await storage.user.create_user_if_not_exists_by_qq(qq_user_id)
    user = await storage.user.get_user_by_qq_id(qq_user_id)
    if user is None:
        logger.error(f"QQ 用户映射失败: qq_user_id={qq_user_id}")
        return

    timestamp: datetime.datetime | None = None
    raw_ts = payload.get("time")
    if isinstance(raw_ts, (int, float)):
        timestamp = datetime.datetime.fromtimestamp(raw_ts)

    metadata: dict[str, Any] = {
        "qq_user_id": qq_user_id,
        "qq_message_type": message_type,
        "qq_message_id": payload.get("message_id"),
        "qq_self_id": self_id,
    }
    qq_group_id = _to_int(payload.get("group_id"))
    if qq_group_id is not None:
        metadata["qq_group_id"] = qq_group_id

    bus.emit(E.IO_MESSAGE_RECEIVED, IncomingMessage(
        channel_type=ChannelType.QQ_NAPCAT_ONEBOT_V11,
        user_id=user.user_id,
        content=content,
        channel_context=None,
        metadata=metadata,
        timestamp=timestamp,
    ))


async def _handle_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        return

    if "echo" in payload:
        _resolve_pending_response(payload)
        return

    post_type = payload.get("post_type")
    if post_type == "message":
        await _handle_message_event(payload)
    elif post_type == "meta_event":
        meta_event_type = payload.get("meta_event_type")
        if meta_event_type == "lifecycle":
            logger.info(f"NapCat 生命周期事件: {payload.get('sub_type', 'unknown')}, self_id={payload.get('self_id')}")


def register_fastapi_routes(app: FastAPI) -> None:
    global _routes_registered
    if _routes_registered:
        return

    @app.websocket(QQ_NAPCAT_WS_PATH)
    async def napcat_reverse_ws(websocket: WebSocket):
        if not _is_authorized(websocket):
            await websocket.close(code=1008, reason="unauthorized")
            logger.warning("NapCat Reverse WS 鉴权失败")
            return

        await websocket.accept()
        session = _NapCatSession(websocket)
        await _replace_active_session(session)
        logger.info(f"NapCat Reverse WS 已连接: path={QQ_NAPCAT_WS_PATH}")

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("收到无法解析的 NapCat 消息, 已忽略")
                    continue
                await _handle_payload(payload)
        except WebSocketDisconnect:
            logger.warning("NapCat Reverse WS 已断开")
        except Exception as e:
            logger.error(f"NapCat Reverse WS 处理异常: {e}", exc_info=e)
        finally:
            was_active = await _detach_active_session(session)
            if was_active:
                _fail_all_pending(RuntimeError("NapCat Reverse WS 连接已断开"))

    _routes_registered = True


@bus.on(E.IO_SEND_MESSAGE)
async def send_outgoing_message(msg: OutgoingMessage) -> None:
    if msg.channel_type != ChannelType.QQ_NAPCAT_ONEBOT_V11:
        return

    user = await storage.user.get_user_by_id(msg.user_id)
    if user is None or user.qq_user_id is None:
        logger.error(f"无法找到 user_id={msg.user_id} 对应的 QQ 用户")
        return

    qq_group_id = _to_int(msg.metadata.get("qq_group_id")) if msg.metadata else None

    try:
        if qq_group_id is not None:
            await _send_action("send_group_msg", {"group_id": qq_group_id, "message": msg.content})
        else:
            await _send_action("send_private_msg", {"user_id": user.qq_user_id, "message": msg.content})
    except Exception as e:
        logger.error(f"向 QQ 用户发送消息失败: user_id={msg.user_id}, error={e}, 即将重试", exc_info=e)
        try:
            await asyncio.sleep(2)
            if qq_group_id is not None:
                await _send_action("send_group_msg", {"group_id": qq_group_id, "message": msg.content})
            else:
                await _send_action("send_private_msg", {"user_id": user.qq_user_id, "message": msg.content})
        except Exception as e2:
            logger.error(f"[重试] 向 QQ 用户发送消息失败: user_id={msg.user_id}, error={e2}", exc_info=e2)


async def main(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    logger.info(f"QQ/NapCat OneBot 通道已启动，等待反向 WS 连接: {QQ_NAPCAT_WS_PATH}")
    await shutdown_event.wait()
    await _close_active_session("service_shutdown")
    _fail_all_pending(RuntimeError("服务已关闭"))
    logger.info("QQ/NapCat OneBot 通道已关闭")
