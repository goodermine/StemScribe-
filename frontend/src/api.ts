import type { JobCreateResponse, JobSummary } from './types/api'

const BASE = 'http://localhost:8000'

export async function createJob(files: File[]): Promise<JobCreateResponse> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const r = await fetch(`${BASE}/jobs`, { method: 'POST', body: form })
  if (!r.ok) throw new Error('Failed to create job')
  return r.json()
}

export async function fetchJob(jobId: string): Promise<JobSummary> {
  const r = await fetch(`${BASE}/jobs/${jobId}`)
  if (!r.ok) throw new Error('Failed to fetch job')
  return r.json()
}

export async function fetchPreviewManifest(jobId: string): Promise<any> {
  const r = await fetch(`${BASE}/jobs/${jobId}/preview-manifest`)
  if (!r.ok) throw new Error('Failed to fetch preview')
  return r.json()
}
