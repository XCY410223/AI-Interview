import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMock = vi.hoisted(() => ({ get: vi.fn() }))
const publicClientMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('@/api/client', () => ({ client: clientMock, publicClient: publicClientMock }))

import { fetchMe, forgotPassword, resetPassword, validateResetToken } from '@/api/auth'

beforeEach(() => {
  clientMock.get.mockReset()
  publicClientMock.get.mockReset()
  publicClientMock.post.mockReset()
})

describe('auth api', () => {
  it('fetchMe uses authed client', async () => {
    clientMock.get.mockResolvedValue({ data: { user: { id: 1, email: 'a@b.com', is_active: true } } })
    await fetchMe()
    expect(clientMock.get).toHaveBeenCalledWith('/auth/me')
    expect(publicClientMock.post).not.toHaveBeenCalled()
  })

  it('forgotPassword posts email via public client (no auth)', async () => {
    publicClientMock.post.mockResolvedValue({ data: {} })
    await forgotPassword('a@b.com')
    expect(publicClientMock.post).toHaveBeenCalledWith('/auth/forgot-password', { email: 'a@b.com' })
    expect(clientMock.get).not.toHaveBeenCalled()
  })

  it('validateResetToken returns valid flag', async () => {
    publicClientMock.get.mockResolvedValue({ data: { valid: true } })
    const valid = await validateResetToken('tok-123')
    expect(publicClientMock.get).toHaveBeenCalledWith('/auth/reset-password/validate', {
      params: { token: 'tok-123' },
    })
    expect(valid).toBe(true)
  })

  it('resetPassword posts token and new password', async () => {
    publicClientMock.post.mockResolvedValue({ data: {} })
    await resetPassword('tok-123', 'newpassword123')
    expect(publicClientMock.post).toHaveBeenCalledWith('/auth/reset-password', {
      token: 'tok-123',
      new_password: 'newpassword123',
    })
  })
})
