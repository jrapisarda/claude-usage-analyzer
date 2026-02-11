import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { explorerKeys } from './keys'

export interface ExplorerRow {
  group: string
  split: string | null
  value: number
}

export interface ExplorerMetadata {
  metric: string
  group_by: string
  split_by: string | null
  total: number
  row_count: number
  groups: string[]
  splits: string[]
}

export interface ExplorerResponse {
  rows: ExplorerRow[]
  metadata: ExplorerMetadata
}

export interface FilterOption {
  value: string
  label: string
  count: number
}

export interface ExplorerFiltersResponse {
  projects: FilterOption[]
  models: FilterOption[]
  branches: FilterOption[]
  languages: FilterOption[]
}

export interface ExplorerDrilldownSession {
  session_id: string
  project: string
  first_timestamp: string | null
  user_type: string
  branch: string
  cc_version: string
  bucket_value: number
  total_cost: number
  turns: number
  tool_calls: number
  errors: number
}

export interface ExplorerDrilldownResponse {
  bucket: {
    metric: string
    group_by: string
    group_value: string
    split_by: string | null
    split_value: string | null
  }
  sessions: ExplorerDrilldownSession[]
  pagination: {
    page: number
    limit: number
    total_count: number
    total_pages: number
  }
}

export interface ExplorerParams {
  metric: string | null
  group_by: string | null
  split_by?: string | null
  from?: string | null
  to?: string | null
  projects?: string | null
  models?: string | null
  branches?: string | null
  languages?: string | null
}

export interface ExplorerDrilldownParams extends ExplorerParams {
  group_value: string | null
  split_value?: string | null
  page?: number
  limit?: number
}

export function useExplorer(params: ExplorerParams) {
  return useQuery({
    queryKey: explorerKeys.query(params),
    queryFn: () => apiFetch<ExplorerResponse>(
      `/explorer${buildQuery({
        metric: params.metric,
        group_by: params.group_by,
        split_by: params.split_by,
        from: params.from,
        to: params.to,
        projects: params.projects,
        models: params.models,
        branches: params.branches,
        languages: params.languages,
      })}`
    ),
    enabled: !!params.metric && !!params.group_by,
  })
}

export function useExplorerDrilldown(params: ExplorerDrilldownParams) {
  return useQuery({
    queryKey: explorerKeys.drilldown(params),
    queryFn: () => apiFetch<ExplorerDrilldownResponse>(
      `/explorer/drilldown${buildQuery({
        metric: params.metric,
        group_by: params.group_by,
        group_value: params.group_value,
        split_by: params.split_by,
        split_value: params.split_value,
        from: params.from,
        to: params.to,
        projects: params.projects,
        models: params.models,
        branches: params.branches,
        languages: params.languages,
        page: params.page ?? 1,
        limit: params.limit ?? 25,
      })}`
    ),
    enabled: !!params.metric
      && !!params.group_by
      && !!params.group_value
      && (!params.split_by || !!params.split_value),
  })
}

export function useExplorerFilters(from: string | null, to: string | null) {
  return useQuery({
    queryKey: explorerKeys.filters(from, to),
    queryFn: () => apiFetch<ExplorerFiltersResponse>(
      `/explorer/filters${buildQuery({ from, to })}`
    ),
  })
}
