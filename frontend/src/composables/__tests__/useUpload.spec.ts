import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/resume', () => ({ uploadResume: vi.fn() }))

import { uploadResume } from '@/api/resume'
import { useUpload } from '@/composables/useUpload'
import type { UploadResponse } from '@/types'

describe('useUpload', () => {
  it('uploads file and returns response', async () => {
    const resp: UploadResponse = { id: 1, status: 'pending', uploaded_at: '2026-09-13T00:00:00Z' }
    vi.mocked(uploadResume).mockResolvedValue(resp)

    const { upload } = useUpload()
    const file = new File(['x'], 'a.pdf', { type: 'application/pdf' })
    const result = await upload(file)

    expect(result).toEqual(resp)
    expect(uploadResume).toHaveBeenCalledTimes(1)
  })

  it('surfaces error message on failure', async () => {
    vi.mocked(uploadResume).mockRejectedValue(new Error('上传失败'))
    const { upload, error } = useUpload()
    await expect(upload(new File(['x'], 'a.pdf'))).rejects.toThrow()
    expect(error.value).toBe('上传失败')
  })
})
