import { useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router'
import { toDateStr } from '@/lib/utils'

export interface DateRange {
  from: string | null
  to: string | null
}

export type Preset = 'today' | 'yesterday' | 'last-7-days' | 'last-14-days' | 'this-week' | 'last-week' | 'last-30-days' | 'this-month' | 'last-month' | 'all-time'

function getPresetRange(preset: Preset): DateRange {
  const now = new Date()
  const today = toDateStr(now)
  const yesterday = toDateStr(new Date(now.getTime() - 86400000))

  switch (preset) {
    case 'today':
      return { from: today, to: today }
    case 'yesterday':
      return { from: yesterday, to: yesterday }
    case 'last-7-days': {
      const from = new Date(now.getTime() - 6 * 86400000)
      return { from: toDateStr(from), to: today }
    }
    case 'last-14-days': {
      const from = new Date(now.getTime() - 13 * 86400000)
      return { from: toDateStr(from), to: today }
    }
    case 'this-week': {
      const day = now.getDay()
      const monday = new Date(now.getTime() - (day === 0 ? 6 : day - 1) * 86400000)
      return { from: toDateStr(monday), to: today }
    }
    case 'last-week': {
      const day = now.getDay()
      const thisMonday = new Date(now.getTime() - (day === 0 ? 6 : day - 1) * 86400000)
      const lastMonday = new Date(thisMonday.getTime() - 7 * 86400000)
      const lastSunday = new Date(thisMonday.getTime() - 86400000)
      return { from: toDateStr(lastMonday), to: toDateStr(lastSunday) }
    }
    case 'last-30-days': {
      const from = new Date(now.getTime() - 29 * 86400000)
      return { from: toDateStr(from), to: today }
    }
    case 'this-month':
      return { from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`, to: today }
    case 'last-month': {
      const firstThisMonth = new Date(now.getFullYear(), now.getMonth(), 1)
      const lastDayPrev = new Date(firstThisMonth.getTime() - 86400000)
      const firstPrev = new Date(lastDayPrev.getFullYear(), lastDayPrev.getMonth(), 1)
      return { from: toDateStr(firstPrev), to: toDateStr(lastDayPrev) }
    }
    case 'all-time':
      return { from: null, to: null }
  }
}

export function useDateRange() {
  const [searchParams, setSearchParams] = useSearchParams()
  const preset: Preset | null = (searchParams.get('preset') as Preset | null) || (
    !searchParams.get('from') && !searchParams.get('to') ? 'last-30-days' : null
  )

  const dateRange: DateRange = useMemo(() => {
    const from = searchParams.get('from')
    const to = searchParams.get('to')
    if (from || to) return { from, to }
    if (preset) return getPresetRange(preset)
    return getPresetRange('last-30-days')
  }, [searchParams, preset])

  const setDateRange = useCallback((range: DateRange) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('preset')
      if (range.from) next.set('from', range.from)
      else next.delete('from')
      if (range.to) next.set('to', range.to)
      else next.delete('to')
      return next
    })
  }, [setSearchParams])

  const setPreset = useCallback((p: Preset) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('preset', p)
      next.delete('from')
      next.delete('to')
      return next
    })
  }, [setSearchParams])

  const granularity = useMemo(() => {
    if (!dateRange.from || !dateRange.to) return 'daily' as const
    const from = new Date(dateRange.from + 'T00:00:00')
    const to = new Date(dateRange.to + 'T00:00:00')
    const days = Math.floor((to.getTime() - from.getTime()) / 86400000) + 1
    if (days > 180) return 'monthly' as const
    if (days > 60) return 'weekly' as const
    return 'daily' as const
  }, [dateRange])

  return { dateRange, setDateRange, preset, setPreset, granularity }
}

export const presets: { label: string; value: Preset }[] = [
  { label: 'Today', value: 'today' },
  { label: 'Yesterday', value: 'yesterday' },
  { label: 'Last 7 Days', value: 'last-7-days' },
  { label: 'Last 14 Days', value: 'last-14-days' },
  { label: 'This Week', value: 'this-week' },
  { label: 'Last Week', value: 'last-week' },
  { label: 'Last 30 Days', value: 'last-30-days' },
  { label: 'This Month', value: 'this-month' },
  { label: 'Last Month', value: 'last-month' },
  { label: 'All Time', value: 'all-time' },
]
