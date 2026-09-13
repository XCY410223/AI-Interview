<script setup lang="ts">
import { onMounted, ref } from 'vue'

defineOptions({ name: 'DashboardView' })
import { useRouter } from 'vue-router'

import { listResumes } from '@/api/resume'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/EmptyState.vue'
import type { Resume } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const resumes = ref<Resume[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const { items } = await listResumes()
    resumes.value = items
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
</script>

<template>
  <div class="dashboard">
    <div class="toolbar">
      <h2>你好，{{ auth.user?.email || '同学' }}</h2>
      <div>
        <el-button type="primary" @click="router.push('/resume/upload')">上传简历</el-button>
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
</style>
