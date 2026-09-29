import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({ client: clientMock }))

import {
  createTemplate,
  deleteTemplate,
  ingestQuestionBank,
  listTemplates,
  parseJD,
  searchQuestionBank,
  updateTemplate,
} from '@/api/questionBank'

beforeEach(() => {
  clientMock.get.mockReset()
  clientMock.post.mockReset()
  clientMock.put.mockReset()
  clientMock.delete.mockReset()
})

describe('questionBank api', () => {
  it('parseJD posts jd_text', async () => {
    clientMock.post.mockResolvedValue({
      data: { position_guess: '后端工程师', capabilities: [], parsed_at: '2026-09-26T00:00:00Z' },
    })
    await parseJD('岗位描述原文……')
    expect(clientMock.post).toHaveBeenCalledWith('/question-bank/jd/parse', {
      jd_text: '岗位描述原文……',
    })
  })

  it('ingestQuestionBank posts full payload', async () => {
    clientMock.post.mockResolvedValue({ data: { item_id: 1, status: 'pending', task_id: 't1' } })
    const payload = {
      company: '字节',
      position: '后端',
      difficulty: 'medium' as const,
      content: '面经原文',
      source_url: 'https://example.com',
    }
    await ingestQuestionBank(payload)
    expect(clientMock.post).toHaveBeenCalledWith('/question-bank/ingest', payload)
  })

  it('searchQuestionBank passes query params', async () => {
    clientMock.get.mockResolvedValue({ data: { items: [] } })
    await searchQuestionBank({ company: '字节', position: '后端', difficulty: 'hard', top_k: 10 })
    expect(clientMock.get).toHaveBeenCalledWith('/question-bank/search', {
      params: { company: '字节', position: '后端', difficulty: 'hard', top_k: 10 },
    })
  })

  it('createTemplate posts payload', async () => {
    clientMock.post.mockResolvedValue({
      data: { id: 1, position: '后端', difficulty: 'medium', category: '架构', content: 'Q', reference_points: [], tags: [], usage_count: 0, created_at: null },
    })
    const payload = {
      position: '后端',
      difficulty: 'medium' as const,
      category: '架构',
      content: 'Q',
      reference_points: [],
      tags: [],
    }
    await createTemplate(payload)
    expect(clientMock.post).toHaveBeenCalledWith('/question-bank/templates', payload)
  })

  it('listTemplates passes pagination and optional position', async () => {
    clientMock.get.mockResolvedValue({ data: { total: 0, items: [] } })
    await listTemplates(2, 10, '后端')
    expect(clientMock.get).toHaveBeenCalledWith('/question-bank/templates', {
      params: { page: 2, page_size: 10, position: '后端' },
    })
  })

  it('updateTemplate puts partial payload', async () => {
    clientMock.put.mockResolvedValue({ data: { id: 1 } })
    await updateTemplate(1, { content: '更新后的内容' })
    expect(clientMock.put).toHaveBeenCalledWith('/question-bank/templates/1', { content: '更新后的内容' })
  })

  it('deleteTemplate deletes by id', async () => {
    clientMock.delete.mockResolvedValue({ data: undefined })
    await deleteTemplate(3)
    expect(clientMock.delete).toHaveBeenCalledWith('/question-bank/templates/3')
  })
})
