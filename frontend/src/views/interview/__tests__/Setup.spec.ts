import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listResumes: vi.fn(),
  startInterview: vi.fn(),
  storeStart: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/resume', () => ({ listResumes: mocks.listResumes }))
vi.mock('@/api/interview', () => ({ startInterview: mocks.startInterview }))
vi.mock('@/stores/interview', () => ({
  useInterviewStore: () => ({ start: mocks.storeStart, interviewId: 9 }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))

import Setup from '@/views/interview/Setup.vue'

function resume(status: string, id = 1) {
  return { id, status, original_ext: 'pdf', uploaded_at: '2026-09-20' }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listResumes.mockResolvedValue({ total: 1, items: [resume('completed')] })
})

describe('InterviewSetupView', () => {
  it('only lists completed resumes and submits with nested config', async () => {
    mocks.listResumes.mockResolvedValue({
      total: 3,
      items: [resume('completed', 1), resume('pending', 2), resume('failed', 3)],
    })
    mocks.storeStart.mockResolvedValue(undefined)

    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: { position: string }; submit: () => Promise<void> }
    vm.form.position = '后端工程师'
    await vm.submit()

    expect(mocks.storeStart).toHaveBeenCalledTimes(1)
    expect(mocks.storeStart).toHaveBeenCalledWith({
      resume_id: 1,
      config: { position: '后端工程师', difficulty: 'medium', question_count: 8, style: 'friendly' },
    })
    expect(mocks.push).toHaveBeenCalledWith('/interview/9')
    wrapper.unmount()
  })

  it('shows empty state when no completed resume', async () => {
    mocks.listResumes.mockResolvedValue({ total: 1, items: [resume('processing')] })
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('请先上传')
    wrapper.unmount()
  })

  it('blocks submit when position is empty', async () => {
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { submit: () => Promise<void> }
    await vm.submit()

    expect(warn).toHaveBeenCalledWith('请输入目标岗位')
    expect(mocks.storeStart).not.toHaveBeenCalled()
    warn.mockRestore()
    wrapper.unmount()
  })

  it('prevents double submit (规范 §6.2)', async () => {
    let resolveStart!: () => void
    mocks.storeStart.mockImplementation(() => new Promise<void>((r) => { resolveStart = r }))
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: { position: string }; submit: () => Promise<void> }
    vm.form.position = '后端工程师'
    const first = vm.submit()
    await vm.submit() // submitting 中，应被忽略
    resolveStart()
    await first

    expect(mocks.storeStart).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
