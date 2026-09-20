<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'

import { useRadarChart } from '@/composables/useRadarChart'
import type { DimensionScore } from '@/types'

const props = defineProps<{ dimensions: DimensionScore[] }>()

const el = ref<HTMLElement | null>(null)
const { render, resize } = useRadarChart(el)

function onResize() {
  resize()
}

onMounted(() => {
  render(props.dimensions)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})

watch(
  () => props.dimensions,
  (dims) => render(dims),
)
</script>

<template>
  <div ref="el" class="radar-chart" />
</template>

<style scoped>
.radar-chart {
  width: 100%;
  height: 320px;
}
</style>
