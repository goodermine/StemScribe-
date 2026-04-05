import { useEffect, useRef } from 'react'
import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay'

export function ScoreViewer({ xmlUrl }: { xmlUrl?: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!xmlUrl || !ref.current) return
    const osmd = new OpenSheetMusicDisplay(ref.current, { drawingParameters: 'compact' })
    fetch(xmlUrl)
      .then((r) => r.text())
      .then((xml) => osmd.load(xml))
      .then(() => osmd.render())
      .catch(() => undefined)
  }, [xmlUrl])

  return <div><h3>Score Preview</h3><div ref={ref} /></div>
}
