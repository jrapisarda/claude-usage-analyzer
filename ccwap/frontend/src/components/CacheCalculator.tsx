import { useState } from 'react'
import { useCacheSimulation } from '@/api/cost'
import { formatCurrency, formatPercent } from '@/lib/utils'
import type { DateRange } from '@/hooks/useDateRange'

interface CacheCalculatorProps {
  dateRange: DateRange
}

export function CacheCalculator({ dateRange }: CacheCalculatorProps) {
  const [targetRate, setTargetRate] = useState(80)
  const { data, isLoading } = useCacheSimulation(targetRate / 100, dateRange)

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Cache What-If Calculator</h3>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-muted-foreground">Target Cache Hit Rate</span>
          <span className="font-mono text-sm">{targetRate}%</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={targetRate}
          onChange={e => setTargetRate(Number(e.target.value))}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-xs text-muted-foreground mt-1">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground">Calculating...</div>
      )}

      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <span className="text-xs text-muted-foreground">Actual Cost</span>
            <p className="font-mono text-lg">{formatCurrency(data.actual_cost)}</p>
            <span className="text-xs text-muted-foreground">
              Hit rate: {formatPercent(data.actual_cache_rate)}
            </span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">Simulated Cost</span>
            <p className="font-mono text-lg">{formatCurrency(data.simulated_cost)}</p>
            <span className="text-xs text-muted-foreground">
              Hit rate: {formatPercent(data.simulated_cache_rate)}
            </span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">Savings</span>
            <p className={`font-mono text-lg ${data.savings > 0 ? 'text-green-500' : data.savings < 0 ? 'text-red-500' : ''}`}>
              {formatCurrency(data.savings)}
            </p>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">Savings %</span>
            <p className={`font-mono text-lg ${data.savings > 0 ? 'text-green-500' : data.savings < 0 ? 'text-red-500' : ''}`}>
              {data.actual_cost > 0 ? formatPercent(data.savings / data.actual_cost) : '0.0%'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
