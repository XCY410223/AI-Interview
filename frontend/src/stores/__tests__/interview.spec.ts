import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMock = vi.hoisted(() => ({
  startInterview: vi.fn(),
  getInterviewMessages: vi.fn(),
  streamAnswer: vi.fn(),
}))

vi.mock('@/api/interview', () => apiMock)

import { buildScoreEvent, useInterviewStore } from '@/stores/interview'
import type { InterviewSSEEvent, InterviewMessage } from '@/types'

function streamWith(...evts: InterviewSSEEvent[]) {
  apiMock.streamAnswer.mockImplementation(async (_id: number, _payload: unknown, onEvent: (e: InterviewSSEEvent) => void) => {
    for (const e of evts) onEvent(e)
  })
}

function msg(overrides: Partial<InterviewMessage>): InterviewMessage {
  return {
    id: 1,
    question_index: 0,
    round: 0,
    role: 'candidate',
    content: null,
    event_type: 'answer',
    payload_json: null,
    created_at: null,
    ...overrides,
  }
}

async function startStore(store: ReturnType<typeof useInterviewStore>) {
  apiMock.startInterview.mockResolvedValue({
    interview_id: 1,
    total_questions: 3,
    first_question: { question_index: 0, round: 0, category: '基础', content: '第一题', reference_points: [], difficulty: 'medium' },
    estimated_minutes: 6,
  })
  await store.start({
    resume_id: 1,
    config: { position: '后端工程师', difficulty: 'medium', question_count: 3, style: 'friendly' },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  apiMock.startInterview.mockReset()
  apiMock.getInterviewMessages.mockReset()
  apiMock.streamAnswer.mockReset()
})

describe('interview store', () => {
  it('start seeds interviewId, total and first question', async () => {
    const store = useInterviewStore()
    await startStore(store)
    expect(store.interviewId).toBe(1)
    expect(store.totalQuestions).toBe(3)
    expect(store.status).toBe('asking')
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('第一题')
    expect(store.style).toBe('friendly')
  })

  it('anti-pollution: chunk text containing {"score":10} does not corrupt score (红线 7)', async () => {
    const store = useInterviewStore()
    await startStore(store)
    streamWith(
      { type: 'meta', interview_id: 1, question_index: 0, round: 0 },
      { type: 'chunk', content: '你的回答 {"score":10} 不错' },
      { type: 'score', score: 7.5, dimensions: { completeness: 8 }, feedback: '不错', follow_up_suggestion: false },
      { type: 'next', next_question: '第二题', next_question_index: 1, round: 0 },
    )
    await store.submitAnswer('我的回答')

    expect(store.lastScore?.score).toBe(7.5)
    const bubble = store.messages.find((m) => m.content.includes('{"score":10}'))
    expect(bubble?.content).toBe('你的回答 {"score":10} 不错') // 原文不解析
    expect(bubble?.score?.score).toBe(7.5)
  })

  it('advances questionIndex/round on a full meta→chunk→score→next sequence', async () => {
    const store = useInterviewStore()
    await startStore(store)
    streamWith(
      { type: 'meta', interview_id: 1, question_index: 0, round: 0 },
      { type: 'chunk', content: '好' },
      { type: 'chunk', content: '不错' },
      { type: 'score', score: 8, dimensions: {}, feedback: '可以', follow_up_suggestion: true },
      { type: 'next', next_question: '追问', next_question_index: 0, round: 1 },
    )
    await store.submitAnswer('答')

    expect(store.status).toBe('asking')
    expect(store.questionIndex).toBe(0)
    expect(store.round).toBe(1)
    // 追问气泡已追加
    expect(store.messages[store.messages.length - 1].content).toBe('追问')
  })

  it('finishes when next_question is null', async () => {
    const store = useInterviewStore()
    await startStore(store)
    streamWith(
      { type: 'meta', interview_id: 1, question_index: 2, round: 0 },
      { type: 'chunk', content: '收尾' },
      { type: 'score', score: 9, dimensions: {}, feedback: '很好', follow_up_suggestion: false },
      { type: 'next', next_question: null, next_question_index: null, round: null },
    )
    await store.submitAnswer('最后一答')
    expect(store.status).toBe('finished')
  })

  it('error event reverts half turn, sets error state and allows resubmit', async () => {
    const store = useInterviewStore()
    await startStore(store)
    streamWith({ type: 'error', code: 'AI_TIMEOUT', message: '评语生成超时' })

    await expect(store.submitAnswer('答')).rejects.toThrow('评语生成超时')
    expect(store.status).toBe('error')
    expect(store.error?.code).toBe('AI_TIMEOUT')
    expect(store.messages).toHaveLength(1) // 半条气泡已回退，只剩首题

    // 可重新提交
    streamWith(
      { type: 'meta', interview_id: 1, question_index: 0, round: 0 },
      { type: 'chunk', content: '重试成功' },
      { type: 'score', score: 6, dimensions: {}, feedback: '', follow_up_suggestion: false },
      { type: 'next', next_question: null, next_question_index: null, round: null },
    )
    await store.submitAnswer('再答')
    expect(store.status).toBe('finished')
  })

  it('guards against concurrent submit (D4)', async () => {
    const store = useInterviewStore()
    await startStore(store)
    let resolve!: () => void
    apiMock.streamAnswer.mockImplementation(() => new Promise<void>((r) => { resolve = r }))

    const first = store.submitAnswer('答')
    const second = store.submitAnswer('重复') // streaming 中，应被忽略
    resolve()
    await first
    await second

    expect(apiMock.streamAnswer).toHaveBeenCalledTimes(1)
  })

  it('abort reverts half state without throwing', async () => {
    const store = useInterviewStore()
    await startStore(store)
    apiMock.streamAnswer.mockImplementation(
      (_id: number, _payload: unknown, _onEvent: (e: InterviewSSEEvent) => void, signal?: AbortSignal) =>
        new Promise<void>((_resolve, reject) => {
          signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        }),
    )

    const p = store.submitAnswer('答')
    store.abortStream()
    await p // 不应抛错

    expect(store.status).toBe('asking')
    expect(store.messages).toHaveLength(1)
  })

  it('resumeFromServer rebuilds bubbles and position from server messages', async () => {
    const store = useInterviewStore()
    apiMock.getInterviewMessages.mockResolvedValue({
      items: [
        msg({ id: 1, question_index: 0, round: 0, role: 'candidate', content: '答一', event_type: 'answer' }),
        msg({ id: 2, question_index: 0, round: 0, role: 'interviewer', content: '点评', event_type: 'score', payload_json: { score: 8, dimensions: { completeness: 8 } } }),
        msg({ id: 3, question_index: 0, round: 0, role: 'interviewer', content: '第二题', event_type: 'next', payload_json: { next_question_index: 1 } }),
        msg({ id: 4, question_index: 1, round: 0, role: 'candidate', content: '答二', event_type: 'answer' }),
      ],
    })
    await store.resumeFromServer(9)

    expect(store.interviewId).toBe(9)
    expect(store.status).toBe('asking')
    expect(store.questionIndex).toBe(1)
    expect(store.round).toBe(0)
    expect(store.totalQuestions).toBe(2)
    expect(store.messages.map((m) => m.role)).toEqual(['user', 'interviewer', 'interviewer', 'user'])
    expect(store.lastScore?.score).toBe(8)
  })

  it('resumeFromServer marks finished when last next is done', async () => {
    const store = useInterviewStore()
    apiMock.getInterviewMessages.mockResolvedValue({
      items: [
        msg({ id: 1, role: 'candidate', content: '答', event_type: 'answer' }),
        msg({ id: 2, role: 'interviewer', content: '面试结束', event_type: 'next', payload_json: { done: true } }),
      ],
    })
    await store.resumeFromServer(9)
    expect(store.status).toBe('finished')
  })

  it('buildScoreEvent returns null without a numeric score', () => {
    expect(buildScoreEvent(null, '')).toBeNull()
    expect(buildScoreEvent({ dimensions: {} }, '')).toBeNull()
    const evt = buildScoreEvent({ score: 7.5, dimensions: { a: 1, b: 'x' } }, '反馈')
    expect(evt).toEqual({ type: 'score', score: 7.5, dimensions: { a: 1 }, feedback: '反馈', follow_up_suggestion: false })
  })
})
