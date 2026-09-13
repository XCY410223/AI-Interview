import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'

import { API_BASE } from './config'

/** axios 实例：自动附加 access token + 401 自动 refresh 续期。 */
export const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

/** 401 响应拦截：access 过期自动 refresh 续期并重放；续期失败清空并跳登录（§6.2）。 */
export async function onUnauthorized(error: AxiosError) {
  const auth = useAuthStore()
  const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined

  if (error.response?.status === 401 && original && !original._retried && auth.refreshToken) {
    original._retried = true
    try {
      const tokens = await auth.tryRefresh()
      original.headers.Authorization = `Bearer ${tokens.access_token}`
      return client.request(original)
    } catch {
      auth.clear()
      router.push({ name: 'login' })
    }
  }
  return Promise.reject(error)
}

client.interceptors.response.use((response) => response, onUnauthorized)
