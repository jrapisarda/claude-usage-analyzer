import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { sessionKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

interface SessionListItem {
  session_id: string
  project_path: string
  project_display: string | null
  first_timestamp: string | null
  last_timestamp: string | null
  duration_seconds: number
  cost: number
  turns: number
  user_turns: number
  tool_calls: number
  errors: number
  is_agent: boolean
  cc_version: string | null
  git_branch: string | null
  model: string | null
}

interface SessionsResponse {
  sessions: SessionListItem[]
  pagination: {
    page: number
    limit: number
    total_count: number
    total_pages: number
  }
}

export interface ToolCallDetail {
  tool_name: string
  file_path: string | null
  success: boolean
  error_message: string | null
  error_category: string | null
  loc_written: number
  lines_added: number
  lines_deleted: number
  language: string | null
}

export interface ReplayTurn {
  uuid: string
  timestamp: string | null
  entry_type: string
  model: string | null
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  thinking_chars: number
  cost: number
  cumulative_cost: number
  stop_reason: string | null
  is_sidechain: boolean
  is_meta: boolean
  user_prompt_preview: string | null
  tool_calls: ToolCallDetail[]
}

export interface SessionReplayData {
  session_id: string
  project_path: string
  project_display: string | null
  first_timestamp: string | null
  last_timestamp: string | null
  duration_seconds: number
  cc_version: string | null
  git_branch: string | null
  is_agent: boolean
  total_cost: number
  total_turns: number
  total_user_turns: number
  total_tool_calls: number
  total_errors: number
  cost_by_model: Record<string, number>
  tool_distribution: Record<string, number>
  turns: ReplayTurn[]
}

export function useSessions(dateRange: DateRange, project?: string, page = 1) {
  return useQuery({
    queryKey: sessionKeys.list(dateRange, project, page),
    queryFn: () => apiFetch<SessionsResponse>(
      `/sessions${buildQuery({ from: dateRange.from, to: dateRange.to, project, page })}`
    ),
  })
}

export function useSessionReplay(sessionId: string) {
  return useQuery({
    queryKey: sessionKeys.replay(sessionId),
    queryFn: () => apiFetch<SessionReplayData>(`/sessions/${sessionId}/replay`),
    enabled: !!sessionId,
  })
}
