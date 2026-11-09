import { hasKey, t, type Key } from '@/i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, ApiError } from '@/api/client'
import type { Pipeline, PipelineStatus, SyncRun } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateTime, formatDuration } from '@/lib/format'

const FAST_POLL_MS = 2000
const SLOW_POLL_MS = 10000

const statusLabel = (status: SyncRun['status']) => t(`mon.status.${status}`)

function StatusBadge({ status }: { status: SyncRun['status'] }) {
  const variant = status === 'failed' ? 'destructive' : status === 'running' ? 'default' : 'secondary'
  return <Badge variant={variant}>{statusLabel(status)}</Badge>
}

function Progress({ run }: { run: SyncRun }) {
  const found = run.games_found ?? 0
  const done = (run.games_processed ?? 0) + (run.games_failed ?? 0)
  const percent = found > 0 ? Math.round((done / found) * 100) : 0
  return (
    <div className="space-y-1">
      <div className="h-2 w-full overflow-hidden rounded bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${percent}%` }} />
      </div>
      <p className="text-xs text-muted-foreground">
        {t('mon.progress', { done, found, percent })}
      </p>
    </div>
  )
}

// a label of the interface for a value that comes from the server; an unknown value is shown as it is
function label(prefix: string, value: string): string {
  const key = `${prefix}.${value}`
  return hasKey(key) ? t(key) : value
}

