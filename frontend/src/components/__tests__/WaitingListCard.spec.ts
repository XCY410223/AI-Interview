import { mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  subscribeWaitingList: vi.fn(),
}))

vi.mock('@/api/waitingList', () => ({ subscribeWaitingList: mocks.subscribeWaitingList }))

import WaitingListCard from '@/components/WaitingListCard.vue'

interface WaitingListVm {
  email: string
  submit: () => Promise<void>
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('WaitingListCard', () => {
  it('subscribes a valid email and shows success', async () => {
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({} as never))
    mocks.subscribeWaitingList.mockResolvedValue({ email: 'a@b.com', already_subscribed: false })
    const wrapper = mount(WaitingListCard, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as WaitingListVm
    vm.email = 'a@b.com'
    await vm.submit()

    expect(mocks.subscribeWaitingList).toHaveBeenCalledWith('a@b.com')
    expect(success).toHaveBeenCalledWith('订阅成功，我们会在上线时通知你')
    success.mockRestore()
    wrapper.unmount()
  })

  it('shows idempotent hint when already subscribed', async () => {
    const info = vi.spyOn(ElMessage, 'info').mockImplementation(() => ({} as never))
    mocks.subscribeWaitingList.mockResolvedValue({ email: 'a@b.com', already_subscribed: true })
    const wrapper = mount(WaitingListCard, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as WaitingListVm
    vm.email = 'a@b.com'
    await vm.submit()

    expect(info).toHaveBeenCalledWith('该邮箱已订阅，无需重复提交')
    info.mockRestore()
    wrapper.unmount()
  })

  it('rejects invalid email without calling API', async () => {
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({} as never))
    const wrapper = mount(WaitingListCard, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as WaitingListVm
    vm.email = 'not-an-email'
    await vm.submit()

    expect(warn).toHaveBeenCalledWith('请输入合法邮箱')
    expect(mocks.subscribeWaitingList).not.toHaveBeenCalled()
    warn.mockRestore()
    wrapper.unmount()
  })

  it('shows rate-limit message on 429', async () => {
    const err = vi.spyOn(ElMessage, 'error').mockImplementation(() => ({} as never))
    mocks.subscribeWaitingList.mockRejectedValue(new Error('操作过于频繁，请稍后再试'))
    const wrapper = mount(WaitingListCard, { global: { plugins: [ElementPlus] } })

    const vm = wrapper.vm as unknown as WaitingListVm
    vm.email = 'a@b.com'
    await vm.submit()

    expect(err).toHaveBeenCalledWith('操作过于频繁，请稍后再试')
    err.mockRestore()
    wrapper.unmount()
  })
})
