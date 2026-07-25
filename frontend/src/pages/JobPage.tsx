import { useEffect, useState } from 'react'
import { fetchJob, fetchPreviewManifest, fileUrl, sheetUrl } from '../api'
import { DownloadPanel } from '../components/DownloadPanel'
import { JobSummary } from '../components/JobSummary'
import { ScoreViewer } from '../components/ScoreViewer'
import type { JobSummary as JobSummaryType, PreviewManifest } from '../types/api'

// Transcribing a full song takes minutes, so the job runs in the background
// and this polls until it settles.
const POLL_MS = 2000

export function JobPage({ jobId, onReset }: { jobId: string; onReset: () => void }) {
  const [job, setJob] = useState<JobSummaryType>()
  const [manifest, setManifest] = useState<PreviewManifest>()

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      if (cancelled) return
      try {
        const next = await fetchJob(jobId)
        if (cancelled) return
        setJob(next)
        if (next.status === 'completed') {
          setManifest(await fetchPreviewManifest(jobId).catch(() => undefined))
          return
        }
        if (next.status === 'failed') return
      } catch {
        // Keep polling: the job directory may not be readable for a moment.
      }
      window.setTimeout(poll, POLL_MS)
    }

    poll()
    return () => {
      cancelled = true
    }
  }, [jobId])

  const status = job?.status ?? 'queued'

  return (
    <div className="page">
      <header className="page-head">
        <button className="link" onClick={onReset}>← New song</button>
        <h2>{job?.title ?? 'Transcribing…'}</h2>
      </header>

      {status !== 'completed' && status !== 'failed' && (
        <p className="status">Analysing the stems — this takes a couple of minutes for a full song.</p>
      )}
      {status === 'failed' && <p className="status error">Analysis failed: {job?.error}</p>}

      {job && status === 'completed' && <JobSummary job={job} />}

      {status === 'completed' && (
        <div className="actions">
          <a className="primary" href={sheetUrl(jobId)} target="_blank" rel="noreferrer">
            Open player sheet
          </a>
          {manifest?.song_midi_path && (
            <a href={fileUrl(jobId, manifest.song_midi_path)}>Download MIDI</a>
          )}
          {manifest?.lead_sheet_path && (
            <a href={fileUrl(jobId, manifest.lead_sheet_path)}>Download lead sheet (MusicXML)</a>
          )}
          {manifest?.full_score_path && (
            <a href={fileUrl(jobId, manifest.full_score_path)}>Download full score (MusicXML)</a>
          )}
        </div>
      )}

      {manifest?.default_score && (
        <ScoreViewer xmlUrl={fileUrl(jobId, manifest.default_score)} />
      )}
      {manifest && <DownloadPanel jobId={jobId} files={manifest.available_downloads} />}
    </div>
  )
}
