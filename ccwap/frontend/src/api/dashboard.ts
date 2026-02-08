import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { dashboardKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

interface DashboardData {
  vitals: {
    sessions: number
    cost: number
    loc_written: number
    error_rate: number
    user_turns: number
    messages: number
    input_tokens: number
    output_tokens: number
  }
  sparkline_7d: { date: string; value: number }[]
  top_projects: {
    project_path: string
    project_display: string
    sessions: number
    cost: number
    loc_written: number
    error_rate: number
    last_session: string | null
  }[]
  cost_trend: { date: string; cost: number; sessions: number; messages: number }[]
  recent_sessions: {
    session_id: string
    project_display: string | null
    first_timestamp: string | null
    duration_seconds: number
    cost: number
    turns: number
    model: string | null
    is_agent: boolean
  }[]
}

export function useDashboard(dateRange: DateRange) {
  return useQuery({
    queryKey: dashboardKeys.data(dateRange),
    queryFn: () => apiFetch<DashboardData>(
      `/dashboard${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export interface PeriodDelta {
  metric: string
  current: number
  previous: number
  delta: number
  pct_change: number
}

export interface ActivityDay {
  date: string
  sessions: number
  cost: number
}

export function useDashboardDeltas(dateRange: DateRange) {
  return useQuery({
    queryKey: dashboardKeys.deltas(dateRange),
    queryFn: () => apiFetch<PeriodDelta[]>(
      `/dashboard/deltas${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
    enabled: !!dateRange.from && !!dateRange.to,
  })
}

export function useActivityCalendar(days: number = 90) {
  return useQuery({
    queryKey: dashboardKeys.activityCalendar(days),
    queryFn: () => apiFetch<ActivityDay[]>(
      `/dashboard/activity-calendar${buildQuery({ days })}`
    ),
  })
}
