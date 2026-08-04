import { useState } from 'react'
import { createJob } from '../api'
import { UploadForm } from '../components/UploadForm'

export function HomePage({ onJob }: { onJob: (id: string) => void }) {
  const [error, setError] = useState('')

  return (
    <div className="page">
      <h1>StemScribe</h1>
      <p className="lede">
        Turn a song's stems into a sheet someone can play from: key, tempo, structure,
        the chord chart and the groove.
      </p>
      <UploadForm
        onSubmit={async (files, title) => {
          setError('')
          try {
            const res = await createJob(files, title)
            onJob(res.job_id)
          } catch (e) {
            setError((e as Error).message)
          }
        }}
      />
      {error && <p className="status error">{error}</p>}
    </div>
  )
}
