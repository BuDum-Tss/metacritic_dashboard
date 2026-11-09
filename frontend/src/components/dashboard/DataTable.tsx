import { t } from '@/i18n'
import type { ReactNode } from 'react'

// The table twin of a chart: every value of the plot is readable here without hovering.
export function DataTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string; align?: 'left' | 'right' }[]
  rows: Record<string, ReactNode>[]
}) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">{t('dataTable.title')}</summary>
      <div className="mt-2 max-h-64 overflow-auto rounded-md border">
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={`px-3 py-2 font-medium ${column.align === 'right' ? 'text-right' : ''}`}>
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-3 py-1.5 ${column.align === 'right' ? 'text-right tabular-nums' : ''}`}
                  >
                    {row[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