// the games a run worked on; the list grows while the run goes
function RunGames({ run }: { run: SyncRun }) {
  const games = useQuery({
    queryKey: ['sync', 'run-games', run.id],
    queryFn: () => api.runGames(run.id),
    refetchInterval: run.status === 'running' ? FAST_POLL_MS : false,
  })

  if (games.isPending) return <p className="text-sm text-muted-foreground">{t('mon.loading')}</p>
  if (games.isError) return <p className="text-sm text-destructive">{t('mon.loadError', { message: games.error.message })}</p>
  if (games.data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {run.status === 'running'
          ? t('mon.noGames')
          : t('mon.noRunGames')}
      </p>
    )
  }
  return (
    <div className="max-h-96 overflow-y-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('mon.colGame')}</TableHead>
            <TableHead>{t('mon.colOutcome')}</TableHead>
            <TableHead>{t('mon.colDetails')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {games.data.map((game, index) => (
            <TableRow key={index}>
              <TableCell>
                {game.game_id ? (
                  <Link to={`/games/${game.game_id}`} className="underline">
                    {game.title ?? game.slug}
                  </Link>
                ) : (
                  <span className="text-muted-foreground">{game.slug}</span>
                )}
              </TableCell>
              <TableCell>
                <Badge
                  variant={
                    game.outcome === 'failed' ? 'destructive' : game.outcome === 'retry' ? 'outline' : 'secondary'
                  }
                >
                  {label('mon.outcome', game.outcome)}
                </Badge>
              </TableCell>
              <TableCell className="whitespace-normal text-sm">
                {game.error ? (
                  <span className="text-destructive">{game.error}</span>
                ) : game.details ? (
                  Object.entries(game.details)
                    .map(([kind, result]) => `${label('mon.kind', kind)}: ${label('mon.result', result)}`)
                    .join(' · ')
                ) : (
                  '—'
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

const PIPELINES: {
  pipeline: Pipeline
  title: Key
  description: Key
  startLabel: Key
  offLabel?: Key
}[] = [
  {
    pipeline: 'crawl',
    title: 'mon.crawl.title',
    description: 'mon.crawl.description',
    startLabel: 'mon.crawl.start',
  },
  {
    pipeline: 'analysis',
    title: 'mon.analysis.title',
    description: 'mon.analysis.description',
    startLabel: 'mon.analysis.start',
    offLabel: 'mon.analysis.off',
  },
  {
    pipeline: 'videos',
    title: 'mon.videos.title',
    description: 'mon.videos.description',
    startLabel: 'mon.videos.start',
    offLabel: 'mon.videos.off',
  },
]

function PipelinePanel({
  pipeline,
  title,
  description,
  startLabel,
  offLabel,
  status,
}: {
  pipeline: Pipeline
  title: Key
  description: Key
  startLabel: Key
  offLabel?: Key
  status: PipelineStatus | undefined
}) {
  const queryClient = useQueryClient()
  const [openRun, setOpenRun] = useState<number | null>(null)
  // the list of runs is folded at first and can be opened; the choice is remembered for every pipeline
  const storageKey = `monitoring:${pipeline}:runs`
  const [runsOpen, setRunsOpen] = useState(() => {
    try {
      return localStorage.getItem(storageKey) === 'open'
    } catch {
      return false
    }
  })
  const toggleRuns = () => {
    const next = !runsOpen
    setRunsOpen(next)
    try {
      localStorage.setItem(storageKey, next ? 'open' : 'folded')
    } catch {
      // the choice is just not remembered
    }
  }
  const running = status?.running ?? false
  const off = status !== undefined && !status.enabled

  const runs = useQuery({
    queryKey: ['sync', 'runs', pipeline],
    queryFn: () => api.syncRuns(pipeline, 10),
    refetchInterval: running ? FAST_POLL_MS : SLOW_POLL_MS,
  })
  const start = useMutation({
    mutationFn: () => api.runSync(pipeline),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['sync'] }),
  })
  const alreadyRunning = start.error instanceof ApiError && start.error.status === 409

  const current = status?.current_run
  const last = status?.last_run

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold">{t(title)}</h2>
            {off && <Badge variant="outline">{offLabel ? t(offLabel) : t('mon.off')}</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">{t(description)}</p>
        </div>
        <Button onClick={() => start.mutate()} disabled={running || off || start.isPending}>
          {running ? t('mon.runningNow') : t(startLabel)}
        </Button>
      </div>

      {start.isError && !alreadyRunning && (
        <p className="text-sm text-destructive">{t('mon.startError', { message: start.error.message })}</p>
      )}
      {alreadyRunning && <p className="text-sm text-muted-foreground">{t('mon.alreadyRunning')}</p>}

      <div className="grid gap-4 md:grid-cols-3">
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">{t('mon.state')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-lg font-semibold">{off ? t('mon.stateOff') : running ? t('mon.stateWorking') : t('mon.stateWaiting')}</p>
            {current && <Progress run={current} />}
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">{t('mon.next')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{off ? '—' : formatDateTime(status?.next_run_at ?? null)}</p>
            <p className="text-xs text-muted-foreground">
              {t('mon.schedule', { hours: status?.interval_hours ?? '—', budget: status?.budget ?? '—' })}
            </p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">{t('mon.last')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {last ? (
              <>
                <StatusBadge status={last.status} />
                <p className="text-xs text-muted-foreground">
                  {t('mon.lastInfo', {
                    time: formatDateTime(last.started_at),
                    processed: last.games_processed ?? 0,
                    failed: last.games_failed ?? 0,
                  })}
                </p>
              </>
            ) : (
              <p className="text-lg font-semibold">—</p>
            )}
          </CardContent>
        </Card>
      </div>

      <button
        type="button"
        onClick={toggleRuns}
        aria-expanded={runsOpen}
        className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        {runsOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        {t('mon.runs')}{runs.data ? ` (${runs.data.length})` : ''}
      </button>
      {runsOpen && (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>#</TableHead>
            <TableHead>{t('mon.colStatus')}</TableHead>
            <TableHead>{t('mon.colRun')}</TableHead>
            <TableHead>{t('mon.colStart')}</TableHead>
            <TableHead>{t('mon.colDuration')}</TableHead>
            <TableHead>{t('mon.colFound')}</TableHead>
            <TableHead>{t('mon.colProcessed')}</TableHead>
            <TableHead>{t('mon.colErrors')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(runs.data ?? []).map((run) => {
            const open = openRun === run.id
            const toggle = () => setOpenRun(open ? null : run.id)
            return (
              <Fragment key={run.id}>
                <TableRow
                  className="cursor-pointer"
                  tabIndex={0}
                  aria-expanded={open}
                  onClick={toggle}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      toggle()
                    }
                  }}
                >
                  <TableCell>
                    <span className="mr-1 text-muted-foreground">{open ? '▾' : '▸'}</span>
                    {run.id}
                  </TableCell>
                  <TableCell title={run.error ?? undefined}>
                    <StatusBadge status={run.status} />
                  </TableCell>
                  <TableCell>{run.trigger === 'manual' ? t('mon.manual') : t('mon.scheduled')}</TableCell>
                  <TableCell>{formatDateTime(run.started_at)}</TableCell>
                  <TableCell>{formatDuration(run.started_at, run.finished_at)}</TableCell>
                  <TableCell>{run.games_found ?? '—'}</TableCell>
                  <TableCell>{run.games_processed ?? '—'}</TableCell>
                  <TableCell>{run.games_failed ?? '—'}</TableCell>
                </TableRow>
                {open && (
                  <TableRow>
                    <TableCell colSpan={8} className="bg-muted/30 whitespace-normal">
                      <RunGames run={run} />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            )
          })}
          {runs.data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={8} className="py-6 text-center text-muted-foreground">
                {t('mon.noRuns')}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      )}
    </section>
  )
}

export function MonitoringPage() {
  const status = useQuery({
    queryKey: ['sync', 'status'],
    queryFn: api.syncStatus,
    refetchInterval: (query) =>
      query.state.data && Object.values(query.state.data).some((pipeline) => pipeline.running)
        ? FAST_POLL_MS
        : SLOW_POLL_MS,
  })

  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-bold">{t('mon.title')}</h1>
      {status.isError && <p className="text-destructive">{t('mon.noServer', { message: status.error.message })}</p>}
      {PIPELINES.map((p) => (
        <PipelinePanel key={p.pipeline} {...p} status={status.data?.[p.pipeline]} />
      ))}
    </div>
  )
}
