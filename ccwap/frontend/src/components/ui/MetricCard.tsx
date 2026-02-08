import { cn } from '@/lib/utils'
import { DeltaBadge } from './DeltaBadge'

interface MetricCardProps {
  title: string
  value: string
  subtitle?: string
  trend?: 'up' | 'down' | 'neutral'
  delta?: number
  deltaLabel?: string
  isLowerBetter?: boolean
  className?: string
}

export function MetricCard({ title, value, subtitle, trend, delta, deltaLabel, isLowerBetter, className }: MetricCardProps) {
  return (
    <div className={cn(
      "rounded-lg border border-border bg-card p-4",
      className,
    )}>
      <p className="text-sm text-muted-foreground">{title}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <p className="text-2xl font-bold">
          {trend === 'up' && <span className="text-green-500 text-sm mr-1">&#9650;</span>}
          {trend === 'down' && <span className="text-red-500 text-sm mr-1">&#9660;</span>}
          {value}
        </p>
        {delta != null && deltaLabel && (
          <DeltaBadge value={delta} label={deltaLabel} isLowerBetter={isLowerBetter} />
        )}
      </div>
      {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
    </div>
  )
}
