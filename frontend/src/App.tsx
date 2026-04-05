import { useState } from 'react'
import { HomePage } from './pages/HomePage'
import { JobPage } from './pages/JobPage'

function App() {
  const [jobId, setJobId] = useState<string>()
  return jobId ? <JobPage jobId={jobId} /> : <HomePage onJob={setJobId} />
}

export default App
