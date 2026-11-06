import { cn } from '@/lib/utils'
import type { Tone } from '@/lib/format'

const tones: Record<Tone, string> = {
  good: 'bg-green-600 text-white',
  mixed: 'bg-yellow-400 text-neutral-900',
  bad: 'bg-red-600 text-white',
  none: 'bg-muted text-muted-foreground',
}

interface Props {
  value: number | null
  tone: Tone
  title: string
  className?: string
}

export function ScoreBadge({ value, tone, title, className }: Props) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex h-7 min-w-9 items-center justify-center rounded px-1.5 text-sm font-bold tabular-nums',
        tones[tone],
        className,
      )}
    >
      {value ?? 'tbd'}
    </span>
  )
}
