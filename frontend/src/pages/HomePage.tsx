import { useState } from 'react'
import { createJob } from '../api'
import { UploadForm } from '../components/UploadForm'

export function HomePage({ onJob }: { onJob: (id: string) => void }) {
  const [error, setError] = useState('')
  return (
    <div>
      <h1>suno-stems-to-notes</h1>
      <UploadForm
        onSubmit={async (files) => {
          setError('')
          try {
            const res = await createJob(files)
            onJob(res.job_id)
          } catch (e) {
            setError((e as Error).message)
          }
        }}
      />
      {error && <p>{error}</p>}
    </div>
  )
}
