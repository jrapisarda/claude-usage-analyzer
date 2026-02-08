import { useState, useMemo, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router'
import { ArrowLeft, X } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { TokenWaterfall } from '@/components/charts/TokenWaterfall'
import type { TokenWaterfallTurn } from '@/components/charts/TokenWaterfall'
import { PageLayout } from '@/components/PageLayout'
import { useSessionReplay } from '@/api/sessions'
import type { ReplayTurn, ToolCallDetail } from '@/api/sessions'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { MetricCard } from '@/components/ui/MetricCard'
import { formatCurrency, formatNumber, formatDuration, cn } from '@/lib/utils'
import { ExportDropdown } from '@/components/ExportDropdown'

const CHART_COLORS = [
  'var(--color-chart-1)', 'var(--color-chart-2)', 'var(--color-chart-3)',
  'var(--color-chart-4)', 'var(--color-chart-5)',
]
const MIN_BLOCK_WIDTH = 24
const MAX_BLOCK_WIDTH = 200

function TurnBlock({
  turn,
  width,
  isSelected,
  onClick,
}: {
  turn: ReplayTurn
  width: number
  isSelected: boolean
  onClick: () => void
}) {
  const hasError = turn.tool_calls.some(tc => !tc.success)
  const hasTruncation = turn.stop_reason === 'max_tokens'
  const costIntensity = Math.min(turn.cost * 500, 1)

  return (
    <button
      onClick={onClick}
      className={cn(
        "h-16 shrink-0 rounded-sm transition-all relative group",
        isSelected ? "ring-2 ring-primary" : "hover:ring-1 hover:ring-primary/50",
        hasError && "border-2 border-red-500",
        hasTruncation && !hasError && "border-2 border-yellow-500",
      )}
      style={{
        width: `${width}px`,
        backgroundColor: `color-mix(in srgb, var(--color-chart-1) ${Math.round(costIntensity * 100)}%, var(--color-muted) 30%)`,
      }}
    >
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded bg-popover border border-border text-popover-foreground text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-20 shadow-md">
        {turn.entry_type} &middot; {formatCurrency(turn.cost)} &middot; {formatNumber(turn.input_tokens + turn.output_tokens)} tokens
      </div>
      {turn.is_sidechain && (
        <div className="absolute top-0 right-0 w-2 h-2 rounded-full bg-purple-500" />
      )}
      {turn.is_meta && (
        <div className="absolute top-0 left-0 w-2 h-2 rounded-full bg-cyan-500" />
      )}
      <span className="absolute bottom-0.5 left-0 right-0 text-[9px] text-center opacity-0 group-hover:opacity-100 truncate px-0.5">
        {formatCurrency(turn.cost)}
      </span>
    </button>
  )
}

function CostOverlayLine({ turns, blockWidths, containerWidth }: {
  turns: ReplayTurn[]
  blockWidths: number[]
  containerWidth: number
}) {
  if (turns.length < 2) return null

  const maxCost = turns[turns.length - 1].cumulative_cost || 1
  const lineHeight = 60
  const gap = 4

  let x = 0
  const points = turns.map((t, i) => {
    const bw = blockWidths[i]
    const cx = x + bw / 2
    x += bw + gap
    const cy = lineHeight - (t.cumulative_cost / maxCost) * (lineHeight - 4)
    return `${cx},${cy}`
  })

  return (
    <svg
      className="absolute top-0 left-0 pointer-events-none"
      width={containerWidth}
      height={lineHeight}
      style={{ overflow: 'visible' }}
    >
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke="var(--color-chart-2)"
        strokeWidth={1.5}
        strokeOpacity={0.6}
      />
    </svg>
  )
}

function TurnDetailPanel({ turn, onClose }: { turn: ReplayTurn; onClose: () => void }) {
  return (
    <div className="w-96 border-l border-border bg-card p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium">Turn Detail</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-accent"><X className="h-4 w-4" /></button>
      </div>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between"><span className="text-muted-foreground">Type</span><span>{turn.entry_type}</span></div>
        <div className="flex justify-between"><span className="text-muted-foreground">Model</span><span className="font-mono">{turn.model || 'N/A'}</span></div>
        <div className="flex justify-between"><span className="text-muted-foreground">Cost</span><span className="font-mono">{formatCurrency(turn.cost)}</span></div>
        <div className="flex justify-between"><span className="text-muted-foreground">Cumulative</span><span className="font-mono">{formatCurrency(turn.cumulative_cost)}</span></div>
        <div className="flex justify-between"><span className="text-muted-foreground">Stop Reason</span><span>{turn.stop_reason || 'N/A'}</span></div>
        {turn.timestamp && (
          <div className="flex justify-between"><span className="text-muted-foreground">Time</span><span>{new Date(turn.timestamp).toLocaleTimeString()}</span></div>
        )}

        <div className="border-t border-border pt-3">
          <h4 className="font-medium text-muted-foreground mb-2">Tokens</h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex justify-between"><span className="text-muted-foreground">Input</span><span className="font-mono">{formatNumber(turn.input_tokens)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Output</span><span className="font-mono">{formatNumber(turn.output_tokens)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Cache Read</span><span className="font-mono">{formatNumber(turn.cache_read_tokens)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Cache Write</span><span className="font-mono">{formatNumber(turn.cache_write_tokens)}</span></div>
          </div>
        </div>

        {turn.thinking_chars > 0 && (
          <div className="flex justify-between"><span className="text-muted-foreground">Thinking</span><span className="font-mono">{formatNumber(turn.thinking_chars)} chars</span></div>
        )}

        {turn.user_prompt_preview && (
          <div className="border-t border-border pt-3">
            <h4 className="font-medium text-muted-foreground mb-2">User Prompt</h4>
            <p className="text-xs bg-muted/50 p-2 rounded whitespace-pre-wrap break-words">{turn.user_prompt_preview}</p>
          </div>
        )}

        {turn.tool_calls.length > 0 && (
          <div className="border-t border-border pt-3">
            <h4 className="font-medium text-muted-foreground mb-2">Tool Calls ({turn.tool_calls.length})</h4>
            <div className="space-y-2">
              {turn.tool_calls.map((tc: ToolCallDetail, i: number) => (
                <div key={i} className={cn("p-2 rounded text-xs", tc.success ? "bg-muted/50" : "bg-red-500/10 border border-red-500/30")}>
                  <div className="flex justify-between">
                    <span className="font-medium">{tc.tool_name}</span>
                    {!tc.success && <span className="text-red-400 text-[10px]">FAILED</span>}
                  </div>
                  {tc.file_path && <div className="text-muted-foreground truncate mt-0.5">{tc.file_path}</div>}
                  {tc.loc_written > 0 && <div className="text-muted-foreground mt-0.5">+{tc.lines_added}/-{tc.lines_deleted} ({tc.loc_written} LOC)</div>}
                  {tc.error_message && <div className="text-red-400 mt-1 break-words">{tc.error_message}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-1 mt-2">
          {turn.is_sidechain && <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">sidechain</span>}
          {turn.is_meta && <span className="text-xs bg-cyan-500/20 text-cyan-400 px-1.5 py-0.5 rounded">meta</span>}
        </div>
      </div>
    </div>
  )
}

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, error } = useSessionReplay(id!)
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null)
  const [chartView, setChartView] = useState<'cost' | 'tokens'>('cost')
  const scrollRef = useRef<HTMLDivElement>(null)

  const blockWidths = useMemo(() => {
    if (!data) return []
    const maxTokens = Math.max(...data.turns.map(t => t.input_tokens + t.output_tokens), 1)
    return data.turns.map(t => {
      const tokens = t.input_tokens + t.output_tokens
      const ratio = tokens / maxTokens
      return Math.max(MIN_BLOCK_WIDTH, Math.round(ratio * MAX_BLOCK_WIDTH))
    })
  }, [data])

  const containerWidth = useMemo(() => {
    const gap = 4
    return blockWidths.reduce((sum, w) => sum + w + gap, 0) - gap
  }, [blockWidths])

  const waterfallData: TokenWaterfallTurn[] = useMemo(() => {
    if (!data) return []
    return data.turns.map((t, i) => ({
      turn_number: i + 1,
      input_tokens: t.input_tokens,
      output_tokens: t.output_tokens,
      cache_read_tokens: t.cache_read_tokens,
      cache_write_tokens: t.cache_write_tokens,
    }))
  }, [data])

  const toolDistData = useMemo(() => {
    if (!data?.tool_distribution) return []
    return Object.entries(data.tool_distribution)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, count]) => ({ name, value: count }))
  }, [data])

  const handleTurnClick = useCallback((index: number) => {
    setSelectedTurn(prev => prev === index ? null : index)
  }, [])

  if (isLoading) return <LoadingState message="Loading session replay..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  const selectedTurnData = selectedTurn !== null ? data.turns[selectedTurn] : null

  return (
    <PageLayout
      title="Session Detail"
      subtitle="Turn-by-turn session replay"
      actions={
        data && <ExportDropdown
          page={`session-${id}`}
          getData={() => (data?.turns || []).map((t, i) => ({
            turn: i + 1,
            entry_type: t.entry_type,
            model: t.model,
            input_tokens: t.input_tokens,
            output_tokens: t.output_tokens,
            cost: t.cost,
            cumulative_cost: t.cumulative_cost,
            stop_reason: t.stop_reason || '',
            is_sidechain: t.is_sidechain,
            user_prompt_preview: t.user_prompt_preview || '',
          }))}
          columns={['turn', 'entry_type', 'model', 'input_tokens', 'output_tokens', 'cost', 'cumulative_cost', 'stop_reason', 'is_sidechain', 'user_prompt_preview']}
        />
      }
    >
      {/* Back link */}
      <Link to="/projects" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to projects
      </Link>

      {/* Session Header */}
      <div className="rounded-lg border border-border bg-card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="font-medium text-lg">{data.project_display || data.project_path}</span>
          {data.is_agent && <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">agent</span>}
          {data.cc_version && <span className="text-muted-foreground">v{data.cc_version}</span>}
          {data.git_branch && <span className="text-muted-foreground font-mono">{data.git_branch}</span>}
        </div>
        <div className="flex flex-wrap gap-4 mt-2 text-xs text-muted-foreground">
          {data.first_timestamp && <span>{new Date(data.first_timestamp).toLocaleString()}</span>}
          <span className="font-mono">{data.session_id.slice(0, 12)}...</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <MetricCard title="Cost" value={formatCurrency(data.total_cost)} />
        <MetricCard title="Duration" value={formatDuration(data.duration_seconds)} />
        <MetricCard title="Turns" value={formatNumber(data.total_turns)} subtitle={`${data.total_user_turns} user`} />
        <MetricCard title="Tool Calls" value={formatNumber(data.total_tool_calls)} />
        <MetricCard title="Errors" value={formatNumber(data.total_errors)} className={data.total_errors > 0 ? 'border-amber-500/50 bg-amber-500/10' : undefined} />
      </div>

      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-6">
          {/* Timeline Scrubber */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-muted-foreground">Timeline</h3>
              <div className="flex gap-3 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Error</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> Truncation</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-500" /> Sidechain</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-500" /> Meta</span>
              </div>
            </div>
            <div ref={scrollRef} className="overflow-x-auto relative" style={{ minHeight: '80px' }}>
              <div className="relative" style={{ width: `${containerWidth}px`, minWidth: '100%' }}>
                <CostOverlayLine turns={data.turns} blockWidths={blockWidths} containerWidth={containerWidth} />
                <div className="flex gap-1 relative z-10">
                  {data.turns.map((turn, i) => (
                    <TurnBlock
                      key={turn.uuid}
                      turn={turn}
                      width={blockWidths[i]}
                      isSelected={selectedTurn === i}
                      onClick={() => handleTurnClick(i)}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* View Toggle */}
          <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 w-fit">
            <button
              onClick={() => setChartView('cost')}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                chartView === 'cost'
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              )}
            >
              Cost Breakdown
            </button>
            <button
              onClick={() => setChartView('tokens')}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                chartView === 'tokens'
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              )}
            >
              Token Waterfall
            </button>
          </div>

          {/* Charts row */}
          {chartView === 'cost' ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Cost by Model */}
              {Object.keys(data.cost_by_model).length > 0 && (
                <div className="rounded-lg border border-border bg-card p-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-3">Cost by Model</h3>
                  <div className="space-y-2">
                    {Object.entries(data.cost_by_model).sort((a, b) => b[1] - a[1]).map(([model, cost]) => (
                      <div key={model} className="flex justify-between text-sm">
                        <span className="truncate font-mono">{model}</span>
                        <span className="font-mono shrink-0 ml-2">{formatCurrency(cost)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tool Distribution */}
              {toolDistData.length > 0 && (
                <div className="rounded-lg border border-border bg-card p-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-3">Tool Distribution</h3>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={toolDistData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} strokeWidth={0}>
                          {toolDistData.map((_, i) => (
                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={{ backgroundColor: 'var(--color-card)', color: 'var(--color-card-foreground)', border: '1px solid var(--color-border)', borderRadius: '6px', fontSize: '12px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {toolDistData.map((d, i) => (
                      <span key={d.name} className="text-[10px] flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                        {d.name} ({d.value})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Token Breakdown per Turn</h3>
              <TokenWaterfall turns={waterfallData} />
            </div>
          )}
        </div>

        {/* Side Panel */}
        {selectedTurnData && (
          <TurnDetailPanel turn={selectedTurnData} onClose={() => setSelectedTurn(null)} />
        )}
      </div>
    </PageLayout>
  )
}
