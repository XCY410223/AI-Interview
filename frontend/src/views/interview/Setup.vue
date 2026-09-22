<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { listResumes } from '@/api/resume'
import EmptyState from '@/components/EmptyState.vue'
import { useInterviewStore } from '@/stores/interview'
import { extractErrorMessage } from '@/utils/error'
import type { InterviewDifficulty, InterviewStyle, Resume } from '@/types'

defineOptions({ name: 'InterviewSetupView' })

const router = useRouter()
const interviewStore = useInterviewStore()

const resumes = ref<Resume[]>([])
const loadingResumes = ref(false)
const submitting = ref(false)

const form = ref<{
  resume_id: number | null
  position: string
  difficulty: InterviewDifficulty
  question_count: number
  style: InterviewStyle
}>({
  resume_id: null,
  position: '',
  difficulty: 'medium',
  question_count: 8,
  style: 'friendly',
})

// 仅解析完成的简历可开面（解析未完成/失败不可开面）
const completedResumes = computed(() => resumes.value.filter((r) => r.status === 'completed'))
const hasCompletedResume = computed(() => completedResumes.value.length > 0)

onMounted(async () => {
  loadingResumes.value = true
  try {
    const { items } = await listResumes()
    resumes.value = items
    if (completedResumes.value.length) form.value.resume_id = completedResumes.value[0].id
  } finally {
    loadingResumes.value = false
  }
})

async function onSubmit() {
  if (submitting.value) return
  if (form.value.resume_id == null) {
    ElMessage.warning('请选择一份已解析完成的简历')
    return
  }
  if (!form.value.position.trim()) {
    ElMessage.warning('请输入目标岗位')
    return
  }
  submitting.value = true
  try {
    await interviewStore.start({
      resume_id: form.value.resume_id,
      config: {
        position: form.value.position.trim(),
        difficulty: form.value.difficulty,
        question_count: form.value.question_count,
        style: form.value.style,
      },
    })
    if (interviewStore.interviewId != null) {
      router.push(`/interview/${interviewStore.interviewId}`)
    }
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    submitting.value = false
  }
}

defineExpose({ form, submit: onSubmit })
</script>

<template>
  <div class="setup-page">
    <el-card class="setup-card">
      <h2>开始模拟面试</h2>

      <template v-if="hasCompletedResume">
        <el-form label-position="top" @submit.prevent="onSubmit">
          <el-form-item label="选择简历（仅解析完成的可用）">
            <el-select v-model="form.resume_id" placeholder="请选择简历" class="full">
              <el-option
                v-for="resume in completedResumes"
                :key="resume.id"
                :label="`简历 #${resume.id}`"
                :value="resume.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="目标岗位">
            <el-input
              v-model="form.position"
              placeholder="例如：后端工程师"
              maxlength="100"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="难度">
            <el-radio-group v-model="form.difficulty">
              <el-radio value="easy">简单</el-radio>
              <el-radio value="medium">中等</el-radio>
              <el-radio value="hard">困难</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="题目数量（3~15 题）">
            <el-input-number v-model="form.question_count" :min="3" :max="15" />
          </el-form-item>

          <el-form-item label="面试官风格">
            <el-radio-group v-model="form.style">
              <el-radio value="friendly">友好</el-radio>
              <el-radio value="stress">压力</el-radio>
              <el-radio value="deep">深挖</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-button
            type="primary"
            class="submit"
            :loading="submitting"
            :disabled="submitting || form.resume_id == null"
            @click="onSubmit"
          >
            开始面试
          </el-button>
        </el-form>
      </template>

      <EmptyState v-else-if="!loadingResumes">
        <p class="empty-hint">还没有已解析完成的简历，请先上传并等待解析完成</p>
        <el-button type="primary" @click="router.push('/resume/upload')">去上传简历</el-button>
      </EmptyState>

      <el-skeleton v-else :rows="4" animated />
    </el-card>
  </div>
</template>

<style scoped>
.setup-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.setup-card h2 {
  margin: 0 0 1.5rem;
}
.full {
  width: 100%;
}
.submit {
  width: 100%;
}
.empty-hint {
  margin: 0 0 0.75rem;
  color: var(--el-text-color-secondary);
}
</style>
