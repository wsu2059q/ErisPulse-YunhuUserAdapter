import asyncio
import json
import uuid
from typing import Optional, Dict, Any, AsyncIterator
from google.protobuf import json_format
from ..proto import ws_pb2

from ErisPulse.Core import client
from ErisPulse.Core.Bases.websocket import WSMessage


class YunhuWSClient:
    WS_URL = "wss://chat-ws-go.jwzhd.com/ws"

    def __init__(self, token: str, user_id: str,
                 platform: str = "windows", device_id: Optional[str] = None,
                 timeout: int = 70, decode: bool = True,
                 mode: str = "black", blacklist: list = None):
        self.token = token
        self.user_id = user_id
        self.platform = platform
        self.device_id = device_id or uuid.uuid4().hex
        self.timeout = int(timeout) if timeout is not None else 70
        self.decode = decode
        self.mode = mode
        self.filter_list = blacklist or []

        self.ws = None
        self._running = False

    async def connect(self) -> AsyncIterator[Dict[str, Any]]:
        self._running = True
        login_data = {
            "seq": uuid.uuid4().hex,
            "cmd": "login",
            "data": {
                "userId": self.user_id,
                "token": self.token,
                "platform": self.platform,
                "deviceId": self.device_id
            }
        }

        try:
            ws = await client.ws_connect(self.WS_URL, heartbeat=30)
            self.ws = ws

            await ws.send_text(json.dumps(login_data))

            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

            try:
                while self._running:
                    try:
                        msg = await asyncio.wait_for(
                            ws.receive(), timeout=self.timeout
                        )

                        if not self._running:
                            break

                        if msg.type == WSMessage.CLOSE:
                            if self._running:
                                print(f"WebSocket 连接关闭")
                            break
                        elif msg.type == WSMessage.ERROR:
                            if self._running:
                                print(f"WebSocket 错误")
                            break

                        raw_data = msg.data

                        if msg.type == WSMessage.TEXT:
                            raw_data = raw_data.encode("utf-8") if isinstance(raw_data, str) else raw_data

                        event = self._parse_message(raw_data)

                        if self._should_filter(event):
                            continue

                        if self.decode and event:
                            yield event
                        elif not self.decode:
                            yield raw_data

                    except asyncio.TimeoutError:
                        if not self._running:
                            break
                        continue
                    except Exception as e:
                        if self._running:
                            print(f"WebSocket 消息处理错误: {e}")
                        break
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            print(f"WebSocket 连接错误: {e}")
        finally:
            if self.ws:
                try:
                    if not self.ws.closed:
                        await self.ws.close()
                except Exception:
                    pass
            self.ws = None
            self._running = False

    async def _heartbeat_loop(self, ws):
        while self._running:
            try:
                heartbeat_data = {
                    "seq": uuid.uuid4().hex,
                    "cmd": "heartbeat",
                    "data": {}
                }
                await ws.send_text(json.dumps(heartbeat_data))
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    print(f"心跳发送错误: {e}")
                break

    def _parse_message(self, message: bytes) -> Optional[Dict[str, Any]]:
        cmd_map = {
            "push_message": ws_pb2.push_message,
            "edit_message": ws_pb2.edit_message,
            "file_send_message": ws_pb2.file_send_message,
            "bot_board_message": ws_pb2.bot_board_message,
            "stream_message": ws_pb2.stream_message,
            "draft_input": ws_pb2.draft_input,
        }

        try:
            msg_temp = ws_pb2.heartbeat_ack()
            msg_temp.ParseFromString(message)

            if self._should_filter_by_cmd(msg_temp.info.cmd):
                return None

            if msg_temp.info.cmd == "heartbeat_ack":
                return json_format.MessageToDict(msg_temp, preserving_proto_field_name=True)
            elif msg_temp.info.cmd in cmd_map:
                msg_class = cmd_map[msg_temp.info.cmd]
                msg_data = msg_class()
                msg_data.ParseFromString(message)
                return json_format.MessageToDict(msg_data, preserving_proto_field_name=True)
            else:
                return None

        except Exception as e:
            print(f"Protobuf 解析错误: {e}")
            return None

    def _should_filter_by_cmd(self, cmd: str) -> bool:
        if self.mode == "black":
            return cmd in self.filter_list
        elif self.mode == "white":
            return cmd not in self.filter_list
        return False

    def _should_filter(self, event: Optional[Dict[str, Any]]) -> bool:
        if not event:
            return True

        cmd = event.get("info", {}).get("cmd", "")

        if self.mode == "black":
            return cmd in self.filter_list
        elif self.mode == "white":
            return cmd not in self.filter_list

        return False

    async def close(self):
        self._running = False
        if self.ws:
            try:
                if not self.ws.closed:
                    await self.ws.close()
            except Exception:
                pass
            self.ws = None
