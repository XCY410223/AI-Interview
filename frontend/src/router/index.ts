import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', name: 'login', component: () => import('@/views/auth/Login.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/auth/Register.vue') },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/resume/upload',
      name: 'resume-upload',
      component: () => import('@/views/resume/Upload.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/resume/:id',
      name: 'resume-detail',
      component: () => import('@/views/resume/Detail.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/interview/setup',
      name: 'interview-setup',
      component: () => import('@/views/interview/Setup.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/interview/:id',
      name: 'interview-chat',
      component: () => import('@/views/interview/Chat.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/report',
      name: 'report-list',
      component: () => import('@/views/report/List.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/report/:id',
      name: 'report-detail',
      component: () => import('@/views/report/Detail.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/practice/:id',
      name: 'practice-pack',
      component: () => import('@/views/practice/Pack.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

// 路由守卫：未登录跳 /login（M1 计划 §6.5）
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if ((to.name === 'login' || to.name === 'register') && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
