import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { advancedKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface ReliabilityData {
  summary: {
    total_tool_calls: number
    total_errors: number
    error_rate: number
    error_cost: number
  }
  heatmap: Array<{ tool_name: string; error_category: string; errors: number; error_cost: number }>
  pareto_tools: Array<{ label: string; count: number; cost: number }>
  pareto_commands: Array<{ label: string; count: number; cost: number }>
  pareto_languages: Array<{ label: string; count: number; cost: number }>
  by_branch: Array<{ branch: string; errors: number; cost: number }>
  top_failing_workflows: Array<{ workflow: string; from_tool: string; to_tool: string; branch: string; failures: number; cost: number }>
}

export interface BranchHealthData {
  branches: Array<{ branch: string; cost: number; errors: number; tool_calls: number; loc_written: number; cache_hit_rate: number }>
  trend: Array<{ date: string; branch: string; cost: number; errors: number; tool_calls: number; loc_written: number; cache_hit_rate: number }>
  anomalies: Array<{ date: string; branch: string; cost: number; zscore: number; reason: string }>
}

export interface PromptEfficiencyPoint {
  session_id: string
  project: string
  model: string
  branch: string
  cost: number
  thinking_chars: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  loc_written: number
  truncations: number
  token_mix_ratio: number
  output_per_cost: number
  efficiency_score: number
}

export interface PromptEfficiencyData {
  summary: {
    total_sessions: number
    sessions_with_thinking: number
    sessions_with_truncation: number
    high_cost_low_output_sessions: number
    avg_cost_per_loc: number
  }
  funnel: Array<{ stage: string; value: number }>
  by_stop_reason: Array<{ stop_reason: string; count: number; percentage: number }>
  scatter: PromptEfficiencyPoint[]
  outliers: PromptEfficiencyPoint[]
}

export interface WorkflowBottleneckData {
  transition_matrix: Array<{ from_tool: string; to_tool: string; count: number; failures: number; failure_rate: number }>
  retry_loops: Array<{ session_id: string; tool_name: string; retries: number; branch: string; user_type: string }>
  failure_handoffs: Array<{ parent_session_id: string; child_session_id: string; branch: string; handoff: string; errors: number; error_rate: number }>
  blocked_sessions: Array<{ session_id: string; project: string; branch: string; user_type: string; failures: number; retries: number; stall_score: number }>
}

export function useReliability(dateRange: DateRange) {
  return useQuery({
    queryKey: advancedKeys.reliability(dateRange),
    queryFn: () => apiFetch<ReliabilityData>(`/reliability${buildQuery({ from: dateRange.from, to: dateRange.to })}`),
  })
}

export function useBranchHealth(dateRange: DateRange, branches?: string | null) {
  return useQuery({
    queryKey: advancedKeys.branchHealth(dateRange, branches),
    queryFn: () => apiFetch<BranchHealthData>(
      `/branch-health${buildQuery({ from: dateRange.from, to: dateRange.to, branches })}`
    ),
  })
}

export function usePromptEfficiency(dateRange: DateRange) {
  return useQuery({
    queryKey: advancedKeys.promptEfficiency(dateRange),
    queryFn: () => apiFetch<PromptEfficiencyData>(
      `/prompt-efficiency${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useWorkflowBottlenecks(dateRange: DateRange) {
  return useQuery({
    queryKey: advancedKeys.workflowBottlenecks(dateRange),
    queryFn: () => apiFetch<WorkflowBottleneckData>(
      `/workflow-bottlenecks${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}
