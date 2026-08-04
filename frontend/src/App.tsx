import { useState } from 'react'
import { HomePage } from './pages/HomePage'
import { JobPage } from './pages/JobPage'
import './app.css'

function App() {
  const [jobId, setJobId] = useState<string>()
  return jobId ? (
    <JobPage jobId={jobId} onReset={() => setJobId(undefined)} />
  ) : (
    <HomePage onJob={setJobId} />
  )
}

export default App
