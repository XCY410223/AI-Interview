import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useQuestionBankStore } from '@/stores/questionBank'

describe('questionBank store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('setSearchItems stores search results', () => {
    const store = useQuestionBankStore()
    const items = [
      { id: 1, company: '字节', position: '后端', difficulty: 'medium', content: 'chunk', source_url: null },
    ]
    store.setSearchItems(items)
    expect(store.searchItems).toEqual(items)
  })

  it('setTemplates stores templates and total', () => {
    const store = useQuestionBankStore()
    const templates = [
      { id: 1, position: '后端', difficulty: 'medium', category: '架构', content: 'Q', reference_points: [], tags: [], usage_count: 0, created_at: null },
    ]
    store.setTemplates(templates, 42)
    expect(store.templates).toEqual(templates)
    expect(store.templateTotal).toBe(42)
  })

  it('clear resets all state', () => {
    const store = useQuestionBankStore()
    store.setSearchItems([
      { id: 1, company: '字节', position: '后端', difficulty: 'medium', content: 'chunk', source_url: null },
    ])
    store.setTemplates(
      [{ id: 1, position: '后端', difficulty: 'medium', category: '架构', content: 'Q', reference_points: [], tags: [], usage_count: 0, created_at: null }],
      1,
    )
    store.clear()
    expect(store.searchItems).toEqual([])
    expect(store.templates).toEqual([])
    expect(store.templateTotal).toBe(0)
  })
})
