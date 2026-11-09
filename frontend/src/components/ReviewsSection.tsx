import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'

import type { Overall, Review, ReviewKind, ReviewSummary, SummaryPoint } from '@/api/types'
import { InfoTip } from '@/components/InfoTip'
import { ScoreHeader } from '@/components/Overall'
import { ScoreBadge } from '@/components/ScoreBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { t, tn, type Key } from '@/i18n'
import { formatDateTime, reviewTone, type ReviewTone } from '@/lib/format'
import { cn } from '@/lib/utils'

const TITLES: Record<ReviewKind, Key> = { critics: 'reviews.titleCritics', users: 'reviews.titleUsers' }

// what the sample is and why it is smaller than the total; the total is counted over all platforms
function sampleNote(kind: ReviewKind, summary: ReviewSummary): string {
  const n = summary.sample_size
  const total = summary.total_reviews
  if (kind === 'critics') {
    const sample = tn('reviews.sampleCritics', n)
    const all = total ? ` ${t('reviews.ofTotalAll', { total })}` : ''
    return `${sample}${all}${t('reviews.criticsTail')}`
  }
  const sample = tn('reviews.sampleUsers', n)
  const all = total ? ` ${tn('reviews.ofTotalUsers', total, { total })}` : ''
  return `${sample}${all}${t('reviews.usersTail')}`
}

type PointKind = 'like' | 'dislike'

// likes are green and dislikes are red; the heading and the icon say it too, not only the colour
const STYLES: Record<PointKind, { heading: string; point: string; active: string; stripe: string; chip: string }> = {
  like: {
    heading: 'text-green-700 dark:text-green-400',
    point: 'border-green-600/40 border-l-green-600 bg-green-600/5 hover:bg-green-600/10',
    active: 'border-green-600 bg-green-600/15 ring-1 ring-green-600',
    stripe: 'border-l-4 border-l-green-600',
    chip: 'border-green-600/40 bg-green-600/10',
  },
  dislike: {
    heading: 'text-red-700 dark:text-red-400',
    point: 'border-red-600/40 border-l-red-600 bg-red-600/5 hover:bg-red-600/10',
    active: 'border-red-600 bg-red-600/15 ring-1 ring-red-600',
    stripe: 'border-l-4 border-l-red-600',
    chip: 'border-red-600/40 bg-red-600/10',
  },
}

const TONES = [
  { key: 'all', label: 'reviews.all' },
  { key: 'positive', label: 'overall.positive' },
  { key: 'mixed', label: 'overall.mixed' },
  { key: 'negative', label: 'overall.negative' },
] as const satisfies readonly { key: string; label: Key }[]
type ToneFilter = (typeof TONES)[number]['key']

function ReviewItem({ review, kind, accent }: { review: Review; kind: ReviewKind; accent?: PointKind }) {
  return (
    <li className={cn('space-y-1 rounded-md border p-3', accent && STYLES[accent].stripe)}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <ScoreBadge kind={kind === 'critics' ? 'critic' : 'user'} value={review.score} title={t('reviews.score')} />
        <span className="font-medium">{review.author ?? t('reviews.anonymous')}</span>
        <span className="text-xs text-muted-foreground">
          {[review.platform, review.date].filter(Boolean).join(' · ')}
        </span>
        {review.url && (
          <a href={review.url} target="_blank" rel="noreferrer" className="ml-auto text-xs underline">
            {t('reviews.full')}
          </a>
        )}
      </div>
      <p className="text-sm leading-relaxed">{review.text}</p>
    </li>
  )
}

// the likes or the dislikes of the summary; a click on a point filters the reviews on the right
function PointGroup({
  kind,
  points,
  activeId,
  onToggle,
}: {
  kind: PointKind
  points: SummaryPoint[]
  activeId: number | null
  onToggle: (id: number) => void
}) {
  const style = STYLES[kind]
  const Icon = kind === 'like' ? ThumbsUp : ThumbsDown
  return (
    <div className="space-y-2">
      <h4 className={cn('flex items-center gap-2 text-sm font-semibold', style.heading)}>
        <Icon className="size-4" />
        {kind === 'like' ? t('reviews.likes') : t('reviews.dislikes')}
      </h4>
      {points.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('reviews.noGrounds')}</p>
      ) : (
        points.map((point) => (
          <button
            key={point.id}
            type="button"
            aria-pressed={point.id === activeId}
            onClick={() => onToggle(point.id)}
            className={cn(
              'w-full rounded-md border border-l-4 px-3 py-2 text-left text-sm transition-colors',
              style.point,
              point.id === activeId && style.active,
            )}
          >
            {point.text}
            <span className="ml-2 text-xs text-muted-foreground">{t('reviews.reviewsCount', { n: point.review_ids.length })}</span>
          </button>
        ))
      )}
    </div>
  )
}

