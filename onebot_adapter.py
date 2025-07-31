import asyncio
import json
import uuid
from typing import Dict, Any, Optional

import websockets
from websockets.client import WebSocketClientProtocol

import config
from main import Amaya
from modules.logger import event_logger

# -- 全局变量 --
# 使用一个字典来管理不同用户的 Amaya 实例
active_sessions: Dict[str, Amaya] = {}
# 全局 WebSocket 连接实例
websocket_connection: Optional[WebSocketClientProtocol] = None
# 用于匹配 API 调用的响应
api_call_futures: Dict[str, asyncio.Future] = {}


# -- 会话管理 --
def get_or_create_session(user_id: str) -> Amaya:
    """
    获取或创建一个新的 Amaya 会话实例。
    """
    if user_id not in active_sessions:
        event_logger.log_event('SESSION_CREATE', {'user_id': user_id})
        print(f"为用户 {user_id} 创建新的会话...")
        amaya_instance = Amaya(user_id=user_id)
        amaya_instance.start() # 仅启动后台模拟线程
        active_sessions[user_id] = amaya_instance
        print(f"用户 {user_id} 的会话已启动。")
    return active_sessions[user_id]


# -- WebSocket 通信 --

async def send_api_call(action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    通过 WebSocket 发送一个 API 调用 (Action) 并等待响应。
    """
    if not websocket_connection or not websocket_connection.open:
        print("[错误] WebSocket 连接不可用，无法发送 API 调用。")
        return None

    echo = str(uuid.uuid4())
    payload = {
        "action": action,
        "params": params,
        "echo": echo
    }

    future = asyncio.get_running_loop().create_future()
    api_call_futures[echo] = future

    try:
        await websocket_connection.send(json.dumps(payload))
        response = await asyncio.wait_for(future, timeout=10)
        event_logger.log_event('ONEBOT_ACTION_SUCCESS', {'action': action, 'params': params, 'response': response})
        return response
    except asyncio.TimeoutError:
        print(f"[错误] API 调用超时: {action}")
        event_logger.log_event('ONEBOT_ACTION_ERROR', {'action': action, 'error': 'Request timed out'})
        return None
    except Exception as e:
        print(f"[错误] 发送 API 调用时出错: {e}")
        event_logger.log_event('ONEBOT_ACTION_ERROR', {'action': action, 'error': str(e)})
        return None
    finally:
        api_call_futures.pop(echo, None)


async def handle_private_message(event: Dict[str, Any]):
    """
    处理私聊消息事件，调用核心逻辑。
    """
    user_id = str(event.get("user_id"))
    message_text = str(event.get("raw_message", "")).strip()

    amaya = get_or_create_session(user_id)

    # 定义一个 OneBot 特定的回调函数
    async def onebot_reply_callback(response_message: Dict[str, Any]):
        content = response_message.get("content", "...")
        await send_api_call(
            action="send_private_msg",
            params={"user_id": int(user_id), "message": content}
        )

    # 调用 Amaya 的核心处理逻辑，并传入 OneBot 的回调
    await amaya.process_user_input(message_text, onebot_reply_callback)


async def handle_event(event: Dict[str, Any]):
    """
    处理从 WebSocket 收到的单个事件，并进行分发。
    """
    if 'echo' in event and event['echo'] in api_call_futures:
        future = api_call_futures.get(event['echo'])
        if future and not future.done():
            future.set_result(event)
        return

    if event.get("post_type") == "message" and event.get("message_type") == "private":
        event_logger.log_event('ONEBOT_EVENT_RECEIVED', {'event': event})
        asyncio.create_task(handle_private_message(event))


async def run_client():
    """
    运行并管理到 OneBot (NapCat) 的 WebSocket 连接。
    """
    global websocket_connection
    ws_url = config.ONEBOT_WS_URL
    headers = {}
    if config.ONEBOT_ACCESS_TOKEN:
        headers['Authorization'] = f'Bearer {config.ONEBOT_ACCESS_TOKEN}'

    reconnect_delay = 5

    while True:
        try:
            print(f"正在尝试连接到: {ws_url}")
            async with websockets.connect(ws_url, extra_headers=headers) as ws:
                print("成功连接到 OneBot (NapCat) 服务器!")
                event_logger.log_event('WEBSOCKET_CONNECTED', {'url': ws_url})
                reconnect_delay = 5
                websocket_connection = ws

                async for message in ws:
                    try:
                        event_data = json.loads(message)
                        await handle_event(event_data)
                    except json.JSONDecodeError:
                        print(f"[警告] 无法解析收到的消息: {message}")
                    except Exception as e:
                        print(f"[错误] 处理事件时出错: {e}")

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError) as e:
            print(f"连接断开或被拒绝: {e}")
        except websockets.exceptions.InvalidHandshake as e:
            print(f"握手失败 (403 Forbidden?): {e}. 请检查 Access Token 是否正确。")
        except Exception as e:
            print(f"发生未知错误: {e}")
        finally:
            websocket_connection = None
            print(f"连接已断开。将在 {reconnect_delay} 秒后尝试重连...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, 60)


# -- 应用关闭事件 --
def shutdown_sessions():
    print("程序正在关闭...")
    for user_id, amaya_instance in active_sessions.items():
        print(f"正在为用户 {user_id} 保存状态并关闭会话...")
        amaya_instance.stop()
    print("所有会话已关闭。")


# -- 启动 --
if __name__ == "__main__":
    print("========================================")
    print("  Amaya OneBot V11 Standalone Adapter  ")
    print("========================================")

    loop = asyncio.get_event_loop()
    main_task = loop.create_task(run_client())

    try:
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        print("检测到手动中断，正在关闭...")
    finally:
        shutdown_sessions()
        main_task.cancel()
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        print("程序已完全关闭。")