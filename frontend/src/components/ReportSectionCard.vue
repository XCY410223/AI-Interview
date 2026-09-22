<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<template>
  <el-card class="report-section" shadow="never">
    <template #header>
      <span class="report-section__title">{{ title }}</span>
    </template>
    <slot />
  </el-card>
</template>

<style scoped>
.report-section {
  margin-bottom: 1rem;
}
.report-section__title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
</style>
