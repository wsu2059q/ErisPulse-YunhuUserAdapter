from typing import Dict, Any, Optional


class ResponseFormatter:
    PLATFORM_NAME = "yunhu_user"
    
    @staticmethod
    def success(
        message_id: str = "",
        data: Optional[Dict] = None,
        raw_response: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成成功响应
        
        :param message_id: 消息 ID
        :param data: 响应数据
        :param raw_response: 原始平台响应
        :return: OneBot12 标准响应
        """
        result_data = data
        if message_id and not result_data:
            result_data = {"message_id": message_id}
        elif message_id and result_data is None:
            result_data = {"message_id": message_id}
        elif not result_data and message_id:
            result_data = {"message_id": message_id}
        
        return {
            "status": "ok",
            "retcode": 0,
            "data": result_data or {},
            "message_id": message_id,
            "message": "",
            f"{ResponseFormatter.PLATFORM_NAME}_raw": raw_response or {}
        }
    
    @staticmethod
    def failed(
        code: int,
        message: str,
        raw_response: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成失败响应
        
        :param code: 返回码（遵循 OneBot12 规范）
        :param message: 错误信息
        :param raw_response: 原始平台响应
        :return: OneBot12 标准响应
        """
        return {
            "status": "failed",
            "retcode": code,
            "data": None,
            "message_id": "",
            "message": message,
            f"{ResponseFormatter.PLATFORM_NAME}_raw": raw_response or {}
        }
    
    @staticmethod
    def from_platform_response(
        response: Dict[str, Any],
        fallback_message_id: str = ""
    ) -> Dict[str, Any]:
        """
        从云湖平台响应转换为 OneBot12 标准格式
        
        :param response: 云湖平台响应
        :param fallback_message_id: 备用消息 ID
        :return: OneBot12 标准响应
        """
        # 检查响应有效性
        if not response or not isinstance(response, dict):
            return ResponseFormatter.failed(
                34000,
                "无效的响应格式",
                str(response)
            )
        
        # 检查 status 字段
        status = response.get("status")
        if not status or not isinstance(status, dict):
            return ResponseFormatter.failed(
                34000,
                "响应缺少status字段",
                response
            )
        
        # 检查 code 字段
        code = status.get("code")
        if code is None:
            return ResponseFormatter.failed(
                34000,
                "响应缺少code字段",
                response
            )
        
        # 处理成功情况
        if code == 1:
            data = response.get("data", {})
            message_id = ""
            
            # 尝试从 data 中获取 message_id
            if data and isinstance(data, dict):
                message_id = data.get("message_id", "")
            elif isinstance(data, str):
                message_id = data
            
            # 优先使用 API 返回的 message_id，否则使用 fallback
            final_message_id = message_id or fallback_message_id
            
            return ResponseFormatter.success(
                message_id=final_message_id,
                data={"message_id": final_message_id} if final_message_id else {},
                raw_response=response
            )
        
        # 处理失败情况
        else:
            error_msg = status.get("msg", "未知错误")
            return ResponseFormatter.failed(
                10003,
                error_msg,
                response
            )
    
    @staticmethod
    def error(error: Exception) -> Dict[str, Any]:
        """
        生成异常响应
        
        :param error: 异常对象
        :return: OneBot12 标准响应
        """
        return ResponseFormatter.failed(
            34000,
            str(error),
            str(error)
        )