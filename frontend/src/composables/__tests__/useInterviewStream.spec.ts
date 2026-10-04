import { beforeEach, describe, expect, it, vi } from 'vitest'

const storeMock = vi.hoisted(() => ({
  submitAnswer: vi.fn(),
  abortStream: vi.fn(),
}))

vi.mock('@/stores/interview', () => ({ useInterviewStore: () => storeMock }))

import { useInterviewStream } from '@/composables/useInterviewStream'

beforeEach(() => {
  storeMock.submitAnswer.mockReset()
  storeMock.abortStream.mockReset()
})

describe('useInterviewStream', () => {
  it('submit delegates to the store', async () => {
    storeMock.submitAnswer.mockResolvedValue(undefined)
    const { submit } = useInterviewStream()
    await submit('我的回答')
    expect(storeMock.submitAnswer).toHaveBeenCalledWith('我的回答')
  })

  it('prevents double submit while streaming (规范 §6.2)', async () => {
    let resolve!: () => void
    storeMock.submitAnswer.mockImplementation(() => new Promise<void>((r) => { resolve = r }))

    const { submit } = useInterviewStream()
    const first = submit('答')
    await submit('重复') // submitting 中，应被忽略
    resolve()
    await first

    expect(storeMock.submitAnswer).toHaveBeenCalledTimes(1)
  })

  it('propagates submit errors', async () => {
    storeMock.submitAnswer.mockRejectedValue(new Error('评语生成超时'))
    const { submit } = useInterviewStream()
    await expect(submit('答')).rejects.toThrow('评语生成超时')
  })

  it('abort delegates to the store', () => {
    const { abort } = useInterviewStream()
    abort()
    expect(storeMock.abortStream).toHaveBeenCalled()
  })
})
