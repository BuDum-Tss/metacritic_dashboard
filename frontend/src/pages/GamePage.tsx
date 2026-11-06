import { useQuery } from '@tanstack/react-query'
import { useLayoutEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '@/api/client'
import type { GameDetail } from '@/api/types'
import { GameCard } from '@/components/GameCard'
import { OverallInline } from '@/components/Overall'
import { ReviewsSection } from '@/components/ReviewsSection'
import { ScoreBadge } from '@/components/ScoreBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { countLabel, formatDateTime } from '@/lib/format'

function Video({ url }: { url: string }) {
  // jwplayer embed pages can be shown in a frame, other links are opened separately
  if (url.includes('/players/')) {
    return (
      <div className="aspect-video w-full max-w-3xl overflow-hidden rounded-lg bg-black">
        <iframe src={url} title="Трейлер" allowFullScreen className="h-full w-full" />
      </div>
    )
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" className="text-sm underline">
      Смотреть видео
    </a>
  )
}

// the height of an element, kept up to date while it is resized
function useHeight<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [height, setHeight] = useState<number | null>(null)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(() => setHeight(element.offsetHeight))
    observer.observe(element)
    setHeight(element.offsetHeight)
    return () => observer.disconnect()
  }, [])
  return [ref, height] as const
}

function Hero({ game: g }: { game: GameDetail }) {
  const [coverRef, coverHeight] = useHeight<HTMLDivElement>()
  const [textRef, textHeight] = useHeight<HTMLDivElement>()
  const [expanded, setExpanded] = useState(false)

  // the text column is folded down to the bottom edge of the cover when it is taller than the cover
  const overflowing = coverHeight !== null && textHeight !== null && textHeight > coverHeight
  const collapsed = overflowing && !expanded

  return (
    <div className="grid items-start gap-6 md:grid-cols-[minmax(0,420px)_1fr]">
      <div ref={coverRef} className="aspect-video w-full overflow-hidden rounded-lg bg-muted">
        {g.cover_url && <img src={g.cover_url} alt={g.title} className="h-full w-full object-cover" />}
      </div>
      <div>
        <div
          className="relative overflow-hidden"
          style={collapsed ? { maxHeight: coverHeight ?? undefined } : undefined}
        >
          <div ref={textRef} className="space-y-3">
            <div>
              <h1 className="text-3xl font-bold">{g.title}</h1>
              {g.developer && <p className="text-muted-foreground">Разработчик: {g.developer}</p>}
            </div>
            {g.genres.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {g.genres.map((genre) => (
                  <Badge key={genre} variant="secondary">
                    {genre}
                  </Badge>
                ))}
              </div>
            )}
            <OverallInline overall={g.overall} />
            {g.description && <p className="whitespace-pre-line leading-relaxed">{g.description}</p>}
          </div>
          {collapsed && (
            <div className="absolute inset-x-0 bottom-0 flex h-16 items-end bg-gradient-to-t from-background via-background/90 to-transparent">
              <Button variant="link" size="sm" className="px-0" onClick={() => setExpanded(true)}>
                Показать полностью
              </Button>
            </div>
          )}
        </div>
        {overflowing && expanded && (
          <Button variant="link" size="sm" className="px-0" onClick={() => setExpanded(false)}>
            Свернуть
          </Button>
        )}
      </div>
    </div>
  )
}

export function GamePage() {
  const id = Number(useParams().id)
  const game = useQuery({
    queryKey: ['game', id],
    queryFn: () => api.game(id),
    enabled: Number.isInteger(id),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  })

  if (game.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  if (game.isError) {
    const notFound = game.error instanceof ApiError && game.error.status === 404
    return (
      <div className="space-y-3">
        <p className="text-destructive">{notFound ? 'Игра не найдена' : `Ошибка: ${game.error.message}`}</p>
        <Link to="/" className="text-sm underline">
          К списку игр
        </Link>
      </div>
    )
  }

  const g = game.data
  return (
    <div className="space-y-8">
      <Link to="/" className="text-sm text-muted-foreground hover:underline">
        ← К списку игр
      </Link>

      <div className="space-y-3">
        {/* the key resets the folded state when another game is opened */}
        <Hero key={g.id} game={g} />
        <p className="text-xs text-muted-foreground">
          Обновлено: {formatDateTime(g.last_processed_at)} ·{' '}
          <a href={g.url} target="_blank" rel="noreferrer" className="underline">
            Страница на Metacritic
          </a>
        </p>
      </div>

      {g.video_url && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Трейлер</h2>
          <Video url={g.video_url} />
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Оценки по платформам</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {g.platforms.map((p) => (
            <Card key={p.platform} size="sm">
              <CardHeader>
                <CardTitle className="text-base">{p.name}</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 items-start gap-x-4 gap-y-3">
                <div className="flex items-center gap-3">
                  <ScoreBadge kind="critic" value={p.metascore} size="md" />
                  <div className="text-xs leading-tight text-muted-foreground">
                    <p className="text-sm font-medium text-foreground">Metascore</p>
                    <p>{countLabel('critics', p.critic_reviews_count)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <ScoreBadge kind="user" value={p.userscore} size="md" />
                  <div className="text-xs leading-tight text-muted-foreground">
                    <p className="text-sm font-medium text-foreground">Userscore</p>
                    <p>{countLabel('users', p.user_reviews_count)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <ReviewsSection key={`reviews-${g.id}`} overall={g.overall} summaries={g.summaries} />

      {g.similar.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Похожие игры</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {g.similar.map((other) => (
              <GameCard key={other.id} game={other} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
