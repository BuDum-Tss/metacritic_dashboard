import { useEffect, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { api } from '@/api/client'
import type { SortKey, SortOrder } from '@/api/types'
import { GameCard } from '@/components/GameCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'

const PAGE_SIZE = 24
const ALL = 'all'

const sortItems = [
  { value: 'metascore', label: 'Metascore' },
  { value: 'userscore', label: 'Userscore' },
  { value: 'release', label: 'Дата релиза' },
  { value: 'title', label: 'Название' },
  { value: 'updated', label: 'Дата добавления' },
]

const orderItems = [
  { value: 'desc', label: 'По убыванию' },
  { value: 'asc', label: 'По возрастанию' },
]

export function GamesPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const platform = params.get('platform') ?? ALL
  const sort = (params.get('sort') ?? 'metascore') as SortKey
  const order = (params.get('order') ?? 'desc') as SortOrder
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  // the search box is local state, the URL is updated after a pause in typing
  const [search, setSearch] = useState(q)
  useEffect(() => {
    if (search === q) return
    const timer = setTimeout(() => update({ q: search, page: null }), 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    }
    setParams(next, { replace: true })
  }

  const platforms = useQuery({ queryKey: ['platforms'], queryFn: api.platforms })
  const games = useQuery({
    queryKey: ['games', { q, platform, sort, order, page }],
    queryFn: () =>
      api.games({ q, platform: platform === ALL ? undefined : platform, sort, order, page, pageSize: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  const platformItems = [
    { value: ALL, label: 'Все платформы' },
    ...(platforms.data ?? []).map((p) => ({ value: p.platform, label: `${p.name} (${p.games})` })),
  ]
  const totalPages = games.data ? Math.max(1, Math.ceil(games.data.total / PAGE_SIZE)) : 1

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <Input
            placeholder="Поиск по названию, жанру, разработчику, описанию"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <Select
          items={platformItems}
          value={platform}
          onValueChange={(value) => update({ platform: value === ALL ? null : value, page: null })}
        >
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {platformItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select items={sortItems} value={sort} onValueChange={(value) => update({ sort: value, page: null })}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sortItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select items={orderItems} value={order} onValueChange={(value) => update({ order: value, page: null })}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {orderItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {games.isError && (
        <p className="text-destructive">Не удалось загрузить игры: {games.error.message}</p>
      )}

      {games.isPending ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 12 }, (_, i) => (
            <Skeleton key={i} className="h-72 w-full" />
          ))}
        </div>
      ) : games.data && games.data.items.length > 0 ? (
        <>
          <p className="text-sm text-muted-foreground">Найдено игр: {games.data.total}</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {games.data.items.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        </>
      ) : (
        !games.isError && <p className="py-12 text-center text-muted-foreground">Игры не найдены</p>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button variant="outline" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
            Назад
          </Button>
          <span className="text-sm text-muted-foreground">
            Страница {page} из {totalPages}
          </span>
          <Button variant="outline" disabled={page >= totalPages} onClick={() => update({ page: String(page + 1) })}>
            Вперёд
          </Button>
        </div>
      )}
    </div>
  )
}
