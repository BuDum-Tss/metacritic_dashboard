import { Popover } from '@base-ui/react/popover'
import { Info } from 'lucide-react'
import type { ReactNode } from 'react'

// An explanation behind an "i": it opens on hover, on focus and on a click or tap.
export function InfoTip({ children, label = 'Пояснение' }: { children: ReactNode; label?: string }) {
  return (
    <Popover.Root>
      <Popover.Trigger
        openOnHover
        delay={150}
        closeDelay={100}
        aria-label={label}
        className="inline-flex size-5 shrink-0 cursor-help items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <Info className="size-4" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={6} className="z-50">
          <Popover.Popup className="max-w-xs rounded-md border bg-popover px-3 py-2 text-sm font-normal leading-relaxed text-popover-foreground shadow-md">
            {children}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}
