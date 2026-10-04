import type { ResetTokenValidateResponse, User } from '@/types'

import { client, publicClient } from './client'

export async function fetchMe(): Promise<User> {
  const { data } = await client.get<{ user: User }>('/auth/me')
  return data.user
}

/** 请求重置密码（匿名端点，防枚举：后端无论邮箱是否注册都返回相同文案）。 */
export async function forgotPassword(email: string): Promise<void> {
  await publicClient.post('/auth/forgot-password', { email })
}

/** 校验重置 token 是否有效（后端不区分过期/无效）。 */
export async function validateResetToken(token: string): Promise<boolean> {
  const { data } = await publicClient.get<ResetTokenValidateResponse>('/auth/reset-password/validate', {
    params: { token },
  })
  return data.valid
}

/** 用一次性 token 重置密码。 */
export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await publicClient.post('/auth/reset-password', { token, new_password: newPassword })
}
