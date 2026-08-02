import asyncio
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ErisPulse import sdk
from ErisPulse.Core import client
from ErisPulse.runtime.config_schema import BotAccountConfig

from .client.http import YunhuHTTPClient
from .client.ws import YunhuWSClient
from .Send import Send
from .utils.constants import CHAT_TYPE_MAP
from .utils.response_formatter import ResponseFormatter


@dataclass
class YunhuUserAccountConfig(BotAccountConfig):
    """云湖用户账户配置"""

    email: str = field(
        default="",
        metadata={
            "description": "登录邮箱",
            "required": True,
            "ui": {"widget": "text", "group": "basic", "order": 1},
        },
    )
    password: str = field(
        default="",
        metadata={
            "description": "登录密码",
            "required": True,
            "secret": True,
            "ui": {"widget": "password", "group": "basic", "order": 2},
        },
    )
    platform: str = field(
        default="windows",
        metadata={
            "description": "登录平台",
            "ui": {
                "widget": "select",
                "group": "connection",
                "order": 3,
                "options": [
                    {"label": "Windows", "value": "windows"},
                    {"label": "Mac", "value": "mac"},
                    {"label": "Linux", "value": "linux"},
                    {"label": "Android", "value": "android"},
                    {"label": "iOS", "value": "ios"},
                    {"label": "Web", "value": "web"},
                ],
            },
        },
    )
    device_id: str = field(
        default="",
        metadata={
            "description": "设备ID（留空自动生成）",
            "ui": {"widget": "text", "group": "connection", "order": 4},
        },
    )


@dataclass
class YunhuUserAdapterConfig:
    """云湖用户适配器全局配置"""

    ws_reconnect_interval: int = field(
        default=30,
        metadata={
            "description": "WebSocket 重连间隔（秒）",
            "ui": {"widget": "number", "group": "connection", "order": 1},
        },
    )
    ws_timeout: int = field(
        default=70,
        metadata={
            "description": "WebSocket 超时时间（秒）",
            "ui": {"widget": "number", "group": "connection", "order": 2},
        },
    )


