import type { WaitingListSubscribeResponse } from '@/types'

import { client, publicClient } from './client'

/** 公开订阅（匿名，D5）：用 publicClient 避免附加 Authorization。 */
export async function subscribeWaitingList(email: string): Promise<WaitingListSubscribeResponse> {
  const { data } = await publicClient.post<WaitingListSubscribeResponse>('/waiting-list', { email })
  return data
}

/** 管理侧 CSV 导出（登录态）：流式 blob 下载，不落本地磁盘（红线 8）。 */
export async function exportWaitingListCsv(): Promise<Blob> {
  const { data } = await client.get<Blob>('/waiting-list/export', { responseType: 'blob' })
  return data
}
