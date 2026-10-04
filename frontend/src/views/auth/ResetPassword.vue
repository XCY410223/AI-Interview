<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { resetPassword, validateResetToken } from '@/api/auth'
import { extractErrorMessage } from '@/utils/error'

defineOptions({ name: 'ResetPasswordView' })

const route = useRoute()
const router = useRouter()

const token = typeof route.query.token === 'string' ? route.query.token : ''
const checking = ref(true)
const valid = ref(false)
const form = ref({ password: '', confirm: '' })
const loading = ref(false)

onMounted(async () => {
  if (!token) {
    valid.value = false
    checking.value = false
    return
  }
  try {
    valid.value = await validateResetToken(token)
  } catch {
    valid.value = false
  } finally {
    checking.value = false
  }
})

async function onSubmit() {
  if (form.value.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (form.value.password !== form.value.confirm) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await resetPassword(token, form.value.password)
    ElMessage.success('密码已重置，请重新登录')
    router.push('/login')
  } catch (e) {
    ElMessage.error(extractErrorMessage(e, '重置失败，请重新获取链接'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2>重置密码</h2>
      <p v-if="checking" class="hint">正在校验链接…</p>
      <template v-else-if="!valid">
        <p class="hint">链接已过期，请重新获取。</p>
        <router-link class="link" to="/forgot-password">重新获取</router-link>
      </template>
      <el-form v-else label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="新密码（至少 8 位）">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="form.confirm" type="password" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="onSubmit">重置密码</el-button>
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
