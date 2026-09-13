import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import ResumeSectionCard from '@/components/ResumeSectionCard.vue'
import type { ParsedResume } from '@/types'

const parsed: ParsedResume = {
  personal: { name: '张三', email: 'a@b.com', phone: null },
  education: [{ school: '清华大学', major: '计算机' }],
  projects: [{ name: '项目A', role: '后端', description: '描述', tech_stack: ['Python'] }],
  skills: ['Python'],
  summary: '概述',
}

describe('ResumeSectionCard', () => {
  it('renders four collapsible sections', () => {
    const wrapper = mount(ResumeSectionCard, {
      props: { parsed },
      global: { plugins: [ElementPlus] },
    })
    const text = wrapper.text()
    expect(text).toContain('基本信息')
    expect(text).toContain('教育经历')
    expect(text).toContain('项目经验')
    expect(text).toContain('技能')
    expect(text).toContain('张三')
  })
})
