export const MAX_RESUME_SIZE = 10 * 1024 * 1024

/** 客户端上传预检（§6.2）：扩展名 + 大小。合法返回 null，否则返回错误提示。 */
export function validateResumeFile(file: File): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext !== 'pdf' && ext !== 'docx') return '仅支持 PDF / DOCX 格式'
  if (file.size > MAX_RESUME_SIZE) return '文件大小不能超过 10MB'
  return null
}
