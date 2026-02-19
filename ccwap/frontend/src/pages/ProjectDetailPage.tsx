import { useMemo } from 'react'
import { useParams, Link } from 'react-router'
import { useDateRange } from '@/hooks/useDateRange'
import { useProjectDetail } from '@/api/projects'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { ErrorState } from '@/components/composite/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, Legend,
} from 'recharts'
import { type ColumnDef } from '@tanstack/react-table'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'
import { formatCurrency, formatNumber } from '@/lib/utils'

interface SessionRow {
  session_id: string
  start_time: string
  total_cost: number
  turn_count: number
  loc_written: number
  model_default: string
}

const sessionColumns: ColumnDef<SessionRow, unknown>[] = [
  {
    accessorKey: 'session_id',
    header: 'Session',
    cell: ({ row }) => (
      <Link to={`/sessions/${row.original.session_id}`} className="font-mono text-primary hover:underline">
        {row.original.session_id.slice(0, 8)}...
      </Link>
    ),
  },
  {
    accessorKey: 'start_time',
    header: 'Started',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.start_time?.slice(0, 16) || 'N/A'}</span>
    ),
  },
  {
    accessorKey: 'total_cost',
    header: () => <span className="text-right block">Cost</span>,
    cell: ({ row }) => (
      <span className="font-mono text-right block">{formatCurrency(row.original.total_cost)}</span>
    ),
  },
  {
    accessorKey: 'turn_count',
    header: () => <span className="text-right block">Turns</span>,
    cell: ({ row }) => (
      <span className="text-right block">{row.original.turn_count}</span>
    ),
  },
  {
    accessorKey: 'loc_written',
    header: () => <span className="text-right block">LOC</span>,
    cell: ({ row }) => (
      <span className="text-right block">{formatNumber(row.original.loc_written)}</span>
    ),
  },
  {
    accessorKey: 'model_default',
    header: 'Model',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.model_default}</span>
    ),
  },
]

export default function ProjectDetailPage() {
  const { path } = useParams<{ path: string }>()
  const { dateRange, preset } = useDateRange()
  const { data, isLoading, error } = useProjectDetail(path || '', dateRange)
  const dateQueryParams = useMemo(() => {
    const params = new URLSearchParams()
    if (preset) {
      params.set('preset', preset)
    } else {
      if (dateRange.from) params.set('from', dateRange.from)
      if (dateRange.to) params.set('to', dateRange.to)
    }
    return params.toString()
  }, [dateRange.from, dateRange.to, preset])
  const projectsHref = dateQueryParams ? `/projects?${dateQueryParams}` : '/projects'

  const projectDisplay = data?.project_display ?? path ?? ''

  if (isLoading) {
    return (
      <PageLayout
        title="..."
        breadcrumbs={[{ label: 'Projects', href: projectsHref }, { label: '...' }]}
      >
        <MetricCardGrid skeleton count={3} className="grid-cols-2 sm:grid-cols-3 mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </PageLayout>
    )
  }
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  return (
    <PageLayout
      title={projectDisplay}
      subtitle={`${formatNumber(data.total_sessions)} sessions | ${formatCurrency(data.total_cost)} total cost | ${formatNumber(data.total_loc)} LOC`}
      breadcrumbs={[
        { label: 'Projects', href: projectsHref },
        { label: projectDisplay },
      ]}
    >
      {/* Summary */}
      <MetricCardGrid className="grid-cols-2 sm:grid-cols-3 mb-6">
        <MetricCard title="Total Cost" value={formatCurrency(data.total_cost)} />
        <MetricCard title="Sessions" value={formatNumber(data.total_sessions)} />
        <MetricCard title="Lines of Code" value={formatNumber(data.total_loc)} />
      </MetricCardGrid>

      {/* Cost Trend + Languages */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <ChartContainer
          title="Cost Trend"
          height={256}
          isEmpty={data.cost_trend.length === 0}
          emptyMessage="No cost data"
        >
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
        </ChartContainer>

        <ChartContainer
          title="Languages"
          height={256}
          isEmpty={data.languages.length === 0}
          emptyMessage="No language data"
        >
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
        </ChartContainer>
      </div>

      {/* Tools + Branches */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <ChartContainer
          title="Top Tools"
          height={256}
          isEmpty={data.tools.length === 0}
          emptyMessage="No tool data"
        >
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
        </ChartContainer>

        <ChartContainer
          title="Branches"
          height={256}
          isEmpty={data.branches.length === 0}
          emptyMessage="No branch data"
        >
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
        </ChartContainer>
      </div>

      {/* Sessions Table */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-medium text-muted-foreground mb-4">
          Sessions <span className="text-xs">({data.sessions.length} most recent)</span>
        </h3>
        <DataTable
          columns={sessionColumns}
          data={data.sessions}
          emptyMessage="No sessions found"
        />
      </div>
    </PageLayout>
  )
}
