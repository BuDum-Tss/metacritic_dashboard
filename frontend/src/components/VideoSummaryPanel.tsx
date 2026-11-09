import { hasKey, t, type Key } from '@/i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { ReactNode } from 'react'

import { api } from '@/api/client'
import type { Moment } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatTimecode } from '@/lib/format'
import { cn } from '@/lib/utils'

// the name of a topic of a moment; an unknown topic is shown as it is
const topicLabel = (topic: string) => (hasKey(`topic.${topic}`) ? t(`topic.${topic}` as Key) : topic)

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
                title={t('video.seekTo', { time: formatTimecode(seconds) })}
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
        aria-label={problem ? t('summary.problem') : t('summary.positive')}
      />
      <button
        type="button"
        onClick={() => onSeek(moment.start)}
        title={t('video.seekHere')}
        className="shrink-0 font-mono text-xs tabular-nums text-primary underline-offset-2 hover:underline"
      >
        {formatTimecode(moment.start)}
      </button>
      <span className="min-w-0">
        <span className="mr-1 text-xs text-muted-foreground">{topicLabel(moment.topic)}:</span>
        {moment.note}
        {moment.quote && <span className="mt-0.5 block text-xs italic text-muted-foreground">«{moment.quote}»</span>}
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
  if (!data) return <p className="p-4 text-sm text-muted-foreground">{t('summary.loading')}</p>
  const running = data.running || data.status === 'running' || data.status === 'pending'

  return (
    <div className="flex min-h-full flex-col gap-4 p-4">
      {/* a ready summary is not rebuilt from here: the button is for a missing or a failed one */}
      {!running && (!data.text || data.status === 'failed') && (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={start.isPending || !data.llm_enabled} onClick={() => start.mutate()}>
            {t('summary.build')}
          </Button>
          {!data.llm_enabled && <span className="text-xs text-muted-foreground">{t('summary.noModel')}</span>}
        </div>
      )}
      {running && (
        <div className="flex min-h-40 flex-1 flex-col items-center justify-center gap-3 text-sm text-muted-foreground" role="status">
          <LoaderCircle className="size-8 animate-spin text-primary" aria-hidden />
          {t('summary.building')}
        </div>
      )}
      {start.isError && <p className="text-sm text-destructive">{start.error.message}</p>}
      {data.status === 'failed' && data.error && <p className="text-sm text-destructive">{t('video.failed', { error: data.error })}</p>}

      {data.text && !running ? (
        <>
          <LinkedText text={data.text} onSeek={onSeek} />
          {data.moments.length > 0 && (
            <details className="rounded-lg border">
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{t('summary.moments', { n: data.moments.length })}</summary>
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
            {t('summary.empty')}
          </p>
        )
      )}
    </div>
  )
}
