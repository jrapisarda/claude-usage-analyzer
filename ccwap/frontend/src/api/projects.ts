import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { projectKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface ProjectData {
  project_path: string
  project_display: string
  sessions: number
  messages: number
  user_turns: number
  loc_written: number
  loc_delivered: number
  lines_added: number
  lines_deleted: number
  files_created: number
  files_edited: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  thinking_chars: number
  cost: number
  cost_per_kloc: number
  tokens_per_loc: number
  error_count: number
  error_rate: number
  tool_calls: number
  agent_spawns: number
  duration_seconds: number
  cache_hit_rate: number
  avg_turn_cost: number
}

interface ProjectsResponse {
  projects: ProjectData[]
  pagination: {
    page: number
    limit: number
    total_count: number
    total_pages: number
  }
}

export function useProjects(
  dateRange: DateRange,
  sort = 'cost',
  order = 'desc',
  page = 1,
  search?: string,
) {
  return useQuery({
    queryKey: projectKeys.list(dateRange, sort, order, page, search),
    queryFn: () => apiFetch<ProjectsResponse>(
      `/projects${buildQuery({ from: dateRange.from, to: dateRange.to, sort, order, page, search })}`
    ),
  })
}

export interface ProjectDetailResponse {
  project_display: string
  total_cost: number
  total_sessions: number
  total_loc: number
  cost_trend: { date: string; cost: number }[]
  languages: { language: string; loc_written: number }[]
  tools: { tool_name: string; count: number; success_rate: number }[]
  branches: { branch: string; sessions: number; cost: number }[]
  sessions: {
    session_id: string
    start_time: string
    total_cost: number
    turn_count: number
    loc_written: number
    model_default: string
  }[]
}

export function useProjectDetail(encodedPath: string, dateRange: DateRange) {
  return useQuery({
    queryKey: projectKeys.detail(encodedPath, dateRange),
    queryFn: () => apiFetch<ProjectDetailResponse>(
      `/projects/${encodedPath}/detail${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
    enabled: !!encodedPath,
  })
}
