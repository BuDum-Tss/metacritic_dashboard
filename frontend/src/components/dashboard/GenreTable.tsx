import { t, tn } from '@/i18n'
import { ChevronDown, ChevronsUpDown, ChevronUp } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { GenreStat } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { compact, decimal } from '@/lib/format'
import { cn } from '@/lib/utils'

type SortKey = 'avg_critics' | 'avg_users' | 'avg_attention'
type Order = 'asc' | 'desc'

const COLUMNS: { key: SortKey; label: () => string; format: (value: number) => string }[] = [
  { key: 'avg_critics', label: () => 'Metascore', format: (value) => decimal(value) },
  { key: 'avg_users', label: () => 'Userscore', format: (value) => decimal(value) },
  { key: 'avg_attention', label: () => t('genres.attention'), format: compact },
]

// the genres by one of the metrics; a genre without the value is always last
function sortGenres(genres: GenreStat[], key: SortKey, order: Order): GenreStat[] {
  const sign = order === 'asc' ? 1 : -1
  return [...genres].sort((a, b) => {
    const x = a[key]
    const y = b[key]
    if (x === null && y === null) return a.genre.localeCompare(b.genre)
    if (x === null) return 1
    if (y === null) return -1
    return x === y ? a.genre.localeCompare(b.genre) : sign * (x - y)
  })
}

function SortIcon({ active, order }: { active: boolean; order: Order }) {
  if (!active) return <ChevronsUpDown className="size-3.5 opacity-40" />
  return order === 'asc' ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />
}

export function GenreTable({ genres }: { genres: GenreStat[] }) {
  // at first by the number of ratings per game, the most responded genres on top
  const [sort, setSort] = useState<{ key: SortKey; order: Order }>({ key: 'avg_attention', order: 'desc' })
  const sorted = useMemo(() => sortGenres(genres, sort.key, sort.order), [genres, sort])

  // a click on the sorted column turns the order round, a click on another one sorts by it, the highest first
  const choose = (key: SortKey) =>
    setSort((current) =>
      current.key === key ? { key, order: current.order === 'desc' ? 'asc' : 'desc' } : { key, order: 'desc' },
    )

  return (
    <ChartCard
      title={t('genres.title')}
      className="lg:h-0 lg:min-h-full"
      contentClassName="min-h-0 flex-1"
      info={t('genres.info')}
    >
      {genres.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t('genres.empty')}
        </p>
      ) : (
        <div className="max-h-96 overflow-auto lg:h-full lg:max-h-none">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">{t('genres.genre')}</th>
                {COLUMNS.map((column, index) => {
                  const active = sort.key === column.key
                  return (
                    <th
                      key={column.key}
                      className={cn('py-2 font-medium', index === COLUMNS.length - 1 ? 'pl-2' : 'px-2')}
                      aria-sort={active ? (sort.order === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      <button
                        type="button"
                        onClick={() => choose(column.key)}
                        title={t('genres.sortBy', { label: column.label() })}
                        className={cn(
                          'inline-flex items-center gap-1 text-left font-medium hover:text-foreground',
                          active && 'text-foreground',
                        )}
                      >
                        {column.label()}
                        <SortIcon active={active} order={sort.order} />
                      </button>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {sorted.map((g) => (
                <tr key={g.genre} className="border-t">
                  <td className="py-2 pr-3">
                    <span className="break-words font-medium">{g.genre}</span>
                    <span className="block text-xs text-muted-foreground">{tn('genres.games', g.games)}</span>
                  </td>
                  {COLUMNS.map((column, index) => (
                    <td key={column.key} className={index === COLUMNS.length - 1 ? 'py-2 pl-2' : 'px-2 py-2'}>
                      <span className="tabular-nums">{g[column.key] === null ? '—' : column.format(g[column.key] as number)}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ChartCard>
  )
}
