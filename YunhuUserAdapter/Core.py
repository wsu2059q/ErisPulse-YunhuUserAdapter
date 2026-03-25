"""
云湖用户账户驱动适配器核心类

支持通过用户邮箱账户与云湖平台交互，使用 WebSocket 接收事件
"""

import asyncio
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass

# ErisPulse 核心导入
from ErisPulse.Core import logger, config as config_manager, adapter
from ErisPulse.Core.Bases import BaseAdapter

# 本地导入
from .client.http import YunhuHTTPClient
from .client.ws import YunhuWSClient
from .Send import Send
from .utils.constants import CHAT_TYPE_MAP
from .utils.response_formatter import ResponseFormatter


@dataclass
class AccountConfig:
    """账户配置"""
    email: str
    password: str
    platform: str = "windows"
    device_id: str = ""
    enabled: bool = True


class YunhuUserAdapter(BaseAdapter):
    """
    云湖用户账户驱动适配器
    
    支持通过用户邮箱账户登录，使用 WebSocket 接收消息事件
    """
    
    Send = Send

    def __init__(self, sdk):
        
        # 调用父类初始化（必须，以初始化 self.Send）
        super().__init__()
        
        self.logger = logger
        self.config_manager = config_manager
        self.adapter = adapter
        
        # 账户配置
        self.accounts = {}
        self._account_configs = {}
        
        # HTTP 和 WebSocket 客户端
        self._http_clients = {}
        self._ws_clients = {}
        self._ws_tasks = {}
        self._running = False
        
        # 转换器
        self.converter = None
        
        # 默认配置
        self.config = self._get_config()
        
        self.logger.info("YunhuUserAdapter 初始化完成")
    
    def _get_config(self) -> Dict[str, Any]:
        """
        获取适配器配置
        
        :return: 配置字典
        """
        if not self.config_manager:
            return {}
        
        config = self.config_manager.getConfig("YunhuUserAdapter", {})
        
        if config is None:
            default_config = {
                "ws_reconnect_interval": 30,
                "ws_timeout": 70,
                "accounts": {
                    "default": {
                        "email": "your_email@example.com",
                        "password": "your_password",
                        "platform": "windows",
                        "device_id": "",
                        "enabled": True
                    }
                }
            }
            self.config_manager.setConfig("YunhuUserAdapter", default_config)
            self.logger.info("已写入默认配置和默认账户模板，请修改 config.toml 中的账户信息")
            return default_config
        
        # 确保配置值为正确的类型
        if "ws_reconnect_interval" in config:
            val = config["ws_reconnect_interval"]
            if isinstance(val, str):
                config["ws_reconnect_interval"] = int(val)
        
        if "ws_timeout" in config:
            val = config["ws_timeout"]
            if isinstance(val, str):
                config["ws_timeout"] = int(val)
        
        return config
    
    def _load_accounts(self) -> None:
        """
        加载账户配置
        
        从配置文件中读取账户信息
        """
        self._account_configs.clear()
        
        # 读取账户配置
        full_config = self.config_manager.getConfig("YunhuUserAdapter", {})
        
        self.logger.debug(f"全量配置: {full_config}")

        # 支持嵌套结构：{'accounts': {'default': {...}}}
        accounts_config = full_config.get("accounts", {})
        
        for key, value in full_config.items():
            if key.startswith("accounts.") and isinstance(value, dict):
                accounts_config[key.split(".", 1)[1]] = value
        
        for account_name, value in accounts_config.items():
            if not isinstance(value, dict):
                continue
                
            # 检查是否启用
            if value.get("enabled", True):
                account_config = AccountConfig(
                    email=value.get("email", ""),
                    password=value.get("password", ""),
                    platform=value.get("platform", "windows"),
                    device_id=value.get("device_id", ""),
                    enabled=value.get("enabled", True)
                )
                
                if account_config.email and account_config.password:
                    self._account_configs[account_name] = account_config
                    self.logger.info(f"加载账户: {account_name} ({account_config.email})")
    
    async def _login_account(self, account_name: str, account_config: AccountConfig) -> Optional[str]:
        """
        登录账户并获取 token 和 user_id
        
        :param account_name: 账户名称
        :param account_config: 账户配置
        :return: 用户 ID，失败返回 None
        """
        http_client = None
        try:
            self.logger.info(f"正在登录账户: {account_name} ({account_config.email})")
            
            # 创建 HTTP 客户端
            http_client = YunhuHTTPClient()
            
            # 登录
            login_response = await http_client.email_login(
                email=account_config.email,
                password=account_config.password,
                device_id=account_config.device_id or uuid.uuid4().hex,
                platform=account_config.platform
            )
            
            self.logger.debug(f"登录响应: {login_response}")

            # 检查登录结果
            if not login_response or login_response.get("code") != 1:
                error_msg = login_response.get("msg", "登录失败") if login_response else "登录失败"
                self.logger.error(f"账户 {account_name} 登录失败: {error_msg}")
                return None
            
            # 获取 token
            token = login_response.get("data", {}).get("token", "")
            if not token:
                self.logger.error(f"账户 {account_name} 未获取到 token")
                return None
            
            # 获取用户信息
            http_client.set_token(token)
            user_info_response = await http_client.get_user_info()

            self.logger.debug(f"用户信息响应: {user_info_response}")
            
            # 获取用户 ID，直接检查 data 是否存在
            data = user_info_response.get("data")
            user_id = data.id if data else ""
            
            # 检查是否成功获取到用户 ID
            if not user_id:
                self.logger.error(f"账户 {account_name} 获取用户信息失败：未获取到用户 ID")
                return None
            
            self.logger.info(f"账户 {account_name} 登录成功，用户ID: {user_id}")
            
            # 保存账户信息
            self.accounts[account_name] = {
                "name": account_name,
                "email": account_config.email,
                "token": token,
                "user_id": user_id,
                "platform": account_config.platform,
                "device_id": account_config.device_id or uuid.uuid4().hex
            }
            
            # 保存 HTTP 客户端
            self._http_clients[account_name] = http_client
            
            return user_id
            
        except Exception as e:
            self.logger.error(f"账户 {account_name} 登录异常: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
        finally:
            # 登录失败时关闭 HTTP 客户端
            if http_client and account_name not in self._http_clients:
                await http_client.close()
    
    async def _handle_ws_event(self, ws_event: Dict[str, Any], account_name: str, account: Dict[str, Any]) -> None:
        """
        处理 WebSocket 事件
        
        :param ws_event: WebSocket 原始事件
        :param account_name: 账户名称
        :param account: 账户信息
        """
        try:
            # 转换事件为 OneBot12 格式
            ob12_event = self.converter.convert(ws_event)
            
            if ob12_event:
                self.logger.debug(f"ob12 事件: {ob12_event}")
                # 填充当前登录用户的 ID
                ob12_event["self"]["user_id"] = account["user_id"]
                
                # 提交事件到适配器系统
                if self.adapter:
                    await self.adapter.emit(ob12_event)
                else:
                    self.logger.warning(f"未设置 adapter，无法提交事件: {ob12_event.get('type')}")
        
        except Exception as e:
            self.logger.error(f"账户 {account_name} 处理 WebSocket 事件失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
    
    async def _ws_listener(self, account_name: str, account: Dict[str, Any]) -> None:
        """
        WebSocket 事件监听器
        
        :param account_name: 账户名称
        :param account: 账户信息
        """
        retry_count = 0
        max_retries = 3
        reconnect_interval = int(self.config.get("ws_reconnect_interval", 30))
        ws_timeout = int(self.config.get("ws_timeout", 70))
        
        while self._running and retry_count < max_retries:
            try:
                self.logger.info(f"账户 {account_name} 正在连接 WebSocket... (尝试 {retry_count + 1}/{max_retries})")
                
                # 创建 WebSocket 客户端
                ws_client = YunhuWSClient(
                    token=account["token"],
                    user_id=account["user_id"],
                    platform=account["platform"],
                    device_id=account["device_id"],
                    timeout=ws_timeout,
                    decode=True,
                    mode="black",
                    blacklist=["heartbeat_ack"]
                )
                
                self._ws_clients[account_name] = ws_client
                
                # 连接并监听事件
                async for ws_event in ws_client.connect():
                    if not self._running:
                        break
                    
                    asyncio.create_task(
                        self._handle_ws_event(ws_event, account_name, account)
                    )
                
                # 正常退出循环
                break
                
            except Exception as e:
                retry_count += 1
                self.logger.error(f"账户 {account_name} WebSocket 连接异常 (重试 {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries:
                    # 等待重连
                    await asyncio.sleep(reconnect_interval)
                else:
                    self.logger.error(f"账户 {account_name} 达到最大重试次数，停止重连")
                    break
            
            finally:
                # 清理连接
                if account_name in self._ws_clients:
                    self._ws_clients[account_name] = None
                    del self._ws_clients[account_name]
    
    async def start(self) -> None:
        """
        启动适配器
        
        登录所有配置的账户并建立 WebSocket 连接
        """
        if self._running:
            self.logger.warning("适配器已在运行")
            return
        
        self._running = True
        
        # 初始化转换器
        from .Converter import YunhuUserConverter
        self.converter = YunhuUserConverter()
        
        # 加载账户配置
        self._load_accounts()
        
        if not self._account_configs:
            self.logger.warning("没有找到启用的账户配置")
            self._running = False
            return
        
        self.logger.info(f"找到 {len(self._account_configs)} 个启用的账户")
        
        # 登录所有账户
        for account_name, account_config in self._account_configs.items():
            user_id = await self._login_account(account_name, account_config)
            
            if user_id:
                # 启动 WebSocket 监听任务
                account = self.accounts.get(account_name)
                if account:
                    task = asyncio.create_task(self._ws_listener(account_name, account))
                    self._ws_tasks[account_name] = task
                    self.logger.info(f"账户 {account_name} WebSocket 监听任务已启动")
        
        self.logger.info("YunhuUserAdapter 已启动")
    
    async def shutdown(self) -> None:
        """
        关闭适配器
        
        清理所有资源和连接
        """
        self.logger.info("正在关闭 YunhuUserAdapter...")
        
        self._running = False
        
        # 关闭所有 WebSocket 连接
        for account_name, ws_client in list(self._ws_clients.items()):
            try:
                if ws_client:
                    await ws_client.close()
                self.logger.info(f"账户 {account_name} WebSocket 已关闭")
            except Exception as e:
                self.logger.error(f"关闭账户 {account_name} WebSocket 时出错: {e}")
        
        # 关闭所有 HTTP 客户端
        for account_name, http_client in list(self._http_clients.items()):
            try:
                if http_client:
                    await http_client.close()
            except Exception as e:
                self.logger.error(f"关闭账户 {account_name} HTTP 客户端时出错: {e}")
        
        # 取消所有任务
        for account_name, task in list(self._ws_tasks.items()):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                self.logger.info(f"账户 {account_name} 任务已取消")
        
        # 清理资源
        self._ws_clients.clear()
        self._http_clients.clear()
        self._ws_tasks.clear()
        self.accounts.clear()
        
        self.logger.info("YunhuUserAdapter 已关闭")
    
    def _get_account_by_user_id(self, user_id: str) -> Optional[str]:
        """
        根据 user_id 查找账户
        
        :param user_id: 用户 ID
        :return: 账户名称
        """
        for account_name, account in self.accounts.items():
            if account.get("user_id") == user_id:
                return account_name
        return None
    
    def _get_account_by_id(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        根据账户 ID（名称或 user_id）查找账户
        
        :param account_id: 账户 ID
        :return: 账户信息
        """
        # 直接查找账户名称
        if account_id in self.accounts:
            return self.accounts[account_id]
        
        # 根据 user_id 查找
        return next((acc for acc in self.accounts.values() if acc.get("user_id") == account_id), None)
    
    def _get_http_client(self, account_name: str) -> Optional[YunhuHTTPClient]:
        """获取指定账户的 HTTP 客户端"""
        return self._http_clients.get(account_name)

    async def call_api(self, endpoint: str, **params) -> Dict[str, Any]:
        """
        调用平台 API

        :param endpoint: API 端点
        :param params: 参数
        :return: OneBot12 标准响应
        """
        try:
            # 获取账户
            account_id = params.get("account_id")
            account = self._get_account_by_id(account_id) if account_id else None
            if not account:
                # 使用第一个启用的账户
                if self.accounts:
                    account = next(iter(self.accounts.values()))
                else:
                    return {
                        "status": "failed",
                        "retcode": 10003,
                        "data": None,
                        "message_id": "",
                        "message": "没有可用的账户",
                        "yunhu_user_raw": {}
                    }

            # 获取 HTTP 客户端
            account_name = account["name"]
            http_client = self._http_clients.get(account_name)
            if not http_client:
                return {
                    "status": "failed",
                    "retcode": 10003,
                    "data": None,
                    "message_id": "",
                    "message": "HTTP 客户端未初始化",
                    "yunhu_user_raw": {}
                }

            # 根据端点分发处理
            if endpoint == "/send":
                return await self._api_send_message(http_client, account, params)
            elif endpoint == "/edit":
                return await self._api_edit_message(http_client, account, params)
            elif endpoint == "/recall":
                return await self._api_recall_message(http_client, account, params)
            elif endpoint == "/recall_batch":
                return await self._api_recall_batch(http_client, account, params)
            elif endpoint == "/list":
                return await self._api_list_messages(http_client, params)
            elif endpoint == "/list_by_seq":
                return await self._api_list_by_seq(http_client, params)
            elif endpoint == "/list_by_mid_seq":
                return await self._api_list_by_mid_seq(http_client, params)
            elif endpoint == "/list_edit_record":
                return await self._api_list_edit_record(http_client, params)
            elif endpoint == "/button_report":
                return await self._api_button_report(http_client, params)
            else:
                return {
                    "status": "failed",
                    "retcode": 10001,
                    "data": None,
                    "message_id": "",
                    "message": f"不支持的端点: {endpoint}",
                    "yunhu_user_raw": {}
                }

        except Exception as e:
            self.logger.error(f"call_api 调用失败: {e}")
            return {
                "status": "failed",
                "retcode": 34000,
                "data": None,
                "message_id": "",
                "message": str(e),
                "yunhu_user_raw": {}
            }

    async def _api_send_message(self, http_client: YunhuHTTPClient,
                              account: Dict[str, Any],
                              params: Dict[str, Any]) -> Dict[str, Any]:
        """发送消息 API"""
        import uuid

        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        message = params.get("message")

        # 映射 target_type 到 chat_type
        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        # 构建消息内容
        content = {"text": message.get("text", "")}
        if "buttons" in message:
            import json
            content["buttons"] = json.dumps(message["buttons"])
        if "mentioned_id" in message:
            content["mentioned_id"] = message["mentioned_id"]
        if "quote_msg_id" in message:
            content["quote_msg_text"] = ""

        # 发送消息
        response = await http_client.send_message(
            chat_id=target_id,
            chat_type=chat_type,
            msg_id=uuid.uuid4().hex,
            msg_type=message.get("msg_type", 1),
            content=content,
            quote_msg_id=message.get("quote_msg_id"),
            media=message.get("media")
        )

        # 格式化响应
        return ResponseFormatter.from_platform_response(response)

    async def _api_edit_message(self, http_client: YunhuHTTPClient,
                             account: Dict[str, Any],
                             params: Dict[str, Any]) -> Dict[str, Any]:
        """编辑消息 API"""
        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        msg_id = params.get("msg_id")
        text = params.get("text", "")
        content_type = params.get("content_type", "text")

        # 映射 content_type
        from .utils.constants import CONTENT_TYPE_MAP
        ct = CONTENT_TYPE_MAP.get(content_type, 1)

        # 映射 target_type 到 chat_type
        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        response = await http_client.edit_message(
            chat_id=target_id,
            chat_type=chat_type,
            msg_id=msg_id,
            text=text,
            msg_type=ct
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_recall_message(self, http_client: YunhuHTTPClient,
                               account: Dict[str, Any],
                               params: Dict[str, Any]) -> Dict[str, Any]:
        """撤回消息 API"""
        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        msg_id = params.get("msg_id")

        # 映射 target_type 到 chat_type
        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        response = await http_client.recall_message(
            chat_id=target_id,
            chat_type=chat_type,
            msg_id=msg_id
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_recall_batch(self, http_client: YunhuHTTPClient,
                              account: Dict[str, Any],
                              params: Dict[str, Any]) -> Dict[str, Any]:
        """批量撤回消息 API"""
        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        msg_id_list = params.get("msg_id_list", [])

        # 映射 target_type 到 chat_type
        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        response = await http_client.recall_msg_batch(
            chat_id=target_id,
            chat_type=chat_type,
            msg_id_list=msg_id_list
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_messages(self, http_client: YunhuHTTPClient,
                               params: Dict[str, Any]) -> Dict[str, Any]:
        """获取消息列表 API"""
        chat_id = params.get("chat_id")
        chat_type = params.get("chat_type", 2)
        msg_count = params.get("msg_count", 1)
        msg_id = params.get("msg_id", "")

        response = await http_client.list_msg(
            chat_id=chat_id,
            chat_type=chat_type,
            msg_count=msg_count,
            msg_id=msg_id
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_by_seq(self, http_client: YunhuHTTPClient,
                              params: Dict[str, Any]) -> Dict[str, Any]:
        """通过序列获取消息 API"""
        chat_id = params.get("chat_id")
        chat_type = params.get("chat_type", 2)
        msg_start = params.get("msg_start", 0)

        response = await http_client.list_msg_by_seq(
            chat_id=chat_id,
            chat_type=chat_type,
            msg_start=msg_start
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_by_mid_seq(self, http_client: YunhuHTTPClient,
                                   params: Dict[str, Any]) -> Dict[str, Any]:
        """通过消息ID和序列获取消息 API"""
        chat_id = params.get("chat_id")
        chat_type = params.get("chat_type", 2)
        msg_id = params.get("msg_id", "")
        msg_count = params.get("msg_count", 1)
        msg_seq = params.get("msg_seq", -1)

        response = await http_client.list_msg_by_mid_seq(
            chat_id=chat_id,
            chat_type=chat_type,
            msg_id=msg_id,
            msg_count=msg_count,
            msg_seq=msg_seq
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_edit_record(self, http_client: YunhuHTTPClient,
                                   params: Dict[str, Any]) -> Dict[str, Any]:
        """获取消息编辑记录 API"""
        msg_id = params.get("msg_id")
        size = params.get("size", 10)
        page = params.get("page", 1)

        response = await http_client.list_msg_edit_record(
            msg_id=msg_id,
            size=size,
            page=page
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_button_report(self, http_client: YunhuHTTPClient,
                                params: Dict[str, Any]) -> Dict[str, Any]:
        """按钮事件报告 API"""
        chat_id = params.get("chat_id")
        chat_type = params.get("chat_type", 2)
        msg_id = params.get("msg_id")
        user_id = params.get("user_id")
        button_value = params.get("button_value")

        response = await http_client.button_report(
            chat_id=chat_id,
            chat_type=chat_type,
            msg_id=msg_id,
            user_id=user_id,
            button_value=button_value
        )

        return ResponseFormatter.from_platform_response(response)