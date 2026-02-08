import { useMemo } from 'react'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, Treemap,
  XAxis, YAxis, Tooltip,
} from 'recharts'
import type { ColumnDef } from '@tanstack/react-table'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { ErrorState } from '@/components/composite/ErrorState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useDateRange } from '@/hooks/useDateRange'
import {
  useProductivity, useEfficiencyTrend, useLanguageTrend,
  useToolSuccessTrend, useFileChurn,
} from '@/api/productivity'
import type { ToolUsageStat } from '@/api/productivity'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS, fillZeros } from '@/lib/chartConfig'

// Custom content renderer for Treemap
function TreemapContent({ x, y, width, height, name, size }: any) {
  if (width < 40 || height < 30) return null
  const displayName = name?.length > 20 ? '...' + name.slice(-17) : name
  return (
    <g>
      <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="var(--color-card-foreground)" fontSize={11} dominantBaseline="central">
        {displayName ?? ''}
      </text>
      <text x={x + width / 2} y={y + height / 2 + 10} textAnchor="middle" fill="var(--color-muted-foreground)" fontSize={10} dominantBaseline="central">
        {size ?? 0} edits
      </text>
    </g>
  )
}

const toolColumns: ColumnDef<ToolUsageStat, unknown>[] = [
  {
    accessorKey: 'tool_name',
    header: 'Tool',
    cell: ({ getValue }) => <span className="font-medium">{getValue<string>()}</span>,
  },
  {
    accessorKey: 'total_calls',
    header: () => <div className="text-right">Calls</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'success_count',
    header: () => <div className="text-right">Success</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'error_count',
    header: () => <div className="text-right">Errors</div>,
    cell: ({ getValue }) => {
      const v = getValue<number>()
      return (
        <div className="text-right font-mono">
          {v > 0 ? <span className="text-red-400">{formatNumber(v)}</span> : '0'}
        </div>
      )
    },
  },
  {
    accessorKey: 'success_rate',
    header: () => <div className="text-right">Success Rate</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatPercent(getValue<number>())}</div>,
  },
  {
    accessorKey: 'loc_written',
    header: () => <div className="text-right">LOC</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
]

