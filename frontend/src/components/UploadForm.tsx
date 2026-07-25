import { useState } from 'react'

type Props = { onSubmit: (files: File[], title: string) => Promise<void> }

const ACCEPTED = '.wav,.flac,.aiff,.aif,.ogg,.mp3,.m4a'

export function UploadForm({ onSubmit }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)

  return (
    <div className="upload">
      <label>
        Song title
        <input
          type="text"
          value={title}
          placeholder="Carved From Stone"
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>

      <label>
        Stems
        <input
          multiple
          type="file"
          accept={ACCEPTED}
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
      </label>

      {!!files.length && (
        <ul className="filelist">
          {files.map((f) => <li key={f.name}>{f.name}</li>)}
        </ul>
      )}

      <button
        className="primary"
        disabled={!files.length || busy}
        onClick={async () => {
          setBusy(true)
          try {
            await onSubmit(files, title)
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? 'Starting…' : 'Transcribe'}
      </button>
      <p className="hint">
        Name the files after the instrument they hold — <code>Drums</code>, <code>Bass</code>,
        <code>Guitar</code>, <code>Lead Vocals</code> — so each one is analysed the right way.
      </p>
    </div>
  )
}
