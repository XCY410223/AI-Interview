<script setup lang="ts">
import type { ParsedResume } from '@/types'

import EmptyState from './EmptyState.vue'

const props = defineProps<{ parsed: ParsedResume }>()

const personal = () => props.parsed.personal ?? {}
</script>

<template>
  <el-collapse class="resume-card">
    <el-collapse-item title="基本信息" name="personal">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="姓名">{{ personal().name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ personal().email || '—' }}</el-descriptions-item>
        <el-descriptions-item label="电话">{{ personal().phone || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-collapse-item>

    <el-collapse-item title="教育经历" name="education">
      <template v-if="parsed.education.length">
        <div v-for="(edu, i) in parsed.education" :key="i" class="section-item">
          <strong>{{ edu.school }}</strong>
          <div class="section-item__meta">
            <span v-if="edu.major">{{ edu.major }}</span>
            <span v-if="edu.degree">{{ edu.degree }}</span>
            <span v-if="edu.start || edu.end">{{ edu.start || '' }} - {{ edu.end || '' }}</span>
          </div>
        </div>
      </template>
      <EmptyState v-else description="暂无教育经历" />
    </el-collapse-item>

    <el-collapse-item title="项目经验" name="projects">
      <template v-if="parsed.projects.length">
        <div v-for="(proj, i) in parsed.projects" :key="i" class="section-item">
          <strong>{{ proj.name }}</strong>
          <p>{{ proj.description }}</p>
          <el-tag v-for="tech in proj.tech_stack" :key="tech" size="small" class="tech-tag">{{ tech }}</el-tag>
        </div>
      </template>
      <EmptyState v-else description="暂无项目经验" />
    </el-collapse-item>

    <el-collapse-item title="技能" name="skills">
      <template v-if="parsed.skills.length">
        <el-tag v-for="skill in parsed.skills" :key="skill" class="tech-tag">{{ skill }}</el-tag>
      </template>
      <EmptyState v-else description="暂无技能" />
    </el-collapse-item>
  </el-collapse>
</template>

<style scoped>
.section-item {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.section-item__meta {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}
.tech-tag {
  margin-right: 0.5rem;
  margin-bottom: 0.25rem;
}
</style>
