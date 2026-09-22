import type { InterviewSSEEvent } from '@/types'

/**
 * SSE 帧解析（红线 7）：按 `\n\n` 分帧 → 取 `data: ` 前缀行拼接 → JSON.parse → 按 type 判别。
 *
 * 只做「整帧 JSON 解析」，绝不从自由文本中抠字段（评分仅来自独立的 `score` 事件）。
 * 非法/空帧丢弃并 console.warn，不中断流（后端 Pydantic 已强类型序列化，此为防御性兜底）。
 * 缓冲区按 `\n\n` 切割，天然支持跨 chunk 半包分帧。
 */
export class SSEDecoder {
  private buffer = ''

  /** 追加一段文本，返回本次新解析出的完整事件数组（半包自动保留到 buffer）。 */
  push(chunk: string): InterviewSSEEvent[] {
    this.buffer += chunk
    const events: InterviewSSEEvent[] = []
    let sep: number
    while ((sep = this.buffer.indexOf('\n\n')) !== -1) {
      const frame = this.buffer.slice(0, sep)
      this.buffer = this.buffer.slice(sep + 2)
      const evt = decodeFrame(frame)
      if (evt) events.push(evt)
    }
    return events
  }

  /** 清空缓冲区（中止/重开时调用）。 */
  reset(): void {
    this.buffer = ''
  }
}

/** 单帧 → 事件；空 data / 非法 JSON / 非事件对象返回 null（含 console.warn）。 */
export function decodeFrame(frame: string): InterviewSSEEvent | null {
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('data:')) {
      // 去掉 `data:` 前缀与紧随的空格；多行 data 拼接为一个 JSON（协议允许）
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }
  if (dataLines.length === 0) return null
  const raw = dataLines.join('\n')
  if (!raw.trim()) return null

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    console.warn('[sse] 非法 JSON 帧已丢弃', raw)
    return null
  }
  if (!isSSEEvent(parsed)) {
    console.warn('[sse] 非事件帧已丢弃', raw)
    return null
  }
  return parsed
}

function isSSEEvent(value: unknown): value is InterviewSSEEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    typeof (value as { type?: unknown }).type === 'string'
  )
}
