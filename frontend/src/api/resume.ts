import type { PageResult, Resume, ResumeDetail, UploadResponse } from '@/types'

import { client } from './client'

export async function uploadResume(form: FormData): Promise<UploadResponse> {
  const { data } = await client.post<UploadResponse>('/resumes/upload', form)
  return data
}

export async function getResume(id: number): Promise<ResumeDetail> {
  const { data } = await client.get<ResumeDetail>(`/resumes/${id}`)
  return data
}

export async function listResumes(page = 1, pageSize = 20): Promise<PageResult<Resume>> {
  const { data } = await client.get<PageResult<Resume>>('/resumes', { params: { page, page_size: pageSize } })
  return data
}
