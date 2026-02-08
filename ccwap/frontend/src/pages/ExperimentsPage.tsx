import { useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router'
import { Trash2, Plus, ArrowRightLeft, X, ChevronDown, ChevronUp } from 'lucide-react'
import {
  BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { PageLayout } from '@/components/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import {
  useTags, useTagComparison, useCreateTag, useDeleteTag,
  useCompareTagsMulti, useTagSessions,
} from '@/api/experiments'
import type { TagCreatePayload, TagComparison } from '@/api/experiments'
import { useProjects } from '@/api/projects'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatPercent, formatCurrency, formatNumber, cn } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'

function TagManager({ onTagClick, expandedTag }: { onTagClick: (tagName: string) => void; expandedTag: string | null }) {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useTags()
  const createTag = useCreateTag()
  const deleteTag = useDeleteTag()
  const [newTagName, setNewTagName] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [projectPath, setProjectPath] = useState('')

  const { data: projectsData } = useProjects(dateRange, 'cost', 'desc', 1, undefined)

  const handleCreate = useCallback(() => {
    if (!newTagName.trim()) return
    const payload: TagCreatePayload = {
      tag_name: newTagName.trim(),
      ...(dateFrom && { date_from: dateFrom }),
      ...(dateTo && { date_to: dateTo }),
      ...(projectPath && { project_path: projectPath }),
    }
    createTag.mutate(payload, {
      onSuccess: () => { setNewTagName(''); setDateFrom(''); setDateTo(''); setProjectPath('') },
    })
  }, [newTagName, dateFrom, dateTo, projectPath, createTag])

  if (isLoading) return <LoadingState message="Loading tags..." />
  if (error) return <ErrorState message={error.message} />

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Tags</h3>

      {/* Create form */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mb-4">
        <input
          type="text"
          value={newTagName}
          onChange={e => setNewTagName(e.target.value)}
          placeholder="Tag name..."
          className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={e => setDateFrom(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <input
          type="date"
          value={dateTo}
          onChange={e => setDateTo(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={projectPath}
          onChange={e => setProjectPath(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Projects</option>
          {projectsData?.projects.map(p => (
            <option key={p.project_path} value={p.project_path}>
              {p.project_display}
            </option>
          ))}
        </select>
        <button
          onClick={handleCreate}
          disabled={!newTagName.trim() || createTag.isPending}
          className="flex items-center justify-center gap-1 px-3 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Create
        </button>
      </div>

      {/* Tag list */}
      {!data || data.tags.length === 0 ? (
        <EmptyState message="No experiment tags" />
      ) : (
        <div className="space-y-1">
          {data.tags.map(tag => (
            <div key={tag.tag_name}>
              <div className="flex items-center justify-between py-2 px-3 rounded hover:bg-accent/10">
                <button
                  onClick={() => onTagClick(tag.tag_name)}
                  className="flex items-center gap-3 text-left"
                >
                  {expandedTag === tag.tag_name
                    ? <ChevronUp className="h-3 w-3 text-muted-foreground" />
                    : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
                  <span className="font-medium text-sm">{tag.tag_name}</span>
                  <span className="text-xs text-muted-foreground">{tag.session_count} sessions</span>
                  {tag.created_at && <span className="text-xs text-muted-foreground">{tag.created_at}</span>}
                </button>
                <button
                  onClick={() => deleteTag.mutate(tag.tag_name)}
                  disabled={deleteTag.isPending}
                  className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {expandedTag === tag.tag_name && (
                <TagSessionsList tagName={tag.tag_name} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TagSessionsList({ tagName }: { tagName: string }) {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useTagSessions(tagName, dateRange)

  if (isLoading) return <div className="px-6 py-2"><LoadingState message="Loading sessions..." /></div>
  if (error) return <div className="px-6 py-2"><ErrorState message={error.message} /></div>
  if (!data || data.sessions.length === 0) return <div className="px-6 py-2"><EmptyState message="No sessions for this tag" /></div>

  return (
    <div className="ml-6 mr-3 mb-2 rounded border border-border overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-muted/50 border-b border-border">
            <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Session</th>
            <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Project</th>
            <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Started</th>
            <th className="text-right px-3 py-1.5 font-medium text-muted-foreground">Cost</th>
            <th className="text-right px-3 py-1.5 font-medium text-muted-foreground">Turns</th>
            <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Model</th>
          </tr>
        </thead>
        <tbody>
          {data.sessions.map(s => (
            <tr key={s.session_id} className="border-b border-border hover:bg-accent/10">
              <td className="px-3 py-1.5">
                <Link to={`/sessions/${s.session_id}`} className="font-mono text-primary hover:underline">
                  {s.session_id.slice(0, 8)}...
                </Link>
              </td>
              <td className="px-3 py-1.5 text-muted-foreground truncate max-w-[150px]">{s.project_display}</td>
              <td className="px-3 py-1.5 text-muted-foreground">{s.start_time?.slice(0, 16) || 'N/A'}</td>
              <td className="px-3 py-1.5 text-right font-mono">{formatCurrency(s.total_cost)}</td>
              <td className="px-3 py-1.5 text-right">{s.turn_count}</td>
              <td className="px-3 py-1.5 text-muted-foreground">{s.model_default}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MultiTagSelector({ tags, selectedTags, onToggle }: {
  tags: { tag_name: string; session_count: number }[]
  selectedTags: string[]
  onToggle: (tag: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">Select tags (up to 4):</span>
      {tags.map(t => {
        const isSelected = selectedTags.includes(t.tag_name)
        const isDisabled = !isSelected && selectedTags.length >= 4
        return (
          <button
            key={t.tag_name}
            onClick={() => onToggle(t.tag_name)}
            disabled={isDisabled}
            className={cn(
              "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
              isSelected
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-accent hover:text-foreground",
              isDisabled && "opacity-40 cursor-not-allowed"
            )}
          >
            {t.tag_name} ({t.session_count})
            {isSelected && <X className="h-3 w-3" />}
          </button>
        )
      })}
    </div>
  )
}

function MultiTagCharts({ tags }: { tags: TagComparison[] }) {
  const metrics = ['sessions', 'cost', 'loc', 'turns', 'error_rate'] as const

  // Build bar chart data: one entry per metric, with a key per tag
  const barData = useMemo(() => {
    return metrics.map(metric => {
      const entry: Record<string, any> = { metric }
      for (const tag of tags) {
        entry[tag.tag_name] = tag[metric]
      }
      return entry
    })
  }, [tags])

  // Build radar data: normalize each metric 0-100 across all tags
  const radarData = useMemo(() => {
    return metrics.map(metric => {
      const values = tags.map(t => t[metric])
      const maxVal = Math.max(...values, 0.001)
      const entry: Record<string, any> = { metric }
      for (const tag of tags) {
        entry[tag.tag_name] = metric === 'error_rate'
          ? (1 - tag[metric]) * 100  // Invert error_rate: lower is better
          : (tag[metric] / maxVal) * 100
      }
      return entry
    })
  }, [tags])

  const metricLabels: Record<string, string> = {
    sessions: 'Sessions',
    cost: 'Cost ($)',
    loc: 'LOC',
    turns: 'Turns',
    error_rate: 'Error Rate',
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Grouped Bar Chart */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h4 className="text-sm font-medium text-muted-foreground mb-3">Metric Comparison</h4>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <XAxis
                dataKey="metric"
                tick={{ fontSize: 10 }}
                stroke="var(--color-muted-foreground)"
                tickFormatter={(v: any) => metricLabels[v] || v}
              />
              <YAxis tick={{ fontSize: 10 }} stroke="var(--color-muted-foreground)" width={55} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(value: any, name: any) => {
                  if (typeof value === 'number') {
                    return [value < 1 ? formatPercent(value) : formatNumber(value), name]
                  }
                  return [value, name]
                }}
                labelFormatter={(label: any) => metricLabels[label] || label}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {tags.map((tag, i) => (
                <Bar
                  key={tag.tag_name}
                  dataKey={tag.tag_name}
                  fill={CHART_COLORS[i % CHART_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Radar Chart */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h4 className="text-sm font-medium text-muted-foreground mb-3">Normalized Radar View</h4>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid stroke="var(--color-border)" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }}
                tickFormatter={(v: any) => metricLabels[v] || v}
              />
              <PolarRadiusAxis tick={{ fontSize: 9 }} domain={[0, 100]} />
              {tags.map((tag, i) => (
                <Radar
                  key={tag.tag_name}
                  name={tag.tag_name}
                  dataKey={tag.tag_name}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  fill={CHART_COLORS[i % CHART_COLORS.length]}
                  fillOpacity={0.15}
                />
              ))}
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value: any, name: any) => [`${Number(value).toFixed(1)}%`, name]} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function MultiComparisonBuilder() {
  const { dateRange } = useDateRange()
  const { data: tagsData } = useTags()
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const { data: multiData, isLoading, error } = useCompareTagsMulti(selectedTags, dateRange)

  const tags = tagsData?.tags || []

  const handleToggle = useCallback((tagName: string) => {
    setSelectedTags(prev =>
      prev.includes(tagName)
        ? prev.filter(t => t !== tagName)
        : prev.length < 4 ? [...prev, tagName] : prev
    )
  }, [])

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Multi-Tag Comparison</h3>

      <div className="mb-4">
        <MultiTagSelector tags={tags} selectedTags={selectedTags} onToggle={handleToggle} />
      </div>

      {selectedTags.length < 2 && (
        <p className="text-sm text-muted-foreground">Select at least 2 tags to compare.</p>
      )}

      {isLoading && <LoadingState message="Comparing tags..." />}
      {error && <ErrorState message={error.message} />}

      {multiData && multiData.tags.length >= 2 && (
        <MultiTagCharts tags={multiData.tags} />
      )}
    </div>
  )
}

function ComparisonBuilder() {
  const { data: tagsData } = useTags()
  const [tagA, setTagA] = useState('')
  const [tagB, setTagB] = useState('')
  const { data: comparison, isLoading, error } = useTagComparison(tagA, tagB)

  const tags = tagsData?.tags || []

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Compare Tags (A vs B)</h3>

      <div className="flex items-center gap-2 mb-4">
        <select
          value={tagA}
          onChange={e => setTagA(e.target.value)}
          className="flex-1 px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select Tag A...</option>
          {tags.map(t => <option key={t.tag_name} value={t.tag_name}>{t.tag_name} ({t.session_count})</option>)}
        </select>
        <ArrowRightLeft className="h-4 w-4 text-muted-foreground shrink-0" />
        <select
          value={tagB}
          onChange={e => setTagB(e.target.value)}
          className="flex-1 px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select Tag B...</option>
          {tags.map(t => <option key={t.tag_name} value={t.tag_name}>{t.tag_name} ({t.session_count})</option>)}
        </select>
      </div>

      {isLoading && <LoadingState message="Comparing..." />}
      {error && <ErrorState message={error.message} />}

      {comparison && (
        <div>
          <div className="flex gap-4 mb-4 text-sm">
            <span><strong>{comparison.tag_a}</strong>: {comparison.tag_a_sessions} sessions</span>
            <span><strong>{comparison.tag_b}</strong>: {comparison.tag_b_sessions} sessions</span>
          </div>

          {comparison.metrics.length === 0 ? (
            <EmptyState message="No metrics to compare" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-3 py-2 font-medium text-muted-foreground">Metric</th>
                    <th className="text-right px-3 py-2 font-medium text-muted-foreground">{comparison.tag_a}</th>
                    <th className="text-right px-3 py-2 font-medium text-muted-foreground">{comparison.tag_b}</th>
                    <th className="text-right px-3 py-2 font-medium text-muted-foreground">Delta</th>
                    <th className="text-right px-3 py-2 font-medium text-muted-foreground">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.metrics.map(m => (
                    <tr key={m.metric_name} className="border-b border-border">
                      <td className="px-3 py-2">{m.metric_name}</td>
                      <td className="px-3 py-2 font-mono text-right">{m.tag_a_value.toFixed(2)}</td>
                      <td className="px-3 py-2 font-mono text-right">{m.tag_b_value.toFixed(2)}</td>
                      <td className="px-3 py-2 font-mono text-right">{m.absolute_delta >= 0 ? '+' : ''}{m.absolute_delta.toFixed(2)}</td>
                      <td className={cn("px-3 py-2 font-mono text-right", m.is_improvement ? "text-green-500" : "text-red-400")}>
                        {m.percentage_delta >= 0 ? '+' : ''}{formatPercent(m.percentage_delta / 100)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ExperimentsPage() {
  const [expandedTag, setExpandedTag] = useState<string | null>(null)

  const handleTagClick = useCallback((tagName: string) => {
    setExpandedTag(prev => prev === tagName ? null : tagName)
  }, [])

  return (
    <PageLayout title="Experiments" subtitle="Tag sessions and compare outcomes">
      <div className="space-y-6">
        <TagManager onTagClick={handleTagClick} expandedTag={expandedTag} />
        <MultiComparisonBuilder />
        <ComparisonBuilder />
      </div>
    </PageLayout>
  )
}
