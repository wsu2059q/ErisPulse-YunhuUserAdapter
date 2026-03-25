from typing import Union, Optional, Dict
import hashlib
import io


class MediaHandler:
    """媒体文件处理器
    
    提供统一的媒体文件处理接口：
    - 自动判断 URL/二进制/本地路径
    - 自动下载文件（如果是URL）
    - 自动读取本地文件（如果是路径）
    - 自动上传到七牛云
    - 获取音频时长
    """
    
    def __init__(self, http_client, logger):
        """
        初始化媒体处理器
        
        :param http_client: HTTP 客户端实例
        :param logger: 日志记录器
        """
        self.http_client = http_client
        self.logger = logger
    
    async def process_file(
        self,
        file: Union[str, bytes],
        file_type: str,
        filename: Optional[str] = None
    ) -> Optional[Dict[str, any]]:
        """
        处理文件：自动判断 URL/本地路径/二进制，下载或读取（如需），上传到七牛云
        
        :param file: 文件 URL、本地文件路径或二进制数据
        :param file_type: 文件类型
        :param filename: 文件名（可选）
        :return: 包含 key 和元数据的字典，失败返回 None
        """
        try:
            file_data: Optional[bytes] = None
            detected_extension = None  # 检测到的文件扩展名
            
            # URL 方式 - 下载文件
            if isinstance(file, str) and file.startswith(("http://", "https://")):
                file_data = await self._download_file(file)
                if not file_data:
                    self.logger.error(f"文件下载失败: {file}")
                    return None
                
                # 从 URL 中提取文件名
                if not filename:
                    import os
                    filename = os.path.basename(file).split("?")[0]
            
            # 本地文件路径 - 读取文件
            elif isinstance(file, str):
                try:
                    import os
                    if os.path.isfile(file):
                        # 从路径中提取文件名
                        if not filename:
                            filename = os.path.basename(file)
                        
                        # 读取文件内容
                        with open(file, "rb") as f:
                            file_data = f.read()
                        self.logger.debug(f"成功读取本地文件: {file}, 大小: {len(file_data)} 字节")
                    else:
                        self.logger.error(f"文件不存在或不是有效路径: {file}")
                        return None
                except Exception as e:
                    self.logger.error(f"读取本地文件失败: {file}, 错误: {e}")
                    return None
            
            # 二进制方式 - 直接使用
            elif isinstance(file, bytes):
                file_data = file
            
            else:
                self.logger.error(f"不支持的文件格式: {type(file)}")
                return None
            
            # 使用 filetype 库检测文件类型和扩展名
            try:
                import filetype
                kind = filetype.guess(file_data)
                if kind:
                    detected_extension = kind.extension
                    self.logger.debug(f"filetype 检测 - MIME: {kind.mime}, 扩展名: {detected_extension}")
            except Exception as e:
                self.logger.debug(f"filetype 检测失败: {e}")
            
            # 如果没有指定文件名，使用检测到的扩展名
            final_filename = filename
            if not final_filename:
                # 优先使用检测到的扩展名
                if detected_extension:
                    md5 = hashlib.md5(file_data).hexdigest()
                    final_filename = f"{md5}.{detected_extension}"
                else:
                    # 否则使用 MD5
                    final_filename = hashlib.md5(file_data).hexdigest()
            elif detected_extension and '.' not in filename:
                # 如果指定了文件名但没有扩展名，添加检测到的扩展名
                final_filename = f"{filename}.{detected_extension}"
            
            # 上传到七牛云
            upload_result = await self._upload_file(file_type, file_data, final_filename)
            if not upload_result:
                self.logger.error("文件上传失败")
                return None
            
            self.logger.info(f"文件处理成功，key: {upload_result['key']}, 大小: {len(file_data)} 字节")
            
            result = {
                "key": upload_result["key"],
                "hash": upload_result.get("hash", ""),
                "file_size": len(file_data),
                "filename": final_filename
            }
            
            return result
        
        except Exception as e:
            self.logger.error(f"文件处理失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    async def get_audio_duration(self, file_data: bytes) -> int:
        """
        获取音频时长（秒）
        
        :param file_data: 音频文件二进制数据
        :return: 音频时长（秒），失败返回 0
        """
        try:
            from mutagen.mp3 import MP3
            from mutagen.mp4 import MP4
            from mutagen import MutagenError
            
            # 尝试解析音频文件
            audio_file = io.BytesIO(file_data)
            
            try:
                # 尝试 MP3
                audio = MP3(audio_file)
                duration = int(audio.info.length)
                self.logger.debug(f"MP3 音频时长: {duration} 秒")
                return duration
            except:
                pass
            
            # 重置文件指针
            audio_file.seek(0)
            
            try:
                # 尝试 MP4/M4A
                audio = MP4(audio_file)
                duration = int(audio.info.length)
                self.logger.debug(f"MP4/M4A 音频时长: {duration} 秒")
                return duration
            except:
                pass
            
            self.logger.warning("无法获取音频时长，使用默认值 0")
            return 0
        
        except Exception as e:
            self.logger.error(f"获取音频时长失败: {e}")
            return 0
    
    async def _download_file(self, url: str) -> Optional[bytes]:
        """
        下载文件
        
        :param url: 文件 URL
        :return: 文件二进制数据，失败返回 None
        """
        try:
            self.logger.debug(f"正在下载文件: {url}")
            file_data = await self.http_client.download_file(url)
            return file_data
        except Exception as e:
            self.logger.error(f"下载文件失败: {e}")
            return None
    
    async def _upload_file(
        self,
        file_type: str,
        file_data: bytes,
        filename: str
    ) -> Optional[Dict]:
        """
        上传文件到七牛云存储
        
        :param file_type: 文件类型
        :param file_data: 文件二进制数据
        :param filename: 文件名
        :return: 上传结果，失败返回 None
        """
        try:
            result = await self.http_client.upload_file(file_type, file_data, filename=filename)
            return result
        except Exception as e:
            self.logger.error(f"上传文件失败: {e}")
            return None