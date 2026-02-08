import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { costKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface CostSummary {
  total_cost: number
  avg_daily_cost: number
  cost_today: number
  cost_this_week: number
  cost_this_month: number
  projected_monthly: number
}

export interface CostByTokenType {
  input_cost: number
  output_cost: number
  cache_read_cost: number
  cache_write_cost: number
  total_cost: number
}

export interface CostByModel {
  model: string
  cost: number
  turns: number
  input_tokens: number
  output_tokens: number
  percentage: number
}

export interface CostTrendPoint {
  date: string
  cost: number
  cumulative_cost: number
}

export interface CostByProject {
  project_path: string
  project_display: string
  cost: number
  percentage: number
}

export interface CacheSavings {
  total_cache_read_tokens: number
  total_input_tokens: number
  cache_hit_rate: number
  estimated_savings: number
  cost_without_cache: number
  actual_cost: number
}

export interface SpendForecast {
  daily_avg: number
  projected_7d: number
  projected_14d: number
  projected_30d: number
  trend_direction: string
  confidence: number
}

export interface CostAnalysisData {
  summary: CostSummary
  by_token_type: CostByTokenType
  by_model: CostByModel[]
  trend: CostTrendPoint[]
  by_project: CostByProject[]
  cache_savings: CacheSavings
  forecast: SpendForecast
}

export function useCostAnalysis(dateRange: DateRange) {
  return useQuery({
    queryKey: costKeys.data(dateRange),
    queryFn: () => apiFetch<CostAnalysisData>(
      `/cost${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

// --- Phase 4 additions ---

export interface CostAnomaly {
  date: string
  cost: number
  is_anomaly: boolean
  threshold: number
}

export interface CumulativeCost {
  date: string
  daily_cost: number
  cumulative: number
}

export interface CacheSimulation {
  actual_cost: number
  actual_cache_rate: number
  simulated_cost: number
  simulated_cache_rate: number
  savings: number
}

export function useCostAnomalies(dateRange: DateRange) {
  return useQuery({
    queryKey: costKeys.anomalies(dateRange),
    queryFn: () => apiFetch<CostAnomaly[]>(
      `/cost/anomalies${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useCumulativeCost(dateRange: DateRange) {
  return useQuery({
    queryKey: costKeys.cumulative(dateRange),
    queryFn: () => apiFetch<CumulativeCost[]>(
      `/cost/cumulative${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useCacheSimulation(targetHitRate: number, dateRange: DateRange) {
  return useQuery({
    queryKey: costKeys.cacheSimulation(targetHitRate, dateRange),
    queryFn: () => apiFetch<CacheSimulation>(
      `/cost/cache-simulation${buildQuery({ target_hit_rate: targetHitRate, from: dateRange.from, to: dateRange.to })}`
    ),
  })
}
