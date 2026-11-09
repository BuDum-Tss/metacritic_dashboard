import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, CircleDashed, Clock, LoaderCircle } from 'lucide-react'
import { useRef, useState } from 'react'

import { api } from '@/api/client'
import type { TranscriptStatus, Video, VideoKind } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatTimecode, videoKindLabels } from '@/lib/format'
import { cn } from '@/lib/utils'

type Tab = 'transcript' | 'summary'

const tabs: { value: Tab; label: string }[] = [
  { value: 'transcript', label: 'Транскрипт' },
  { value: 'summary', label: 'Резюме' },
]

// 'new': the video was never asked for
type PartStatus = TranscriptStatus | 'new'

const statusLabels: Record<PartStatus, string> = {
  new: 'не анализировалась',
  pending: 'в очереди',
  running: 'обрабатывается',
  done: 'проанализирована',
  failed: 'ошибка',
}

function StatusIcon({ status }: { status: PartStatus }) {
  const common = 'size-4 shrink-0'
  switch (status) {
    case 'done':
      return <CircleCheck className={cn(common, 'text-emerald-600')} aria-hidden />
    case 'running':
      return <LoaderCircle className={cn(common, 'animate-spin text-primary')} aria-hidden />
    case 'pending':
      return <Clock className={cn(common, 'text-muted-foreground')} aria-hidden />
    case 'failed':
      return <CircleAlert className={cn(common, 'text-destructive')} aria-hidden />
    default:
      return <CircleDashed className={cn(common, 'text-muted-foreground')} aria-hidden />
  }
}

