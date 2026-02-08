import { cn } from '@/lib/utils'

interface DeltaBadgeProps {
  value: number
  label: string
  isLowerBetter?: boolean
  className?: string
}

export function DeltaBadge({ value, label, isLowerBetter = false, className }: DeltaBadgeProps) {
  const isPositive = value > 0
  const isGood = isLowerBetter ? !isPositive : isPositive

  return (
    <span className={cn(
      "text-xs font-mono inline-flex items-center",
      isGood ? "text-green-500" : "text-red-400",
      className,
    )}>
      {isPositive ? '+' : ''}{label}
    </span>
  )
}
