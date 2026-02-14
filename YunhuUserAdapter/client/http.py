import aiohttp
from typing import Dict, Any, Optional


class YunhuHTTPClient:

    BASE_URL = "https://chat-go.jwzhd.com/v1"
    
    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        """
        初始化 HTTP 客户端

        :param token: 用户 token
        :param timeout: 请求超时时间（秒）
        """
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._client: Optional[aiohttp.ClientSession] = None
        # 添加 logger
        from ErisPulse.Core import logger
        self.logger = logger

        # 添加别名方法
        self.list = self.list_msg
        self.list_by_seq = self.list_msg_by_seq
        self.list_by_mid_seq = self.list_msg_by_mid_seq
        self.send = self.send_msg
        self.recall = self.recall_msg
        self.recall_batch = self.recall_msg_batch
        self.edit = self.edit_msg
        self.edit_record = self.list_msg_edit_record
    
    @property
    def client(self) -> aiohttp.ClientSession:
        """获取或创建客户端会话"""
        if self._client is None or self._client.closed:
            self._client = aiohttp.ClientSession(timeout=self.timeout)
        return self._client
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["token"] = self.token
        return headers
    
    def set_token(self, token: str):
        self.token = token
    
    async def email_login(self, email: str, password: str, 
                       device_id: str, platform: str = "windows") -> Dict[str, Any]:
        """
        邮箱登录
        
        :param email: 邮箱
        :param password: 密码
        :param device_id: 设备ID
        :param platform: 平台
        :return: 登录响应
        """
        url = f"{self.BASE_URL}/user/email-login"
        payload = {
            "email": email,
            "password": password,
            "deviceId": device_id,
            "platform": platform
        }
        
        async with self.client.post(url, json=payload) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_user_info(self) -> Dict[str, Any]:
        """
        获取用户信息
        
        :return: 用户信息响应
        """
        from ..proto.user_pb2 import user_info_response
        
        url = f"{self.BASE_URL}/user/info"
        async with self.client.get(url, headers=self._get_headers()) as response:
            response.raise_for_status()
            
            # 解析 Protobuf 响应
            resp = user_info_response()
            resp.ParseFromString(await response.read())
            
            return {
                "status": resp.status,
                "data": resp.data
            }
    
    async def list_msg(self, chat_id: str, chat_type: int,
                      msg_count: int = 1, msg_id: str = "") -> Dict[str, Any]:
        """
        获取消息列表
        
        :param chat_id: 会话ID
        :param chat_type: 会话类型 (1=user, 2=group, 3=bot)
        :param msg_count: 获取消息数量
        :param msg_id: 从指定消息ID开始（不包含此消息）
        :return: 消息列表响应
        """
        from ..proto.msg_pb2 import list_message_send, list_message
        from google.protobuf import json_format

        request = list_message_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_count = msg_count
        request.msg_id = msg_id

        url = f"{self.BASE_URL}/msg/list-message"
        data = request.SerializeToString()

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            resp = list_message()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)

    async def list_msg_by_seq(self, chat_id: str, chat_type: int,
                             msg_start: int = 0) -> Dict[str, Any]:
        """
        通过序列获取消息
        
        :param chat_id: 会话ID
        :param chat_type: 会话类型 (1=user, 2=group, 3=bot)
        :param msg_start: 开始的消息序列
        :return: 消息列表响应
        """
        from ..proto.msg_pb2 import list_message_by_seq_send, list_message_by_seq
        from google.protobuf import json_format

        request = list_message_by_seq_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_seq = msg_start

        url = f"{self.BASE_URL}/msg/list-message-by-seq"
        data = request.SerializeToString()

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            resp = list_message_by_seq()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)

    async def list_msg_by_mid_seq(self, chat_id: str, chat_type: int,
                                msg_id: str = "", msg_count: int = 1,
                                msg_seq: int = -1) -> Dict[str, Any]:
        """
        通过消息ID和序列获取消息
        
        :param chat_id: 会话ID
        :param chat_type: 会话类型 (1=user, 2=group, 3=bot)
        :param msg_id: 开始的消息ID（包含此消息）
        :param msg_count: 获取的消息数量
        :param msg_seq: 从指定的msg_seq开始
        :return: 消息列表响应
        """
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

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            resp = list_message_by_mid_seq()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)

    async def list_msg_edit_record(self, msg_id: str,
                                   size: int = 10, page: int = 1) -> Dict[str, Any]:
        """
        获取消息编辑记录
        
        :param msg_id: 消息ID
        :param size: 每页消息数
        :param page: 获取第N页
        :return: 编辑记录响应
        """
        url = f"{self.BASE_URL}/msg/list-message-edit-record"
        payload = {
            "msgId": msg_id,
            "size": size,
            "page": page
        }

        async with self.client.post(url, headers=self._get_headers(), json=payload) as response:
            response.raise_for_status()
            return await response.json()

    async def send_msg(self, chat_id: str, chat_type: int,
                      msg_id: str, msg_type: int = 1,
                      content: Optional[Dict] = None,
                      quote_msg_id: Optional[str] = None,
                      media: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送消息（别名方法）

        :param chat_id: 会话ID
        :param chat_type: 会话类型 (1=user, 2=group, 3=bot)
        :param msg_id: 消息ID
        :param msg_type: 消息类型
        :param content: 消息内容
        :param quote_msg_id: 引用消息ID
        :param media: 媒体信息
        :return: 发送响应
        """
        return await self.send_message(chat_id, chat_type, msg_id, msg_type,
                                     content, quote_msg_id, media)

    async def send_message(self, chat_id: str, chat_type: int,
                       msg_id: str, msg_type: int = 1,
                       content: Optional[Dict] = None,
                       quote_msg_id: Optional[str] = None,
                       media: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送消息

        :param chat_id: 会话ID
        :param chat_type: 会话类型 (1=user, 2=group, 3=bot)
        :param msg_id: 消息ID
        :param msg_type: 消息类型
        :param content: 消息内容
        :param quote_msg_id: 引用消息ID
        :param media: 媒体信息
        :return: 发送响应
        """
        from ..proto.msg_pb2 import send_message_send, send_message
        from google.protobuf import json_format

        from ErisPulse.Core import logger


        logger.debug(f"send_message: chat_id={chat_id}, chat_type={chat_type}, msg_id={msg_id}, msg_type={msg_type}, content={content}, quote_msg_id={quote_msg_id}, media={media}")

        # 构建请求
        request = send_message_send()
        request.msg_id = msg_id
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.content_type = msg_type

        if content:
            content_msg = request.content
            for key, value in content.items():
                if hasattr(content_msg, key):
                    # 特殊处理 repeated 字段 mentioned_id
                    if key == "mentioned_id" and isinstance(value, list):
                        # 清空现有值并扩展新值
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

        # 序列化并发送
        url = f"{self.BASE_URL}/msg/send-message"
        data = request.SerializeToString()

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            # 解析响应
            resp = send_message()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)
    
    async def edit_msg(self, chat_id: str, chat_type: int, msg_id: str,
                      text: str, msg_type: int = 1,
                      quote_msg_id: Optional[str] = None,
                      buttons: Optional[str] = None) -> Dict[str, Any]:
        """
        编辑消息（别名方法）

        :param chat_id: 会话ID
        :param chat_type: 会话类型
        :param msg_id: 消息ID
        :param text: 新文本内容
        :param msg_type: 消息类型
        :param quote_msg_id: 引用消息ID
        :param buttons: 按钮 JSON 字符串
        :return: 编辑响应
        """
        return await self.edit_message(chat_id, chat_type, msg_id, text, msg_type,
                                    quote_msg_id, buttons)

    async def edit_message(self, chat_id: str, chat_type: int, msg_id: str,
                       text: str, msg_type: int = 1,
                       quote_msg_id: Optional[str] = None,
                       buttons: Optional[str] = None) -> Dict[str, Any]:
        """
        编辑消息

        :param chat_id: 会话ID
        :param chat_type: 会话类型
        :param msg_id: 消息ID
        :param text: 新文本内容
        :param msg_type: 消息类型
        :param quote_msg_id: 引用消息ID
        :param buttons: 按钮 JSON 字符串
        :return: 编辑响应
        """
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

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            resp = edit_message()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)
    
    async def recall_msg(self, chat_id: str, chat_type: int, msg_id: str) -> Dict[str, Any]:
        """
        撤回消息（别名方法）

        :param chat_id: 会话ID
        :param chat_type: 会话类型
        :param msg_id: 消息ID
        :return: 撤回响应
        """
        return await self.recall_message(chat_id, chat_type, msg_id)

    async def recall_message(self, chat_id: str, chat_type: int, msg_id: str) -> Dict[str, Any]:
        """
        撤回消息

        :param chat_id: 会话ID
        :param chat_type: 会话类型
        :param msg_id: 消息ID
        :return: 撤回响应
        """
        from ..proto.msg_pb2 import recall_msg_send, recall_msg
        from google.protobuf import json_format

        request = recall_msg_send()
        request.msg_id = msg_id
        request.chat_id = chat_id
        request.chat_type = chat_type

        url = f"{self.BASE_URL}/msg/recall-msg"
        data = request.SerializeToString()

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            resp = recall_msg()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)

    async def recall_msg_batch(self, chat_id: str, chat_type: int,
                              msg_id_list: list) -> Dict[str, Any]:
        """
        批量撤回消息

        :param chat_id: 会话ID
        :param chat_type: 会话类型
        :param msg_id_list: 消息ID列表
        :return: 批量撤回响应
        """
        from ..proto.msg_pb2 import recall_msg_batch_send, recall_msg_batch
        from google.protobuf import json_format

        request = recall_msg_batch_send()
        request.chat_id = chat_id
        request.chat_type = chat_type
        request.msg_id.extend(msg_id_list)

        url = f"{self.BASE_URL}/msg/recall-msg-batch"
        data = request.SerializeToString()

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            resp = recall_msg_batch()
            resp.ParseFromString(await response.read())

            return json_format.MessageToDict(resp, preserving_proto_field_name=True)

    async def button_report(self, chat_id: str, chat_type: int,
                          msg_id: str, user_id: str,
                          button_value: str) -> Dict[str, Any]:
        """
        按钮事件报告

        :param chat_id: 会话ID
        :param chat_type: 会话类型
        :param msg_id: 消息ID
        :param user_id: 用户ID
        :param button_value: 按钮的值
        :return: 按钮事件报告响应
        """
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

        async with self.client.post(url, headers=self._get_headers(), data=data) as response:
            response.raise_for_status()

            return json_format.MessageToDict(request, preserving_proto_field_name=True)
    
    async def download_file(self, url: str) -> Optional[bytes]:
        """
        从 URL 下载文件

        :param url: 文件 URL
        :return: 文件二进制数据
        """
        try:
            self.logger.debug(f"正在下载文件: {url}")
            # 使用 allow_redirects=True 自动跟随重定向
            async with self.client.get(url, timeout=aiohttp.ClientTimeout(total=60), allow_redirects=True) as response:
                response.raise_for_status()
                file_data = await response.read()
                content_type = response.headers.get('Content-Type', '')
                final_url = str(response.url)
                self.logger.debug(f"文件下载成功，最终URL: {final_url}, Content-Type: {content_type}, 大小: {len(file_data)} 字节")

                # 检查下载的内容是否过小（可能是错误页面）
                if len(file_data) < 1000:
                    self.logger.warning(f"下载的文件大小过小（{len(file_data)} 字节），可能是错误页面或重定向问题")

                return file_data
        except Exception as e:
            self.logger.error(f"文件下载失败: {e}")
            return None

    async def upload_file(self, file_type: str, file_data: bytes,
                      filename: Optional[str] = None) -> Optional[str]:
        """
        上传文件到七牛云存储

        :param file_type: 文件类型 (image/audio/video/file)
        :param file_data: 文件二进制数据
        :param filename: 文件名
        :return: 文件 key
        """
        import hashlib

        # 获取七牛 token
        token_url = {
            "image": f"{self.BASE_URL}/misc/qiniu-token",
            "audio": f"{self.BASE_URL}/misc/qiniu-token-audio",
            "video": f"{self.BASE_URL}/misc/qiniu-token-video",
            "file": f"{self.BASE_URL}/misc/qiniu-token2"
        }.get(file_type, f"{self.BASE_URL}/misc/qiniu-token")

        self.logger.debug(f"获取七牛 token，URL: {token_url}, 文件类型: {file_type}")

        async with self.client.get(token_url, headers=self._get_headers()) as token_response:
            token_response.raise_for_status()
            token_data = await token_response.json()

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

        # 获取上传域名
        access_key = upload_token.split(":")[0]
        qiniu_query_url = f"https://api.qiniu.com/v4/query?ak={access_key}&bucket={bucket}"

        try:
            async with self.client.get(qiniu_query_url) as query_response:
                query_response.raise_for_status()
                query_data = await query_response.json()
                up_host = query_data["hosts"][0]["up"]["domains"][0]
            self.logger.debug(f"获取七牛上传域名成功: {up_host}, bucket: {bucket}")
        except Exception as e:
            self.logger.error(f"获取七牛上传域名失败: {e}")
            return None

        # 生成文件 key
        md5 = hashlib.md5(file_data).hexdigest()
        name = filename or md5
        key = name  # 直接使用文件名或MD5

        self.logger.debug(f"准备上传文件，key: {key}, 文件大小: {len(file_data)} 字节")

        # 根据文件类型设置 MIME 类型
        content_type_map = {
            "image": "image/jpeg",
            "audio": "audio/mpeg",
            "video": "video/mp4",
            "file": "application/octet-stream"
        }
        content_type = content_type_map.get(file_type, "application/octet-stream")

        # 优先使用 filetype 库检测 MIME 类型
        try:
            import filetype
            kind = filetype.guess(file_data)
            if kind and kind.mime:
                content_type = kind.mime
                self.logger.debug(f"使用 filetype 检测到 MIME 类型: {content_type}")
        except Exception as e:
            self.logger.debug(f"filetype 检测失败: {e}")

        # 如果 filetype 检测失败，尝试从文件名推断 MIME 类型
        if content_type == "application/octet-stream" and filename:
            import mimetypes
            guessed_type = mimetypes.guess_type(filename)
            if guessed_type and guessed_type[0]:
                content_type = guessed_type[0]
                self.logger.debug(f"从文件名推断 MIME 类型: {content_type}")

        try:
            import io
            form_data = aiohttp.FormData()
            form_data.add_field('token', upload_token)
            form_data.add_field('key', key)
            form_data.add_field('file', file_data, filename=name, content_type=content_type)

            # 上传文件
            upload_url = f"https://{up_host}"
            self.logger.debug(f"上传文件到: {upload_url}")
            async with self.client.post(upload_url, data=form_data) as upload_response:
                response_text = await upload_response.text()
                self.logger.debug(f"七牛上传响应状态: {upload_response.status}, 响应内容: {response_text}")
                upload_response.raise_for_status()
                upload_result = await upload_response.json()

            self.logger.info(f"文件上传成功，key: {key}")
            return {
                "key": key,
                "hash": upload_result.get("hash", ""),
                "bucket": bucket
            }

        except aiohttp.ClientResponseError as e:
            self.logger.error(f"文件上传失败: {e.status}, message='{e.message}', url='{upload_url}'")
            return None
        except Exception as e:
            self.logger.error(f"文件上传失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    async def close(self):
        if self._client and not self._client.closed:
            await self._client.close()
