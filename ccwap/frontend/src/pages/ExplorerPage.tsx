import { useState, useMemo, useCallback, useEffect } from 'react'
import { Link } from 'react-router'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Treemap,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { EmptyState } from '@/components/composite/EmptyState'
import { ErrorState } from '@/components/composite/ErrorState'
import { SavedViewsBar } from '@/components/composite/SavedViewsBar'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectLabel,
} from '@/components/ui/select'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useDateRange } from '@/hooks/useDateRange'
import { useExplorer, useExplorerDrilldown, useExplorerFilters } from '@/api/explorer'
import { useSessionReplay } from '@/api/sessions'
import type { ExplorerParams, ExplorerDrilldownSession, FilterOption } from '@/api/explorer'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'
import { formatNumber, formatCurrency, formatDuration, cn } from '@/lib/utils'
import { type ColumnDef } from '@tanstack/react-table'
import { ChevronDown, ExternalLink, X } from 'lucide-react'

// Metric definitions
const METRICS = [
  { value: 'cost', label: 'Cost ($)', group: 'Turns' },
  { value: 'input_tokens', label: 'Input Tokens', group: 'Turns' },
  { value: 'output_tokens', label: 'Output Tokens', group: 'Turns' },
  { value: 'cache_read_tokens', label: 'Cache Read Tokens', group: 'Turns' },
  { value: 'cache_write_tokens', label: 'Cache Write Tokens', group: 'Turns' },
  { value: 'ephemeral_5m_tokens', label: 'Ephemeral 5m Tokens', group: 'Turns' },
  { value: 'ephemeral_1h_tokens', label: 'Ephemeral 1h Tokens', group: 'Turns' },
  { value: 'thinking_chars', label: 'Thinking Chars', group: 'Turns' },
  { value: 'turns_count', label: 'Turns Count', group: 'Turns' },
  { value: 'loc_written', label: 'LOC Written', group: 'Tools' },
  { value: 'tool_calls_count', label: 'Tool Calls', group: 'Tools' },
  { value: 'errors', label: 'Errors', group: 'Tools' },
  { value: 'lines_added', label: 'Lines Added', group: 'Tools' },
  { value: 'lines_deleted', label: 'Lines Deleted', group: 'Tools' },
  { value: 'sessions_count', label: 'Sessions', group: 'Sessions' },
  { value: 'duration_seconds', label: 'Duration (s)', group: 'Sessions' },
]

const ALL_DIMENSIONS = [
  { value: 'date', label: 'Date' },
  { value: 'model', label: 'Model' },
  { value: 'project', label: 'Project' },
  { value: 'branch', label: 'Branch' },
  { value: 'language', label: 'Language' },
  { value: 'tool_name', label: 'Tool Name' },
  { value: 'cc_version', label: 'CC Version' },
  { value: 'entry_type', label: 'Entry Type' },
  { value: 'is_agent', label: 'Agent/User' },
]

