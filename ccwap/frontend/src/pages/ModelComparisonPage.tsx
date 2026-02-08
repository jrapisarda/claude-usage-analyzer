import { useState, useMemo } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  AreaChart, Area, ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { useDateRange } from '@/hooks/useDateRange'
import { useModelComparison } from '@/api/models'
import type { ModelMetrics } from '@/api/models'
import { PageLayout } from '@/components/PageLayout'
import { MetricCard } from '@/components/ui/MetricCard'
import { ChartCard } from '@/components/ui/ChartCard'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { formatCurrency, formatNumber } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS, AXIS_STYLE, fillZeros } from '@/lib/chartConfig'

type SortField = 'model' | 'sessions' | 'turns' | 'total_cost' | 'avg_turn_cost' | 'loc_written'
type SortDir = 'asc' | 'desc'

const SORT_HEADERS: { key: SortField; label: string; align: 'left' | 'right' }[] = [
  { key: 'model', label: 'Model', align: 'left' },
  { key: 'sessions', label: 'Sessions', align: 'right' },
  { key: 'turns', label: 'Turns', align: 'right' },
  { key: 'total_cost', label: 'Cost', align: 'right' },
  { key: 'avg_turn_cost', label: 'Avg Turn Cost', align: 'right' },
  { key: 'loc_written', label: 'LOC', align: 'right' },
]

