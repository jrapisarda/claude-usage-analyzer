import { useMemo, useCallback } from 'react'
import {
  AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, Legend,
} from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import { useWorkflows } from '@/api/workflows'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { ErrorState } from '@/components/composite/ErrorState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { AgentTreeView } from '@/components/charts/AgentTreeView'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'

const USER_TYPE_COLORS: Record<string, string> = {
  human: CHART_COLORS[0],
  agent: CHART_COLORS[2],
}

export default function WorkflowPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error, refetch } = useWorkflows(dateRange)

  // Pivot the flat trend array into { date, human, agent } for stacked area
  const trendPivoted = useMemo(() => {
    if (!data?.user_type_trend) return []
    const byDate: Record<string, Record<string, number>> = {}
    for (const row of data.user_type_trend) {
      if (!byDate[row.date]) byDate[row.date] = {}
      byDate[row.date][row.user_type] = row.sessions
    }
    const pivoted = Object.entries(byDate)
      .map(([date, vals]) => ({ date, ...vals }))
      .sort((a, b) => a.date.localeCompare(b.date))
    return fillZeros(pivoted, ['human', 'agent'])
  }, [data?.user_type_trend])

  const getExportData = useCallback(() => {
    if (!data) return []
    return data.user_types.map(t => ({
      user_type: t.user_type,
      sessions: t.sessions,
      total_cost: t.total_cost,
      total_turns: t.total_turns,
    }))
  }, [data])

  if (error) return <ErrorState message={error.message} onRetry={() => refetch()} />

  const user_types = data?.user_types ?? []
  const agent_trees = data?.agent_trees ?? []
  const tool_sequences = data?.tool_sequences ?? []

  const totalSessions = user_types.reduce((s, t) => s + t.sessions, 0)
  const totalCost = user_types.reduce((s, t) => s + t.total_cost, 0)
  const agentType = user_types.find(t => t.user_type === 'agent')
  const humanType = user_types.find(t => t.user_type === 'human')
  const agentPct = totalSessions > 0 && agentType ? agentType.sessions / totalSessions : 0

  const pieData = user_types.map(t => ({
    name: t.user_type,
    value: t.sessions,
    color: USER_TYPE_COLORS[t.user_type] || CHART_COLORS[4],
  }))

  return (
    <PageLayout
      title="Workflows"
      subtitle="Human vs Agent sessions, agent trees, and tool patterns"
      actions={
        <ExportDropdown page="workflows" getData={getExportData} />
      }
    >
      {/* Summary cards */}
      <MetricCardGrid skeleton={isLoading} count={4} className="mb-6">
        {data && (
          <>
            <MetricCard title="Total Sessions" value={formatNumber(totalSessions)} />
            <MetricCard title="Total Cost" value={formatCurrency(totalCost)} />
            <MetricCard
              title="Human Sessions"
              value={formatNumber(humanType?.sessions ?? 0)}
              subtitle={`${formatCurrency(humanType?.total_cost ?? 0)} cost`}
            />
            <MetricCard
              title="Agent Sessions"
              value={formatNumber(agentType?.sessions ?? 0)}
              subtitle={`${formatPercent(agentPct)} of total`}
            />
          </>
        )}
      </MetricCardGrid>

      {/* Donut + Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <ChartContainer
          title="Session Breakdown - Human vs Agent"
          height={256}
          isLoading={isLoading}
          isEmpty={pieData.length === 0}
          emptyMessage="No session data"
        >
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={2}
              label={({ name, value, percent }: any) => `${name ?? ''}: ${value ?? 0} (${((percent ?? 0) * 100).toFixed(0)}%)`}
            >
              {pieData.map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend />
          </PieChart>
        </ChartContainer>

        <ChartContainer
          title="Session Trend - Stacked by user type"
          height={256}
          isLoading={isLoading}
          isEmpty={trendPivoted.length === 0}
          emptyMessage="No trend data"
        >
          <AreaChart data={trendPivoted}>
            <defs>
              <linearGradient id="humanGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="agentGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS[2]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={CHART_COLORS[2]} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={d => d.slice(5)}
              stroke="var(--color-muted-foreground)"
            />
            <YAxis
              tick={{ fontSize: 11 }}
              stroke="var(--color-muted-foreground)"
              allowDecimals={false}
            />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend />
            <Area
              type="monotone"
              dataKey="human"
              stackId="1"
              stroke={CHART_COLORS[0]}
              fill="url(#humanGrad)"
              strokeWidth={2}
              name="Human"
            />
            <Area
              type="monotone"
              dataKey="agent"
              stackId="1"
              stroke={CHART_COLORS[2]}
              fill="url(#agentGrad)"
              strokeWidth={2}
              name="Agent"
            />
          </AreaChart>
        </ChartContainer>
      </div>

      {/* Agent Trees + Tool Sequences */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Agent Session Trees</CardTitle>
            <CardDescription>Parent-child session hierarchy</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="animate-pulse rounded bg-primary/10 h-8 w-full" />
                ))}
              </div>
            ) : (
              <ScrollArea className="h-96">
                <AgentTreeView trees={agent_trees} />
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Tool Sequences</CardTitle>
            <CardDescription>Most common tool call patterns</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="animate-pulse rounded bg-primary/10 h-8 w-full" />
                ))}
              </div>
            ) : tool_sequences.length > 0 ? (
              <ScrollArea className="h-96">
                <div className="space-y-2">
                  {tool_sequences.map((seq, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground w-6 text-right shrink-0">
                        {i + 1}.
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1 flex-wrap">
                          {seq.sequence.map((tool, j) => (
                            <span key={j}>
                              <Badge variant="secondary" className="font-mono text-xs">
                                {tool}
                              </Badge>
                              {j < seq.sequence.length - 1 && (
                                <span className="text-muted-foreground mx-0.5">&rarr;</span>
                              )}
                            </span>
                          ))}
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-accent/30 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${seq.pct}%`,
                                backgroundColor: CHART_COLORS[1],
                              }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground shrink-0">
                            {seq.count}x ({seq.pct.toFixed(1)}%)
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <p className="text-sm text-muted-foreground">No tool sequence data</p>
            )}
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
