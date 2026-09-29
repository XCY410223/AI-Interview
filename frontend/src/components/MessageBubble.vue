<script setup lang="ts">
import type { ChatBubble } from '@/types'

defineProps<{ bubble: ChatBubble }>()

const DIMENSION_TEXT: Record<string, string> = {
  completeness: '完整性',
  accuracy: '准确性',
  depth: '深度',
  clarity: '表达',
}
</script>

<template>
  <div class="bubble" :class="bubble.role === 'user' ? 'bubble--user' : 'bubble--interviewer'">
    <div class="bubble__role">{{ bubble.role === 'user' ? '我' : '面试官' }}</div>
    <div class="bubble__content">{{ bubble.content }}</div>

    <div v-if="bubble.role === 'interviewer' && bubble.score" class="score-card">
      <div class="score-card__head">
        <span class="score-card__value">{{ bubble.score.score.toFixed(1) }} 分</span>
        <span class="score-card__feedback">{{ bubble.score.feedback }}</span>
      </div>
      <div v-for="(val, key) in bubble.score.dimensions" :key="key" class="score-card__dim">
        <span class="score-card__dim-label">{{ DIMENSION_TEXT[key] || key }}</span>
        <el-progress :percentage="val * 10" :show-text="false" class="score-card__bar" />
        <span class="score-card__dim-val">{{ val.toFixed(1) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bubble {
  max-width: 80%;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}
.bubble--user {
  align-self: flex-end;
  background: var(--el-color-primary-light-9);
}
.bubble--interviewer {
  align-self: flex-start;
  background: var(--el-fill-color-light);
}
.bubble__role {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.25rem;
}
.bubble__content {
  white-space: pre-wrap;
  line-height: 1.6;
}
.score-card {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: var(--el-bg-color);
  border-radius: 6px;
}
.score-card__head {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.score-card__value {
  font-weight: 700;
  color: var(--el-color-primary);
}
.score-card__feedback {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}
.score-card__dim {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}
.score-card__dim-label {
  width: 4rem;
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
}
.score-card__bar {
  flex: 1;
}
.score-card__dim-val {
  width: 2rem;
  font-size: 0.8rem;
  text-align: right;
}
</style>
