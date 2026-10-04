<script setup lang="ts">
import { ref } from 'vue'

import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { ingestQuestionBank } from '@/api/questionBank'
import { extractErrorMessage } from '@/utils/error'
import type { IngestResponse, InterviewDifficulty } from '@/types'

defineOptions({ name: 'QuestionBankIngestView' })

const router = useRouter()

const form = ref({
  company: '',
  position: '',
  difficulty: 'medium' as InterviewDifficulty,
  content: '',
  source_url: '',
})
const submitting = ref(false)
const result = ref<IngestResponse | null>(null)

/** 溯源 URL 仅接受 http(s)（与后端 400 QUESTION_BANK_INVALID_SOURCE 对齐）。 */
function isValidSourceUrl(url: string): boolean {
  try {
    const u = new URL(url)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

async function onSubmit() {
  if (submitting.value) return
  if (!form.value.company.trim() || !form.value.position.trim() || !form.value.content.trim()) {
    ElMessage.warning('请填写公司、岗位与面经内容')
    return
  }
  const source = form.value.source_url.trim()
  if (source && !isValidSourceUrl(source)) {
    ElMessage.warning('来源链接仅支持 http/https')
    return
  }
  submitting.value = true
  try {
    result.value = await ingestQuestionBank({
      company: form.value.company.trim(),
      position: form.value.position.trim(),
      difficulty: form.value.difficulty,
      content: form.value.content.trim(),
      source_url: source || null,
    })
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    submitting.value = false
  }
}

defineExpose({ form, result, submit: onSubmit })
</script>

<template>
  <div class="ingest-page">
    <el-page-header class="header" content="面经入库" @back="router.push('/question-bank/search')" />

    <el-card>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="公司">
          <el-input v-model="form.company" placeholder="例如：字节" maxlength="100" />
        </el-form-item>
        <el-form-item label="岗位">
          <el-input v-model="form.position" placeholder="例如：后端" maxlength="100" />
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="form.difficulty">
            <el-radio value="easy">简单</el-radio>
            <el-radio value="medium">中等</el-radio>
            <el-radio value="hard">困难</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="面经内容">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="8"
            placeholder="粘贴面经原文"
            maxlength="20000"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="来源链接（可选）">
          <el-input v-model="form.source_url" placeholder="https://公开链接" maxlength="500" />
        </el-form-item>

        <el-button
          type="primary"
          class="submit"
          :loading="submitting"
          :disabled="submitting"
          @click="onSubmit"
        >
          提交入库
        </el-button>
      </el-form>

      <div v-if="result" class="result">
        <p class="result__line">
          已提交，作业编号 <strong>#{{ result.item_id }}</strong>
          <el-tag class="result__tag" type="info">待处理</el-tag>
        </p>
        <p class="hint">面经正在后台异步入库（切片 → 去重 → embedding），完成后可用于真题检索出题。</p>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.ingest-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
.submit {
  width: 100%;
}
.result {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.result__line {
  margin: 0 0 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.result__tag {
  margin-left: 0.25rem;
}
.hint {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}
</style>
