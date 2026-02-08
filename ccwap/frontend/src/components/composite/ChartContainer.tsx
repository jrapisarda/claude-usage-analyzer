import type { ReactNode } from 'react'
import { ResponsiveContainer } from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface ChartContainerProps {
  title?: string
  height?: number
  isLoading?: boolean
  isEmpty?: boolean
  emptyMessage?: string
  children: ReactNode
  className?: string
}

export function ChartContainer({
  title,
  height = 256,
  isLoading,
  isEmpty,
  emptyMessage = 'No data available',
  children,
  className,
}: ChartContainerProps) {
  if (isLoading) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-4', className)}>
        {title && <Skeleton className="h-5 w-32 mb-4" />}
        <Skeleton className="w-full" style={{ height }} />
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-4', className)}>
        {title && <h3 className="text-sm font-medium text-muted-foreground mb-4">{title}</h3>}
        <div
          className="flex items-center justify-center text-muted-foreground text-sm"
          style={{ height }}
        >
          {emptyMessage}
        </div>
      </div>
    )
  }

  return (
    <div className={cn('rounded-lg border border-border bg-card p-4', className)}>
      {title && <h3 className="text-sm font-medium text-muted-foreground mb-4">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        {children as any}
      </ResponsiveContainer>
    </div>
  )
}
