import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosError } from 'axios'

const { pushMock, authMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  authMock: {
    accessToken: '',
    refreshToken: '',
    clear: vi.fn(),
    tryRefresh: vi.fn(),
  },
}))

vi.mock('@/router', () => ({ default: { push: pushMock } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authMock }))

import { client, onUnauthorized } from '@/api/client'

function make401(config?: Record<string, unknown>): AxiosError {
  return {
    response: { status: 401 },
    config: { headers: {}, ...(config ?? {}) },
  } as unknown as AxiosError
}

beforeEach(() => {
  pushMock.mockReset()
  authMock.accessToken = ''
  authMock.refreshToken = ''
  authMock.clear.mockReset()
  authMock.tryRefresh.mockReset()
})

describe('onUnauthorized interceptor', () => {
  it('retries request with refreshed token on 401', async () => {
    authMock.refreshToken = 'rt'
    authMock.tryRefresh.mockResolvedValue({ access_token: 'new-at', refresh_token: 'new-rt' })
    const requestSpy = vi.spyOn(client, 'request').mockResolvedValue({ data: 'ok' })

    const error = make401()
    const result = await onUnauthorized(error)

    expect(authMock.tryRefresh).toHaveBeenCalled()
    expect(requestSpy).toHaveBeenCalled()
    expect(result).toEqual({ data: 'ok' })
    expect((error.config as { headers: Record<string, string> }).headers.Authorization).toBe('Bearer new-at')
  })

  it('clears auth and redirects to login on refresh failure', async () => {
    authMock.refreshToken = 'rt'
    authMock.tryRefresh.mockRejectedValue(new Error('expired'))
    const requestSpy = vi.spyOn(client, 'request').mockResolvedValue({})

    const error = make401()
    await expect(onUnauthorized(error)).rejects.toBe(error)

    expect(authMock.clear).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith({ name: 'login' })
    expect(requestSpy).not.toHaveBeenCalled()
  })

  it('rejects non-401 errors unchanged', async () => {
    const error = { response: { status: 500 }, config: { headers: {} } } as unknown as AxiosError
    await expect(onUnauthorized(error)).rejects.toBe(error)
    expect(authMock.tryRefresh).not.toHaveBeenCalled()
  })

  it('does not retry twice (respects _retried flag)', async () => {
    authMock.refreshToken = 'rt'
    const error = make401({ _retried: true })
    await expect(onUnauthorized(error)).rejects.toBe(error)
    expect(authMock.tryRefresh).not.toHaveBeenCalled()
  })
})
