import { metascoreTone, userscoreTone, type Tone } from '@/lib/format'
import { cn } from '@/lib/utils'

const tones: Record<Tone, string> = {
  good: 'bg-green-600 text-white',
  mixed: 'bg-yellow-400 text-neutral-900',
  bad: 'bg-red-600 text-white',
  none: 'bg-muted text-muted-foreground',
}

const sizes = {
  sm: 'size-8 text-sm',
  md: 'size-11 text-lg',
  lg: 'size-16 text-3xl',
}

interface Props {
  // critics' scores are rounded squares, players' scores are circles, as on Metacritic
  kind: 'critic' | 'user'
  value: number | null
  size?: keyof typeof sizes
  title?: string
  className?: string
}

export function ScoreBadge({ kind, value, size = 'sm', title, className }: Props) {
  const tone = kind === 'critic' ? metascoreTone(value) : userscoreTone(value)
  return (
    <span
      title={title ?? (kind === 'critic' ? 'Metascore' : 'Userscore')}
      className={cn(
        'inline-flex shrink-0 items-center justify-center font-bold tabular-nums',
        kind === 'critic' ? 'rounded-md' : 'rounded-full',
        sizes[size],
        value === null && 'text-xs',
        tones[tone],
        className,
      )}
    >
      {value ?? 'tbd'}
    </span>
  )
}
