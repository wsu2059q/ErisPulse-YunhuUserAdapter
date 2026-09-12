import asyncio
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ErisPulse import sdk
from ErisPulse.Core import client
from ErisPulse.Core.Bases import BotAccountConfig

from .client.http import YunhuHTTPClient
from .client.ws import YunhuWSClient
from .Send import Send
from .utils.constants import CHAT_TYPE_MAP
from .utils.response_formatter import ResponseFormatter

try:
    from ErisPulse.runtime.tasks import spawn_background
except ImportError:  # pragma: no cover
    spawn_background = None

__version__ = "4.2.0"

# 软依赖的框架最低版本（运行时检测，仅提示不强制）
MIN_FRAMEWORK_VERSION = (2, 7, 1)


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

    # ==================== Api DSL（用户API，protobuf over HTTP） ====================

    class Api(sdk.BaseAdapter.Api):
        """云湖用户 API 动作实现（基于 full.proto / v1 端点）

        {!--< tips >!--}
        1. chat_type 取值：1=user 2=group 3=bot（详见 utils/constants.py CHAT_TYPE_MAP）
        2. delete_message 等消息操作需要 chat_id + chat_type 上下文
        3. 更多用户API（通讯录/会话/群管理/好友申请等）直接调用 YunhuHTTPClient 方法
        {!--< /tips >!--}
        """

        @property
        def _http(self):
            account_name = self._adapter._resolve_account(self._account_id)[0]
            http_client = self._adapter._http_clients.get(account_name)
            if http_client is None:
                raise RuntimeError(f"账户 {account_name} 的 HTTP 客户端未初始化（未登录？）")
            return http_client

        async def get_self_info(self) -> dict:
            from google.protobuf import json_format

            raw = await self._http.get_user_info()
            data = raw.get("data")
            data_dict = json_format.MessageToDict(data, preserving_proto_field_name=True) if data else {}
            user_id = str(data_dict.get("user_id", "") or data_dict.get("id", ""))
            return self._adapter.make_response(
                data={
                    "user_id": user_id,
                    "user_name": data_dict.get("nickname", ""),
                    "user_displayname": data_dict.get("nickname", ""),
                    "user_avatar": data_dict.get("avatar_url", ""),
                    "yunhu_user_raw": data_dict,
                }
            )

        async def get_user(self, user_id: str) -> dict:
            """获取用户详细信息（POST /user/get-user）"""
            raw = await self._http.get_user(user_id)
            return self._adapter.make_response(data=raw)

        async def edit_nickname(self, nickname: str) -> dict:
            return await self._http.edit_nickname(nickname)

        async def edit_avatar(self, avatar_url: str) -> dict:
            return await self._http.edit_avatar(avatar_url)

        async def get_friend_address_book(self, md5: str = "") -> dict:
            """获取通讯录"""
            return await self._http.friend_address_book(md5)

        async def get_friend_requests(self) -> dict:
            """获取好友/加群申请列表"""
            return await self._http.friend_request_list()

        async def friend_apply(self, user_id: str, description: str = "") -> dict:
            return await self._http.friend_apply(user_id, description)

        async def friend_agree_apply(self, user_id: str, description: str = "") -> dict:
            return await self._http.friend_agree_apply(user_id, description)

        async def friend_ignore_apply(self, user_id: str) -> dict:
            return await self._http.friend_ignore_apply(user_id)

        async def friend_delete(self, user_id: str) -> dict:
            return await self._http.friend_delete(user_id)

        async def get_group_info(self, group_id: str) -> dict:
            return await self._http.group_info(group_id)

        async def get_group_member_list(self, group_id: str, keywords: str = "") -> dict:
            return await self._http.group_member_list(group_id, keywords)

        async def create_group(self, name: str, introduction: str = "", avatar_url: str = "") -> dict:
            return await self._http.create_group(name, introduction, avatar_url)

        async def dismiss_group(self, group_id: str) -> dict:
            return await self._http.dismiss_group(group_id)

        async def group_invite(self, group_id: str, user_ids: list) -> dict:
            return await self._http.group_invite(group_id, user_ids)

        async def group_remove_member(self, group_id: str, user_id: str) -> dict:
            return await self._http.group_remove_member(group_id, user_id)

        async def group_gag_member(self, group_id: str, user_id: str, gag_time: int) -> dict:
            return await self._http.group_gag_member(group_id, user_id, gag_time)

        async def get_group_bot_list(self, group_id: str) -> dict:
            return await self._http.group_bot_list(group_id)

        async def get_conversation_list(self, md5: str = "") -> dict:
            return await self._http.conversation_list(md5)

        async def get_message_list(
            self, chat_id: str, chat_type: int, msg_count: int = 1, msg_id: str = ""
        ) -> dict:
            return await self._http.list_msg(chat_id, int(chat_type), msg_count, msg_id)

        async def delete_message(self, message_id: str, chat_id: str, chat_type: int) -> dict:
            return await self._http.recall_msg(chat_id, int(chat_type), message_id)

        async def button_report(
            self, chat_id: str, chat_type: int, msg_id: str, user_id: str, button_value: str
        ) -> dict:
            return await self._http.button_report(chat_id, int(chat_type), msg_id, user_id, button_value)

        async def get_status(self) -> dict:
            ad = self._adapter
            bots = []
            for name, user_id in ad._user_ids.items():
                bots.append({
                    "self": {"platform": ad.platform, "user_id": user_id, "account_id": name},
                    "online": name in ad._ws_tasks,
                })
            return ad.make_response(data={"good": any(b["online"] for b in bots), "bots": bots})

        async def get_version(self) -> dict:
            from . import __version__

            return self._adapter.make_response(
                data={"impl": "ErisPulse-YunhuUserAdapter", "version": __version__, "onebot_version": "12"}
            )

        async def get_supported_actions(self) -> dict:
            actions = {
                "get_self_info", "get_user", "edit_nickname", "edit_avatar",
                "get_friend_address_book", "get_friend_requests", "friend_apply",
                "friend_agree_apply", "friend_ignore_apply", "friend_delete",
                "get_group_info", "get_group_member_list", "create_group", "dismiss_group",
                "group_invite", "group_remove_member", "group_gag_member", "get_group_bot_list",
                "get_conversation_list", "get_message_list", "delete_message", "button_report",
                "get_status", "get_version", "get_supported_actions",
            }
            return self._adapter.make_response(data=sorted(actions))

    def __init__(self, sdk_instance=None):
        super().__init__(sdk_instance)

        self.adapter = sdk.adapter
        self._http_clients: Dict[str, YunhuHTTPClient] = {}
        self._ws_clients: Dict[str, YunhuWSClient] = {}
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._user_ids: Dict[str, str] = {}

        self.converter = None
        self._check_framework_version()
        self._get_logger().info(f"YunhuUserAdapter v{__version__} 已加载")

    @staticmethod
    def _parse_version(version_str: str) -> tuple:
        """解析版本号为可比较的三元组（忽略 dev/预发布后缀，如 2.8.0-dev.3 → (2, 8, 0)）"""
        parts = []
        for piece in str(version_str).split("."):
            digits = "".join(ch for ch in piece if ch.isdigit())
            parts.append(int(digits) if digits else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def _check_framework_version(self):
        """软依赖检测：框架版本过低时打警告（不阻断加载）"""
        try:
            from importlib.metadata import version as _pkg_version

            raw = _pkg_version("ErisPulse")
        except Exception:
            return
        try:
            if self._parse_version(raw) < MIN_FRAMEWORK_VERSION:
                self._get_logger().warning(
                    f"当前 ErisPulse 版本 {raw} 过低：YunhuUserAdapter v{__version__} 需要 >= "
                    f"{'.'.join(map(str, MIN_FRAMEWORK_VERSION))}"
                    "（spawn_background 等特性），"
                    "部分功能可能不可用，建议升级框架"
                )
        except Exception:
            pass

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
                coro = self._ws_listener(account_name, account_config)
                # 生命周期任务使用 spawn_background（owner 归属，shutdown 自动回收）
                task = (
                    spawn_background(coro) if spawn_background is not None else asyncio.create_task(coro)
                )
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
