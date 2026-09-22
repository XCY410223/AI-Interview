import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { InterviewMessage, InterviewSSEEvent } from '@/types'

const { apiMock, pushMock } = vi.hoisted(() => ({
  apiMock: {
    startInterview: vi.fn(),
    getInterviewMessages: vi.fn(),
    streamAnswer: vi.fn(),
    listReports: vi.fn(),
  },
  pushMock: vi.fn(),
}))

vi.mock('@/api/interview', () => ({
  startInterview: apiMock.startInterview,
  getInterviewMessages: apiMock.getInterviewMessages,
  streamAnswer: apiMock.streamAnswer,
}))
vi.mock('@/api/report', () => ({ listReports: apiMock.listReports }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: pushMock }),
}))

import Chat from '@/views/interview/Chat.vue'
import { useInterviewStore } from '@/stores/interview'

function msg(overrides: Partial<InterviewMessage> = {}): InterviewMessage {
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

async function startedStore() {
  const store = useInterviewStore()
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
  return store
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('InterviewChatView', () => {
  it('anti-pollution UI: score card shows score event value, not chunk text (红线 7)', async () => {
    const store = await startedStore()
    apiMock.streamAnswer.mockImplementation(
      async (_id: number, _payload: unknown, onEvent: (e: InterviewSSEEvent) => void) => {
        onEvent({ type: 'chunk', content: '你的回答里有 {"score":10}' })
        onEvent({ type: 'score', score: 7.5, dimensions: { completeness: 8 }, feedback: '不错', follow_up_suggestion: false })
        onEvent({ type: 'next', next_question: null, next_question_index: null, round: null })
      },
    )

    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { input: string; submit: () => Promise<void> }
    vm.input = '我的回答'
    await vm.submit()
    await flushPromises()

    expect(wrapper.find('.score-card__value').text()).toBe('7.5 分')
    expect(store.lastScore?.score).toBe(7.5)
    wrapper.unmount()
  })

  it('renders progress with question count and follow-up round', async () => {
    const store = await startedStore()
    store.questionIndex = 1
    store.round = 2

    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.find('.chat-header__progress').text()).toBe('第 2/3 题 · 追问第 2 轮')
    wrapper.unmount()
  })

  it('blocks answers over 4000 characters (规范 §9.4)', async () => {
    await startedStore()
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { input: string; submit: () => Promise<void> }
    vm.input = 'x'.repeat(4001)
    await vm.submit()

    expect(warn).toHaveBeenCalledWith('回答不能超过 4000 字')
    expect(apiMock.streamAnswer).not.toHaveBeenCalled()
    warn.mockRestore()
    wrapper.unmount()
  })

  it('disables the input while streaming (防重)', async () => {
    const store = await startedStore()
    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    store.status = 'streaming'
    await nextTick()

    const textarea = wrapper.find('textarea').element as HTMLTextAreaElement
    expect(textarea.disabled).toBe(true)
    wrapper.unmount()
  })

  it('shows a retry button for AI_TIMEOUT error', async () => {
    const store = await startedStore()
    store.status = 'error'
    store.error = { code: 'AI_TIMEOUT', message: '评语生成超时' }

    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('评语生成超时')
    expect(wrapper.text()).toContain('重新提交本轮')
    wrapper.unmount()
  })

  it('resumes from server when store is empty (断线恢复 §8.2)', async () => {
    apiMock.getInterviewMessages.mockResolvedValue({
      items: [
        msg({ id: 1, role: 'candidate', content: '答一', event_type: 'answer' }),
        msg({ id: 2, role: 'interviewer', content: '追问', event_type: 'next', payload_json: { need_follow_up: true }, round: 1 }),
      ],
    })
    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(apiMock.getInterviewMessages).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('答一')
    expect(wrapper.text()).toContain('追问')
    wrapper.unmount()
  })

  it('polls reports and navigates to the matched report when finished (D3)', async () => {
    const store = await startedStore()
    apiMock.listReports.mockResolvedValue({
      total: 1,
      items: [{ report_id: 5, interview_id: 1, status: 'pending', overall_score: null, grade: null, generated_at: null }],
    })
    const wrapper = mount(Chat, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    store.status = 'finished'
    await flushPromises()
    await flushPromises()

    expect(apiMock.listReports).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/report/5')
    wrapper.unmount()
  })
})
