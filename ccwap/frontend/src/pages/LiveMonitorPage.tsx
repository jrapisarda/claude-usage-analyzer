import { useMemo } from 'react'
import { Wifi, WifiOff, Activity } from 'lucide-react'
import { AreaChart, Area } from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useDashboard } from '@/api/dashboard'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { EmptyState } from '@/components/composite/EmptyState'
import { CostTicker } from '@/components/ui/CostTicker'
import { ActiveSessionBadge } from '@/components/ui/ActiveSessionBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
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
  const statusVariant = status === 'connected' ? 'default' as const : status === 'connecting' ? 'secondary' as const : 'destructive' as const

  return (
    <PageLayout title="Live Monitor" subtitle="Real-time session tracking">
      {/* Connection Status + Active Session */}
      <div className="flex items-center justify-between mb-6">
        <div className={cn("flex items-center gap-2 text-sm", statusColor)}>
          <StatusIcon className="h-4 w-4" />
          <Badge variant={statusVariant} className="capitalize">{status}</Badge>
          {status === 'connected' && lastMessage && (
            <span className="text-muted-foreground ml-2 text-xs">
              Last update: {lastMessage.timestamp ? new Date(lastMessage.timestamp).toLocaleTimeString() : 'N/A'}
            </span>
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
        <EmptyState
          icon={<Activity className="h-12 w-12" />}
          title={status === 'connecting' ? 'Connecting...' : 'Disconnected'}
          message={
            status === 'connecting'
              ? 'Establishing WebSocket connection to the server...'
              : 'WebSocket connection lost. Reconnecting automatically...'
          }
        />
      ) : (
        <>
          {/* Today's Vitals Mini Dashboard */}
          <MetricCardGrid className="mb-6">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground mb-1">Cost Today</p>
              <CostTicker
                targetCost={latestCostMessage?.cost_today ?? dashboardData?.vitals.cost ?? 0}
              />
              {latestCostMessage && (
                <p className="text-xs text-muted-foreground mt-1">
                  {latestCostMessage.sessions_today} session{latestCostMessage.sessions_today !== 1 ? 's' : ''}
                </p>
              )}
            </Card>
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
          </MetricCardGrid>

          {/* Live Totals (this session's WebSocket data) */}
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <MetricCard title="Turns Received" value={formatNumber(totals.turns)} />
            <MetricCard title="Tool Calls" value={formatNumber(totals.toolCalls)} />
            <MetricCard title="Files Processed" value={formatNumber(totals.files)} />
          </div>

          {/* Sparkline */}
          {sparklineData.length > 1 && (
            <ChartContainer title="Recent Activity (turns/update)" height={80} className="mb-6">
              <AreaChart data={sparklineData}>
                <defs>
                  <linearGradient id="liveGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--color-chart-2)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="turns" stroke="var(--color-chart-2)" fill="url(#liveGrad)" strokeWidth={2} isAnimationActive={false} />
              </AreaChart>
            </ChartContainer>
          )}

          {/* Event Log */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">Event Log</CardTitle>
            </CardHeader>
            <CardContent>
              {etlMessages.length === 0 ? (
                <EmptyState
                  icon={<Activity className="h-8 w-8 animate-pulse" />}
                  message="Waiting for activity... Start a Claude Code session to see live updates"
                />
              ) : (
                <ScrollArea className="h-96">
                  <div className="space-y-1">
                    {etlMessages.map((m, i) => (
                      <div key={i} className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-accent/10">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
                          <span className="text-xs text-muted-foreground">{m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : ''}</span>
                        </div>
                        <div className="flex items-center gap-3 text-xs font-mono">
                          {(m.files_processed ?? 0) > 0 && <Badge variant="outline">{m.files_processed} files</Badge>}
                          {(m.turns_inserted ?? 0) > 0 && <Badge variant="outline">{m.turns_inserted} turns</Badge>}
                          {(m.tool_calls_inserted ?? 0) > 0 && <Badge variant="outline">{m.tool_calls_inserted} tool calls</Badge>}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </PageLayout>
  )
}