// The video of a game. Until it is analysed only the player is shown, in the middle; after that the
// tabs stand left of it and the text (or the summary) right of it. The parts of a playlist are the
// chips above, each with the icon of its state.
export function VideoSection({ gameId, videos }: { gameId: number; videos: Video[] }) {
  const [kind, setKind] = useState<VideoKind>(videos[0].kind)
  const [tab, setTab] = useState<Tab>('transcript')
  const [chosen, setChosen] = useState<string | null>(null)
  const frame = useRef<HTMLIFrameElement>(null)
  const queryClient = useQueryClient()

  const shown = videos.find((video) => video.kind === kind) ?? videos[0]
  const videoId = chosen ?? shown.video_id

  // the parts of a playlist are known after the first request; before it only the video found for the game
  const transcript = useQuery({
    queryKey: ['transcripts', gameId, kind, videoId],
    placeholderData: keepPreviousData,
    queryFn: () => api.transcripts(gameId, kind, videoId),
    // while the task works the state is asked for again
    refetchInterval: (query) => {
      const data = query.state.data
      const busy = data && (data.running || data.videos.some((v) => v.status === 'pending' || v.status === 'running'))
      return busy ? 2500 : false
    },
  })
  const data = transcript.data
  const parts = data?.videos ?? []
  const part = parts.find((item) => item.video_id === videoId)
  const running = Boolean(data?.running)
  const allDone = parts.length > 0 && parts.every((item) => item.status === 'done')
  const analysed = part?.status === 'done'
  const segments = data?.segments ?? null

  const start = useMutation({
    mutationFn: () => api.requestTranscripts(gameId, kind),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transcripts', gameId, kind] }),
  })

  function seek(seconds: number) {
    const target = frame.current?.contentWindow
    if (!target) return
    for (const func of ['seekTo', 'playVideo']) {
      target.postMessage(
        JSON.stringify({ event: 'command', func, args: func === 'seekTo' ? [seconds, true] : [] }),
        '*',
      )
    }
  }

  function changeKind(next: VideoKind) {
    setKind(next)
    setChosen(null)
  }

  const chips: { video_id: string; label: string; title: string; status: PartStatus }[] =
    parts.length > 0
      ? parts.map((item) => ({
          video_id: item.video_id,
          label: kind === 'letsplay' ? `Серия ${item.position + 1}` : videoKindLabels[kind],
          title: item.title ?? item.video_id,
          status: item.status,
        }))
      : [
          {
            video_id: shown.video_id,
            label: kind === 'letsplay' ? 'Серия 1' : videoKindLabels[kind],
            title: shown.title ?? shown.video_id,
            status: 'new',
          },
        ]

  const player = (
    <div className="aspect-video w-full overflow-hidden rounded-lg bg-black">
      {/* the key makes another video load afresh; enablejsapi lets the page move the player */}
      <iframe
        key={videoId}
        ref={frame}
        src={`https://www.youtube-nocookie.com/embed/${videoId}?rel=0&enablejsapi=1`}
        title={`${videoKindLabels[kind]}: ${part?.title ?? shown.title ?? 'видео на YouTube'}`}
        allow="accelerometer; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
        className="h-full w-full"
      />
    </div>
  )

  let note: string | null = null
  if (!analysed) {
    if (part?.status === 'failed') note = `Не получилось: ${part.error ?? 'неизвестная ошибка'}`
    else if (part?.status === 'running' || part?.status === 'pending' || running) note = 'Идёт расшифровка…'
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Видео</h2>
        {videos.length > 1 && (
          <div className="flex gap-1">
            {videos.map((video) => (
              <Button
                key={video.kind}
                size="sm"
                variant={video.kind === kind ? 'default' : 'outline'}
                onClick={() => changeKind(video.kind)}
              >
                {videoKindLabels[video.kind]}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-start justify-between gap-3 border-b pb-3">
        <div className="flex min-w-0 gap-1 overflow-x-auto pb-1" role="tablist" aria-label="Серии">
          {chips.map((chip) => (
            <button
              key={chip.video_id}
              type="button"
              role="tab"
              aria-selected={chip.video_id === videoId}
              title={`${chip.title} — ${statusLabels[chip.status]}`}
              onClick={() => setChosen(chip.video_id)}
              className={cn(
                'inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-sm',
                chip.video_id === videoId ? 'border-foreground bg-muted font-medium' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <StatusIcon status={chip.status} />
              {chip.label}
            </button>
          ))}
        </div>
        <Button size="sm" className="shrink-0" disabled={running || allDone || start.isPending} onClick={() => start.mutate()}>
          {running ? 'Идёт расшифровка…' : allDone ? 'Всё проанализировано' : 'Проанализировать все'}
        </Button>
      </div>
      {start.isError && <p className="text-sm text-destructive">{start.error.message}</p>}

      {analysed ? (
        <div className="grid gap-4 md:grid-cols-2">
          {/* on a wide screen the text and its tabs are on the left, the player on the right */}
          <div className="md:order-2">{player}</div>

          <div className="flex min-h-72 flex-col gap-2 md:order-1 md:min-h-0">
            <div className="flex gap-4 border-b text-sm" role="tablist" aria-label="Раздел">
              {tabs.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  role="tab"
                  aria-selected={tab === item.value}
                  onClick={() => setTab(item.value)}
                  className={cn(
                    '-mb-px border-b-2 px-1 pb-2 font-medium',
                    tab === item.value
                      ? 'border-foreground text-foreground'
                      : 'border-transparent text-muted-foreground hover:text-foreground',
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="relative min-h-0 flex-1 rounded-lg border">
            <div className="max-h-96 overflow-y-auto md:absolute md:inset-0 md:max-h-none">
              {tab === 'summary' ? (
                <p className="p-4 text-sm text-muted-foreground">Резюме по видео появится позже.</p>
              ) : segments && segments.length > 0 ? (
                <>
                  <p className="border-b px-3 py-1.5 text-xs text-muted-foreground">
                    {part?.source === 'captions' ? 'Субтитры YouTube' : 'Распознавание речи'}
                  </p>
                  <ul className="divide-y text-sm">
                    {segments.map((segment, index) => (
                      <li key={index} className="flex gap-3 px-3 py-1.5">
                        <button
                          type="button"
                          onClick={() => seek(segment.start)}
                          title="Перемотать видео сюда"
                          className="shrink-0 font-mono text-xs tabular-nums text-primary underline-offset-2 hover:underline"
                        >
                          {formatTimecode(segment.start)}
                        </button>
                        <span className="min-w-0">
                          {segment.speaker !== null && (
                            <span className="mr-1 text-xs font-medium text-muted-foreground">[{segment.speaker}]</span>
                          )}
                          {segment.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="p-4 text-sm text-muted-foreground">Загружаю текст…</p>
              )}
            </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="mx-auto max-w-3xl space-y-2">
          {player}
          <p className={cn('text-center text-sm', part?.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>
            {note ?? 'Видео не анализировалось: нажмите «Проанализировать все», чтобы получить транскрипт.'}
          </p>
        </div>
      )}
    </section>
  )
}
