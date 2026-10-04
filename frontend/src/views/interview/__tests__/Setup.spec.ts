import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listResumes: vi.fn(),
  startInterview: vi.fn(),
  parseJD: vi.fn(),
  storeStart: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/resume', () => ({ listResumes: mocks.listResumes }))
vi.mock('@/api/interview', () => ({ startInterview: mocks.startInterview }))
vi.mock('@/api/questionBank', () => ({ parseJD: mocks.parseJD }))
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

const jdResponse = {
  position_guess: '后端工程师',
  capabilities: [
    { name: 'Kafka 消息可靠性', category: 'hard_skill', keywords: ['Kafka'], importance: 'must' },
    { name: '沟通表达', category: 'soft_skill', keywords: ['沟通'], importance: 'nice_to_have' },
  ],
  parsed_at: '2026-09-26T00:00:00Z',
}

interface SetupVm {
  form: { position: string; use_templates: boolean }
  jdText: string
  jdResult: { position_guess: string; capabilities: { name: string }[] } | null
  selectedCapabilities: string[]
  parseJD: () => Promise<void>
  submit: () => Promise<void>
}

describe('InterviewSetupView JD 定制 (M4 F8)', () => {
  it('parses JD and auto-selects must capabilities', async () => {
    mocks.parseJD.mockResolvedValue(jdResponse)
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as SetupVm
    vm.jdText = 'x'.repeat(50)
    await vm.parseJD()

    expect(vm.jdResult?.position_guess).toBe('后端工程师')
    expect(vm.selectedCapabilities).toEqual(['Kafka 消息可靠性'])
    wrapper.unmount()
  })

  it('shows error message on JD parse failure (422)', async () => {
    const err = vi.spyOn(ElMessage, 'error').mockImplementation(() => ({} as never))
    mocks.parseJD.mockRejectedValue(new Error('JD 解析失败，请重贴'))
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as SetupVm
    vm.jdText = 'x'.repeat(50)
    await vm.parseJD()

    expect(err).toHaveBeenCalledWith('JD 解析失败，请重贴')
    expect(vm.jdResult).toBeNull()
    err.mockRestore()
    wrapper.unmount()
  })

  it('shows rate-limit message on 429 AI_RATE_LIMITED', async () => {
    const err = vi.spyOn(ElMessage, 'error').mockImplementation(() => ({} as never))
    mocks.parseJD.mockRejectedValue(new Error('AI 调用过于频繁，请稍后再试'))
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as SetupVm
    vm.jdText = 'x'.repeat(50)
    await vm.parseJD()

    expect(err).toHaveBeenCalledWith('AI 调用过于频繁，请稍后再试')
    err.mockRestore()
    wrapper.unmount()
  })

  it('rejects too-short JD without calling parseJD', async () => {
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({} as never))
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as SetupVm
    vm.jdText = '太短'
    await vm.parseJD()

    expect(warn).toHaveBeenCalledWith('JD 原文需在 50~20000 字之间')
    expect(mocks.parseJD).not.toHaveBeenCalled()
    warn.mockRestore()
    wrapper.unmount()
  })

  it('passes jd_text and selected capabilities into submit payload', async () => {
    mocks.parseJD.mockResolvedValue(jdResponse)
    mocks.storeStart.mockResolvedValue(undefined)
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as SetupVm
    vm.form.position = '后端工程师'
    const jd = 'x'.repeat(60)
    vm.jdText = jd
    await vm.parseJD()
    await vm.submit()

    expect(mocks.storeStart).toHaveBeenCalledWith({
      resume_id: 1,
      config: {
        position: '后端工程师',
        difficulty: 'medium',
        question_count: 8,
        style: 'friendly',
        jd_text: jd,
        capabilities: [
          { name: 'Kafka 消息可靠性', category: 'hard_skill', keywords: ['Kafka'], importance: 'must' },
        ],
      },
    })
    wrapper.unmount()
  })

  it('passes use_templates when enabled', async () => {
    mocks.storeStart.mockResolvedValue(undefined)
    const wrapper = mount(Setup, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const vm = wrapper.vm as unknown as SetupVm
    vm.form.position = '后端工程师'
    vm.form.use_templates = true
    await vm.submit()

    expect(mocks.storeStart).toHaveBeenCalledWith({
      resume_id: 1,
      config: {
        position: '后端工程师',
        difficulty: 'medium',
        question_count: 8,
        style: 'friendly',
        use_templates: true,
      },
    })
    wrapper.unmount()
  })
})