// one tab: the score, the summary on the left, the reviews on the right
function ReviewPane({
  kind,
  overall,
  summary,
}: {
  kind: ReviewKind
  overall: Overall | null
  summary: ReviewSummary | null
}) {
  const [tone, setTone] = useState<ToneFilter>('all')
  const [pointId, setPointId] = useState<number | null>(null)

  const sample = summary?.reviews ?? []
  const byTone = (t: ReviewTone) => sample.filter((r) => r.score !== null && reviewTone(kind, r.score) === t)
  const counts: Record<ToneFilter, number> = {
    all: sample.length,
    positive: byTone('positive').length,
    mixed: byTone('mixed').length,
    negative: byTone('negative').length,
  }

  const likes = summary?.likes ?? []
  const dislikes = summary?.dislikes ?? []
  const point = [...likes, ...dislikes].find((p) => p.id === pointId)
  const pointKind: PointKind | undefined = point ? (likes.includes(point) ? 'like' : 'dislike') : undefined
  // the tone narrows the sample, a chosen point keeps only the reviews it is based on
  const shown = (tone === 'all' ? sample : byTone(tone)).filter((r) => !point || point.review_ids.includes(r.id))

  // choosing a point shows all the reviews it cites; choosing it again removes the filter
  const toggle = (id: number) => {
    if (id === pointId) {
      setPointId(null)
    } else {
      setPointId(id)
      setTone('all')
    }
  }

  return (
    <div className="space-y-4">
      {overall && (
        <Card>
          <CardContent>
            <ScoreHeader kind={kind} overall={overall} />
          </CardContent>
        </Card>
      )}

      {summary ? (
        <div className="grid items-stretch gap-4 lg:min-h-[28rem] lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Card>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-base font-semibold">{t('reviews.aiSummary')}</h3>
                <InfoTip>
                  {t('reviews.aiNote', {
                    sample: sampleNote(kind, summary),
                    model: summary.model,
                    time: formatDateTime(summary.generated_at),
                  })}{' '}
                  {t('reviews.clickHint')}
                  {kind === 'critics' && ` ${t('reviews.criticsBias')}`}
                </InfoTip>
              </div>
              <PointGroup kind="like" points={likes} activeId={pointId} onToggle={toggle} />
              <PointGroup kind="dislike" points={dislikes} activeId={pointId} onToggle={toggle} />
            </CardContent>
          </Card>

          {/* on wide screens the card takes the height of the summary and the list scrolls inside it */}
          <Card className="lg:h-0 lg:min-h-full">
            <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
              {point && pointKind ? (
                <div
                  className={cn(
                    'flex items-start justify-between gap-3 rounded-md border p-2 pl-3',
                    STYLES[pointKind].chip,
                  )}
                >
                  <p className="text-sm">
                    {t('reviews.forPoint')}<span className="font-medium">«{point.text}»</span>
                  </p>
                  <Button variant="outline" size="sm" onClick={() => setPointId(null)}>
                    {t('reviews.reset')}
                  </Button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-base font-semibold">{t('reviews.sampleReviews')}</h3>
                  <InfoTip>{sampleNote(kind, summary)}</InfoTip>
                </div>
              )}

              <div role="group" aria-label={t('reviews.tone')} className="flex flex-wrap gap-2">
                {TONES.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    aria-pressed={tone === item.key}
                    onClick={() => setTone(item.key)}
                    className={cn(
                      'rounded-full border px-3 py-1 text-xs transition-colors hover:bg-muted',
                      tone === item.key && 'border-foreground bg-muted font-semibold',
                    )}
                  >
                    {t(item.label)} ({counts[item.key]})
                  </button>
                ))}
              </div>

              {shown.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('reviews.noMatch')}</p>
              ) : (
                <ul className="max-h-[36rem] min-h-0 space-y-2 overflow-y-auto pr-1 lg:max-h-none lg:flex-1">
                  {shown.map((review) => (
                    <ReviewItem key={review.id} review={review} kind={kind} accent={pointKind} />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t('reviews.unavailable')}</p>
      )}
    </div>
  )
}

export function ReviewsSection({
  overall,
  summaries,
}: {
  overall: Record<ReviewKind, Overall | null>
  summaries: Record<ReviewKind, ReviewSummary | null>
}) {
  const kinds = ['critics', 'users'] as const
  const [active, setActive] = useState<ReviewKind>(overall.critics || summaries.critics ? 'critics' : 'users')

  if (!overall.critics && !overall.users && !summaries.critics && !summaries.users) return null
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">{t('reviews.title')}</h2>
      <div role="tablist" className="flex gap-6 border-b">
        {kinds.map((kind) => {
          const count = overall[kind]?.reviews_count ?? summaries[kind]?.total_reviews ?? null
          return (
            <button
              key={kind}
              role="tab"
              type="button"
              aria-selected={active === kind}
              onClick={() => setActive(kind)}
              className={cn(
                '-mb-px border-b-2 border-transparent pb-2 text-base text-muted-foreground hover:text-foreground',
                active === kind && 'border-foreground font-semibold text-foreground',
              )}
            >
              {t(TITLES[kind])}
              {count !== null && <span className="ml-1.5 text-sm">{`(${count})`}</span>}
            </button>
          )
        })}
      </div>
      {/* both panes stay mounted, so the chosen point and tone of a tab survive switching */}
      {kinds.map((kind) => (
        <div key={kind} role="tabpanel" className={cn(active !== kind && 'hidden')}>
          <ReviewPane kind={kind} overall={overall[kind]} summary={summaries[kind]} />
        </div>
      ))}
    </section>
  )
}
