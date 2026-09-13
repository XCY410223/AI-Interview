import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePolling } from '@/composables/usePolling'

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('polls repeatedly and stops', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'processing' })
    const { data, start, stop } = usePolling(fetcher, { interval: 1000, backoff: false })

    start()
    await vi.advanceTimersByTimeAsync(0)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(data.value).toEqual({ status: 'processing' })

    await vi.advanceTimersByTimeAsync(1000)
    expect(fetcher).toHaveBeenCalledTimes(2)

    stop()
    const count = fetcher.mock.calls.length
    await vi.advanceTimersByTimeAsync(5000)
    expect(fetcher.mock.calls.length).toBe(count)
  })

  it('updates data until terminal status', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValueOnce({ status: 'completed' })
    const { data, start, stop } = usePolling(fetcher, { interval: 1000, backoff: false })

    start()
    await vi.advanceTimersByTimeAsync(0)
    expect(data.value).toEqual({ status: 'processing' })
    await vi.advanceTimersByTimeAsync(1000)
    expect(data.value).toEqual({ status: 'completed' })
    stop()
  })
})
