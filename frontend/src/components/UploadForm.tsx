import { useState } from 'react'

type Props = { onSubmit: (files: File[]) => Promise<void> }

export function UploadForm({ onSubmit }: Props) {
  const [files, setFiles] = useState<File[]>([])
  return (
    <div>
      <input multiple type="file" accept=".wav" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
      <button onClick={() => onSubmit(files)} disabled={!files.length}>Process Stems</button>
    </div>
  )
}
