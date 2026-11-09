import { locale, t, tn } from '@/i18n'

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
  return seconds < 60 ? t('duration.seconds', { n: seconds }) : t('duration.minutes', { m: Math.floor(seconds / 60), s: seconds % 60 })
}

export type ReviewTone = 'positive' | 'mixed' | 'negative'

// the same split Metacritic uses for the colours of a score
export function reviewTone(kind: 'critics' | 'users', score: number): ReviewTone {
  const tone = kind === 'critics' ? metascoreTone(score) : userscoreTone(score)
  return tone === 'good' ? 'positive' : tone === 'mixed' ? 'mixed' : 'negative'
}

export function countLabel(kind: 'critics' | 'users', count: number | null): string {
  return count === null ? t('common.noData') : tn(kind === 'critics' ? 'count.critics' : 'count.users', count)
}

export function formatDate(iso: string): string {
  // a plain date (2026-11-05): read it as a calendar day, whatever the time zone
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(locale(), { day: 'numeric', month: 'long', year: 'numeric' })
}

export function compact(n: number): string {
  return new Intl.NumberFormat(locale(), { notation: 'compact', maximumFractionDigits: 1 }).format(n)
}

export function decimal(n: number | null, digits = 1): string {
  return n === null ? '—' : n.toLocaleString(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

// the names of the kinds of video in the current language
export const videoKindLabels: Record<'letsplay' | 'review', string> = {
  get letsplay() {
    return t('video.letsplay')
  },
  get review() {
    return t('video.review')
  },
}

// seconds from the start of a video as 4:07 or 1:02:09
export function formatTimecode(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}
