import { useMemo } from 'react'

interface DateRange {
  from?: string
  to?: string
}

export function useSmartStaleTime(dateRange?: DateRange): number {
  return useMemo(() => {
    if (!dateRange?.from && !dateRange?.to) return 5 * 60 * 1000 // 5min for all-time

    const today = new Date().toISOString().slice(0, 10)
    const to = dateRange.to || today

    if (to >= today) return 2 * 60 * 1000 // 2min if includes today
    return Infinity // historical data never changes
  }, [dateRange?.from, dateRange?.to])
}
