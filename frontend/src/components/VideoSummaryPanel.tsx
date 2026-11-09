import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { ReactNode } from 'react'

import { api } from '@/api/client'
import type { Moment } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatTimecode } from '@/lib/format'
import { cn } from '@/lib/utils'

const topicLabels: Record<string, string> = {
  controls: 'управление',
  navigation: 'ориентирование',
  event: 'событие',
  mechanics: 'механики',
  story: 'сюжет',
  visuals: 'графика',
  sound: 'звук',
  performance: 'оптимизация',
  overall: 'в целом',
  other: 'другое',
}

const LINK = /\[([^\]\n]+)\]\(t=(\d+)\)/g

// The text of the conclusion: paragraphs, and the words in [words](t=seconds) are links that move the player.
export function LinkedText({ text, onSeek }: { text: string; onSeek: (seconds: number) => void }) {
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {text
        .split(/\n\s*\n/)
        .filter((paragraph) => paragraph.trim())
        .map((paragraph, index) => {
          const parts: ReactNode[] = []
          let last = 0
          for (const match of paragraph.matchAll(LINK)) {
            parts.push(paragraph.slice(last, match.index))
            const seconds = Number(match[2])
            parts.push(
              <button
                key={`${index}-${match.index}`}
                type="button"
                onClick={() => onSeek(seconds)}
                title={`Перемотать на ${formatTimecode(seconds)}`}
                className="text-primary underline decoration-dotted underline-offset-2 hover:decoration-solid"
              >
                {match[1]}
              </button>,
            )
            last = match.index + match[0].length
          }
          parts.push(paragraph.slice(last))
          return <p key={index}>{parts}</p>
        })}
    </div>
  )
}

function MomentRow({ moment, onSeek }: { moment: Moment; onSeek: (seconds: number) => void }) {
  const problem = moment.type === 'problem'
  const Icon = problem ? ThumbsDown : ThumbsUp
  return (
    <li className="flex items-start gap-2 px-3 py-1.5">
      <Icon
        className={cn('mt-0.5 size-4 shrink-0', problem ? 'text-destructive' : 'text-emerald-600')}
        aria-label={problem ? 'Проблема' : 'Положительная реакция'}
      />
      <button
        type="button"
        onClick={() => onSeek(moment.start)}
        title="Перемотать видео сюда"
        className="shrink-0 font-mono text-xs tabular-nums text-primary underline-offset-2 hover:underline"
      >
        {formatTimecode(moment.start)}
      </button>
      <span className="min-w-0">
        <span className="mr-1 text-xs text-muted-foreground">{topicLabels[moment.topic] ?? moment.topic}:</span>
        {moment.note}
      </span>
    </li>
  )
}

// The «Резюме» tab of a video: the button, the conclusion with links to the time, the bright moments it rests on.
export function VideoSummaryPanel({
  gameId,
  videoId,
  onSeek,
}: {
  gameId: number
  videoId: string
  onSeek: (seconds: number) => void
}) {
  const queryClient = useQueryClient()
  const summary = useQuery({
    queryKey: ['video-summary', gameId, videoId],
    queryFn: () => api.videoSummary(gameId, videoId),
    // while the model works the state is asked for again
    refetchInterval: (query) => (query.state.data?.running || query.state.data?.status === 'running' || query.state.data?.status === 'pending' ? 3000 : false),
  })
  const start = useMutation({
    mutationFn: () => api.requestVideoSummary(gameId, videoId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['video-summary', gameId, videoId] }),
  })

  const data = summary.data
  if (!data) return <p className="p-4 text-sm text-muted-foreground">Загружаю…</p>
  const running = data.running || data.status === 'running' || data.status === 'pending'

  return (
    <div className="flex min-h-full flex-col gap-4 p-4">
      {/* a ready summary is not rebuilt from here: the button is for a missing or a failed one */}
      {!running && (!data.text || data.status === 'failed') && (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={start.isPending || !data.llm_enabled} onClick={() => start.mutate()}>
            Составить резюме
          </Button>
          {!data.llm_enabled && <span className="text-xs text-muted-foreground">Модель не настроена (нет LLM_API_KEY).</span>}
        </div>
      )}
      {running && (
        <div className="flex min-h-40 flex-1 flex-col items-center justify-center gap-3 text-sm text-muted-foreground" role="status">
          <LoaderCircle className="size-8 animate-spin text-primary" aria-hidden />
          Составляю резюме…
        </div>
      )}
      {start.isError && <p className="text-sm text-destructive">{start.error.message}</p>}
      {data.status === 'failed' && data.error && <p className="text-sm text-destructive">Не получилось: {data.error}</p>}

      {data.text && !running ? (
        <>
          <LinkedText text={data.text} onSeek={onSeek} />
          {data.moments.length > 0 && (
            <details className="rounded-lg border">
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium">Яркие моменты ({data.moments.length})</summary>
              <ul className="divide-y border-t text-sm">
                {data.moments.map((moment) => (
                  <MomentRow key={`${moment.start}-${moment.note}`} moment={moment} onSeek={onSeek} />
                ))}
              </ul>
            </details>
          )}
        </>
      ) : (
        !running &&
        data.status !== 'failed' && (
          <p className="text-sm text-muted-foreground">
            Резюме ещё нет. Модель найдёт в транскрипте места, где автор видео столкнулся с проблемой или отреагировал
            положительно, и напишет по ним заключение со ссылками на таймкоды.
          </p>
        )
      )}
    </div>
  )
}
