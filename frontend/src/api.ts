import type { JobCreateResponse, JobSummary, PreviewManifest } from './types/api'

export const BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export async function createJob(files: File[], title: string): Promise<JobCreateResponse> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  form.append('title', title || 'Untitled')
  const r = await fetch(`${BASE}/jobs`, { method: 'POST', body: form })
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? 'Failed to start the job')
  return r.json()
}

export async function fetchJob(jobId: string): Promise<JobSummary> {
  const r = await fetch(`${BASE}/jobs/${jobId}`)
  if (!r.ok) throw new Error('Failed to fetch job')
  return r.json()
}

export async function fetchPreviewManifest(jobId: string): Promise<PreviewManifest> {
  const r = await fetch(`${BASE}/jobs/${jobId}/preview-manifest`)
  if (!r.ok) throw new Error('Preview not ready')
  return r.json()
}

export function fileUrl(jobId: string, path: string): string {
  return `${BASE}/jobs/${jobId}/files/${path}`
}

export function sheetUrl(jobId: string): string {
  return `${BASE}/jobs/${jobId}/sheet`
}
