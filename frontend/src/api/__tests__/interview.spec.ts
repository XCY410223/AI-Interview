import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { InterviewSSEEvent, StartInterviewPayload } from '@/types'

const { clientMock, authMock, pushMock } = vi.hoisted(() => ({
  clientMock: { post: vi.fn(), get: vi.fn() },
  authMock: {
    accessToken: 'at',
    refreshToken: 'rt',
    clear: vi.fn(),
    tryRefresh: vi.fn(),
  },
  pushMock: vi.fn(),
}))

vi.mock('@/api/client', () => ({ client: clientMock }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authMock }))
vi.mock('@/router', () => ({ default: { push: pushMock } }))

import { getInterviewMessages, startInterview, streamAnswer } from '@/api/interview'

const fetchMock = vi.fn()

function sseResponse(frames: string[]): Record<string, unknown> {
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        const enc = new TextEncoder()
        let i = 0
        return {
          read: async () =>
            i < frames.length
              ? { done: false, value: enc.encode(frames[i++]) }
              : { done: true, value: undefined },
          releaseLock: () => {},
        }
      },
    },
  }
}

beforeEach(() => {
  clientMock.post.mockReset()
  clientMock.get.mockReset()
  authMock.accessToken = 'at'
  authMock.refreshToken = 'rt'
  authMock.clear.mockReset()
  authMock.tryRefresh.mockReset()
  pushMock.mockReset()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('interview api', () => {
  it('startInterview serializes nested config', async () => {
    clientMock.post.mockResolvedValue({
      data: {
        interview_id: 9,
        total_questions: 3,
        first_question: { question_index: 0, round: 0, category: '基础', content: 'Q', reference_points: [], difficulty: 'medium' },
        estimated_minutes: 6,
      },
    })
    const payload: StartInterviewPayload = {
      resume_id: 1,
      config: { position: '后端工程师', difficulty: 'hard', question_count: 5, style: 'stress' },
    }
    const result = await startInterview(payload)
    expect(clientMock.post).toHaveBeenCalledWith('/interviews', payload)
    expect(result.interview_id).toBe(9)
  })

  it('getInterviewMessages fetches by id and unwraps items', async () => {
    clientMock.get.mockResolvedValue({ data: { items: [{ id: 1, question_index: 0, round: 0, role: 'candidate', content: '答', event_type: 'answer', payload_json: null, created_at: null }] } })
    const { items } = await getInterviewMessages(5)
    expect(clientMock.get).toHaveBeenCalledWith('/interviews/5/messages')
    expect(items).toHaveLength(1)
  })

  it('streamAnswer emits parsed events from the SSE stream', async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        'data: {"type":"meta","interview_id":9,"question_index":0,"round":0}\n\n',
        'data: {"type":"chunk","content":"亮点在于"}\n\n',
        'data: {"type":"score","score":7.5,"dimensions":{},"feedback":"不错","follow_up_suggestion":false}\n\n',
        'data: {"type":"next","next_question":null,"next_question_index":null,"round":null}\n\n',
      ]),
    )
    const events: InterviewSSEEvent[] = []
    await streamAnswer(9, { content: '回答', round: 0 }, (e) => events.push(e))

    expect(events.map((e) => e.type)).toEqual(['meta', 'chunk', 'score', 'next'])
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer at')
  })

  it('streamAnswer retries once after refresh on 401', async () => {
    fetchMock
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ message: 'expired' }) })
      .mockResolvedValueOnce(sseResponse(['data: {"type":"chunk","content":"重放"}\n\n']))
    authMock.tryRefresh.mockResolvedValue({ access_token: 'new-at', refresh_token: 'new-rt' })

    const events: InterviewSSEEvent[] = []
    await streamAnswer(9, { content: 'a', round: 0 }, (e) => events.push(e))

    expect(authMock.tryRefresh).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(events).toHaveLength(1)
  })

  it('streamAnswer clears auth and redirects to login when refresh fails', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 401, json: async () => ({ message: 'expired' }) })
    authMock.tryRefresh.mockRejectedValue(new Error('expired'))

    await expect(streamAnswer(9, { content: 'a', round: 0 }, () => {})).rejects.toThrow()
    expect(authMock.clear).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith({ name: 'login' })
  })

  it('streamAnswer throws backend message for non-ok status', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ code: 'INTERVIEW_INVALID_STATE', message: '面试作答进行中，请勿重复提交' }),
    })
    await expect(streamAnswer(9, { content: 'a', round: 0 }, () => {})).rejects.toThrow(
      '面试作答进行中，请勿重复提交',
    )
  })

  it('streamAnswer passes the abort signal to fetch', async () => {
    fetchMock.mockResolvedValue(sseResponse([]))
    const controller = new AbortController()
    await streamAnswer(9, { content: 'a', round: 0 }, () => {}, controller.signal)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.signal).toBe(controller.signal)
  })
})
