import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getPractice: vi.fn(),
  push: vi.fn(),
  back: vi.fn(),
}))

vi.mock('@/api/practice', () => ({ getPractice: mocks.getPractice }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: mocks.push, back: mocks.back }),
}))

import Pack from '@/views/practice/Pack.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PracticePackView', () => {
  it('renders questions read-only with self-test notice', async () => {
    mocks.getPractice.mockResolvedValue({
      practice_id: 1,
      report_id: 5,
      count: 2,
      questions: [
        { question_index: 0, round: 0, category: '基础', content: '练习题一', reference_points: ['要点A'], difficulty: 'medium' },
        { question_index: 1, round: 0, category: '进阶', content: '练习题二', reference_points: [], difficulty: 'hard' },
      ],
    })
    const wrapper = mount(Pack, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(mocks.getPractice).toHaveBeenCalledWith(1)
    const text = wrapper.text()
    expect(text).toContain('练习为自测形态')
    expect(text).toContain('练习题一')
    expect(text).toContain('练习题二')
    wrapper.unmount()
  })

  it('navigates back to setup on 再练一场', async () => {
    mocks.getPractice.mockResolvedValue({ practice_id: 1, report_id: 5, count: 1, questions: [] })
    const wrapper = mount(Pack, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const btn = wrapper.findAll('button').find((b) => b.text() === '再练一场')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')

    expect(mocks.push).toHaveBeenCalledWith('/interview/setup')
    wrapper.unmount()
  })
})
