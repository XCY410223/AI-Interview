<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { forgotPassword } from '@/api/auth'
import { extractErrorMessage } from '@/utils/error'

defineOptions({ name: 'ForgotPasswordView' })

const form = ref({ email: '' })
const loading = ref(false)
const submitted = ref(false)

async function onSubmit() {
  if (!form.value.email) {
    ElMessage.warning('请输入邮箱')
    return
  }
  loading.value = true
  try {
    await forgotPassword(form.value.email)
    submitted.value = true
  } catch (e) {
    ElMessage.error(extractErrorMessage(e, '发送失败，请稍后再试'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2>忘记密码</h2>
      <template v-if="submitted">
        <p class="hint">如邮箱已注册，重置邮件已发送，请查收并点击邮件中的链接。</p>
        <router-link class="link" to="/login">返回登录</router-link>
      </template>
      <el-form v-else label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" placeholder="you@example.com" />
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="onSubmit">发送重置邮件</el-button>
        <router-link class="link" to="/login">返回登录</router-link>
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
.hint {
  margin: 1rem 0;
  color: #666;
  font-size: 0.9rem;
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
