import { useState, useMemo } from 'react'
import { useDateRange } from '@/hooks/useDateRange'
import { useHeatmap } from '@/api/heatmap'
import { PageLayout } from '@/components/PageLayout'
import { MetricCard } from '@/components/ui/MetricCard'
import { ChartCard } from '@/components/ui/ChartCard'
import { HeatmapGrid, type HeatmapDataPoint } from '@/components/charts/HeatmapGrid'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { formatNumber, formatCurrency } from '@/lib/utils'

const METRICS = ['sessions', 'cost', 'loc', 'tool_calls'] as const
type Metric = typeof METRICS[number]

const METRIC_LABELS: Record<Metric, string> = {
  sessions: 'Sessions',
  cost: 'Cost',
  loc: 'Lines of Code',
  tool_calls: 'Tool Calls',
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const HOURS = Array.from({ length: 24 }, (_, i) => `${i}`)

export default function HeatmapPage() {
  const { dateRange } = useDateRange()
  const [metric, setMetric] = useState<Metric>('sessions')
  const { data, isLoading, error } = useHeatmap(dateRange, metric)

  const formatValue = useMemo(
    () => metric === 'cost' ? (v: number) => formatCurrency(v) : (v: number) => formatNumber(v),
    [metric],
  )

  // Transform API cells into HeatmapDataPoint[] for the grid component
  const gridData: HeatmapDataPoint[] = useMemo(() => {
    if (!data) return []
    return data.cells
      .filter(c => c.day >= 0 && c.day < 7 && c.hour >= 0 && c.hour < 24)
      .map(c => ({ row: c.day, col: c.hour, value: c.value }))
  }, [data])

  // Summary stats
  const { total, peakDay, peakHour, peakVal } = useMemo(() => {
    if (!data || data.cells.length === 0) {
      return { total: 0, peakDay: 0, peakHour: 0, peakVal: 0 }
    }
    let t = 0, pd = 0, ph = 0, pv = 0
    for (const cell of data.cells) {
      t += cell.value
      if (cell.value > pv) {
        pv = cell.value
        pd = cell.day
        ph = cell.hour
      }
    }
    return { total: t, peakDay: pd, peakHour: ph, peakVal: pv }
  }, [data])

  if (isLoading) return <LoadingState message="Loading heatmap..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  return (
    <PageLayout title="Activity Heatmap" subtitle="Hourly activity patterns across days of the week">
      {/* Metric toggle */}
      <div className="flex gap-1 mb-6">
        {METRICS.map(m => (
          <button
            key={m}
            onClick={() => setMetric(m)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              m === metric
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-accent'
            }`}
          >
            {METRIC_LABELS[m]}
          </button>
        ))}
      </div>

      <ChartCard title={`${METRIC_LABELS[metric]} by Day & Hour`}>
        <HeatmapGrid
          data={gridData}
          rowLabels={DAYS}
          colLabels={HOURS}
          maxValue={data.max_value}
          formatValue={formatValue}
          formatTooltip={(row, col, value) =>
            `${row} ${col}:00 - ${formatValue(value)}`
          }
        />
      </ChartCard>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        <MetricCard title={`Total ${METRIC_LABELS[metric]}`} value={formatValue(total)} />
        <MetricCard title="Peak Day" value={DAYS[peakDay] || 'N/A'} subtitle={formatValue(peakVal)} />
        <MetricCard title="Peak Hour" value={`${peakHour}:00`} subtitle={formatValue(peakVal)} />
        <MetricCard title="Max Cell" value={formatValue(data.max_value)} />
      </div>
    </PageLayout>
  )
}
