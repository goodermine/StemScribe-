export function DownloadPanel({ files }: { files: string[] }) {
  return <div><h3>Downloads</h3><ul>{files.map((f) => <li key={f}>{f}</li>)}</ul></div>
}
