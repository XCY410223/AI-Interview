<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { getInterviewReplay, reEvaluateAnswer } from '@/api/interview'
import { listReports } from '@/api/report'
import EmptyState from '@/components/EmptyState.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import { buildScoreEvent } from '@/stores/interview'
import { extractErrorMessage } from '@/utils/error'
import type {
  ChatBubble,
  InterviewMessage,
  InterviewReplay,
  QuestionItem,
  ReEvaluateResponse,
} from '@/types'

defineOptions({ name: 'InterviewReplayView' })

const route = useRoute()
const router = useRouter()

const interviewId = computed(() => Number(route.params.id))

const replay = ref<InterviewReplay | null>(null)
const reportId = ref<number | null>(null)
const loading = ref(true)
const reEvaluations = ref<Record<number, ReEvaluateResponse[]>>({})
const reEvaluating = ref<number | null>(null)

const DIFFICULTY_TEXT: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
const STYLE_TEXT: Record<string, string> = { friendly: '友好', stress: '压力', deep: '深挖' }
const STATUS_TEXT: Record<string, string> = { in_progress: '进行中', completed: '已完成' }

interface RoundGroup {
  round: number
  bubbles: ChatBubble[]
}

/** 逐条消息 → 气泡。红线 7：score 只取 payload_json 结构化字段，绝不从文本解析。 */
function messageToBubble(m: InterviewMessage): ChatBubble | null {
  if (m.role === 'candidate') {
    if (!m.content) return null
    return { id: m.id, role: 'user', content: m.content, score: null }
  }
  if (m.event_type === 'score') {
    return {
      id: m.id,
      role: 'interviewer',
      content: m.content ?? '',
      score: buildScoreEvent(m.payload_json, m.content ?? ''),
    }
  }
  // interviewer「next」：round 0 为基础题目（快照头部已展示，避免重复）；done 空内容跳过
  if (m.round === 0 || !m.content) return null
  return { id: m.id, role: 'interviewer', content: m.content, score: null }
}

/** 按 (question_index, round) 双键分组（追问轮次可视化）。 */
const groups = computed(() => {
  const r = replay.value
  if (!r) return [] as { question: QuestionItem; rounds: RoundGroup[] }[]
  return r.questions.map((q) => {
    const roundMap = new Map<number, ChatBubble[]>()
    for (const m of r.messages) {
      if (m.question_index !== q.question_index) continue
      const bubble = messageToBubble(m)
      if (!bubble) continue
      const list = roundMap.get(m.round) ?? []
      list.push(bubble)
      roundMap.set(m.round, list)
    }
    const rounds = [...roundMap.entries()]
      .sort(([a], [b]) => a - b)
      .map(([round, bubbles]) => ({ round, bubbles }))
    return { question: q, rounds }
  })
})

async function load() {
  loading.value = true
  try {
    const [r, reportPage] = await Promise.all([
      getInterviewReplay(interviewId.value),
      listReports(1, 100),
    ])
    replay.value = r
    const hit = reportPage.items.find((item) => item.interview_id === interviewId.value)
    reportId.value = hit?.report_id ?? null
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    loading.value = false
  }
}

async function onReEvaluate(questionIndex: number) {
  try {
    await ElMessageBox.confirm(
      '重评将独立调用 AI 计费，不会修改原评分与报告。确定重评此题？',
      '重评确认',
      { type: 'warning', confirmButtonText: '重评', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  reEvaluating.value = questionIndex
  try {
    const result = await reEvaluateAnswer(interviewId.value, questionIndex)
    const list = reEvaluations.value[questionIndex] ?? []
    reEvaluations.value[questionIndex] = [...list, result]
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    reEvaluating.value = null
  }
}

onMounted(load)

defineExpose({ replay, reportId, reEvaluations, load, onReEvaluate })
</script>

<template>
  <div class="replay-page">
    <el-page-header class="header" content="面试回放" @back="router.push('/interview/history')" />

    <template v-if="replay">
    <el-card class="summary-card">
      <p class="summary-card__meta">
        岗位：{{ replay.position }} · 难度：{{ DIFFICULTY_TEXT[replay.difficulty] ?? replay.difficulty }}
        · 风格：{{ STYLE_TEXT[replay.style] ?? replay.style }}
        · 状态：{{ STATUS_TEXT[replay.status] ?? replay.status }}
      </p>
      <template v-if="replay.report_summary || reportId != null">
        <p class="summary-card__report">报告摘要：{{ replay.report_summary || '报告已生成' }}</p>
        <el-button v-if="reportId != null" link type="primary" @click="router.push(`/report/${reportId}`)">
          查看完整报告
        </el-button>
      </template>
    </el-card>

    <el-card
      v-for="g in groups"
      :key="g.question.question_index"
      class="question-card"
    >
      <h3 class="question-title">第 {{ g.question.question_index + 1 }} 题 · {{ g.question.category }}</h3>
      <p class="question-content">{{ g.question.content }}</p>

      <div v-for="r in g.rounds" :key="r.round" class="round">
        <p v-if="r.round > 0" class="round-label">追问第 {{ r.round }} 轮</p>
        <div class="messages">
          <MessageBubble v-for="b in r.bubbles" :key="b.id" :bubble="b" />
        </div>
      </div>

      <div v-if="(reEvaluations[g.question.question_index] ?? []).length" class="re-evals">
        <div v-for="(re, i) in reEvaluations[g.question.question_index]" :key="i" class="re-eval">
          <el-tag size="small" type="warning">重评</el-tag>
          <span class="re-eval__score">{{ re.score.toFixed(1) }} 分</span>
          <span class="re-eval__feedback">{{ re.feedback }}</span>
        </div>
      </div>

      <el-button
        class="re-eval-btn"
        :loading="reEvaluating === g.question.question_index"
        @click="onReEvaluate(g.question.question_index)"
      >
        重评此题
      </el-button>
    </el-card>

    <EmptyState v-if="!groups.length" description="暂无回放数据" />
    </template>

    <el-skeleton v-else-if="loading" :rows="6" animated />
    <EmptyState v-else description="暂无回放数据" />
  </div>
</template>

<style scoped>
.replay-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
.summary-card {
  margin-bottom: 1rem;
}
.summary-card__meta {
  margin: 0 0 0.5rem;
}
.summary-card__report {
  margin: 0 0 0.5rem;
  color: var(--el-text-color-secondary);
}
.question-card {
  margin-bottom: 1rem;
}
.question-title {
  margin: 0 0 0.5rem;
}
.question-content {
  margin: 0 0 0.75rem;
  color: var(--el-text-color-regular);
}
.round {
  margin-bottom: 0.75rem;
}
.round-label {
  margin: 0 0 0.5rem;
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}
.messages {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.re-evals {
  margin: 0.75rem 0;
}
.re-eval {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border: 1px dashed var(--el-color-warning);
  border-radius: 6px;
  margin-bottom: 0.5rem;
}
.re-eval__score {
  font-weight: 700;
  color: var(--el-color-warning);
}
.re-eval__feedback {
  color: var(--el-text-color-secondary);
}
.re-eval-btn {
  margin-top: 0.25rem;
}
</style>
