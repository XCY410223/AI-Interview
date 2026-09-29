import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMock = vi.hoisted(() => ({ get: vi.fn() }))
const publicClientMock = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('@/api/client', () => ({ client: clientMock, publicClient: publicClientMock }))

import { exportWaitingListCsv, subscribeWaitingList } from '@/api/waitingList'

beforeEach(() => {
  clientMock.get.mockReset()
  publicClientMock.post.mockReset()
})

describe('waitingList api', () => {
  it('subscribeWaitingList posts email via public client (no auth)', async () => {
    publicClientMock.post.mockResolvedValue({
      data: { email: 'a@b.com', already_subscribed: false },
    })
    await subscribeWaitingList('a@b.com')
    expect(publicClientMock.post).toHaveBeenCalledWith('/waiting-list', { email: 'a@b.com' })
    expect(clientMock.get).not.toHaveBeenCalled()
  })

  it('exportWaitingListCsv requests a blob', async () => {
    clientMock.get.mockResolvedValue({ data: new Blob(['email,created_at\n']) })
    await exportWaitingListCsv()
    expect(clientMock.get).toHaveBeenCalledWith('/waiting-list/export', { responseType: 'blob' })
  })
})
