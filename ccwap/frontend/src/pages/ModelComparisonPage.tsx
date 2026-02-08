import { useState, useMemo, useCallback } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  AreaChart, Area, ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  Tooltip, Legend,
} from 'recharts'
import { type ColumnDef } from '@tanstack/react-table'
import { useDateRange } from '@/hooks/useDateRange'
import { useModelComparison } from '@/api/models'
import type { ModelMetrics } from '@/api/models'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { ErrorState } from '@/components/composite/ErrorState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { formatCurrency, formatNumber } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS, AXIS_STYLE, fillZeros } from '@/lib/chartConfig'

function sortModels(models: ModelMetrics[], field: keyof ModelMetrics, dir: 'asc' | 'desc'): ModelMetrics[] {
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

const modelTableColumns: ColumnDef<ModelMetrics, unknown>[] = [
  {
    accessorKey: 'model',
    header: 'Model',
    cell: ({ row }) => (
      <span className="font-medium truncate max-w-[200px] block">{row.original.model}</span>
    ),
  },
  {
    accessorKey: 'sessions',
    header: () => <span className="text-right block">Sessions</span>,
    cell: ({ row }) => (
      <span className="font-mono text-right block">{formatNumber(row.original.sessions)}</span>
    ),
  },
  {
    accessorKey: 'turns',
    header: () => <span className="text-right block">Turns</span>,
    cell: ({ row }) => (
      <span className="font-mono text-right block">{formatNumber(row.original.turns)}</span>
    ),
  },
  {
    accessorKey: 'total_cost',
    header: () => <span className="text-right block">Cost</span>,
    cell: ({ row }) => (
      <span className="font-mono text-right block">{formatCurrency(row.original.total_cost)}</span>
    ),
  },
  {
    accessorKey: 'avg_turn_cost',
    header: () => <span className="text-right block">Avg Turn Cost</span>,
    cell: ({ row }) => (
      <span className="font-mono text-right block">{formatCurrency(row.original.avg_turn_cost)}</span>
    ),
  },
  {
    accessorKey: 'loc_written',
    header: () => <span className="text-right block">LOC</span>,
    cell: ({ row }) => (
      <span className="font-mono text-right block">{formatNumber(row.original.loc_written)}</span>
    ),
  },
]

export default function ModelComparisonPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error, refetch } = useModelComparison(dateRange)
  const [chartTab, setChartTab] = useState('radar')

  // Sort the models table
  const sortedModels = useMemo(() => {
    if (!data) return []
    return sortModels(data.models, 'total_cost', 'desc')
  }, [data])

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

  const getExportData = useCallback(() => {
    if (!data) return []
    return data.models.map(m => ({
      model: m.model,
      sessions: m.sessions,
      turns: m.turns,
      total_cost: m.total_cost,
      avg_turn_cost: m.avg_turn_cost,
      loc_written: m.loc_written,
    }))
  }, [data])

  if (error) return <ErrorState message={error.message} onRetry={() => refetch()} />

  // Summary stats
  const totalModels = data?.models.length ?? 0
  const mostUsed = data && data.models.length > 0
    ? sortModels(data.models, 'sessions', 'desc')[0]
    : null
  const highestCost = data && data.models.length > 0
    ? sortModels(data.models, 'total_cost', 'desc')[0]
    : null

  return (
    <PageLayout
      title="Model Comparison"
      subtitle="Compare performance and cost across models"
      actions={
        <ExportDropdown page="model-comparison" getData={getExportData} />
      }
    >
      {/* Summary Cards */}
      <MetricCardGrid skeleton={isLoading} count={3} className="grid-cols-2 lg:grid-cols-3 mb-6">
        {data && (
          <>
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
          </>
        )}
      </MetricCardGrid>

      {/* Sortable Model Table */}
      <div className="mb-6">
        <DataTable
          columns={modelTableColumns}
          data={sortedModels}
          isLoading={isLoading}
          emptyMessage="No model data available"
        />
      </div>

      {/* Charts organized in Tabs */}
      <Tabs value={chartTab} onValueChange={setChartTab} className="mb-6">
        <TabsList>
          <TabsTrigger value="radar">Radar</TabsTrigger>
          <TabsTrigger value="scatter">Cost vs LOC</TabsTrigger>
          <TabsTrigger value="trend">Usage Trend</TabsTrigger>
        </TabsList>

        <TabsContent value="radar">
          <ChartContainer
            title="Model Comparison (Top 4) - Normalized metrics (0-100)"
            height={288}
            isLoading={isLoading}
            isEmpty={radarData.length === 0 || top4Models.length === 0}
            emptyMessage="Not enough data for radar comparison"
          >
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
          </ChartContainer>
        </TabsContent>

        <TabsContent value="scatter">
          <ChartContainer
            title="Cost vs LOC per Session - Each point is a session"
            height={288}
            isLoading={isLoading}
            isEmpty={scatterByModel.size === 0}
            emptyMessage="No scatter data available"
          >
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
          </ChartContainer>
        </TabsContent>

        <TabsContent value="trend">
          <ChartContainer
            title="Model Usage Over Time - Sessions per day by model"
            height={288}
            isLoading={isLoading}
            isEmpty={areaData.points.length === 0}
            emptyMessage="No usage trend data available"
          >
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
          </ChartContainer>
        </TabsContent>
      </Tabs>
    </PageLayout>
  )
}
