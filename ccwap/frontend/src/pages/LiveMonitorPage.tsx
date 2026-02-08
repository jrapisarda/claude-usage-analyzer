import { useMemo } from 'react'
import { Wifi, WifiOff, Activity } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { PageLayout } from '@/components/PageLayout'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useDashboard } from '@/api/dashboard'
import { MetricCard } from '@/components/ui/MetricCard'
import { CostTicker } from '@/components/ui/CostTicker'
import { ActiveSessionBadge } from '@/components/ui/ActiveSessionBadge'
import { formatNumber, cn } from '@/lib/utils'

function getWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/live`
}

function getTodayRange() {
  const today = new Date().toISOString().split('T')[0]
  return { from: today, to: today }
}

export default function LiveMonitorPage() {
  const { status, lastMessage, messages } = useWebSocket(getWsUrl())
  const { data: dashboardData } = useDashboard(getTodayRange())

  const etlMessages = useMemo(
    () => messages.filter(m => m.type === 'etl_update'),
    [messages]
  )

  const latestCostMessage = useMemo(
    () => messages.find(m => m.type === 'daily_cost_update'),
    [messages]
  )

  const latestSessionMessage = useMemo(
    () => messages.find(m => m.type === 'active_session'),
    [messages]
  )

  const totals = useMemo(() => {
    let turns = 0
    let toolCalls = 0
    let files = 0
    for (const m of etlMessages) {
      turns += m.turns_inserted || 0
      toolCalls += m.tool_calls_inserted || 0
      files += m.files_processed || 0
    }
    return { turns, toolCalls, files }
  }, [etlMessages])

  const sparklineData = useMemo(() => {
    return etlMessages.slice(0, 30).reverse().map((m, i) => ({
      i,
      turns: m.turns_inserted || 0,
    }))
  }, [etlMessages])

  const statusColor = status === 'connected' ? 'text-green-500' : status === 'connecting' ? 'text-yellow-500' : 'text-red-400'
  const StatusIcon = status === 'connected' ? Wifi : WifiOff

  return (
    <PageLayout title="Live Monitor" subtitle="Real-time session tracking">
      {/* Connection Status + Active Session */}
      <div className="flex items-center justify-between mb-6">
        <div className={cn("flex items-center gap-2 text-sm", statusColor)}>
          <StatusIcon className="h-4 w-4" />
          <span className="font-medium capitalize">{status}</span>
          {status === 'connected' && lastMessage && (
            <span className="text-muted-foreground ml-2">Last update: {lastMessage.timestamp ? new Date(lastMessage.timestamp).toLocaleTimeString() : 'N/A'}</span>
          )}
        </div>
        {latestSessionMessage && latestSessionMessage.project_display && (
          <ActiveSessionBadge
            projectDisplay={latestSessionMessage.project_display}
            gitBranch={latestSessionMessage.git_branch}
          />
        )}
      </div>

      {status !== 'connected' ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">
            {status === 'connecting' ? 'Connecting...' : 'Disconnected'}
          </h3>
          <p className="text-sm text-muted-foreground">
            {status === 'connecting'
              ? 'Establishing WebSocket connection to the server...'
              : 'WebSocket connection lost. Reconnecting automatically...'}
          </p>
        </div>
      ) : (
        <>
          {/* Today's Vitals Mini Dashboard */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Cost Today</p>
              <div className="mt-1">
                <CostTicker
                  targetCost={latestCostMessage?.cost_today ?? dashboardData?.vitals.cost ?? 0}
                />
              </div>
              {latestCostMessage && (
                <p className="text-xs text-muted-foreground mt-1">
                  {latestCostMessage.sessions_today} session{latestCostMessage.sessions_today !== 1 ? 's' : ''}
                </p>
              )}
            </div>
            <MetricCard
              title="Sessions Today"
              value={formatNumber(latestCostMessage?.sessions_today ?? dashboardData?.vitals.sessions ?? 0)}
            />
            <MetricCard
              title="Messages Today"
              value={formatNumber(dashboardData?.vitals.messages ?? 0)}
            />
            <MetricCard
              title="Error Rate"
              value={dashboardData?.vitals.error_rate != null ? `${(dashboardData.vitals.error_rate * 100).toFixed(1)}%` : '0.0%'}
            />
          </div>

          {/* Live Totals (this session's WebSocket data) */}
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <MetricCard title="Turns Received" value={formatNumber(totals.turns)} />
            <MetricCard title="Tool Calls" value={formatNumber(totals.toolCalls)} />
            <MetricCard title="Files Processed" value={formatNumber(totals.files)} />
          </div>

          {/* Sparkline */}
          {sparklineData.length > 1 && (
            <div className="rounded-lg border border-border bg-card p-4 mb-6">
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Recent Activity (turns/update)</h3>
              <div className="h-20">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparklineData}>
                    <defs>
                      <linearGradient id="liveGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="turns" stroke="var(--color-chart-2)" fill="url(#liveGrad)" strokeWidth={2} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Event Log */}
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Event Log</h3>
            {etlMessages.length === 0 ? (
              <div className="text-center py-8">
                <Activity className="h-8 w-8 text-muted-foreground mx-auto mb-2 animate-pulse" />
                <p className="text-sm text-muted-foreground">Waiting for activity...</p>
                <p className="text-xs text-muted-foreground mt-1">Start a Claude Code session to see live updates</p>
              </div>
            ) : (
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {etlMessages.map((m, i) => (
                  <div key={i} className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-accent/10">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
                      <span className="text-xs text-muted-foreground">{m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : ''}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs font-mono">
                      {(m.files_processed ?? 0) > 0 && <span>{m.files_processed} files</span>}
                      {(m.turns_inserted ?? 0) > 0 && <span>{m.turns_inserted} turns</span>}
                      {(m.tool_calls_inserted ?? 0) > 0 && <span>{m.tool_calls_inserted} tool calls</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </PageLayout>
  )
}
