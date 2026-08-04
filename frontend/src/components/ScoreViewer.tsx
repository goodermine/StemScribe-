import { useEffect, useRef, useState } from 'react'
import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay'

export function ScoreViewer({ xmlUrl }: { xmlUrl?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!xmlUrl || !ref.current) return
    let cancelled = false
    const osmd = new OpenSheetMusicDisplay(ref.current, { drawingParameters: 'default' })

    fetch(xmlUrl)
      .then((r) => r.text())
      .then((xml) => (cancelled ? undefined : osmd.load(xml)))
      .then(() => (cancelled ? undefined : osmd.render()))
      .catch(() => !cancelled && setError('Could not render this score in the browser.'))

    return () => {
      cancelled = true
    }
  }, [xmlUrl])

  if (!xmlUrl) return null
  return (
    <div className="score">
      <h3>Score preview</h3>
      {error && <p className="status error">{error}</p>}
      {/* Engraving is drawn in black, so it needs a light backdrop in dark mode. */}
      <div className="score-inner" ref={ref} />
    </div>
  )
}
