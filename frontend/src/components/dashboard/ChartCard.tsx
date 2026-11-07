import type { ReactNode } from 'react'

import { InfoTip } from '@/components/InfoTip'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// A card around one block of the dashboard: the title names what is plotted, the "i" says how to read it.
export function ChartCard({
  title,
  info,
  action,
  children,
  className,
}: {
  title: string
  info?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            {title}
            {info && <InfoTip>{info}</InfoTip>}
          </CardTitle>
          {action}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  )
}
