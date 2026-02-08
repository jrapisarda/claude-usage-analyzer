import { Menu, Search } from 'lucide-react'
import { ThemeToggle } from '@/components/ThemeToggle'
import { DateRangePicker } from '@/components/composite/DateRangePicker'
import { useDateRange } from '@/hooks/useDateRange'
import { Button } from '@/components/ui/button'

interface TopBarProps {
  onCommandK?: () => void
  isMobile?: boolean
  onMobileMenuOpen?: () => void
}

export function TopBar({ onCommandK, isMobile, onMobileMenuOpen }: TopBarProps) {
  const { dateRange, preset, setPreset, setDateRange } = useDateRange()

  return (
    <header className="border-b border-border bg-card px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-2">
        {isMobile && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onMobileMenuOpen}
            aria-label="Open menu"
            className="shrink-0"
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}
        <DateRangePicker
          preset={preset}
          dateRange={dateRange}
          onPresetChange={setPreset}
          onDateChange={setDateRange}
        />
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onCommandK}
          className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground"
        >
          <Search className="h-3.5 w-3.5" />
          <span>Search</span>
          <kbd className="px-1.5 py-0.5 text-[10px] bg-muted rounded font-mono">Ctrl+K</kbd>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onCommandK}
          className="sm:hidden"
          aria-label="Search"
        >
          <Search className="h-4 w-4" />
        </Button>
        <ThemeToggle />
      </div>
    </header>
  )
}
