import { ref } from 'vue'

import { uploadResume } from '@/api/resume'
import type { UploadResponse } from '@/types'
import { extractErrorMessage } from '@/utils/error'

export function useUpload() {
  const uploading = ref(false)
  const error = ref<string | null>(null)

  async function upload(file: File): Promise<UploadResponse> {
    uploading.value = true
    error.value = null
    try {
      const form = new FormData()
      form.append('file', file)
      return await uploadResume(form)
    } catch (e) {
      error.value = extractErrorMessage(e)
      throw e
    } finally {
      uploading.value = false
    }
  }

  return { uploading, error, upload }
}
