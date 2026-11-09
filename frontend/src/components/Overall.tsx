import type { Overall, ReviewKind } from '@/api/types'
import { ScoreBadge } from '@/components/ScoreBadge'
import { t, tn, type Key } from '@/i18n'
import { countLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

const TONES = [
  { key: 'positive', label: 'overall.positive', color: 'bg-green-600' },
  { key: 'mixed', label: 'overall.mixed', color: 'bg-yellow-400' },
  { key: 'negative', label: 'overall.negative', color: 'bg-red-600' },
] as const satisfies readonly { key: string; label: Key; color: string }[]

function ToneBar({ kind, overall }: { kind: ReviewKind; overall: Overall }) {
  const total = TONES.reduce((sum, tone) => sum + (overall[tone.key] ?? 0), 0)
  if (total === 0) return null
  const noun: Key = kind === 'critics' ? 'overall.nounCritics' : 'overall.nounUsers'
  return (
    <div className="space-y-2">
      <div className="flex h-1.5 gap-0.5">
        {TONES.map((tone) => {
          const count = overall[tone.key] ?? 0
          return count > 0 && <div key={tone.key} style={{ flexGrow: count }} className={cn('rounded-full', tone.color)} />
        })}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        {TONES.map((tone) => {
          const count = overall[tone.key] ?? 0
          return (
            <div key={tone.key}>
              <p className="font-semibold">
                {Math.round((count / total) * 100)}% {t(tone.label)}
              </p>
              <p className="text-muted-foreground">
                {tn(noun, count)}
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
          <p className="font-semibold">{overall.verdict ?? t('overall.none')}</p>
          <p className="text-sm text-muted-foreground">{t('overall.basedOn', { count: countLabel(kind, overall.reviews_count) })}</p>
        </div>
        <ToneBar kind={kind} overall={overall} />
      </div>
    </div>
  )
}
