<script setup lang="ts">
defineProps<{ description?: string }>()
</script>

<template>
  <div class="empty-state">
    <slot>
      <p class="empty-state__text">{{ description || '暂无数据' }}</p>
    </slot>
  </div>
</template>

<style scoped>
.empty-state {
  padding: 2rem 0;
  text-align: center;
  color: var(--el-text-color-secondary);
}
.empty-state__text {
  margin: 0;
}
</style>
