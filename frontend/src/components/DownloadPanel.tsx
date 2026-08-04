import { fileUrl } from '../api'

export function DownloadPanel({ jobId, files }: { jobId: string; files: string[] }) {
  if (!files.length) return null
  return (
    <details className="downloads">
      <summary>All generated files ({files.length})</summary>
      <ul>
        {files.map((f) => (
          <li key={f}>
            <a href={fileUrl(jobId, f)}>{f}</a>
          </li>
        ))}
      </ul>
    </details>
  )
}
