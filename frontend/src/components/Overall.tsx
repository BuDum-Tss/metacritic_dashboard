import type { Overall, ReviewKind } from '@/api/types'
import { ScoreBadge } from '@/components/ScoreBadge'
import { countLabel, plural } from '@/lib/format'
import { cn } from '@/lib/utils'

const TONES = [
  { key: 'positive', label: 'Положительные', color: 'bg-green-600' },
  { key: 'mixed', label: 'Смешанные', color: 'bg-yellow-400' },
  { key: 'negative', label: 'Отрицательные', color: 'bg-red-600' },
] as const

function ToneBar({ kind, overall }: { kind: ReviewKind; overall: Overall }) {
  const total = TONES.reduce((sum, t) => sum + (overall[t.key] ?? 0), 0)
  if (total === 0) return null
  const noun: [string, string, string] = kind === 'critics' ? ['отзыв', 'отзыва', 'отзывов'] : ['оценка', 'оценки', 'оценок']
  return (
    <div className="space-y-2">
      <div className="flex h-1.5 gap-0.5">
        {TONES.map((t) => {
          const count = overall[t.key] ?? 0
          return count > 0 && <div key={t.key} style={{ flexGrow: count }} className={cn('rounded-full', t.color)} />
        })}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        {TONES.map((t) => {
          const count = overall[t.key] ?? 0
          return (
            <div key={t.key}>
              <p className="font-semibold">
                {Math.round((count / total) * 100)}% {t.label}
              </p>
              <p className="text-muted-foreground">
                {count} {plural(count, noun)}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// the header of a reviews column, as on Metacritic: the score, the verdict and the tone split
export function ScoreHeader({ kind, overall }: { kind: ReviewKind; overall: Overall }) {
  return (
    <div className="flex items-start gap-4">
      <ScoreBadge kind={kind === 'critics' ? 'critic' : 'user'} value={overall.score} size="lg" />
      <div className="min-w-0 flex-1 space-y-3">
        <div>
          <p className="font-semibold">{overall.verdict ?? 'Оценки пока нет'}</p>
          <p className="text-sm text-muted-foreground">На основе: {countLabel(kind, overall.reviews_count)}</p>
        </div>
        <ToneBar kind={kind} overall={overall} />
      </div>
    </div>
  )
}

// the overall scores in the hero of a game card
export function OverallInline({ overall }: { overall: Record<ReviewKind, Overall | null> }) {
  const blocks = (['critics', 'users'] as const).filter((kind) => overall[kind])
  if (blocks.length === 0) return null
  return (
    <div className="flex flex-wrap gap-x-8 gap-y-3">
      {blocks.map((kind) => {
        const o = overall[kind]!
        return (
          <div key={kind} className="flex items-center gap-3">
            <ScoreBadge kind={kind === 'critics' ? 'critic' : 'user'} value={o.score} size="md" />
            <div className="text-sm leading-tight">
              <p className="font-semibold">{kind === 'critics' ? 'Metascore' : 'Оценка игроков'}</p>
              <p className="text-muted-foreground">{o.verdict ?? 'оценки пока нет'}</p>
              <p className="text-xs text-muted-foreground">{countLabel(kind, o.reviews_count)}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
