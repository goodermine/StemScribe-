export function MelodyPanel({ leadPath }: { leadPath?: string }) {
  return <div><h3>Lead Melody</h3><p>{leadPath ?? 'Unavailable'}</p></div>
}
