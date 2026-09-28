<script setup lang="ts">
import { ref } from 'vue'

defineOptions({ name: 'LoginView' })
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { extractErrorMessage } from '@/utils/error'
import WaitingListCard from '@/components/WaitingListCard.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = ref({ email: '', password: '' })
const loading = ref(false)

async function onSubmit() {
  if (!form.value.email || !form.value.password) {
    ElMessage.warning('请输入邮箱和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.value)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' ? redirect : '/dashboard')
  } catch (e) {
    ElMessage.error(extractErrorMessage(e, '登录失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2>登录</h2>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" placeholder="you@example.com" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="onSubmit">登录</el-button>
        <router-link class="link" to="/register">没有账号？去注册</router-link>
      </el-form>
    </el-card>

    <WaitingListCard class="waiting" />
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  padding-top: 4rem;
}
.auth-card {
  width: 360px;
}
.waiting {
  position: absolute;
  bottom: 2rem;
  width: 360px;
}
.submit {
  width: 100%;
}
.link {
  display: block;
  margin-top: 1rem;
  text-align: center;
  font-size: 0.85rem;
}
</style>
