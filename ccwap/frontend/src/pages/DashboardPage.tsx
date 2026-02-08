import { useMemo } from 'react'
import { Link } from 'react-router'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { PageLayout } from '@/components/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import { useDashboard, useDashboardDeltas, useActivityCalendar } from '@/api/dashboard'
import type { ActivityDay } from '@/api/dashboard'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { MetricCard } from '@/components/ui/MetricCard'
import { HeatmapGrid } from '@/components/charts/HeatmapGrid'
import type { HeatmapDataPoint } from '@/components/charts/HeatmapGrid'
import { formatCurrency, formatNumber, formatPercent, formatDuration, toDateStr } from '@/lib/utils'
import { ExportDropdown } from '@/components/ExportDropdown'

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

  if (isLoading) return <LoadingState message="Loading dashboard..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

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
      actions={
        <ExportDropdown
          page="dashboard"
          getData={() => [
            { metric: 'Sessions', value: vitals.sessions },
            { metric: 'Cost', value: vitals.cost },
            { metric: 'LOC Written', value: vitals.loc_written },
            { metric: 'Error Rate', value: vitals.error_rate },
            ...top_projects.map(p => ({ metric: `Project: ${p.project_display}`, value: p.cost, sessions: p.sessions, loc: p.loc_written })),
          ]}
        />
      }
    >
      {/* Vitals Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Sessions"
          value={formatNumber(vitals.sessions)}
          subtitle={`${formatNumber(vitals.user_turns)} user turns`}
          delta={sessionsDelta?.pct_change}
          deltaLabel={sessionsDelta ? `${sessionsDelta.pct_change > 0 ? '+' : ''}${sessionsDelta.pct_change.toFixed(1)}%` : undefined}
        />
        <MetricCard
          title="Total Cost"
          value={formatCurrency(vitals.cost)}
          delta={costDelta?.pct_change}
          deltaLabel={costDelta ? `${costDelta.pct_change > 0 ? '+' : ''}${costDelta.pct_change.toFixed(1)}%` : undefined}
          isLowerBetter
        />
        <MetricCard
          title="LOC Written"
          value={formatNumber(vitals.loc_written)}
          delta={locDelta?.pct_change}
          deltaLabel={locDelta ? `${locDelta.pct_change > 0 ? '+' : ''}${locDelta.pct_change.toFixed(1)}%` : undefined}
        />
        <MetricCard
          title="Error Rate"
          value={formatPercent(vitals.error_rate)}
          delta={errorRateDelta?.pct_change}
          deltaLabel={errorRateDelta ? `${errorRateDelta.pct_change > 0 ? '+' : ''}${errorRateDelta.pct_change.toFixed(1)}%` : undefined}
          isLowerBetter
        />
      </div>

      {/* Activity Calendar */}
      {activityDays && activityDays.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Activity (last 90 days)</h3>
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
        </div>
      )}

      {/* 7-Day Sparkline */}
      {sparkline_7d.length > 1 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">7-Day Cost</h3>
          <div className="h-16">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkline_7d}>
                <defs>
                  <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="value" stroke="var(--color-chart-1)" fill="url(#sparkGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Cost Trend Chart */}
        {cost_trend.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Cost Trend</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={cost_trend}>
                  <defs>
                    <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `$${v}`} stroke="var(--color-muted-foreground)" width={50} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--color-card)', color: 'var(--color-card-foreground)', border: '1px solid var(--color-border)', borderRadius: '6px' }}
                    labelStyle={{ color: 'var(--color-foreground)' }}
                    formatter={(v: number | undefined) => [v != null ? formatCurrency(v) : '', 'Cost']}
                  />
                  <Area type="monotone" dataKey="cost" stroke="var(--color-chart-1)" fill="url(#costGrad)" strokeWidth={2} isAnimationActive={cost_trend.length < 365} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Top Projects */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Top Projects</h3>
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
        </div>
      </div>

      {/* Recent Sessions */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Recent Sessions</h3>
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
                  {s.is_agent && <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">agent</span>}
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
      </div>
    </PageLayout>
  )
}
