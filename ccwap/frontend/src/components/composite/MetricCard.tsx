import type { ReactNode } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: ReactNode
  delta?: { value: number; label?: string }
  isLoading?: boolean
  className?: string
}

export function MetricCard({
  title,
  value,
  subtitle,
  icon,
  delta,
  isLoading,
  className,
}: MetricCardProps) {
  if (isLoading) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-4', className)}>
        <Skeleton className="h-4 w-24 mb-2" />
        <Skeleton className="h-8 w-16 mb-1" />
        <Skeleton className="h-3 w-20" />
      </div>
    )
  }

  return (
    <div className={cn('rounded-lg border border-border bg-card p-4', className)}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-muted-foreground">{title}</span>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="flex items-center gap-2 mt-1">
        {delta && (
          <span
            className={cn(
              'text-xs font-medium',
              delta.value >= 0 ? 'text-green-500' : 'text-red-500'
            )}
          >
            {delta.value >= 0 ? '+' : ''}
            {delta.value.toFixed(1)}%
            {delta.label && (
              <span className="text-muted-foreground ml-1">{delta.label}</span>
            )}
          </span>
        )}
        {subtitle && (
          <span className="text-xs text-muted-foreground">{subtitle}</span>
        )}
      </div>
    </div>
  )
}
