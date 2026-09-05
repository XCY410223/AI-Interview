"""统一异常体系（规范 §6.3/§8.3）。

业务异常继承 AppError（code / message / http_status），
由全局 ExceptionHandler 转为统一响应 `{"code": ..., "message": ..., "data": ...}`。
生产环境禁止泄漏堆栈/内部错误信息。
"""


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    message: str = "服务内部错误"
    http_status: int = 500

    def __init__(self, message: str | None = None, code: str | None = None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)


# 模块前缀错误码示例（规范 §8.3）：
# AUTH_* / RESUME_* / INTERVIEW_* / AI_*（如 AI_TIMEOUT、AI_OVERLOAD）
class AITimeoutError(AppError):
    code = "AI_TIMEOUT"
    http_status = 503


class AIOverloadError(AppError):
    code = "AI_OVERLOAD"
    http_status = 503
