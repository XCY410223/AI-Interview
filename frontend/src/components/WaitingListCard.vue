<script setup lang="ts">
import { ref } from 'vue'

import { ElMessage } from 'element-plus'

import { subscribeWaitingList } from '@/api/waitingList'
import { extractErrorMessage } from '@/utils/error'

defineOptions({ name: 'WaitingListCard' })

const email = ref('')
const submitting = ref(false)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

async function onSubmit() {
  if (submitting.value) return
  const value = email.value.trim()
  if (!EMAIL_RE.test(value)) {
    ElMessage.warning('请输入合法邮箱')
    return
  }
  submitting.value = true
  try {
    const result = await subscribeWaitingList(value)
    if (result.already_subscribed) ElMessage.info('该邮箱已订阅，无需重复提交')
    else ElMessage.success('订阅成功，我们会在上线时通知你')
    email.value = ''
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    submitting.value = false
  }
}

defineExpose({ email, submit: onSubmit })
</script>

<template>
  <div class="waiting-list-card">
    <h4>抢先体验</h4>
    <p class="hint">留下邮箱，上线时第一时间通知你。</p>
    <div class="row">
      <el-input v-model="email" placeholder="you@example.com" @keyup.enter="onSubmit" />
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="submitting"
        @click="onSubmit"
      >
        订阅
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.waiting-list-card {
  padding: 1rem;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.waiting-list-card h4 {
  margin: 0 0 0.25rem;
}
.hint {
  margin: 0 0 0.75rem;
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}
.row {
  display: flex;
  gap: 0.5rem;
}
</style>
