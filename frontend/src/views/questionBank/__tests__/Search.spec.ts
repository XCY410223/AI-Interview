import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  searchQuestionBank: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/questionBank', () => ({ searchQuestionBank: mocks.searchQuestionBank }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))

import Search from '@/views/questionBank/Search.vue'

interface SearchVm {
  form: { company: string; position: string; top_k: number }
  items: { id: number; content: string; source_url: string | null }[]
  searched: boolean
  search: () => Promise<void>
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('QuestionBankSearchView', () => {
  it('searches and renders result cards', async () => {
    mocks.searchQuestionBank.mockResolvedValue({
      items: [
        { id: 1, company: '字节', position: '后端', difficulty: 'medium', content: '真题 chunk', source_url: null },
      ],
    })
    const wrapper = mount(Search, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as SearchVm
    vm.form.company = '字节'
    vm.form.position = '后端'
    await vm.search()

    expect(mocks.searchQuestionBank).toHaveBeenCalledWith({
      company: '字节',
      position: '后端',
      difficulty: 'medium',
      top_k: 8,
    })
    expect(vm.items).toHaveLength(1)
    expect(wrapper.text()).toContain('真题 chunk')
    wrapper.unmount()
  })

  it('shows empty state when no results', async () => {
    mocks.searchQuestionBank.mockResolvedValue({ items: [] })
    const wrapper = mount(Search, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as SearchVm
    vm.form.company = '字节'
    vm.form.position = '后端'
    await vm.search()

    expect(wrapper.text()).toContain('未检索到相关真题')
    wrapper.unmount()
  })

  it('renders source_url as external link with rel=noopener', async () => {
    mocks.searchQuestionBank.mockResolvedValue({
      items: [
        { id: 1, company: '字节', position: '后端', difficulty: 'medium', content: 'chunk', source_url: 'https://example.com/jd' },
      ],
    })
    const wrapper = mount(Search, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as SearchVm
    vm.form.company = '字节'
    vm.form.position = '后端'
    await vm.search()

    const link = wrapper.find('a')
    expect(link.attributes('href')).toBe('https://example.com/jd')
    expect(link.attributes('rel')).toContain('noopener')
    wrapper.unmount()
  })
})
