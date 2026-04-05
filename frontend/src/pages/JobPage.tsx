import { useEffect, useState } from 'react'
import { fetchJob, fetchPreviewManifest } from '../api'
import { BeatGridPanel } from '../components/BeatGridPanel'
import { DownloadPanel } from '../components/DownloadPanel'
import { JobSummary } from '../components/JobSummary'
import { MelodyPanel } from '../components/MelodyPanel'
import { ScoreViewer } from '../components/ScoreViewer'
import type { JobSummary as JobSummaryType } from '../types/api'

const BASE = 'http://localhost:8000'

export function JobPage({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobSummaryType>()
  const [manifest, setManifest] = useState<any>()

  useEffect(() => {
    fetchJob(jobId).then(setJob)
    fetchPreviewManifest(jobId).then(setManifest)
  }, [jobId])

  const xmlUrl = manifest?.default_score ? `${BASE}/jobs/${jobId}/files/${manifest.default_score}` : undefined

  return (
    <div>
      <h2>Job: {jobId}</h2>
      {job && <JobSummary job={job} />}
      <BeatGridPanel tempo={job?.tempo} />
      <MelodyPanel leadPath={manifest?.lead_melody_path} />
      <DownloadPanel files={manifest?.available_downloads ?? []} />
      <ScoreViewer xmlUrl={xmlUrl} />
    </div>
  )
}
