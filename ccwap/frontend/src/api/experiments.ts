import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { experimentKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface ExperimentTag {
  tag_name: string
  session_count: number
  created_at: string | null
}

export interface ComparisonMetric {
  metric_name: string
  tag_a_value: number
  tag_b_value: number
  absolute_delta: number
  percentage_delta: number
  is_improvement: boolean
}

export interface ComparisonData {
  tag_a: string
  tag_b: string
  tag_a_sessions: number
  tag_b_sessions: number
  metrics: ComparisonMetric[]
}

export interface TagCreatePayload {
  tag_name: string
  session_ids?: string[]
  date_from?: string
  date_to?: string
  project_path?: string
}

export function useTags() {
  return useQuery({
    queryKey: experimentKeys.tags,
    queryFn: () => apiFetch<{ tags: ExperimentTag[] }>('/experiments/tags'),
  })
}

export function useTagComparison(tagA: string, tagB: string) {
  return useQuery({
    queryKey: experimentKeys.compare(tagA, tagB),
    queryFn: () => apiFetch<ComparisonData>(
      `/experiments/compare${buildQuery({ tag_a: tagA, tag_b: tagB })}`
    ),
    enabled: !!tagA && !!tagB,
  })
}

export function useCreateTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: TagCreatePayload) =>
      apiFetch('/experiments/tags', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: experimentKeys.tags }),
  })
}

export function useDeleteTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (tagName: string) =>
      apiFetch(`/experiments/tags/${encodeURIComponent(tagName)}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: experimentKeys.tags }),
  })
}

export interface TagComparison {
  tag_name: string
  sessions: number
  cost: number
  loc: number
  turns: number
  error_rate: number
}

export interface TagComparisonMultiResponse {
  tags: TagComparison[]
}

export interface TagSession {
  session_id: string
  project_display: string
  start_time: string
  total_cost: number
  turn_count: number
  model_default: string
}

export interface TagSessionsResponse {
  sessions: TagSession[]
}

export function useCompareTagsMulti(tags: string[], dateRange: DateRange) {
  return useQuery({
    queryKey: experimentKeys.compareMulti(tags),
    queryFn: () => apiFetch<TagComparisonMultiResponse>(
      `/experiments/compare-multi${buildQuery({ tags: tags.join(','), from: dateRange.from, to: dateRange.to })}`
    ),
    enabled: tags.length >= 2,
  })
}

export function useTagSessions(tagName: string, dateRange: DateRange) {
  return useQuery({
    queryKey: experimentKeys.tagSessions(tagName),
    queryFn: () => apiFetch<TagSessionsResponse>(
      `/experiments/tags/${encodeURIComponent(tagName)}/sessions${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
    enabled: !!tagName,
  })
}
