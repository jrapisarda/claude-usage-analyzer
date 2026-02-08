import { useMemo } from 'react'
import { Link } from 'react-router'
import { AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { ErrorState } from '@/components/composite/ErrorState'
import { EmptyState } from '@/components/composite/EmptyState'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useDateRange } from '@/hooks/useDateRange'
import { useDashboard, useDashboardDeltas, useActivityCalendar } from '@/api/dashboard'
import type { ActivityDay } from '@/api/dashboard'
import { HeatmapGrid } from '@/components/charts/HeatmapGrid'
import type { HeatmapDataPoint } from '@/components/charts/HeatmapGrid'
import { formatCurrency, formatNumber, formatPercent, formatDuration, toDateStr } from '@/lib/utils'
import { TOOLTIP_STYLE } from '@/lib/chartConfig'

/** Convert ActivityDay[] into heatmap data for a 7-row x 13-col grid (days of week x weeks). */
function buildCalendarHeatmap(days: ActivityDay[]): {
  data: HeatmapDataPoint[]
  maxValue: number
  colLabels: string[]
} {
  if (days.length === 0) return { data: [], maxValue: 0, colLabels: [] }

  // Sort days ascending by date
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date))

  // Find the date of the earliest entry and align to the Monday of that week
  const firstDate = new Date(sorted[0].date + 'T00:00:00')
  const dayOfWeek = (firstDate.getDay() + 6) % 7 // 0=Mon, 6=Sun
  const startMonday = new Date(firstDate)
  startMonday.setDate(startMonday.getDate() - dayOfWeek)

  // Build a map of date -> sessions
  const dateMap = new Map<string, number>()
  let maxValue = 0
  for (const d of sorted) {
    dateMap.set(d.date, d.sessions)
    if (d.sessions > maxValue) maxValue = d.sessions
  }

  // Generate 13 columns (weeks) of labels and data points
  const colLabels: string[] = []
  const data: HeatmapDataPoint[] = []
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  for (let week = 0; week < 13; week++) {
    // Column label: show month abbreviation if the Monday of this week is in a new month, else empty
    const weekStart = new Date(startMonday)
    weekStart.setDate(weekStart.getDate() + week * 7)

    if (week === 0) {
      colLabels.push(monthNames[weekStart.getMonth()])
    } else {
      const prevWeekStart = new Date(startMonday)
      prevWeekStart.setDate(prevWeekStart.getDate() + (week - 1) * 7)
      if (weekStart.getMonth() !== prevWeekStart.getMonth()) {
        colLabels.push(monthNames[weekStart.getMonth()])
      } else {
        colLabels.push('')
      }
    }

    // Fill data for each day of the week (Mon=0 through Sun=6)
    for (let dow = 0; dow < 7; dow++) {
      const cellDate = new Date(startMonday)
      cellDate.setDate(cellDate.getDate() + week * 7 + dow)
      const dateStr = toDateStr(cellDate)
      const value = dateMap.get(dateStr) ?? 0
      if (value > 0) {
        data.push({ row: dow, col: week, value })
      }
    }
  }

  return { data, maxValue, colLabels }
}

