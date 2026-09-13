import { getCurrentInstance, onUnmounted, ref, type Ref } from 'vue'

export interface PollingOptions {
  interval?: number
  backoff?: boolean
  maxInterval?: number
}

export interface PollingResult<T> {
  data: Ref<T | null>
  error: Ref<unknown>
  start: () => void
  stop: () => void
}

/** 通用轮询 hook：固定间隔 + 可选指数退避（M1 计划 §6.2）。 */
export function usePolling<T>(fetcher: () => Promise<T>, options: PollingOptions = {}): PollingResult<T> {
  const interval = options.interval ?? 1500
  const backoff = options.backoff ?? true
  const maxInterval = options.maxInterval ?? 30000

  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref<unknown>(null)
  let timer: ReturnType<typeof setTimeout> | null = null
  let currentInterval = interval
  let running = false

  async function poll() {
    if (!running) return
    try {
      data.value = await fetcher()
      error.value = null
    } catch (e) {
      error.value = e
    }
    currentInterval = backoff ? Math.min(currentInterval * 2, maxInterval) : interval
    timer = setTimeout(poll, currentInterval)
  }

  function start() {
    if (running) return
    running = true
    currentInterval = interval
    void poll()
  }

  function stop() {
    running = false
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  // 组件内使用则自动清理；单测中无组件实例时跳过（避免 onUnmounted 告警）
  if (getCurrentInstance()) {
    onUnmounted(stop)
  }

  return { data, error, start, stop }
}
