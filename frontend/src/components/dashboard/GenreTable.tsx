import type { GenreStat } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { compact, decimal } from '@/lib/format'

// One thin bar per value; each column has its own scale, so no two scales share a plot.
function BarCell({ value, max, text }: { value: number | null; max: number; text: string }) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 bg-muted">
        <div
          className="h-2 rounded-r-[4px]"
          style={{ width: `${Math.max(2, (value / max) * 100)}%`, background: 'var(--viz-accent)' }}
        />
      </div>
      <span className="w-12 shrink-0 text-right tabular-nums">{text}</span>
    </div>
  )
}

export function GenreTable({ genres }: { genres: GenreStat[] }) {
  const maxAttention = Math.max(1, ...genres.map((g) => g.avg_attention))
  return (
    <ChartCard
      title="Жанры"
      subtitle="Какие жанры успешнее: средние оценки и внимание игроков. Только жанры, в которых не меньше 3 игр."
    >
      {genres.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Жанры появятся, когда в них наберётся хотя бы 3 игры.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Жанр</th>
                <th className="px-3 py-2 font-medium">Средний Metascore</th>
                <th className="px-3 py-2 font-medium">Средний Userscore</th>
                <th className="py-2 pl-3 font-medium">Оценок игроков на игру</th>
              </tr>
            </thead>
            <tbody>
              {genres.map((g) => (
                <tr key={g.genre} className="border-t">
                  <td className="py-2 pr-3">
                    <span className="font-medium">{g.genre}</span>
                    <span className="block text-xs text-muted-foreground">{g.games} игр</span>
                  </td>
                  <td className="px-3 py-2">
                    <BarCell value={g.avg_critics} max={100} text={decimal(g.avg_critics)} />
                  </td>
                  <td className="px-3 py-2">
                    <BarCell value={g.avg_users} max={10} text={decimal(g.avg_users)} />
                  </td>
                  <td className="py-2 pl-3">
                    <BarCell value={g.avg_attention} max={maxAttention} text={compact(g.avg_attention)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ChartCard>
  )
}
