import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '@/api/client'
import { Carousel } from '@/components/Carousel'
import { Divergences } from '@/components/dashboard/Divergences'
import { GenreTable } from '@/components/dashboard/GenreTable'
import { Rhythm } from '@/components/dashboard/Rhythm'
import { SuccessMap } from '@/components/dashboard/SuccessMap'
import { Tiles } from '@/components/dashboard/Tiles'
import { GameCard } from '@/components/GameCard'
import { InfoTip } from '@/components/InfoTip'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export function DashboardPage() {
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  })
  const recent = useQuery({
    queryKey: ['recent-releases'],
    queryFn: () => api.games({ sort: 'release', order: 'desc', page: 1, pageSize: 12 }),
  })

  const data = dashboard.data
  return (
    <div className="space-y-8">
      <h1 className="flex items-center gap-2 text-3xl font-bold">
        Рынок игр
        <InfoTip>Какие игры успешнее и почему, по данным Metacritic.</InfoTip>
      </h1>

      {dashboard.isError && <p className="text-destructive">Не удалось загрузить дашборд: {dashboard.error.message}</p>}

      {!data ? (
        !dashboard.isError && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
            <Skeleton className="h-96 w-full" />
          </div>
        )
      ) : (
        // while the numbers reload the page keeps its shape and only dims
        <div className={cn('space-y-8 transition-opacity', dashboard.isFetching && 'opacity-70')}>
          <Tiles tiles={data.tiles} />
          {/* the map is square; the genres take the rest of the row */}
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,34rem)_minmax(0,1fr)]">
            <SuccessMap points={data.map.points} attentionMedian={data.map.attention_median} />
            <GenreTable genres={data.genres} />
          </div>
          <Divergences criticsLove={data.divergences.critics_love} playersLove={data.divergences.players_love} />
          <Rhythm days={data.rhythm.days} coverage={data.rhythm.coverage} />
        </div>
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Недавние релизы</h2>
          <Link
            to="/games?sort=release&order=desc"
            className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
          >
            Смотреть все →
          </Link>
        </div>
        {recent.isPending ? (
          <Skeleton className="h-72 w-full" />
        ) : recent.data && recent.data.items.length > 0 ? (
          <Carousel>
            {recent.data.items.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </Carousel>
        ) : (
          <p className="text-sm text-muted-foreground">Игр пока нет.</p>
        )}
      </section>
    </div>
  )
}
