import { useQuery } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { productivityKeys } from './keys'
import type { DateRange } from '@/hooks/useDateRange'

export interface EfficiencySummary {
  total_loc_written: number
  total_loc_delivered: number
  avg_loc_per_session: number
  cost_per_kloc: number
  tokens_per_loc: number
  error_rate: number
}

export interface LocTrendPoint {
  date: string
  loc_written: number
  loc_delivered: number
  lines_added: number
  lines_deleted: number
}

export interface LanguageBreakdown {
  language: string
  loc_written: number
  files_count: number
  percentage: number
}

export interface ToolUsageStat {
  tool_name: string
  total_calls: number
  success_count: number
  error_count: number
  success_rate: number
  loc_written: number
}

export interface ErrorCategory {
  category: string
  count: number
  percentage: number
}

export interface ErrorAnalysis {
  total_errors: number
  error_rate: number
  categories: ErrorCategory[]
  top_errors: Record<string, unknown>[]
}

export interface FileHotspot {
  file_path: string
  edit_count: number
  write_count: number
  total_touches: number
  loc_written: number
  language: string | null
}

export interface ProductivityData {
  summary: EfficiencySummary
  loc_trend: LocTrendPoint[]
  languages: LanguageBreakdown[]
  tool_usage: ToolUsageStat[]
  error_analysis: ErrorAnalysis
  file_hotspots: FileHotspot[]
}

export function useProductivity(dateRange: DateRange) {
  return useQuery({
    queryKey: productivityKeys.data(dateRange),
    queryFn: () => apiFetch<ProductivityData>(
      `/productivity${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

// --- Phase 4 additions ---

export interface EfficiencyTrend {
  date: string
  cost_per_kloc: number
}

export interface LanguageTrend {
  date: string
  language: string
  loc_written: number
}

export interface ToolSuccessTrend {
  date: string
  tool_name: string
  success_rate: number
  total: number
}

export interface FileChurn {
  file_path: string
  edit_count: number
  total_loc: number
}

export function useEfficiencyTrend(dateRange: DateRange) {
  return useQuery({
    queryKey: productivityKeys.efficiencyTrend(dateRange),
    queryFn: () => apiFetch<EfficiencyTrend[]>(
      `/productivity/efficiency-trend${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useLanguageTrend(dateRange: DateRange) {
  return useQuery({
    queryKey: productivityKeys.languageTrend(dateRange),
    queryFn: () => apiFetch<LanguageTrend[]>(
      `/productivity/language-trend${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useToolSuccessTrend(dateRange: DateRange) {
  return useQuery({
    queryKey: productivityKeys.toolSuccessTrend(dateRange),
    queryFn: () => apiFetch<ToolSuccessTrend[]>(
      `/productivity/tool-success-trend${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}

export function useFileChurn(dateRange: DateRange) {
  return useQuery({
    queryKey: productivityKeys.fileChurn(dateRange),
    queryFn: () => apiFetch<FileChurn[]>(
      `/productivity/file-churn${buildQuery({ from: dateRange.from, to: dateRange.to })}`
    ),
  })
}
