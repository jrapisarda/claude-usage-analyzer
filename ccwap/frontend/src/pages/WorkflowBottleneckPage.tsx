import { useMemo } from 'react'
import { Link } from 'react-router'
import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import type { ColumnDef } from '@tanstack/react-table'
import { PageLayout } from '@/components/layout/PageLayout'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ErrorState } from '@/components/composite/ErrorState'
import { useDateRange } from '@/hooks/useDateRange'
import { useWorkflowBottlenecks } from '@/api/advanced'
import { formatNumber, formatPercent } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'

interface BlockedSessionRow {
  session_id: string
  project: string
  branch: string
  user_type: string
  failures: number
  retries: number
  stall_score: number
}

const blockedColumns: ColumnDef<BlockedSessionRow, unknown>[] = [
  {
    accessorKey: 'session_id',
    header: 'Session',
    cell: ({ row }) => (
      <Link to={`/sessions/${row.original.session_id}`} className="font-mono text-xs text-primary hover:underline">
        {row.original.session_id}
      </Link>
    ),
  },
  {
    accessorKey: 'project',
    header: 'Project',
    cell: ({ row }) => <span className="truncate block max-w-[220px]">{row.original.project}</span>,
  },
  {
    accessorKey: 'branch',
    header: 'Branch',
    cell: ({ row }) => <span className="font-mono text-xs">{row.original.branch}</span>,
  },
  {
    accessorKey: 'user_type',
    header: 'Type',
    cell: ({ row }) => <span className="capitalize">{row.original.user_type}</span>,
  },
  {
    accessorKey: 'failures',
    header: () => <div className="text-right">Failures</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatNumber(row.original.failures)}</div>,
  },
  {
    accessorKey: 'retries',
    header: () => <div className="text-right">Retries</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatNumber(row.original.retries)}</div>,
  },
  {
    accessorKey: 'stall_score',
    header: () => <div className="text-right">Stall Score</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatNumber(row.original.stall_score)}</div>,
  },
]

export default function WorkflowBottleneckPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useWorkflowBottlenecks(dateRange)

  const topTransitions = useMemo(() => (data?.transition_matrix ?? []).slice(0, 15), [data?.transition_matrix])
  const retryCount = (data?.retry_loops ?? []).reduce((acc, r) => acc + r.retries, 0)
  const handoffFailures = (data?.failure_handoffs ?? []).reduce((acc, h) => acc + h.errors, 0)
  const avgTransitionFailureRate = topTransitions.length > 0
    ? topTransitions.reduce((acc, t) => acc + t.failure_rate, 0) / topTransitions.length
    : 0

  if (error) return <ErrorState message={error.message} />
  if (isLoading || !data) {
    return (
      <PageLayout title="Workflow Bottlenecks" subtitle="Transition failures, retry loops, and handoff stalls">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  return (
    <PageLayout title="Workflow Bottlenecks" subtitle="Show where human/agent workflows stall">
      <MetricCardGrid className="mb-6">
        <MetricCard title="Transitions" value={formatNumber(data.transition_matrix.length)} />
        <MetricCard title="Retry Loops" value={formatNumber(retryCount)} />
        <MetricCard title="Failure Handoffs" value={formatNumber(handoffFailures)} />
        <MetricCard title="Avg Transition Failure" value={formatPercent(avgTransitionFailureRate)} />
      </MetricCardGrid>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartContainer title="Transition Failure Matrix (Top)" height={320} isEmpty={topTransitions.length === 0}>
          <BarChart data={topTransitions} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="to_tool" width={100} tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, name: any) => name === 'failure_rate' ? formatPercent(v ?? 0) : formatNumber(v ?? 0)} />
            <Bar dataKey="failures" fill={CHART_COLORS[0]} name="Failures" />
          </BarChart>
        </ChartContainer>
        <ChartContainer title="Retry Loops by Tool" height={320} isEmpty={data.retry_loops.length === 0}>
          <BarChart
            data={Object.values(
              data.retry_loops.reduce((acc: Record<string, { tool_name: string; retries: number }>, row) => {
                const key = row.tool_name
                acc[key] = acc[key] || { tool_name: key, retries: 0 }
                acc[key].retries += row.retries
                return acc
              }, {})
            ).sort((a, b) => b.retries - a.retries).slice(0, 12)}
          >
            <XAxis dataKey="tool_name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="retries" fill={CHART_COLORS[2]} />
          </BarChart>
        </ChartContainer>
      </div>

      <div className="rounded-md border border-border overflow-hidden mb-6">
        <div className="px-4 py-2 border-b border-border text-sm font-medium text-muted-foreground">
          Failure Handoffs
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left">Parent</th>
              <th className="px-3 py-2 text-left">Child</th>
              <th className="px-3 py-2 text-left">Branch</th>
              <th className="px-3 py-2 text-left">Handoff</th>
              <th className="px-3 py-2 text-right">Errors</th>
              <th className="px-3 py-2 text-right">Error Rate</th>
            </tr>
          </thead>
          <tbody>
            {data.failure_handoffs.slice(0, 20).map((h, idx) => (
              <tr key={`${h.parent_session_id}-${h.child_session_id}-${idx}`} className="border-b border-border/60">
                <td className="px-3 py-2 font-mono text-xs">{h.parent_session_id}</td>
                <td className="px-3 py-2 font-mono text-xs">{h.child_session_id}</td>
                <td className="px-3 py-2">{h.branch}</td>
                <td className="px-3 py-2">{h.handoff}</td>
                <td className="px-3 py-2 text-right font-mono">{formatNumber(h.errors)}</td>
                <td className="px-3 py-2 text-right font-mono">{formatPercent(h.error_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DataTable columns={blockedColumns} data={data.blocked_sessions} emptyMessage="No blocked sessions found" />
    </PageLayout>
  )
}
