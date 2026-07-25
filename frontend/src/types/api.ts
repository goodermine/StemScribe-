export type JobCreateResponse = { job_id: string; status: string }

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'unknown'

export type PartSummary = {
  key: string
  name: string
  lane: string
  note_count: number
  range: string
  confidence: number
}

export type JobSummary = {
  job_id: string
  status: JobStatus
  title?: string
  error?: string
  duration_sec?: number
  warnings?: string[]
  parts?: PartSummary[]
  key?: { key_name: string; confidence: number }
  tempo?: { bpm: number; time_signature: string; bar_count: number; confidence: number }
  sections?: { name: string; start_bar: number; end_bar: number }[]
  chord_count?: number
  confidence_summary?: Record<string, number>
}

export type PreviewManifest = {
  title: string
  available_scores: string[]
  default_score: string
  lead_sheet_path: string
  full_score_path: string
  available_downloads: string[]
  song_midi_path: string
  player_sheet_html: string
  summary: Record<string, string | number>
}
