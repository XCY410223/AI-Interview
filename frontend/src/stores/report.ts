import { defineStore } from 'pinia'

import type { ReportDetail, ReportStatus } from '@/types'

export const useReportStore = defineStore('report', {
  state: () => ({
    current: null as ReportDetail | null,
  }),
  getters: {
    status: (state): ReportStatus | null => state.current?.status ?? null,
  },
  actions: {
    setCurrent(report: ReportDetail) {
      this.current = report
    },
    clear() {
      this.current = null
    },
  },
})
