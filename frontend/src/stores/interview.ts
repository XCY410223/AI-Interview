import { defineStore } from 'pinia'

import { getInterviewMessages, startInterview, streamAnswer } from '@/api/interview'
import { extractErrorMessage } from '@/utils/error'
import type {
  ChatBubble,
  ErrorEvent,
  InterviewSSEEvent,
  InterviewStatus,
  InterviewStyle,
  QuestionItem,
  ScoreEvent,
  StartInterviewPayload,
} from '@/types'

/**
 * 面试会话状态机（M2）。
 *
 * 红线 7：`lastScore` 只存 `score` 事件对象，绝不从 chunk 文本抠评分；
 * `submitAnswer` 内的 `error` 事件与网络异常统一回退半条气泡并置 error 态。
 */
export const useInterviewStore = defineStore('interview', {
  state: () => ({
    interviewId: null as number | null,
    totalQuestions: 0,
    questionIndex: 0,
    round: 0,
    currentQuestion: null as QuestionItem | null,
    position: '',
    style: null as InterviewStyle | null,
    messages: [] as ChatBubble[],
    lastScore: null as ScoreEvent | null,
    error: null as { code?: string; message: string } | null,
    status: 'idle' as InterviewStatus,
    _bubbleSeq: 0,
    _abort: null as AbortController | null,
  }),

  actions: {
    _newBubble(role: ChatBubble['role'], content: string, score: ScoreEvent | null = null): ChatBubble {
      this._bubbleSeq += 1
      return { id: this._bubbleSeq, role, content, score }
    },

    _removeBubbles(...bubbles: ChatBubble[]) {
      const ids = new Set(bubbles.map((b) => b.id))
      this.messages = this.messages.filter((m) => !ids.has(m.id))
    },

    /** 开始面试：出题 → 记录 interviewId/首题/进度 → 进入 asking。 */
    async start(payload: StartInterviewPayload) {
      const resp = await startInterview(payload)
      this.interviewId = resp.interview_id
      this.totalQuestions = resp.total_questions
      this.questionIndex = resp.first_question.question_index
      this.round = resp.first_question.round
      this.currentQuestion = resp.first_question
      this.position = payload.config.position
      this.style = payload.config.style
      this.messages = [this._newBubble('interviewer', resp.first_question.content, null)]
      this.lastScore = null
      this.error = null
      this.status = 'asking'
    },

    /**
     * 提交回答并流式消费 SSE（meta → chunk* → score → next）。
     * 防重：streaming/finished 态拒绝再次提交（D4，后端 Redis 锁兜底）。
     */
    async submitAnswer(content: string): Promise<void> {
      if (this.status === 'streaming' || this.status === 'finished') return
      const id = this.interviewId
      if (id == null) return

      const userBubble = this._newBubble('user', content)
      const feedbackBubble = this._newBubble('interviewer', '', null)
      this.messages.push(userBubble, feedbackBubble)
      this.lastScore = null
      this.error = null
      this.status = 'streaming'

      const controller = new AbortController()
      this._abort = controller

      try {
        await streamAnswer(
          id,
          { content, round: this.round },
          (evt) => {
            if (evt.type === 'error') throw evt
            this._handleEvent(evt, feedbackBubble)
          },
          controller.signal,
        )
      } catch (e) {
        if (isErrorEvent(e)) {
          // SSE error 事件（如 AI_TIMEOUT）：答案未落库，回退半条并置 error，允许重提
          this._removeBubbles(userBubble, feedbackBubble)
          this.status = 'error'
          this.error = { code: e.code, message: e.message }
          throw new Error(e.message)
        }
        if (controller.signal.aborted) {
          // 用户主动中止：静默回退，不抛错（§8.2 abort 不残留半条状态）
          this._removeBubbles(userBubble, feedbackBubble)
          this.status = 'asking'
          return
        }
        this._removeBubbles(userBubble, feedbackBubble)
        this.status = 'error'
        this.error = { message: extractErrorMessage(e) }
        throw e
      } finally {
        if (this._abort === controller) this._abort = null
      }

      if (this.status === 'streaming') this.status = 'asking'
    },

    /** 逐事件分发（meta/chunk/score/next），error 由 submitAnswer 统一捕获。 */
    _handleEvent(evt: InterviewSSEEvent, feedbackBubble: ChatBubble) {
      switch (evt.type) {
        case 'meta':
          if (evt.question_index !== this.questionIndex || evt.round !== this.round) {
            console.warn(
              `[interview] meta 双键不一致，以服务端为准：前端(${this.questionIndex},${this.round}) 服务端(${evt.question_index},${evt.round})`,
            )
            this.questionIndex = evt.question_index
            this.round = evt.round
          }
          break
        case 'chunk':
          feedbackBubble.content += evt.content
          break
        case 'score':
          this.lastScore = evt
          feedbackBubble.score = evt
          break
        case 'next':
          if (evt.next_question == null) {
            this.status = 'finished'
          } else {
            this.questionIndex = evt.next_question_index ?? this.questionIndex
            this.round = evt.round ?? this.round
            this.messages.push(this._newBubble('interviewer', evt.next_question, null))
            this.status = 'asking'
          }
          break
        default:
          break
      }
    },

    /** 中止当前流（规范 §8.2）。 */
    abortStream() {
      this._abort?.abort()
      this._abort = null
      if (this.status === 'streaming') this.status = 'asking'
    },

    /** 断线恢复：只信服务端 messages 重建现场（D6，不落 localStorage）。 */
    async resumeFromServer(interviewId: number) {
      const { items } = await getInterviewMessages(interviewId)
      this.interviewId = interviewId
      this.messages = []
      this.lastScore = null
      this.error = null
      this.currentQuestion = null

      let questionIndex = 0
      let round = 0
      let finished = false
      let maxQuestionIndex = 0

      for (const m of items) {
        maxQuestionIndex = Math.max(maxQuestionIndex, m.question_index)
        if (m.role === 'candidate' && m.event_type === 'answer') {
          this.messages.push(this._newBubble('user', m.content ?? '', null))
          questionIndex = m.question_index
          round = m.round
        } else if (m.role === 'interviewer' && m.event_type === 'score') {
          const score = buildScoreEvent(m.payload_json, m.content ?? '')
          this.messages.push(this._newBubble('interviewer', m.content ?? '', score))
          if (score) this.lastScore = score
        } else if (m.role === 'interviewer' && m.event_type === 'next') {
          const payload = m.payload_json ?? {}
          if (payload.done) {
            finished = true
          } else if (m.content) {
            this.messages.push(this._newBubble('interviewer', m.content, null))
          }
          if (typeof payload.next_question_index === 'number') {
            questionIndex = payload.next_question_index
            round = 0
          } else if (payload.need_follow_up) {
            questionIndex = m.question_index
            round = m.round
          }
        }
      }

      this.questionIndex = questionIndex
      this.round = round
      this.totalQuestions = Math.max(this.totalQuestions, maxQuestionIndex + 1)
      this.status = finished ? 'finished' : 'asking'
    },

    reset() {
      this._abort?.abort()
      this.interviewId = null
      this.totalQuestions = 0
      this.questionIndex = 0
      this.round = 0
      this.currentQuestion = null
      this.position = ''
      this.style = null
      this.messages = []
      this.lastScore = null
      this.error = null
      this.status = 'idle'
      this._bubbleSeq = 0
      this._abort = null
    },
  },
})

function isErrorEvent(value: unknown): value is ErrorEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as { type?: unknown }).type === 'error'
  )
}

/** 从 score 消息的 payload_json 重建 ScoreEvent（断线恢复用）。 */
export function buildScoreEvent(
  payload: Record<string, unknown> | null,
  feedback: string,
): ScoreEvent | null {
  if (!payload || typeof payload.score !== 'number') return null
  const dimensions: Record<string, number> = {}
  if (payload.dimensions && typeof payload.dimensions === 'object') {
    for (const [k, v] of Object.entries(payload.dimensions as Record<string, unknown>)) {
      if (typeof v === 'number') dimensions[k] = v
    }
  }
  return {
    type: 'score',
    score: payload.score,
    dimensions,
    feedback,
    follow_up_suggestion: false,
  }
}
