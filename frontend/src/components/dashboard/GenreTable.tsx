import type { GenreStat } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { compact, decimal } from '@/lib/format'

export function GenreTable({ genres }: { genres: GenreStat[] }) {
  return (
    <ChartCard
      title="Жанры"
      className="lg:h-0 lg:min-h-full"
      contentClassName="min-h-0 flex-1"
      info="Какие жанры успешнее: средние оценки и число оценок игроков на игру жанра. Только жанры, где не меньше 3 игр."
    >
      {genres.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Жанры появятся, когда в них наберётся хотя бы 3 игры.
        </p>
      ) : (
        <div className="max-h-96 overflow-auto lg:h-full lg:max-h-none">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Жанр</th>
                <th className="px-2 py-2 font-medium">Metascore</th>
                <th className="px-2 py-2 font-medium">Userscore</th>
                <th className="py-2 pl-2 font-medium">Оценок на игру</th>
              </tr>
            </thead>
            <tbody>
              {genres.map((g) => (
                <tr key={g.genre} className="border-t">
                  <td className="py-2 pr-3">
                    <span className="break-words font-medium">{g.genre}</span>
                    <span className="block text-xs text-muted-foreground">{g.games} игр</span>
                  </td>
                  <td className="px-2 py-2">
                    <span className="tabular-nums">{g.avg_critics === null ? '—' : decimal(g.avg_critics)}</span>
                  </td>
                  <td className="px-2 py-2">
                    <span className="tabular-nums">{g.avg_users === null ? '—' : decimal(g.avg_users)}</span>
                  </td>
                  <td className="py-2 pl-2">
                    <span className="tabular-nums">{g.avg_attention === null ? '—' : compact(g.avg_attention)}</span>
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
