export function BeatGridPanel({ tempo }: { tempo?: { bpm: number; time_signature_guess: string } }) {
  if (!tempo) return null
  return <div><h3>Tempo</h3><p>{tempo.bpm.toFixed(1)} BPM • {tempo.time_signature_guess}</p></div>
}
