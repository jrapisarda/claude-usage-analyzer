import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ReferenceDot } from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ErrorState } from '@/components/composite/ErrorState'
import { useDateRange } from '@/hooks/useDateRange'
import { useBranchHealth } from '@/api/advanced'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

type MetricKey = 'cost' | 'errors' | 'loc_written' | 'cache_hit_rate'

export default function BranchHealthPage() {
  const { dateRange } = useDateRange()
  const [branchFilter, setBranchFilter] = useState('')
  const [metric, setMetric] = useState<MetricKey>('cost')

  const { data, isLoading, error } = useBranchHealth(dateRange, branchFilter.trim() || null)

  const branchNames = useMemo(() => (data?.branches ?? []).map(b => b.branch), [data?.branches])
  const pivot = useMemo(() => {
    if (!data) return []
    const byDate = new Map<string, Record<string, any>>()
    for (const point of data.trend) {
      if (!byDate.has(point.date)) byDate.set(point.date, { date: point.date })
      byDate.get(point.date)![point.branch] = point[metric]
    }
    return fillZeros(
      Array.from(byDate.values()).sort((a, b) => String(a.date).localeCompare(String(b.date))),
      branchNames
    )
  }, [data, branchNames, metric])

  const metricFormatter = (v: number) => (
    metric === 'cost' ? formatCurrency(v)
      : metric === 'cache_hit_rate' ? formatPercent(v)
        : formatNumber(v)
  )

  const summaryTotals = useMemo(() => {
    const branches = data?.branches ?? []
    const totalCost = branches.reduce((acc, b) => acc + b.cost, 0)
    const totalErrors = branches.reduce((acc, b) => acc + b.errors, 0)
    const totalLoc = branches.reduce((acc, b) => acc + b.loc_written, 0)
    const avgCache = branches.length > 0
      ? branches.reduce((acc, b) => acc + b.cache_hit_rate, 0) / branches.length
      : 0
    return { totalCost, totalErrors, totalLoc, avgCache }
  }, [data?.branches])

  if (error) return <ErrorState message={error.message} />
  if (isLoading || !data) {
    return (
      <PageLayout title="Branch Health" subtitle="Branch cost/quality/productivity before merge">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  return (
    <PageLayout title="Branch Health" subtitle="Branch cost/quality/productivity before merge">
      <MetricCardGrid className="mb-6">
        <MetricCard title="Branches" value={formatNumber(data.branches.length)} />
        <MetricCard title="Total Cost" value={formatCurrency(summaryTotals.totalCost)} />
        <MetricCard title="Total Errors" value={formatNumber(summaryTotals.totalErrors)} />
        <MetricCard title="Avg Cache Hit" value={formatPercent(summaryTotals.avgCache)} />
      </MetricCardGrid>

      <div className="rounded-md border border-border p-3 mb-4 flex items-center gap-3">
        <span className="text-xs text-muted-foreground">Branch Filter</span>
        <Input
          value={branchFilter}
          onChange={e => setBranchFilter(e.target.value)}
          placeholder="main, develop, feat-x (comma-separated)"
          className="max-w-sm h-8"
        />
        <Tabs value={metric} onValueChange={v => setMetric(v as MetricKey)}>
          <TabsList>
            <TabsTrigger value="cost">Cost</TabsTrigger>
            <TabsTrigger value="errors">Errors</TabsTrigger>
            <TabsTrigger value="loc_written">LOC</TabsTrigger>
            <TabsTrigger value="cache_hit_rate">Cache Hit</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <ChartContainer title="Branch Trend Overlay" height={320} isEmpty={pivot.length === 0}>
        <LineChart data={pivot}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: any) => metricFormatter(Number(v ?? 0))} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => metricFormatter(Number(v ?? 0))} />
          <Legend />
          {branchNames.map((branch, idx) => (
            <Line
              key={branch}
              dataKey={branch}
              stroke={CHART_COLORS[idx % CHART_COLORS.length]}
              strokeWidth={2}
              dot={false}
              name={branch}
            />
          ))}
          {data.anomalies.map((a, idx) => (
            <ReferenceDot
              key={`${a.branch}-${a.date}-${idx}`}
              x={a.date}
              y={metric === 'cost' ? a.cost : 0}
              r={metric === 'cost' ? 4 : 0}
              fill="var(--color-destructive, #ef4444)"
            />
          ))}
        </LineChart>
      </ChartContainer>

      <div className="rounded-md border border-border overflow-hidden mt-6">
        <div className="px-4 py-2 border-b border-border text-sm font-medium text-muted-foreground">
          Branch Anomaly Markers
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2 text-left">Branch</th>
              <th className="px-3 py-2 text-right">Cost</th>
              <th className="px-3 py-2 text-right">Z-Score</th>
            </tr>
          </thead>
          <tbody>
            {data.anomalies.length === 0 ? (
              <tr><td className="px-3 py-3 text-muted-foreground" colSpan={4}>No anomalies detected.</td></tr>
            ) : data.anomalies.map((a, idx) => (
              <tr key={`${a.branch}-${a.date}-${idx}`} className="border-b border-border/60">
                <td className="px-3 py-2 font-mono">{a.date}</td>
                <td className="px-3 py-2">{a.branch}</td>
                <td className="px-3 py-2 text-right font-mono">{formatCurrency(a.cost)}</td>
                <td className="px-3 py-2 text-right font-mono">{a.zscore.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageLayout>
  )
}
