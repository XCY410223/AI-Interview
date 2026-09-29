import type {
  IngestResponse,
  JDParseResponse,
  PageResult,
  QuestionBankIngestPayload,
  QuestionBankSearchResponse,
  QuestionTemplate,
  QuestionTemplateCreatePayload,
  QuestionTemplateUpdatePayload,
} from '@/types'

import { client } from './client'

/** JD 解析（同步，计入 AI 限流）：贴入 JD 原文 → 岗位名 + 能力项清单。 */
export async function parseJD(jdText: string): Promise<JDParseResponse> {
  const { data } = await client.post<JDParseResponse>('/question-bank/jd/parse', { jd_text: jdText })
  return data
}

/** 面经入库（文本粘贴，Celery 异步）：建作业行 → 下发切片/去重/embedding。 */
export async function ingestQuestionBank(payload: QuestionBankIngestPayload): Promise<IngestResponse> {
  const { data } = await client.post<IngestResponse>('/question-bank/ingest', payload)
  return data
}

/** 真题检索：按公司+岗位+难度 cosine top-K（带 Redis 缓存）。 */
export async function searchQuestionBank(params: {
  company: string
  position: string
  difficulty?: string
  top_k?: number
}): Promise<QuestionBankSearchResponse> {
  const { data } = await client.get<QuestionBankSearchResponse>('/question-bank/search', { params })
  return data
}

export async function createTemplate(payload: QuestionTemplateCreatePayload): Promise<QuestionTemplate> {
  const { data } = await client.post<QuestionTemplate>('/question-bank/templates', payload)
  return data
}

export async function listTemplates(
  page = 1,
  pageSize = 20,
  position?: string,
): Promise<PageResult<QuestionTemplate>> {
  const { data } = await client.get<PageResult<QuestionTemplate>>('/question-bank/templates', {
    params: { page, page_size: pageSize, ...(position ? { position } : {}) },
  })
  return data
}

export async function getTemplate(id: number): Promise<QuestionTemplate> {
  const { data } = await client.get<QuestionTemplate>(`/question-bank/templates/${id}`)
  return data
}

export async function updateTemplate(
  id: number,
  payload: QuestionTemplateUpdatePayload,
): Promise<QuestionTemplate> {
  const { data } = await client.put<QuestionTemplate>(`/question-bank/templates/${id}`, payload)
  return data
}

export async function deleteTemplate(id: number): Promise<void> {
  await client.delete(`/question-bank/templates/${id}`)
}
