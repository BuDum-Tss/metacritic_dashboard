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

export type ReviewTone = 'positive' | 'mixed' | 'negative'

// the same split Metacritic uses for the colours of a score
export function reviewTone(kind: 'critics' | 'users', score: number): ReviewTone {
  const tone = kind === 'critics' ? metascoreTone(score) : userscoreTone(score)
  return tone === 'good' ? 'positive' : tone === 'mixed' ? 'mixed' : 'negative'
}

export function plural(n: number, forms: [string, string, string]): string {
  const mod100 = n % 100
  const mod10 = n % 10
  if (mod100 >= 11 && mod100 <= 14) return forms[2]
  if (mod10 === 1) return forms[0]
  if (mod10 >= 2 && mod10 <= 4) return forms[1]
  return forms[2]
}

const COUNT_FORMS: Record<'critics' | 'users', [string, string, string]> = {
  critics: ['отзыв критика', 'отзыва критиков', 'отзывов критиков'],
  users: ['оценка игроков', 'оценки игроков', 'оценок игроков'],
}

export function countLabel(kind: 'critics' | 'users', count: number | null): string {
  return count === null ? 'нет данных' : `${count} ${plural(count, COUNT_FORMS[kind])}`
}

export function formatDate(iso: string): string {
  // a plain date (2026-11-05): read it as a calendar day, whatever the time zone
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export function compact(n: number): string {
  return new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
}

export function decimal(n: number | null, digits = 1): string {
  return n === null ? '—' : n.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
