<script setup lang="ts">
import { ref, watch } from 'vue'

defineOptions({ name: 'ResumeUploadView' })
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'

import { getResume } from '@/api/resume'
import { usePolling } from '@/composables/usePolling'
import { useUpload } from '@/composables/useUpload'
import { useResumeStore } from '@/stores/resume'
import { validateResumeFile } from '@/utils/validate'
import ResumeSectionCard from '@/components/ResumeSectionCard.vue'
import type { ParsedResume, ResumeDetail, ResumeStatus } from '@/types'

const resumeStore = useResumeStore()
const { uploading, error, upload } = useUpload()

const card = ref<{ filename: string; status: ResumeStatus; parsed: ParsedResume | null } | null>(null)
const progress = ref(0)
const resumeId = ref<number | null>(null)

const { data, start, stop } = usePolling<ResumeDetail>(
  () => getResume(resumeId.value as number),
  { interval: 1500, backoff: true },
)

const STATUS_TEXT: Record<ResumeStatus, string> = {
  pending: '排队中',
  processing: '解析中',
  completed: '完成',
  failed: '失败',
}

function statusProgress(status: ResumeStatus): number {
  return { pending: 10, processing: 50, completed: 100, failed: 100 }[status]
}

function onFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (!file) return
  const invalid = validateResumeFile(file)
  if (invalid) {
    ElMessage.error(invalid)
    return
  }

  // 乐观更新：立即显示进度卡片（禁止等响应才出现 UI，§6.2）
  card.value = { filename: file.name, status: 'pending', parsed: null }
  progress.value = 10
  void doUpload(file)
}

async function doUpload(file: File) {
  try {
    const resp = await upload(file)
    resumeStore.setUpload(resp)
    resumeId.value = resp.id
    start()
  } catch {
    if (card.value) card.value.status = 'failed'
    ElMessage.error(error.value || '上传失败')
  }
}

watch(data, (resume) => {
  if (!resume || !card.value) return
  card.value.status = resume.status
  progress.value = statusProgress(resume.status)
  if (resume.status === 'completed') {
    card.value.parsed = resume.parsed_content ?? null
    stop()
  } else if (resume.status === 'failed') {
    stop()
  }
})
</script>

<template>
  <div class="upload-page">
    <el-upload drag :auto-upload="false" :show-file-list="false" :on-change="onFileChange" accept=".pdf,.docx">
      <div class="upload-drop">
        <p>将简历拖拽到此处，或 <em>点击选择文件</em></p>
        <p class="hint">支持 PDF / DOCX，最大 10MB</p>
      </div>
    </el-upload>

    <el-card v-if="card" class="progress-card">
      <div class="progress-card__header">
        <span class="filename">{{ card.filename }}</span>
        <el-tag :type="card.status === 'failed' ? 'danger' : card.status === 'completed' ? 'success' : 'info'">
          {{ STATUS_TEXT[card.status] }}
        </el-tag>
      </div>
      <el-progress
        :percentage="progress"
        :status="card.status === 'failed' ? 'exception' : card.status === 'completed' ? 'success' : undefined"
      />
      <el-alert
        v-if="card.status === 'failed'"
        type="error"
        :closable="false"
        show-icon
        :title="error || '解析失败'"
      />
      <ResumeSectionCard v-if="card.status === 'completed' && card.parsed" :parsed="card.parsed" />
    </el-card>

    <div v-if="uploading" class="uploading">上传中…</div>
  </div>
</template>

<style scoped>
.upload-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.upload-drop {
  padding: 2rem 0;
}
.upload-drop em {
  color: var(--el-color-primary);
  font-style: normal;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}
.progress-card {
  margin-top: 1.5rem;
}
.progress-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.uploading {
  margin-top: 1rem;
  text-align: center;
  color: var(--el-text-color-secondary);
}
</style>
