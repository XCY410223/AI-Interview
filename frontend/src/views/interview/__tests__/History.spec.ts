import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listInterviews: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/interview', () => ({ listInterviews: mocks.listInterviews }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))

import History from '@/views/interview/History.vue'

const row = {
  interview_id: 1,
  position: '后端工程师',
  difficulty: 'medium',
  style: 'friendly',
  status: 'completed',
  question_count: 8,
  created_at: '2026-09-26T00:00:00Z',
  completed_at: '2026-09-26T00:30:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listInterviews.mockResolvedValue({ total: 1, items: [row] })
})

describe('InterviewHistoryView', () => {
  it('loads list on mount and renders rows', async () => {
    const wrapper = mount(History, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(mocks.listInterviews).toHaveBeenCalledWith(1, 10)
    expect(wrapper.text()).toContain('后端工程师')
    wrapper.unmount()
  })

  it('shows empty state when no interviews', async () => {
    mocks.listInterviews.mockResolvedValue({ total: 0, items: [] })
    const wrapper = mount(History, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.text()).toContain('还没有面试记录')
    wrapper.unmount()
  })

  it('navigates to replay on row action', async () => {
    const wrapper = mount(History, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const replayBtn = wrapper.findAll('button').find((b) => b.text() === '回放')
    expect(replayBtn).toBeTruthy()
    await replayBtn!.trigger('click')

    expect(mocks.push).toHaveBeenCalledWith('/interview/1/replay')
    wrapper.unmount()
  })
})
