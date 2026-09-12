from typing import Dict, Any, Optional

from ErisPulse.Core import client
from ErisPulse.Core.Bases.errors import ClientError


class YunhuHTTPClient:

    BASE_URL = "https://chat-go.jwzhd.com/v1"

    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        self.token = token
        self.timeout = timeout
        from ErisPulse.Core import logger
        self.logger = logger

        self.list = self.list_msg
        self.list_by_seq = self.list_msg_by_seq
        self.list_by_mid_seq = self.list_msg_by_mid_seq
        self.send = self.send_msg
        self.recall = self.recall_msg
        self.recall_batch = self.recall_msg_batch
        self.edit = self.edit_msg
        self.edit_record = self.list_msg_edit_record

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["token"] = self.token
        return headers

    def set_token(self, token: str):
        self.token = token

    async def email_login(self, email: str, password: str,
                          device_id: str, platform: str = "windows") -> Dict[str, Any]:
        url = f"{self.BASE_URL}/user/email-login"
        payload = {
            "email": email,
            "password": password,
            "deviceId": device_id,
            "platform": platform
        }
        resp = await client.post(url, json=payload, timeout=self.timeout)
        return await resp.json()

    async def get_user_info(self) -> Dict[str, Any]:
        from ..proto.user_pb2 import user_info_response

        url = f"{self.BASE_URL}/user/info"
        resp = await client.get(url, headers=self._get_headers(), timeout=self.timeout)
        raw = await resp.read()

        user_resp = user_info_response()
        user_resp.ParseFromString(raw)

        return {
            "status": user_resp.status,
            "data": user_resp.data
        }

    async def list_msg(self, chat_id: str, chat_type: int,
                       msg_count: int = 1, msg_id: str = "") -> Dict[str, Any]:
        from ..proto.msg_pb2 import list_message_send, list_message
        from google.protobuf import json_format

        request = list_message_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_count = msg_count
        request.msg_id = msg_id

        url = f"{self.BASE_URL}/msg/list-message"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = list_message()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def list_msg_by_seq(self, chat_id: str, chat_type: int,
                              msg_start: int = 0) -> Dict[str, Any]:
        from ..proto.msg_pb2 import list_message_by_seq_send, list_message_by_seq
        from google.protobuf import json_format

        request = list_message_by_seq_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_seq = msg_start

        url = f"{self.BASE_URL}/msg/list-message-by-seq"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = list_message_by_seq()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def list_msg_by_mid_seq(self, chat_id: str, chat_type: int,
                                  msg_id: str = "", msg_count: int = 1,
                                  msg_seq: int = -1) -> Dict[str, Any]:
        from ..proto.msg_pb2 import list_message_by_mid_seq_send, list_message_by_mid_seq
        from google.protobuf import json_format

        request = list_message_by_mid_seq_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_id = msg_id
        request.msg_count = msg_count
        request.msg_seq = msg_seq

        url = f"{self.BASE_URL}/msg/list-message-by-mid-seq"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = list_message_by_mid_seq()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def list_msg_edit_record(self, msg_id: str,
                                   size: int = 10, page: int = 1) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/msg/list-message-edit-record"
        payload = {
            "msgId": msg_id,
            "size": size,
            "page": page
        }

        resp = await client.post(
            url, headers=self._get_headers(), json=payload, timeout=self.timeout
        )
        return await resp.json()

    async def send_msg(self, chat_id: str, chat_type: int,
                       msg_id: str, msg_type: int = 1,
                       content: Optional[Dict] = None,
                       quote_msg_id: Optional[str] = None,
                       media: Optional[Dict] = None) -> Dict[str, Any]:
        return await self.send_message(chat_id, chat_type, msg_id, msg_type,
                                       content, quote_msg_id, media)

    async def send_message(self, chat_id: str, chat_type: int,
                           msg_id: str, msg_type: int = 1,
                           content: Optional[Dict] = None,
                           quote_msg_id: Optional[str] = None,
                           media: Optional[Dict] = None) -> Dict[str, Any]:
        from ..proto.msg_pb2 import send_message_send, send_message
        from google.protobuf import json_format

        self.logger.debug(
            f"send_message: chat_id={chat_id}, chat_type={chat_type}, "
            f"msg_id={msg_id}, msg_type={msg_type}, content={content}, "
            f"quote_msg_id={quote_msg_id}, media={media}"
        )

        request = send_message_send()
        request.msg_id = msg_id
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.content_type = msg_type

        if content:
            content_msg = request.content
            for key, value in content.items():
                if hasattr(content_msg, key):
                    if key == "mentioned_id" and isinstance(value, list):
                        content_msg.ClearField(key)
                        content_msg.mentioned_id.extend(value)
                    else:
                        setattr(content_msg, key, value)

        if quote_msg_id:
            request.quote_msg_id = quote_msg_id

        if media:
            media_msg = request.media
            for key, value in media.items():
                if hasattr(media_msg, key):
                    setattr(media_msg, key, value)

        url = f"{self.BASE_URL}/msg/send-message"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = send_message()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def edit_msg(self, chat_id: str, chat_type: int, msg_id: str,
                       text: str, msg_type: int = 1,
                       quote_msg_id: Optional[str] = None,
                       buttons: Optional[str] = None) -> Dict[str, Any]:
        return await self.edit_message(chat_id, chat_type, msg_id, text, msg_type,
                                       quote_msg_id, buttons)

    async def edit_message(self, chat_id: str, chat_type: int, msg_id: str,
                           text: str, msg_type: int = 1,
                           quote_msg_id: Optional[str] = None,
                           buttons: Optional[str] = None) -> Dict[str, Any]:
        from ..proto.msg_pb2 import edit_message_send, edit_message
        from google.protobuf import json_format

        request = edit_message_send()
        request.msg_id = msg_id
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.content_type = msg_type

        content = request.content
        content.text = text
        if quote_msg_id:
            request.quote_msg_id = quote_msg_id
        if buttons:
            content.buttons = buttons

        url = f"{self.BASE_URL}/msg/edit-message"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = edit_message()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def recall_msg(self, chat_id: str, chat_type: int, msg_id: str) -> Dict[str, Any]:
        return await self.recall_message(chat_id, chat_type, msg_id)

    async def recall_message(self, chat_id: str, chat_type: int, msg_id: str) -> Dict[str, Any]:
        from ..proto.msg_pb2 import recall_msg_send, recall_msg
        from google.protobuf import json_format

        request = recall_msg_send()
        request.msg_id = msg_id
        request.chat_id = chat_id
        request.chat_type = chat_type

        url = f"{self.BASE_URL}/msg/recall-msg"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = recall_msg()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def recall_msg_batch(self, chat_id: str, chat_type: int,
                               msg_id_list: list) -> Dict[str, Any]:
        from ..proto.msg_pb2 import recall_msg_batch_send, recall_msg_batch
        from google.protobuf import json_format

        request = recall_msg_batch_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_id.extend(msg_id_list)

        url = f"{self.BASE_URL}/msg/recall-msg-batch"
        data = request.SerializeToString()

        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()

        msg_resp = recall_msg_batch()
        msg_resp.ParseFromString(raw)

        return json_format.MessageToDict(msg_resp, preserving_proto_field_name=True)

    async def button_report(self, chat_id: str, chat_type: int,
                            msg_id: str, user_id: str,
                            button_value: str) -> Dict[str, Any]:
        from ..proto.msg_pb2 import button_report_send
        from google.protobuf import json_format

        request = button_report_send()
        request.msg_id = msg_id
        request.chat_type = chat_type
        request.chat_id = chat_id
        request.user_id = user_id
        request.button_value = button_value

        url = f"{self.BASE_URL}/msg/button-report"
        data = request.SerializeToString()

        await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )

        return json_format.MessageToDict(request, preserving_proto_field_name=True)

    async def download_file(self, url: str) -> Optional[bytes]:
        try:
            self.logger.debug(f"正在下载文件: {url}")
            resp = await client.get(url, timeout=60)
            file_data = await resp.read()
            content_type = resp.headers.get('Content-Type', '')
            self.logger.debug(
                f"文件下载成功, Content-Type: {content_type}, 大小: {len(file_data)} 字节"
            )

            if len(file_data) < 1000:
                self.logger.warning(
                    f"下载的文件大小过小（{len(file_data)} 字节），可能是错误页面"
                )

            return file_data
        except ClientError as e:
            self.logger.error(f"文件下载失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"文件下载失败: {e}")
            return None

    async def upload_file(self, file_type: str, file_data: bytes,
                          filename: Optional[str] = None) -> Optional[str]:
        import hashlib

        token_url = {
            "image": f"{self.BASE_URL}/misc/qiniu-token",
            "audio": f"{self.BASE_URL}/misc/qiniu-token-audio",
            "video": f"{self.BASE_URL}/misc/qiniu-token-video",
            "file": f"{self.BASE_URL}/misc/qiniu-token2"
        }.get(file_type, f"{self.BASE_URL}/misc/qiniu-token")

        self.logger.debug(f"获取七牛 token，URL: {token_url}, 文件类型: {file_type}")

        token_resp = await client.get(
            token_url, headers=self._get_headers(), timeout=self.timeout
        )
        token_data = await token_resp.json()

        upload_token = token_data.get("data", {}).get("token")
        if not upload_token:
            self.logger.error(f"获取七牛上传 token 失败，响应: {token_data}")
            return None

        self.logger.debug(f"获取七牛 token 成功，bucket: {file_type}")

        bucket = {
            "image": "chat68",
            "audio": "chat68-audio",
            "video": "chat68-video",
            "file": "chat68-file",
            "group_disk": "chat68-file"
        }.get(file_type, "chat68-file")

        access_key = upload_token.split(":")[0]
        qiniu_query_url = f"https://api.qiniu.com/v4/query?ak={access_key}&bucket={bucket}"

        try:
            query_resp = await client.get(qiniu_query_url, timeout=self.timeout)
            query_data = await query_resp.json()
            up_host = query_data["hosts"][0]["up"]["domains"][0]
            self.logger.debug(f"获取七牛上传域名成功: {up_host}, bucket: {bucket}")
        except Exception as e:
            self.logger.error(f"获取七牛上传域名失败: {e}")
            return None

        md5 = hashlib.md5(file_data).hexdigest()
        name = filename or md5
        key = name

        self.logger.debug(f"准备上传文件，key: {key}, 文件大小: {len(file_data)} 字节")

        content_type_map = {
            "image": "image/jpeg",
            "audio": "audio/mpeg",
            "video": "video/mp4",
            "file": "application/octet-stream"
        }
        content_type = content_type_map.get(file_type, "application/octet-stream")

        try:
            import filetype as ft
            kind = ft.guess(file_data)
            if kind and kind.mime:
                content_type = kind.mime
                self.logger.debug(f"使用 filetype 检测到 MIME 类型: {content_type}")
        except Exception as e:
            self.logger.debug(f"filetype 检测失败: {e}")

        if content_type == "application/octet-stream" and filename:
            import mimetypes
            guessed_type = mimetypes.guess_type(filename)
            if guessed_type and guessed_type[0]:
                content_type = guessed_type[0]
                self.logger.debug(f"从文件名推断 MIME 类型: {content_type}")

        try:
            import aiohttp
            import io as _io

            form_data = aiohttp.FormData()
            form_data.add_field('token', upload_token)
            form_data.add_field('key', key)
            form_data.add_field(
                'file', _io.BytesIO(file_data),
                filename=name, content_type=content_type
            )

            upload_url = f"https://{up_host}"
            self.logger.debug(f"上传文件到: {upload_url}")
            upload_resp = await client.post(
                upload_url, data=form_data, timeout=120
            )
            upload_result = await upload_resp.json()

            self.logger.info(f"文件上传成功，key: {key}")
            return {
                "key": key,
                "hash": upload_result.get("hash", ""),
                "bucket": bucket
            }

        except ClientError as e:
            self.logger.error(f"文件上传失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"文件上传失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    async def close(self):
        pass

    # ==================== 用户 API 扩展（full.proto / v1 端点） ====================

    async def _proto_request(self, path: str, request_msg, response_cls=None):
        """通用 protobuf 请求：序列化 request → POST → 解析 response（可选）"""
        url = f"{self.BASE_URL}{path}"
        data = request_msg.SerializeToString() if request_msg is not None else b""
        resp = await client.post(
            url, headers=self._get_headers(), data=data, timeout=self.timeout
        )
        raw = await resp.read()
        if response_cls is None:
            from ..proto import full_pb2

            status = full_pb2.StatusResponse()
            status.ParseFromString(raw)
            from google.protobuf import json_format

            return json_format.MessageToDict(status, preserving_proto_field_name=True)
        response = response_cls()
        response.ParseFromString(raw)
        from google.protobuf import json_format

        return json_format.MessageToDict(response, preserving_proto_field_name=True)

    async def _json_request(self, path: str, payload: dict) -> Dict[str, Any]:
        """通用 JSON 请求（用户 API 中部分端点接受 JSON）"""
        url = f"{self.BASE_URL}{path}"
        resp = await client.post(
            url, headers=self._get_headers(), json=payload, timeout=self.timeout
        )
        return await resp.json()

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """获取用户详细信息（POST /user/get-user）"""
        from ..proto import full_pb2

        request = full_pb2.GetUserRequest()
        request.id = str(user_id)
        return await self._proto_request("/user/get-user", request, full_pb2.GetUserResponse)

    async def edit_nickname(self, nickname: str) -> Dict[str, Any]:
        """修改自己的昵称（POST /user/edit-nickname）"""
        from ..proto import full_pb2

        request = full_pb2.EditNicknameRequest()
        request.name = nickname
        return await self._proto_request("/user/edit-nickname", request)

    async def edit_avatar(self, avatar_url: str) -> Dict[str, Any]:
        """修改自己的头像（POST /user/edit-avatar）"""
        from ..proto import full_pb2

        request = full_pb2.EditAvatarRequest()
        request.url = avatar_url
        return await self._proto_request("/user/edit-avatar", request)

    async def friend_address_book(self, md5: str = "") -> Dict[str, Any]:
        """获取通讯录（POST /friend/address-book-list）"""
        from ..proto import full_pb2

        request = full_pb2.AddressBookListRequest()
        if md5:
            request.md5 = md5
        return await self._proto_request("/friend/address-book-list", request, full_pb2.AddressBookListResponse)

    async def friend_request_list(self) -> Dict[str, Any]:
        """获取好友/加群申请列表（POST /friend/request-list）"""
        from ..proto import full_pb2

        return await self._proto_request("/friend/request-list", None, full_pb2.RequestListResponse)

    async def friend_apply(self, user_id: str, description: str = "") -> Dict[str, Any]:
        """申请添加好友（POST /friend/apply）"""
        return await self._json_request("/friend/apply", {
            "userId": str(user_id), "description": description,
        })

    async def friend_agree_apply(self, user_id: str, description: str = "") -> Dict[str, Any]:
        """同意好友申请（POST /friend/agree-apply）"""
        return await self._json_request("/friend/agree-apply", {
            "userId": str(user_id), "description": description,
        })

    async def friend_ignore_apply(self, user_id: str) -> Dict[str, Any]:
        """忽略好友申请（POST /friend/ignore-apply）"""
        return await self._json_request("/friend/ignore-apply", {"userId": str(user_id)})

    async def friend_delete(self, user_id: str) -> Dict[str, Any]:
        """删除好友（POST /friend/delete-friend）"""
        return await self._json_request("/friend/delete-friend", {"userId": str(user_id)})

    async def group_info(self, group_id: str) -> Dict[str, Any]:
        """获取群组信息（POST /group/info）"""
        from ..proto import full_pb2

        request = full_pb2.GroupInfoRequest()
        request.group_id = str(group_id)
        return await self._proto_request("/group/info", request, full_pb2.GroupInfoResponse)

    async def group_member_list(self, group_id: str, keywords: str = "") -> Dict[str, Any]:
        """获取群成员列表（POST /group/list-member）"""
        from ..proto import full_pb2

        request = full_pb2.ListMemberRequest()
        request.group_id = str(group_id)
        if keywords:
            request.keywords = keywords
        return await self._proto_request("/group/list-member", request, full_pb2.ListMemberResponse)

    async def conversation_list(self, md5: str = "") -> Dict[str, Any]:
        """获取会话列表（POST /conversation/list）"""
        from ..proto import full_pb2

        request = full_pb2.ConversationListRequest()
        if md5:
            request.md5 = md5
        return await self._proto_request("/conversation/list", request, full_pb2.ConversationListResponse)

    async def create_group(self, name: str, introduction: str = "", avatar_url: str = "") -> Dict[str, Any]:
        """创建群组（POST /group/create-group）"""
        from ..proto import full_pb2

        request = full_pb2.CreateGroupRequest()
        request.name = name
        if introduction:
            request.introduction = introduction
        if avatar_url:
            request.avatar_url = avatar_url
        return await self._proto_request("/group/create-group", request, full_pb2.CreateGroupResponse)

    async def dismiss_group(self, group_id: str) -> Dict[str, Any]:
        """解散群组（POST /group/dismiss-group）"""
        from ..proto import full_pb2

        request = full_pb2.DismissGroupRequest()
        request.group_id = str(group_id)
        return await self._proto_request("/group/dismiss-group", request)

    async def group_invite(self, group_id: str, user_ids: list) -> Dict[str, Any]:
        """邀请用户进群（POST /group/invite）"""
        return await self._json_request("/group/invite", {
            "groupId": str(group_id), "userIdList": [str(u) for u in user_ids],
        })

    async def group_remove_member(self, group_id: str, user_id: str) -> Dict[str, Any]:
        """移出群成员（POST /group/remove-member）"""
        return await self._json_request("/group/remove-member", {
            "groupId": str(group_id), "userId": str(user_id),
        })

    async def group_gag_member(self, group_id: str, user_id: str, gag_time: int) -> Dict[str, Any]:
        """禁言群成员（POST /group/gag-member，gag_time 为秒数，0=解除）"""
        return await self._json_request("/group/gag-member", {
            "groupId": str(group_id), "userId": str(user_id), "gagTime": int(gag_time),
        })

    async def group_bot_list(self, group_id: str) -> Dict[str, Any]:
        """获取群内机器人列表（POST /group/bot-list）"""
        from ..proto import full_pb2

        request = full_pb2.BotListRequest()
        request.group_id = str(group_id)
        return await self._proto_request("/group/bot-list", request, full_pb2.BotListResponse)

    async def bot_board(self, target_id: str, chat_type: int, content: str) -> Dict[str, Any]:
        """设置看板（POST /bot/board）"""
        from ..proto import full_pb2

        request = full_pb2.BoardRequest()
        request.id = str(target_id)
        request.chat_type = chat_type
        _ = content  # 看板内容字段见 full.proto BoardRequest/BoardResponse
        return await self._proto_request("/bot/board", request, full_pb2.BoardResponse)