const TURNS_DIMS = new Set(['date', 'model', 'project', 'branch', 'cc_version', 'entry_type', 'is_agent'])
const TOOL_DIMS = new Set(['date', 'model', 'project', 'branch', 'language', 'tool_name', 'cc_version', 'entry_type', 'is_agent'])
const SESSION_DIMS = new Set(['date', 'project', 'branch', 'cc_version', 'is_agent'])
const TURNS_METRICS_SET = new Set(['cost', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens', 'ephemeral_5m_tokens', 'ephemeral_1h_tokens', 'thinking_chars', 'turns_count'])
const TOOL_METRICS_SET = new Set(['loc_written', 'tool_calls_count', 'errors', 'lines_added', 'lines_deleted'])
const DRILLDOWN_PAGE_SIZE = 20

function getAllowedDims(metric: string | null): Set<string> {
  if (!metric) return new Set()
  if (TURNS_METRICS_SET.has(metric)) return TURNS_DIMS
  if (TOOL_METRICS_SET.has(metric)) return TOOL_DIMS
  return SESSION_DIMS
}

function formatValue(value: number, metric: string): string {
  if (metric === 'cost') return formatCurrency(value)
  if (metric === 'duration_seconds') return formatDuration(value)
  return formatNumber(value)
}

function toStringList(input: unknown): string[] {
  if (Array.isArray(input)) {
    return input.map(v => String(v).trim()).filter(Boolean)
  }
  if (typeof input === 'string') {
    return input.split(',').map(v => v.trim()).filter(Boolean)
  }
  return []
}

function toNullableString(input: unknown): string | null {
  if (typeof input !== 'string') return null
  const trimmed = input.trim()
  return trimmed.length > 0 ? trimmed : null
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return 'N/A'
  const parsed = new Date(timestamp)
  if (Number.isNaN(parsed.getTime())) return timestamp
  return parsed.toLocaleString()
}

// Multi-select dropdown component using Popover
function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: FilterOption[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  const [open, setOpen] = useState(false)

  const toggle = useCallback((val: string) => {
    onChange(
      selected.includes(val)
        ? selected.filter(v => v !== val)
        : [...selected, val]
    )
  }, [selected, onChange])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            "w-full justify-between text-sm font-normal h-9",
            selected.length > 0 && "ring-1 ring-primary/30",
          )}
        >
          <span className="truncate">
            {selected.length > 0 ? `${label} (${selected.length})` : label}
          </span>
          <div className="flex items-center gap-1 shrink-0 ml-1">
            {selected.length > 0 && (
              <X
                className="h-3 w-3 text-muted-foreground hover:text-foreground"
                onClick={e => { e.stopPropagation(); onChange([]) }}
              />
            )}
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <ScrollArea className="max-h-60">
          <div className="p-1">
            {options.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">No options</p>
            ) : options.map(opt => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-accent/50 cursor-pointer text-sm rounded-sm"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(opt.value)}
                  onChange={() => toggle(opt.value)}
                  className="rounded border-border"
                />
                <span className="flex-1 truncate">{opt.label}</span>
                <span className="text-xs text-muted-foreground">{opt.count}</span>
              </label>
            ))}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )
}

