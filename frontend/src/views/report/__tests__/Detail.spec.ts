import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import type { ReportDetail } from '@/types'

const mocks = vi.hoisted(() => ({
  getReport: vi.fn(),
  createReport: vi.fn(),
  exportReportPdf: vi.fn(),
  downloadReportPdf: vi.fn(),
  setCurrent: vi.fn(),
  back: vi.fn(),
}))

vi.mock('@/api/report', () => ({
  getReport: mocks.getReport,
  createReport: mocks.createReport,
  exportReportPdf: mocks.exportReportPdf,
  downloadReportPdf: mocks.downloadReportPdf,
}))
vi.mock('@/stores/report', () => ({
  useReportStore: () => ({ setCurrent: mocks.setCurrent, clear: vi.fn() }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ back: mocks.back }),
}))
vi.mock('@/components/RadarChart.vue', () => ({ default: { template: '<div class="radar-stub" />' } }))

import Detail from '@/views/report/Detail.vue'

function makeReport(overrides: Partial<ReportDetail> = {}): ReportDetail {
  return {
    report_id: 1,
    interview_id: 1,
    status: 'completed',
    overall_score: 8.5,
    grade: '良好',
    summary: '整体不错',
    dimensions: [],
    strengths: [],
    weaknesses: [],
    suggestions: [],
    question_scores: [],
    pdf_ready: false,
    ...overrides,
  }
}

describe('ReportDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders queued state for pending', async () => {
    mocks.getReport.mockResolvedValue(makeReport({ status: 'pending' }))
    const wrapper = mount(Detail, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('报告排队中')
    wrapper.unmount()
  })

  it('renders full report when completed', async () => {
    mocks.getReport.mockResolvedValue(makeReport({ status: 'completed' }))
    const wrapper = mount(Detail, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('面试评估报告')
    expect(wrapper.text()).toContain('整体不错')
    wrapper.unmount()
  })

  it('renders alert when failed', async () => {
    mocks.getReport.mockResolvedValue(makeReport({ status: 'failed', error_message: '生成失败' }))
    const wrapper = mount(Detail, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('生成失败')
    expect(wrapper.text()).toContain('重新生成')
    wrapper.unmount()
  })

  it('shows PDF export failure message when present', async () => {
    mocks.getReport.mockResolvedValue(
      makeReport({ status: 'completed', pdf_ready: false, pdf_error_message: 'libpango 缺失' }),
    )
    const wrapper = mount(Detail, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('PDF 导出失败')
    expect(wrapper.text()).toContain('libpango 缺失')
    wrapper.unmount()
  })

  it('exports and downloads the PDF on button click', async () => {
    mocks.getReport.mockResolvedValue(makeReport({ status: 'completed', pdf_ready: true }))
    mocks.exportReportPdf.mockResolvedValue({ report_id: 1, status: 'processing' })
    mocks.downloadReportPdf.mockResolvedValue(new Blob(['%PDF-fake']))

    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    const click = vi.fn()
    const originalCreate = URL.createObjectURL
    const originalRevoke = URL.revokeObjectURL
    const originalClick = HTMLAnchorElement.prototype.click
    ;(URL as unknown as { createObjectURL: typeof createObjectURL }).createObjectURL = createObjectURL
    ;(URL as unknown as { revokeObjectURL: typeof revokeObjectURL }).revokeObjectURL = revokeObjectURL
    HTMLAnchorElement.prototype.click = click

    try {
      const wrapper = mount(Detail, { global: { plugins: [ElementPlus] } })
      await flushPromises()

      await wrapper.findAll('.report-actions button')[0].trigger('click')
      await flushPromises()

      expect(mocks.exportReportPdf).toHaveBeenCalledWith(1)
      expect(mocks.downloadReportPdf).toHaveBeenCalledWith(1)
      expect(createObjectURL).toHaveBeenCalled()
      expect(click).toHaveBeenCalled()
      wrapper.unmount()
    } finally {
      ;(URL as unknown as { createObjectURL: typeof originalCreate }).createObjectURL = originalCreate
      ;(URL as unknown as { revokeObjectURL: typeof originalRevoke }).revokeObjectURL = originalRevoke
      HTMLAnchorElement.prototype.click = originalClick
    }
  })
})
