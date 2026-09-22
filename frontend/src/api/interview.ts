import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import type {
  InterviewMessage,
  InterviewSSEEvent,
  StartInterviewPayload,
  StartInterviewResponse,
} from '@/types'

import { client } from './client'
import { API_BASE } from './config'
import { SSEDecoder } from './sse'

/** 开始面试：简历 + 岗位配置 → 出题落库 → 返回 interview_id + 首题。 */
export async function startInterview(payload: StartInterviewPayload): Promise<StartInterviewResponse> {
  const { data } = await client.post<StartInterviewResponse>('/interviews', payload)
  return data
}

/** 历史回放：断线重连后按 (question_index, round) 恢复现场（规范 §8.2）。 */
export async function getInterviewMessages(
  interviewId: number,
): Promise<{ items: InterviewMessage[] }> {
  const { data } = await client.get<{ items: InterviewMessage[] }>(
    `/interviews/${interviewId}/messages`,
  )
  return data
}

/**
 * SSE 流式作答（D1/D2）：用 fetch + ReadableStream 而非 EventSource——
 * EventSource 不支持 POST 与 Authorization 头。
 *
 * 401 时 tryRefresh 续期后单次重放（幂等：后端 Redis 互斥锁保证不交错）；
 * 重放失败清 token 并跳登录（对齐 client.ts 行为）。
 */
export async function streamAnswer(
  interviewId: number,
  payload: { content: string; round: number },
  onEvent: (evt: InterviewSSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const auth = useAuthStore()

  const run = (token: string): Promise<Response> =>
    fetch(`${API_BASE}/interviews/${interviewId}/answer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal,
    })

  let response = await run(auth.accessToken)
  if (response.status === 401 && auth.refreshToken) {
    try {
      const tokens = await auth.tryRefresh()
      response = await run(tokens.access_token)
    } catch {
      auth.clear()
      router.push({ name: 'login' })
      throw new Error('登录已过期，请重新登录')
    }
  }

  if (!response.ok) {
    throw new Error(await readError(response))
  }
  if (!response.body) {
    throw new Error('当前环境不支持流式读取')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const sse = new SSEDecoder()

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const evt of sse.push(text)) onEvent(evt)
    }
  } finally {
    reader.releaseLock?.()
  }
}

/** 从后端统一错误响应 {code, message, data} 中提取 message。 */
async function readError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      body &&
      typeof body === 'object' &&
      'message' in body &&
      typeof (body as { message?: unknown }).message === 'string' &&
      (body as { message: string }).message
    ) {
      return (body as { message: string }).message
    }
  } catch {
    // ignore：非 JSON 错误体，走状态码兜底
  }
  return `请求失败（${response.status}）`
}
