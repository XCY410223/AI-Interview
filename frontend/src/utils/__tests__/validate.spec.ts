import { describe, expect, it } from 'vitest'

import { validateResumeFile } from '@/utils/validate'

describe('validateResumeFile', () => {
  it('accepts pdf', () => {
    expect(validateResumeFile(new File(['x'], 'a.pdf', { type: 'application/pdf' }))).toBeNull()
  })

  it('accepts docx', () => {
    expect(
      validateResumeFile(new File(['x'], 'a.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })),
    ).toBeNull()
  })

  it('rejects wrong extension', () => {
    expect(validateResumeFile(new File(['x'], 'a.exe', { type: 'application/pdf' }))).toContain('PDF')
  })

  it('rejects oversized file', () => {
    const file = new File(['x'], 'a.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 11 * 1024 * 1024 })
    expect(validateResumeFile(file)).toContain('10MB')
  })
})
