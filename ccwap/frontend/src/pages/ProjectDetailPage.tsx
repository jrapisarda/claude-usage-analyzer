import { useParams, Link } from 'react-router'
import { useDateRange } from '@/hooks/useDateRange'
import { useProjectDetail } from '@/api/projects'
import { PageLayout } from '@/components/PageLayout'
import { MetricCard } from '@/components/ui/MetricCard'
import { ChartCard } from '@/components/ui/ChartCard'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'
import { formatCurrency, formatNumber } from '@/lib/utils'
import { ArrowLeft } from 'lucide-react'

export default function ProjectDetailPage() {
  const { path } = useParams<{ path: string }>()
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useProjectDetail(path || '', dateRange)

  if (isLoading) return <LoadingState message="Loading project details..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  return (
    <div>
      {/* Back link outside PageLayout since subtitle only accepts string */}
      <div className="px-6 pt-4">
        <Link
          to="/projects"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3 w-3" /> Back to Projects
        </Link>
      </div>

      <PageLayout
        title={data.project_display}
        subtitle={`${formatNumber(data.total_sessions)} sessions | ${formatCurrency(data.total_cost)} total cost | ${formatNumber(data.total_loc)} LOC`}
      >
        {/* Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          <MetricCard title="Total Cost" value={formatCurrency(data.total_cost)} />
          <MetricCard title="Sessions" value={formatNumber(data.total_sessions)} />
          <MetricCard title="Lines of Code" value={formatNumber(data.total_loc)} />
        </div>

        {/* Cost Trend + Languages */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <ChartCard title="Cost Trend">
            {data.cost_trend.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.cost_trend}>
                    <defs>
                      <linearGradient id="projCostGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
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
                      tickFormatter={(v) => `$${v.toFixed(2)}`}
                      stroke="var(--color-muted-foreground)"
                      width={50}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(v: number | undefined) => [v != null ? formatCurrency(v) : '', 'Cost']}
                    />
                    <Area
                      type="monotone"
                      dataKey="cost"
                      stroke={CHART_COLORS[0]}
                      fill="url(#projCostGrad)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No cost data</p>
            )}
          </ChartCard>

          <ChartCard title="Languages">
            {data.languages.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.languages}
                      dataKey="loc_written"
                      nameKey="language"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                      label={({ name }: any) => name ?? ''}
                    >
                      {data.languages.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No language data</p>
            )}
          </ChartCard>
        </div>

        {/* Tools + Branches */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <ChartCard title="Top Tools">
            {data.tools.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.tools.slice(0, 10)} layout="vertical" margin={{ left: 60 }}>
                    <XAxis type="number" tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
                    <YAxis
                      type="category"
                      dataKey="tool_name"
                      tick={{ fontSize: 10 }}
                      width={55}
                      stroke="var(--color-muted-foreground)"
                    />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="count" fill={CHART_COLORS[1]} name="Calls" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No tool data</p>
            )}
          </ChartCard>

          <ChartCard title="Branches">
            {data.branches.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.branches}>
                    <XAxis
                      dataKey="branch"
                      tick={{ fontSize: 9 }}
                      interval={0}
                      angle={-20}
                      textAnchor="end"
                      height={50}
                      stroke="var(--color-muted-foreground)"
                    />
                    <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="sessions" fill={CHART_COLORS[2]} name="Sessions" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="cost" fill={CHART_COLORS[3]} name="Cost" radius={[4, 4, 0, 0]} />
                    <Legend />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No branch data</p>
            )}
          </ChartCard>
        </div>

        {/* Sessions List */}
        <ChartCard title="Sessions" subtitle={`${data.sessions.length} most recent`}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Session</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Started</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">Cost</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">Turns</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">LOC</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Model</th>
                </tr>
              </thead>
              <tbody>
                {data.sessions.map(s => (
                  <tr key={s.session_id} className="border-b border-border hover:bg-accent/10">
                    <td className="px-3 py-2">
                      <Link to={`/sessions/${s.session_id}`} className="font-mono text-primary hover:underline">
                        {s.session_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{s.start_time?.slice(0, 16) || 'N/A'}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatCurrency(s.total_cost)}</td>
                    <td className="px-3 py-2 text-right">{s.turn_count}</td>
                    <td className="px-3 py-2 text-right">{formatNumber(s.loc_written)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{s.model_default}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </PageLayout>
    </div>
  )
}
