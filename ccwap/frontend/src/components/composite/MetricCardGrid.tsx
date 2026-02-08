import type { ReactNode } from 'react'
import { MetricCard } from './MetricCard'
import { cn } from '@/lib/utils'

interface MetricCardGridProps {
  children?: ReactNode
  skeleton?: boolean
  count?: number
  className?: string
}

export function MetricCardGrid({
  children,
  skeleton,
  count = 4,
  className,
}: MetricCardGridProps) {
  if (skeleton) {
    return (
      <div className={cn('grid grid-cols-2 lg:grid-cols-4 gap-4', className)}>
        {Array.from({ length: count }).map((_, i) => (
          <MetricCard key={i} title="" value="" isLoading />
        ))}
      </div>
    )
  }

  return (
    <div className={cn('grid grid-cols-2 lg:grid-cols-4 gap-4', className)}>
      {children}
    </div>
  )
}
