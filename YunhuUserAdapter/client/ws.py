import json
import uuid
import websockets
from typing import Optional, Dict, Any, AsyncIterator
from google.protobuf import json_format
from ..proto import ws_pb2


class YunhuWSClient:
    WS_URL = "wss://chat-ws-go.jwzhd.com/ws"
    
    def __init__(self, token: str, user_id: str, 
                 platform: str = "windows", device_id: Optional[str] = None,
                 timeout: int = 70, decode: bool = True, 
                 mode: str = "black", blacklist: list = None):
        """
        初始化 WebSocket 客户端
        
        :param token: 用户 token
        :param user_id: 用户 ID
        :param platform: 平台
        :param device_id: 设备 ID
        :param timeout: 超时时间（秒）
        :param decode: 是否解码消息
        :param mode: 过滤模式 (black/white)
        :param blacklist: 黑名单或白名单列表
        """
        self.token = token
        self.user_id = user_id
        self.platform = platform
        self.device_id = device_id or uuid.uuid4().hex
        # 确保 timeout 为整数类型
        self.timeout = int(timeout) if timeout is not None else 70
        self.decode = decode
        self.mode = mode
        self.filter_list = blacklist or []
        
        self.ws = None
        self._running = False
    
    async def connect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        连接到 WebSocket 并监听事件
        
        :return: 异步迭代器，返回解析后的事件
        """
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
            # 此处兼容：使用 ping_interval 和 ping_timeout 替代 timeout
            # 非必要勿修改
            async with websockets.connect(
                self.WS_URL,
                ping_interval=30,
                ping_timeout=self.timeout,
                close_timeout=10
            ) as ws:
                self.ws = ws
                
                # 发送登录消息
                login_json = json.dumps(login_data)
                await ws.send(login_json)
                
                # 启动心跳任务
                import asyncio
                heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
                
                try:
                    # 接收消息循环
                    while self._running:
                        try:
                            # 等待接收消息
                            recv_task = asyncio.create_task(ws.recv())
                            message = await asyncio.wait_for(recv_task, timeout=self.timeout)
                            
                            if not self._running:
                                break
                            
                            # 解析事件
                            event = self._parse_message(message)
                            
                            # 检查是否需要过滤
                            if self._should_filter(event):
                                continue
                            
                            # 是否解码
                            if self.decode and event:
                                yield event
                            elif not self.decode:
                                yield message
                                
                        except asyncio.TimeoutError:
                            # 超时，继续等待
                            continue
                        except Exception as e:
                            # 其他错误，打印日志
                            if self._running:
                                print(f"WebSocket 消息处理错误: {e}")
                            break
                finally:
                    # 取消心跳任务
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    
        except Exception as e:
            print(f"WebSocket 连接错误: {e}")
        finally:
            self.ws = None
            self._running = False
    
    async def _heartbeat_loop(self, ws):
        import asyncio
        heartbeat_data = {
            "seq": uuid.uuid4().hex,
            "cmd": "heartbeat",
            "data": {}
        }
        
        while self._running:
            try:
                heartbeat_json = json.dumps(heartbeat_data)
                await ws.send(heartbeat_json)
                await asyncio.sleep(30)  # 30 秒发送一次心跳
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    print(f"心跳发送错误: {e}")
                break
    
    def _parse_message(self, message: bytes) -> Optional[Dict[str, Any]]:
        """
        解析 WebSocket 消息

        :param message: 消息二进制数据（Protobuf 格式）
        :return: 解析后的事件字典
        """
        # 命令类型映射
        cmd_map = {
            "push_message": ws_pb2.push_message,
            "edit_message": ws_pb2.edit_message,
            "file_send_message": ws_pb2.file_send_message,
            "bot_board_message": ws_pb2.bot_board_message,
            "stream_message": ws_pb2.stream_message,
            "draft_input": ws_pb2.draft_input,
        }

        try:
            # 先解析为 heartbeat_ack 获取命令类型
            msg_temp = ws_pb2.heartbeat_ack()
            msg_temp.ParseFromString(message)

            # 检查是否需要过滤
            if self._should_filter_by_cmd(msg_temp.info.cmd):
                return None

            # 根据命令类型解析
            if msg_temp.info.cmd == "heartbeat_ack":
                # 心跳响应
                return json_format.MessageToDict(msg_temp, preserving_proto_field_name=True)
            elif msg_temp.info.cmd in cmd_map:
                # 具体消息类型
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
        """
        根据命令检查是否需要过滤
        
        :param cmd: 命令字符串
        :return: True 表示需要过滤
        """
        if self.mode == "black":
            # 黑名单模式：在列表中则过滤
            return cmd in self.filter_list
        elif self.mode == "white":
            # 白名单模式：不在列表中则过滤
            return cmd not in self.filter_list
        return False
    
    def _should_filter(self, event: Optional[Dict[str, Any]]) -> bool:
        """
        检查事件是否需要被过滤
        
        :param event: 事件数据
        :return: True 表示需要过滤
        """
        if not event:
            return True
        
        cmd = event.get("info", {}).get("cmd", "")
        
        if self.mode == "black":
            # 黑名单模式：在列表中则过滤
            return cmd in self.filter_list
        elif self.mode == "white":
            # 白名单模式：不在列表中则过滤
            return cmd not in self.filter_list
        
        return False
    
    async def close(self):
        self._running = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None