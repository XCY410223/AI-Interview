<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElMessage } from 'element-plus'

import { createReport, downloadReportPdf, exportReportPdf, getReport } from '@/api/report'
import { createPractice } from '@/api/practice'
import { usePolling } from '@/composables/usePolling'
import RadarChart from '@/components/RadarChart.vue'
import ReportSectionCard from '@/components/ReportSectionCard.vue'
import { useReportStore } from '@/stores/report'
import { extractErrorMessage } from '@/utils/error'
import type { ReportDetail } from '@/types'

defineOptions({ name: 'ReportDetailView' })

const route = useRoute()
const router = useRouter()
const reportStore = useReportStore()

const reportId = computed(() => Number(route.params.id))
const exporting = ref(false)
const practiceCount = ref(5)
const generatingPractice = ref(false)

// 报告页用固定 1.5s 轮询（backoff: false），避免退避到 30s 让首屏等太久（M3 计划 §八）
const { data, start, stop } = usePolling<ReportDetail>(
  () => getReport(reportId.value),
  { interval: 1500, backoff: false },
)

const status = computed(() => data.value?.status ?? 'pending')

onMounted(() => start())

watch(data, (report) => {
  if (!report) return
  reportStore.setCurrent(report)
  if (report.status === 'completed' || report.status === 'failed') stop()
})

function retry() {
  if (!data.value) return
  void createReport(data.value.interview_id)
    .then(() => {
      if (data.value) data.value.status = 'pending'
      start()
    })
    .catch((e) => ElMessage.error(extractErrorMessage(e)))
}

async function waitForPdf(): Promise<boolean> {
  for (let i = 0; i < 20; i++) {
    const report = await getReport(reportId.value)
    data.value = report
    if (report.pdf_ready) return true
    await new Promise((resolve) => setTimeout(resolve, 1500))
  }
  return false
}

async function downloadPdf() {
  const blob = await downloadReportPdf(reportId.value)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `面试评估报告_${reportId.value}.pdf`
  document.body.appendChild(a) // Firefox 需元素在 DOM 中才能触发下载
  a.click()
  a.remove()
  // 延迟 revoke：立即 revoke 会让部分浏览器在下载真正开始前回收 blob URL
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function exportPdf() {
  if (!data.value || exporting.value) return
  exporting.value = true
  try {
    await exportReportPdf(reportId.value)
    const ready = await waitForPdf()
    if (ready) await downloadPdf()
    else ElMessage.warning('PDF 生成超时，请稍后重试')
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    exporting.value = false
  }
}

/** 针对报告弱项生成专项练习包（计入 AI 限流）。 */
async function generatePractice() {
  if (generatingPractice.value) return
  generatingPractice.value = true
  try {
    const pack = await createPractice(reportId.value, practiceCount.value)
    router.push(`/practice/${pack.practice_id}`)
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    generatingPractice.value = false
  }
}

defineExpose({ generatePractice, practiceCount })
</script>

<template>
  <div class="report-page">
    <template v-if="status === 'pending' || status === 'processing'">
      <el-card class="report-card" shadow="never">
        <el-progress :percentage="status === 'processing' ? 60 : 20" />
        <p class="report-card__hint">{{ status === 'processing' ? '正在生成报告…' : '报告排队中…' }}</p>
      </el-card>
    </template>

    <template v-else-if="status === 'failed'">
      <el-alert
        type="error"
        :closable="false"
        show-icon
        :title="data?.error_message || '报告生成失败，请重试'"
      />
      <div class="report-actions">
        <el-button type="primary" @click="retry">重新生成</el-button>
        <el-button @click="router.back()">返回</el-button>
      </div>
    </template>

    <template v-else-if="status === 'completed' && data">
      <div class="report-header">
        <h1 class="report-header__title">面试评估报告</h1>
        <div class="report-header__score">{{ data.overall_score ?? '—' }}</div>
        <el-tag v-if="data.grade" type="primary">{{ data.grade }}</el-tag>
      </div>

      <el-card class="report-card" shadow="never">
        <RadarChart :dimensions="data.dimensions" />
      </el-card>

      <ReportSectionCard title="整体评价">
        <p class="report-text">{{ data.summary || '—' }}</p>
        <p v-if="data.hire_recommendation" class="report-text">
          <b>录用建议：</b>{{ data.hire_recommendation }}
        </p>
      </ReportSectionCard>

      <ReportSectionCard title="优势">
        <ul v-if="data.strengths.length" class="report-list">
          <li v-for="(item, i) in data.strengths" :key="i">{{ item }}</li>
        </ul>
        <p v-else class="report-text">—</p>
      </ReportSectionCard>

      <ReportSectionCard title="不足">
        <ul v-if="data.weaknesses.length" class="report-list">
          <li v-for="(item, i) in data.weaknesses" :key="i">{{ item }}</li>
        </ul>
        <p v-else class="report-text">—</p>
      </ReportSectionCard>

      <ReportSectionCard title="改进建议">
        <ul v-if="data.suggestions.length" class="report-list">
          <li v-for="(item, i) in data.suggestions" :key="i">{{ item }}</li>
        </ul>
        <p v-else class="report-text">—</p>
      </ReportSectionCard>

      <ReportSectionCard title="逐题明细">
        <template v-if="data.question_scores.length">
          <div v-for="(q, i) in data.question_scores" :key="i" class="question-item">
            <div class="question-item__meta">
              第 {{ q.question_index + 1 }} 题 · 第 {{ q.round + 1 }} 轮 · 评分 {{ q.score }}
            </div>
            <div><b>问题：</b>{{ q.question }}</div>
            <div><b>点评：</b>{{ q.feedback || '—' }}</div>
          </div>
        </template>
        <p v-else class="report-text">—</p>
      </ReportSectionCard>

      <ReportSectionCard title="弱项专项练习">
        <p class="report-text">针对本报告弱项生成一组专项练习题（1~10 题）。</p>
        <div class="practice-row">
          <el-input-number v-model="practiceCount" :min="1" :max="10" />
          <el-button
            type="primary"
            :loading="generatingPractice"
            :disabled="generatingPractice"
            @click="generatePractice"
          >
            生成练习
          </el-button>
        </div>
      </ReportSectionCard>

      <div class="report-actions">
        <el-button type="primary" :loading="exporting" @click="exportPdf">导出 PDF</el-button>
        <el-button @click="router.back()">返回</el-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.report-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.report-header {
  text-align: center;
  margin-bottom: 1.5rem;
}
.report-header__title {
  margin: 0 0 0.5rem;
  font-size: 1.6rem;
}
.report-header__score {
  font-size: 2.2rem;
  font-weight: bold;
  color: var(--el-color-primary);
}
.report-card {
  margin-bottom: 1rem;
}
.report-card__hint {
  margin-top: 1rem;
  text-align: center;
  color: var(--el-text-color-secondary);
}
.report-text {
  margin: 0.25rem 0;
  line-height: 1.8;
}
.report-list {
  margin: 0;
  padding-left: 1.2rem;
}
.report-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.practice-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}
.question-item {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.question-item:last-child {
  border-bottom: none;
}
.question-item__meta {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
  margin-bottom: 0.25rem;
}
</style>
