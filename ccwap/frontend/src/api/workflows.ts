import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { workflowKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface UserTypeBreakdown {
  user_type: string
  sessions: number
  total_cost: number
  total_turns: number
}

export interface UserTypeTrend {
  date: string
  user_type: string
  sessions: number
  cost: number
}

export interface AgentTreeNode {
  session_id: string
  project_display: string
  user_type: string
  total_cost: number
  children: AgentTreeNode[]
}

export interface ToolSequence {
  sequence: string[]
  count: number
  pct: number
}

export interface WorkflowResponse {
  user_types: UserTypeBreakdown[]
  user_type_trend: UserTypeTrend[]
  agent_trees: AgentTreeNode[]
  tool_sequences: ToolSequence[]
}

export function useWorkflows(dateRange: DateRange) {
  return useQuery({
    queryKey: workflowKeys.data(dateRange),
    queryFn: () => apiFetch<WorkflowResponse>(
      `/workflows${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}
