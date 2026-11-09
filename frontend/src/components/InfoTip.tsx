import { t } from '@/i18n'
import { Popover } from '@base-ui/react/popover'
import { Info } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'

// An explanation behind an "i": with a mouse it shows while the pointer is on the icon and goes away
// when the pointer leaves (a click does not pin it); with the keyboard it follows the focus;
// on a touch screen a tap opens it and a tap elsewhere closes it.
export function InfoTip({ children, label = t('common.explanation') }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false)
  const mouse = useRef(false)

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next, details) => {
        // with a mouse the hover decides, so a click on the icon must not close or pin the hint
        if (mouse.current && details.reason === 'trigger-press') return
        setOpen(next)
      }}
    >
      <Popover.Trigger
        aria-label={label}
        onPointerEnter={(e) => {
          mouse.current = e.pointerType === 'mouse'
          if (mouse.current) setOpen(true)
        }}
        onPointerLeave={(e) => {
          if (e.pointerType === 'mouse') setOpen(false)
        }}
        className="inline-flex size-5 shrink-0 cursor-help items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <Info className="size-4" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={6} className="z-50">
          <Popover.Popup className="pointer-events-none max-w-xs rounded-md border bg-popover px-3 py-2 text-sm font-normal leading-relaxed text-popover-foreground shadow-md">
            {children}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}
