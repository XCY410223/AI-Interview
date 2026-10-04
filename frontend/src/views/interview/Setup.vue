<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { listResumes } from '@/api/resume'
import { parseJD } from '@/api/questionBank'
import EmptyState from '@/components/EmptyState.vue'
import { useInterviewStore } from '@/stores/interview'
import { extractErrorMessage } from '@/utils/error'
import type {
  CapabilityCategory,
  InterviewConfig,
  InterviewDifficulty,
  InterviewStyle,
  JDParseResponse,
  Resume,
} from '@/types'

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
  use_templates: boolean
}>({
  resume_id: null,
  position: '',
  difficulty: 'medium',
  question_count: 8,
  style: 'friendly',
  use_templates: false,
})

// 仅解析完成的简历可开面（解析未完成/失败不可开面）
const completedResumes = computed(() => resumes.value.filter((r) => r.status === 'completed'))
const hasCompletedResume = computed(() => completedResumes.value.length > 0)

// ---- JD 定制（M4 F8，可选）：贴入 JD → 解析能力项 → 勾选透传出题 ----
const jdText = ref('')
const parsingJd = ref(false)
const jdResult = ref<JDParseResponse | null>(null)
const selectedCapabilities = ref<string[]>([])

const CAPABILITY_GROUP_LABELS: { key: CapabilityCategory; label: string }[] = [
  { key: 'hard_skill', label: '硬技能' },
  { key: 'soft_skill', label: '软素质' },
  { key: 'domain', label: '领域知识' },
  { key: 'experience', label: '项目经验' },
]

const capabilityGroups = computed(() =>
  CAPABILITY_GROUP_LABELS.map(({ key, label }) => ({
    key,
    label,
    items: (jdResult.value?.capabilities ?? []).filter((c) => c.category === key),
  })).filter((g) => g.items.length > 0),
)

async function handleParseJD() {
  if (parsingJd.value) return
  const text = jdText.value.trim()
  if (text.length < 50 || text.length > 20000) {
    ElMessage.warning('JD 原文需在 50~20000 字之间')
    return
  }
  parsingJd.value = true
  try {
    const result = await parseJD(text)
    jdResult.value = result
    // must 能力项默认勾选（D3），nice_to_have 由用户自行勾选
    selectedCapabilities.value = result.capabilities
      .filter((c) => c.importance === 'must')
      .map((c) => c.name)
  } catch (e) {
    jdResult.value = null
    selectedCapabilities.value = []
    ElMessage.error(extractErrorMessage(e))
  } finally {
    parsingJd.value = false
  }
}

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
    // 不贴 JD / 不开模板时，config 与既有行为完全一致（零回退）
    const config: InterviewConfig = {
      position: form.value.position.trim(),
      difficulty: form.value.difficulty,
      question_count: form.value.question_count,
      style: form.value.style,
    }
    const jd = jdText.value.trim()
    if (jd) config.jd_text = jd
    const selected = (jdResult.value?.capabilities ?? []).filter((c) =>
      selectedCapabilities.value.includes(c.name),
    )
    if (selected.length) config.capabilities = selected
    if (form.value.use_templates) config.use_templates = true

    await interviewStore.start({
      resume_id: form.value.resume_id,
      config,
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

defineExpose({
  form,
  jdText,
  jdResult,
  selectedCapabilities,
  parseJD: handleParseJD,
  submit: onSubmit,
})
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

          <el-form-item label="使用题库模板">
            <el-switch v-model="form.use_templates" />
          </el-form-item>

          <el-collapse class="jd-panel">
            <el-collapse-item title="JD 定制（可选）" name="jd">
              <el-form-item label="JD 原文（50~20000 字）">
                <el-input
                  v-model="jdText"
                  type="textarea"
                  :rows="6"
                  placeholder="粘贴岗位描述原文，解析出岗位与能力项"
                  maxlength="20000"
                  show-word-limit
                />
              </el-form-item>
              <el-button
                class="parse-btn"
                :loading="parsingJd"
                :disabled="parsingJd"
                @click="handleParseJD"
              >
                解析 JD
              </el-button>

              <template v-if="jdResult">
                <p class="jd-guess">解析岗位：{{ jdResult.position_guess }}</p>
                <div v-for="group in capabilityGroups" :key="group.key" class="cap-group">
                  <p class="cap-group-label">{{ group.label }}</p>
                  <el-checkbox-group v-model="selectedCapabilities">
                    <el-checkbox v-for="cap in group.items" :key="cap.name" :value="cap.name">
                      {{ cap.name }}
                    </el-checkbox>
                  </el-checkbox-group>
                </div>
              </template>
            </el-collapse-item>
          </el-collapse>

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
.jd-panel {
  margin-bottom: 1rem;
}
.parse-btn {
  margin-bottom: 0.75rem;
}
.jd-guess {
  font-weight: 600;
  margin: 0.5rem 0;
}
.cap-group {
  margin-bottom: 0.75rem;
}
.cap-group-label {
  margin: 0 0 0.25rem;
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}
</style>
