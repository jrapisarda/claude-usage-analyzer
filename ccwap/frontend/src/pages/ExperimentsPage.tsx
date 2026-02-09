import { useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router'
import { Trash2, Plus, ArrowRightLeft, X, ChevronDown, ChevronUp, Zap, Lock } from 'lucide-react'
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
import type { TagCreatePayload, TagComparison, ComparisonMetric } from '@/api/experiments'
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
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
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

// Metric display configuration
const METRIC_LABELS: Record<string, string> = {
  cost: 'Total Cost',
  cost_per_kloc: 'Cost/KLOC',
  cache_hit_rate: 'Cache Hit Rate',
  loc_written: 'LOC Written',
  loc_delivered: 'LOC Delivered',
  files_created: 'Files Created',
  files_edited: 'Files Edited',
  input_tokens: 'Input Tokens',
  output_tokens: 'Output Tokens',
  tokens_per_loc: 'Tokens/LOC',
  thinking_chars: 'Thinking Chars',
  sessions: 'Sessions',
  user_turns: 'User Turns',
  tool_calls: 'Tool Calls',
  error_rate: 'Error Rate',
  agent_spawns: 'Agent Spawns',
}

const CATEGORY_LABELS: Record<string, string> = {
  cost: 'Cost & Efficiency',
  productivity: 'Productivity',
  tokens: 'Tokens',
  quality: 'Quality & Workflow',
}

const CATEGORY_ORDER = ['cost', 'productivity', 'tokens', 'quality']

function formatMetricValue(name: string, value: number): string {
  if (name === 'cost' || name === 'cost_per_kloc') return formatCurrency(value)
  if (name === 'error_rate' || name === 'cache_hit_rate') return formatPercent(value)
  if (name === 'input_tokens' || name === 'output_tokens' || name === 'thinking_chars')
    return value > 1000 ? `${(value / 1000).toFixed(1)}K` : formatNumber(value)
  return formatNumber(value)
}

function TagManager({ onTagClick, expandedTag }: { onTagClick: (tagName: string) => void; expandedTag: string | null }) {
  const { dateRange } = useDateRange()
  const { data, isLoading, error, refetch } = useTags()
  const createTag = useCreateTag()
  const deleteTag = useDeleteTag()
  const [newTagName, setNewTagName] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [projectPath, setProjectPath] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [ccVersion, setCcVersion] = useState('')
  const [model, setModel] = useState('')
  const [minCost, setMinCost] = useState('')
  const [maxCost, setMaxCost] = useState('')
  const [minLoc, setMinLoc] = useState('')
  const [maxLoc, setMaxLoc] = useState('')

  const { data: projectsData } = useProjects(dateRange, 'cost', 'desc', 1, undefined)

  const handleCreate = useCallback(() => {
    if (!newTagName.trim()) return
    const payload: TagCreatePayload = {
      tag_name: newTagName.trim(),
      ...(dateFrom && { date_from: dateFrom }),
      ...(dateTo && { date_to: dateTo }),
      ...(projectPath && { project_path: projectPath }),
      ...(ccVersion && { cc_version: ccVersion }),
      ...(model && { model }),
      ...(minCost && { min_cost: parseFloat(minCost) }),
      ...(maxCost && { max_cost: parseFloat(maxCost) }),
      ...(minLoc && { min_loc: parseInt(minLoc) }),
      ...(maxLoc && { max_loc: parseInt(maxLoc) }),
    }
    createTag.mutate(payload, {
      onSuccess: () => {
        setNewTagName(''); setDateFrom(''); setDateTo(''); setProjectPath('')
        setCcVersion(''); setModel(''); setMinCost(''); setMaxCost('')
        setMinLoc(''); setMaxLoc('')
      },
    })
  }, [newTagName, dateFrom, dateTo, projectPath, ccVersion, model, minCost, maxCost, minLoc, maxLoc, createTag])

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
        {/* Create form - Row 1: Core fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mb-2">
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
          <Select value={projectPath || '__all__'} onValueChange={v => setProjectPath(v === '__all__' ? '' : v)}>
            <SelectTrigger>
              <SelectValue placeholder="All Projects" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Projects</SelectItem>
              {projectsData?.projects.map(p => (
                <SelectItem key={p.project_path} value={p.project_path}>
                  {p.project_display}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex gap-1">
            <Button
              onClick={handleCreate}
              disabled={!newTagName.trim() || createTag.isPending}
              size="sm"
              className="h-9 flex-1"
            >
              <Plus className="mr-1 h-4 w-4" />
              Create
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-9 px-2"
              onClick={() => setShowAdvanced(!showAdvanced)}
              title="Advanced criteria"
            >
              <ChevronDown className={cn("h-4 w-4 transition-transform", showAdvanced && "rotate-180")} />
            </Button>
          </div>
        </div>

        {/* Row 2: Advanced criteria (collapsible) */}
        {showAdvanced && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-4 p-3 rounded-md bg-muted/30 border border-border/50">
            <Input
              type="text"
              value={ccVersion}
              onChange={e => setCcVersion(e.target.value)}
              placeholder="CC Version..."
              className="text-xs"
            />
            <Input
              type="text"
              value={model}
              onChange={e => setModel(e.target.value)}
              placeholder="Model (e.g. opus)..."
              className="text-xs"
            />
            <Input
              type="number"
              step="0.01"
              value={minCost}
              onChange={e => setMinCost(e.target.value)}
              placeholder="Min cost ($)..."
              className="text-xs"
            />
            <Input
              type="number"
              step="0.01"
              value={maxCost}
              onChange={e => setMaxCost(e.target.value)}
              placeholder="Max cost ($)..."
              className="text-xs"
            />
            <Input
              type="number"
              value={minLoc}
              onChange={e => setMinLoc(e.target.value)}
              placeholder="Min LOC..."
              className="text-xs"
            />
            <Input
              type="number"
              value={maxLoc}
              onChange={e => setMaxLoc(e.target.value)}
              placeholder="Max LOC..."
              className="text-xs"
            />
          </div>
        )}

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
                    className="flex flex-col gap-1 text-left"
                  >
                    <div className="flex items-center gap-3">
                      {expandedTag === tag.tag_name
                        ? <ChevronUp className="h-3 w-3 text-muted-foreground" />
                        : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
                      <span className="font-medium text-sm">{tag.tag_name}</span>
                      <Badge variant="secondary">{tag.session_count} sessions</Badge>
                      {tag.is_smart
                        ? <Badge variant="outline" className="text-cyan-400 border-cyan-400/30 gap-1"><Zap className="h-3 w-3" />Smart</Badge>
                        : <Badge variant="outline" className="text-muted-foreground gap-1"><Lock className="h-3 w-3" />Static</Badge>
                      }
                      {tag.created_at && <span className="text-xs text-muted-foreground">{tag.created_at}</span>}
                    </div>
                    {tag.is_smart && tag.criteria && (
                      <div className="flex flex-wrap gap-1.5 ml-6">
                        {tag.criteria.project_path && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            Project: {tag.criteria.project_path.split(/[/\\]/).pop()}
                          </span>
                        )}
                        {tag.criteria.date_from && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            From: {tag.criteria.date_from}
                          </span>
                        )}
                        {tag.criteria.date_to && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            To: {tag.criteria.date_to}
                          </span>
                        )}
                        {tag.criteria.cc_version && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            CC: {tag.criteria.cc_version}
                          </span>
                        )}
                        {tag.criteria.model && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            Model: {tag.criteria.model}
                          </span>
                        )}
                        {tag.criteria.min_cost != null && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            Min $: {tag.criteria.min_cost}
                          </span>
                        )}
                        {tag.criteria.max_cost != null && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            Max $: {tag.criteria.max_cost}
                          </span>
                        )}
                        {tag.criteria.min_loc != null && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            Min LOC: {tag.criteria.min_loc}
                          </span>
                        )}
                        {tag.criteria.max_loc != null && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
                            Max LOC: {tag.criteria.max_loc}
                          </span>
                        )}
                      </div>
                    )}
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
                  <div>
                    {/* Show criteria summary for smart tags */}
                    {tag.is_smart && tag.criteria && (
                      <div className="ml-6 mr-3 mb-2 p-2 rounded bg-muted/20 text-xs text-muted-foreground flex flex-wrap gap-3">
                        {tag.criteria.date_from && <span>From: {tag.criteria.date_from}</span>}
                        {tag.criteria.date_to && <span>To: {tag.criteria.date_to}</span>}
                        {tag.criteria.project_path && <span>Project: {tag.criteria.project_path}</span>}
                        {tag.criteria.cc_version && <span>CC: {tag.criteria.cc_version}</span>}
                        {tag.criteria.model && <span>Model: {tag.criteria.model}</span>}
                        {tag.criteria.min_cost != null && <span>Min $: {tag.criteria.min_cost}</span>}
                        {tag.criteria.max_cost != null && <span>Max $: {tag.criteria.max_cost}</span>}
                        {tag.criteria.min_loc != null && <span>Min LOC: {tag.criteria.min_loc}</span>}
                        {tag.criteria.max_loc != null && <span>Max LOC: {tag.criteria.max_loc}</span>}
                      </div>
                    )}
                    <TagSessionsList tagName={tag.tag_name} />
                  </div>
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

