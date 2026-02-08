import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: ReactNode
  title?: string
  message: string
  action?: ReactNode
  className?: string
}

export function EmptyState({
  icon,
  title,
  message,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-12 text-center',
        className
      )}
    >
      {icon && <div className="text-muted-foreground mb-3">{icon}</div>}
      {title && <h3 className="text-lg font-medium mb-1">{title}</h3>}
      <p className="text-sm text-muted-foreground max-w-sm">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
