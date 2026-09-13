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
