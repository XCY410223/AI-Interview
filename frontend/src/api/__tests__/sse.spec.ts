import { describe, expect, it, vi } from 'vitest'

import { SSEDecoder, decodeFrame } from '@/api/sse'
import type { InterviewSSEEvent } from '@/types'

describe('decodeFrame', () => {
  it('parses a single chunk frame', () => {
    const evt = decodeFrame('data: {"type":"chunk","content":"你好"}')
    expect(evt).toEqual({ type: 'chunk', content: '你好' })
  })

  it('joins multiple data lines into one JSON', () => {
    const evt = decodeFrame('data: {"type":"chunk",\ndata: "content":"多行"}\n')
    expect(evt).toEqual({ type: 'chunk', content: '多行' })
  })

  it('returns null for empty data (no data lines)', () => {
    expect(decodeFrame('')).toBeNull()
    expect(decodeFrame(': keep-alive\n\n')).toBeNull()
  })

  it('returns null for empty data payload', () => {
    expect(decodeFrame('data:   ')).toBeNull()
  })

  it('drops invalid JSON with a warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(decodeFrame('data: {not json}')).toBeNull()
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })

  it('drops a JSON object without a type field', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(decodeFrame('data: {"foo":1}')).toBeNull()
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})

describe('SSEDecoder', () => {
  it('parses a single frame from one push', () => {
    const d = new SSEDecoder()
    const evts = d.push('data: {"type":"meta","interview_id":1,"question_index":0,"round":0}\n\n')
    expect(evts).toHaveLength(1)
    expect(evts[0].type).toBe('meta')
  })

  it('parses multiple frames in one push', () => {
    const d = new SSEDecoder()
    const body = [
      'data: {"type":"chunk","content":"a"}\n\n',
      'data: {"type":"chunk","content":"b"}\n\n',
    ].join('')
    const evts = d.push(body)
    expect(evts).toHaveLength(2)
    expect((evts[0] as { content: string }).content).toBe('a')
    expect((evts[1] as { content: string }).content).toBe('b')
  })

  it('reassembles a frame split across chunk boundaries (half packet)', () => {
    const d = new SSEDecoder()
    const full = 'data: {"type":"chunk","content":"跨包分帧"}\n\n'
    // 前 5 字符先到，其余后到
    const first = d.push(full.slice(0, 5))
    expect(first).toHaveLength(0)
    const second = d.push(full.slice(5))
    expect(second).toHaveLength(1)
    expect((second[0] as { content: string }).content).toBe('跨包分帧')
  })

  it('ignores empty and invalid frames without breaking the stream', () => {
    const d = new SSEDecoder()
    const evts = d.push(
      'data: {"type":"chunk","content":"ok"}\n\n\n\n' +
        'data: {bad}\n\n' +
        'data: {"type":"score","score":7.5,"dimensions":{},"feedback":"","follow_up_suggestion":false}\n\n',
    )
    expect(evts).toHaveLength(2)
    expect(evts[0].type).toBe('chunk')
    expect(evts[1].type).toBe('score')
  })

  it('keeps partial frame in buffer until completed', () => {
    const d = new SSEDecoder()
    d.push('data: {"type":"next","next_question":"追问？","next_question_index":0,"round":1}\n') // 无结尾空行
    const evts = d.push('\n')
    expect(evts).toHaveLength(1)
    expect(evts[0].type).toBe('next')
  })

  it('reset clears the buffer', () => {
    const d = new SSEDecoder()
    d.push('data: {"type":"chu') // 半包
    d.reset()
    const evts = d.push('nk","content":"x"}\n\n')
    expect(evts).toHaveLength(0) // 半包已丢弃，不产生脏帧
  })

  it('emits a typed event union end-to-end', () => {
    const d = new SSEDecoder()
    const evts: InterviewSSEEvent[] = d.push('data: {"type":"error","code":"AI_TIMEOUT","message":"超时"}\n\n')
    expect(evts[0]).toEqual({ type: 'error', code: 'AI_TIMEOUT', message: '超时' })
  })
})
