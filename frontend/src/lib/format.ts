export type Tone = 'good' | 'mixed' | 'bad' | 'none'

// Metacritic colours: green / yellow / red
export function metascoreTone(score: number | null): Tone {
  if (score === null) return 'none'
  if (score >= 75) return 'good'
  if (score >= 50) return 'mixed'
  return 'bad'
}

export function userscoreTone(score: number | null): Tone {
  if (score === null) return 'none'
  if (score >= 7.5) return 'good'
  if (score >= 5) return 'mixed'
  return 'bad'
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function formatDuration(from: string, to: string | null): string {
  const end = to ? new Date(to).getTime() : Date.now()
  const seconds = Math.max(0, Math.round((end - new Date(from).getTime()) / 1000))
  return seconds < 60 ? `${seconds} с` : `${Math.floor(seconds / 60)} мин ${seconds % 60} с`
}
