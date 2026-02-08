import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ReferenceLine, ReferenceDot,
} from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { ErrorState } from '@/components/composite/ErrorState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { useDateRange } from '@/hooks/useDateRange'
import { useCostAnalysis, useCostAnomalies, useCumulativeCost } from '@/api/cost'
import { BudgetTracker } from '@/components/BudgetTracker'
import { CacheCalculator } from '@/components/CacheCalculator'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { TOOLTIP_STYLE } from '@/lib/chartConfig'

const TOKEN_COLORS = {
  input: 'var(--color-token-input)',
  output: 'var(--color-token-output)',
  cache_read: 'var(--color-token-cache-read)',
  cache_write: 'var(--color-token-cache-write)',
}

export default function CostPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useCostAnalysis(dateRange)
  const { data: anomalies } = useCostAnomalies(dateRange)
  const { data: cumulative } = useCumulativeCost(dateRange)
  const [budget] = useLocalStorage('ccwap:monthly-budget', 0)

  if (error) return <ErrorState message={error.message} />

  if (isLoading || !data) {
    return (
      <PageLayout title="Cost Analysis" subtitle="Detailed cost breakdowns and forecasting">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  const { summary, by_token_type, by_model, trend, by_project, cache_savings, forecast } = data
  const anomalyPoints = anomalies?.filter(a => a.is_anomaly) ?? []
  const anomalyThreshold = anomalies && anomalies.length > 0 ? anomalies[0].threshold : 0

  const tokenTypeData = [
    { name: 'Input', value: by_token_type.input_cost, color: TOKEN_COLORS.input },
    { name: 'Output', value: by_token_type.output_cost, color: TOKEN_COLORS.output },
    { name: 'Cache Read', value: by_token_type.cache_read_cost, color: TOKEN_COLORS.cache_read },
    { name: 'Cache Write', value: by_token_type.cache_write_cost, color: TOKEN_COLORS.cache_write },
  ].filter(d => d.value > 0)

  return (
    <PageLayout
      title="Cost Analysis"
      subtitle="Detailed cost breakdowns and forecasting"
      actions={
        <ExportDropdown
          page="cost"
          getData={() => [
            ...trend.map(t => ({ date: t.date, cost: t.cost })),
            ...by_model.map(m => ({ type: 'by_model', model: m.model, cost: m.cost })),
            ...by_project.map(p => ({ type: 'by_project', project: p.project_display, cost: p.cost })),
          ]}
        />
      }
    >
      {/* Summary Cards */}
      <MetricCardGrid className="mb-6">
        <MetricCard title="Total Cost" value={formatCurrency(summary.total_cost)} />
        <MetricCard title="Avg Daily" value={formatCurrency(summary.avg_daily_cost)} />
        <MetricCard title="Today" value={formatCurrency(summary.cost_today)} />
        <MetricCard title="Projected Monthly" value={formatCurrency(summary.projected_monthly)} />
      </MetricCardGrid>

      {/* Forecast */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">Spend Forecast</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div><span className="text-xs text-muted-foreground">Daily Avg</span><p className="font-mono text-lg">{formatCurrency(forecast.daily_avg)}</p></div>
            <div><span className="text-xs text-muted-foreground">7-Day</span><p className="font-mono text-lg">{formatCurrency(forecast.projected_7d)}</p></div>
            <div><span className="text-xs text-muted-foreground">14-Day</span><p className="font-mono text-lg">{formatCurrency(forecast.projected_14d)}</p></div>
            <div><span className="text-xs text-muted-foreground">30-Day</span><p className="font-mono text-lg">{formatCurrency(forecast.projected_30d)}</p></div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Cost Trend */}
        <ChartContainer
          title="Cost Trend"
          height={256}
          isEmpty={trend.length === 0}
          emptyMessage="No cost trend data"
        >
          <AreaChart data={trend}>
            <defs>
              <linearGradient id="costTrendGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" width={50} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v != null ? formatCurrency(v) : '', 'Cost']} />
            <Area type="monotone" dataKey="cost" stroke="var(--color-chart-1)" fill="url(#costTrendGrad)" strokeWidth={2} isAnimationActive={trend.length < 365} />
          </AreaChart>
        </ChartContainer>

        {/* Cost by Token Type */}
        <ChartContainer
          title="Cost by Token Type"
          height={192}
          isEmpty={tokenTypeData.length === 0}
          emptyMessage="No token type data"
        >
          <PieChart>
            <Pie data={tokenTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} strokeWidth={0}>
              {tokenTypeData.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Pie>
            <Tooltip contentStyle={{ ...TOOLTIP_STYLE }} formatter={(v: any) => [v != null ? formatCurrency(v) : '']} />
          </PieChart>
        </ChartContainer>
      </div>

      {/* Token type legend (below chart container) */}
      {tokenTypeData.length > 0 && (
        <div className="flex flex-wrap gap-3 -mt-4 mb-6 ml-4">
          {tokenTypeData.map(d => (
            <span key={d.name} className="text-xs flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
              {d.name}: {formatCurrency(d.value)}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Cost by Model */}
        <ChartContainer
          title="Cost by Model"
          height={256}
          isEmpty={by_model.length === 0}
          emptyMessage="No model data"
        >
          <BarChart data={by_model.slice(0, 10)} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" />
            <YAxis type="category" dataKey="model" tick={{ fontSize: 10 }} width={120} stroke="var(--color-muted-foreground)" />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v != null ? formatCurrency(v) : '', 'Cost']} />
            <Bar dataKey="cost" fill="var(--color-chart-1)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ChartContainer>

        {/* Cost by Project */}
        <ChartContainer
          title="Cost by Project (Top 10)"
          height={256}
          isEmpty={by_project.length === 0}
          emptyMessage="No project data"
        >
          <BarChart data={by_project.slice(0, 10)} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" />
            <YAxis type="category" dataKey="project_display" tick={{ fontSize: 10 }} width={120} stroke="var(--color-muted-foreground)" />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v != null ? formatCurrency(v) : '', 'Cost']} />
            <Bar dataKey="cost" fill="var(--color-chart-2)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ChartContainer>
      </div>

      {/* Cache Savings */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">Cache Savings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div><span className="text-xs text-muted-foreground">Cache Hit Rate</span><p className="font-mono text-lg">{formatPercent(cache_savings.cache_hit_rate)}</p></div>
            <div><span className="text-xs text-muted-foreground">Estimated Savings</span><p className="font-mono text-lg text-green-500">{formatCurrency(cache_savings.estimated_savings)}</p></div>
            <div><span className="text-xs text-muted-foreground">Cost w/o Cache</span><p className="font-mono text-lg">{formatCurrency(cache_savings.cost_without_cache)}</p></div>
            <div><span className="text-xs text-muted-foreground">Actual Cost</span><p className="font-mono text-lg">{formatCurrency(cache_savings.actual_cost)}</p></div>
          </div>
        </CardContent>
      </Card>

      {/* Budget Tracker */}
      <div className="mb-6">
        <BudgetTracker spent={summary.cost_this_month} />
      </div>

      {/* Anomaly Detection */}
      {anomalies && anomalies.length > 0 && (
        <div className="mb-6">
          <ChartContainer
            title="Anomaly Detection"
            height={256}
          >
            <AreaChart data={anomalies}>
              <defs>
                <linearGradient id="anomalyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" width={50} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [formatCurrency(v ?? 0), 'Cost']} />
              <Area type="monotone" dataKey="cost" stroke="var(--color-chart-1)" fill="url(#anomalyGrad)" strokeWidth={2} isAnimationActive={anomalies.length < 365} />
              {anomalyThreshold > 0 && (
                <ReferenceLine y={anomalyThreshold} stroke="var(--color-chart-4)" strokeDasharray="5 5" label={{ value: 'Threshold', position: 'right', fill: 'var(--color-muted-foreground)', fontSize: 10 }} />
              )}
              {anomalyPoints.map((a) => (
                <ReferenceDot key={a.date} x={a.date} y={a.cost} r={5} fill="var(--color-destructive, #ef4444)" stroke="none" />
              ))}
            </AreaChart>
          </ChartContainer>
          {anomalyPoints.length > 0 && (
            <p className="text-xs text-muted-foreground mt-2 ml-4">
              {anomalyPoints.length} anomal{anomalyPoints.length === 1 ? 'y' : 'ies'} detected above {formatCurrency(anomalyThreshold)} threshold
            </p>
          )}
        </div>
      )}

      {/* Cumulative Cost */}
      {cumulative && cumulative.length > 0 && (
        <div className="mb-6">
          <ChartContainer
            title="Cumulative Cost"
            height={256}
          >
            <AreaChart data={cumulative}>
              <defs>
                <linearGradient id="cumulativeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" width={60} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, name: any) => [formatCurrency(v ?? 0), name === 'cumulative' ? 'Cumulative' : 'Daily']} />
              <Area type="monotone" dataKey="cumulative" stroke="var(--color-chart-2)" fill="url(#cumulativeGrad)" strokeWidth={2} name="cumulative" isAnimationActive={cumulative.length < 365} />
              {budget > 0 && (
                <ReferenceLine y={budget} stroke="var(--color-chart-4)" strokeDasharray="5 5" label={{ value: `Budget: ${formatCurrency(budget)}`, position: 'right', fill: 'var(--color-muted-foreground)', fontSize: 10 }} />
              )}
            </AreaChart>
          </ChartContainer>
        </div>
      )}

      {/* Cache What-If Calculator */}
      <div className="mb-6">
        <CacheCalculator dateRange={dateRange} />
      </div>
    </PageLayout>
  )
}
