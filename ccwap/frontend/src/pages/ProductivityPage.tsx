import { useMemo } from 'react'
import { AreaChart, Area, BarChart, Bar, LineChart, Line, Treemap, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { PageLayout } from '@/components/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import { useProductivity, useEfficiencyTrend, useLanguageTrend, useToolSuccessTrend, useFileChurn } from '@/api/productivity'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { MetricCard } from '@/components/ui/MetricCard'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/utils'
import { ExportDropdown } from '@/components/ExportDropdown'
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

  if (isLoading) return <LoadingState message="Loading productivity data..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

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
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="LOC Written" value={formatNumber(summary.total_loc_written)} />
        <MetricCard title="LOC Delivered" value={formatNumber(summary.total_loc_delivered)} />
        <MetricCard title="Cost/kLOC" value={formatCurrency(summary.cost_per_kloc)} />
        <MetricCard title="Error Rate" value={formatPercent(summary.error_rate)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* LOC Trend */}
        {loc_trend.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">LOC Trend</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
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
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" width={50} />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--color-card)', color: 'var(--color-card-foreground)', border: '1px solid var(--color-border)', borderRadius: '6px' }} />
                  <Area type="monotone" dataKey="loc_written" stroke="var(--color-chart-2)" fill="url(#locGrad)" strokeWidth={2} name="LOC Written" isAnimationActive={loc_trend.length < 365} />
                  <Area type="monotone" dataKey="loc_delivered" stroke="var(--color-chart-3)" fill="url(#locDeliveredGrad)" strokeWidth={2} name="LOC Delivered" isAnimationActive={loc_trend.length < 365} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Language Distribution */}
        {languages.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Languages</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={languages.slice(0, 10)} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
                  <YAxis type="category" dataKey="language" tick={{ fontSize: 10 }} width={80} stroke="var(--color-muted-foreground)" />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--color-card)', color: 'var(--color-card-foreground)', border: '1px solid var(--color-border)', borderRadius: '6px', fontSize: '12px' }} />
                  <Bar dataKey="loc_written" fill="var(--color-chart-3)" radius={[0, 4, 4, 0]} name="LOC" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Tool Usage Table */}
      {tool_usage.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden mb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Tool</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">Calls</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">Success</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">Errors</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">Success Rate</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">LOC</th>
                </tr>
              </thead>
              <tbody>
                {tool_usage.map(t => (
                  <tr key={t.tool_name} className="border-b border-border hover:bg-accent/10">
                    <td className="px-4 py-3 font-medium">{t.tool_name}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatNumber(t.total_calls)}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatNumber(t.success_count)}</td>
                    <td className="px-4 py-3 font-mono text-right">{t.error_count > 0 ? <span className="text-red-400">{formatNumber(t.error_count)}</span> : '0'}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatPercent(t.success_rate)}</td>
                    <td className="px-4 py-3 font-mono text-right">{formatNumber(t.loc_written)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Error Analysis */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Error Analysis</h3>
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
        </div>

        {/* File Hotspots */}
        {file_hotspots.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">File Hotspots</h3>
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
          </div>
        )}
      </div>

      {/* LOC Efficiency Trend */}
      {efficiencyData && efficiencyData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">LOC Efficiency Trend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={efficiencyData}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => `$${v ?? 0}`} stroke="var(--color-muted-foreground)" width={50} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [formatCurrency(v ?? 0), 'Cost/kLOC']} />
                <Line type="monotone" dataKey="cost_per_kloc" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} name="Cost/kLOC" isAnimationActive={efficiencyData.length < 365} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Language Trend */}
      {pivotedLangData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Language Trend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={pivotedLangData}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" width={50} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, name: any) => [formatNumber(v ?? 0), name ?? '']} />
                {langKeys.map((lang, i) => (
                  <Area key={lang} type="monotone" dataKey={lang} stackId="lang" stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.6} strokeWidth={1} isAnimationActive={pivotedLangData.length < 365} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-3 mt-2">
            {langKeys.map((lang, i) => (
              <span key={lang} className="text-xs flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                {lang}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tool Success Rate Trend */}
      {pivotedToolData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Tool Success Rate Trend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={pivotedToolData}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: any) => d?.slice(5) ?? ''} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: any) => formatPercent((v ?? 0))} stroke="var(--color-muted-foreground)" width={50} domain={[0, 1]} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, name: any) => [formatPercent(v ?? 0), name ?? '']} />
                {toolKeys.map((tool, i) => (
                  <Line key={tool} type="monotone" dataKey={tool} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={false} name={tool} isAnimationActive={pivotedToolData.length < 365} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-3 mt-2">
            {toolKeys.map((tool, i) => (
              <span key={tool} className="text-xs flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                {tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* File Churn Treemap */}
      {treemapData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">File Churn</h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={treemapData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="var(--color-border)"
                content={<TreemapContent />}
              />
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Showing top {treemapData.length} files by edit count
          </p>
        </div>
      )}
    </PageLayout>
  )
}
