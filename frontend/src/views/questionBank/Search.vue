<script setup lang="ts">
import { ref } from 'vue'

import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { searchQuestionBank } from '@/api/questionBank'
import EmptyState from '@/components/EmptyState.vue'
import { extractErrorMessage } from '@/utils/error'
import type { InterviewDifficulty, QuestionBankSearchItem } from '@/types'

defineOptions({ name: 'QuestionBankSearchView' })

const router = useRouter()

const form = ref({
  company: '',
  position: '',
  difficulty: 'medium' as InterviewDifficulty,
  top_k: 8,
})
const items = ref<QuestionBankSearchItem[]>([])
const searching = ref(false)
const searched = ref(false)

const DIFFICULTY_TEXT: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

async function onSearch() {
  if (searching.value) return
  if (!form.value.company.trim() || !form.value.position.trim()) {
    ElMessage.warning('请填写公司与岗位')
    return
  }
  searching.value = true
  try {
    const { items: list } = await searchQuestionBank({
      company: form.value.company.trim(),
      position: form.value.position.trim(),
      difficulty: form.value.difficulty,
      top_k: form.value.top_k,
    })
    items.value = list
    searched.value = true
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    searching.value = false
  }
}

defineExpose({ form, items, searched, search: onSearch })
</script>

<template>
  <div class="search-page">
    <el-page-header class="header" content="真题检索" @back="router.push('/dashboard')" />

    <el-card class="filter-card">
      <el-form inline @submit.prevent="onSearch">
        <el-form-item label="公司">
          <el-input v-model="form.company" placeholder="例如：字节" maxlength="100" />
        </el-form-item>
        <el-form-item label="岗位">
          <el-input v-model="form.position" placeholder="例如：后端" maxlength="100" />
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="form.difficulty" class="difficulty-select">
            <el-option value="easy" label="简单" />
            <el-option value="medium" label="中等" />
            <el-option value="hard" label="困难" />
          </el-select>
        </el-form-item>
        <el-form-item label="条数">
          <el-input-number v-model="form.top_k" :min="1" :max="32" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="searching" :disabled="searching" @click="onSearch">
            检索
          </el-button>
          <el-button link type="primary" @click="router.push('/question-bank/ingest')">
            面经入库
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="result-card">
      <div v-if="items.length" class="items">
        <div v-for="item in items" :key="item.id" class="item">
          <p class="item__content">{{ item.content }}</p>
          <div class="item__meta">
            <span>{{ item.company }} · {{ item.position }} · {{ DIFFICULTY_TEXT[item.difficulty] ?? item.difficulty }}</span>
            <a
              v-if="item.source_url"
              :href="item.source_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              来源
            </a>
          </div>
        </div>
      </div>

      <EmptyState v-else-if="!searching" :description="searched ? '未检索到相关真题' : '填写公司/岗位后检索真题'" />
    </el-card>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
.filter-card {
  margin-bottom: 1rem;
}
.difficulty-select {
  width: 120px;
}
.items {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.item {
  padding: 0.75rem 1rem;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.item__content {
  margin: 0 0 0.5rem;
  white-space: pre-wrap;
}
.item__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}
</style>
