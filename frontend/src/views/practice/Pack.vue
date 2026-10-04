<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { getPractice } from '@/api/practice'
import EmptyState from '@/components/EmptyState.vue'
import { extractErrorMessage } from '@/utils/error'
import type { PracticePack } from '@/types'
import { ElMessage } from 'element-plus'

defineOptions({ name: 'PracticePackView' })

const route = useRoute()
const router = useRouter()

const practiceId = computed(() => Number(route.params.id))
const pack = ref<PracticePack | null>(null)
const loading = ref(true)

const DIFFICULTY_TEXT: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

onMounted(async () => {
  loading.value = true
  try {
    pack.value = await getPractice(practiceId.value)
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="pack-page">
    <el-page-header class="header" content="专项练习" @back="router.back()" />

    <el-alert
      class="notice"
      type="info"
      :closable="false"
      show-icon
      title="练习为自测形态，作答能力尚未开放；如需正式面试，请点「再练一场」回到面试配置。"
    />

    <el-card v-if="pack">
      <h3 class="pack-title">练习包 #{{ pack.practice_id }}（共 {{ pack.count }} 题）</h3>

      <div v-if="pack.questions.length" class="questions">
        <div v-for="(q, i) in pack.questions" :key="i" class="question">
          <div class="question__meta">
            第 {{ q.question_index + 1 }} 题 · {{ q.category }} · {{ DIFFICULTY_TEXT[q.difficulty] ?? q.difficulty }}
          </div>
          <p class="question__content">{{ q.content }}</p>
          <ul v-if="q.reference_points.length" class="question__points">
            <li v-for="(p, j) in q.reference_points" :key="j">{{ p }}</li>
          </ul>
        </div>
      </div>
      <EmptyState v-else description="练习包暂无题目" />

      <div class="actions">
        <el-button type="primary" @click="router.push('/interview/setup')">再练一场</el-button>
        <el-button @click="router.back()">返回</el-button>
      </div>
    </el-card>

    <el-skeleton v-else-if="loading" :rows="6" animated />
  </div>
</template>

<style scoped>
.pack-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
.notice {
  margin-bottom: 1rem;
}
.pack-title {
  margin: 0 0 1rem;
}
.questions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.question {
  padding: 0.75rem 1rem;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.question__meta {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
  margin-bottom: 0.25rem;
}
.question__content {
  margin: 0 0 0.5rem;
  white-space: pre-wrap;
}
.question__points {
  margin: 0;
  padding-left: 1.2rem;
  color: var(--el-text-color-regular);
}
.actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
</style>
