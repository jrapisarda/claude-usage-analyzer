import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  PieChart, Pie, Cell, AreaChart, Area, LineChart, Line,
} from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { ErrorState } from '@/components/composite/ErrorState'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useDateRange } from '@/hooks/useDateRange'
import { useAnalytics, useThinkingTrend, useCacheTrend } from '@/api/analytics'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'
import { formatNumber, formatPercent } from '@/lib/utils'

export default function AnalyticsPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useAnalytics(dateRange)
  const { data: thinkingTrend } = useThinkingTrend(dateRange)
  const { data: cacheTrend } = useCacheTrend(dateRange)

  if (error) return <ErrorState message={error.message} />

  if (isLoading || !data) {
    return (
      <PageLayout title="Deep Analytics" subtitle="Advanced metrics and analysis">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  const { thinking, truncation, sidechains, cache_tiers, branches, versions, skills_agents } = data

  return (
    <PageLayout title="Deep Analytics" subtitle="Advanced metrics and analysis">
      <Tabs defaultValue="thinking" className="space-y-6">
        <TabsList>
          <TabsTrigger value="thinking">Thinking</TabsTrigger>
          <TabsTrigger value="cache">Cache</TabsTrigger>
          <TabsTrigger value="sidechains">Sidechains</TabsTrigger>
          <TabsTrigger value="branches">Branches & Versions</TabsTrigger>
        </TabsList>

        {/* Thinking Tab */}
        <TabsContent value="thinking" className="space-y-6">
          <MetricCardGrid>
            <MetricCard title="Total Thinking" value={formatNumber(thinking.total_thinking_chars)} subtitle="characters" />
            <MetricCard title="Avg / Turn" value={formatNumber(thinking.avg_thinking_per_turn)} />
            <MetricCard title="Turns w/ Thinking" value={formatNumber(thinking.turns_with_thinking)} />
            <MetricCard title="Thinking Rate" value={formatPercent(thinking.thinking_rate)} />
          </MetricCardGrid>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartContainer
              title="Thinking by Model"
              height={256}
              isEmpty={thinking.by_model.length === 0}
              emptyMessage="No thinking data"
            >
              <BarChart data={thinking.by_model} layout="vertical" margin={{ left: 80 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
                <YAxis type="category" dataKey="model" tick={{ fontSize: 10 }} width={75} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => formatNumber(v ?? 0)} />
                <Bar dataKey="thinking_chars" fill={CHART_COLORS[0]} name="Thinking Chars" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ChartContainer>

            <ChartContainer
              title="Thinking Trend"
              height={288}
              isEmpty={!thinkingTrend || thinkingTrend.length === 0}
              emptyMessage="No trend data"
            >
              <AreaChart data={_aggregateThinkingByDate(thinkingTrend ?? [])}>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => formatNumber(v ?? 0)} />
                <Area type="monotone" dataKey="thinking_chars" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.2} />
              </AreaChart>
            </ChartContainer>
          </div>

          {/* Truncation */}
          <ChartContainer
            title={`Truncation Analysis (${truncation.total_turns} total turns)`}
            height={256}
            isEmpty={truncation.by_stop_reason.length === 0}
            emptyMessage="No truncation data"
          >
            <PieChart>
              <Pie
                data={truncation.by_stop_reason}
                dataKey="count"
                nameKey="stop_reason"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                label={({ name, percent }: any) => `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`}
              >
                {truncation.by_stop_reason.map((_: any, i: number) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend />
            </PieChart>
          </ChartContainer>
        </TabsContent>

        {/* Cache Tab */}
        <TabsContent value="cache" className="space-y-6">
          <MetricCardGrid className="lg:grid-cols-3">
            <MetricCard title="Ephemeral 5m" value={formatNumber(cache_tiers.ephemeral_5m_tokens)} subtitle="tokens" />
            <MetricCard title="Ephemeral 1h" value={formatNumber(cache_tiers.ephemeral_1h_tokens)} subtitle="tokens" />
            <MetricCard title="Standard Cache" value={formatNumber(cache_tiers.standard_cache_tokens)} subtitle="tokens" />
          </MetricCardGrid>

          <ChartContainer
            title="Cache Tier Trend"
            height={256}
            isEmpty={!cacheTrend || cacheTrend.length === 0}
            emptyMessage="No cache trend data"
          >
            <AreaChart data={fillZeros(cacheTrend ?? [], ['ephemeral_5m', 'ephemeral_1h', 'standard_cache'])}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => formatNumber(v ?? 0)} />
              <Area type="monotone" dataKey="ephemeral_5m" stackId="1" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.6} name="5min Ephemeral" />
              <Area type="monotone" dataKey="ephemeral_1h" stackId="1" stroke={CHART_COLORS[1]} fill={CHART_COLORS[1]} fillOpacity={0.6} name="1hr Ephemeral" />
              <Area type="monotone" dataKey="standard_cache" stackId="1" stroke={CHART_COLORS[2]} fill={CHART_COLORS[2]} fillOpacity={0.6} name="Standard Cache" />
              <Legend />
            </AreaChart>
          </ChartContainer>
        </TabsContent>

        {/* Sidechains Tab */}
        <TabsContent value="sidechains" className="space-y-6">
          <MetricCardGrid className="lg:grid-cols-2">
            <MetricCard title="Total Sidechains" value={formatNumber(sidechains.total_sidechains)} />
            <MetricCard title="Sidechain Rate" value={formatPercent(sidechains.sidechain_rate)} />
          </MetricCardGrid>

          <ChartContainer
            title="Sidechains by Project"
            height={256}
            isEmpty={sidechains.by_project.length === 0}
            emptyMessage="No sidechain data"
          >
            <BarChart data={sidechains.by_project.slice(0, 10)}>
              <XAxis dataKey="project" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="sidechains" fill={CHART_COLORS[3]} name="Sidechains" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ChartContainer>

          {/* Skills & Agents */}
          <MetricCardGrid className="lg:grid-cols-3">
            <MetricCard title="Agent Spawns" value={formatNumber(skills_agents.total_agent_spawns)} />
            <MetricCard title="Skill Invocations" value={formatNumber(skills_agents.total_skill_invocations)} />
            <MetricCard title="Agent Cost" value={`$${skills_agents.agent_cost.toFixed(4)}`} />
          </MetricCardGrid>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">Skills & Agents by Date</CardTitle>
            </CardHeader>
            <CardContent>
              {skills_agents.by_date.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border">
                        {Object.keys(skills_agents.by_date[0]).map(k => (
                          <th key={k} className="text-left px-3 py-2 font-medium text-muted-foreground">{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {skills_agents.by_date.slice(0, 20).map((row, i) => (
                        <tr key={i} className="border-b border-border hover:bg-accent/10">
                          {Object.values(row).map((v, j) => (
                            <td key={j} className="px-3 py-2 font-mono">{String(v ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="text-sm text-muted-foreground">No skills data</p>}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Branches & Versions Tab */}
        <TabsContent value="branches" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartContainer
              title="Branch Analytics"
              height={256}
              isEmpty={branches.branches.length === 0}
              emptyMessage="No branch data"
            >
              <BarChart data={branches.branches.slice(0, 10)} layout="vertical" margin={{ left: 80 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="branch" tick={{ fontSize: 10 }} width={75} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="cost" fill={CHART_COLORS[0]} name="Cost" radius={[0, 4, 4, 0]} />
                <Bar dataKey="sessions" fill={CHART_COLORS[1]} name="Sessions" radius={[0, 4, 4, 0]} />
                <Legend />
              </BarChart>
            </ChartContainer>

            <ChartContainer
              title="CC Version Impact"
              height={256}
              isEmpty={versions.versions.length === 0}
              emptyMessage="No version data"
            >
              <LineChart data={versions.versions}>
                <XAxis dataKey="version" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: any) => `$${(v ?? 0).toFixed(3)}`} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => `$${(v ?? 0).toFixed(4)}`} />
                <Line type="monotone" dataKey="avg_turn_cost" stroke={CHART_COLORS[4]} strokeWidth={2} dot={{ r: 3 }} name="Avg Turn Cost" />
              </LineChart>
            </ChartContainer>
          </div>
        </TabsContent>
      </Tabs>
    </PageLayout>
  )
}

/** Aggregate thinking trend data by date (sum across models) */
function _aggregateThinkingByDate(data: { date: string; thinking_chars: number }[]) {
  const map = new Map<string, number>()
  for (const d of data) {
    map.set(d.date, (map.get(d.date) || 0) + d.thinking_chars)
  }
  return Array.from(map, ([date, thinking_chars]) => ({ date, thinking_chars }))
    .sort((a, b) => a.date.localeCompare(b.date))
}
