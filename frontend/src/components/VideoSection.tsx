import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { api } from '@/api/client'
import type { TranscriptStatus, Video, VideoKind } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatTimecode, videoKindLabels } from '@/lib/format'
import { cn } from '@/lib/utils'

type Tab = 'transcript' | 'summary'

const statusLabels: Record<TranscriptStatus, string> = {
  pending: 'в очереди',
  running: 'обрабатывается',
  done: 'готово',
  failed: 'ошибка',
}

// The video of a game with its transcript: the player on the left, the phrases with their time on the right.
export function VideoSection({ gameId, videos }: { gameId: number; videos: Video[] }) {
  const [kind, setKind] = useState<VideoKind>(videos[0].kind)
  const [tab, setTab] = useState<Tab>('transcript')
  const [chosen, setChosen] = useState<string | null>(null)
  const frame = useRef<HTMLIFrameElement>(null)
  const queryClient = useQueryClient()

  const shown = videos.find((video) => video.kind === kind) ?? videos[0]

  // the parts of a playlist are known after the first request; before it only the video found for the game
  const videoId = chosen ?? shown.video_id
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
  const unfinished = !data || data.videos.length === 0 || data.videos.some((v) => v.status !== 'done')

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

  const segments = data?.segments ?? null
  const failure = part?.status === 'failed' ? part.error : null

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

      <div className="flex gap-4 border-b text-sm">
        {(
          [
            ['transcript', 'Транскрипт'],
            ['summary', 'Резюме'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            aria-current={tab === value}
            className={cn(
              '-mb-px border-b-2 px-1 pb-2 font-medium',
              tab === value ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'summary' ? (
        <p className="py-10 text-center text-sm text-muted-foreground">Резюме по видео появится позже.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
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
            {parts.length > 1 && (
              <select
                value={videoId}
                onChange={(event) => setChosen(event.target.value)}
                aria-label="Часть плейлиста"
                className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
              >
                {parts.map((item) => (
                  <option key={item.video_id} value={item.video_id}>
                    {item.position + 1}. {item.title ?? item.video_id} — {statusLabels[item.status]}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex min-h-72 flex-col gap-2 md:aspect-video md:min-h-0">
            <div className="flex flex-wrap items-center gap-2">
              {unfinished && (
                <Button size="sm" disabled={running || start.isPending} onClick={() => start.mutate()}>
                  {running ? 'Идёт расшифровка…' : parts.length === 0 ? 'Получить транскрипт' : 'Доделать транскрипт'}
                </Button>
              )}
              {part?.status === 'done' && part.source && (
                <span className="text-xs text-muted-foreground">
                  {part.source === 'captions' ? 'субтитры YouTube' : 'распознавание речи'}
                </span>
              )}
              {parts.length > 1 && (
                <span className="text-xs text-muted-foreground">
                  готово {parts.filter((item) => item.status === 'done').length} из {parts.length}
                </span>
              )}
            </div>
            {start.isError && <p className="text-sm text-destructive">{start.error.message}</p>}

            <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border">
              {segments && segments.length > 0 ? (
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
              ) : (
                <p className="p-4 text-sm text-muted-foreground">
                  {failure
                    ? `Не получилось: ${failure}`
                    : running || part?.status === 'running' || part?.status === 'pending'
                      ? 'Расшифровка идёт, текст появится здесь.'
                      : parts.length === 0
                        ? 'Транскрипта пока нет. Нажмите кнопку, чтобы получить его: сначала берутся субтитры YouTube, а если их нет, речь распознаётся.'
                        : 'Для этого видео транскрипта пока нет. Нажмите кнопку, чтобы доделать.'}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