class YunhuUserAdapter(sdk.BaseAdapter):
    """
    云湖用户账户驱动适配器

    支持通过用户邮箱账户登录，使用 WebSocket 接收消息事件
    """

    _platform = "yunhu_user"
    AccountConfigClass = YunhuUserAccountConfig
    ConfigClass = YunhuUserAdapterConfig

    Send = Send

    def __init__(self, sdk_instance=None):
        super().__init__(sdk_instance)

        self.adapter = sdk.adapter
        self._http_clients: Dict[str, YunhuHTTPClient] = {}
        self._ws_clients: Dict[str, YunhuWSClient] = {}
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._user_ids: Dict[str, str] = {}

        self.converter = None

    def _get_config_key(self) -> str:
        return "YunhuUserAdapter"

    def _load_accounts(self) -> dict:
        from ErisPulse.runtime.config_schema import dict_to_dataclass
        from ErisPulse.Core.config import config as config_mgr

        key = f"{self._get_config_key()}.accounts"
        data = config_mgr.getConfig(key)

        if not data:
            old_config = config_mgr.getConfig(self._get_config_key())
            if old_config and "accounts" in old_config:
                data = old_config["accounts"]
            else:
                self.logger.info("未找到账户配置，创建默认配置模板")
                data = {
                    "default": {
                        "email": "your_email@example.com",
                        "password": "your_password",
                        "platform": "windows",
                        "device_id": "",
                        "enabled": True,
                    }
                }
                try:
                    config_mgr.setConfig(key, data)
                    self.logger.info("已写入默认配置模板，请修改 config.toml 中的账户信息")
                except Exception as e:
                    self.logger.error(f"保存默认配置失败: {e}")

        accounts = {}
        for name, account_data in data.items():
            if not isinstance(account_data, dict):
                continue

            email = account_data.get("email", "")
            password = account_data.get("password", "")

            template_emails = {"your_email@example.com"}
            template_passwords = {"your_password"}
            if email in template_emails and password in template_passwords:
                self.logger.warning(f"跳过模板账户: {name}，请修改配置")
                continue

            instance = dict_to_dataclass(YunhuUserAccountConfig, account_data)
            instance.name = name
            accounts[name] = instance

        self.logger.info(f"加载 {len(accounts)} 个账户")
        return accounts

    async def _login_account(
        self, account_name: str, account_config: YunhuUserAccountConfig
    ) -> Optional[str]:
        http_client = None
        try:
            self.logger.info(f"正在登录账户: {account_name} ({account_config.email})")

            http_client = YunhuHTTPClient()

            login_response = await http_client.email_login(
                email=account_config.email,
                password=account_config.password,
                device_id=account_config.device_id or uuid.uuid4().hex,
                platform=account_config.platform,
            )

            self.logger.debug(f"登录响应: {login_response}")

            if not login_response or login_response.get("code") != 1:
                error_msg = (
                    login_response.get("msg", "登录失败")
                    if login_response
                    else "登录失败"
                )
                self.logger.error(f"账户 {account_name} 登录失败: {error_msg}")
                return None

            token = login_response.get("data", {}).get("token", "")
            if not token:
                self.logger.error(f"账户 {account_name} 未获取到 token")
                return None

            http_client.set_token(token)
            user_info_response = await http_client.get_user_info()

            self.logger.debug(f"用户信息响应: {user_info_response}")

            data = user_info_response.get("data")
            user_id = data.id if data else ""

            if not user_id:
                self.logger.error(f"账户 {account_name} 获取用户信息失败")
                return None

            self.logger.info(f"账户 {account_name} 登录成功，用户ID: {user_id}")

            self._user_ids[account_name] = str(user_id)
            self._http_clients[account_name] = http_client

            return str(user_id)

        except Exception as e:
            self.logger.error(f"账户 {account_name} 登录异常: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
        finally:
            if http_client and account_name not in self._http_clients:
                await http_client.close()

    async def _handle_ws_event(
        self, ws_event: Dict[str, Any], account_name: str, user_id: str
    ) -> None:
        try:
            ob12_event = self.converter.convert(ws_event)

            if ob12_event:
                self.logger.debug(f"ob12 事件: {ob12_event}")
                ob12_event["self"]["user_id"] = user_id

                if self.adapter:
                    await self.adapter.emit(ob12_event)
                else:
                    self.logger.warning(f"未设置 adapter，无法提交事件")

        except Exception as e:
            self.logger.error(f"账户 {account_name} 处理 WebSocket 事件失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())

    async def _ws_listener(self, account_name: str, account_config: YunhuUserAccountConfig) -> None:
        retry_count = 0
        max_retries = 3
        reconnect_interval = self.config.ws_reconnect_interval if self._config_instance else 30
        ws_timeout = self.config.ws_timeout if self._config_instance else 70

        user_id = self._user_ids.get(account_name, "")
        if not user_id:
            self.logger.error(f"账户 {account_name} 没有有效的 user_id")
            return

        while self._running and retry_count < max_retries:
            try:
                self.logger.info(
                    f"账户 {account_name} 正在连接 WebSocket... (尝试 {retry_count + 1}/{max_retries})"
                )

                ws_client = YunhuWSClient(
                    token=self._http_clients[account_name].token,
                    user_id=user_id,
                    platform=account_config.platform,
                    device_id=account_config.device_id or uuid.uuid4().hex,
                    timeout=ws_timeout,
                    decode=True,
                    mode="black",
                    blacklist=["heartbeat_ack"],
                )

                self._ws_clients[account_name] = ws_client

                await self.emit_meta("connect", user_id)

                async for ws_event in ws_client.connect():
                    if not self._running:
                        break

                    asyncio.create_task(
                        self._handle_ws_event(ws_event, account_name, user_id)
                    )

                if not self._running:
                    break

                retry_count += 1
                self.logger.warning(
                    f"账户 {account_name} WebSocket 连接断开 (重试 {retry_count}/{max_retries})"
                )

                if retry_count < max_retries:
                    await asyncio.sleep(reconnect_interval)
                else:
                    self.logger.error(f"账户 {account_name} 达到最大重试次数")
                    break

            except Exception as e:
                retry_count += 1
                self.logger.error(
                    f"账户 {account_name} WebSocket 连接异常 (重试 {retry_count}/{max_retries}): {e}"
                )

                if retry_count < max_retries:
                    await asyncio.sleep(reconnect_interval)
                else:
                    self.logger.error(f"账户 {account_name} 达到最大重试次数")
                    break

            finally:
                try:
                    await self.emit_meta("disconnect", user_id)
                except Exception:
                    pass
                if account_name in self._ws_clients:
                    del self._ws_clients[account_name]

    async def start(self) -> None:
        if self._running:
            self.logger.warning("适配器已在运行")
            return

        self._running = True

        from .Converter import YunhuUserConverter
        self.converter = YunhuUserConverter()

        enabled = self.enabled_accounts
        if not enabled:
            self.logger.warning("没有找到启用的账户配置")
            self._running = False
            return

        self.logger.info(f"找到 {len(enabled)} 个启用的账户")

        for account_name, account_config in enabled.items():
            user_id = await self._login_account(account_name, account_config)

            if user_id:
                task = asyncio.create_task(self._ws_listener(account_name, account_config))
                self._ws_tasks[account_name] = task
                self.logger.info(f"账户 {account_name} WebSocket 监听任务已启动")

        self.logger.info("YunhuUserAdapter 已启动")

    async def shutdown(self) -> None:
        self.logger.info("正在关闭 YunhuUserAdapter...")

        self._running = False

        for account_name, ws_client in list(self._ws_clients.items()):
            try:
                if ws_client:
                    await ws_client.close()
                self.logger.info(f"账户 {account_name} WebSocket 已关闭")
            except Exception as e:
                self.logger.error(f"关闭账户 {account_name} WebSocket 时出错: {e}")

        for account_name, http_client in list(self._http_clients.items()):
            try:
                if http_client:
                    await http_client.close()
            except Exception as e:
                self.logger.error(f"关闭账户 {account_name} HTTP 客户端时出错: {e}")

        for account_name, task in list(self._ws_tasks.items()):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                self.logger.info(f"账户 {account_name} 任务已取消")

        self._ws_clients.clear()
        self._http_clients.clear()
        self._ws_tasks.clear()
        self._user_ids.clear()

        for account_name, account in self.enabled_accounts.items():
            user_id = self._user_ids.get(account_name, "")
            if user_id:
                try:
                    await self.emit_meta("disconnect", user_id)
                except Exception:
                    pass

        self.logger.info("YunhuUserAdapter 已关闭")

    def _get_account_by_user_id(self, user_id: str) -> Optional[str]:
        for name, uid in self._user_ids.items():
            if uid == user_id:
                return name
        return None

    def _get_http_client(self, account_name: str) -> Optional[YunhuHTTPClient]:
        return self._http_clients.get(account_name)

    def _resolve_to_account_name(self, account_id: Optional[str] = None) -> Optional[str]:
        if account_id is None:
            for name in self._user_ids:
                return name
            return None

        if account_id in self._user_ids:
            return account_id

        return self._get_account_by_user_id(account_id)

    async def call_api(self, endpoint: str, _account_id: str = None, **params) -> Dict[str, Any]:
        try:
            account_name = self._resolve_to_account_name(_account_id)
            if not account_name:
                return self.make_error(retcode=10003, message="没有可用的账户")

            http_client = self._http_clients.get(account_name)
            if not http_client:
                return self.make_error(retcode=10003, message="HTTP 客户端未初始化")

            if endpoint == "/send":
                return await self._api_send_message(http_client, params)
            elif endpoint == "/edit":
                return await self._api_edit_message(http_client, params)
            elif endpoint == "/recall":
                return await self._api_recall_message(http_client, params)
            elif endpoint == "/recall_batch":
                return await self._api_recall_batch(http_client, params)
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
                return self.make_error(retcode=10001, message=f"不支持的端点: {endpoint}")

        except Exception as e:
            self.logger.error(f"call_api 调用失败: {e}")
            return self.make_error(retcode=34000, message=str(e))

    async def _api_send_message(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        import uuid

        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        message = params.get("message")

        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        content = {"text": message.get("text", "")}
        if "buttons" in message:
            import json
            content["buttons"] = json.dumps(message["buttons"])
        if "mentioned_id" in message:
            content["mentioned_id"] = message["mentioned_id"]
        if "quote_msg_id" in message:
            content["quote_msg_text"] = ""

        response = await http_client.send_message(
            chat_id=target_id,
            chat_type=chat_type,
            msg_id=uuid.uuid4().hex,
            msg_type=message.get("msg_type", 1),
            content=content,
            quote_msg_id=message.get("quote_msg_id"),
            media=message.get("media"),
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_edit_message(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        from .utils.constants import CONTENT_TYPE_MAP

        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        msg_id = params.get("msg_id")
        text = params.get("text", "")
        content_type = params.get("content_type", "text")

        ct = CONTENT_TYPE_MAP.get(content_type, 1)
        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        response = await http_client.edit_message(
            chat_id=target_id,
            chat_type=chat_type,
            msg_id=msg_id,
            text=text,
            msg_type=ct,
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_recall_message(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        msg_id = params.get("msg_id")

        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        response = await http_client.recall_message(
            chat_id=target_id, chat_type=chat_type, msg_id=msg_id
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_recall_batch(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        target_type = params.get("target_type", "group")
        target_id = params.get("target_id")
        msg_id_list = params.get("msg_id_list", [])

        chat_type = CHAT_TYPE_MAP.get(target_type, 2)

        response = await http_client.recall_msg_batch(
            chat_id=target_id, chat_type=chat_type, msg_id_list=msg_id_list
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_messages(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        chat_id = params.get("chat_id")
        chat_type = params.get("chat_type", 2)
        msg_count = params.get("msg_count", 1)
        msg_id = params.get("msg_id", "")

        response = await http_client.list_msg(
            chat_id=chat_id, chat_type=chat_type, msg_count=msg_count, msg_id=msg_id
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_by_seq(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        chat_id = params.get("chat_id")
        chat_type = params.get("chat_type", 2)
        msg_start = params.get("msg_start", 0)

        response = await http_client.list_msg_by_seq(
            chat_id=chat_id, chat_type=chat_type, msg_start=msg_start
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_by_mid_seq(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            msg_seq=msg_seq,
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_list_edit_record(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        msg_id = params.get("msg_id")
        size = params.get("size", 10)
        page = params.get("page", 1)

        response = await http_client.list_msg_edit_record(
            msg_id=msg_id, size=size, page=page
        )

        return ResponseFormatter.from_platform_response(response)

    async def _api_button_report(
        self, http_client: YunhuHTTPClient, params: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            button_value=button_value,
        )

        return ResponseFormatter.from_platform_response(response)
