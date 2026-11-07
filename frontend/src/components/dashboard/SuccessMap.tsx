import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { MapPoint } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { DataTable } from '@/components/dashboard/DataTable'
import { Button } from '@/components/ui/button'
import { compact, decimal } from '@/lib/format'

type Metric = 'critics' | 'users'

const METRICS = {
  critics: { label: 'Metascore критиков', threshold: 75, max: 100, ticks: [0, 25, 50, 75, 100] },
  users: { label: 'Userscore игроков', threshold: 7.5, max: 10, ticks: [0, 2.5, 5, 7.5, 10] },
}

interface Dot {
  id: number
  title: string
  x: number // the attention: player ratings
  y: number // the score on the chosen axis
  critics: number | null
  users: number | null
}

interface DotProps {
  cx?: number
  cy?: number
  payload?: Dot
  onOpen: (id: number) => void
}

// A point is 10px wide with a 2px ring in the colour of the card; its hit area is much larger.
function GameDot({ cx, cy, payload, onOpen }: DotProps) {
  if (cx === undefined || cy === undefined || !payload) return null
  const open = () => onOpen(payload.id)
  return (
    <g
      className="viz-dot cursor-pointer outline-none"
      role="link"
      tabIndex={0}
      aria-label={payload.title}
      onClick={open}
      onKeyDown={(event) => event.key === 'Enter' && open()}
    >
      <circle cx={cx} cy={cy} r={12} fill="transparent" />
      <circle cx={cx} cy={cy} r={5} fill="var(--viz-accent)" stroke="var(--card)" strokeWidth={2} />
    </g>
  )
}

interface TipProps {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: Dot }>
}

function MapTooltip({ active, payload }: TipProps) {
  const dot = active ? payload?.[0]?.payload : undefined
  if (!dot) return null
  return (
    <div className="space-y-1 rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="text-xs text-muted-foreground">{dot.title}</p>
      <p>
        Metascore <b>{dot.critics ?? '—'}</b> · Userscore <b>{decimal(dot.users)}</b>
      </p>
      <p>
        Оценок игроков <b>{dot.x.toLocaleString('ru-RU')}</b>
      </p>
    </div>
  )
}

const axisText = { fill: 'var(--viz-muted)', fontSize: 12 }

export function SuccessMap({ points, attentionMedian }: { points: MapPoint[]; attentionMedian: number | null }) {
  const navigate = useNavigate()
  const [metric, setMetric] = useState<Metric>('critics')
  const { threshold, max, ticks, label } = METRICS[metric]

  const dots: Dot[] = useMemo(
    () =>
      points
        .filter((p) => p[metric] !== null)
        .map((p) => ({ id: p.id, title: p.title, x: p.attention, y: p[metric] as number, critics: p.critics, users: p.users })),
    [points, metric],
  )

  const top = Math.max(10, ...dots.map((d) => d.x))
  const xMax = 10 ** Math.ceil(Math.log10(top * 1.01))
  const xTicks = Array.from({ length: Math.round(Math.log10(xMax)) + 1 }, (_, i) => 10 ** i)
  const median = attentionMedian !== null && attentionMedian >= 1 && attentionMedian <= xMax ? attentionMedian : null

  const zone = (value: string, position: 'insideTopLeft' | 'insideTopRight' | 'insideBottomLeft' | 'insideBottomRight') => ({
    value,
    position,
    fill: 'var(--viz-muted)',
    fontSize: 12,
  })

  return (
    <ChartCard
      title="Карта успеха"
      info={
        <div className="space-y-2">
          <p>Каждая точка — игра: по горизонтали внимание (число оценок игроков), по вертикали оценка. Клик по точке открывает игру.</p>
          <p>
            Линии: оценка {decimal(threshold, Number.isInteger(threshold) ? 0 : 1)} ({label}) и медианное внимание
            {median !== null ? `, ${median.toLocaleString('ru-RU')} оценок` : ''}.
          </p>
        </div>
      }
      action={
        <div className="flex gap-1" role="group" aria-label="Оценка на вертикальной оси">
          {(['critics', 'users'] as const).map((key) => (
            <Button key={key} size="sm" variant={metric === key ? 'default' : 'outline'} onClick={() => setMetric(key)}>
              {key === 'critics' ? 'Критики' : 'Игроки'}
            </Button>
          ))}
        </div>
      }
    >
      {dots.length < 3 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Пока слишком мало игр с оценками и числом оценок игроков, чтобы строить карту.
        </p>
      ) : (
        <>
          <div className="aspect-square w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 0 }}>
                <CartesianGrid stroke="var(--viz-grid)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  scale="log"
                  domain={[1, xMax]}
                  ticks={xTicks}
                  tickFormatter={(value: number) => compact(value)}
                  tick={axisText}
                  axisLine={{ stroke: 'var(--viz-axis)' }}
                  tickLine={false}
                  allowDataOverflow
                  label={{ value: 'Число оценок игроков (логарифмическая шкала)', position: 'insideBottom', offset: -14, ...axisText }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  domain={[0, max]}
                  ticks={ticks}
                  tickFormatter={(value: number) => decimal(value, Number.isInteger(value) ? 0 : 1)}
                  tick={axisText}
                  axisLine={{ stroke: 'var(--viz-axis)' }}
                  tickLine={false}
                  width={44}
                />
                {median !== null && (
                  <>
                    <ReferenceArea x1={1} x2={median} y1={threshold} y2={max} fill="none" stroke="none" label={zone('Скрытые жемчужины', 'insideTopLeft')} />
                    <ReferenceArea x1={median} x2={xMax} y1={threshold} y2={max} fill="none" stroke="none" label={zone('Хиты', 'insideTopRight')} />
                    <ReferenceArea x1={1} x2={median} y1={0} y2={threshold} fill="none" stroke="none" label={zone('Провалы', 'insideBottomLeft')} />
                    <ReferenceArea x1={median} x2={xMax} y1={0} y2={threshold} fill="none" stroke="none" label={zone('Громкие и спорные', 'insideBottomRight')} />
                    <ReferenceLine x={median} stroke="var(--viz-axis)" />
                  </>
                )}
                <ReferenceLine y={threshold} stroke="var(--viz-axis)" />
                <Tooltip cursor={false} content={(props) => <MapTooltip {...(props as unknown as TipProps)} />} />
                <Scatter
                  data={dots}
                  isAnimationActive={false}
                  shape={(props: unknown) => (
                    <GameDot {...(props as Omit<DotProps, 'onOpen'>)} onOpen={(id) => navigate(`/games/${id}`)} />
                  )}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <DataTable
            columns={[
              { key: 'title', label: 'Игра' },
              { key: 'critics', label: 'Metascore', align: 'right' },
              { key: 'users', label: 'Userscore', align: 'right' },
              { key: 'attention', label: 'Оценок игроков', align: 'right' },
            ]}
            rows={[...dots]
              .sort((a, b) => b.x - a.x)
              .map((d) => ({ title: d.title, critics: d.critics ?? '—', users: decimal(d.users), attention: d.x.toLocaleString('ru-RU') }))}
          />
        </>
      )}
    </ChartCard>
  )
}
