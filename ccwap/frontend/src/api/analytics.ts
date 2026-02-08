import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { analyticsKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface ThinkingAnalysis {
  total_thinking_chars: number
  avg_thinking_per_turn: number
  turns_with_thinking: number
  total_turns: number
  thinking_rate: number
  by_model: Record<string, unknown>[]
}

export interface TruncationAnalysis {
  total_turns: number
  by_stop_reason: Record<string, unknown>[]
}

export interface SidechainAnalysis {
  total_sidechains: number
  sidechain_rate: number
  by_project: Record<string, unknown>[]
}

export interface CacheTierAnalysis {
  ephemeral_5m_tokens: number
  ephemeral_1h_tokens: number
  standard_cache_tokens: number
  by_date: Record<string, unknown>[]
}

export interface BranchAnalytics {
  branches: Record<string, unknown>[]
}

export interface VersionImpact {
  versions: Record<string, unknown>[]
}

export interface SkillsAgents {
  total_agent_spawns: number
  total_skill_invocations: number
  agent_cost: number
  by_date: Record<string, unknown>[]
}

export interface AnalyticsData {
  thinking: ThinkingAnalysis
  truncation: TruncationAnalysis
  sidechains: SidechainAnalysis
  cache_tiers: CacheTierAnalysis
  branches: BranchAnalytics
  versions: VersionImpact
  skills_agents: SkillsAgents
}

export function useAnalytics(dateRange: DateRange) {
  return useQuery({
    queryKey: analyticsKeys.data(dateRange),
    queryFn: () => apiFetch<AnalyticsData>(
      `/analytics${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export interface ThinkingTrendPoint {
  date: string
  model: string
  thinking_chars: number
}

export interface CacheTrendPoint {
  date: string
  ephemeral_5m: number
  ephemeral_1h: number
  standard_cache: number
}

export function useThinkingTrend(dateRange: DateRange) {
  return useQuery({
    queryKey: analyticsKeys.thinkingTrend(dateRange),
    queryFn: () => apiFetch<ThinkingTrendPoint[]>(
      `/analytics/thinking-trend${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useCacheTrend(dateRange: DateRange) {
  return useQuery({
    queryKey: analyticsKeys.cacheTrend(dateRange),
    queryFn: () => apiFetch<CacheTrendPoint[]>(
      `/analytics/cache-trend${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}
