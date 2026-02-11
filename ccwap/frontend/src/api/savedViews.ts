import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { savedViewKeys } from './keys'

export interface SavedView {
  id: number
  name: string
  page: string
  filters: Record<string, unknown>
  created_at: string | null
}

export interface AlertRule {
  id: number
  name: string
  page: string
  metric: string
  operator: string
  threshold: number
  filters: Record<string, unknown>
  enabled: boolean
  created_at: string | null
}

export interface AlertEvaluation {
  rule_id: number
  name: string
  page: string
  metric: string
  operator: string
  threshold: number
  current_value: number
  triggered: boolean
}

export function useSavedViews(page: string) {
  return useQuery({
    queryKey: savedViewKeys.views(page),
    queryFn: () => apiFetch<{ views: SavedView[] }>(`/saved-views${buildQuery({ page })}`),
  })
}

export function useCreateSavedView(page: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { name: string; filters: Record<string, unknown> }) =>
      apiFetch<SavedView>('/saved-views', {
        method: 'POST',
        body: JSON.stringify({ ...payload, page }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: savedViewKeys.views(page) })
    },
  })
}

export function useDeleteSavedView(page: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch<{ deleted: number }>(`/saved-views/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: savedViewKeys.views(page) })
    },
  })
}

export function useAlertRules(page?: string) {
  return useQuery({
    queryKey: savedViewKeys.alerts(page ?? null),
    queryFn: () => apiFetch<{ rules: AlertRule[] }>(`/alert-rules${buildQuery({ page })}`),
  })
}

export function useCreateAlertRule(page: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      name: string
      metric: string
      operator: string
      threshold: number
      filters: Record<string, unknown>
      enabled?: boolean
    }) =>
      apiFetch<AlertRule>('/alert-rules', {
        method: 'POST',
        body: JSON.stringify({
          ...payload,
          page,
          enabled: payload.enabled ?? true,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: savedViewKeys.alerts(page) })
    },
  })
}

export function useDeleteAlertRule(page: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch<{ deleted: number }>(`/alert-rules/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: savedViewKeys.alerts(page) })
    },
  })
}

export function useAlertEvaluations(page: string, from: string | null, to: string | null) {
  return useQuery({
    queryKey: savedViewKeys.alertEval(page, from, to),
    queryFn: () =>
      apiFetch<{ evaluations: AlertEvaluation[] }>(
        `/alert-rules/evaluate${buildQuery({ page, from, to })}`
      ),
  })
}
