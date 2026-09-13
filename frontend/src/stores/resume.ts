import { defineStore } from 'pinia'

import type { ResumeDetail, ResumeStatus, UploadResponse } from '@/types'

export const useResumeStore = defineStore('resume', {
  state: () => ({
    current: null as ResumeDetail | null,
    upload: null as UploadResponse | null,
  }),
  getters: {
    status: (state): ResumeStatus | null => state.current?.status ?? state.upload?.status ?? null,
  },
  actions: {
    setUpload(resp: UploadResponse) {
      this.upload = resp
    },
    setCurrent(resume: ResumeDetail) {
      this.current = resume
    },
    clear() {
      this.current = null
      this.upload = null
    },
  },
})
