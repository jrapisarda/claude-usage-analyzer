import { useMemo } from 'react'
import { Link } from 'react-router'
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ZAxis, BarChart, Bar } from 'recharts'
import type { ColumnDef } from '@tanstack/react-table'
import { PageLayout } from '@/components/layout/PageLayout'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { DataTable } from '@/components/composite/DataTable'
import { ErrorState } from '@/components/composite/ErrorState'
import { useDateRange } from '@/hooks/useDateRange'
import { usePromptEfficiency, type PromptEfficiencyPoint } from '@/api/advanced'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'

const outlierColumns: ColumnDef<PromptEfficiencyPoint, unknown>[] = [
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
    accessorKey: 'model',
    header: 'Model',
    cell: ({ row }) => <span className="font-mono text-xs">{row.original.model}</span>,
  },
  {
    accessorKey: 'cost',
    header: () => <div className="text-right">Cost</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatCurrency(row.original.cost)}</div>,
  },
  {
    accessorKey: 'output_tokens',
    header: () => <div className="text-right">Output</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatNumber(row.original.output_tokens)}</div>,
  },
  {
    accessorKey: 'thinking_chars',
    header: () => <div className="text-right">Thinking</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatNumber(row.original.thinking_chars)}</div>,
  },
  {
    accessorKey: 'loc_written',
    header: () => <div className="text-right">LOC</div>,
    cell: ({ row }) => <div className="text-right font-mono">{formatNumber(row.original.loc_written)}</div>,
  },
]

export default function PromptEfficiencyPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = usePromptEfficiency(dateRange)

  const stopReasonData = data?.by_stop_reason.slice(0, 10) ?? []
  const highCostLowOutputRate = data && data.summary.total_sessions > 0
    ? data.summary.high_cost_low_output_sessions / data.summary.total_sessions
    : 0

  const scatter = useMemo(
    () => (data?.scatter ?? []).map(s => ({
      ...s,
      bubble: Math.max(20, Math.min(200, Math.floor(s.thinking_chars / 150))),
    })),
    [data?.scatter]
  )

  if (error) return <ErrorState message={error.message} />
  if (isLoading || !data) {
    return (
      <PageLayout title="Prompt Efficiency" subtitle="Find expensive prompt patterns and low-output sessions">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  return (
    <PageLayout title="Prompt Efficiency" subtitle="Detect expensive prompt patterns and truncation/overthinking overhead">
      <MetricCardGrid className="mb-6">
        <MetricCard title="Sessions" value={formatNumber(data.summary.total_sessions)} />
        <MetricCard title="With Thinking" value={formatNumber(data.summary.sessions_with_thinking)} />
        <MetricCard title="With Truncation" value={formatNumber(data.summary.sessions_with_truncation)} />
        <MetricCard title="High-Cost Low-Output" value={formatPercent(highCostLowOutputRate)} />
      </MetricCardGrid>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartContainer title="Cost vs LOC (bubble=thinking chars)" height={320} isEmpty={scatter.length === 0}>
          <ScatterChart>
            <XAxis type="number" dataKey="cost" name="Cost" tick={{ fontSize: 10 }} />
            <YAxis type="number" dataKey="loc_written" name="LOC" tick={{ fontSize: 10 }} />
            <ZAxis type="number" dataKey="bubble" range={[30, 280]} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(v: any, n: any) => {
                if (n === 'cost') return [formatCurrency(v ?? 0), 'Cost']
                if (n === 'loc_written') return [formatNumber(v ?? 0), 'LOC']
                return [formatNumber(v ?? 0), n]
              }}
              labelFormatter={(_, payload: any) => payload?.[0]?.payload?.session_id ?? 'session'}
            />
            <Scatter data={scatter} fill={CHART_COLORS[0]} />
          </ScatterChart>
        </ChartContainer>

        <ChartContainer title="Stop Reason / Truncation Profile" height={320} isEmpty={stopReasonData.length === 0}>
          <BarChart data={stopReasonData}>
            <XAxis dataKey="stop_reason" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, n: any) => n === 'percentage' ? formatPercent(v ?? 0) : formatNumber(v ?? 0)} />
            <Bar dataKey="count" fill={CHART_COLORS[2]} name="Count" />
          </BarChart>
        </ChartContainer>
      </div>

      <div className="rounded-md border border-border p-4 mb-6">
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Funnel Cards</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {data.funnel.map(f => (
            <div key={f.stage} className="rounded border border-border p-3 bg-card">
              <p className="text-xs text-muted-foreground">{f.stage}</p>
              <p className="font-mono text-lg">{formatNumber(f.value)}</p>
            </div>
          ))}
        </div>
      </div>

      <DataTable columns={outlierColumns} data={data.outliers} emptyMessage="No outliers detected" />
    </PageLayout>
  )
}
