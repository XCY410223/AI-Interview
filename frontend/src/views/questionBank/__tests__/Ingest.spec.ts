import { mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  ingestQuestionBank: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/questionBank', () => ({ ingestQuestionBank: mocks.ingestQuestionBank }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))

import Ingest from '@/views/questionBank/Ingest.vue'

interface IngestVm {
  form: { company: string; position: string; content: string; source_url: string }
  result: { item_id: number } | null
  submit: () => Promise<void>
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('QuestionBankIngestView', () => {
  it('submits valid form and shows item id', async () => {
    mocks.ingestQuestionBank.mockResolvedValue({ item_id: 3, status: 'pending', task_id: 't1' })
    const wrapper = mount(Ingest, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as IngestVm
    vm.form.company = '字节'
    vm.form.position = '后端'
    vm.form.content = '一面问了些基础'
    await vm.submit()

    expect(mocks.ingestQuestionBank).toHaveBeenCalledWith({
      company: '字节',
      position: '后端',
      difficulty: 'medium',
      content: '一面问了些基础',
      source_url: null,
    })
    expect(vm.result?.item_id).toBe(3)
    expect(wrapper.text()).toContain('#3')
    wrapper.unmount()
  })

  it('rejects non-http source_url without submitting', async () => {
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({} as never))
    const wrapper = mount(Ingest, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as IngestVm
    vm.form.company = '字节'
    vm.form.position = '后端'
    vm.form.content = '内容'
    vm.form.source_url = 'ftp://example.com'
    await vm.submit()

    expect(warn).toHaveBeenCalledWith('来源链接仅支持 http/https')
    expect(mocks.ingestQuestionBank).not.toHaveBeenCalled()
    warn.mockRestore()
    wrapper.unmount()
  })

  it('blocks submit when required fields are empty', async () => {
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({} as never))
    const wrapper = mount(Ingest, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as IngestVm
    await vm.submit()

    expect(warn).toHaveBeenCalledWith('请填写公司、岗位与面经内容')
    expect(mocks.ingestQuestionBank).not.toHaveBeenCalled()
    warn.mockRestore()
    wrapper.unmount()
  })

  it('shows error message on submit failure', async () => {
    const err = vi.spyOn(ElMessage, 'error').mockImplementation(() => ({} as never))
    mocks.ingestQuestionBank.mockRejectedValue(new Error('来源链接仅支持 http/https'))
    const wrapper = mount(Ingest, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as IngestVm
    vm.form.company = '字节'
    vm.form.position = '后端'
    vm.form.content = '内容'
    await vm.submit()

    expect(err).toHaveBeenCalledWith('来源链接仅支持 http/https')
    err.mockRestore()
    wrapper.unmount()
  })
})