function sortModels(models: ModelMetrics[], field: SortField, dir: SortDir): ModelMetrics[] {
  const sorted = [...models]
  sorted.sort((a, b) => {
    const av = a[field]
    const bv = b[field]
    if (typeof av === 'string' && typeof bv === 'string') {
      return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    return dir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
  })
  return sorted
}

export default function ModelComparisonPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useModelComparison(dateRange)
  const [sortField, setSortField] = useState<SortField>('total_cost')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // Sort the models table
  const sortedModels = useMemo(() => {
    if (!data) return []
    return sortModels(data.models, sortField, sortDir)
  }, [data, sortField, sortDir])

  // Radar chart data: normalize top 4 models across 5 metrics to [0..100]
  const radarData = useMemo(() => {
    if (!data || data.models.length === 0) return []
    const top4 = sortModels(data.models, 'sessions', 'desc').slice(0, 4)

    // Define axes with whether lower is better (inverted on radar)
    const axisDefs = [
      { axis: 'Sessions', getter: (m: ModelMetrics) => m.sessions, invert: false },
      { axis: 'Cost', getter: (m: ModelMetrics) => m.total_cost, invert: true },
      { axis: 'Tokens', getter: (m: ModelMetrics) => m.total_input_tokens + m.total_output_tokens, invert: false },
      { axis: 'Thinking', getter: (m: ModelMetrics) => m.avg_thinking_chars, invert: false },
      { axis: 'LOC', getter: (m: ModelMetrics) => m.loc_written, invert: false },
    ]

    return axisDefs.map(a => {
      const values = top4.map(m => a.getter(m))
      const min = Math.min(...values)
      const max = Math.max(...values)
      const range = max - min

      const point: Record<string, string | number> = { axis: a.axis }
      for (const m of top4) {
        const raw = a.getter(m)
        const normalized = range === 0 ? 50 : ((raw - min) / range) * 100
        point[m.model] = Math.round(a.invert ? 100 - normalized : normalized)
      }
      return point
    })
  }, [data])

  const top4Models = useMemo(() => {
    if (!data) return []
    return sortModels(data.models, 'sessions', 'desc').slice(0, 4).map(m => m.model)
  }, [data])

  // Stacked area chart: pivot usage_trend by model per date
  const areaData = useMemo(() => {
    if (!data) return { points: [] as Record<string, string | number>[], models: [] as string[] }
    const uniqueModels = [...new Set(data.usage_trend.map(t => t.model))]
    const byDate = new Map<string, Record<string, string | number>>()
    for (const t of data.usage_trend) {
      if (!byDate.has(t.date)) byDate.set(t.date, { date: t.date })
      byDate.get(t.date)![t.model] = t.count
    }
    const points = fillZeros(
      [...byDate.values()].sort((a, b) => (a.date as string).localeCompare(b.date as string)),
      uniqueModels,
    )
    return { points, models: uniqueModels }
  }, [data])

  // Scatter data: group by model
  const scatterByModel = useMemo(() => {
    if (!data) return new Map<string, { cost: number; loc_written: number }[]>()
    const grouped = new Map<string, { cost: number; loc_written: number }[]>()
    for (const pt of data.scatter) {
      if (!grouped.has(pt.model)) grouped.set(pt.model, [])
      grouped.get(pt.model)!.push({ cost: pt.cost, loc_written: pt.loc_written })
    }
    return grouped
  }, [data])

  function handleSort(field: SortField) {
    if (field === sortField) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  if (isLoading) return <LoadingState message="Loading model comparison..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  // Summary stats
  const totalModels = data.models.length
  const mostUsed = sortedModels.length > 0
    ? sortModels(data.models, 'sessions', 'desc')[0]
    : null
  const highestCost = sortedModels.length > 0
    ? sortModels(data.models, 'total_cost', 'desc')[0]
    : null

  return (
    <PageLayout title="Model Comparison" subtitle="Compare performance and cost across models">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <MetricCard title="Total Models" value={String(totalModels)} />
        <MetricCard
          title="Most Used"
          value={mostUsed?.model || 'N/A'}
          subtitle={mostUsed ? `${formatNumber(mostUsed.sessions)} sessions` : undefined}
        />
        <MetricCard
          title="Highest Cost"
          value={highestCost?.model || 'N/A'}
          subtitle={highestCost ? formatCurrency(highestCost.total_cost) : undefined}
        />
      </div>

      {/* Sortable Model Table */}
      {sortedModels.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden mb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  {SORT_HEADERS.map(h => (
                    <th
                      key={h.key}
                      onClick={() => handleSort(h.key)}
                      className={`px-4 py-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none ${
                        h.align === 'right' ? 'text-right' : 'text-left'
                      }`}
                    >
                      {h.label}
                      {sortField === h.key && (
                        <span className="ml-1">{sortDir === 'asc' ? '\u25B2' : '\u25BC'}</span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedModels.map(m => (
                  <tr key={m.model} className="border-b border-border hover:bg-accent/10">
                    <td className="px-4 py-3 font-medium truncate max-w-[200px]">{m.model}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatNumber(m.sessions)}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatNumber(m.turns)}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatCurrency(m.total_cost)}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatCurrency(m.avg_turn_cost)}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatNumber(m.loc_written)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Radar Chart */}
        {radarData.length > 0 && top4Models.length > 0 && (
          <ChartCard title="Model Comparison (Top 4)" subtitle="Normalized metrics (0-100)">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="var(--color-border)" />
                  <PolarAngleAxis dataKey="axis" tick={AXIS_STYLE} />
                  <PolarRadiusAxis tick={false} domain={[0, 100]} axisLine={false} />
                  {top4Models.map((model, i) => (
                    <Radar
                      key={model}
                      name={model}
                      dataKey={model}
                      stroke={CHART_COLORS[i % CHART_COLORS.length]}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                  ))}
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        )}

        {/* Scatter Chart: Cost vs LOC */}
        {scatterByModel.size > 0 && (
          <ChartCard title="Cost vs LOC per Session" subtitle="Each point is a session">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <XAxis
                    type="number"
                    dataKey="cost"
                    name="Cost"
                    tick={AXIS_STYLE}
                    tickFormatter={v => `$${v}`}
                    stroke="var(--color-muted-foreground)"
                  />
                  <YAxis
                    type="number"
                    dataKey="loc_written"
                    name="LOC"
                    tick={AXIS_STYLE}
                    stroke="var(--color-muted-foreground)"
                    width={50}
                  />
                  <ZAxis range={[30, 30]} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(value: any, name: any) => [
                      name === 'Cost' ? formatCurrency(value ?? 0) : formatNumber(value ?? 0),
                      name ?? '',
                    ]}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  {[...scatterByModel.entries()].map(([model, points], i) => (
                    <Scatter
                      key={model}
                      name={model}
                      data={points}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                      opacity={0.7}
                    />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        )}
      </div>

      {/* Stacked Area Chart: Usage Over Time */}
      {areaData.points.length > 0 && (
        <ChartCard title="Model Usage Over Time" subtitle="Sessions per day by model">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={areaData.points}>
                <defs>
                  {areaData.models.map((model, i) => (
                    <linearGradient key={model} id={`modelGrad-${i}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS[i % CHART_COLORS.length]} stopOpacity={0.4} />
                      <stop offset="95%" stopColor={CHART_COLORS[i % CHART_COLORS.length]} stopOpacity={0.05} />
                    </linearGradient>
                  ))}
                </defs>
                <XAxis
                  dataKey="date"
                  tick={AXIS_STYLE}
                  tickFormatter={d => (d as string).slice(5)}
                  stroke="var(--color-muted-foreground)"
                />
                <YAxis tick={AXIS_STYLE} stroke="var(--color-muted-foreground)" width={40} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                {areaData.models.map((model, i) => (
                  <Area
                    key={model}
                    type="monotone"
                    dataKey={model}
                    stackId="1"
                    stroke={CHART_COLORS[i % CHART_COLORS.length]}
                    fill={`url(#modelGrad-${i})`}
                    strokeWidth={1.5}
                    isAnimationActive={areaData.points.length < 365}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      )}
    </PageLayout>
  )
}
