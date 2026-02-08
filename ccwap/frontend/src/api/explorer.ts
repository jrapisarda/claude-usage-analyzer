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

export function useExplorerFilters(from: string | null, to: string | null) {
  return useQuery({
    queryKey: explorerKeys.filters(from, to),
    queryFn: () => apiFetch<ExplorerFiltersResponse>(
      `/explorer/filters${buildQuery({ from, to })}`
    ),
  })
}
