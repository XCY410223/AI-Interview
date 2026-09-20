import { beforeEach, describe, expect, it, vi } from 'vitest'

const echartsMock = vi.hoisted(() => {
  const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
  return { init: vi.fn(() => chart), chart }
})

vi.mock('echarts', () => echartsMock)

import { ref } from 'vue'

import { useRadarChart } from '@/composables/useRadarChart'
import type { DimensionScore } from '@/types'

const DIMS: DimensionScore[] = [
  { key: 'fundamentals', name: '基础知识', score: 8 },
  { key: 'technical_depth', name: '技术深度', score: 7 },
  { key: 'project_experience', name: '项目经验', score: 6 },
  { key: 'logical_thinking', name: '逻辑思维', score: 9 },
  { key: 'communication', name: '表达沟通', score: 8.5 },
  { key: 'job_fit', name: '岗位匹配', score: 7.5 },
]

beforeEach(() => {
  echartsMock.init.mockClear()
  echartsMock.chart.setOption.mockClear()
})

describe('useRadarChart', () => {
  it('renders 6 indicators with max=10 and scores', () => {
    const el = ref<HTMLElement | null>(document.createElement('div'))
    const { render } = useRadarChart(el)
    render(DIMS)

    expect(echartsMock.init).toHaveBeenCalledTimes(1)
    const option = echartsMock.chart.setOption.mock.calls[0][0]
    expect(option.radar.indicator).toHaveLength(6)
    expect(option.radar.indicator[0]).toEqual({ name: '基础知识', max: 10 })
    expect(option.series[0].data[0].value).toEqual([8, 7, 6, 9, 8.5, 7.5])
  })

  it('does nothing when element is missing', () => {
    const el = ref<HTMLElement | null>(null)
    const { render } = useRadarChart(el)
    render(DIMS)
    expect(echartsMock.init).not.toHaveBeenCalled()
  })
})
