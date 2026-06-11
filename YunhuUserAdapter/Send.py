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
        super().__init__(adapter_obj, target_type, target_id, account_id)
        self._buttons = None
        self._media_handler = None

    def Buttons(self, buttons: List[Dict[str, Any]]) -> "Send":
        self._buttons = buttons
        return self

    def _reset_modifiers(self):
        self._buttons = None

    def _resolve_http_client(self):
        account_name = self._adapter._resolve_to_account_name(self._account_id)
        if account_name:
            return self._adapter._get_http_client(account_name)
        return None

    def _get_media_handler(self) -> MediaHandler:
        if self._media_handler is None:
            http_client = self._resolve_http_client()
            self._media_handler = MediaHandler(http_client, self._adapter.logger)
        return self._media_handler

    def _map_detail_type_to_chat_type(self) -> int:
        return CHAT_TYPE_MAP.get(self._target_type, ChatType.GROUP)

    def _build_send_content(self, quote_text: str = "") -> Dict[str, Any]:
        content = {}

        if self._at_user_ids:
            content["mentioned_id"] = self._at_user_ids

        if self._reply_message_id:
            content["quote_msg_id"] = self._reply_message_id
            if quote_text:
                content["quote_msg_text"] = quote_text

        if self._buttons:
            content["buttons"] = json.dumps(self._buttons)

        return content

    async def _get_quote_text_if_needed(self) -> str:
        if self._reply_message_id:
            return await self._get_quote_message_text(self._reply_message_id)
        return ""

    async def _get_quote_message_text(self, message_id: str) -> str:
        try:
            http_client = self._resolve_http_client()
            if not http_client:
                return ""

            response = await http_client.list_msg_by_mid_seq(
                chat_id=self._target_id,
                chat_type=self._map_detail_type_to_chat_type(),
                msg_id=message_id,
                msg_count=1,
            )

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
        http_client = self._resolve_http_client()
        if not http_client:
            return ResponseFormatter.failed(10003, "没有可用的账户")

        quote_text = await self._get_quote_text_if_needed()

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
        try:
            media_handler = self._get_media_handler()
            process_result = await media_handler.process_file(file, file_type)

            if not process_result:
                return ResponseFormatter.failed(10003, "文件处理失败")

            quote_text = await self._get_quote_text_if_needed()

            send_content = self._build_send_content(quote_text)

            content_field_map = {
                "image": "image",
                "video": "video",
                "audio": "audio",
                "file": "file",
            }
            content_field = content_field_map.get(file_type, "file")
            send_content[content_field] = process_result["key"]

            send_content["file_size"] = process_result["file_size"]

            if file_type == "file" and process_result.get("filename"):
                send_content["file_name"] = process_result["filename"]

            if extra_content:
                send_content.update(extra_content)

            if buttons:
                send_content["buttons"] = json.dumps(buttons)

            http_client = self._resolve_http_client()
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
        if isinstance(a2ui_data, (dict, list)):
            a2ui_str = json.dumps(a2ui_data, ensure_ascii=False)
        else:
            a2ui_str = str(a2ui_data)

        return self.Raw_ob12(
            [{"type": "a2ui", "data": {"a2ui": a2ui_str, "buttons": buttons}}]
        )

    def Edit(self, msg_id: str, text: str, content_type: str = "text") -> asyncio.Task:
        async def _edit():
            http_client = self._resolve_http_client()
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
        async def _recall():
            http_client = self._resolve_http_client()
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
        groups = []
        current_group = []
        text_mergeable_types = ["text", "mention"]

        for segment in message:
            seg_type = segment.get("type", "")

            if seg_type == "reply":
                if not current_group:
                    current_group.append(segment)
                else:
                    current_group.append(segment)
                continue

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

            else:
                if current_group:
                    groups.append(current_group)
                groups.append([segment])
                current_group = []

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

            http_client = self._resolve_http_client()
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
            http_client = self._resolve_http_client()
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
