export interface User {
  id: number
  email: string
  avatar_url?: string | null
  is_active: boolean
  created_at?: string | null
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type?: string
}

export interface AuthResponse extends AuthTokens {
  user: User
}

export interface RegisterPayload {
  email: string
  password: string
}

export interface LoginPayload {
  email: string
  password: string
}

export type ResumeStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface Resume {
  id: number
  status: ResumeStatus
  original_ext?: string | null
  size_bytes?: number
  uploaded_at?: string | null
  processed_at?: string | null
  error_message?: string | null
}

export interface PersonalInfo {
  name?: string | null
  email?: string | null
  phone?: string | null
}

export interface EducationItem {
  school: string
  major?: string | null
  degree?: string | null
  start?: string | null
  end?: string | null
}

export interface ProjectItem {
  name: string
  role?: string | null
  description: string
  tech_stack: string[]
}

export interface ParsedResume {
  personal: PersonalInfo
  education: EducationItem[]
  projects: ProjectItem[]
  skills: string[]
  summary: string
}

export interface ResumeDetail extends Resume {
  parsed_content?: ParsedResume | null
}

export interface PageResult<T> {
  total: number
  items: T[]
}

export interface UploadResponse {
  id: number
  status: ResumeStatus
  task_id?: string | null
  uploaded_at: string
}

// ---- 报告（M3）----
export type ReportStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface DimensionScore {
  key: string
  name?: string
  score: number
  comment?: string
}

export interface QuestionScore {
  question_index: number
  round: number
  question: string
  score: number
  feedback?: string
}

export interface ReportDetail {
  report_id: number
  interview_id: number
  status: ReportStatus
  prompt_version?: string | null
  overall_score?: number | null
  grade?: string | null
  summary?: string | null
  dimensions: DimensionScore[]
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  hire_recommendation?: string | null
  question_scores: QuestionScore[]
  answer_quality_avg?: number | null
  pdf_ready: boolean
  error_message?: string | null
  generated_at?: string | null
}

export interface ReportListItem {
  report_id: number
  interview_id: number
  status: ReportStatus
  overall_score?: number | null
  grade?: string | null
  generated_at?: string | null
}

// 雷达维度：与后端 app/schemas/report.py 逐字对齐（前后端唯一真源）
export const DIMENSION_KEYS = [
  'fundamentals',
  'technical_depth',
  'project_experience',
  'logical_thinking',
  'communication',
  'job_fit',
] as const

export const DIMENSION_LABELS: Record<string, string> = {
  fundamentals: '基础知识',
  technical_depth: '技术深度',
  project_experience: '项目经验',
  logical_thinking: '逻辑思维',
  communication: '表达沟通',
  job_fit: '岗位匹配',
}

// ---- 面试（M2）----
// 逐字段对齐后端 app/schemas/interview.py / interview_event.py / interview_message.py（唯一真源）

export type InterviewStyle = 'friendly' | 'stress' | 'deep'
export type InterviewDifficulty = 'easy' | 'medium' | 'hard'

export interface InterviewConfig {
  position: string // 1~100 字，必填
  difficulty: InterviewDifficulty // 默认 medium
  question_count: number // 3~15，默认 8
  style: InterviewStyle // 默认 friendly
  company?: string | null // M4 R5：真题 RAG 检索公司
  jd_text?: string | null // M4 R2：JD 原文（入 config_json）
  capabilities?: JDCapability[] | null // M4 R2：JD 能力项（可选注入出题）
  use_templates?: boolean // M4 R7-a：是否引用题库模板出题
}

export interface StartInterviewPayload {
  resume_id: number
  config: InterviewConfig
}

export interface QuestionItem {
  question_index: number
  round: number
  category: string
  content: string
  reference_points: string[]
  difficulty: string
  source?: string | null // M4 R5：真题溯源回显（{company}·{source_url}）
}

export interface StartInterviewResponse {
  interview_id: number
  total_questions: number
  first_question: QuestionItem
  estimated_minutes: number
}

// ---- SSE 五类事件（对齐 app/schemas/interview_event.py，红线 7 禁止扩充）----
export interface MetaEvent {
  type: 'meta'
  interview_id: number
  question_index: number
  round: number
}

export interface ChunkEvent {
  type: 'chunk'
  content: string
}

export interface ScoreEvent {
  type: 'score'
  score: number
  dimensions: Record<string, number>
  feedback: string
  follow_up_suggestion: boolean
}

