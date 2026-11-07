import type { ReactNode } from 'react'

import { InfoTip } from '@/components/InfoTip'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

// A card around one block of the dashboard: the title names what is plotted, the "i" says how to read it.
export function ChartCard({
  title,
  info,
  action,
  children,
  className,
  contentClassName,
}: {
  title: string
  info?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CardTitle className="text-lg">{title}</CardTitle>
          <div className="ml-auto flex items-center gap-3">
            {action}
            {info && <InfoTip>{info}</InfoTip>}
          </div>
        </div>
      </CardHeader>
      <CardContent className={cn('space-y-3', contentClassName)}>{children}</CardContent>
    </Card>
  )
}
