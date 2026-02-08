import { useState, useEffect, useRef } from 'react'
import { formatCurrency } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface CostTickerProps {
  targetCost: number
  className?: string
}

export function CostTicker({ targetCost, className }: CostTickerProps) {
  const [displayCost, setDisplayCost] = useState(targetCost)
  const rafRef = useRef<number>(undefined)
  const targetRef = useRef(targetCost)
  targetRef.current = targetCost

  useEffect(() => {
    let currentDisplay = displayCost
    const animate = () => {
      const diff = targetRef.current - currentDisplay
      if (Math.abs(diff) < 0.00005) {
        currentDisplay = targetRef.current
      } else {
        currentDisplay += diff * 0.1
      }
      setDisplayCost(currentDisplay)
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return (
    <span className={cn("font-mono tabular-nums text-2xl", className)}>
      {formatCurrency(displayCost)}
    </span>
  )
}
