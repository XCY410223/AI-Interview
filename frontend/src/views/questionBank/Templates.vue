<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  createTemplate,
  deleteTemplate,
  listTemplates,
  updateTemplate,
} from '@/api/questionBank'
import EmptyState from '@/components/EmptyState.vue'
import { extractErrorMessage } from '@/utils/error'
import type { InterviewDifficulty, QuestionTemplate, QuestionTemplateCreatePayload } from '@/types'

defineOptions({ name: 'QuestionBankTemplatesView' })

const router = useRouter()

const rows = ref<QuestionTemplate[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const positionFilter = ref('')

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  position: '',
  difficulty: 'medium' as InterviewDifficulty,
  category: '',
  content: '',
  reference_points: '',
  tags: [] as string[],
})

const DIFFICULTY_TEXT: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

async function load() {
  loading.value = true
  try {
    const { items, total: t } = await listTemplates(
      page.value,
      pageSize,
      positionFilter.value.trim() || undefined,
    )
    rows.value = items
    total.value = t
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  void load()
}

function onPageChange(p: number) {
  page.value = p
  void load()
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    position: '',
    difficulty: 'medium',
    category: '',
    content: '',
    reference_points: '',
    tags: [],
  })
  dialogVisible.value = true
}

function openEdit(row: QuestionTemplate) {
  editingId.value = row.id
  Object.assign(form, {
    position: row.position,
    difficulty: row.difficulty as InterviewDifficulty,
    category: row.category,
    content: row.content,
    reference_points: (row.reference_points ?? []).join('\n'),
    tags: [...(row.tags ?? [])],
  })
  dialogVisible.value = true
}

function buildPayload(): QuestionTemplateCreatePayload {
  return {
    position: form.position.trim(),
    difficulty: form.difficulty,
    category: form.category.trim(),
    content: form.content.trim(),
    reference_points: form.reference_points
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
    tags: [...form.tags],
  }
}

async function submitDialog() {
  if (saving.value) return
  if (!form.position.trim() || !form.category.trim() || !form.content.trim()) {
    ElMessage.warning('请填写岗位、分类与题目内容')
    return
  }
  saving.value = true
  try {
    if (editingId.value == null) {
      await createTemplate(buildPayload())
    } else {
      await updateTemplate(editingId.value, buildPayload())
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    saving.value = false
  }
}

async function remove(row: QuestionTemplate) {
  try {
    await ElMessageBox.confirm(`确认删除模板「${row.content.slice(0, 20)}」？删除后不可恢复。`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  try {
    await deleteTemplate(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  }
}

onMounted(load)

defineExpose({ rows, form, load, openCreate, openEdit, submit: submitDialog, remove })
</script>

<template>
  <div class="templates-page">
    <el-page-header class="header" content="题库模板" @back="router.push('/dashboard')" />

    <el-card>
      <div class="toolbar">
        <el-input
          v-model="positionFilter"
          placeholder="按岗位过滤"
          class="filter-input"
          clearable
          @keyup.enter="onSearch"
        />
        <el-button @click="onSearch">查询</el-button>
        <el-button type="primary" @click="openCreate">新建模板</el-button>
      </div>

      <el-table v-if="rows.length" :data="rows" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="position" label="岗位" width="120" />
        <el-table-column label="难度" width="90">
          <template #default="{ row }">{{ DIFFICULTY_TEXT[row.difficulty] ?? row.difficulty }}</template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="content" label="题目" show-overflow-tooltip />
        <el-table-column prop="usage_count" label="引用" width="80" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <EmptyState v-else-if="!loading" description="还没有题库模板" />

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

    <el-dialog v-model="dialogVisible" :title="editingId == null ? '新建模板' : '编辑模板'" width="560px">
      <el-form label-position="top">
        <el-form-item label="岗位">
          <el-input v-model="form.position" maxlength="100" />
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="form.difficulty">
            <el-radio value="easy">简单</el-radio>
            <el-radio value="medium">中等</el-radio>
            <el-radio value="hard">困难</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" maxlength="50" />
        </el-form-item>
        <el-form-item label="题目内容">
          <el-input v-model="form.content" type="textarea" :rows="4" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="参考答案要点（每行一条）">
          <el-input v-model="form.reference_points" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车创建标签"
            class="tags-select"
          >
            <el-option v-for="tag in form.tags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="saving" @click="submitDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.templates-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.header {
  margin-bottom: 1.5rem;
}
.toolbar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.filter-input {
  max-width: 220px;
}
.tags-select {
  width: 100%;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
