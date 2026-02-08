import { useState } from 'react'
import { presets } from '@/hooks/useDateRange'
import type { DateRange, Preset } from '@/hooks/useDateRange'
import { cn, toDateStr } from '@/lib/utils'

interface DateRangePickerProps {
  preset: Preset | null
  dateRange: DateRange
  onPresetChange: (preset: Preset) => void
  onDateChange: (range: DateRange) => void
}

export function DateRangePicker({ preset, dateRange, onPresetChange, onDateChange }: DateRangePickerProps) {
  const [showCustom, setShowCustom] = useState(false)
  const todayStr = toDateStr(new Date())

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {presets.map(p => (
          <button
            key={p.value}
            onClick={() => { onPresetChange(p.value); setShowCustom(false) }}
            className={cn(
              "px-3 py-1 text-xs rounded-md transition-colors",
              preset === p.value && !showCustom
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-accent"
            )}
          >
            {p.label}
          </button>
        ))}
        <button
          onClick={() => setShowCustom(v => !v)}
          className={cn(
            "px-3 py-1 text-xs rounded-md transition-colors",
            showCustom
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-secondary-foreground hover:bg-accent"
          )}
        >
          Custom
        </button>
      </div>
      {showCustom && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={dateRange.from ?? ''}
            max={dateRange.to ?? todayStr}
            onChange={e => onDateChange({ from: e.target.value || null, to: dateRange.to })}
            className="px-2 py-1 text-xs rounded-md border border-border bg-background"
          />
          <span className="text-xs text-muted-foreground">to</span>
          <input
            type="date"
            value={dateRange.to ?? ''}
            min={dateRange.from ?? undefined}
            max={todayStr}
            onChange={e => onDateChange({ from: dateRange.from, to: e.target.value || null })}
            className="px-2 py-1 text-xs rounded-md border border-border bg-background"
          />
        </div>
      )}
    </div>
  )
}
