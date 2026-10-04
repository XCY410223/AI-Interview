import * as echarts from 'echarts'
import { getCurrentInstance, onUnmounted, type Ref } from 'vue'

import { DIMENSION_LABELS, type DimensionScore } from '@/types'

/** ECharts 雷达图封装：6 维 indicator、max=10（与后端 SVG 共用同一份维度定义）。 */
export function useRadarChart(el: Ref<HTMLElement | null>) {
  let chart: echarts.ECharts | null = null

  function render(dimensions: DimensionScore[]) {
    if (!el.value) return
    if (!chart) chart = echarts.init(el.value)
    chart.setOption({
      radar: {
        indicator: dimensions.map((d) => ({
          name: d.name || DIMENSION_LABELS[d.key] || d.key,
          max: 10,
        })),
        radius: '65%',
      },
      series: [
        {
          type: 'radar',
          data: [{ value: dimensions.map((d) => d.score), name: '能力评分' }],
        },
      ],
    })
  }

  function resize() {
    chart?.resize()
  }

  function dispose() {
    chart?.dispose()
    chart = null
  }

  // 组件内使用时自动清理；单测中无组件实例时跳过（与 usePolling 约定一致）
  if (getCurrentInstance()) {
    onUnmounted(dispose)
  }

  return { render, resize, dispose }
}
