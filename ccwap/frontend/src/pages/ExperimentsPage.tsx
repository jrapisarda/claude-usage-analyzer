import { useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router'
import { Trash2, Plus, ArrowRightLeft, X, ChevronDown, ChevronUp } from 'lucide-react'
import {
  BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, Tooltip, Legend,
} from 'recharts'
import { PageLayout } from '@/components/layout/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import {
  useTags, useTagComparison, useCreateTag, useDeleteTag,
  useCompareTagsMulti, useTagSessions,
} from '@/api/experiments'
import type { TagCreatePayload, TagComparison } from '@/api/experiments'
import { useProjects } from '@/api/projects'
import { ErrorState } from '@/components/composite/ErrorState'
import { EmptyState } from '@/components/composite/EmptyState'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableHeader, TableBody, TableHead, TableRow, TableCell,
} from '@/components/ui/table'
import { type ColumnDef } from '@tanstack/react-table'
import { formatPercent, formatCurrency, formatNumber, cn } from '@/lib/utils'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'

interface TagSessionRow {
  session_id: string
  project_display: string
  start_time: string
  total_cost: number
  turn_count: number
  model_default: string
}

const tagSessionColumns: ColumnDef<TagSessionRow, unknown>[] = [
  {
    accessorKey: 'session_id',
    header: 'Session',
    cell: ({ row }) => (
      <Link to={`/sessions/${row.original.session_id}`} className="font-mono text-xs text-primary hover:underline">
        {row.original.session_id.slice(0, 8)}...
      </Link>
    ),
  },
  {
    accessorKey: 'project_display',
    header: 'Project',
    cell: ({ row }) => (
      <span className="text-muted-foreground truncate max-w-[150px] block text-xs">{row.original.project_display}</span>
    ),
  },
  {
    accessorKey: 'start_time',
    header: 'Started',
    cell: ({ row }) => (
      <span className="text-muted-foreground text-xs">{row.original.start_time?.slice(0, 16) || 'N/A'}</span>
    ),
  },
  {
    accessorKey: 'total_cost',
    header: () => <span className="text-right block">Cost</span>,
    cell: ({ row }) => (
      <span className="font-mono text-xs text-right block">{formatCurrency(row.original.total_cost)}</span>
    ),
  },
  {
    accessorKey: 'turn_count',
    header: () => <span className="text-right block">Turns</span>,
    cell: ({ row }) => (
      <span className="text-xs text-right block">{row.original.turn_count}</span>
    ),
  },
  {
    accessorKey: 'model_default',
    header: 'Model',
    cell: ({ row }) => (
      <span className="text-muted-foreground text-xs">{row.original.model_default}</span>
    ),
  },
]

