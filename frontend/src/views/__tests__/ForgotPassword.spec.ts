import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ forgotPassword: vi.fn() }))

vi.mock('@/api/auth', () => ({ forgotPassword: mocks.forgotPassword }))

import ForgotPassword from '@/views/auth/ForgotPassword.vue'

function mountView() {
  return mount(ForgotPassword, {
    global: { plugins: [ElementPlus], stubs: { RouterLink: RouterLinkStub } },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.forgotPassword.mockResolvedValue(undefined)
})

describe('ForgotPasswordView', () => {
  it('renders email form', () => {
    const wrapper = mountView()
    expect(wrapper.text()).toContain('忘记密码')
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('submits and shows fixed success message regardless of email existence', async () => {
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('button.submit').trigger('click')
    await flushPromises()

    expect(mocks.forgotPassword).toHaveBeenCalledWith('a@b.com')
    expect(wrapper.text()).toContain('如邮箱已注册，重置邮件已发送')
    wrapper.unmount()
  })

  it('does not submit empty email', async () => {
    const wrapper = mountView()
    await wrapper.find('button.submit').trigger('click')
    await flushPromises()
    expect(mocks.forgotPassword).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
