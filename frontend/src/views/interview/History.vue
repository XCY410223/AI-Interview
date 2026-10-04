<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { useRouter } from 'vue-router'

import { listInterviews } from '@/api/interview'
import EmptyState from '@/components/EmptyState.vue'
import type { InterviewListItem } from '@/types'

defineOptions({ name: 'InterviewHistoryView' })

const router = useRouter()

const rows = ref<InterviewListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

const DIFFICULTY_TEXT: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
const STATUS_TEXT: Record<string, string> = { in_progress: '进行中', completed: '已完成' }

async function load() {
  loading.value = true
  try {
    const { items, total: t } = await listInterviews(page.value, pageSize)
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

onMounted(load)
</script>

<template>
  <div class="history-page">
    <el-page-header class="header" content="历史面试" @back="router.push('/dashboard')" />

    <el-card>
      <el-table v-if="rows.length" :data="rows" v-loading="loading">
        <el-table-column prop="interview_id" label="面试 ID" width="90" />
        <el-table-column prop="position" label="岗位" />
        <el-table-column label="难度" width="90">
          <template #default="{ row }">{{ DIFFICULTY_TEXT[row.difficulty] ?? row.difficulty }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'info'">
              {{ STATUS_TEXT[row.status] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="开始时间" width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/interview/${row.interview_id}/replay`)">
              回放
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <EmptyState v-else-if="!loading" description="还没有面试记录" />

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
.history-page {
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
