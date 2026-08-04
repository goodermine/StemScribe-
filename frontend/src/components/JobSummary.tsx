import type { JobSummary as JobSummaryType } from '../types/api'

export function JobSummary({ job }: { job: JobSummaryType }) {
  const minutes = Math.floor((job.duration_sec ?? 0) / 60)
  const seconds = Math.round((job.duration_sec ?? 0) % 60)

  return (
    <div className="summary">
      <div className="pills">
        {job.key && <span className="pill">{job.key.key_name}</span>}
        {job.tempo && <span className="pill">{Math.round(job.tempo.bpm)} BPM</span>}
        {job.tempo && <span className="pill">{job.tempo.time_signature}</span>}
        {job.tempo && <span className="pill">{job.tempo.bar_count} bars</span>}
        <span className="pill">{minutes}:{String(seconds).padStart(2, '0')}</span>
        {job.chord_count !== undefined && <span className="pill">{job.chord_count} chord changes</span>}
      </div>

      {!!job.sections?.length && (
        <p className="sections">{job.sections.map((s) => s.name).join(' · ')}</p>
      )}

      {!!job.parts?.length && (
        <table className="parts">
          <thead>
            <tr><th>Part</th><th>Events</th><th>Range</th><th>Confidence</th></tr>
          </thead>
          <tbody>
            {job.parts.map((p) => (
              <tr key={p.key}>
                <td>{p.name}</td>
                <td>{p.note_count}</td>
                <td>{p.range}</td>
                <td>{p.confidence.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!!job.warnings?.length && (
        <ul className="warnings">
          {job.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
    </div>
  )
}
