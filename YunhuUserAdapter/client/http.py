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