export default function ExplorerPage() {
  const { dateRange } = useDateRange()

  // Controls state
  const [metric, setMetric] = useState<string | null>(null)
  const [groupBy, setGroupBy] = useState<string | null>(null)
  const [splitBy, setSplitBy] = useState<string | null>(null)

  // Filters state
  const [selProjects, setSelProjects] = useState<string[]>([])
  const [selModels, setSelModels] = useState<string[]>([])
  const [selBranches, setSelBranches] = useState<string[]>([])
  const [selLanguages, setSelLanguages] = useState<string[]>([])
  const [selectedBucket, setSelectedBucket] = useState<{ group: string; split: string | null } | null>(null)
  const [drillPage, setDrillPage] = useState(1)
  const [isDrillOpen, setIsDrillOpen] = useState(false)
  const [selectedDrillSessionId, setSelectedDrillSessionId] = useState<string | null>(null)

  const allowedDims = getAllowedDims(metric)

  // Reset invalid dimensions when metric changes
  const effectiveGroupBy = groupBy && allowedDims.has(groupBy) ? groupBy : null
  const effectiveSplitBy = splitBy && allowedDims.has(splitBy) && splitBy !== effectiveGroupBy ? splitBy : null

  const params: ExplorerParams = {
    metric,
    group_by: effectiveGroupBy,
    split_by: effectiveSplitBy,
    from: dateRange.from,
    to: dateRange.to,
    projects: selProjects.length ? selProjects.join(',') : null,
    models: selModels.length ? selModels.join(',') : null,
    branches: selBranches.length ? selBranches.join(',') : null,
    languages: selLanguages.length ? selLanguages.join(',') : null,
  }

  const { data, isLoading, error } = useExplorer(params)
  const { data: filterData } = useExplorerFilters(dateRange.from, dateRange.to)
  const { data: drilldownData, isLoading: drilldownLoading, error: drilldownError } = useExplorerDrilldown({
    ...params,
    group_value: selectedBucket?.group ?? null,
    split_value: selectedBucket?.split ?? null,
    page: drillPage,
    limit: DRILLDOWN_PAGE_SIZE,
  })
  const { data: replayData, isLoading: replayLoading, error: replayError } = useSessionReplay(selectedDrillSessionId ?? '')

  useEffect(() => {
    setSelectedBucket(null)
    setDrillPage(1)
    setIsDrillOpen(false)
    setSelectedDrillSessionId(null)
  }, [metric, effectiveGroupBy, effectiveSplitBy, dateRange.from, dateRange.to, selProjects, selModels, selBranches, selLanguages])

  useEffect(() => {
    if (!selectedBucket || selectedDrillSessionId) return
    const firstSessionId = drilldownData?.sessions?.[0]?.session_id ?? null
    if (firstSessionId) {
      setSelectedDrillSessionId(firstSessionId)
    }
  }, [selectedBucket, drilldownData?.sessions, selectedDrillSessionId])

  const isTimeSeries = effectiveGroupBy === 'date'
  const hasSplit = !!effectiveSplitBy
  const metricLabel = METRICS.find(m => m.value === metric)?.label ?? metric ?? ''

  const onSelectBucket = useCallback((group: string, split: string | null) => {
    const cleanedGroup = String(group ?? '').trim()
    if (!cleanedGroup) return
    setSelectedBucket({ group: cleanedGroup, split })
    setDrillPage(1)
    setSelectedDrillSessionId(null)
    setIsDrillOpen(true)
  }, [])

  const onApplySavedView = useCallback((filters: Record<string, unknown>) => {
    setMetric(toNullableString(filters.metric))
    setGroupBy(toNullableString(filters.group_by))
    setSplitBy(toNullableString(filters.split_by))
    setSelProjects(toStringList(filters.projects))
    setSelModels(toStringList(filters.models))
    setSelBranches(toStringList(filters.branches))
    setSelLanguages(toStringList(filters.languages))
    setSelectedBucket(null)
    setDrillPage(1)
    setIsDrillOpen(false)
    setSelectedDrillSessionId(null)
  }, [])

  const currentFilters = useMemo(() => ({
    metric,
    group_by: effectiveGroupBy,
    split_by: effectiveSplitBy,
    projects: selProjects,
    models: selModels,
    branches: selBranches,
    languages: selLanguages,
  }), [metric, effectiveGroupBy, effectiveSplitBy, selProjects, selModels, selBranches, selLanguages])

  const onSelectTimePoint = useCallback((entry: any, split: string | null) => {
    const groupValue = entry?.payload?.date ?? entry?.date
    if (!groupValue) return
    onSelectBucket(String(groupValue), split)
  }, [onSelectBucket])

  const onSelectCategoryPoint = useCallback((entry: any, split: string | null) => {
    const groupValue = entry?.payload?.name ?? entry?.name
    if (!groupValue) return
    onSelectBucket(String(groupValue), split)
  }, [onSelectBucket])

  // Pivot data for charts
  const { timeData, catData, pieData, treemapData, radarData, splitKeys, tableRows } = useMemo(() => {
    if (!data || data.rows.length === 0) {
      return { timeData: [], catData: [], pieData: [], treemapData: [], radarData: [], splitKeys: [] as string[], tableRows: [] as any[] }
    }

    const rows = data.rows
    const splits = data.metadata.splits

    if (isTimeSeries && hasSplit) {
      // Pivot: date -> { date, [split1]: val, [split2]: val, ... }
      const map = new Map<string, Record<string, any>>()
      for (const r of rows) {
        if (!map.has(r.group)) map.set(r.group, { date: r.group })
        const entry = map.get(r.group)!
        entry[r.split ?? ''] = r.value
      }
      const pivoted = fillZeros(
        Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date)),
        splits,
      )
      return { timeData: pivoted, catData: [], pieData: [], treemapData: [], radarData: [], splitKeys: splits, tableRows: rows }
    }

    if (isTimeSeries) {
      // Simple time series: { date, value }
      const sorted = [...rows]
        .map(r => ({ date: r.group, value: r.value }))
        .sort((a, b) => a.date.localeCompare(b.date))
      return { timeData: sorted, catData: [], pieData: [], treemapData: [], radarData: [], splitKeys: [] as string[], tableRows: rows }
    }

    if (hasSplit) {
      // Categorical with split: group -> { name, [split1], [split2], ... , total }
      const map = new Map<string, Record<string, any>>()
      for (const r of rows) {
        if (!map.has(r.group)) map.set(r.group, { name: r.group, total: 0 })
        const entry = map.get(r.group)!
        entry[r.split ?? ''] = r.value
        entry.total = (entry.total || 0) + r.value
      }
      const all = fillZeros(
        Array.from(map.values()).sort((a, b) => b.total - a.total),
        splits,
      )
      const top20 = all.slice(0, 20)
      const radar = all.slice(0, 8)
      return { timeData: [], catData: top20, pieData: [], treemapData: [], radarData: radar, splitKeys: splits, tableRows: rows }
    }

    // Categorical, no split
    const sorted = [...rows]
      .map(r => ({ name: r.group, value: r.value }))
      .sort((a, b) => b.value - a.value)
    const top20 = sorted.slice(0, 20)
    const top10 = sorted.slice(0, 10)
    const top30 = sorted.slice(0, 30)
    const treemap = top30.map((d, i) => ({
      ...d,
      fill: CHART_COLORS[i % CHART_COLORS.length],
    }))
    return { timeData: [], catData: top20, pieData: top10, treemapData: treemap, radarData: [], splitKeys: [] as string[], tableRows: rows }
  }, [data, isTimeSeries, hasSplit])

  // Dynamic columns for the raw data table
  const rawTableColumns: ColumnDef<any, unknown>[] = useMemo(() => {
    const cols: ColumnDef<any, unknown>[] = [
      {
        accessorKey: 'group',
        header: effectiveGroupBy ?? 'Group',
        cell: ({ row }) => (
          <Button
            variant="link"
            className="h-auto p-0 text-left"
            onClick={() => onSelectBucket(row.original.group, row.original.split ?? null)}
          >
            {row.original.group}
          </Button>
        ),
      },
    ]
    if (hasSplit) {
      cols.push({
        accessorKey: 'split',
        header: effectiveSplitBy ?? 'Split',
        cell: ({ row }) => <span>{row.original.split}</span>,
      })
    }
    cols.push({
      accessorKey: 'value',
      header: () => <span className="text-right block">{metricLabel}</span>,
      cell: ({ row }) => (
        <span className="font-mono text-right block">{formatValue(row.original.value, metric!)}</span>
      ),
    })
    return cols
  }, [effectiveGroupBy, effectiveSplitBy, hasSplit, metricLabel, metric, onSelectBucket])

  const drilldownColumns: ColumnDef<ExplorerDrilldownSession, unknown>[] = useMemo(() => ([
    {
      accessorKey: 'session_id',
      header: 'Session',
      cell: ({ row }) => (
        <button
          type="button"
          className="font-mono text-xs text-primary hover:underline"
          onClick={() => setSelectedDrillSessionId(row.original.session_id)}
        >
          {row.original.session_id}
        </button>
      ),
    },
    {
      id: 'open',
      header: '',
      cell: ({ row }) => (
        <Link to={`/sessions/${row.original.session_id}`} className="inline-flex items-center text-muted-foreground hover:text-foreground" title="Open session page">
          <ExternalLink className="h-3.5 w-3.5" />
        </Link>
      ),
    },
    {
      accessorKey: 'project',
      header: 'Project',
      cell: ({ row }) => <span className="truncate block max-w-[180px]">{row.original.project}</span>,
    },
    {
      accessorKey: 'bucket_value',
      header: () => <span className="text-right block">{metricLabel}</span>,
      cell: ({ row }) => (
        <span className="font-mono text-right block">{formatValue(row.original.bucket_value, metric ?? 'turns_count')}</span>
      ),
    },
    {
      accessorKey: 'errors',
      header: () => <span className="text-right block">Errors</span>,
      cell: ({ row }) => <span className="font-mono text-right block">{formatNumber(row.original.errors)}</span>,
    },
  ]), [metric, metricLabel])

  return (
    <>
    <PageLayout title="Data Explorer" subtitle="Query any metric by any dimension">
      <SavedViewsBar
        page="explorer"
        currentFilters={currentFilters}
        onApply={onApplySavedView}
        from={dateRange.from}
        to={dateRange.to}
        defaultMetricForAlert={metric ?? 'cost'}
      />

      {/* Controls row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Metric</label>
          <Select
            value={metric ?? '__none__'}
            onValueChange={(val) => { setMetric(val === '__none__' ? null : val); setGroupBy(null); setSplitBy(null) }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select metric..." />
            </SelectTrigger>
            <SelectContent>
              {['Turns', 'Tools', 'Sessions'].map(group => (
                <SelectGroup key={group}>
                  <SelectLabel>{group}</SelectLabel>
                  {METRICS.filter(m => m.group === group).map(m => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Group By</label>
          <Select
            value={effectiveGroupBy ?? '__none__'}
            onValueChange={(val) => setGroupBy(val === '__none__' ? null : val)}
            disabled={!metric}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select dimension..." />
            </SelectTrigger>
            <SelectContent>
              {ALL_DIMENSIONS.map(d => (
                <SelectItem
                  key={d.value}
                  value={d.value}
                  disabled={!allowedDims.has(d.value)}
                >
                  {d.label}{!allowedDims.has(d.value) ? ' (N/A)' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Split By (optional)</label>
          <Select
            value={effectiveSplitBy ?? '__none__'}
            onValueChange={(val) => setSplitBy(val === '__none__' ? null : val)}
            disabled={!metric || !effectiveGroupBy}
          >
            <SelectTrigger>
              <SelectValue placeholder="None" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">None</SelectItem>
              {ALL_DIMENSIONS.filter(d => d.value !== effectiveGroupBy).map(d => (
                <SelectItem
                  key={d.value}
                  value={d.value}
                  disabled={!allowedDims.has(d.value)}
                >
                  {d.label}{!allowedDims.has(d.value) ? ' (N/A)' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Filters row */}
      {filterData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <MultiSelect
            label="Projects"
            options={filterData.projects}
            selected={selProjects}
            onChange={setSelProjects}
          />
          <MultiSelect
            label="Models"
            options={filterData.models}
            selected={selModels}
            onChange={setSelModels}
          />
          <MultiSelect
            label="Branches"
            options={filterData.branches}
            selected={selBranches}
            onChange={setSelBranches}
          />
          <MultiSelect
            label="Languages"
            options={filterData.languages}
            selected={selLanguages}
            onChange={setSelLanguages}
          />
        </div>
      )}

      {/* States */}
      {!metric || !effectiveGroupBy ? (
        <EmptyState message="Select a metric and dimension to explore" />
      ) : isLoading ? (
        <div className="space-y-4">
          <MetricCardGrid skeleton count={4} />
          <Skeleton className="h-80 w-full" />
        </div>
      ) : error ? (
        <ErrorState message={error.message} />
      ) : !data || data.rows.length === 0 ? (
        <EmptyState message="No data for current selection" />
      ) : (
        <>
          {/* Summary cards */}
          <MetricCardGrid className="mb-6">
            <MetricCard title="Total" value={formatValue(data.metadata.total, metric)} />
            <MetricCard title="Data Points" value={formatNumber(data.metadata.row_count)} />
            <MetricCard title="Groups" value={formatNumber(data.metadata.groups.length)} />
            <MetricCard
              title={hasSplit ? 'Splits' : 'Avg per Group'}
              value={hasSplit
                ? formatNumber(data.metadata.splits.length)
                : formatValue(data.metadata.total / Math.max(data.metadata.groups.length, 1), metric)
              }
            />
          </MetricCardGrid>

          {/* Charts -- time series, no split */}
          {isTimeSeries && !hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <ChartContainer title={`${metricLabel} Over Time`} height={320}>
                <LineChart data={timeData}>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={CHART_COLORS[0]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name={metricLabel}
                    onClick={(entry: any) => onSelectTimePoint(entry, null)}
                  />
                </LineChart>
              </ChartContainer>
              <ChartContainer title={`${metricLabel} Over Time`} height={320}>
                <AreaChart data={timeData}>
                  <defs>
                    <linearGradient id="explorerGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={CHART_COLORS[0]}
                    fill="url(#explorerGrad)"
                    name={metricLabel}
                    onClick={(entry: any) => onSelectTimePoint(entry, null)}
                  />
                </AreaChart>
              </ChartContainer>
            </div>
          )}

          {/* Charts -- time series, with split */}
          {isTimeSeries && hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <ChartContainer title={`${metricLabel} by ${effectiveSplitBy}`} height={320}>
                <LineChart data={timeData}>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  {splitKeys.map((k, i) => (
                    <Line
                      key={k}
                      type="monotone"
                      dataKey={k}
                      stroke={CHART_COLORS[i % CHART_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      name={k}
                      onClick={(entry: any) => onSelectTimePoint(entry, k)}
                    />
                  ))}
                </LineChart>
              </ChartContainer>
              <ChartContainer title={`${metricLabel} Stacked`} height={320}>
                <AreaChart data={timeData}>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  {splitKeys.map((k, i) => (
                    <Area
                      key={k}
                      type="monotone"
                      dataKey={k}
                      stackId="1"
                      stroke={CHART_COLORS[i % CHART_COLORS.length]}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                      fillOpacity={0.4}
                      name={k}
                      onClick={(entry: any) => onSelectTimePoint(entry, k)}
                    />
                  ))}
                </AreaChart>
              </ChartContainer>
            </div>
          )}

          {/* Charts -- categorical, no split */}
          {!isTimeSeries && !hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <ChartContainer title={`${metricLabel} by ${effectiveGroupBy}`} height={320}>
                <BarChart data={catData} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar
                    dataKey="value"
                    fill={CHART_COLORS[0]}
                    radius={[0, 4, 4, 0]}
                    name={metricLabel}
                    onClick={(entry: any) => onSelectCategoryPoint(entry, null)}
                  />
                </BarChart>
              </ChartContainer>
              <ChartContainer title={`${metricLabel} Distribution`} height={320}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={{ strokeWidth: 1 }}
                    onClick={(entry: any) => onSelectCategoryPoint(entry, null)}
                  >
                    {pieData.map((_: any, i: number) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ChartContainer>
              <Card>
                <CardHeader className="pb-3 pt-4 px-4">
                  <CardTitle className="text-sm font-medium text-muted-foreground">{metricLabel} Treemap</CardTitle>
                  <span className="text-xs text-muted-foreground">Top 30 by size</span>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <Treemap
                        data={treemapData}
                        dataKey="value"
                        nameKey="name"
                        stroke="var(--color-border)"
                        content={({ x, y, width, height, name, fill }: any) => (
                          <g>
                            <rect
                              x={x}
                              y={y}
                              width={width}
                              height={height}
                              fill={fill}
                              rx={2}
                              className="cursor-pointer"
                              onClick={() => {
                                if (name) onSelectBucket(String(name), null)
                              }}
                            />
                            {width >= 30 && height >= 20 && (
                              <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="middle" fill="white" fontSize={10}>
                                {String(name ?? '').slice(0, Math.floor(width / 7))}
                              </text>
                            )}
                          </g>
                        )}
                      />
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Charts -- categorical, with split */}
          {!isTimeSeries && hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <ChartContainer title={`${metricLabel} Grouped`} height={320}>
                <BarChart data={catData}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  {splitKeys.map((k, i) => (
                    <Bar
                      key={k}
                      dataKey={k}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                      radius={[4, 4, 0, 0]}
                      name={k}
                      onClick={(entry: any) => onSelectCategoryPoint(entry, k)}
                    />
                  ))}
                </BarChart>
              </ChartContainer>
              <ChartContainer title={`${metricLabel} Stacked`} height={320}>
                <BarChart data={catData}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  {splitKeys.map((k, i) => (
                    <Bar
                      key={k}
                      dataKey={k}
                      stackId="stack"
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                      name={k}
                      onClick={(entry: any) => onSelectCategoryPoint(entry, k)}
                    />
                  ))}
                </BarChart>
              </ChartContainer>
              {radarData.length > 0 && radarData.length <= 8 && (
                <ChartContainer title={`${metricLabel} Radar`} height={320}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <PolarRadiusAxis tick={{ fontSize: 9 }} />
                    {splitKeys.map((k, i) => (
                      <Radar key={k} dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.2} name={k} />
                    ))}
                    <Legend />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                  </RadarChart>
                </ChartContainer>
              )}
            </div>
          )}

          {/* Data table */}
          <Card>
            <CardHeader className="pb-3 pt-4 px-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">Raw Data</CardTitle>
              <span className="text-xs text-muted-foreground">Click a row to drill into sessions ({tableRows.length} rows, max 100 shown)</span>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <DataTable
                columns={rawTableColumns}
                data={tableRows.slice(0, 100)}
                emptyMessage="No data"
                onRowClick={(row: any) => onSelectBucket(row.group, row.split ?? null)}
                getRowClassName={(row: any) => (
                  selectedBucket
                    && row.group === selectedBucket.group
                    && (row.split ?? null) === (selectedBucket.split ?? null)
                    ? 'bg-accent/40'
                    : ''
                )}
              />
            </CardContent>
          </Card>

        </>
      )}
    </PageLayout>

    <Sheet open={isDrillOpen} onOpenChange={(open) => {
      setIsDrillOpen(open)
      if (!open) {
        setSelectedDrillSessionId(null)
      }
    }}>
      <SheetContent side="right" className="w-[95vw] sm:max-w-5xl p-0">
        <div className="h-full flex flex-col">
          <SheetHeader className="px-4 py-3 border-b border-border">
            <SheetTitle className="text-base">Explorer Drill-down</SheetTitle>
            <SheetDescription>
              {selectedBucket
                ? `${effectiveGroupBy}: ${selectedBucket.group}${hasSplit ? ` | ${effectiveSplitBy}: ${selectedBucket.split ?? 'N/A'}` : ''}`
                : 'Select a chart bucket or data row'}
            </SheetDescription>
          </SheetHeader>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 flex-1 min-h-0">
            <div className="border-b lg:border-b-0 lg:border-r border-border min-h-0 flex flex-col">
              <div className="px-4 py-3 border-b border-border">
                <MetricCardGrid className="grid-cols-3">
                  <MetricCard title="Sessions" value={formatNumber(drilldownData?.pagination.total_count ?? 0)} />
                  <MetricCard
                    title="Page"
                    value={`${drilldownData?.pagination.page ?? drillPage} / ${Math.max(drilldownData?.pagination.total_pages ?? 1, 1)}`}
                  />
                  <MetricCard title="Metric" value={metricLabel || 'N/A'} />
                </MetricCardGrid>
              </div>

              <div className="p-3 min-h-0 flex-1 overflow-auto">
                {!selectedBucket ? (
                  <p className="text-sm text-muted-foreground">Select a bucket to load sessions.</p>
                ) : drilldownError ? (
                  <p className="text-sm text-destructive">{drilldownError.message}</p>
                ) : (
                  <>
                    <DataTable
                      columns={drilldownColumns}
                      data={drilldownData?.sessions ?? []}
                      isLoading={drilldownLoading}
                      emptyMessage="No sessions for this bucket"
                      onRowClick={(row) => setSelectedDrillSessionId(row.session_id)}
                      getRowClassName={(row) => (
                        selectedDrillSessionId === row.session_id ? 'bg-accent/40' : ''
                      )}
                    />

                    <div className="flex items-center justify-end gap-2 mt-3">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDrillPage(prev => Math.max(1, prev - 1))}
                        disabled={drilldownLoading || drillPage <= 1}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDrillPage(prev => prev + 1)}
                        disabled={
                          drilldownLoading
                          || !drilldownData
                          || drillPage >= (drilldownData.pagination.total_pages || 1)
                        }
                      >
                        Next
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="min-h-0 flex flex-col">
              <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                <h3 className="text-sm font-medium text-muted-foreground">Turn and Tool Details</h3>
                {selectedDrillSessionId && (
                  <Link to={`/sessions/${selectedDrillSessionId}`} className="text-xs text-primary hover:underline">
                    Open session page
                  </Link>
                )}
              </div>
              <ScrollArea className="flex-1 p-4">
                {!selectedDrillSessionId ? (
                  <p className="text-sm text-muted-foreground">Select a session to inspect replay details.</p>
                ) : replayError ? (
                  <p className="text-sm text-destructive">{replayError.message}</p>
                ) : replayLoading || !replayData ? (
                  <div className="space-y-3">
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-24 w-full" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="rounded-md border border-border p-3 bg-card">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div><span className="text-muted-foreground">Session:</span> <span className="font-mono">{replayData.session_id}</span></div>
                        <div><span className="text-muted-foreground">Branch:</span> {replayData.git_branch ?? 'unknown'}</div>
                        <div><span className="text-muted-foreground">Project:</span> {replayData.project_display ?? replayData.project_path}</div>
                        <div><span className="text-muted-foreground">Started:</span> {formatTimestamp(replayData.first_timestamp)}</div>
                      </div>
                      <div className="grid grid-cols-4 gap-2 mt-3 text-xs">
                        <div><span className="text-muted-foreground block">Cost</span><span className="font-mono">{formatCurrency(replayData.total_cost)}</span></div>
                        <div><span className="text-muted-foreground block">Turns</span><span className="font-mono">{formatNumber(replayData.total_turns)}</span></div>
                        <div><span className="text-muted-foreground block">Tools</span><span className="font-mono">{formatNumber(replayData.total_tool_calls)}</span></div>
                        <div><span className="text-muted-foreground block">Errors</span><span className="font-mono">{formatNumber(replayData.total_errors)}</span></div>
                      </div>
                    </div>

                    {replayData.turns.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No turns found for this session.</p>
                    ) : replayData.turns.map((turn) => (
                      <div key={turn.uuid} className="rounded-md border border-border p-3 bg-card">
                        <div className="flex items-center justify-between gap-2 text-xs mb-2">
                          <span className="font-mono">{turn.uuid}</span>
                          <span className="text-muted-foreground">{formatTimestamp(turn.timestamp)}</span>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs mb-2">
                          <span className="rounded border border-border px-2 py-0.5">{turn.entry_type}</span>
                          {turn.model && <span className="rounded border border-border px-2 py-0.5">{turn.model}</span>}
                          <span className="rounded border border-border px-2 py-0.5">Cost {formatCurrency(turn.cost)}</span>
                          {turn.stop_reason && <span className="rounded border border-border px-2 py-0.5">Stop {turn.stop_reason}</span>}
                        </div>

                        {turn.user_prompt_preview && (
                          <p className="text-xs text-muted-foreground mb-2">Prompt: {turn.user_prompt_preview}</p>
                        )}

                        <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                          <span>Input {formatNumber(turn.input_tokens)}</span>
                          <span>Output {formatNumber(turn.output_tokens)}</span>
                          <span>Cache Read {formatNumber(turn.cache_read_tokens)}</span>
                          <span>Thinking {formatNumber(turn.thinking_chars)}</span>
                        </div>

                        {turn.tool_calls.length > 0 ? (
                          <div className="space-y-1.5">
                            {turn.tool_calls.map((tc, idx) => (
                              <div key={`${turn.uuid}-${idx}`} className="rounded border border-border/80 px-2 py-1.5 text-xs bg-background/60">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-medium">{tc.tool_name}</span>
                                  <span className={tc.success ? 'text-green-600' : 'text-destructive'}>
                                    {tc.success ? 'success' : 'failed'}
                                  </span>
                                </div>
                                <div className="flex flex-wrap gap-2 mt-1 text-muted-foreground">
                                  {tc.language && <span>{tc.language}</span>}
                                  {tc.file_path && <span className="font-mono">{tc.file_path}</span>}
                                  <span>LOC {formatNumber(tc.loc_written)}</span>
                                  <span>+{formatNumber(tc.lines_added)} / -{formatNumber(tc.lines_deleted)}</span>
                                </div>
                                {!tc.success && tc.error_category && (
                                  <p className="text-destructive mt-1">{tc.error_category}{tc.error_message ? `: ${tc.error_message}` : ''}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-muted-foreground">No tool calls on this turn.</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
    </>
  )
}
