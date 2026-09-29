import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listTemplates: vi.fn(),
  createTemplate: vi.fn(),
  updateTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/questionBank', () => ({
  listTemplates: mocks.listTemplates,
  createTemplate: mocks.createTemplate,
  updateTemplate: mocks.updateTemplate,
  deleteTemplate: mocks.deleteTemplate,
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))

import Templates from '@/views/questionBank/Templates.vue'

const templateRow = {
  id: 1,
  position: '后端',
  difficulty: 'medium',
  category: '架构',
  content: '如何设计高并发系统？',
  reference_points: ['要点一', '要点二'],
  tags: ['架构'],
  usage_count: 0,
  created_at: null,
}

interface TemplatesVm {
  rows: typeof templateRow[]
  form: { position: string; category: string; content: string; reference_points: string; tags: string[] }
  load: () => Promise<void>
  openCreate: () => void
  openEdit: (row: typeof templateRow) => void
  submit: () => Promise<void>
  remove: (row: typeof templateRow) => Promise<void>
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listTemplates.mockResolvedValue({ total: 1, items: [templateRow] })
})

describe('QuestionBankTemplatesView', () => {
  it('loads template list on mount', async () => {
    const wrapper = mount(Templates, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(mocks.listTemplates).toHaveBeenCalledWith(1, 10, undefined)
    expect(wrapper.text()).toContain('如何设计高并发系统？')
    wrapper.unmount()
  })

  it('creates a template with newline-split reference_points', async () => {
    mocks.createTemplate.mockResolvedValue(templateRow)
    const wrapper = mount(Templates, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as TemplatesVm
    vm.openCreate()
    vm.form.position = '后端'
    vm.form.category = '架构'
    vm.form.content = '如何设计高并发系统？'
    vm.form.reference_points = '要点一\n要点二\n'
    vm.form.tags = ['架构']
    await vm.submit()

    expect(mocks.createTemplate).toHaveBeenCalledWith({
      position: '后端',
      difficulty: 'medium',
      category: '架构',
      content: '如何设计高并发系统？',
      reference_points: ['要点一', '要点二'],
      tags: ['架构'],
    })
    wrapper.unmount()
  })

  it('pre-fills form on edit', async () => {
    const wrapper = mount(Templates, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as TemplatesVm
    vm.openEdit(templateRow)

    expect(vm.form.position).toBe('后端')
    expect(vm.form.reference_points).toBe('要点一\n要点二')
    expect(vm.form.tags).toEqual(['架构'])
    wrapper.unmount()
  })

  it('updates an existing template', async () => {
    mocks.updateTemplate.mockResolvedValue(templateRow)
    const wrapper = mount(Templates, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as TemplatesVm
    vm.openEdit(templateRow)
    vm.form.content = '更新后的内容'
    await vm.submit()

    expect(mocks.updateTemplate).toHaveBeenCalledWith(1, expect.objectContaining({ content: '更新后的内容' }))
    wrapper.unmount()
  })

  it('deletes after confirmation', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    vi.spyOn(ElMessage, 'success').mockImplementation(() => ({} as never))
    mocks.deleteTemplate.mockResolvedValue(undefined)
    const wrapper = mount(Templates, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as TemplatesVm
    await vm.remove(templateRow)

    expect(confirm).toHaveBeenCalled()
    expect(mocks.deleteTemplate).toHaveBeenCalledWith(1)
    confirm.mockRestore()
    wrapper.unmount()
  })

  it('skips delete when cancelled', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as never)
    const wrapper = mount(Templates, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as TemplatesVm
    await vm.remove(templateRow)

    expect(mocks.deleteTemplate).not.toHaveBeenCalled()
    confirm.mockRestore()
    wrapper.unmount()
  })
})
