import type { DateRange } from '@/hooks/useDateRange'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  data: (range: DateRange) => ['dashboard', range.from, range.to] as const,
  deltas: (range: DateRange) => ['dashboard', 'deltas', range.from, range.to] as const,
  activityCalendar: (days: number) => ['dashboard', 'activity-calendar', days] as const,
}

export const projectKeys = {
  all: ['projects'] as const,
  list: (range: DateRange, sort?: string, order?: string, page?: number, search?: string) =>
    ['projects', 'list', range.from, range.to, sort, order, page, search] as const,
  detail: (path: string, range: DateRange) =>
    ['projects', 'detail', path, range.from, range.to] as const,
}

export const sessionKeys = {
  all: ['sessions'] as const,
  list: (range: DateRange, project?: string, page?: number) =>
    ['sessions', 'list', range.from, range.to, project, page] as const,
  replay: (id: string) => ['sessions', 'replay', id] as const,
}

export const costKeys = {
  all: ['cost'] as const,
  data: (range: DateRange) => ['cost', range.from, range.to] as const,
  anomalies: (range: DateRange) => ['cost', 'anomalies', range.from, range.to] as const,
  cumulative: (range: DateRange) => ['cost', 'cumulative', range.from, range.to] as const,
  cacheSimulation: (rate: number, range: DateRange) => ['cost', 'cache-simulation', rate, range.from, range.to] as const,
}

export const productivityKeys = {
  all: ['productivity'] as const,
  data: (range: DateRange) => ['productivity', range.from, range.to] as const,
  efficiencyTrend: (range: DateRange) => ['productivity', 'efficiency-trend', range.from, range.to] as const,
  languageTrend: (range: DateRange) => ['productivity', 'language-trend', range.from, range.to] as const,
  toolSuccessTrend: (range: DateRange) => ['productivity', 'tool-success-trend', range.from, range.to] as const,
  fileChurn: (range: DateRange) => ['productivity', 'file-churn', range.from, range.to] as const,
}

export const analyticsKeys = {
  all: ['analytics'] as const,
  data: (range: DateRange) => ['analytics', range.from, range.to] as const,
  thinkingTrend: (range: DateRange) => ['analytics', 'thinking-trend', range.from, range.to] as const,
  cacheTrend: (range: DateRange) => ['analytics', 'cache-trend', range.from, range.to] as const,
}

export const experimentKeys = {
  tags: ['experiments', 'tags'] as const,
  compare: (tagA: string, tagB: string) => ['experiments', 'compare', tagA, tagB] as const,
  compareMulti: (tags: string[]) => ['experiments', 'compare-multi', ...tags.sort()] as const,
  tagSessions: (tagName: string) => ['experiments', 'tag-sessions', tagName] as const,
}

export const settingsKeys = {
  all: ['settings'] as const,
}

export const heatmapKeys = {
  all: ['heatmap'] as const,
  data: (range: DateRange, metric: string) => ['heatmap', range.from, range.to, metric] as const,
}

export const modelKeys = {
  all: ['models'] as const,
  data: (range: DateRange) => ['models', range.from, range.to] as const,
}

export const workflowKeys = {
  all: ['workflows'] as const,
  data: (range: DateRange) => ['workflows', range.from, range.to] as const,
}

export const searchKeys = {
  query: (q: string) => ['search', q] as const,
}

export const explorerKeys = {
  all: ['explorer'] as const,
  query: (params: { metric: string | null; group_by: string | null; split_by?: string | null; from?: string | null; to?: string | null; projects?: string | null; models?: string | null; branches?: string | null; languages?: string | null }) =>
    ['explorer', 'query', params.metric, params.group_by, params.split_by, params.from, params.to, params.projects, params.models, params.branches, params.languages] as const,
  drilldown: (params: { metric: string | null; group_by: string | null; group_value: string | null; split_by?: string | null; split_value?: string | null; from?: string | null; to?: string | null; projects?: string | null; models?: string | null; branches?: string | null; languages?: string | null; page?: number; limit?: number }) =>
    ['explorer', 'drilldown', params.metric, params.group_by, params.group_value, params.split_by, params.split_value, params.from, params.to, params.projects, params.models, params.branches, params.languages, params.page, params.limit] as const,
  filters: (from: string | null, to: string | null) => ['explorer', 'filters', from, to] as const,
}

export const advancedKeys = {
  reliability: (range: DateRange) => ['advanced', 'reliability', range.from, range.to] as const,
  branchHealth: (range: DateRange, branches?: string | null) =>
    ['advanced', 'branch-health', range.from, range.to, branches] as const,
  promptEfficiency: (range: DateRange) => ['advanced', 'prompt-efficiency', range.from, range.to] as const,
  workflowBottlenecks: (range: DateRange) => ['advanced', 'workflow-bottlenecks', range.from, range.to] as const,
}

export const savedViewKeys = {
  views: (page: string) => ['saved-views', page] as const,
  alerts: (page?: string | null) => ['alert-rules', page] as const,
  alertEval: (page: string, from: string | null, to: string | null) => ['alert-rules', 'evaluate', page, from, to] as const,
}
