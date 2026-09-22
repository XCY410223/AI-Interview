import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listResumes: vi.fn(),
  listReports: vi.fn(),
  push: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('@/api/resume', () => ({ listResumes: mocks.listResumes }))
vi.mock('@/api/report', () => ({ listReports: mocks.listReports }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { email: 'a@b.com' }, logout: mocks.logout }),
}))

import Dashboard from '@/views/Dashboard.vue'

function resume() {
  return { id: 1, status: 'completed', original_ext: 'pdf', uploaded_at: '2026-09-20T10:00:00' }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listResumes.mockResolvedValue({ total: 1, items: [resume()] })
  mocks.listReports.mockResolvedValue({ total: 0, items: [] })
})

describe('DashboardView', () => {
  it('renders resume list even when report list fails', async () => {
    mocks.listReports.mockRejectedValue(new Error('reports 表未迁移'))
    const wrapper = mount(Dashboard, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.text()).toContain('我的简历')
    expect(wrapper.text()).toContain('pdf') // 简历行已渲染，未被报告接口失败拖垮
    expect(wrapper.text()).toContain('完成')
    wrapper.unmount()
  })

  it('renders report list when both succeed', async () => {
    mocks.listReports.mockResolvedValue({
      total: 1,
      items: [{ report_id: 1, interview_id: 1, status: 'completed', overall_score: 8.5, grade: '良好', generated_at: '2026-09-20T10:00:00' }],
    })
    const wrapper = mount(Dashboard, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.text()).toContain('我的报告')
    expect(wrapper.text()).toContain('良好')
    wrapper.unmount()
  })
})
