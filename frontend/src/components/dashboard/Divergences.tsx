import { t } from '@/i18n'
import { Link } from 'react-router-dom'

import type { Divergence } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { InfoTip } from '@/components/InfoTip'
import { ScoreBadge } from '@/components/ScoreBadge'

function Row({ item }: { item: Divergence }) {
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
      </div>
      <p className="text-xs text-muted-foreground">
        {item.reason
          ? `${item.reason.source === 'users' ? t('divergences.usersComplain') : t('divergences.criticsComplain')}: ${item.reason.text}`
          : t('divergences.noSummary')}
      </p>
    </li>
  )
}

function Column({ title, subtitle, items }: { title: string; subtitle: string; items: Divergence[] }) {
  return (
    <ChartCard title={title} info={subtitle}>
      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">{t('divergences.empty')}</p>
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
      <h2 className="flex items-center justify-between gap-2 text-xl font-semibold">
        {t('divergences.title')}
        <InfoTip>{t('divergences.info')}</InfoTip>
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <Column title={t('divergences.criticsLove')} subtitle={t('divergences.criticsLoveSub')} items={criticsLove} />
        <Column title={t('divergences.playersLove')} subtitle={t('divergences.playersLoveSub')} items={playersLove} />
      </div>
    </section>
  )
}
