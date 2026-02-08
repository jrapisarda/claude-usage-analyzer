import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Treemap,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { PageLayout } from '@/components/PageLayout'
import { MetricCard } from '@/components/ui/MetricCard'
import { ChartCard } from '@/components/ui/ChartCard'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { useDateRange } from '@/hooks/useDateRange'
import { useExplorer, useExplorerFilters } from '@/api/explorer'
import type { ExplorerParams, FilterOption } from '@/api/explorer'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'
import { formatNumber, formatCurrency, formatDuration, cn } from '@/lib/utils'
import { ChevronDown, X } from 'lucide-react'

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

// Multi-select dropdown component
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
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const toggle = useCallback((val: string) => {
    onChange(
      selected.includes(val)
        ? selected.filter(v => v !== val)
        : [...selected, val]
    )
  }, [selected, onChange])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 w-full px-3 py-1.5 text-sm rounded-md border border-border bg-background",
          "hover:bg-accent/50 text-left",
          selected.length > 0 && "ring-1 ring-primary/30",
        )}
      >
        <span className="flex-1 truncate">
          {selected.length > 0 ? `${label} (${selected.length})` : label}
        </span>
        {selected.length > 0 && (
          <X
            className="h-3 w-3 text-muted-foreground hover:text-foreground shrink-0"
            onClick={e => { e.stopPropagation(); onChange([]) }}
          />
        )}
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-64 max-h-60 overflow-y-auto rounded-md border border-border bg-card shadow-lg">
          {options.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No options</p>
          ) : options.map(opt => (
            <label
              key={opt.value}
              className="flex items-center gap-2 px-3 py-1.5 hover:bg-accent/50 cursor-pointer text-sm"
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
      )}
    </div>
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

  const isTimeSeries = effectiveGroupBy === 'date'
  const hasSplit = !!effectiveSplitBy
  const metricLabel = METRICS.find(m => m.value === metric)?.label ?? metric ?? ''

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

  return (
    <PageLayout title="Analytics Explorer" subtitle="Query any metric by any dimension">
      {/* Controls row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Metric</label>
          <select
            value={metric ?? ''}
            onChange={e => { setMetric(e.target.value || null); setGroupBy(null); setSplitBy(null) }}
            className="w-full px-3 py-1.5 text-sm rounded-md border border-border bg-background"
          >
            <option value="">Select metric...</option>
            {['Turns', 'Tools', 'Sessions'].map(group => (
              <optgroup key={group} label={group}>
                {METRICS.filter(m => m.group === group).map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Group By</label>
          <select
            value={effectiveGroupBy ?? ''}
            onChange={e => setGroupBy(e.target.value || null)}
            className="w-full px-3 py-1.5 text-sm rounded-md border border-border bg-background"
            disabled={!metric}
          >
            <option value="">Select dimension...</option>
            {ALL_DIMENSIONS.map(d => (
              <option key={d.value} value={d.value} disabled={!allowedDims.has(d.value)}>
                {d.label}{!allowedDims.has(d.value) ? ' (N/A)' : ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Split By (optional)</label>
          <select
            value={effectiveSplitBy ?? ''}
            onChange={e => setSplitBy(e.target.value || null)}
            className="w-full px-3 py-1.5 text-sm rounded-md border border-border bg-background"
            disabled={!metric || !effectiveGroupBy}
          >
            <option value="">None</option>
            {ALL_DIMENSIONS.filter(d => d.value !== effectiveGroupBy).map(d => (
              <option key={d.value} value={d.value} disabled={!allowedDims.has(d.value)}>
                {d.label}{!allowedDims.has(d.value) ? ' (N/A)' : ''}
              </option>
            ))}
          </select>
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
        <LoadingState message="Querying data..." />
      ) : error ? (
        <ErrorState message={error.message} />
      ) : !data || data.rows.length === 0 ? (
        <EmptyState message="No data for current selection" />
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
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
          </div>

          {/* Charts — time series, no split */}
          {isTimeSeries && !hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <ChartCard title={`${metricLabel} Over Time`} subtitle="Line chart">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeData}>
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Line type="monotone" dataKey="value" stroke={CHART_COLORS[0]} strokeWidth={2} dot={{ r: 3 }} name={metricLabel} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <ChartCard title={`${metricLabel} Over Time`} subtitle="Area chart">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
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
                      <Area type="monotone" dataKey="value" stroke={CHART_COLORS[0]} fill="url(#explorerGrad)" name={metricLabel} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>
          )}

          {/* Charts — time series, with split */}
          {isTimeSeries && hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <ChartCard title={`${metricLabel} by ${effectiveSplitBy}`} subtitle="Multi-line chart">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeData}>
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend />
                      {splitKeys.map((k, i) => (
                        <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={false} name={k} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <ChartCard title={`${metricLabel} Stacked`} subtitle="Stacked area chart">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={timeData}>
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend />
                      {splitKeys.map((k, i) => (
                        <Area key={k} type="monotone" dataKey={k} stackId="1" stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.4} name={k} />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>
          )}

          {/* Charts — categorical, no split */}
          {!isTimeSeries && !hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <ChartCard title={`${metricLabel} by ${effectiveGroupBy}`} subtitle="Bar chart (top 20)">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={catData} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 10 }} />
                      <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Bar dataKey="value" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} name={metricLabel} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <ChartCard title={`${metricLabel} Distribution`} subtitle="Donut chart (top 10)">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
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
                      >
                        {pieData.map((_: any, i: number) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <ChartCard title={`${metricLabel} Treemap`} subtitle="Top 30 by size">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <Treemap
                      data={treemapData}
                      dataKey="value"
                      nameKey="name"
                      stroke="var(--color-border)"
                      content={({ x, y, width, height, name, fill }: any) => (
                        <g>
                          <rect x={x} y={y} width={width} height={height} fill={fill} rx={2} />
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
              </ChartCard>
            </div>
          )}

          {/* Charts — categorical, with split */}
          {!isTimeSeries && hasSplit && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <ChartCard title={`${metricLabel} Grouped`} subtitle="Grouped bar chart">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={catData}>
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend />
                      {splitKeys.map((k, i) => (
                        <Bar key={k} dataKey={k} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[4, 4, 0, 0]} name={k} />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <ChartCard title={`${metricLabel} Stacked`} subtitle="Stacked bar chart">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={catData}>
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend />
                      {splitKeys.map((k, i) => (
                        <Bar key={k} dataKey={k} stackId="stack" fill={CHART_COLORS[i % CHART_COLORS.length]} name={k} />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              {radarData.length > 0 && radarData.length <= 8 && (
                <ChartCard title={`${metricLabel} Radar`} subtitle="Radar chart">
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
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
                    </ResponsiveContainer>
                  </div>
                </ChartCard>
              )}
            </div>
          )}

          {/* Data table */}
          <ChartCard title="Raw Data" subtitle={`${tableRows.length} rows (max 100 shown)`}>
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="py-2 px-3 font-medium text-muted-foreground">{effectiveGroupBy}</th>
                    {hasSplit && <th className="py-2 px-3 font-medium text-muted-foreground">{effectiveSplitBy}</th>}
                    <th className="py-2 px-3 font-medium text-muted-foreground text-right">{metricLabel}</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.slice(0, 100).map((r, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-accent/30">
                      <td className="py-1.5 px-3">{r.group}</td>
                      {hasSplit && <td className="py-1.5 px-3">{r.split}</td>}
                      <td className="py-1.5 px-3 text-right font-mono">{formatValue(r.value, metric!)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartCard>
        </>
      )}
    </PageLayout>
  )
}
