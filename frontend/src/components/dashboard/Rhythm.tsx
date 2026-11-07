import { useMemo } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { RhythmDay } from '@/api/types'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { DataTable } from '@/components/dashboard/DataTable'
import { InfoTip } from '@/components/InfoTip'
import { decimal } from '@/lib/format'

interface Row extends RhythmDay {
  label: string // 07.11
}

interface TipProps {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: Row }>
}

const axisText = { fill: 'var(--viz-muted)', fontSize: 12 }
const axisLine = { stroke: 'var(--viz-axis)' }

function Tip({ active, payload, children }: TipProps & { children: (row: Row) => React.ReactNode }) {
  const row = active ? payload?.[0]?.payload : undefined
  if (!row) return null
  return (
    <div className="space-y-1 rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="text-xs text-muted-foreground">{row.date.split('-').reverse().join('.')}</p>
      {children(row)}
    </div>
  )
}

function LegendItem({ children, mark }: { children: string; mark: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2">
      {mark}
      {children}
    </span>
  )
}

export function Rhythm({
  days,
  coverage,
}: {
  days: RhythmDay[]
  coverage: { with_date: number; total: number }
}) {
  const data: Row[] = useMemo(
    () => days.map((d) => ({ ...d, label: `${d.date.slice(8, 10)}.${d.date.slice(5, 7)}` })),
    [days],
  )
  const lastScored = data.reduce((last, d, i) => (d.critics_avg7 !== null ? i : last), -1)
  const note =
    coverage.with_date === 0
      ? 'Дата релиза пока неизвестна ни у одной игры: она появится при ближайших обходах.'
      : `Дата релиза известна у ${coverage.with_date} из ${coverage.total} игр, остальные на графиках не учтены.`

  return (
    <section className="space-y-3">
      <h2 className="flex items-center justify-between gap-2 text-xl font-semibold">
        Ритм рынка
        <InfoTip>Игры по дате релиза за последние 30 дней. {note}</InfoTip>
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Сколько игр выходит" info="Релизов в день и среднее за скользящие 7 дней">
          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
            <LegendItem mark={<span className="size-2.5 rounded-sm" style={{ background: 'var(--viz-accent-soft)' }} />}>
              Релизов за день
            </LegendItem>
            <LegendItem mark={<span className="h-0.5 w-4" style={{ background: 'var(--viz-accent-deep)' }} />}>
              Среднее за 7 дней
            </LegendItem>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                <XAxis dataKey="label" tick={axisText} axisLine={axisLine} tickLine={false} interval="preserveStartEnd" minTickGap={24} />
                <YAxis allowDecimals={false} tick={axisText} axisLine={false} tickLine={false} width={32} />
                <Tooltip
                  cursor={{ stroke: 'var(--viz-axis)' }}
                  content={(props) => (
                    <Tip {...(props as unknown as TipProps)}>
                      {(row) => (
                        <>
                          <p>
                            Релизов <b>{row.games}</b>
                          </p>
                          <p>
                            Среднее за 7 дней <b>{decimal(row.games_avg7)}</b>
                          </p>
                        </>
                      )}
                    </Tip>
                  )}
                />
                <Bar dataKey="games" fill="var(--viz-accent-soft)" radius={[4, 4, 0, 0]} maxBarSize={14} isAnimationActive={false} />
                <Line
                  type="monotone"
                  dataKey="games_avg7"
                  stroke="var(--viz-accent-deep)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5, stroke: 'var(--card)', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Растёт ли качество новинок" info="Средний Metascore игр, вышедших за скользящие 7 дней">
          {lastScored < 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              Пока нет игр с оценкой критиков и известной датой релиза за этот период.
            </p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                  <XAxis dataKey="label" tick={axisText} axisLine={axisLine} tickLine={false} interval="preserveStartEnd" minTickGap={24} />
                  <YAxis
                    domain={['dataMin - 5', 'dataMax + 5']}
                    allowDecimals={false}
                    tickFormatter={(value: number) => String(Math.round(value))}
                    tick={axisText}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                  />
                  <Tooltip
                    cursor={{ stroke: 'var(--viz-axis)' }}
                    content={(props) => (
                      <Tip {...(props as unknown as TipProps)}>
                        {(row) => (
                          <>
                            <p>
                              Средний Metascore за 7 дней <b>{decimal(row.critics_avg7)}</b>
                            </p>
                            <p>
                              Игр в окне <b>{Math.round(row.games_avg7 * 7)}</b>
                            </p>
                          </>
                        )}
                      </Tip>
                    )}
                  />
                  <Line
                    type="monotone"
                    dataKey="critics_avg7"
                    stroke="var(--viz-accent)"
                    strokeWidth={2}
                    isAnimationActive={false}
                    dot={(props: { cx?: number; cy?: number; index?: number }) =>
                      props.index === lastScored && props.cx !== undefined && props.cy !== undefined ? (
                        <circle key="end" cx={props.cx} cy={props.cy} r={5} fill="var(--viz-accent)" stroke="var(--card)" strokeWidth={2} />
                      ) : (
                        <g key={props.index} />
                      )
                    }
                    activeDot={{ r: 5, stroke: 'var(--card)', strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>
      </div>
      <DataTable
        columns={[
          { key: 'date', label: 'Дата' },
          { key: 'games', label: 'Релизов', align: 'right' },
          { key: 'avg7', label: 'Среднее за 7 дней', align: 'right' },
          { key: 'critics', label: 'Metascore за день', align: 'right' },
          { key: 'critics7', label: 'Metascore за 7 дней', align: 'right' },
        ]}
        rows={days.map((d) => ({
          date: d.date.split('-').reverse().join('.'),
          games: d.games,
          avg7: decimal(d.games_avg7),
          critics: decimal(d.avg_critics),
          critics7: decimal(d.critics_avg7),
        }))}
      />
    </section>
  )
}
