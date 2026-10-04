"""统一异常体系（规范 §6.3/§8.3）。

业务异常继承 AppError（code / message / http_status），
由全局 ExceptionHandler 转为统一响应 `{"code": ..., "message": ..., "data": null}`。
生产环境禁止泄漏堆栈/内部错误信息。

错误码按模块前缀：AUTH_* / RESUME_* / INTERVIEW_* / AI_*（规范 §8.3）。
"""
from __future__ import annotations


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


# ---- AI（LLM 调用相关，规范 §8.3/§9.1）----
class AIClientError(AppError):
    """LLM 客户端调用最终失败（未配置/主备模型均不可用/返回非法 JSON 等）。"""

    code = "AI_CLIENT_ERROR"
    http_status = 502


class AITimeoutError(AppError):
    code = "AI_TIMEOUT"
    http_status = 503


class AIOverloadError(AppError):
    code = "AI_OVERLOAD"
    http_status = 503


class AIRateLimited(AppError):
    """AI 调用超出每小时限流（复用 AI_RATE_LIMIT_PER_HOUR，规范 §9.1/§11.4）。"""

    code = "AI_RATE_LIMITED"
    message = "AI 调用过于频繁，请稍后再试"
    http_status = 429


# ---- AUTH（规范 §3.3/§6.3）----
class AuthError(AppError):
    """账户模块异常基类（不直接抛出）。"""


class AuthInvalidCredentials(AuthError):
    """登录失败，不区分邮箱不存在 vs 密码错（防枚举，§3.4）。"""

    code = "AUTH_INVALID_CREDENTIALS"
    message = "邮箱或密码错误"
    http_status = 401


class AuthEmailTaken(AuthError):
    code = "AUTH_EMAIL_TAKEN"
    http_status = 409


class AuthTokenExpired(AuthError):
    code = "AUTH_TOKEN_EXPIRED"
    http_status = 401


class AuthTokenRevoked(AuthError):
    code = "AUTH_TOKEN_REVOKED"
    http_status = 401


class AuthRateLimited(AuthError):
    code = "AUTH_RATE_LIMITED"
    http_status = 429


class AuthResetTokenInvalid(AuthError):
    """重置 token 无效/过期/已使用（统一文案，不区分具体原因，防探测 §2.1）。"""

    code = "AUTH_RESET_TOKEN_INVALID"
    message = "重置链接无效或已过期，请重新获取"
    http_status = 400


# ---- RESUME（规范 §4.5/§11.3）----
class ResumeError(AppError):
    """简历模块异常基类（不直接抛出）。"""


class ResumeInvalidExtension(ResumeError):
    code = "RESUME_INVALID_EXTENSION"
    http_status = 400


class ResumeInvalidMime(ResumeError):
    code = "RESUME_INVALID_MIME"
    http_status = 400


class ResumeFilenameInvalid(ResumeError):
    code = "RESUME_FILENAME_INVALID"
    http_status = 400


class ResumeFileTooLarge(ResumeError):
    code = "RESUME_FILE_TOO_LARGE"
    http_status = 413


class ResumeNotFound(ResumeError):
    code = "RESUME_NOT_FOUND"
    http_status = 404


class ResumeForbidden(ResumeError):
    code = "RESUME_FORBIDDEN"
    http_status = 403


class ResumeFileCorrupted(ResumeError):
    code = "RESUME_FILE_CORRUPTED"
    http_status = 422


# ---- INTERVIEW（规范 §8.3）----
class InterviewError(AppError):
    """面试模块异常基类（不直接抛出）。"""


class InterviewNotFound(InterviewError):
    code = "INTERVIEW_NOT_FOUND"
    http_status = 404


class InterviewForbidden(InterviewError):
    code = "INTERVIEW_FORBIDDEN"
    http_status = 403


class InterviewInvalidState(InterviewError):
    code = "INTERVIEW_INVALID_STATE"
    http_status = 409


# ---- REPORT（M3，规范 §8.3）----
class ReportError(AppError):
    """报告模块异常基类（不直接抛出）。"""


class ReportNotFound(ReportError):
    """报告不存在或非本人（不返回 403，避免暴露资源存在性，§11.3）。"""

    code = "REPORT_NOT_FOUND"
    http_status = 404


class ReportNotReady(ReportError):
    """报告尚未生成完成，暂不可导出 PDF。"""

    code = "REPORT_NOT_READY"
    http_status = 409


class InterviewNotFinished(ReportError):
    """面试尚未结束，无法生成报告。"""

    code = "INTERVIEW_NOT_FINISHED"
    http_status = 409


# ---- QUESTION_BANK（M4：JD 解析 / 真题 RAG / 题库模板）----
class QuestionBankError(AppError):
    """题库模块异常基类（不直接抛出）。"""


class QuestionBankParseError(QuestionBankError):
    """JD 解析失败（LLM 不可用 / 返回非法 JSON / Pydantic 校验失败），提示用户重贴。"""

    code = "QUESTION_BANK_JD_PARSE_FAILED"
    message = "JD 解析失败，请重新粘贴完整的岗位描述"
    http_status = 422


class QuestionBankNotFound(QuestionBankError):
    code = "QUESTION_BANK_NOT_FOUND"
    http_status = 404


class QuestionBankForbidden(QuestionBankError):
    code = "QUESTION_BANK_FORBIDDEN"
    http_status = 403


class QuestionBankInvalidSource(QuestionBankError):
    """真题溯源 source_url 仅接受公开 http(s) URL（§9.6 禁令）。"""

    code = "QUESTION_BANK_INVALID_SOURCE"
    message = "溯源链接仅支持公开 http/https URL"
    http_status = 400


# ---- PRACTICE（M4：弱项专项练习）----
class PracticeNotFound(AppError):
    code = "PRACTICE_NOT_FOUND"
    http_status = 404
