import { t } from '@/i18n'
import type { DashboardTiles } from '@/api/types'
import { InfoTip } from '@/components/InfoTip'
import { Card, CardContent } from '@/components/ui/card'
import { decimal } from '@/lib/format'

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Card size="sm">
      <CardContent className="space-y-1">
        <p className="flex items-center justify-between gap-1 text-sm text-muted-foreground">
          {label}
          <InfoTip>{note}</InfoTip>
        </p>
        <p className="text-3xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  )
}

export function Tiles({ tiles }: { tiles: DashboardTiles }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Tile label={t('tiles.games')} value={String(tiles.games_total)} note={t('tiles.gamesNote')} />
      <Tile label={t('tiles.new')} value={String(tiles.new_7d)} note={t('tiles.newNote')} />
      <Tile
        label={t('tiles.hits')}
        value={tiles.hits_share === null ? '—' : `${tiles.hits_share}%`}
        note={t('tiles.hitsNote')}
      />
      <Tile
        label={t('tiles.gap')}
        value={decimal(tiles.avg_gap)}
        note={t('tiles.gapNote')}
      />
    </div>
  )
}
