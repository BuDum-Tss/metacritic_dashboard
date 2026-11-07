import { useState } from 'react'

import type { Overall, Review, ReviewKind, ReviewSummary, SummaryPoint } from '@/api/types'
import { ScoreHeader } from '@/components/Overall'
import { ScoreBadge } from '@/components/ScoreBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime, reviewTone, type ReviewTone } from '@/lib/format'
import { cn } from '@/lib/utils'

const TITLES: Record<ReviewKind, string> = { critics: 'Отзывы критиков', users: 'Отзывы игроков' }

const TABS = [
  { key: 'all', label: 'Все' },
  { key: 'positive', label: 'Положительные' },
  { key: 'mixed', label: 'Смешанные' },
  { key: 'negative', label: 'Отрицательные' },
] as const
type Tab = (typeof TABS)[number]['key']

function ReviewItem({ review, kind }: { review: Review; kind: ReviewKind }) {
  return (
    <li className="space-y-1 rounded-md border p-3">
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

function ReviewList({ reviews, kind }: { reviews: Review[]; kind: ReviewKind }) {
  return (
    <ul className="max-h-[32rem] space-y-2 overflow-y-auto pr-1">
      {reviews.map((review) => (
        <ReviewItem key={review.id} review={review} kind={kind} />
      ))}
    </ul>
  )
}

// one of the two columns of the summary: what is liked or what is not; a click filters the reviews
function PointColumn({
  heading,
  points,
  activeId,
  onToggle,
}: {
  heading: string
  points: SummaryPoint[]
  activeId: number | null
  onToggle: (id: number) => void
}) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold">{heading}</h4>
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
              'w-full rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted',
              point.id === activeId && 'border-primary bg-muted',
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

function ReviewColumn({
  kind,
  overall,
  summary,
}: {
  kind: ReviewKind
  overall: Overall | null
  summary: ReviewSummary | null
}) {
  const [tab, setTab] = useState<Tab>('all')
  const [pointId, setPointId] = useState<number | null>(null)

  const sample = summary?.reviews ?? []
  const byTone = (tone: ReviewTone) =>
    sample.filter((r) => r.score !== null && reviewTone(kind, r.score) === tone)
  const counts: Record<Tab, number> = {
    all: sample.length,
    positive: byTone('positive').length,
    mixed: byTone('mixed').length,
    negative: byTone('negative').length,
  }

  const point = summary ? [...summary.likes, ...summary.dislikes].find((p) => p.id === pointId) : undefined
  // the tab narrows the sample by tone, a chosen point keeps only the reviews it is based on
  const shown = (tab === 'all' ? sample : byTone(tab)).filter((r) => !point || point.review_ids.includes(r.id))

  // choosing a point shows all the reviews it cites; choosing it again removes the filter
  const toggle = (id: number) => {
    if (id === pointId) {
      setPointId(null)
    } else {
      setPointId(id)
      setTab('all')
    }
  }

  return (
    <Card>
      <CardHeader className="space-y-4">
        <CardTitle className="text-lg">{TITLES[kind]}</CardTitle>
        {overall && <ScoreHeader kind={kind} overall={overall} />}
      </CardHeader>
      <CardContent className="space-y-4">
        {summary ? (
          <>
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Резюме ИИ по {summary.sample_size}
                {summary.total_reviews ? ` из ${summary.total_reviews}` : ''} отзывов · {summary.model} ·{' '}
                {formatDateTime(summary.generated_at)}. Нажмите на пункт, чтобы оставить только отзывы, на которых он
                основан.
                {kind === 'critics' &&
                  ' Доступные отзывы критиков смещены к высоким оценкам: отсутствие критики здесь не значит, что недостатков нет.'}
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <PointColumn heading="Что нравится" points={summary.likes} activeId={pointId} onToggle={toggle} />
                <PointColumn
                  heading="Что не нравится"
                  points={summary.dislikes}
                  activeId={pointId}
                  onToggle={toggle}
                />
              </div>
            </div>

            <div role="tablist" className="flex flex-wrap gap-x-4 gap-y-1 border-b">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  role="tab"
                  type="button"
                  aria-selected={tab === t.key}
                  onClick={() => setTab(t.key)}
                  className={cn(
                    '-mb-px border-b-2 border-transparent pb-2 text-sm text-muted-foreground hover:text-foreground',
                    tab === t.key && 'border-foreground font-semibold text-foreground',
                  )}
                >
                  {t.label}
                  <span className="ml-1 text-xs">({counts[t.key]})</span>
                </button>
              ))}
            </div>

            <div className="space-y-2">
              {point ? (
                <div className="flex items-start justify-between gap-3 rounded-md bg-muted/40 p-2 pl-3">
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
              {shown.length === 0 ? (
                <p className="text-sm text-muted-foreground">Нет отзывов, подходящих под выбранный фильтр</p>
              ) : (
                <ReviewList reviews={shown} kind={kind} />
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Резюме ИИ и отзывы пока недоступны</p>
        )}
      </CardContent>
    </Card>
  )
}

export function ReviewsSection({
  overall,
  summaries,
}: {
  overall: Record<ReviewKind, Overall | null>
  summaries: Record<ReviewKind, ReviewSummary | null>
}) {
  if (!overall.critics && !overall.users && !summaries.critics && !summaries.users) return null
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold">Отзывы</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {(['critics', 'users'] as const).map((kind) => (
          <ReviewColumn key={kind} kind={kind} overall={overall[kind]} summary={summaries[kind]} />
        ))}
      </div>
    </section>
  )
}
