import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { settingsKeys } from './keys'

export interface PricingEntry {
  input: number
  output: number
  cache_read: number
  cache_write_5m: number
  cache_write_1h: number
  cache_write?: number
}

export interface EtlStatus {
  files_total: number
  files_processed: number
  last_run: string | null
  database_size_bytes: number
}

export interface DatabaseStats {
  sessions: number
  turns: number
  tool_calls: number
  experiment_tags: number
  daily_summaries: number
  etl_state: number
  snapshots: number
}

export interface SettingsData {
  pricing: Record<string, PricingEntry>
  etl_status: EtlStatus
  db_stats: DatabaseStats
  version: string
}

export function useSettings() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: () => apiFetch<SettingsData>('/settings'),
  })
}

export function useUpdatePricing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { model: string; pricing: PricingEntry }) =>
      apiFetch('/settings/pricing', {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  })
}

export function useRebuildDatabase() {
  return useMutation({
    mutationFn: () => apiFetch('/settings/rebuild', { method: 'POST' }),
  })
}
