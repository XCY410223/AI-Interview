<script setup lang="ts">
import { onMounted, ref } from 'vue'

defineOptions({ name: 'ResumeDetailView' })
import { useRoute } from 'vue-router'

import { getResume } from '@/api/resume'
import ResumeSectionCard from '@/components/ResumeSectionCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import type { ResumeDetail } from '@/types'

const route = useRoute()
const resume = ref<ResumeDetail | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    resume.value = await getResume(Number(route.params.id))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="detail-page">
    <el-page-header class="header" content="简历详情" @back="$router.back()" />
    <el-skeleton v-if="loading" :rows="6" animated />
    <template v-else-if="resume && resume.parsed_content">
      <ResumeSectionCard :parsed="resume.parsed_content" />
    </template>
    <EmptyState v-else description="暂无解析结果" />
  </div>
</template>

<style scoped>
.detail-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
</style>
