import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { modelKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface ModelMetrics {
  model: string
  sessions: number
  turns: number
  total_cost: number
  avg_turn_cost: number
  total_input_tokens: number
  total_output_tokens: number
  avg_thinking_chars: number
  loc_written: number
}

export interface ModelUsageTrend {
  date: string
  model: string
  count: number
}

export interface ModelScatterPoint {
  session_id: string
  model: string
  cost: number
  loc_written: number
}

export interface ModelComparisonResponse {
  models: ModelMetrics[]
  usage_trend: ModelUsageTrend[]
  scatter: ModelScatterPoint[]
}

export function useModelComparison(dateRange: DateRange) {
  return useQuery({
    queryKey: modelKeys.data(dateRange),
    queryFn: () => apiFetch<ModelComparisonResponse>(
      `/models${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}
