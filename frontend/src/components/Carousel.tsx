import { t } from '@/i18n'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

import { useScroller } from '@/lib/useScroller'

import { cn } from '@/lib/utils'

export function ArrowButton({
  direction,
  onClick,
  className,
}: {
  direction: 'prev' | 'next'
  onClick: () => void
  className?: string
}) {
  const Icon = direction === 'prev' ? ChevronLeft : ChevronRight
  return (
    <button
      type="button"
      aria-label={direction === 'prev' ? t('common.back') : t('common.forward')}
      onClick={onClick}
      className={cn(
        'absolute top-1/2 z-10 flex size-9 -translate-y-1/2 items-center justify-center rounded-full bg-black/60 text-white shadow transition-colors hover:bg-black/80',
        direction === 'prev' ? 'left-2' : 'right-2',
        className,
      )}
    >
      <Icon className="size-5" />
    </button>
  )
}

export const hideScrollbar = '[scrollbar-width:none] [&::-webkit-scrollbar]:hidden'

// Several items in a row, scrolled by swiping or with the arrows.
export function Carousel({
  children,
  itemClassName = 'w-64 sm:w-72',
}: {
  children: ReactNode[]
  itemClassName?: string
}) {
  const { ref, canPrev, canNext, scrollPage } = useScroller()
  return (
    <div className="relative">
      <div
        ref={ref}
        className={cn('flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth pb-2', hideScrollbar)}
      >
        {children.map((child, i) => (
          <div key={i} className={cn('shrink-0 snap-start', itemClassName)}>
            {child}
          </div>
        ))}
      </div>
      {canPrev && <ArrowButton direction="prev" onClick={() => scrollPage(-1, 0.8)} />}
      {canNext && <ArrowButton direction="next" onClick={() => scrollPage(1, 0.8)} />}
    </div>
  )
}
