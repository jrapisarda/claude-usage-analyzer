import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { heatmapKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface HeatmapCell {
  day: number
  hour: number
  value: number
}

export interface HeatmapResponse {
  cells: HeatmapCell[]
  metric: string
  max_value: number
}

export function useHeatmap(dateRange: DateRange, metric: string) {
  return useQuery({
    queryKey: heatmapKeys.data(dateRange, metric),
    queryFn: () => apiFetch<HeatmapResponse>(
      `/heatmap${buildQuery({ from: dateRange.from, to: dateRange.to, metric })}`
    ),
  })
}
