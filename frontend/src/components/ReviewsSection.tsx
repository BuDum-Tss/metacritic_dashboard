import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'

import type { Overall, Review, ReviewKind, ReviewSummary, SummaryPoint } from '@/api/types'
import { ScoreHeader } from '@/components/Overall'
import { ScoreBadge } from '@/components/ScoreBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { formatDateTime, reviewTone, type ReviewTone } from '@/lib/format'
import { cn } from '@/lib/utils'

const TITLES: Record<ReviewKind, string> = { critics: 'Отзывы критиков', users: 'Отзывы игроков' }

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
  { key: 'all', label: 'Все' },
  { key: 'positive', label: 'Положительные' },
  { key: 'mixed', label: 'Смешанные' },
  { key: 'negative', label: 'Отрицательные' },
] as const
type ToneFilter = (typeof TONES)[number]['key']

function ReviewItem({ review, kind, accent }: { review: Review; kind: ReviewKind; accent?: PointKind }) {
  return (
    <li className={cn('space-y-1 rounded-md border p-3', accent && STYLES[accent].stripe)}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <ScoreBadge kind={kind === 'critics' ? 'critic' : 'user'} value={review.score} title="Оценка" />
        <span className="font-medium">{review.author ?? 'Аноним'}</span>
        <span className="text-xs text-muted-foreground">
          {[review.platform, review.date].filter(Boolean).join(' · ')}
        </span>
        {review.url && (
          <a href={review.url} target="_blank" rel="noreferrer" className="ml-auto text-xs underline">
            Полный обзор
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
        {kind === 'like' ? 'Что нравится' : 'Что не нравится'}
      </h4>
      {points.length === 0 ? (
        <p className="text-sm text-muted-foreground">В выборке нет оснований для этого раздела</p>
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
            <span className="ml-2 text-xs text-muted-foreground">· отзывов: {point.review_ids.length}</span>
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
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Card>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Резюме ИИ по {summary.sample_size}
                {summary.total_reviews ? ` из ${summary.total_reviews}` : ''} отзывов · {summary.model} ·{' '}
                {formatDateTime(summary.generated_at)}. Нажмите на пункт, чтобы оставить справа только отзывы, на
                которых он основан.
                {kind === 'critics' &&
                  ' Доступные отзывы критиков смещены к высоким оценкам: отсутствие критики здесь не значит, что недостатков нет.'}
              </p>
              <PointGroup kind="like" points={likes} activeId={pointId} onToggle={toggle} />
              <PointGroup kind="dislike" points={dislikes} activeId={pointId} onToggle={toggle} />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-3">
              {point && pointKind ? (
                <div
                  className={cn(
                    'flex items-start justify-between gap-3 rounded-md border p-2 pl-3',
                    STYLES[pointKind].chip,
                  )}
                >
                  <p className="text-sm">
                    Отзывы к пункту: <span className="font-medium">«{point.text}»</span>
                  </p>
                  <Button variant="outline" size="sm" onClick={() => setPointId(null)}>
                    Сбросить
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Выборка, на которой построено резюме: {summary.sample_size}
                  {summary.total_reviews ? ` из ${summary.total_reviews}` : ''} отзывов.
                </p>
              )}

              <div role="group" aria-label="Тональность" className="flex flex-wrap gap-2">
                {TONES.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    aria-pressed={tone === t.key}
                    onClick={() => setTone(t.key)}
                    className={cn(
                      'rounded-full border px-3 py-1 text-xs transition-colors hover:bg-muted',
                      tone === t.key && 'border-foreground bg-muted font-semibold',
                    )}
                  >
                    {t.label} ({counts[t.key]})
                  </button>
                ))}
              </div>

              {shown.length === 0 ? (
                <p className="text-sm text-muted-foreground">Нет отзывов, подходящих под выбранный фильтр</p>
              ) : (
                <ul className="max-h-[36rem] space-y-2 overflow-y-auto pr-1">
                  {shown.map((review) => (
                    <ReviewItem key={review.id} review={review} kind={kind} accent={pointKind} />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Резюме ИИ и отзывы пока недоступны</p>
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
      <h2 className="text-xl font-semibold">Отзывы</h2>
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
              {TITLES[kind]}
              {count !== null && <span className="ml-1 text-sm">({count})</span>}
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
