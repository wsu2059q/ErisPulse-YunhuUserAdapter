import asyncio
import uuid
import json
from typing import Union, Optional, List, Dict, Any

from .utils.constants import MessageTypes, ChatType, CHAT_TYPE_MAP, CONTENT_TYPE_MAP
from .utils.response_formatter import ResponseFormatter
from .utils.media_handler import MediaHandler
from ErisPulse.Core.Bases import BaseAdapter


class Send(BaseAdapter.Send):
    def __init__(
        self,
        adapter_obj,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        self._adapter = adapter_obj
        self._target_type = target_type
        self._target_id = target_id
        self._account_id = account_id

        # 链式修饰属性
        self._at_user_ids = []
        self._at_all = False
        self._reply_message_id = None
        self._buttons = None

        # 初始化媒体处理器
        self._media_handler = None

    def At(self, user_id: str) -> "Send":
        if user_id not in self._at_user_ids:
            self._at_user_ids.append(user_id)
        return self

    def AtAll(self) -> "Send":
        self._at_all = True
        return self

    def Reply(self, message_id: str) -> "Send":
        self._reply_message_id = message_id
        return self

    def Buttons(self, buttons: List[Dict[str, Any]]) -> "Send":
        self._buttons = buttons
        return self

    def _get_account(self) -> Optional[Dict[str, Any]]:
        """
        获取当前账户
        """
        if self._account_id:
            return self._adapter._get_account_by_id(self._account_id)

        if self._adapter.accounts:
            return next(iter(self._adapter.accounts.values()))

        return None

    def _get_http_client(self):
        """获取当前账户的 HTTP 客户端"""
        from .client.http import YunhuHTTPClient

        account = self._get_account()
        if account:
            account_name = account["name"]
            return self._adapter._get_http_client(account_name)
        return None

    def _get_media_handler(self) -> MediaHandler:
        """
        获取或创建媒体处理器
        """
        if self._media_handler is None:
            http_client = self._get_http_client()
            self._media_handler = MediaHandler(http_client, self._adapter.logger)
        return self._media_handler

    def _map_detail_type_to_chat_type(self) -> int:
        """
        将 OneBot12 detail_type 映射到云湖 chat_type

        :return: 云湖 chat_type
        """
        return CHAT_TYPE_MAP.get(self._target_type, ChatType.GROUP)

    def _build_send_content(self, quote_text: str = "") -> Dict[str, Any]:
        """
        构建发送消息内容

        :param quote_text: 引用消息的文本（如果需要回复）
        :return: 消息内容字典
        """
        content = {}

        # 添加 @用户
        if self._at_user_ids:
            content["mentioned_id"] = self._at_user_ids

        # 添加回复
        if self._reply_message_id:
            content["quote_msg_id"] = self._reply_message_id
            # 使用传入的引用文本
            if quote_text:
                content["quote_msg_text"] = quote_text

        # 添加按钮
        if self._buttons:
            content["buttons"] = json.dumps(self._buttons)

        return content

    async def _get_quote_text_if_needed(self) -> str:
        """
        如果需要回复消息，获取被引用消息的真实文本

        :return: 引用消息文本，如果不需要回复则返回空字符串
        """
        if self._reply_message_id:
            return await self._get_quote_message_text(self._reply_message_id)
        return ""

    async def _get_quote_message_text(self, message_id: str) -> str:
        """
        获取被引用消息的文本内容

        :param message_id: 消息 ID
        :return: 消息文本内容
        """
        try:
            http_client = self._get_http_client()
            if not http_client:
                return ""

            response = await http_client.list_msg_by_mid_seq(
                chat_id=self._target_id,
                chat_type=self._map_detail_type_to_chat_type(),
                msg_id=message_id,
                msg_count=1,
            )

            # 解析响应获取消息文本
            if response and response.get("status", {}).get("code") == 1:
                messages = response.get("msg", [])
                if messages and len(messages) > 0:
                    msg = messages[0]
                    content = msg.get("content", {})
                    text = content.get("text", "")
                    return text

            return ""
        except Exception as e:
            self._adapter.logger.error(f"获取引用消息文本失败: {e}")
            return ""

    async def _send_text_like(
        self, text: str, msg_type: int, buttons: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        统一发送文本类消息

        :param text: 文本内容
        :param msg_type: 消息类型
        :param buttons: 按钮列表
        :return: 发送结果
        """
        http_client = self._get_http_client()
        if not http_client:
            return ResponseFormatter.failed(10003, "没有可用的账户")

        # 获取引用消息的真实文本
        quote_text = await self._get_quote_text_if_needed()

        # 构建发送数据
        send_content = self._build_send_content(quote_text)
        send_content["text"] = text
        if buttons:
            send_content["buttons"] = json.dumps(buttons)

        try:
            msg_id = uuid.uuid4().hex
            response = await http_client.send_message(
                chat_id=self._target_id,
                chat_type=self._map_detail_type_to_chat_type(),
                msg_id=msg_id,
                msg_type=msg_type,
                content=send_content,
                quote_msg_id=self._reply_message_id,
                media=None,
            )
            return ResponseFormatter.from_platform_response(response, msg_id)
        except Exception as e:
            self._adapter.logger.error(f"发送文本类消息失败: {e}")
            return ResponseFormatter.error(e)

    async def _send_media(
        self,
        file: Union[str, bytes],
        file_type: str,
        msg_type: int,
        extra_content: Optional[Dict] = None,
        buttons: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        统一发送媒体消息

        :param file: 文件 URL 或二进制数据
        :param file_type: 文件类型
        :param msg_type: 消息类型
        :param extra_content: 额外内容（如 file_size, audio_time 等）
        :param buttons: 按钮列表
        :return: 发送结果
        """
        try:
            # 处理文件
            media_handler = self._get_media_handler()
            process_result = await media_handler.process_file(file, file_type)

            if not process_result:
                return ResponseFormatter.failed(10003, "文件处理失败")

            # 获取引用消息的真实文本
            quote_text = await self._get_quote_text_if_needed()

            # 构建发送内容
            send_content = self._build_send_content(quote_text)

            # 根据文件类型设置内容字段
            content_field_map = {
                "image": "image",
                "video": "video",
                "audio": "audio",
                "file": "file",
            }
            content_field = content_field_map.get(file_type, "file")
            send_content[content_field] = process_result["key"]

            # 自动添加文件大小
            send_content["file_size"] = process_result["file_size"]

            # 自动添加文件名（仅文件类型）
            if file_type == "file" and process_result.get("filename"):
                send_content["file_name"] = process_result["filename"]

            # 添加额外内容（允许覆盖自动检测的值）
            if extra_content:
                send_content.update(extra_content)

            # 添加按钮
            if buttons:
                send_content["buttons"] = json.dumps(buttons)

            # 发送消息
            http_client = self._get_http_client()
            msg_id = uuid.uuid4().hex
            response = await http_client.send_message(
                chat_id=self._target_id,
                chat_type=self._map_detail_type_to_chat_type(),
                msg_id=msg_id,
                msg_type=msg_type,
                content=send_content,
                quote_msg_id=self._reply_message_id,
                media=None,
            )

            return ResponseFormatter.from_platform_response(response, msg_id)

        except Exception as e:
            self._adapter.logger.error(f"发送媒体消息失败: {e}")
            return ResponseFormatter.error(e)

    # ============ 公开发送方法（委托给 Raw_ob12） ============

    def Text(self, text: str, buttons: Optional[List] = None) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "text", "data": {"text": text, "buttons": buttons}}]
        )

    def Html(self, html: str, buttons: Optional[List] = None) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "html", "data": {"html": html, "buttons": buttons}}]
        )

    def Markdown(self, markdown: str, buttons: Optional[List] = None) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "markdown", "data": {"markdown": markdown, "buttons": buttons}}]
        )

    def Image(
        self, file: Union[str, bytes], buttons: Optional[List] = None
    ) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "image", "data": {"file": file, "buttons": buttons}}]
        )

    def Video(
        self, file: Union[str, bytes], buttons: Optional[List] = None
    ) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "video", "data": {"file": file, "buttons": buttons}}]
        )

    def Audio(
        self, file: Union[str, bytes], buttons: Optional[List] = None
    ) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "audio", "data": {"file": file, "buttons": buttons}}]
        )

    def Voice(
        self, file: Union[str, bytes], buttons: Optional[List] = None
    ) -> asyncio.Task:
        return self.Audio(file, buttons)

    def File(
        self,
        file: Union[str, bytes],
        file_name: Optional[str] = None,
        buttons: Optional[List] = None,
    ) -> asyncio.Task:
        return self.Raw_ob12(
            [
                {
                    "type": "file",
                    "data": {"file": file, "file_name": file_name, "buttons": buttons},
                }
            ]
        )

    def Face(
        self, file: Union[str, bytes], buttons: Optional[List] = None
    ) -> asyncio.Task:
        return self.Raw_ob12(
            [{"type": "face", "data": {"file": file, "buttons": buttons}}]
        )

    def A2ui(self, a2ui_data: Union[str, Dict, List], buttons: Optional[List] = None) -> asyncio.Task:
        """
        发送 A2UI 消息（消息类型14）

        A2UI JSON 数据会填入 text 字段发送

        :param a2ui_data: A2UI JSON 数据（字符串、字典或列表）
        :param buttons: 按钮列表
        :return: asyncio.Task
        """
        if isinstance(a2ui_data, (dict, list)):
            a2ui_str = json.dumps(a2ui_data, ensure_ascii=False)
        else:
            a2ui_str = str(a2ui_data)

        return self.Raw_ob12(
            [{"type": "a2ui", "data": {"a2ui": a2ui_str, "buttons": buttons}}]
        )

    def Edit(self, msg_id: str, text: str, content_type: str = "text") -> asyncio.Task:
        """
        编辑消息

        :param msg_id: 消息 ID
        :param text: 新消息内容
        :param content_type: 内容类型
        :return: asyncio.Task
        """

        async def _edit():
            http_client = self._get_http_client()
            if not http_client:
                return ResponseFormatter.failed(10003, "没有可用的账户")

            try:
                msg_type = CONTENT_TYPE_MAP.get(content_type, MessageTypes.TEXT)

                response = await http_client.edit_message(
                    chat_id=self._target_id,
                    chat_type=self._map_detail_type_to_chat_type(),
                    msg_id=msg_id,
                    text=text,
                    msg_type=msg_type,
                    quote_msg_id=self._reply_message_id
                    if self._reply_message_id
                    else None,
                    buttons=json.dumps(self._buttons) if self._buttons else None,
                )

                return ResponseFormatter.from_platform_response(response)

            except Exception as e:
                self._adapter.logger.error(f"编辑消息失败: {e}")
                return ResponseFormatter.error(e)

        return asyncio.create_task(_edit())

    def Recall(self, msg_id: str) -> asyncio.Task:
        """
        撤回消息

        :param msg_id: 消息 ID
        :return: asyncio.Task
        """

        async def _recall():
            http_client = self._get_http_client()
            if not http_client:
                return ResponseFormatter.failed(10003, "没有可用的账户")

            try:
                response = await http_client.recall_message(
                    chat_id=self._target_id,
                    chat_type=self._map_detail_type_to_chat_type(),
                    msg_id=msg_id,
                )
                return ResponseFormatter.from_platform_response(response)

            except Exception as e:
                self._adapter.logger.error(f"撤回消息失败: {e}")
                return ResponseFormatter.error(e)

        return asyncio.create_task(_recall())

    def Raw_ob12(self, message: Union[List, Dict]) -> asyncio.Task:
        if isinstance(message, dict):
            message = [message]

        grouped_messages = self._group_ob12_messages(message)

        async def _send_grouped_messages():
            results = []
            for msg_group in grouped_messages:
                result = await self._send_ob12_group(msg_group)
                results.append(result)
            self._reset_modifiers()
            return results[-1] if results else None

        return asyncio.create_task(_send_grouped_messages())

    def _group_ob12_messages(self, message: List[Dict]) -> List[List[Dict]]:
        """
        将 OneBot12 消息段数组分组

        :param message: OneBot12 消息段数组
        :return: 分组后的消息段数组列表
        """
        groups = []
        current_group = []

        # 定义可以合并到文本组的消息类型
        text_mergeable_types = ["text", "mention"]

        for segment in message:
            seg_type = segment.get("type", "")

            # 回复消息可以附加到任何组
            if seg_type == "reply":
                if not current_group:
                    current_group.append(segment)
                else:
                    current_group.append(segment)
                continue

            # 文本消息、@可以合并
            if seg_type in text_mergeable_types:
                if not current_group or all(
                    s.get("type") in text_mergeable_types or s.get("type") == "reply"
                    for s in current_group
                ):
                    current_group.append(segment)
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [segment]

            # 其他消息类型单独成组
            else:
                if current_group:
                    groups.append(current_group)
                groups.append([segment])
                current_group = []

        # 保存最后一组
        if current_group:
            groups.append(current_group)

        return groups

    async def _send_ob12_group(self, msg_group: List[Dict]) -> Dict:
        if not msg_group:
            return None

        first_segment = msg_group[0]
        seg_type = first_segment.get("type", "")

        reply_message_id = None
        for segment in msg_group:
            if segment.get("type") == "reply":
                reply_message_id = segment.get("data", {}).get("message_id")
                break

        old_reply_id = self._reply_message_id
        if reply_message_id:
            self._reply_message_id = reply_message_id
        old_buttons = self._buttons
        final_buttons = self._buttons
        seg_data = first_segment.get("data", {})
        if final_buttons is None and "buttons" in seg_data:
            final_buttons = seg_data["buttons"]

        try:
            if seg_type in ["text", "mention"]:
                text_parts = []
                for segment in msg_group:
                    s_type = segment.get("type", "")
                    s_data = segment.get("data", {})
                    if s_type == "text":
                        text_parts.append(s_data.get("text", ""))
                    elif s_type == "mention":
                        user_id = s_data.get("user_id", "")
                        text_parts.append(f"@{user_id}")

                if self._at_user_ids:
                    at_text = " ".join([f"@{uid}" for uid in self._at_user_ids])
                    text_parts.insert(0, at_text)

                text = " ".join(text_parts) or " "
                return await self._send_text_like(
                    text, MessageTypes.TEXT, final_buttons
                )

            if seg_type == "image":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._send_media(
                    file_url, "image", MessageTypes.IMAGE, buttons=final_buttons
                )

            elif seg_type == "audio":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._send_audio(file_url, buttons=final_buttons)

            elif seg_type == "video":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._send_media(
                    file_url, "video", MessageTypes.VIDEO, buttons=final_buttons
                )

            elif seg_type == "file":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                file_name = seg_data.get("file_name", "")
                extra_content = {"file_name": file_name} if file_name else {}
                return await self._send_media(
                    file_url, "file", MessageTypes.FILE, extra_content, final_buttons
                )

            elif seg_type == "markdown":
                markdown_text = seg_data.get("markdown", "")
                return await self._send_text_like(
                    markdown_text, MessageTypes.MARKDOWN, final_buttons
                )

            elif seg_type == "html":
                html_text = seg_data.get("html", "")
                return await self._send_text_like(
                    html_text, MessageTypes.HTML, final_buttons
                )

            elif seg_type == "face":
                file = seg_data.get("file", "")
                return await self._send_face(file, buttons=final_buttons)

            elif seg_type == "a2ui":
                a2ui_str = seg_data.get("a2ui", "")
                return await self._send_text_like(
                    a2ui_str, MessageTypes.A2UI, final_buttons
                )

            elif seg_type == "reply":
                return await self._send_text_like("", MessageTypes.TEXT, final_buttons)

            elif seg_type.startswith("yunhu_"):
                return await self._send_text_like(
                    str(seg_data), MessageTypes.TEXT, final_buttons
                )

            else:
                return await self._send_text_like(
                    str(seg_data), MessageTypes.TEXT, final_buttons
                )
        finally:
            self._reply_message_id = old_reply_id
            self._buttons = old_buttons

    def _reset_modifiers(self):
        self._at_user_ids = []
        self._at_all = False
        self._reply_message_id = None
        self._buttons = None

    async def _send_audio(self, file, buttons: Optional[List] = None) -> Dict[str, Any]:
        try:
            media_handler = self._get_media_handler()
            process_result = await media_handler.process_file(file, "audio")

            if not process_result:
                return ResponseFormatter.failed(10003, "文件处理失败")

            file_data = None
            if isinstance(file, bytes):
                file_data = file
            else:
                file_data = await media_handler._download_file(file)

            audio_time = 0
            if file_data:
                audio_time = await media_handler.get_audio_duration(file_data)

            quote_text = await self._get_quote_text_if_needed()
            send_content = self._build_send_content(quote_text)
            send_content["audio"] = process_result["key"]
            send_content["audio_time"] = audio_time
            send_content["file_size"] = process_result["file_size"]

            if buttons:
                send_content["buttons"] = json.dumps(buttons)

            http_client = self._get_http_client()
            msg_id = uuid.uuid4().hex
            response = await http_client.send_message(
                chat_id=self._target_id,
                chat_type=self._map_detail_type_to_chat_type(),
                msg_id=msg_id,
                msg_type=MessageTypes.AUDIO,
                content=send_content,
                quote_msg_id=self._reply_message_id,
                media=None,
            )

            return ResponseFormatter.from_platform_response(response, msg_id)
        except Exception as e:
            self._adapter.logger.error(f"发送语音消息失败: {e}")
            return ResponseFormatter.error(e)

    async def _send_face(self, file, buttons: Optional[List] = None) -> Dict[str, Any]:
        try:
            http_client = self._get_http_client()
            if not http_client:
                return ResponseFormatter.failed(10003, "没有可用的账户")

            quote_text = await self._get_quote_text_if_needed()
            send_content = self._build_send_content(quote_text)

            if isinstance(file, str) and file.startswith(("http://", "https://")):
                send_content["sticker_url"] = file
            elif isinstance(file, str):
                send_content["expression_id"] = file
            elif isinstance(file, bytes):
                media_handler = self._get_media_handler()
                process_result = await media_handler.process_file(file, "image")
                if not process_result:
                    return ResponseFormatter.failed(10003, "文件处理失败")
                send_content["sticker_url"] = process_result["key"]
            else:
                return ResponseFormatter.failed(10003, "不支持的文件格式")

            if buttons:
                send_content["buttons"] = json.dumps(buttons)

            msg_id = uuid.uuid4().hex
            response = await http_client.send_message(
                chat_id=self._target_id,
                chat_type=self._map_detail_type_to_chat_type(),
                msg_id=msg_id,
                msg_type=MessageTypes.STICKER,
                content=send_content,
                quote_msg_id=self._reply_message_id,
                media=None,
            )

            return ResponseFormatter.from_platform_response(response, msg_id)
        except Exception as e:
            self._adapter.logger.error(f"发送表情消息失败: {e}")
            return ResponseFormatter.error(e)
