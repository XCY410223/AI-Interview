<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { useRouter } from 'vue-router'

import { listReports } from '@/api/report'
import { usePolling } from '@/composables/usePolling'
import EmptyState from '@/components/EmptyState.vue'
import { gradeOf, type ReportListItem, type ReportStatus } from '@/types'

defineOptions({ name: 'ReportListView' })

const router = useRouter()

const rows = ref<ReportListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const STATUS_TEXT: Record<ReportStatus, string> = {
  pending: '排队中',
  processing: '生成中',
  completed: '已完成',
  failed: '失败',
}

const GRADE_TAG: Record<string, 'success' | 'primary' | 'warning' | 'danger'> = {
  优秀: 'success',
  良好: 'primary',
  合格: 'warning',
  待提升: 'danger',
}

async function load() {
  loading.value = true
  try {
    const { items, total: t } = await listReports(page.value, pageSize)
    rows.value = items
    total.value = t
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  void load()
}

// 进行中轮询：存在 pending/processing 行时启动，全部终态后停止
const { start, stop } = usePolling(load, { interval: 1500, backoff: false })
watch(rows, (items) => {
  const hasActive = items.some((r) => r.status === 'pending' || r.status === 'processing')
  if (hasActive) start()
  else stop()
})

onMounted(() => load())

function gradeText(row: ReportListItem): string {
  if (row.grade) return row.grade
  if (row.overall_score != null) return gradeOf(row.overall_score)
  return '—'
}
</script>

<template>
  <div class="list-page">
    <el-page-header class="header" content="我的报告" @back="router.push('/dashboard')" />

    <el-card>
      <el-table
        v-if="rows.length"
        :data="rows"
        v-loading="loading"
        @row-click="(row: ReportListItem) => router.push(`/report/${row.report_id}`)"
      >
        <el-table-column prop="report_id" label="报告 ID" width="90" />
        <el-table-column prop="interview_id" label="面试 ID" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">
              {{ STATUS_TEXT[row.status as ReportStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总分" width="90">
          <template #default="{ row }">
            {{ row.overall_score != null ? row.overall_score.toFixed(1) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="等级" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.grade || row.overall_score != null" :type="GRADE_TAG[gradeText(row)] || 'info'" effect="plain">
              {{ gradeText(row) }}
            </el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" />
      </el-table>

      <EmptyState v-else-if="!loading" description="还没有报告，完成一场面试后自动生成" />

      <div v-if="total > pageSize" class="pagination">
        <el-pagination
          layout="prev, pager, next, total"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.list-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
