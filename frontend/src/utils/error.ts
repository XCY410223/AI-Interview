import axios from 'axios'

/** 从后端统一错误响应 {code, message, data} 中提取 message。 */
export function extractErrorMessage(error: unknown, fallback = '操作失败，请重试'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === 'object' && 'message' in data) {
      const message = (data as { message?: unknown }).message
      if (typeof message === 'string' && message) return message
    }
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}
