import type { PageResult, ReportDetail, ReportListItem } from '@/types'

import { client } from './client'

export interface CreateReportResult {
  report_id: number
  status: string
}

export async function createReport(interviewId: number): Promise<CreateReportResult> {
  const { data } = await client.post<CreateReportResult>('/reports', { interview_id: interviewId })
  return data
}

export async function getReport(id: number): Promise<ReportDetail> {
  const { data } = await client.get<ReportDetail>(`/reports/${id}`)
  return data
}

export async function listReports(page = 1, pageSize = 20): Promise<PageResult<ReportListItem>> {
  const { data } = await client.get<PageResult<ReportListItem>>('/reports', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function exportReportPdf(id: number): Promise<CreateReportResult> {
  const { data } = await client.post<CreateReportResult>(`/reports/${id}/pdf`)
  return data
}

export async function downloadReportPdf(id: number): Promise<Blob> {
  const { data } = await client.get<Blob>(`/reports/${id}/pdf`, { responseType: 'blob' })
  return data
}
