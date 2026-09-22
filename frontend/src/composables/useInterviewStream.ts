import { getCurrentInstance, onUnmounted, ref } from 'vue'

import { useInterviewStore } from '@/stores/interview'

/**
 * 面试流式提交封装：防重提交（规范 §6.2）+ 组件卸载自动中止（规范 §8.2）。
 * 状态机本身在 `useInterviewStore` 内；此处只负责组件生命周期的提交胶水。
 */
export function useInterviewStream() {
  const store = useInterviewStore()
  const submitting = ref(false)

  async function submit(content: string): Promise<void> {
    if (submitting.value) return
    submitting.value = true
    try {
      await store.submitAnswer(content)
    } finally {
      submitting.value = false
    }
  }

  function abort() {
    store.abortStream()
  }

  // 组件卸载自动中止流（与 usePolling/useRadarChart 约定一致，单测中跳过）
  if (getCurrentInstance()) {
    onUnmounted(() => store.abortStream())
  }

  return { submitting, submit, abort }
}