type MetricCategory = 'all' | 'cost' | 'productivity' | 'tokens' | 'quality'

const MULTI_CHART_METRICS: Record<MetricCategory, (keyof TagComparison)[]> = {
  all: ['sessions', 'cost', 'loc', 'turns', 'error_rate'],
  cost: ['cost', 'cost_per_kloc', 'cache_hit_rate'],
  productivity: ['loc', 'loc_delivered', 'files_created', 'files_edited'],
  tokens: ['input_tokens', 'output_tokens', 'tokens_per_loc', 'thinking_chars'],
  quality: ['sessions', 'turns', 'error_rate', 'agent_spawns'],
}

function MultiTagCharts({ tags }: { tags: TagComparison[] }) {
  const [category, setCategory] = useState<MetricCategory>('all')
  const metrics = MULTI_CHART_METRICS[category]

  const barData = useMemo(() => {
    return metrics.map(metric => {
      const entry: Record<string, any> = { metric }
      for (const tag of tags) {
        entry[tag.tag_name] = tag[metric]
      }
      return entry
    })
  }, [tags, metrics])

  const radarData = useMemo(() => {
    return metrics.map(metric => {
      const values = tags.map(t => t[metric] as number)
      const maxVal = Math.max(...values, 0.001)
      const entry: Record<string, any> = { metric }
      for (const tag of tags) {
        entry[tag.tag_name] = metric === 'error_rate'
          ? (1 - (tag[metric] as number)) * 100
          : ((tag[metric] as number) / maxVal) * 100
      }
      return entry
    })
  }, [tags, metrics])

  return (
    <div>
      {/* Category selector */}
      <div className="flex flex-wrap gap-1 mb-4">
        {(['all', 'cost', 'productivity', 'tokens', 'quality'] as MetricCategory[]).map(cat => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={cn(
              "px-3 py-1 rounded-full text-xs font-medium transition-colors",
              category === cat
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-accent"
            )}
          >
            {cat === 'all' ? 'Overview' : CATEGORY_LABELS[cat] || cat}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartContainer title="Metric Comparison" height={288}>
          <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <XAxis
              dataKey="metric"
              tick={{ fontSize: 10 }}
              stroke="var(--color-muted-foreground)"
              tickFormatter={(v: any) => METRIC_LABELS[v] || v}
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
              labelFormatter={(label: any) => METRIC_LABELS[label] || label}
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

        <ChartContainer title="Normalized Radar View" height={288}>
          <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid stroke="var(--color-border)" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }}
              tickFormatter={(v: any) => METRIC_LABELS[v] || v}
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

  // Group metrics by category
  const groupedMetrics = useMemo(() => {
    if (!comparison?.metrics) return []
    const groups: Record<string, ComparisonMetric[]> = {}
    for (const m of comparison.metrics) {
      const cat = m.category || 'general'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(m)
    }
    return CATEGORY_ORDER
      .filter(cat => groups[cat]?.length)
      .map(cat => ({ category: cat, label: CATEGORY_LABELS[cat] || cat, metrics: groups[cat] }))
  }, [comparison])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Compare Tags (A vs B)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 mb-4">
          <Select value={tagA || undefined} onValueChange={setTagA}>
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="Select Tag A..." />
            </SelectTrigger>
            <SelectContent>
              {tags.map(t => (
                <SelectItem key={t.tag_name} value={t.tag_name}>
                  {t.tag_name} ({t.session_count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <ArrowRightLeft className="h-4 w-4 text-muted-foreground shrink-0" />
          <Select value={tagB || undefined} onValueChange={setTagB}>
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="Select Tag B..." />
            </SelectTrigger>
            <SelectContent>
              {tags.map(t => (
                <SelectItem key={t.tag_name} value={t.tag_name}>
                  {t.tag_name} ({t.session_count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isLoading && <Skeleton className="h-32 w-full" />}
        {error && <ErrorState message={error.message} onRetry={() => refetch()} />}

        {comparison && (
          <div>
            <div className="flex gap-4 mb-4 text-sm">
              <span><strong>{comparison.tag_a}</strong>: {comparison.tag_a_sessions} sessions</span>
              <span><strong>{comparison.tag_b}</strong>: {comparison.tag_b_sessions} sessions</span>
            </div>

            {groupedMetrics.length === 0 ? (
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
                    {groupedMetrics.map(group => (
                      <>
                        <TableRow key={`cat-${group.category}`} className="bg-muted/30">
                          <TableCell colSpan={5} className="font-semibold text-xs text-muted-foreground uppercase tracking-wider py-1.5">
                            {group.label}
                          </TableCell>
                        </TableRow>
                        {group.metrics.map(m => (
                          <TableRow key={m.metric_name}>
                            <TableCell className="text-sm">{METRIC_LABELS[m.metric_name] || m.metric_name}</TableCell>
                            <TableCell className="font-mono text-right text-sm">{formatMetricValue(m.metric_name, m.tag_a_value)}</TableCell>
                            <TableCell className="font-mono text-right text-sm">{formatMetricValue(m.metric_name, m.tag_b_value)}</TableCell>
                            <TableCell className="font-mono text-right text-sm">
                              {m.absolute_delta >= 0 ? '+' : ''}{formatMetricValue(m.metric_name, m.absolute_delta)}
                            </TableCell>
                            <TableCell className={cn("font-mono text-right text-sm", m.is_improvement ? "text-green-500" : "text-red-400")}>
                              {m.percentage_delta >= 0 ? '+' : ''}{formatPercent(m.percentage_delta / 100)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </>
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
