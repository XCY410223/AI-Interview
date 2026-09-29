import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('@/api/client', () => ({ client: clientMock }))

import { createPractice, getPractice } from '@/api/practice'

beforeEach(() => {
  clientMock.get.mockReset()
  clientMock.post.mockReset()
})

describe('practice api', () => {
  it('createPractice posts report_id and count', async () => {
    clientMock.post.mockResolvedValue({
      data: { practice_id: 1, report_id: 7, count: 5, questions: [] },
    })
    await createPractice(7, 5)
    expect(clientMock.post).toHaveBeenCalledWith('/practice', { report_id: 7, count: 5 })
  })

  it('getPractice fetches by id', async () => {
    clientMock.get.mockResolvedValue({
      data: { practice_id: 1, report_id: 7, count: 5, questions: [] },
    })
    await getPractice(1)
    expect(clientMock.get).toHaveBeenCalledWith('/practice/1')
  })
})
