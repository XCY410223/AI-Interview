import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'

vi.mock('axios', () => ({ default: { post: vi.fn() } }))

import { useAuthStore } from '@/stores/auth'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.mocked(axios.post).mockReset()
  })

  it('login sets tokens and user', async () => {
    vi.mocked(axios.post).mockResolvedValue({
      data: { user: { id: 1, email: 'a@b.com' }, access_token: 'at', refresh_token: 'rt' },
    })
    const auth = useAuthStore()
    await auth.login({ email: 'a@b.com', password: 'password123' })

    expect(auth.accessToken).toBe('at')
    expect(auth.refreshToken).toBe('rt')
    expect(auth.user?.email).toBe('a@b.com')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/auth/login', { email: 'a@b.com', password: 'password123' })
  })

  it('clear removes tokens', () => {
    const auth = useAuthStore()
    auth.setTokens({ access_token: 'at', refresh_token: 'rt' })
    expect(auth.isAuthenticated).toBe(true)
    auth.clear()
    expect(auth.accessToken).toBe('')
    expect(auth.isAuthenticated).toBe(false)
  })

  it('tryRefresh posts refresh token and updates', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: { access_token: 'new-at', refresh_token: 'new-rt' } })
    const auth = useAuthStore()
    auth.refreshToken = 'old-rt'
    await auth.tryRefresh()
    expect(auth.accessToken).toBe('new-at')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/auth/refresh', { refresh_token: 'old-rt' })
  })
})
