export type JobCreateResponse = { job_id: string; status: string }
export type JobSummary = {
  job_id: string
  status: string
  warnings: string[]
  tempo?: { bpm: number; time_signature_guess: string; beat_times: number[]; bar_starts: number[] }
}
