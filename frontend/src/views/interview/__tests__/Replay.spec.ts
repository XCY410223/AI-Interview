import { flushPromises, mount } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getInterviewReplay: vi.fn(),
  reEvaluateAnswer: vi.fn(),
  listReports: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/interview', () => ({
  getInterviewReplay: mocks.getInterviewReplay,
  reEvaluateAnswer: mocks.reEvaluateAnswer,
}))
vi.mock('@/api/report', () => ({ listReports: mocks.listReports }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: mocks.push }),
}))

import Replay from '@/views/interview/Replay.vue'

const replayFixture = {
  interview_id: 1,
  position: '后端工程师',
  difficulty: 'medium',
  style: 'friendly',
  status: 'completed',
  question_count: 1,
  questions: [
    { question_index: 0, round: 0, category: '基础', content: '请自我介绍', reference_points: [], difficulty: 'medium' },
  ],
  messages: [
    { id: 1, question_index: 0, round: 0, role: 'interviewer', content: '请自我介绍', event_type: 'next', payload_json: null, created_at: null },
    { id: 2, question_index: 0, round: 0, role: 'candidate', content: '我的回答，有人写 {"score":10}', event_type: 'answer', payload_json: null, created_at: null },
    { id: 3, question_index: 0, round: 0, role: 'interviewer', content: '不错', event_type: 'score', payload_json: { score: 7.5, dimensions: { completeness: 7.5 }, re_evaluated: false }, created_at: null },
    { id: 4, question_index: 0, round: 1, role: 'interviewer', content: '追问一下细节', event_type: 'next', payload_json: { need_follow_up: true }, created_at: null },
    { id: 5, question_index: 0, round: 1, role: 'candidate', content: '追问回答', event_type: 'answer', payload_json: null, created_at: null },
  ],
  report_summary: '表现良好',
  created_at: null,
  completed_at: null,
}

interface ReplayVm {
  reEvaluations: Record<number, { score: number; feedback: string }[]>
  onReEvaluate: (questionIndex: number) => Promise<void>
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getInterviewReplay.mockResolvedValue(replayFixture)
  mocks.listReports.mockResolvedValue({ total: 0, items: [] })
})

describe('InterviewReplayView', () => {
  it('renders messages grouped by (question_index, round) with anti-pollution score', async () => {
    const wrapper = mount(Replay, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const text = wrapper.text()
    // 题目快照
    expect(text).toContain('请自我介绍')
    // 逐条消息（含追问轮次）
    expect(text).toContain('我的回答，有人写 {"score":10}')
    expect(text).toContain('追问第 1 轮')
    expect(text).toContain('追问一下细节')
    expect(text).toContain('追问回答')
    // 反污染（红线 7）：真实分数来自 payload_json，文本里的 {"score":10} 不渲染成评分卡
    expect(text).toContain('7.5 分')
    expect(text).not.toContain('10.0 分')
    wrapper.unmount()
  })

  it('re-evaluates after confirmation and appends result without changing original', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    mocks.reEvaluateAnswer.mockResolvedValue({
      question_index: 0,
      score: 8.5,
      dimensions: { completeness: 8.5 },
      feedback: '重评反馈',
    })
    const wrapper = mount(Replay, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as ReplayVm
    await vm.onReEvaluate(0)

    expect(confirm).toHaveBeenCalled()
    expect(mocks.reEvaluateAnswer).toHaveBeenCalledWith(1, 0)
    expect(vm.reEvaluations[0]).toHaveLength(1)
    const text = wrapper.text()
    // 原评分卡不变 + 新重评卡追加
    expect(text).toContain('7.5 分')
    expect(text).toContain('重评')
    expect(text).toContain('8.5 分')
    confirm.mockRestore()
    wrapper.unmount()
  })

  it('skips re-evaluate when confirmation cancelled', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as never)
    const wrapper = mount(Replay, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as ReplayVm
    await vm.onReEvaluate(0)

    expect(mocks.reEvaluateAnswer).not.toHaveBeenCalled()
    confirm.mockRestore()
    wrapper.unmount()
  })

  it('shows report link when report matches interview_id', async () => {
    mocks.listReports.mockResolvedValue({
      total: 1,
      items: [{ report_id: 5, interview_id: 1, status: 'completed', overall_score: 8, grade: '良好', generated_at: null }],
    })
    const wrapper = mount(Replay, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.text()).toContain('查看完整报告')
    wrapper.unmount()
  })
})
