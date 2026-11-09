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

const statusLabels: Record<SyncRun['status'], string> = {
  running: 'Выполняется',
  success: 'Успешно',
  failed: 'Ошибка',
}

function StatusBadge({ status }: { status: SyncRun['status'] }) {
  const variant = status === 'failed' ? 'destructive' : status === 'running' ? 'default' : 'secondary'
  return <Badge variant={variant}>{statusLabels[status]}</Badge>
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
        {done} из {found} игр ({percent}%)
      </p>
    </div>
  )
}

const outcomeLabels: Record<string, string> = {
  new: 'Новая',
  revisited: 'Обновлена',
  summarized: 'Резюме построено',
  found: 'Видео найдены',
  none: 'Ничего не найдено',
  checked: 'Без изменений',
  retry: 'Повтор позже',
  failed: 'Ошибка',
}

const kindLabels: Record<string, string> = { critics: 'критики', users: 'игроки', letsplay: 'летсплей', review: 'обзор' }

const resultLabels: Record<string, string> = {
  created: 'резюме построено',
  same_sample: 'выборка прежняя',
  too_few: 'мало отзывов в выборке',
  model_unavailable: 'модель недоступна',
  bad_answer: 'неразборчивый ответ модели',
  video: 'видео',
  playlist: 'плейлист (показано первое видео)',
  none: 'не найдено',
}

// the games a run worked on; the list grows while the run goes
function RunGames({ run }: { run: SyncRun }) {
  const games = useQuery({
    queryKey: ['sync', 'run-games', run.id],
    queryFn: () => api.runGames(run.id),
    refetchInterval: run.status === 'running' ? FAST_POLL_MS : false,
  })

  if (games.isPending) return <p className="text-sm text-muted-foreground">Загрузка…</p>
  if (games.isError) return <p className="text-sm text-destructive">Не удалось загрузить: {games.error.message}</p>
  if (games.data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {run.status === 'running'
          ? 'Пока ни одной игры.'
          : 'Нет данных об играх этого запуска: он сделан до появления журнала игр или обрабатывать было нечего.'}
      </p>
    )
  }
  return (
    <div className="max-h-96 overflow-y-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Игра</TableHead>
            <TableHead>Итог</TableHead>
            <TableHead>Подробности</TableHead>
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
                  {outcomeLabels[game.outcome] ?? game.outcome}
                </Badge>
              </TableCell>
              <TableCell className="whitespace-normal text-sm">
                {game.error ? (
                  <span className="text-destructive">{game.error}</span>
                ) : game.details ? (
                  Object.entries(game.details)
                    .map(([kind, result]) => `${kindLabels[kind] ?? kind}: ${resultLabels[result] ?? result}`)
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
  title: string
  description: string
  startLabel: string
  offLabel?: string
}[] = [
  {
    pipeline: 'crawl',
    title: 'Обход',
    description: 'Находит новые игры и обновляет известные: страницы игр, оценки по платформам.',
    startLabel: 'Запустить обход',
  },
  {
    pipeline: 'analysis',
    title: 'Анализ отзывов',
    description: 'Читает отзывы и строит резюме ИИ для игр, у которых изменилось число отзывов.',
    startLabel: 'Запустить анализ',
    offLabel: 'ИИ не настроен',
  },
  {
    pipeline: 'videos',
    title: 'Видео YouTube',
    description: 'Ищет для игр самый популярный летсплей и обзор на YouTube; многосерийный летсплей сохраняет плейлистом.',
    startLabel: 'Запустить поиск видео',
    offLabel: 'YouTube не настроен',
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
  title: string
  description: string
  startLabel: string
  offLabel?: string
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
            <h2 className="text-xl font-semibold">{title}</h2>
            {off && <Badge variant="outline">{offLabel ?? 'Выключен'}</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <Button onClick={() => start.mutate()} disabled={running || off || start.isPending}>
          {running ? 'Выполняется…' : startLabel}
        </Button>
      </div>

      {start.isError && !alreadyRunning && (
        <p className="text-sm text-destructive">Не удалось запустить: {start.error.message}</p>
      )}
      {alreadyRunning && <p className="text-sm text-muted-foreground">Уже выполняется.</p>}

      <div className="grid gap-4 md:grid-cols-3">
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Состояние</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-lg font-semibold">{off ? 'Выключен' : running ? 'Работает' : 'Ожидает'}</p>
            {current && <Progress run={current} />}
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Следующий запуск</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{off ? '—' : formatDateTime(status?.next_run_at ?? null)}</p>
            <p className="text-xs text-muted-foreground">
              Раз в {status?.interval_hours ?? '—'} ч · до {status?.budget ?? '—'} игр за запуск
            </p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Последний запуск</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {last ? (
              <>
                <StatusBadge status={last.status} />
                <p className="text-xs text-muted-foreground">
                  {formatDateTime(last.started_at)} · обработано {last.games_processed ?? 0}, ошибок{' '}
                  {last.games_failed ?? 0}
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
        Запуски{runs.data ? ` (${runs.data.length})` : ''}
      </button>
      {runsOpen && (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>#</TableHead>
            <TableHead>Статус</TableHead>
            <TableHead>Запуск</TableHead>
            <TableHead>Начало</TableHead>
            <TableHead>Длительность</TableHead>
            <TableHead>Выбрано</TableHead>
            <TableHead>Обработано</TableHead>
            <TableHead>Ошибок</TableHead>
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
                  <TableCell>{run.trigger === 'manual' ? 'Вручную' : 'По расписанию'}</TableCell>
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
                Запусков ещё не было
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
      <h1 className="text-2xl font-bold">Мониторинг</h1>
      {status.isError && <p className="text-destructive">Нет связи с сервером: {status.error.message}</p>}
      {PIPELINES.map((p) => (
        <PipelinePanel key={p.pipeline} {...p} status={status.data?.[p.pipeline]} />
      ))}
    </div>
  )
}
