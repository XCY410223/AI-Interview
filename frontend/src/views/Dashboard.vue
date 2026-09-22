<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listReports } from '@/api/report'
import { listResumes } from '@/api/resume'
import EmptyState from '@/components/EmptyState.vue'
import { useAuthStore } from '@/stores/auth'
import { gradeOf, type ReportListItem, type ReportStatus, type Resume } from '@/types'

defineOptions({ name: 'DashboardView' })

const router = useRouter()
const auth = useAuthStore()
const resumes = ref<Resume[]>([])
const reports = ref<ReportListItem[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    // 简历与报告独立加载：任一失败不影响另一块（如 reports 表未迁移时报告 500，简历仍应显示）
    const [resumePage, reportPage] = await Promise.allSettled([listResumes(), listReports(1, 20)])
    if (resumePage.status === 'fulfilled') resumes.value = resumePage.value.items
    if (reportPage.status === 'fulfilled') reports.value = reportPage.value.items
  } finally {
    loading.value = false
  }
})

const STATUS_TEXT: Record<string, string> = {
  pending: '排队中',
  processing: '解析中',
  completed: '完成',
  failed: '失败',
}

function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status
}

const REPORT_STATUS_TEXT: Record<ReportStatus, string> = {
  pending: '排队中',
  processing: '生成中',
  completed: '已完成',
  failed: '失败',
}

function gradeText(row: ReportListItem): string {
  if (row.grade) return row.grade
  if (row.overall_score != null) return gradeOf(row.overall_score)
  return '—'
}
</script>

<template>
  <div class="dashboard">
    <div class="toolbar">
      <h2>你好，{{ auth.user?.email || '同学' }}</h2>
      <div>
        <el-button type="primary" @click="router.push('/interview/setup')">开始面试</el-button>
        <el-button type="primary" plain @click="router.push('/resume/upload')">上传简历</el-button>
        <el-button @click="auth.logout().then(() => router.push('/login'))">退出登录</el-button>
      </div>
    </div>

    <el-card>
      <h3>我的简历</h3>
      <el-table
        v-if="resumes.length"
        :data="resumes"
        v-loading="loading"
        @row-click="(row: Resume) => router.push(`/resume/${row.id}`)"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="original_ext" label="类型" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">{{ statusText(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="uploaded_at" label="上传时间" />
      </el-table>
      <EmptyState v-else description="还没有简历，点击上方上传" />
    </el-card>

    <el-card class="report-card">
      <div class="report-card__head">
        <h3>我的报告</h3>
        <el-button v-if="reports.length" link type="primary" @click="router.push('/report')">查看全部</el-button>
      </div>
      <el-table
        v-if="reports.length"
        :data="reports"
        @row-click="(row: ReportListItem) => router.push(`/report/${row.report_id}`)"
      >
        <el-table-column prop="report_id" label="报告 ID" width="90" />
        <el-table-column prop="interview_id" label="面试 ID" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            {{ REPORT_STATUS_TEXT[row.status as ReportStatus] ?? row.status }}
          </template>
        </el-table-column>
        <el-table-column label="总分" width="90">
          <template #default="{ row }">
            {{ row.overall_score != null ? row.overall_score.toFixed(1) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="等级" width="100">
          <template #default="{ row }">{{ gradeText(row) }}</template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" />
      </el-table>
      <EmptyState v-else description="还没有报告，完成一场面试后自动生成" />
    </el-card>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.report-card {
  margin-top: 1.5rem;
}
.report-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.report-card__head h3 {
  margin: 0;
}
</style>
