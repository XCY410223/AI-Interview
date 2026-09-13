import type { User } from '@/types'

import { client } from './client'

export async function fetchMe(): Promise<User> {
  const { data } = await client.get<{ user: User }>('/auth/me')
  return data.user
}
