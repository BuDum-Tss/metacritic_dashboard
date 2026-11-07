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
      <Tile label="Игр в базе" value={String(tiles.games_total)} note="по которым собраны данные" />
      <Tile label="Новых за 7 дней" value={String(tiles.new_7d)} note="впервые попали в базу" />
      <Tile
        label="Доля хитов"
        value={tiles.hits_share === null ? '—' : `${tiles.hits_share}%`}
        note="критики от 75 и игроки от 7,5"
      />
      <Tile
        label="Разрыв критиков и игроков"
        value={decimal(tiles.avg_gap)}
        note="в среднем, баллов из 100"
      />
    </div>
  )
}
