import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  validateResetToken: vi.fn(),
  resetPassword: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/auth', () => ({
  validateResetToken: mocks.validateResetToken,
  resetPassword: mocks.resetPassword,
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { token: 'tok-123' } }),
  useRouter: () => ({ push: mocks.push }),
}))

import ResetPassword from '@/views/auth/ResetPassword.vue'

function mountView() {
  return mount(ResetPassword, {
    global: { plugins: [ElementPlus], stubs: { RouterLink: RouterLinkStub } },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.validateResetToken.mockResolvedValue(true)
  mocks.resetPassword.mockResolvedValue(undefined)
})

describe('ResetPasswordView', () => {
  it('shows expired message when token invalid', async () => {
    mocks.validateResetToken.mockResolvedValue(false)
    const wrapper = mountView()
    await flushPromises()

    expect(mocks.validateResetToken).toHaveBeenCalledWith('tok-123')
    expect(wrapper.text()).toContain('链接已过期，请重新获取')
    wrapper.unmount()
  })

  it('shows password form when token valid', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('新密码')
    wrapper.unmount()
  })

  it('rejects mismatched passwords', async () => {
    const wrapper = mountView()
    await flushPromises()

    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('password123')
    await inputs[1].setValue('different123')
    await wrapper.find('button.submit').trigger('click')
    await flushPromises()

    expect(mocks.resetPassword).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('submits reset and navigates to login', async () => {
    const wrapper = mountView()
    await flushPromises()

    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('password123')
    await inputs[1].setValue('password123')
    await wrapper.find('button.submit').trigger('click')
    await flushPromises()

    expect(mocks.resetPassword).toHaveBeenCalledWith('tok-123', 'password123')
    expect(mocks.push).toHaveBeenCalledWith('/login')
    wrapper.unmount()
  })
})
