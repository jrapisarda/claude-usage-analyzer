import { ThemeToggle } from './ThemeToggle'
import { DateRangePicker } from './DateRangePicker'
import { useDateRange } from '@/hooks/useDateRange'
import { Search } from 'lucide-react'

interface TopBarProps {
  onCommandK?: () => void
}

export function TopBar({ onCommandK }: TopBarProps) {
  const { dateRange, preset, setPreset, setDateRange } = useDateRange()

  return (
    <header className="border-b border-border bg-card px-6 py-3 flex items-center justify-between gap-4">
      <DateRangePicker
        preset={preset}
        dateRange={dateRange}
        onPresetChange={setPreset}
        onDateChange={setDateRange}
      />
      <div className="flex items-center gap-2">
        <button
          onClick={onCommandK}
          className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground border border-border rounded-md hover:bg-accent/50 transition-colors"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden sm:inline px-1.5 py-0.5 text-[10px] bg-muted rounded font-mono">Ctrl+K</kbd>
        </button>
        <ThemeToggle />
      </div>
    </header>
  )
}