const ROW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export default function DashboardPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useDashboard(dateRange)
  const { data: deltas } = useDashboardDeltas(dateRange)
  const { data: activityDays } = useActivityCalendar(90)

  const calendarHeatmap = useMemo(
    () => buildCalendarHeatmap(activityDays ?? []),
    [activityDays],
  )

  if (error) return <ErrorState message={error.message} />

  if (isLoading || !data) {
    return (
      <PageLayout title="Dashboard" subtitle="Overview of your Claude Code usage">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  const { vitals, sparkline_7d, top_projects, cost_trend, recent_sessions } = data

  // Build a lookup for deltas by metric name
  const deltaMap = new Map<string, { pct_change: number }>(
    (deltas ?? []).map(d => [d.metric, { pct_change: d.pct_change }])
  )

  const sessionsDelta = deltaMap.get('sessions')
  const costDelta = deltaMap.get('cost')
  const locDelta = deltaMap.get('loc_written')
  const errorRateDelta = deltaMap.get('error_rate')

  return (
    <PageLayout
      title="Dashboard"
      subtitle="Overview of your Claude Code usage"
    >
      {/* Vitals Strip */}
      <MetricCardGrid className="mb-6">
        <MetricCard
          title="Sessions"
          value={formatNumber(vitals.sessions)}
          subtitle={`${formatNumber(vitals.user_turns)} user turns`}
          delta={sessionsDelta ? { value: sessionsDelta.pct_change } : undefined}
        />
        <MetricCard
          title="Total Cost"
          value={formatCurrency(vitals.cost)}
          delta={costDelta ? { value: costDelta.pct_change } : undefined}
        />
        <MetricCard
          title="LOC Written"
          value={formatNumber(vitals.loc_written)}
          delta={locDelta ? { value: locDelta.pct_change } : undefined}
        />
        <MetricCard
          title="Error Rate"
          value={formatPercent(vitals.error_rate)}
          delta={errorRateDelta ? { value: errorRateDelta.pct_change } : undefined}
        />
      </MetricCardGrid>

      {/* Activity Calendar */}
      {activityDays && activityDays.length > 0 && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Activity (last 90 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <HeatmapGrid
                data={calendarHeatmap.data}
                maxValue={calendarHeatmap.maxValue}
                rowLabels={ROW_LABELS}
                colLabels={calendarHeatmap.colLabels}
                cellSize={18}
                formatValue={(v) => `${v} session${v !== 1 ? 's' : ''}`}
                formatTooltip={(row, col, value) =>
                  `${row}${col ? ` ${col}` : ''}: ${value} session${value !== 1 ? 's' : ''}`
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* 7-Day Sparkline */}
      {sparkline_7d.length > 1 && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">7-Day Cost</CardTitle>
          </CardHeader>
          <CardContent className="h-16">
            <ChartContainer height={64} className="border-0 p-0">
              <AreaChart data={sparkline_7d}>
                <defs>
                  <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="value" stroke="var(--color-chart-1)" fill="url(#sparkGrad)" strokeWidth={2} />
              </AreaChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Cost Trend Chart */}
        <ChartContainer
          title="Cost Trend"
          height={256}
          isEmpty={cost_trend.length === 0}
          emptyMessage="No cost trend data"
        >
          <AreaChart data={cost_trend}>
            <defs>
              <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" width={50} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(v: any) => [v != null ? formatCurrency(v) : '', 'Cost']}
            />
            <Area type="monotone" dataKey="cost" stroke="var(--color-chart-1)" fill="url(#costGrad)" strokeWidth={2} isAnimationActive={cost_trend.length < 365} />
          </AreaChart>
        </ChartContainer>

        {/* Top Projects */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Top Projects</CardTitle>
          </CardHeader>
          <CardContent>
            {top_projects.length === 0 ? (
              <EmptyState message="No project data" />
            ) : (
              <div className="space-y-1">
                {top_projects.map(p => (
                  <Link
                    key={p.project_path}
                    to={`/projects?search=${encodeURIComponent(p.project_display)}`}
                    className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="truncate font-medium">{p.project_display}</span>
                      <span className="text-xs text-muted-foreground shrink-0">{p.sessions} sessions</span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-xs text-muted-foreground">{formatNumber(p.loc_written)} LOC</span>
                      <span className="font-mono text-sm">{formatCurrency(p.cost)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Sessions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">Recent Sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {recent_sessions.length === 0 ? (
            <EmptyState message="No sessions" />
          ) : (
            <div className="space-y-1">
              {recent_sessions.map(s => (
                <Link
                  key={s.session_id}
                  to={`/sessions/${s.session_id}`}
                  className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="truncate font-medium">{s.project_display || 'Unknown'}</span>
                    {s.is_agent && (
                      <Badge variant="secondary" className="bg-purple-500/20 text-purple-400 text-[10px] px-1.5 py-0.5">
                        agent
                      </Badge>
                    )}
                    <span className="text-xs text-muted-foreground shrink-0">{s.model}</span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-muted-foreground">{s.turns} turns</span>
                    <span className="text-xs text-muted-foreground">{formatDuration(s.duration_seconds)}</span>
                    <span className="font-mono text-sm">{formatCurrency(s.cost)}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </PageLayout>
  )
}
