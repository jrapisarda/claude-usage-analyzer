import { useState, useMemo } from 'react'
import { CalendarIcon } from 'lucide-react'
import type { DateRange as RDPDateRange } from 'react-day-picker'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'
import { presets } from '@/hooks/useDateRange'
import type { DateRange, Preset } from '@/hooks/useDateRange'

interface DateRangePickerProps {
  preset: Preset | null
  dateRange: DateRange
  onPresetChange: (preset: Preset) => void
  onDateChange: (range: DateRange) => void
}

function formatDateDisplay(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function getDisplayLabel(preset: Preset | null, dateRange: DateRange): string {
  if (preset) {
    const found = presets.find((p) => p.value === preset)
    if (found) return found.label
  }

  if (dateRange.from && dateRange.to) {
    return `${formatDateDisplay(dateRange.from)} - ${formatDateDisplay(dateRange.to)}`
  }
  if (dateRange.from) {
    return `${formatDateDisplay(dateRange.from)} - ...`
  }
  if (dateRange.to) {
    return `... - ${formatDateDisplay(dateRange.to)}`
  }
  return 'All Time'
}

// Quick presets for the popover
const quickPresets: { label: string; value: Preset }[] = [
  { label: '7d', value: 'last-7-days' },
  { label: '30d', value: 'last-30-days' },
  { label: '90d', value: 'last-14-days' },
  { label: 'All', value: 'all-time' },
]

export function DateRangePicker({
  preset,
  dateRange,
  onPresetChange,
  onDateChange,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false)

  const calendarRange: RDPDateRange | undefined = useMemo(() => {
    if (!dateRange.from && !dateRange.to) return undefined
    return {
      from: dateRange.from ? new Date(dateRange.from + 'T00:00:00') : undefined,
      to: dateRange.to ? new Date(dateRange.to + 'T00:00:00') : undefined,
    }
  }, [dateRange])

  function toDateStr(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  function handleCalendarSelect(range: RDPDateRange | undefined) {
    if (!range) {
      onDateChange({ from: null, to: null })
      return
    }
    onDateChange({
      from: range.from ? toDateStr(range.from) : null,
      to: range.to ? toDateStr(range.to) : null,
    })
  }

  function handlePresetClick(presetValue: Preset) {
    onPresetChange(presetValue)
    setOpen(false)
  }

  const displayLabel = getDisplayLabel(preset, dateRange)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn(
            'justify-start text-left font-normal',
            !dateRange.from && !dateRange.to && !preset && 'text-muted-foreground'
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          <span className="truncate">{displayLabel}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="flex flex-col sm:flex-row">
          <div className="border-b border-border p-3 sm:border-b-0 sm:border-r">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground px-2 mb-2">
                Presets
              </p>
              {presets.map((p) => (
                <button
                  key={p.value}
                  onClick={() => handlePresetClick(p.value)}
                  className={cn(
                    'w-full text-left px-3 py-1.5 text-sm rounded-md transition-colors',
                    preset === p.value
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent hover:text-accent-foreground'
                  )}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div className="p-3">
            <p className="text-xs font-medium text-muted-foreground px-2 mb-2">
              Custom Range
            </p>
            <Calendar
              mode="range"
              selected={calendarRange}
              onSelect={handleCalendarSelect}
              numberOfMonths={2}
              disabled={{ after: new Date() }}
            />
          </div>
        </div>
        <Separator />
        <div className="flex items-center justify-between p-3">
          <div className="flex items-center gap-1">
            {quickPresets.map((qp) => (
              <Button
                key={qp.value}
                variant={preset === qp.value ? 'default' : 'secondary'}
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => handlePresetClick(qp.value)}
              >
                {qp.label}
              </Button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-7"
            onClick={() => setOpen(false)}
          >
            Done
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
