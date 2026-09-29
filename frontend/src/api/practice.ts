import type { PracticePack } from '@/types'

import { client } from './client'

/** 生成专项练习（计入 AI 限流）：报告弱项 → 针对性题目包。 */
export async function createPractice(reportId: number, count = 5): Promise<PracticePack> {
  const { data } = await client.post<PracticePack>('/practice', { report_id: reportId, count })
  return data
}

/** 查询练习包（归属校验）。 */
export async function getPractice(practiceId: number): Promise<PracticePack> {
  const { data } = await client.get<PracticePack>(`/practice/${practiceId}`)
  return data
}
