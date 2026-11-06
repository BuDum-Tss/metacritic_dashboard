import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '@/api/client'
import type { SyncRun } from '@/api/types'
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

export function MonitoringPage() {
  const queryClient = useQueryClient()

  const status = useQuery({
    queryKey: ['sync', 'status'],
    queryFn: api.syncStatus,
    refetchInterval: (query) => (query.state.data?.running ? FAST_POLL_MS : SLOW_POLL_MS),
  })
  const running = status.data?.running ?? false
  const runs = useQuery({
    queryKey: ['sync', 'runs'],
    queryFn: () => api.syncRuns(20),
    refetchInterval: running ? FAST_POLL_MS : SLOW_POLL_MS,
  })

  const start = useMutation({
    mutationFn: api.runSync,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['sync'] }),
  })
  const alreadyRunning = start.error instanceof ApiError && start.error.status === 409

  const current = status.data?.current_run
  const last = status.data?.last_run

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Мониторинг</h1>
        <Button onClick={() => start.mutate()} disabled={running || start.isPending}>
          {running ? 'Цикл выполняется…' : 'Запустить обработку'}
        </Button>
      </div>

      {status.isError && <p className="text-destructive">Нет связи с сервером: {status.error.message}</p>}
      {start.isError && !alreadyRunning && (
        <p className="text-destructive">Не удалось запустить: {start.error.message}</p>
      )}
      {alreadyRunning && <p className="text-sm text-muted-foreground">Цикл уже выполняется.</p>}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Воркер</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-lg font-semibold">{running ? 'Работает' : 'Ожидает'}</p>
            {current && <Progress run={current} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Следующий запуск</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{formatDateTime(status.data?.next_run_at ?? null)}</p>
            <p className="text-xs text-muted-foreground">Интервал: {status.data?.interval_hours ?? '—'} ч</p>
          </CardContent>
        </Card>
        <Card>
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

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Журнал запусков</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Запуск</TableHead>
              <TableHead>Пачка</TableHead>
              <TableHead>Начало</TableHead>
              <TableHead>Длительность</TableHead>
              <TableHead>Найдено</TableHead>
              <TableHead>Обработано</TableHead>
              <TableHead>Ошибок</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(runs.data ?? []).map((run) => (
              <TableRow key={run.id}>
                <TableCell>{run.id}</TableCell>
                <TableCell title={run.error ?? undefined}>
                  <StatusBadge status={run.status} />
                </TableCell>
                <TableCell>{run.trigger === 'manual' ? 'Вручную' : 'По расписанию'}</TableCell>
                <TableCell>{run.batch_index}</TableCell>
                <TableCell>{formatDateTime(run.started_at)}</TableCell>
                <TableCell>{formatDuration(run.started_at, run.finished_at)}</TableCell>
                <TableCell>{run.games_found ?? '—'}</TableCell>
                <TableCell>{run.games_processed ?? '—'}</TableCell>
                <TableCell>{run.games_failed ?? '—'}</TableCell>
              </TableRow>
            ))}
            {runs.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                  Запусков ещё не было
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </section>
    </div>
  )
}
