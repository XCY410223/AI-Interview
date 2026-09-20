import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('@/api/client', () => ({ client: clientMock }))

import {
  createReport,
  downloadReportPdf,
  exportReportPdf,
  getReport,
  listReports,
} from '@/api/report'

beforeEach(() => {
  clientMock.get.mockReset()
  clientMock.post.mockReset()
})

describe('report api', () => {
  it('createReport posts interview_id', async () => {
    clientMock.post.mockResolvedValue({ data: { report_id: 1, status: 'pending' } })
    const result = await createReport(7)
    expect(clientMock.post).toHaveBeenCalledWith('/reports', { interview_id: 7 })
    expect(result).toEqual({ report_id: 1, status: 'pending' })
  })

  it('getReport fetches by id', async () => {
    const detail = {
      report_id: 1, interview_id: 1, status: 'completed',
      dimensions: [], strengths: [], weaknesses: [], suggestions: [],
      question_scores: [], pdf_ready: false,
    }
    clientMock.get.mockResolvedValue({ data: detail })
    const result = await getReport(1)
    expect(clientMock.get).toHaveBeenCalledWith('/reports/1')
    expect(result).toEqual(detail)
  })

  it('listReports passes pagination params', async () => {
    clientMock.get.mockResolvedValue({ data: { total: 0, items: [] } })
    await listReports(2, 10)
    expect(clientMock.get).toHaveBeenCalledWith('/reports', { params: { page: 2, page_size: 10 } })
  })

  it('exportReportPdf posts to pdf endpoint', async () => {
    clientMock.post.mockResolvedValue({ data: { report_id: 1, status: 'processing' } })
    await exportReportPdf(1)
    expect(clientMock.post).toHaveBeenCalledWith('/reports/1/pdf')
  })

  it('downloadReportPdf requests a blob', async () => {
    clientMock.get.mockResolvedValue({ data: new Blob(['pdf']) })
    await downloadReportPdf(1)
    expect(clientMock.get).toHaveBeenCalledWith('/reports/1/pdf', { responseType: 'blob' })
  })
})
