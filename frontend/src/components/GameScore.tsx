import { t } from '@/i18n'
import type { Score } from '@/api/types'
import { ScoreBadge } from '@/components/ScoreBadge'

// The single score of a game: critics in a square, players in a circle.
export function GameScore({
  score,
  size,
  captions = false,
}: {
  score: Score
  size: 'sm' | 'md' | 'lg'
  captions?: boolean
}) {
  return (
    <div className="flex shrink-0 items-start gap-2">
      <div className="flex flex-col items-center gap-1">
        <ScoreBadge kind="critic" value={score.critics} size={size} title={t('score.metascoreTip')} />
        {captions && <span className="text-xs text-muted-foreground">{t('score.critics')}</span>}
      </div>
      <div className="flex flex-col items-center gap-1">
        <ScoreBadge kind="user" value={score.users} size={size} title={t('score.userscoreTip')} />
        {captions && <span className="text-xs text-muted-foreground">{t('score.players')}</span>}
      </div>
    </div>
  )
}