export default function ProductivityPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useProductivity(dateRange)
  const { data: efficiencyData } = useEfficiencyTrend(dateRange)
  const { data: langTrendData } = useLanguageTrend(dateRange)
  const { data: toolSuccessData } = useToolSuccessTrend(dateRange)
  const { data: fileChurnData } = useFileChurn(dateRange)

  // Pivot language trend data: group by date, one key per language
  const { pivotedLangData, langKeys } = useMemo(() => {
    if (!langTrendData || langTrendData.length === 0) return { pivotedLangData: [], langKeys: [] as string[] }
    const allLangs = [...new Set(langTrendData.map(d => d.language))]
    const grouped: Record<string, Record<string, number>> = {}
    for (const row of langTrendData) {
      if (!grouped[row.date]) grouped[row.date] = { date: row.date } as any
      grouped[row.date][row.language] = row.loc_written
    }
    const pivoted = fillZeros(
      Object.values(grouped).sort((a: any, b: any) => (a.date as string).localeCompare(b.date as string)),
      allLangs,
    )
    return { pivotedLangData: pivoted, langKeys: allLangs }
  }, [langTrendData])

  // Pivot tool success trend: group by date, one line per tool (top 5)
  const { pivotedToolData, toolKeys } = useMemo(() => {
    if (!toolSuccessData || toolSuccessData.length === 0) return { pivotedToolData: [], toolKeys: [] as string[] }
    // Find top 5 tools by total calls
    const totals: Record<string, number> = {}
    for (const row of toolSuccessData) {
      totals[row.tool_name] = (totals[row.tool_name] ?? 0) + row.total
    }
    const top5 = Object.entries(totals).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([name]) => name)
    const grouped: Record<string, Record<string, number>> = {}
    for (const row of toolSuccessData) {
      if (!top5.includes(row.tool_name)) continue
      if (!grouped[row.date]) grouped[row.date] = { date: row.date } as any
      grouped[row.date][row.tool_name] = row.success_rate
    }
    const pivoted = fillZeros(
      Object.values(grouped).sort((a: any, b: any) => (a.date as string).localeCompare(b.date as string)),
      top5,
    )
    return { pivotedToolData: pivoted, toolKeys: top5 }
  }, [toolSuccessData])

  // Treemap data for file churn
  const treemapData = useMemo(() => {
    if (!fileChurnData || fileChurnData.length === 0) return []
    return fileChurnData
      .slice(0, 50)
      .map((f, i) => ({
        name: f.file_path.split('/').pop() || f.file_path,
        size: f.edit_count,
        fill: CHART_COLORS[i % CHART_COLORS.length],
      }))
  }, [fileChurnData])

  if (error) return <ErrorState message={error.message} />

  if (isLoading || !data) {
    return (
      <PageLayout title="Productivity" subtitle="LOC trends, tool usage, and error analysis">
        <MetricCardGrid skeleton count={4} className="mb-6" />
      </PageLayout>
    )
  }

  const { summary, loc_trend, languages, tool_usage, error_analysis, file_hotspots } = data

  return (
    <PageLayout
      title="Productivity"
      subtitle="LOC trends, tool usage, and error analysis"
      actions={
        <ExportDropdown
          page="productivity"
          getData={() => [
            ...(data?.loc_trend || []).map(t => ({ date: t.date, loc_written: t.loc_written, loc_delivered: t.loc_delivered })),
            ...(data?.tool_usage || []).map(t => ({ type: 'tool', tool_name: t.tool_name, total_calls: t.total_calls, success_rate: t.success_rate })),
          ]}
        />
      }
    >
      {/* Summary Cards */}
      <MetricCardGrid className="mb-6">
        <MetricCard title="LOC Written" value={formatNumber(summary.total_loc_written)} />
        <MetricCard title="LOC Delivered" value={formatNumber(summary.total_loc_delivered)} />
        <MetricCard title="Cost/kLOC" value={formatCurrency(summary.cost_per_kloc)} />
        <MetricCard title="Error Rate" value={formatPercent(summary.error_rate)} />
      </MetricCardGrid>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* LOC Trend */}
        <ChartContainer
          title="LOC Trend"
          height={256}
          isEmpty={loc_trend.length === 0}
          emptyMessage="No LOC trend data"
        >
          <AreaChart data={loc_trend}>
            <defs>
              <linearGradient id="locGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-2)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--color-chart-2)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="locDeliveredGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-3)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--color-chart-3)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
            <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" width={50} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Area type="monotone" dataKey="loc_written" stroke="var(--color-chart-2)" fill="url(#locGrad)" strokeWidth={2} name="LOC Written" isAnimationActive={loc_trend.length < 365} />
            <Area type="monotone" dataKey="loc_delivered" stroke="var(--color-chart-3)" fill="url(#locDeliveredGrad)" strokeWidth={2} name="LOC Delivered" isAnimationActive={loc_trend.length < 365} />
          </AreaChart>
        </ChartContainer>

        {/* Language Distribution */}
        <ChartContainer
          title="Languages"
          height={256}
          isEmpty={languages.length === 0}
          emptyMessage="No language data"
        >
          <BarChart data={languages.slice(0, 10)} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
            <YAxis type="category" dataKey="language" tick={{ fontSize: 10 }} width={80} stroke="var(--color-muted-foreground)" />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="loc_written" fill="var(--color-chart-3)" radius={[0, 4, 4, 0]} name="LOC" />
          </BarChart>
        </ChartContainer>
      </div>

      {/* Tool Usage Table */}
      {tool_usage.length > 0 && (
        <div className="mb-6">
          <DataTable
            columns={toolColumns}
            data={tool_usage}
            emptyMessage="No tool usage data"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Error Analysis */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Error Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div><span className="text-xs text-muted-foreground">Total Errors</span><p className="font-mono text-lg">{formatNumber(error_analysis.total_errors)}</p></div>
              <div><span className="text-xs text-muted-foreground">Error Rate</span><p className="font-mono text-lg">{formatPercent(error_analysis.error_rate)}</p></div>
            </div>
            {error_analysis.categories.length > 0 && (
              <div className="space-y-2">
                {error_analysis.categories.map(c => (
                  <div key={c.category} className="flex items-center justify-between text-sm">
                    <span className="truncate">{c.category}</span>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="font-mono">{formatNumber(c.count)}</span>
                      <span className="text-xs text-muted-foreground w-12 text-right">{formatPercent(c.percentage)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* File Hotspots */}
        {file_hotspots.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">File Hotspots</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {file_hotspots.slice(0, 15).map(f => (
                  <div key={f.file_path} className="flex items-center justify-between text-sm">
                    <span className="truncate font-mono text-xs flex-1 min-w-0">{f.file_path}</span>
                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      <span className="text-xs text-muted-foreground">{f.total_touches} touches</span>
                      <span className="font-mono text-xs">{formatNumber(f.loc_written)} LOC</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Trend Charts - Tabbed */}
      <Tabs defaultValue="efficiency" className="mb-6">
        <TabsList>
          <TabsTrigger value="efficiency">LOC Efficiency</TabsTrigger>
          <TabsTrigger value="language">Language Trend</TabsTrigger>
          <TabsTrigger value="toolsuccess">Tool Success Rate</TabsTrigger>
          <TabsTrigger value="filechurn">File Churn</TabsTrigger>
        </TabsList>

        <TabsContent value="efficiency">
          <ChartContainer
            title="LOC Efficiency Trend"
            height={256}
            isEmpty={!efficiencyData || efficiencyData.length === 0}
            emptyMessage="No efficiency trend data"
          >
            <LineChart data={efficiencyData ?? []}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" width={50} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [formatCurrency(v ?? 0), 'Cost/kLOC']} />
              <Line type="monotone" dataKey="cost_per_kloc" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} name="Cost/kLOC" isAnimationActive={(efficiencyData ?? []).length < 365} />
            </LineChart>
          </ChartContainer>
        </TabsContent>

        <TabsContent value="language">
          <ChartContainer
            title="Language Trend"
            height={256}
            isEmpty={pivotedLangData.length === 0}
            emptyMessage="No language trend data"
          >
            <AreaChart data={pivotedLangData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
              <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" width={50} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, name: any) => [formatNumber(v ?? 0), name ?? '']} />
              {langKeys.map((lang, i) => (
                <Area key={lang} type="monotone" dataKey={lang} stackId="lang" stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.6} strokeWidth={1} isAnimationActive={pivotedLangData.length < 365} />
              ))}
            </AreaChart>
          </ChartContainer>
          {langKeys.length > 0 && (
            <div className="flex flex-wrap gap-3 mt-2">
              {langKeys.map((lang, i) => (
                <span key={lang} className="text-xs flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                  {lang}
                </span>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="toolsuccess">
          <ChartContainer
            title="Tool Success Rate Trend"
            height={256}
            isEmpty={pivotedToolData.length === 0}
            emptyMessage="No tool success trend data"
          >
            <LineChart data={pivotedToolData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => formatPercent(v ?? 0)} stroke="var(--color-muted-foreground)" width={50} domain={[0, 1]} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, name: any) => [formatPercent(v ?? 0), name ?? '']} />
              {toolKeys.map((tool, i) => (
                <Line key={tool} type="monotone" dataKey={tool} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={false} name={tool} isAnimationActive={pivotedToolData.length < 365} />
              ))}
            </LineChart>
          </ChartContainer>
          {toolKeys.length > 0 && (
            <div className="flex flex-wrap gap-3 mt-2">
              {toolKeys.map((tool, i) => (
                <span key={tool} className="text-xs flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                  {tool}
                </span>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="filechurn">
          <ChartContainer
            title="File Churn"
            height={320}
            isEmpty={treemapData.length === 0}
            emptyMessage="No file churn data"
          >
            <Treemap
              data={treemapData}
              dataKey="size"
              aspectRatio={4 / 3}
              stroke="var(--color-border)"
              content={<TreemapContent />}
            />
          </ChartContainer>
          {treemapData.length > 0 && (
            <p className="text-xs text-muted-foreground mt-2">
              Showing top {treemapData.length} files by edit count
            </p>
          )}
        </TabsContent>
      </Tabs>
    </PageLayout>
  )
}
