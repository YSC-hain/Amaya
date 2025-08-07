import asyncio
import json
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable

import websockets
from websockets.client import WebSocketClientProtocol

import config
from modules.logger import event_logger


class OneBotAdapter:
    """
    OneBot V11 协议适配器，负责与 OneBot 服务器建立 WebSocket 连接，
    发送 API 调用，并接收、分发事件。
    """

    def __init__(self, message_handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        self.ws_url = config.ONEBOT_WS_URL
        self.access_token = config.ONEBOT_ACCESS_TOKEN
        self.websocket_connection: Optional[WebSocketClientProtocol] = None
        self.api_call_futures: Dict[str, asyncio.Future] = {}
        self.message_handler = message_handler  # 用于处理接收到的消息事件的回调函数

    async def send_api_call(self, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        通过 WebSocket 发送一个 API 调用 (Action) 并等待响应。
        """
        if not self.websocket_connection or not self.websocket_connection.open:
            print("[错误] WebSocket 连接不可用，无法发送 API 调用。")
            return None

        echo = str(uuid.uuid4())
        payload = {
            "action": action,
            "params": params,
            "echo": echo
        }

        future = asyncio.get_running_loop().create_future()
        self.api_call_futures[echo] = future

        try:
            await self.websocket_connection.send(json.dumps(payload))
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
            self.api_call_futures.pop(echo, None)

    async def _handle_event(self, event: Dict[str, Any]):
        """
        处理从 WebSocket 收到的单个事件，并进行分发。
        """
        if 'echo' in event and event['echo'] in self.api_call_futures:
            future = self.api_call_futures.get(event['echo'])
            if future and not future.done():
                future.set_result(event)
            return

        # 仅处理消息事件，并将其传递给外部定义的消息处理器
        if event.get("post_type") == "message":
            event_logger.log_event('ONEBOT_EVENT_RECEIVED', {'event': event})
            # 将事件传递给外部注册的消息处理函数
            asyncio.create_task(self.message_handler(event))

    async def run(self):
        """
        运行并管理到 OneBot (NapCat) 的 WebSocket 连接。
        """
        headers = {}
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'

        reconnect_delay = 5

        while True:
            try:
                print(f"正在尝试连接到: {self.ws_url}")
                async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                    print("成功连接到 OneBot (NapCat) 服务器!")
                    event_logger.log_event('WEBSOCKET_CONNECTED', {'url': self.ws_url})
                    reconnect_delay = 5
                    self.websocket_connection = ws

                    async for message in ws:
                        try:
                            event_data = json.loads(message)
                            await self._handle_event(event_data)
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
                self.websocket_connection = None
                print(f"连接已断开。将在 {reconnect_delay} 秒后尝试重连...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 60)