import { defineStore } from 'pinia'

import type { QuestionBankSearchItem, QuestionTemplate } from '@/types'

/** 题库域共享状态（M4）：检索结果 + 模板列表，供各视图只读消费。 */
export const useQuestionBankStore = defineStore('questionBank', {
  state: () => ({
    searchItems: [] as QuestionBankSearchItem[],
    templates: [] as QuestionTemplate[],
    templateTotal: 0,
  }),
  actions: {
    setSearchItems(items: QuestionBankSearchItem[]) {
      this.searchItems = items
    },
    setTemplates(items: QuestionTemplate[], total: number) {
      this.templates = items
      this.templateTotal = total
    },
    clear() {
      this.searchItems = []
      this.templates = []
      this.templateTotal = 0
    },
  },
})
