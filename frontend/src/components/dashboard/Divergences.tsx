import { Link } from 'react-router-dom'

import type { Divergence } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { ScoreBadge } from '@/components/ScoreBadge'
import { decimal } from '@/lib/format'

function Row({ item }: { item: Divergence }) {
  const sign = item.gap > 0 ? '+' : '−'
  return (
    <li className="space-y-1 py-3">
      <div className="flex items-center gap-3">
        <Link to={`/games/${item.id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
          {item.title}
        </Link>
        <div className="flex shrink-0 items-center gap-1.5">
          <ScoreBadge kind="critic" value={item.critics} />
          <ScoreBadge kind="user" value={item.users} />
        </div>
        <span className="w-14 shrink-0 text-right text-sm tabular-nums text-muted-foreground" title="Разрыв, баллов из 100">
          {sign}
          {decimal(Math.abs(item.gap), 0)}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {item.reason
          ? `${item.reason.source === 'users' ? 'Игроки жалуются' : 'Критики жалуются'}: ${item.reason.text}`
          : 'Резюме ИИ пока нет'}
      </p>
    </li>
  )
}

function Column({ title, subtitle, items }: { title: string; subtitle: string; items: Divergence[] }) {
  return (
    <ChartCard title={title} subtitle={subtitle}>
      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Пока нет игр с заметным разрывом.</p>
      ) : (
        <ul className="divide-y">
          {items.map((item) => (
            <Row key={item.id} item={item} />
          ))}
        </ul>
      )}
    </ChartCard>
  )
}

export function Divergences({ criticsLove, playersLove }: { criticsLove: Divergence[]; playersLove: Divergence[] }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-xl font-semibold">Где критики и игроки расходятся</h2>
        <p className="text-sm text-muted-foreground">
          Разрыв считается между Metascore и Userscore × 10; учитываются игры, у которых не меньше 10 оценок игроков.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Column title="Критики хвалят, игроки нет" subtitle="Чем недовольны игроки" items={criticsLove} />
        <Column title="Игроки любят, критики нет" subtitle="Чем недовольны критики" items={playersLove} />
      </div>
    </section>
  )
}
