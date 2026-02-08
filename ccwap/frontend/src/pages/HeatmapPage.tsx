import { useState, useMemo, useCallback } from 'react'
import { useDateRange } from '@/hooks/useDateRange'
import { useHeatmap } from '@/api/heatmap'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ErrorState } from '@/components/composite/ErrorState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { HeatmapGrid, type HeatmapDataPoint } from '@/components/charts/HeatmapGrid'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  const { data, isLoading, error, refetch } = useHeatmap(dateRange, metric)

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

  const getExportData = useCallback(() => {
    if (!data) return []
    return data.cells.map(c => ({
      day: DAYS[c.day] || c.day,
      hour: c.hour,
      value: c.value,
      metric,
    }))
  }, [data, metric])

  if (error) return <ErrorState message={error.message} onRetry={() => refetch()} />

  return (
    <PageLayout
      title="Activity Heatmap"
      subtitle="Hourly activity patterns across days of the week"
      actions={
        <ExportDropdown page="heatmap" getData={getExportData} />
      }
    >
      {/* Metric toggle */}
      <Tabs value={metric} onValueChange={(v) => setMetric(v as Metric)} className="mb-6">
        <TabsList>
          {METRICS.map(m => (
            <TabsTrigger key={m} value={m}>
              {METRIC_LABELS[m]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card className="mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {METRIC_LABELS[metric]} by Day & Hour
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : data ? (
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
          ) : null}
        </CardContent>
      </Card>

      <MetricCardGrid skeleton={isLoading} count={4}>
        {data && (
          <>
            <MetricCard title={`Total ${METRIC_LABELS[metric]}`} value={formatValue(total)} />
            <MetricCard title="Peak Day" value={DAYS[peakDay] || 'N/A'} subtitle={formatValue(peakVal)} />
            <MetricCard title="Peak Hour" value={`${peakHour}:00`} subtitle={formatValue(peakVal)} />
            <MetricCard title="Max Cell" value={formatValue(data.max_value)} />
          </>
        )}
      </MetricCardGrid>
    </PageLayout>
  )
}
