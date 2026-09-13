<script setup lang="ts">
import { computed, ref } from 'vue'

defineOptions({ name: 'RegisterView' })
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { extractErrorMessage } from '@/utils/error'

const router = useRouter()
const auth = useAuthStore()

const form = ref({ email: '', password: '', confirm: '' })
const loading = ref(false)

const passwordValid = computed(() => form.value.password.length >= 8)

async function onSubmit() {
  if (!form.value.email) {
    ElMessage.warning('请输入邮箱')
    return
  }
  if (!passwordValid.value) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (form.value.password !== form.value.confirm) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await auth.register({ email: form.value.email, password: form.value.password })
    ElMessage.success('注册成功')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(extractErrorMessage(e, '注册失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2>注册</h2>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" placeholder="you@example.com" />
        </el-form-item>
        <el-form-item label="密码（至少 8 位）">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="form.confirm" type="password" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="onSubmit">注册</el-button>
        <router-link class="link" to="/login">已有账号？去登录</router-link>
      </el-form>
    </el-card>
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
