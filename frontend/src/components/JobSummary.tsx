import type { JobSummary as JobSummaryType } from '../types/api'

export function JobSummary({ job }: { job: JobSummaryType }) {
  return <pre>{JSON.stringify(job, null, 2)}</pre>
}
