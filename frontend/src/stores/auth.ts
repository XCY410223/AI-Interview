import axios from 'axios'
import { defineStore } from 'pinia'

import type { AuthResponse, AuthTokens, LoginPayload, RegisterPayload, User } from '@/types'

import { API_BASE } from '@/api/config'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem(ACCESS_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_KEY) || '',
    user: null as User | null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
  },
  actions: {
    setTokens(tokens: AuthTokens) {
      this.accessToken = tokens.access_token
      this.refreshToken = tokens.refresh_token
      localStorage.setItem(ACCESS_KEY, tokens.access_token)
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
    },
    setUser(user: User) {
      this.user = user
    },
    clear() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
    },
    async login(payload: LoginPayload): Promise<AuthResponse> {
      const { data } = await axios.post<AuthResponse>(`${API_BASE}/auth/login`, payload)
      this.setTokens(data)
      this.setUser(data.user)
      return data
    },
    async register(payload: RegisterPayload): Promise<AuthResponse> {
      const { data } = await axios.post<AuthResponse>(`${API_BASE}/auth/register`, payload)
      this.setTokens(data)
      this.setUser(data.user)
      return data
    },
    /** 用 raw axios 刷新（绕过 client 拦截器，避免递归）。 */
    async tryRefresh(): Promise<AuthTokens> {
      const { data } = await axios.post<AuthTokens>(`${API_BASE}/auth/refresh`, {
        refresh_token: this.refreshToken,
      })
      this.setTokens(data)
      return data
    },
    async logout() {
      try {
        await axios.post(`${API_BASE}/auth/logout`, { refresh_token: this.refreshToken })
      } finally {
        this.clear()
      }
    },
  },
})
