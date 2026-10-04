import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ReportListItem } from '@/types'

const { listReportsMock, pushMock } = vi.hoisted(() => ({
  listReportsMock: vi.fn(),
  pushMock: vi.fn(),
}))

vi.mock('@/api/report', () => ({ listReports: listReportsMock }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: pushMock }) }))

import List from '@/views/report/List.vue'

function report(overrides: Partial<ReportListItem> = {}): ReportListItem {
  return {
    report_id: 1,
    interview_id: 1,
    status: 'completed',
    overall_score: 8.5,
    grade: '良好',
    generated_at: '2026-09-20T10:00:00',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  listReportsMock.mockResolvedValue({ total: 1, items: [report()] })
})

describe('ReportListView', () => {
  it('renders report rows with status, score, grade', async () => {
    const wrapper = mount(List, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(listReportsMock).toHaveBeenCalledWith(1, 20)
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('8.5')
    expect(wrapper.text()).toContain('良好')
    wrapper.unmount()
  })

  it('navigates to report detail on row click', async () => {
    const wrapper = mount(List, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    await wrapper.find('tbody tr').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/report/1')
    wrapper.unmount()
  })

  it('shows empty state when no reports', async () => {
    listReportsMock.mockResolvedValue({ total: 0, items: [] })
    const wrapper = mount(List, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('还没有报告')
    wrapper.unmount()
  })

  it('falls back to gradeOf when grade is null but score present', async () => {
    listReportsMock.mockResolvedValue({ total: 1, items: [report({ grade: null, overall_score: 6.5 })] })
    const wrapper = mount(List, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('待提升')
    wrapper.unmount()
  })

  it('polls while reports are pending/processing and stops when terminal', async () => {
    vi.useFakeTimers()
    listReportsMock.mockResolvedValue({ total: 1, items: [report({ status: 'pending' })] })
    const wrapper = mount(List, { global: { plugins: [ElementPlus] } })
    await vi.advanceTimersByTimeAsync(0)

    const started = listReportsMock.mock.calls.length
    expect(started).toBeGreaterThanOrEqual(1)

    // 变为终态后，轮询应在下一次后停止
    listReportsMock.mockResolvedValue({ total: 1, items: [report({ status: 'completed' })] })
    await vi.advanceTimersByTimeAsync(1500)
    await vi.advanceTimersByTimeAsync(1500)
    const after = listReportsMock.mock.calls.length
    expect(after).toBeGreaterThan(started)

    const stoppedAt = listReportsMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(6000)
    expect(listReportsMock.mock.calls.length).toBe(stoppedAt)

    vi.useRealTimers()
    wrapper.unmount()
  })
})
