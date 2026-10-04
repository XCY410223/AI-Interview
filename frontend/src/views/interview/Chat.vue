<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { listReports } from '@/api/report'
import MessageBubble from '@/components/MessageBubble.vue'
import { usePolling } from '@/composables/usePolling'
import { useInterviewStore } from '@/stores/interview'
import { extractErrorMessage } from '@/utils/error'
import type { PageResult, ReportListItem } from '@/types'

defineOptions({ name: 'InterviewChatView' })

const MAX_ANSWER_LEN = 4000 // 对齐后端 SubmitAnswerRequest.max_length（规范 §9.4）
const MAX_REPORT_TRIES = 30 // ≈45s，未命中则降级为手动入口

const route = useRoute()
const router = useRouter()
const store = useInterviewStore()

const interviewId = computed(() => Number(route.params.id))
const input = ref('')

const STYLE_TEXT: Record<string, string> = { friendly: '友好', stress: '压力', deep: '深挖' }

const status = computed(() => store.status)

const progress = computed(() => {
  const total = store.totalQuestions
  const base = total > 0 ? `第 ${store.questionIndex + 1}/${total} 题` : `第 ${store.questionIndex + 1} 题`
  return store.round > 0 ? `${base} · 追问第 ${store.round} 轮` : base
})

// 结束 → 报告承接（D3）：轮询 listReports 按 interview_id 匹配 report_id
const {
  data: reportPage,
  start: startReportPoll,
  stop: stopReportPoll,
} = usePolling<PageResult<ReportListItem>>(() => listReports(1, 20), { interval: 1500, backoff: false })
const reportTries = ref(0)
const reportTimeout = ref(false)

watch(
  () => store.status,
  (s) => {
    if (s === 'finished') startReportPoll()
  },
)

watch(reportPage, (page) => {
  if (!page) return
  const hit = page.items.find((r) => r.interview_id === interviewId.value)
  if (hit) {
    stopReportPoll()
    router.push(`/report/${hit.report_id}`)
    return
  }
  reportTries.value += 1
  if (reportTries.value >= MAX_REPORT_TRIES) {
    stopReportPoll()
    reportTimeout.value = true
  }
})

onMounted(async () => {
  // 断线/刷新恢复（§8.2）：store 为空或属于别的面试 → 从服务端重建现场
  if (!store.interviewId || store.interviewId !== interviewId.value) {
    store.reset()
    try {
      await store.resumeFromServer(interviewId.value)
    } catch (e) {
      ElMessage.error(extractErrorMessage(e))
      router.push('/dashboard')
    }
  }
})

onUnmounted(() => store.abortStream())

async function onSubmit() {
  const content = input.value.trim()
  if (!content) return
  if (content.length > MAX_ANSWER_LEN) {
    ElMessage.warning(`回答不能超过 ${MAX_ANSWER_LEN} 字`)
    return
  }
  try {
    await store.submitAnswer(content)
    input.value = '' // 成功才清空；失败保留，供「重新提交本轮」复用
  } catch (e) {
    ElMessage.error(extractErrorMessage(e, store.error?.message ?? '提交失败'))
  }
}

async function onAbort() {
  try {
    await ElMessageBox.confirm('确定要中止本次面试吗？中止后可重新提交当前轮', '中止面试', {
      type: 'warning',
      confirmButtonText: '中止',
      cancelButtonText: '继续面试',
    })
  } catch {
    return
  }
  store.abortStream()
  ElMessage.info('已中止当前作答，可继续输入')
}

defineExpose({ submit: onSubmit, input })
</script>

<template>
  <div class="chat-page">
    <header class="chat-header">
      <div class="chat-header__progress">{{ progress }}</div>
      <div class="chat-header__right">
        <el-tag v-if="store.style" size="small" effect="plain">{{ STYLE_TEXT[store.style] || store.style }}</el-tag>
        <el-button
          v-if="status !== 'finished'"
          size="small"
          type="danger"
          plain
          :disabled="status === 'streaming'"
          @click="onAbort"
        >
          中止面试
        </el-button>
      </div>
    </header>

    <el-scrollbar class="chat-scroll">
      <div class="messages">
        <MessageBubble v-for="bubble in store.messages" :key="bubble.id" :bubble="bubble" />
      </div>
    </el-scrollbar>

    <footer v-if="status !== 'finished'" class="chat-input">
      <div v-if="status === 'error'" class="error-box">
        <el-alert
          :title="store.error?.message || '提交失败，请重试'"
          type="error"
          :closable="false"
          show-icon
        />
        <div class="error-box__actions">
          <el-button v-if="store.error?.code === 'AI_TIMEOUT'" type="primary" @click="onSubmit">
            重新提交本轮
          </el-button>
          <el-button v-if="store.error?.code === 'INVALID_STATE'" @click="router.push('/dashboard')">
            返回首页
          </el-button>
        </div>
      </div>

      <el-input
        v-model="input"
        type="textarea"
        :rows="3"
        :maxlength="MAX_ANSWER_LEN"
        show-word-limit
        :disabled="status === 'streaming'"
        placeholder="请输入你的回答…"
      />
      <div class="chat-input__actions">
        <el-button
          type="primary"
          :loading="status === 'streaming'"
          :disabled="status === 'streaming' || !input.trim()"
          @click="onSubmit"
        >
          提交回答
        </el-button>
      </div>
    </footer>

    <footer v-else class="chat-finished">
      <el-card shadow="never">
        <h3>面试结束</h3>
        <template v-if="!reportTimeout">
          <p class="chat-finished__hint">报告生成中…</p>
        </template>
        <template v-else>
          <p class="chat-finished__hint">报告生成较慢，稍后可在「我的报告」查看</p>
          <el-button type="primary" @click="router.push('/report')">查看我的报告</el-button>
        </template>
        <el-button @click="router.push('/dashboard')">返回首页</el-button>
      </el-card>
    </footer>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 860px;
  margin: 0 auto;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.chat-header__progress {
  font-weight: 600;
}
.chat-header__right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.chat-scroll {
  flex: 1;
  min-height: 0;
}
.messages {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.chat-input {
  padding: 1rem;
  border-top: 1px solid var(--el-border-color-lighter);
}
.chat-input__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.75rem;
}
.error-box {
  margin-bottom: 0.75rem;
}
.error-box__actions {
  margin-top: 0.5rem;
}
.chat-finished {
  padding: 1rem;
}
.chat-finished__hint {
  margin: 0.5rem 0 1rem;
  color: var(--el-text-color-secondary);
}
</style>
