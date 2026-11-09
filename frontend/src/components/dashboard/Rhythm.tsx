import { t } from '@/i18n'
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
      ? t('rhythm.noDates')
      : t('rhythm.someDates', { known: coverage.with_date, total: coverage.total })

  return (
    <section className="space-y-3">
      <h2 className="flex items-center justify-between gap-2 text-xl font-semibold">
        {t('rhythm.title')}
        <InfoTip>{t('rhythm.info', { note })}</InfoTip>
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title={t('rhythm.countTitle')} info={t('rhythm.countInfo')}>
          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
            <LegendItem mark={<span className="size-2.5 rounded-sm" style={{ background: 'var(--viz-accent-soft)' }} />}>
              {t('rhythm.perDay')}
            </LegendItem>
            <LegendItem mark={<span className="h-0.5 w-4" style={{ background: 'var(--viz-accent-deep)' }} />}>
              {t('rhythm.avg7')}
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
                            {t('rhythm.releases')} <b>{row.games}</b>
                          </p>
                          <p>
                            {t('rhythm.avg7')} <b>{decimal(row.games_avg7)}</b>
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

        <ChartCard title={t('rhythm.qualityTitle')} info={t('rhythm.qualityInfo')}>
          {lastScored < 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {t('rhythm.qualityEmpty')}
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
                              {t('rhythm.avgMeta7')} <b>{decimal(row.critics_avg7)}</b>
                            </p>
                            <p>
                              {t('rhythm.gamesInWindow')} <b>{Math.round(row.games_avg7 * 7)}</b>
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
          { key: 'date', label: t('rhythm.colDate') },
          { key: 'games', label: t('rhythm.releases'), align: 'right' },
          { key: 'avg7', label: t('rhythm.avg7'), align: 'right' },
          { key: 'critics', label: t('rhythm.colMeta'), align: 'right' },
          { key: 'critics7', label: t('rhythm.colMeta7'), align: 'right' },
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