export interface NextEvent {
  type: 'next'
  next_question: string | null
  next_question_index: number | null
  round: number | null
}

export type ErrorCode = 'AI_TIMEOUT' | 'AI_OVERLOAD' | 'INTERVIEW_DONE' | 'INVALID_STATE'

export interface ErrorEvent {
  type: 'error'
  code: ErrorCode
  message: string
}

export type InterviewSSEEvent = MetaEvent | ChunkEvent | ScoreEvent | NextEvent | ErrorEvent

// ---- 历史消息（对齐 app/schemas/interview_message.py InterviewMessageOut）----
// 注意：后端 role 为 candidate/interviewer，事件语义由 event_type（answer/score/next）承载，
// 与计划书手稿中的 role 枚举不同——以前端唯一真源（后端 schema）为准。
export interface InterviewMessage {
  id: number
  question_index: number
  round: number
  role: 'candidate' | 'interviewer'
  content: string | null
  event_type: string
  payload_json: Record<string, unknown> | null
  created_at: string | null
}

// ---- 渲染用气泡 ----
export interface ChatBubble {
  id: number
  role: 'interviewer' | 'user'
  content: string
  score?: ScoreEvent | null
}

export type InterviewStatus = 'idle' | 'asking' | 'streaming' | 'finished' | 'error'

// ---- 报告等级档位（对齐后端 app/schemas/report.py 阈值，前端仅展示兜底）----
export const GRADE_LABELS = ['优秀', '良好', '合格', '待提升'] as const
export type GradeLabel = (typeof GRADE_LABELS)[number]

/** 总分 → 等级（阈值与后端一致：优秀≥9 / 良好≥8 / 合格≥7 / 待提升<7）。 */
export function gradeOf(score: number): GradeLabel {
  if (score >= 9) return '优秀'
  if (score >= 8) return '良好'
  if (score >= 7) return '合格'
  return '待提升'
}

// ---- 题库（M4，逐字段对齐 app/schemas/question_bank.py）----
export type CapabilityCategory = 'hard_skill' | 'soft_skill' | 'domain' | 'experience'
export type CapabilityImportance = 'must' | 'nice_to_have'

export interface JDCapability {
  name: string
  category: CapabilityCategory
  keywords: string[]
  importance: CapabilityImportance
}

export interface JDParseResponse {
  position_guess: string
  capabilities: JDCapability[]
  parsed_at: string
}

export interface QuestionBankIngestPayload {
  company: string
  position: string
  difficulty: InterviewDifficulty
  content: string
  source_url?: string | null
}

export interface IngestResponse {
  item_id: number
  status: string
  task_id?: string | null
}

export interface QuestionBankSearchItem {
  id: number
  company: string
  position: string
  difficulty: string
  content: string
  source_url?: string | null
}

export interface QuestionBankSearchResponse {
  items: QuestionBankSearchItem[]
}

export interface QuestionTemplate {
  id: number
  position: string
  difficulty: string
  category: string
  content: string
  reference_points: string[]
  tags: string[]
  usage_count: number
  created_at?: string | null
}

export interface QuestionTemplateCreatePayload {
  position: string
  difficulty: InterviewDifficulty
  category: string
  content: string
  reference_points: string[]
  tags: string[]
}

export type QuestionTemplateUpdatePayload = Partial<QuestionTemplateCreatePayload>

// ---- 历史回放（M4，对齐 app/schemas/interview.py）----
export interface InterviewListItem {
  interview_id: number
  position: string
  difficulty: string
  style: string
  status: string
  question_count: number
  created_at?: string | null
  completed_at?: string | null
}

export interface ReEvaluateResponse {
  question_index: number
  score: number
  dimensions: Record<string, number>
  feedback: string
}

export interface InterviewReplay {
  interview_id: number
  position: string
  difficulty: string
  style: string
  status: string
  question_count: number
  questions: QuestionItem[]
  messages: InterviewMessage[]
  report_summary?: string | null
  created_at?: string | null
  completed_at?: string | null
}

// ---- 弱项专项练习（M4，对齐 app/schemas/practice.py）----
export interface PracticePack {
  practice_id: number
  report_id: number
  count: number
  questions: QuestionItem[]
}

// ---- Waiting List（M4，对齐 app/schemas/waiting_list.py）----
export interface WaitingListSubscribeResponse {
  email: string
  already_subscribed: boolean
}

