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