function TagManager({ onTagClick, expandedTag }: { onTagClick: (tagName: string) => void; expandedTag: string | null }) {
  const { dateRange } = useDateRange()
  const { data, isLoading, error, refetch } = useTags()
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

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-sm">Tags</CardTitle></CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full mb-4" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    )
  }
  if (error) return <ErrorState message={error.message} onRetry={() => refetch()} />

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Tags</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Create form */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mb-4">
          <Input
            type="text"
            value={newTagName}
            onChange={e => setNewTagName(e.target.value)}
            placeholder="Tag name..."
          />
          <Input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
          />
          <Input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
          />
          <select
            value={projectPath}
            onChange={e => setProjectPath(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">All Projects</option>
            {projectsData?.projects.map(p => (
              <option key={p.project_path} value={p.project_path}>
                {p.project_display}
              </option>
            ))}
          </select>
          <Button
            onClick={handleCreate}
            disabled={!newTagName.trim() || createTag.isPending}
            size="sm"
            className="h-9"
          >
            <Plus className="mr-1 h-4 w-4" />
            Create
          </Button>
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
                    <Badge variant="secondary">{tag.session_count} sessions</Badge>
                    {tag.created_at && <span className="text-xs text-muted-foreground">{tag.created_at}</span>}
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteTag.mutate(tag.tag_name)}
                    disabled={deleteTag.isPending}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                {expandedTag === tag.tag_name && (
                  <TagSessionsList tagName={tag.tag_name} />
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function TagSessionsList({ tagName }: { tagName: string }) {
  const { dateRange } = useDateRange()
  const { data, isLoading, error, refetch } = useTagSessions(tagName, dateRange)

  if (error) return <div className="px-6 py-2"><ErrorState message={error.message} onRetry={() => refetch()} /></div>

  const sessions = data?.sessions ?? []

  return (
    <div className="ml-6 mr-3 mb-2">
      <DataTable
        columns={tagSessionColumns}
        data={sessions}
        isLoading={isLoading}
        emptyMessage="No sessions for this tag"
      />
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
      <ChartContainer title="Metric Comparison" height={288}>
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
      </ChartContainer>

      {/* Radar Chart */}
      <ChartContainer title="Normalized Radar View" height={288}>
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
      </ChartContainer>
    </div>
  )
}

function MultiComparisonBuilder() {
  const { dateRange } = useDateRange()
  const { data: tagsData } = useTags()
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const { data: multiData, isLoading, error, refetch } = useCompareTagsMulti(selectedTags, dateRange)

  const tags = tagsData?.tags || []

  const handleToggle = useCallback((tagName: string) => {
    setSelectedTags(prev =>
      prev.includes(tagName)
        ? prev.filter(t => t !== tagName)
        : prev.length < 4 ? [...prev, tagName] : prev
    )
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Multi-Tag Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <MultiTagSelector tags={tags} selectedTags={selectedTags} onToggle={handleToggle} />
        </div>

        {selectedTags.length < 2 && (
          <p className="text-sm text-muted-foreground">Select at least 2 tags to compare.</p>
        )}

        {isLoading && <Skeleton className="h-64 w-full" />}
        {error && <ErrorState message={error.message} onRetry={() => refetch()} />}

        {multiData && multiData.tags.length >= 2 && (
          <MultiTagCharts tags={multiData.tags} />
        )}
      </CardContent>
    </Card>
  )
}

function ComparisonBuilder() {
  const { data: tagsData } = useTags()
  const [tagA, setTagA] = useState('')
  const [tagB, setTagB] = useState('')
  const { data: comparison, isLoading, error, refetch } = useTagComparison(tagA, tagB)

  const tags = tagsData?.tags || []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Compare Tags (A vs B)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 mb-4">
          <select
            value={tagA}
            onChange={e => setTagA(e.target.value)}
            className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">Select Tag A...</option>
            {tags.map(t => <option key={t.tag_name} value={t.tag_name}>{t.tag_name} ({t.session_count})</option>)}
          </select>
          <ArrowRightLeft className="h-4 w-4 text-muted-foreground shrink-0" />
          <select
            value={tagB}
            onChange={e => setTagB(e.target.value)}
            className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">Select Tag B...</option>
            {tags.map(t => <option key={t.tag_name} value={t.tag_name}>{t.tag_name} ({t.session_count})</option>)}
          </select>
        </div>

        {isLoading && <Skeleton className="h-32 w-full" />}
        {error && <ErrorState message={error.message} onRetry={() => refetch()} />}

        {comparison && (
          <div>
            <div className="flex gap-4 mb-4 text-sm">
              <span><strong>{comparison.tag_a}</strong>: {comparison.tag_a_sessions} sessions</span>
              <span><strong>{comparison.tag_b}</strong>: {comparison.tag_b_sessions} sessions</span>
            </div>

            {comparison.metrics.length === 0 ? (
              <EmptyState message="No metrics to compare" />
            ) : (
              <div className="rounded-md border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Metric</TableHead>
                      <TableHead className="text-right">{comparison.tag_a}</TableHead>
                      <TableHead className="text-right">{comparison.tag_b}</TableHead>
                      <TableHead className="text-right">Delta</TableHead>
                      <TableHead className="text-right">Change</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {comparison.metrics.map(m => (
                      <TableRow key={m.metric_name}>
                        <TableCell>{m.metric_name}</TableCell>
                        <TableCell className="font-mono text-right">{m.tag_a_value.toFixed(2)}</TableCell>
                        <TableCell className="font-mono text-right">{m.tag_b_value.toFixed(2)}</TableCell>
                        <TableCell className="font-mono text-right">{m.absolute_delta >= 0 ? '+' : ''}{m.absolute_delta.toFixed(2)}</TableCell>
                        <TableCell className={cn("font-mono text-right", m.is_improvement ? "text-green-500" : "text-red-400")}>
                          {m.percentage_delta >= 0 ? '+' : ''}{formatPercent(m.percentage_delta / 100)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
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
