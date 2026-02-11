import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ScatterChart, Scatter, ZAxis } from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { ErrorState } from '@/components/composite/ErrorState'
import { useDateRange } from '@/hooks/useDateRange'
import { useReliability } from '@/api/advanced'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'

export default function ReliabilityPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useReliability(dateRange)

  const heatmapByPair = useMemo(() => {
    const heatmap = data?.heatmap ?? []
    const max = Math.max(...heatmap.map(h => h.errors), 1)
    return heatmap.slice(0, 40).map(h => ({
      ...h,
      intensity: h.errors / max,
    }))
  }, [data?.heatmap])

  if (error) return <ErrorState message={error.message} />
  if (isLoading || !data) {
    return (
      <PageLayout title="Reliability" subtitle="What breaks, where, and at what cost">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  return (
    <PageLayout title="Reliability" subtitle="What breaks, where, and at what cost">
      <MetricCardGrid className="mb-6">
        <MetricCard title="Tool Calls" value={formatNumber(data.summary.total_tool_calls)} />
        <MetricCard title="Errors" value={formatNumber(data.summary.total_errors)} />
        <MetricCard title="Error Rate" value={formatPercent(data.summary.error_rate)} />
        <MetricCard title="Error Cost" value={formatCurrency(data.summary.error_cost)} />
      </MetricCardGrid>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartContainer title="Pareto: Failing Tools" height={280} isEmpty={data.pareto_tools.length === 0}>
          <BarChart data={data.pareto_tools}>
            <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="count" fill={CHART_COLORS[0]} name="Errors" />
          </BarChart>
        </ChartContainer>
        <ChartContainer title="Pareto: Error Categories by Cost" height={280} isEmpty={data.heatmap.length === 0}>
          <ScatterChart>
            <XAxis type="number" dataKey="errors" name="Errors" tick={{ fontSize: 10 }} />
            <YAxis type="number" dataKey="error_cost" name="Error Cost" tick={{ fontSize: 10 }} />
            <ZAxis type="number" dataKey="errors" range={[30, 220]} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, n: any) => [n === 'error_cost' ? formatCurrency(v ?? 0) : formatNumber(v ?? 0), n]} />
            <Scatter data={data.heatmap.slice(0, 80)} fill={CHART_COLORS[2]} />
          </ScatterChart>
        </ChartContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartContainer title="Top Failing Workflows" height={280} isEmpty={data.top_failing_workflows.length === 0}>
          <BarChart data={data.top_failing_workflows.slice(0, 12)} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="workflow" width={140} tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="failures" fill={CHART_COLORS[1]} />
          </BarChart>
        </ChartContainer>
        <ChartContainer title="Failure Distribution by Branch" height={280} isEmpty={data.by_branch.length === 0}>
          <BarChart data={data.by_branch}>
            <XAxis dataKey="branch" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="errors" fill={CHART_COLORS[3]} name="Errors" />
          </BarChart>
        </ChartContainer>
      </div>

      <div className="rounded-md border border-border overflow-hidden">
        <div className="px-4 py-2 border-b border-border text-sm font-medium text-muted-foreground">
          Reliability Heatmap (Tool x Error Category)
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-left">Tool</th>
                <th className="px-3 py-2 text-left">Category</th>
                <th className="px-3 py-2 text-right">Errors</th>
                <th className="px-3 py-2 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {heatmapByPair.map((row, idx) => (
                <tr
                  key={`${row.tool_name}-${row.error_category}-${idx}`}
                  style={{ backgroundColor: `rgba(239, 68, 68, ${Math.min(0.08 + row.intensity * 0.35, 0.45)})` }}
                  className="border-b border-border/60"
                >
                  <td className="px-3 py-2 font-mono text-xs">{row.tool_name}</td>
                  <td className="px-3 py-2">{row.error_category}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatNumber(row.errors)}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatCurrency(row.error_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </PageLayout>
  )
}
