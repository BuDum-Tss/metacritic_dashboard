import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '@/api/client'
import { GameCard } from '@/components/GameCard'
import { ScoreBadge } from '@/components/ScoreBadge'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateTime, metascoreTone, userscoreTone } from '@/lib/format'

function Video({ url }: { url: string }) {
  // jwplayer embed pages can be shown in a frame, other links are opened separately
  if (url.includes('/players/')) {
    return (
      <div className="aspect-video w-full overflow-hidden rounded-lg bg-black">
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

      <div className="grid gap-6 md:grid-cols-[minmax(0,420px)_1fr]">
        <div className="aspect-video w-full overflow-hidden rounded-lg bg-muted">
          {g.cover_url && <img src={g.cover_url} alt={g.title} className="h-full w-full object-cover" />}
        </div>
        <div className="space-y-4">
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
          {g.description && <p className="whitespace-pre-line leading-relaxed">{g.description}</p>}
          {g.video_url && <Video url={g.video_url} />}
          <p className="text-xs text-muted-foreground">
            Обновлено: {formatDateTime(g.last_processed_at)} ·{' '}
            <a href={g.url} target="_blank" rel="noreferrer" className="underline">
              Страница на Metacritic
            </a>
          </p>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Оценки по платформам</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Платформа</TableHead>
              <TableHead>Metascore</TableHead>
              <TableHead>Отзывов критиков</TableHead>
              <TableHead>Userscore</TableHead>
              <TableHead>Оценок игроков</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {g.platforms.map((p) => (
              <TableRow key={p.platform}>
                <TableCell className="font-medium">{p.name}</TableCell>
                <TableCell>
                  <ScoreBadge value={p.metascore} tone={metascoreTone(p.metascore)} title="Metascore" />
                </TableCell>
                <TableCell>{p.critic_reviews_count ?? '—'}</TableCell>
                <TableCell>
                  <ScoreBadge value={p.userscore} tone={userscoreTone(p.userscore)} title="Userscore" />
                </TableCell>
                <TableCell>{p.user_reviews_count ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

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
