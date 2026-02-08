import { useMemo } from 'react'
import {
  AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { PageLayout } from '@/components/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import { useWorkflows } from '@/api/workflows'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { MetricCard } from '@/components/ui/MetricCard'
import { ChartCard } from '@/components/ui/ChartCard'
import { AgentTreeView } from '@/components/charts/AgentTreeView'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'

const USER_TYPE_COLORS: Record<string, string> = {
  human: CHART_COLORS[0],
  agent: CHART_COLORS[2],
}

export default function WorkflowPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useWorkflows(dateRange)

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

  if (isLoading) return <LoadingState message="Loading workflow data..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  const { user_types, agent_trees, tool_sequences } = data

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
    >
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
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
      </div>

      {/* Donut + Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <ChartCard title="Session Breakdown" subtitle="Human vs Agent">
          {pieData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
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
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No session data</p>
          )}
        </ChartCard>

        <ChartCard title="Session Trend" subtitle="Stacked by user type over time">
          {trendPivoted.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
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
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No trend data</p>
          )}
        </ChartCard>
      </div>

      {/* Agent Trees + Tool Sequences */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Agent Session Trees" subtitle="Parent-child session hierarchy">
          <div className="max-h-96 overflow-y-auto">
            <AgentTreeView trees={agent_trees} />
          </div>
        </ChartCard>

        <ChartCard title="Tool Sequences" subtitle="Most common tool call patterns">
          {tool_sequences.length > 0 ? (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {tool_sequences.map((seq, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground w-6 text-right shrink-0">
                    {i + 1}.
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 flex-wrap">
                      {seq.sequence.map((tool, j) => (
                        <span key={j}>
                          <span className="text-xs font-mono bg-accent/50 px-1.5 py-0.5 rounded">
                            {tool}
                          </span>
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
          ) : (
            <p className="text-sm text-muted-foreground">No tool sequence data</p>
          )}
        </ChartCard>
      </div>
    </PageLayout>
  )
}
