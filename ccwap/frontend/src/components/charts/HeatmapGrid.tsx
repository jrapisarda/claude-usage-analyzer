import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

export interface HeatmapDataPoint {
  row: number
  col: number
  value: number
}

interface HeatmapGridProps {
  data: HeatmapDataPoint[]
  maxValue: number
  rowLabels: string[]
  colLabels: string[]
  formatValue?: (value: number) => string
  formatTooltip?: (row: string, col: string, value: number) => string
  cellSize?: number
  className?: string
}

export function HeatmapGrid({
  data,
  maxValue,
  rowLabels,
  colLabels,
  formatValue,
  formatTooltip,
  cellSize = 20,
  className,
}: HeatmapGridProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null)

  const cellMap = useMemo(() => {
    const map = new Map<string, number>()
    for (const d of data) {
      map.set(`${d.row}-${d.col}`, d.value)
    }
    return map
  }, [data])

  return (
    <div className={cn("relative", className)}>
      <div
        className="inline-grid gap-px"
        style={{ gridTemplateColumns: `48px repeat(${colLabels.length}, ${cellSize}px)` }}
      >
        {/* Header row */}
        <div />
        {colLabels.map((label, i) => (
          <div key={i} className="text-[10px] text-muted-foreground text-center py-1 truncate">
            {label}
          </div>
        ))}

        {/* Data rows */}
        {rowLabels.map((rowLabel, ri) => (
          <div key={`row-${ri}`} className="contents">
            <div className="text-xs text-muted-foreground flex items-center pr-2">
              {rowLabel}
            </div>
            {colLabels.map((colLabel, ci) => {
              const value = cellMap.get(`${ri}-${ci}`) ?? 0
              const intensity = maxValue > 0 ? Math.round((value / maxValue) * 100) : 0
              return (
                <div
                  key={`${ri}-${ci}`}
                  className="rounded-sm cursor-pointer hover:ring-1 hover:ring-primary/50 transition-shadow"
                  style={{
                    width: cellSize,
                    height: cellSize,
                    backgroundColor: intensity > 0
                      ? `color-mix(in srgb, var(--color-chart-1) ${intensity}%, var(--color-muted) 20%)`
                      : 'var(--color-muted)',
                  }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect()
                    const text = formatTooltip
                      ? formatTooltip(rowLabel, colLabel, value)
                      : `${rowLabel} ${colLabel}: ${formatValue ? formatValue(value) : value}`
                    setTooltip({ x: rect.left + rect.width / 2, y: rect.top - 8, text })
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              )
            })}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-1 mt-3 text-xs text-muted-foreground">
        <span>Less</span>
        {[0, 25, 50, 75, 100].map(pct => (
          <div
            key={pct}
            className="w-3 h-3 rounded-sm"
            style={{
              backgroundColor: pct > 0
                ? `color-mix(in srgb, var(--color-chart-1) ${pct}%, var(--color-muted) 20%)`
                : 'var(--color-muted)',
            }}
          />
        ))}
        <span>More</span>
      </div>

      {/* Floating tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 px-2 py-1 text-xs text-popover-foreground bg-popover border border-border rounded shadow-md pointer-events-none"
          style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  )
}
