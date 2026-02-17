import time
import uuid
from typing import Optional, Dict, Any, List
from .proto import ws_pb2 as ws_pb2


class YunhuUserConverter:
    
    def convert(self, ws_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        将云湖 WebSocket 事件转换为 OneBot12 标准格式

        :param ws_event: 云湖 WebSocket 原始事件
        :return: OneBot12 标准事件，如果不支持的事件类型则返回 None
        """
        if not isinstance(ws_event, dict):
            return None

        info = ws_event.get("info", {})
        cmd = info.get("cmd", "")

        # 根据命令类型分发处理
        if cmd == "push_message":
            return self._convert_message(ws_event)
        elif cmd == "edit_message":
            return self._convert_edit_notice(ws_event)
        elif cmd == "file_send_message":
            return self._convert_file_send_message(ws_event)
        elif cmd == "bot_board_message":
            return self._convert_bot_board_message(ws_event)
        # 暂时注释掉流式消息处理（stream_message），因为频繁发送造成困扰
        # elif cmd == "stream_message":
        #     return self._convert_stream_message(ws_event)
        # draft_input 暂不处理（非必要功能）
        else:
            # 不支持的事件类型
            return None
    
    def _convert_message(self, ws_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换推送消息事件为 OneBot12 message 事件
        
        :param ws_event: push_message 事件
        :return: OneBot12 message 事件
        """
        data = ws_event.get("data", {})
        msg = data.get("msg", {})
        info = ws_event.get("info", {})
        
        # 提取基本信息
        chat_type = msg.get("chat_type", 1)  # 1=user, 2=group, 3=bot
        chat_id = msg.get("chat_id", "")
        content_type = msg.get("content_type", 1)
        content = msg.get("content", {})
        sender = msg.get("sender", {})
        
        # 时间戳转换（毫秒转秒）
        timestamp = int(int(msg.get("timestamp", time.time() * 1000)) / 1000)
        
        # 转换 detail_type
        detail_type = self._map_chat_type(chat_type)
        
        # 构建消息段
        message_segments = self._convert_content_to_segments(content, content_type, msg)
        alt_message = self._build_alt_message(message_segments)
        
        # 提取发送者信息
        user_id = sender.get("chat_id", "")
        user_nickname = sender.get("name", "")
        
        # 构建 OneBot12 事件
        ob12_event = {
            "id": self._generate_event_id(msg),
            "time": int(time.time()),
            "type": "message",
            "detail_type": detail_type,
            "platform": "yunhu_user",
            "self": {
                "platform": "yunhu_user",
                "user_id": ""  # 由适配器填充为当前登录用户ID
            },
            "message": message_segments,
            "alt_message": alt_message,
            "user_id": user_id,
            "user_nickname": user_nickname,
            "yunhu_user_raw": ws_event,
            "yunhu_user_raw_type": "push_message"
        }
        
        # 群聊消息添加 group_id
        if detail_type == "group":
            ob12_event["group_id"] = chat_id
        elif detail_type == "bot":
            ob12_event["bot_id"] = chat_id
        
        # 消息ID
        message_id = msg.get("msg_id", "")
        if message_id:
            ob12_event["message_id"] = message_id
        
        return ob12_event
    
    def _convert_edit_notice(self, ws_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换编辑消息事件为 OneBot12 notice 事件
        
        :param ws_event: edit_message 事件
        :return: OneBot12 notice 事件
        """
        data = ws_event.get("data", {})
        msg = data.get("msg", {})
        info = ws_event.get("info", {})
        
        # 提取基本信息
        message_id = msg.get("msg_id", "")
        chat_type = msg.get("chat_type", 1)
        chat_id = msg.get("chat_id", "")
        sender = msg.get("sender", {})
        
        # 提取编辑者信息
        user_id = sender.get("chat_id", "")
        user_nickname = sender.get("name", "")
        
        # 编辑时间
        edit_time = int(int(msg.get("edit_time", time.time() * 1000)) / 1000)
        
        # 转换 detail_type
        detail_type = self._map_chat_type(chat_type)
        
        # 构建 OneBot12 事件
        ob12_event = {
            "id": self._generate_event_id(ws_event),
            "time": int(time.time()),
            "type": "notice",
            "detail_type": "message_edit",
            "platform": "yunhu_user",
            "self": {
                "platform": "yunhu_user",
                "user_id": ""  # 由适配器填充
            },
            "message_id": message_id,
            "user_id": user_id,
            "user_nickname": user_nickname,
            "edit_time": edit_time,
            "yunhu_user_raw": ws_event,
            "yunhu_user_raw_type": "edit_message"
        }
        
        # 添加位置信息
        if detail_type == "group":
            ob12_event["group_id"] = chat_id
        elif detail_type == "bot":
            ob12_event["bot_id"] = chat_id
        
        return ob12_event
    
    def _convert_recall_notice(self, ws_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换撤回消息事件为 OneBot12 notice 事件
        
        :param ws_event: recall_msg 事件
        :return: OneBot12 notice 事件
        """
        data = ws_event.get("data", {})
        msg = data.get("msg", {})
        info = ws_event.get("info", {})
        
        # 提取基本信息
        message_id = msg.get("msg_id", "")
        chat_type = msg.get("chat_type", 1)
        chat_id = msg.get("chat_id", "")
        sender = msg.get("sender", {})
        
        # 提取撤回者信息
        user_id = sender.get("chat_id", "")
        user_nickname = sender.get("name", "")
        
        # 撤回时间
        delete_time = int(int(msg.get("delete_time", time.time() * 1000)) / 1000)
        
        # 转换 detail_type
        detail_type = self._map_chat_type(chat_type)
        
        # 构建 OneBot12 事件
        ob12_event = {
            "id": self._generate_event_id(ws_event),
            "time": int(time.time()),
            "type": "notice",
            "detail_type": "message_delete",
            "platform": "yunhu_user",
            "self": {
                "platform": "yunhu_user",
                "user_id": ""  # 由适配器填充
            },
            "message_id": message_id,
            "user_id": user_id,
            "user_nickname": user_nickname,
            "delete_time": delete_time,
            "yunhu_user_raw": ws_event,
            "yunhu_user_raw_type": "recall_msg"
        }
        
        # 添加位置信息
        if detail_type == "group":
            ob12_event["group_id"] = chat_id
        elif detail_type == "bot":
            ob12_event["bot_id"] = chat_id
        
        return ob12_event
    
    def _convert_content_to_segments(
        self, 
        content: Dict[str, Any], 
        content_type: int,
        msg: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        将云湖消息内容转换为 OneBot12 消息段
        
        :param content: 云湖消息内容
        :param content_type: 内容类型
        :param msg: 完整消息对象
        :return: OneBot12 消息段列表
        """
        segments = []
        
        # 文本消息
        if content_type == 1:
            text = content.get("text", "")
            if text:
                segments.append({"type": "text", "data": {"text": text}})
        
        # 图片消息
        elif content_type == 2:
            image_url = content.get("image_url", "")
            if image_url:
                segments.append({"type": "image", "data": {"file_id": image_url}})
        
        # Markdown 消息
        elif content_type == 3:
            markdown = content.get("text", "")
            if markdown:
                segments.append({"type": "text", "data": {"text": markdown}})
        
        # 文件消息
        elif content_type == 4:
            file_url = content.get("file_url", "")
            file_name = content.get("file_name", "")
            file_size = content.get("file_size", 0)
            if file_url:
                segments.append({
                    "type": "file",
                    "data": {
                        "file_id": file_url,
                        "file_name": file_name,
                        "file_size": file_size
                    }
                })
        
        # 表单消息
        elif content_type == 5:
            form = content.get("form", "")
            if form:
                segments.append({
                    "type": "yunhu_user_form",
                    "data": {"form": form}
                })
        
        # 文章消息
        elif content_type == 6:
            post_id = content.get("post_id", "")
            post_title = content.get("post_title", "")
            post_content = content.get("post_content", "")
            if post_id:
                segments.append({
                    "type": "yunhu_user_post",
                    "data": {
                        "post_id": post_id,
                        "post_title": post_title,
                        "post_content": post_content
                    }
                })
        
        # 表情/贴纸消息
        elif content_type == 7:
            sticker_url = content.get("sticker_url", "")
            if sticker_url:
                segments.append({
                    "type": "yunhu_user_sticker",
                    "data": {"file_id": sticker_url}
                })
        
        # HTML 消息
        elif content_type == 8:
            html = content.get("text", "")
            if html:
                segments.append({"type": "text", "data": {"text": html}})
        
        # 语音消息
        elif content_type == 11:
            audio_url = content.get("audio_url", "")
            audio_time = content.get("audio_time", 0)
            if audio_url:
                segments.append({
                    "type": "audio",
                    "data": {
                        "file_id": audio_url,
                        "duration": audio_time
                    }
                })
        
        # 视频消息
        # 假设视频消息使用 content_type 13 或其他
        video_url = content.get("video_url", "")
        if video_url:
            segments.append({
                "type": "video",
                "data": {"file_id": video_url}
            })
        
        # 处理按钮
        buttons_str = content.get("buttons", "")
        if buttons_str:
            import json
            try:
                buttons = json.loads(buttons_str) if isinstance(buttons_str, str) else buttons_str
                if buttons:
                    segments.append({
                        "type": "yunhu_user_button",
                        "data": {"buttons": buttons}
                    })
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 处理 @用户
        mentioned_id = content.get("mentioned_id", [])
        if isinstance(mentioned_id, list) and mentioned_id:
            for uid in mentioned_id:
                segments.append({
                    "type": "mention",
                    "data": {"user_id": uid}
                })
        
        # 处理回复
        quote_msg_id = msg.get("quote_msg_id", "")
        if quote_msg_id:
            segments.append({
                "type": "reply",
                "data": {"message_id": quote_msg_id}
            })
        
        return segments if segments else [{"type": "text", "data": {"text": ""}}]
    
    def _build_alt_message(self, segments: List[Dict[str, Any]]) -> str:
        """
        构建消息段的备用文本
        
        :param segments: 消息段列表
        :return: 备用文本
        """
        texts = []
        for segment in segments:
            seg_type = segment.get("type", "")
            data = segment.get("data", {})
            
            if seg_type == "text":
                texts.append(data.get("text", ""))
            elif seg_type == "image":
                texts.append("[图片]")
            elif seg_type == "audio":
                texts.append("[语音]")
            elif seg_type == "video":
                texts.append("[视频]")
            elif seg_type == "file":
                texts.append(f"[文件: {data.get('file_name', '')}]")
            elif seg_type == "mention":
                texts.append(f"@{data.get('user_id', '')}")
        
        return " ".join(texts)
    
    def _map_chat_type(self, chat_type: int) -> str:
        """
        映射云湖 chat_type 到 OneBot12 detail_type
        
        :param chat_type: 云湖 chat_type (1=user, 2=group, 3=bot)
        :return: OneBot12 detail_type
        """
        mapping = {
            1: "private",
            2: "group",
            3: "bot"
        }
        return mapping.get(chat_type, "private")
    
    def _generate_event_id(self, event: Dict[str, Any]) -> str:
        """
        生成事件 ID

        :param event: 原始事件
        :return: 事件 ID
        """
        # 尝试从消息中获取 ID
        if "msg" in event.get("data", {}):
            msg = event["data"]["msg"]
            msg_id = msg.get("msg_id", "")
            if msg_id:
                return msg_id

        # 否则生成 UUID
        return str(uuid.uuid4())

    def _convert_file_send_message(self, ws_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换超级文件分享事件为 OneBot12 notice 事件

        :param ws_event: file_send_message 事件
        :return: OneBot12 notice 事件
        """
        data = ws_event.get("data", {})
        sender_info = data.get("sender", {})
        info = ws_event.get("info", {})

        # 提取基本信息
        send_user_id = sender_info.get("send_user_id", "")
        user_id = sender_info.get("user_id", "")
        send_type = sender_info.get("send_type", "")
        file_data = sender_info.get("data", "")

        # 构建 OneBot12 事件
        ob12_event = {
            "id": self._generate_event_id(ws_event),
            "time": int(time.time()),
            "type": "notice",
            "detail_type": "yunhu_user_file_send",
            "platform": "yunhu_user",
            "self": {
                "platform": "yunhu_user",
                "user_id": ""  # 由适配器填充
            },
            "user_id": send_user_id,
            "user_nickname": "",
            "yunhu_user_file_send": {
                "send_user_id": send_user_id,
                "user_id": user_id,
                "send_type": send_type,
                "data": file_data
            },
            "yunhu_user_raw": ws_event,
            "yunhu_user_raw_type": "file_send_message"
        }

        return ob12_event

    def _convert_bot_board_message(self, ws_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换机器人公告设置事件为 OneBot12 notice 事件

        :param ws_event: bot_board_message 事件
        :return: OneBot12 notice 事件
        """
        data = ws_event.get("data", {})
        board = data.get("board", {})
        info = ws_event.get("info", {})

        # 提取基本信息
        bot_id = board.get("bot_id", "")
        chat_id = board.get("chat_id", "")
        chat_type = board.get("chat_type", 1)
        content = board.get("content", "")
        content_type = board.get("content_type", 1)
        last_update_time = board.get("last_update_time", 0)
        bot_name = board.get("bot_name", "")

        # 转换 detail_type
        detail_type = self._map_chat_type(chat_type)

        # 构建 OneBot12 事件
        ob12_event = {
            "id": self._generate_event_id(ws_event),
            "time": int(time.time()),
            "type": "notice",
            "detail_type": "yunhu_user_bot_board",
            "platform": "yunhu_user",
            "self": {
                "platform": "yunhu_user",
                "user_id": ""  # 由适配器填充
            },
            "bot_id": bot_id,
            "bot_name": bot_name,
            "yunhu_user_bot_board": {
                "bot_id": bot_id,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "content": content,
                "content_type": content_type,
                "last_update_time": last_update_time
            },
            "yunhu_user_raw": ws_event,
            "yunhu_user_raw_type": "bot_board_message"
        }

        # 添加位置信息
        if detail_type == "group":
            ob12_event["group_id"] = chat_id
        elif detail_type == "bot":
            ob12_event["bot_id"] = chat_id

        return ob12_event

    def _convert_stream_message(self, ws_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换流式消息事件为 OneBot12 message 事件

        :param ws_event: stream_message 事件
        :return: OneBot12 message 事件
        """
        data = ws_event.get("data", {})
        stream_msg = data.get("msg", {})
        info = ws_event.get("info", {})

        # 提取基本信息
        msg_id = stream_msg.get("msg_id", "")
        recv_id = stream_msg.get("recv_id", "")
        chat_id = stream_msg.get("chat_id", "")
        content = stream_msg.get("content", "")

        # 流式消息通常是私聊或群聊，这里默认为私聊
        detail_type = "private"

        # 构建消息段
        message_segments = [{"type": "text", "data": {"text": content}}]
        alt_message = content

        # 构建 OneBot12 事件
        ob12_event = {
            "id": msg_id or self._generate_event_id(ws_event),
            "time": int(time.time()),
            "type": "message",
            "detail_type": detail_type,
            "platform": "yunhu_user",
            "self": {
                "platform": "yunhu_user",
                "user_id": ""  # 由适配器填充
            },
            "message": message_segments,
            "alt_message": alt_message,
            "user_id": recv_id,
            "user_nickname": "",
            "yunhu_user_raw": ws_event,
            "yunhu_user_raw_type": "stream_message"
        }

        # 如果有 chat_id，可能是群聊
        if chat_id:
            ob12_event["chat_id"] = chat_id

        if msg_id:
            ob12_event["message_id"] = msg_id

        return ob12_event