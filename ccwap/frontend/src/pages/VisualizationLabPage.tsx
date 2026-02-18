import { useState, useMemo, useCallback } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ReferenceDot,
} from 'recharts'
import { type ColumnDef } from '@tanstack/react-table'
import { PageLayout } from '@/components/layout/PageLayout'
import { MetricCard } from '@/components/composite/MetricCard'
import { MetricCardGrid } from '@/components/composite/MetricCardGrid'
import { ChartContainer } from '@/components/composite/ChartContainer'
import { DataTable } from '@/components/composite/DataTable'
import { EmptyState } from '@/components/composite/EmptyState'
import { ErrorState } from '@/components/composite/ErrorState'
import { SavedViewsBar } from '@/components/composite/SavedViewsBar'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectLabel,
} from '@/components/ui/select'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useDateRange } from '@/hooks/useDateRange'
import { useExplorer, useExplorerFilters, type ExplorerParams, type FilterOption } from '@/api/explorer'
import { TOOLTIP_STYLE, CHART_COLORS } from '@/lib/chartConfig'
import { formatCurrency, formatNumber, formatDuration, cn } from '@/lib/utils'
import { ChevronDown, X } from 'lucide-react'

interface MetricOption {
  value: string
  label: string
  group: 'Turns' | 'Tools' | 'Sessions'
  formatter: 'number' | 'currency' | 'duration'
}

interface DimensionOption {
  value: string
  label: string
}

type RankBy = 'combined' | 'x' | 'y' | 'bubble'
type Quadrant = 'Q1' | 'Q2' | 'Q3' | 'Q4'

interface RawPoint {
  group: string
  rawX: number
  rawY: number
  rawBubble: number
  ratio: number | null
}

interface PlotPoint extends RawPoint {
  x: number
  y: number
  bubbleSize: number
  quadrant: Quadrant
}

interface RegressionLine {
  slope: number
  intercept: number
  xStart: number
  xEnd: number
  yStart: number
  yEnd: number
}

const METRICS: MetricOption[] = [
  { value: 'cost', label: 'Cost ($)', group: 'Turns', formatter: 'currency' },
  { value: 'input_tokens', label: 'Input Tokens', group: 'Turns', formatter: 'number' },
  { value: 'output_tokens', label: 'Output Tokens', group: 'Turns', formatter: 'number' },
  { value: 'cache_read_tokens', label: 'Cache Read Tokens', group: 'Turns', formatter: 'number' },
  { value: 'cache_write_tokens', label: 'Cache Write Tokens', group: 'Turns', formatter: 'number' },
  { value: 'ephemeral_5m_tokens', label: 'Ephemeral 5m Tokens', group: 'Turns', formatter: 'number' },
  { value: 'ephemeral_1h_tokens', label: 'Ephemeral 1h Tokens', group: 'Turns', formatter: 'number' },
  { value: 'thinking_chars', label: 'Thinking Chars', group: 'Turns', formatter: 'number' },
  { value: 'turns_count', label: 'Turns Count', group: 'Turns', formatter: 'number' },
  { value: 'loc_written', label: 'LOC Written', group: 'Tools', formatter: 'number' },
  { value: 'tool_calls_count', label: 'Tool Calls', group: 'Tools', formatter: 'number' },
  { value: 'errors', label: 'Errors', group: 'Tools', formatter: 'number' },
  { value: 'lines_added', label: 'Lines Added', group: 'Tools', formatter: 'number' },
  { value: 'lines_deleted', label: 'Lines Deleted', group: 'Tools', formatter: 'number' },
  { value: 'sessions_count', label: 'Sessions', group: 'Sessions', formatter: 'number' },
  { value: 'duration_seconds', label: 'Duration (s)', group: 'Sessions', formatter: 'duration' },
]

const ALL_DIMENSIONS: DimensionOption[] = [
  { value: 'date', label: 'Date' },
  { value: 'model', label: 'Model' },
  { value: 'project', label: 'Project' },
  { value: 'branch', label: 'Branch' },
  { value: 'language', label: 'Language' },
  { value: 'tool_name', label: 'Tool Name' },
  { value: 'cc_version', label: 'CC Version' },
  { value: 'entry_type', label: 'Entry Type' },
  { value: 'is_agent', label: 'Agent/User' },
]

const TURNS_DIMS = new Set(['date', 'model', 'project', 'branch', 'cc_version', 'entry_type', 'is_agent'])
const TOOL_DIMS = new Set(['date', 'model', 'project', 'branch', 'language', 'tool_name', 'cc_version', 'entry_type', 'is_agent'])
const SESSION_DIMS = new Set(['date', 'project', 'branch', 'cc_version', 'is_agent'])

const TURNS_METRICS_SET = new Set(['cost', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens', 'ephemeral_5m_tokens', 'ephemeral_1h_tokens', 'thinking_chars', 'turns_count'])
const TOOL_METRICS_SET = new Set(['loc_written', 'tool_calls_count', 'errors', 'lines_added', 'lines_deleted'])

const METRIC_LOOKUP = new Map(METRICS.map(m => [m.value, m]))
const DIMENSION_LOOKUP = new Map(ALL_DIMENSIONS.map(d => [d.value, d]))
const QUADRANT_COLORS: Record<Quadrant, string> = {
  Q1: CHART_COLORS[0],
  Q2: CHART_COLORS[1],
  Q3: CHART_COLORS[2],
  Q4: CHART_COLORS[3],
}

function getAllowedDims(metric: string | null): Set<string> {
  if (!metric) return new Set()
  if (TURNS_METRICS_SET.has(metric)) return TURNS_DIMS
  if (TOOL_METRICS_SET.has(metric)) return TOOL_DIMS
  return SESSION_DIMS
}

function formatMetricValue(value: number, metric: string | null): string {
  if (!Number.isFinite(value)) return 'N/A'
  const option = metric ? METRIC_LOOKUP.get(metric) : null
  if (option?.formatter === 'currency') return formatCurrency(value)
  if (option?.formatter === 'duration') return formatDuration(Math.max(0, Math.round(value)))
  return formatNumber(value)
}

function formatRatio(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A'
  return value.toFixed(4)
}

function formatAxisTick(value: number, metric: string | null, isLogScale: boolean): string {
  const rawValue = isLogScale ? Math.pow(10, value) : value
  return formatMetricValue(rawValue, metric)
}

function parseErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Failed to load visualization data'
}

function toStringList(input: unknown): string[] {
  if (Array.isArray(input)) {
    return input.map(v => String(v).trim()).filter(Boolean)
  }
  if (typeof input === 'string') {
    return input.split(',').map(v => v.trim()).filter(Boolean)
  }
  return []
}

function toNullableString(input: unknown): string | null {
  if (typeof input !== 'string') return null
  const trimmed = input.trim()
  return trimmed.length > 0 ? trimmed : null
}

function toBoolean(input: unknown, fallback: boolean): boolean {
  if (typeof input === 'boolean') return input
  if (typeof input === 'string') {
    if (input.toLowerCase() === 'true') return true
    if (input.toLowerCase() === 'false') return false
  }
  return fallback
}

function clampTopN(value: number): number {
  return Math.max(10, Math.min(1000, Math.floor(value)))
}

function toPositiveInt(input: unknown, fallback: number): number {
  if (typeof input === 'number' && Number.isFinite(input)) return clampTopN(input)
  if (typeof input === 'string') {
    const parsed = Number(input)
    if (Number.isFinite(parsed)) return clampTopN(parsed)
  }
  return clampTopN(fallback)
}

function toRankBy(input: unknown): RankBy {
  if (input === 'combined' || input === 'x' || input === 'y' || input === 'bubble') {
    return input
  }
  return 'combined'
}

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2
  }
  return sorted[mid]
}

function computePearson(points: Pick<PlotPoint, 'x' | 'y'>[]): number | null {
  if (points.length < 2) return null
  const n = points.length

  let sumX = 0
  let sumY = 0
  let sumXX = 0
  let sumYY = 0
  let sumXY = 0

  for (const point of points) {
    sumX += point.x
    sumY += point.y
    sumXX += point.x * point.x
    sumYY += point.y * point.y
    sumXY += point.x * point.y
  }

  const numerator = (n * sumXY) - (sumX * sumY)
  const denominator = Math.sqrt(((n * sumXX) - (sumX * sumX)) * ((n * sumYY) - (sumY * sumY)))

  if (denominator === 0) return null
  return numerator / denominator
}

function computeRegression(points: Pick<PlotPoint, 'x' | 'y'>[]): RegressionLine | null {
  if (points.length < 2) return null

  const n = points.length
  let sumX = 0
  let sumY = 0
  let sumXX = 0
  let sumXY = 0

  for (const point of points) {
    sumX += point.x
    sumY += point.y
    sumXX += point.x * point.x
    sumXY += point.x * point.y
  }

  const denominator = (n * sumXX) - (sumX * sumX)
  if (denominator === 0) return null

  const slope = ((n * sumXY) - (sumX * sumY)) / denominator
  const intercept = (sumY - (slope * sumX)) / n

  const xValues = points.map(p => p.x)
  const xStart = Math.min(...xValues)
  const xEnd = Math.max(...xValues)

  return {
    slope,
    intercept,
    xStart,
    xEnd,
    yStart: (slope * xStart) + intercept,
    yEnd: (slope * xEnd) + intercept,
  }
}

function classifyQuadrant(x: number, y: number, medianX: number | null, medianY: number | null): Quadrant {
  if (medianX === null || medianY === null) return 'Q1'
  if (x >= medianX && y >= medianY) return 'Q1'
  if (x < medianX && y >= medianY) return 'Q2'
  if (x < medianX && y < medianY) return 'Q3'
  return 'Q4'
}

function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: FilterOption[]
  selected: string[]
  onChange: (values: string[]) => void
}) {
  const [open, setOpen] = useState(false)

  const toggle = useCallback((value: string) => {
    onChange(
      selected.includes(value)
        ? selected.filter(v => v !== value)
        : [...selected, value]
    )
  }, [onChange, selected])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'w-full justify-between text-sm font-normal h-9',
            selected.length > 0 && 'ring-1 ring-primary/30',
          )}
        >
          <span className="truncate">
            {selected.length > 0 ? `${label} (${selected.length})` : label}
          </span>
          <div className="flex items-center gap-1 shrink-0 ml-1">
            {selected.length > 0 && (
              <X
                className="h-3 w-3 text-muted-foreground hover:text-foreground"
                onClick={(event) => {
                  event.stopPropagation()
                  onChange([])
                }}
              />
            )}
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <ScrollArea className="max-h-60">
          <div className="p-1">
            {options.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">No options</p>
            ) : options.map(opt => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-accent/50 cursor-pointer text-sm rounded-sm"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(opt.value)}
                  onChange={() => toggle(opt.value)}
                  className="rounded border-border"
                />
                <span className="flex-1 truncate">{opt.label}</span>
                <span className="text-xs text-muted-foreground">{opt.count}</span>
              </label>
            ))}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )
}

export default function VisualizationLabPage() {
  const { dateRange } = useDateRange()

  const [xMetric, setXMetric] = useState<string | null>('cost')
  const [yMetric, setYMetric] = useState<string | null>('loc_written')
  const [bubbleMetric, setBubbleMetric] = useState<string | null>(null)
  const [groupBy, setGroupBy] = useState<string | null>('project')
  const [rankBy, setRankBy] = useState<RankBy>('combined')
  const [topN, setTopN] = useState<number>(120)

  const [logX, setLogX] = useState(false)
  const [logY, setLogY] = useState(false)
  const [showTrendline, setShowTrendline] = useState(true)
  const [showQuadrants, setShowQuadrants] = useState(true)

  const [selProjects, setSelProjects] = useState<string[]>([])
  const [selModels, setSelModels] = useState<string[]>([])
  const [selBranches, setSelBranches] = useState<string[]>([])
  const [selLanguages, setSelLanguages] = useState<string[]>([])

  const availableDimensions = useMemo(() => {
    if (!xMetric || !yMetric) return [] as DimensionOption[]

    const common = new Set<string>(getAllowedDims(xMetric))
    const yAllowed = getAllowedDims(yMetric)

    for (const dim of [...common]) {
      if (!yAllowed.has(dim)) common.delete(dim)
    }

    if (bubbleMetric) {
      const bubbleAllowed = getAllowedDims(bubbleMetric)
      for (const dim of [...common]) {
        if (!bubbleAllowed.has(dim)) common.delete(dim)
      }
    }

    return ALL_DIMENSIONS.filter(dim => common.has(dim.value))
  }, [xMetric, yMetric, bubbleMetric])

  const effectiveGroupBy = groupBy && availableDimensions.some(dim => dim.value === groupBy)
    ? groupBy
    : null

  const sharedParams = useMemo(() => ({
    from: dateRange.from,
    to: dateRange.to,
    projects: selProjects.length > 0 ? selProjects.join(',') : null,
    models: selModels.length > 0 ? selModels.join(',') : null,
    branches: selBranches.length > 0 ? selBranches.join(',') : null,
    languages: selLanguages.length > 0 ? selLanguages.join(',') : null,
  }), [dateRange.from, dateRange.to, selProjects, selModels, selBranches, selLanguages])

  const xParams: ExplorerParams = {
    metric: xMetric,
    group_by: effectiveGroupBy,
    ...sharedParams,
  }

  const yParams: ExplorerParams = {
    metric: yMetric,
    group_by: effectiveGroupBy,
    ...sharedParams,
  }

  const bubbleNeedsFetch = !!bubbleMetric && bubbleMetric !== xMetric && bubbleMetric !== yMetric

  const bubbleParams: ExplorerParams = {
    metric: bubbleNeedsFetch ? bubbleMetric : null,
    group_by: bubbleNeedsFetch ? effectiveGroupBy : null,
    ...sharedParams,
  }

  const xQuery = useExplorer(xParams)
  const yQuery = useExplorer(yParams)
  const bubbleQuery = useExplorer(bubbleParams)

  const { data: filterData } = useExplorerFilters(dateRange.from, dateRange.to)

  const bubbleData = useMemo(() => {
    if (!bubbleMetric) return null
    if (bubbleMetric === xMetric) return xQuery.data ?? null
    if (bubbleMetric === yMetric) return yQuery.data ?? null
    return bubbleQuery.data ?? null
  }, [bubbleMetric, bubbleQuery.data, xMetric, xQuery.data, yMetric, yQuery.data])

  const mergedPoints = useMemo<RawPoint[]>(() => {
    if (!xQuery.data || !yQuery.data) return []

    const xMap = new Map<string, number>()
    for (const row of xQuery.data.rows) {
      xMap.set(row.group, row.value)
    }

    const yMap = new Map<string, number>()
    for (const row of yQuery.data.rows) {
      yMap.set(row.group, row.value)
    }

    const bubbleMap = new Map<string, number>()
    if (bubbleMetric && bubbleData) {
      for (const row of bubbleData.rows) {
        bubbleMap.set(row.group, row.value)
      }
    }

    const points: RawPoint[] = []
    for (const [group, rawX] of xMap.entries()) {
      if (!yMap.has(group)) continue
      const rawY = yMap.get(group) ?? 0
      const rawBubble = bubbleMetric ? (bubbleMap.get(group) ?? 0) : 1
      points.push({
        group,
        rawX,
        rawY,
        rawBubble,
        ratio: rawX !== 0 ? rawY / rawX : null,
      })
    }

    return points
  }, [bubbleData, bubbleMetric, xQuery.data, yQuery.data])

  const rankedPoints = useMemo(() => {
    const sorted = [...mergedPoints]
    const score = (point: RawPoint): number => {
      if (rankBy === 'x') return point.rawX
      if (rankBy === 'y') return point.rawY
      if (rankBy === 'bubble') return point.rawBubble
      return Math.abs(point.rawX) + Math.abs(point.rawY)
    }

    sorted.sort((a, b) => score(b) - score(a))
    return sorted.slice(0, clampTopN(topN))
  }, [mergedPoints, rankBy, topN])

  const plotted = useMemo(() => {
    const filtered: Omit<PlotPoint, 'bubbleSize' | 'quadrant'>[] = []
    let droppedByScale = 0

    for (const point of rankedPoints) {
      if ((logX && point.rawX <= 0) || (logY && point.rawY <= 0)) {
        droppedByScale += 1
        continue
      }

      const x = logX ? Math.log10(point.rawX) : point.rawX
      const y = logY ? Math.log10(point.rawY) : point.rawY

      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        droppedByScale += 1
        continue
      }

      filtered.push({ ...point, x, y })
    }

    const bubbleValues = filtered.map(p => p.rawBubble)
    const minBubble = bubbleValues.length > 0 ? Math.min(...bubbleValues) : 0
    const maxBubble = bubbleValues.length > 0 ? Math.max(...bubbleValues) : 0

    const toBubbleSize = (value: number): number => {
      if (!bubbleMetric) return 90
      if (minBubble === maxBubble) return 120
      const normalized = (value - minBubble) / (maxBubble - minBubble)
      return 40 + (normalized * 220)
    }

    const medianX = median(filtered.map(p => p.x))
    const medianY = median(filtered.map(p => p.y))

    const points: PlotPoint[] = filtered.map(point => ({
      ...point,
      bubbleSize: toBubbleSize(point.rawBubble),
      quadrant: classifyQuadrant(point.x, point.y, medianX, medianY),
    }))

    return {
      points,
      droppedByScale,
      medianX,
      medianY,
      minBubble,
      maxBubble,
    }
  }, [bubbleMetric, logX, logY, rankedPoints])

  const correlation = useMemo(() => computePearson(plotted.points), [plotted.points])
  const trendline = useMemo(
    () => showTrendline ? computeRegression(plotted.points) : null,
    [plotted.points, showTrendline],
  )

  const quadrantCounts = useMemo(() => {
    const counts: Record<Quadrant, number> = { Q1: 0, Q2: 0, Q3: 0, Q4: 0 }
    for (const point of plotted.points) {
      counts[point.quadrant] += 1
    }
    return counts
  }, [plotted.points])

  const highestYPoint = useMemo(() => {
    if (plotted.points.length === 0) return null
    return plotted.points.reduce((best, point) => (point.rawY > best.rawY ? point : best), plotted.points[0])
  }, [plotted.points])

  const bestRatioPoint = useMemo(() => {
    const ratioPoints = plotted.points.filter(point => point.ratio !== null)
    if (ratioPoints.length === 0) return null
    return ratioPoints.reduce((best, point) => ((point.ratio ?? -Infinity) > (best.ratio ?? -Infinity) ? point : best), ratioPoints[0])
  }, [plotted.points])

  const averageRatio = useMemo(() => {
    const values = plotted.points
      .map(point => point.ratio)
      .filter((value): value is number => value !== null && Number.isFinite(value))

    if (values.length === 0) return null
    return values.reduce((sum, value) => sum + value, 0) / values.length
  }, [plotted.points])

  const xLabel = METRIC_LOOKUP.get(xMetric ?? '')?.label ?? 'X Axis'
  const yLabel = METRIC_LOOKUP.get(yMetric ?? '')?.label ?? 'Y Axis'
  const bubbleLabel = bubbleMetric ? (METRIC_LOOKUP.get(bubbleMetric)?.label ?? 'Bubble') : 'Bubble (fixed)'
  const groupLabel = DIMENSION_LOOKUP.get(effectiveGroupBy ?? '')?.label ?? 'Group'

  const tableColumns: ColumnDef<PlotPoint, unknown>[] = useMemo(() => {
    const columns: ColumnDef<PlotPoint, unknown>[] = [
      {
        accessorKey: 'group',
        header: groupLabel,
        cell: ({ row }) => <span className="font-medium truncate max-w-[240px] block">{row.original.group}</span>,
      },
      {
        accessorKey: 'rawX',
        header: () => <span className="text-right block">{xLabel}</span>,
        cell: ({ row }) => <span className="font-mono text-right block">{formatMetricValue(row.original.rawX, xMetric)}</span>,
      },
      {
        accessorKey: 'rawY',
        header: () => <span className="text-right block">{yLabel}</span>,
        cell: ({ row }) => <span className="font-mono text-right block">{formatMetricValue(row.original.rawY, yMetric)}</span>,
      },
    ]

    if (bubbleMetric) {
      columns.push({
        accessorKey: 'rawBubble',
        header: () => <span className="text-right block">{bubbleLabel}</span>,
        cell: ({ row }) => <span className="font-mono text-right block">{formatMetricValue(row.original.rawBubble, bubbleMetric)}</span>,
      })
    }

    columns.push({
      accessorKey: 'ratio',
      header: () => <span className="text-right block">Y/X Ratio</span>,
      cell: ({ row }) => <span className="font-mono text-right block">{formatRatio(row.original.ratio)}</span>,
    })

    columns.push({
      accessorKey: 'quadrant',
      header: 'Quadrant',
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.quadrant}</span>,
    })

    return columns
  }, [bubbleLabel, bubbleMetric, groupLabel, xLabel, xMetric, yLabel, yMetric])

  const onApplySavedView = useCallback((filters: Record<string, unknown>) => {
    setXMetric(toNullableString(filters.x_metric))
    setYMetric(toNullableString(filters.y_metric))
    setBubbleMetric(toNullableString(filters.bubble_metric))
    setGroupBy(toNullableString(filters.group_by))

    setSelProjects(toStringList(filters.projects))
    setSelModels(toStringList(filters.models))
    setSelBranches(toStringList(filters.branches))
    setSelLanguages(toStringList(filters.languages))

    setRankBy(toRankBy(filters.rank_by))
    setTopN(toPositiveInt(filters.top_n, 120))
    setLogX(toBoolean(filters.log_x, false))
    setLogY(toBoolean(filters.log_y, false))
    setShowTrendline(toBoolean(filters.show_trendline, true))
    setShowQuadrants(toBoolean(filters.show_quadrants, true))
  }, [])

  const currentFilters = useMemo(() => ({
    x_metric: xMetric,
    y_metric: yMetric,
    bubble_metric: bubbleMetric,
    group_by: effectiveGroupBy,
    projects: selProjects,
    models: selModels,
    branches: selBranches,
    languages: selLanguages,
    rank_by: rankBy,
    top_n: topN,
    log_x: logX,
    log_y: logY,
    show_trendline: showTrendline,
    show_quadrants: showQuadrants,
  }), [
    xMetric,
    yMetric,
    bubbleMetric,
    effectiveGroupBy,
    selProjects,
    selModels,
    selBranches,
    selLanguages,
    rankBy,
    topN,
    logX,
    logY,
    showTrendline,
    showQuadrants,
  ])

  const canQuery = !!xMetric && !!yMetric && !!effectiveGroupBy

  const isLoading = canQuery && (
    xQuery.isLoading
    || yQuery.isLoading
    || (bubbleNeedsFetch && bubbleQuery.isLoading)
  )

  const queryError = xQuery.error ?? yQuery.error ?? (bubbleNeedsFetch ? bubbleQuery.error : null)

  const getExportData = useCallback(() => {
    return plotted.points.map(point => ({
      group: point.group,
      x_metric: xMetric,
      x_value: point.rawX,
      y_metric: yMetric,
      y_value: point.rawY,
      bubble_metric: bubbleMetric,
      bubble_value: point.rawBubble,
      y_over_x_ratio: point.ratio,
      quadrant: point.quadrant,
    }))
  }, [bubbleMetric, plotted.points, xMetric, yMetric])

  const controlsDisabled = !xMetric || !yMetric

  return (
    <PageLayout
      title="Visualization Lab"
      subtitle="Pick any metric for X/Y axes and compare relationships across any shared dimension"
      actions={<ExportDropdown page="visualization-lab" getData={getExportData} />}
    >
      <SavedViewsBar
        page="visualization-lab"
        currentFilters={currentFilters}
        onApply={onApplySavedView}
        from={dateRange.from}
        to={dateRange.to}
        defaultMetricForAlert={yMetric ?? xMetric ?? 'cost'}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">X Axis Metric</label>
          <Select
            value={xMetric ?? '__none__'}
            onValueChange={(value) => setXMetric(value === '__none__' ? null : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose X metric" />
            </SelectTrigger>
            <SelectContent>
              {['Turns', 'Tools', 'Sessions'].map(group => (
                <SelectGroup key={`x-${group}`}>
                  <SelectLabel>{group}</SelectLabel>
                  {METRICS.filter(metric => metric.group === group).map(metric => (
                    <SelectItem key={metric.value} value={metric.value}>{metric.label}</SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-1">Y Axis Metric</label>
          <Select
            value={yMetric ?? '__none__'}
            onValueChange={(value) => setYMetric(value === '__none__' ? null : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose Y metric" />
            </SelectTrigger>
            <SelectContent>
              {['Turns', 'Tools', 'Sessions'].map(group => (
                <SelectGroup key={`y-${group}`}>
                  <SelectLabel>{group}</SelectLabel>
                  {METRICS.filter(metric => metric.group === group).map(metric => (
                    <SelectItem key={metric.value} value={metric.value}>{metric.label}</SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-1">Bubble Metric (optional)</label>
          <Select
            value={bubbleMetric ?? '__none__'}
            onValueChange={(value) => setBubbleMetric(value === '__none__' ? null : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Fixed size" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">Fixed size</SelectItem>
              {['Turns', 'Tools', 'Sessions'].map(group => (
                <SelectGroup key={`bubble-${group}`}>
                  <SelectLabel>{group}</SelectLabel>
                  {METRICS.filter(metric => metric.group === group).map(metric => (
                    <SelectItem key={metric.value} value={metric.value}>{metric.label}</SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-1">Group By</label>
          <Select
            value={effectiveGroupBy ?? '__none__'}
            onValueChange={(value) => setGroupBy(value === '__none__' ? null : value)}
            disabled={controlsDisabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose shared dimension" />
            </SelectTrigger>
            <SelectContent>
              {availableDimensions.map(dim => (
                <SelectItem key={dim.value} value={dim.value}>{dim.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {filterData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <MultiSelect
            label="Projects"
            options={filterData.projects}
            selected={selProjects}
            onChange={setSelProjects}
          />
          <MultiSelect
            label="Models"
            options={filterData.models}
            selected={selModels}
            onChange={setSelModels}
          />
          <MultiSelect
            label="Branches"
            options={filterData.branches}
            selected={selBranches}
            onChange={setSelBranches}
          />
          <MultiSelect
            label="Languages"
            options={filterData.languages}
            selected={selLanguages}
            onChange={setSelLanguages}
          />
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2 mb-6">
        <div className="min-w-[180px]">
          <label className="block text-xs text-muted-foreground mb-1">Rank and Keep Top N</label>
          <div className="flex items-center gap-2">
            <Select value={rankBy} onValueChange={(value) => setRankBy(toRankBy(value))}>
              <SelectTrigger className="h-9 w-[150px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="combined">Combined</SelectItem>
                <SelectItem value="x">X Axis</SelectItem>
                <SelectItem value="y">Y Axis</SelectItem>
                <SelectItem value="bubble">Bubble</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="number"
              min={10}
              max={1000}
              step={10}
              value={topN}
              onChange={(event) => setTopN(toPositiveInt(event.target.value, topN))}
              className="w-24"
            />
          </div>
        </div>

        <Button size="sm" variant={logX ? 'default' : 'outline'} onClick={() => setLogX(prev => !prev)}>
          Log X
        </Button>
        <Button size="sm" variant={logY ? 'default' : 'outline'} onClick={() => setLogY(prev => !prev)}>
          Log Y
        </Button>
        <Button size="sm" variant={showTrendline ? 'default' : 'outline'} onClick={() => setShowTrendline(prev => !prev)}>
          Trendline
        </Button>
        <Button size="sm" variant={showQuadrants ? 'default' : 'outline'} onClick={() => setShowQuadrants(prev => !prev)}>
          Quadrants
        </Button>
      </div>

      {!canQuery ? (
        <EmptyState message="Select X metric, Y metric, and a shared group dimension" />
      ) : isLoading ? (
        <>
          <MetricCardGrid skeleton count={4} className="mb-6" />
          <ChartContainer title="Scatter" height={420} isLoading>
            <ScatterChart />
          </ChartContainer>
        </>
      ) : queryError ? (
        <ErrorState message={parseErrorMessage(queryError)} />
      ) : plotted.points.length === 0 ? (
        <EmptyState
          message={
            plotted.droppedByScale > 0
              ? 'No plottable points with current log settings. Disable log scale or adjust filters.'
              : 'No overlapping data between selected X and Y metrics for current filters.'
          }
        />
      ) : (
        <>
          <MetricCardGrid className="mb-6">
            <MetricCard title="Overlapping Groups" value={formatNumber(mergedPoints.length)} subtitle={`Grouped by ${groupLabel}`} />
            <MetricCard
              title="Rendered Points"
              value={formatNumber(plotted.points.length)}
              subtitle={plotted.droppedByScale > 0 ? `${formatNumber(plotted.droppedByScale)} removed by log scale` : undefined}
            />
            <MetricCard
              title="Pearson Correlation"
              value={correlation === null ? 'N/A' : correlation.toFixed(3)}
              subtitle={logX || logY ? 'Computed in log space' : 'Computed in linear space'}
            />
            <MetricCard
              title="Avg Y/X Ratio"
              value={formatRatio(averageRatio)}
              subtitle={`${yLabel} per ${xLabel}`}
            />
          </MetricCardGrid>

          <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-6">
            <ChartContainer title={`${yLabel} vs ${xLabel} by ${groupLabel}`} height={420} className="xl:col-span-3">
              <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={xLabel}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(value) => formatAxisTick(value, xMetric, logX)}
                  stroke="var(--color-muted-foreground)"
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name={yLabel}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(value) => formatAxisTick(value, yMetric, logY)}
                  stroke="var(--color-muted-foreground)"
                  width={72}
                />
                <ZAxis type="number" dataKey="bubbleSize" range={bubbleMetric ? [40, 260] : [90, 90]} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelFormatter={(_label, payload) => {
                    const point = payload?.[0]?.payload as PlotPoint | undefined
                    return point?.group ?? ''
                  }}
                  formatter={(_value, name, item) => {
                    const point = item.payload as PlotPoint
                    if (name === 'x') return [formatMetricValue(point.rawX, xMetric), xLabel]
                    if (name === 'y') return [formatMetricValue(point.rawY, yMetric), yLabel]
                    if (name === 'bubbleSize') return [formatMetricValue(point.rawBubble, bubbleMetric), bubbleLabel]
                    return [String(_value), String(name)]
                  }}
                />

                {showQuadrants && plotted.medianX !== null && (
                  <ReferenceLine x={plotted.medianX} stroke="var(--color-muted-foreground)" strokeDasharray="4 4" />
                )}
                {showQuadrants && plotted.medianY !== null && (
                  <ReferenceLine y={plotted.medianY} stroke="var(--color-muted-foreground)" strokeDasharray="4 4" />
                )}

                {showTrendline && trendline && (
                  <ReferenceLine
                    segment={[
                      { x: trendline.xStart, y: trendline.yStart },
                      { x: trendline.xEnd, y: trendline.yEnd },
                    ]}
                    stroke="var(--color-chart-5)"
                    strokeDasharray="5 5"
                  />
                )}

                {highestYPoint && (
                  <ReferenceDot
                    x={highestYPoint.x}
                    y={highestYPoint.y}
                    r={4}
                    fill="var(--color-foreground)"
                    stroke="var(--color-background)"
                    strokeWidth={1}
                  />
                )}

                <Scatter data={plotted.points} name={`${yLabel} vs ${xLabel}`}>
                  {plotted.points.map((point, index) => (
                    <Cell key={`${point.group}-${index}`} fill={QUADRANT_COLORS[point.quadrant]} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ChartContainer>

            <Card>
              <CardHeader className="pb-3 pt-4 px-4">
                <CardTitle className="text-sm font-medium text-muted-foreground">Insights</CardTitle>
                <span className="text-xs text-muted-foreground">Auto-generated from current plot</span>
              </CardHeader>
              <CardContent className="px-4 pb-4 space-y-3 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Highest {yLabel}</p>
                  <p className="font-medium truncate" title={highestYPoint?.group ?? 'N/A'}>{highestYPoint?.group ?? 'N/A'}</p>
                  <p className="font-mono text-xs">{highestYPoint ? formatMetricValue(highestYPoint.rawY, yMetric) : 'N/A'}</p>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground">Best Y/X Ratio</p>
                  <p className="font-medium truncate" title={bestRatioPoint?.group ?? 'N/A'}>{bestRatioPoint?.group ?? 'N/A'}</p>
                  <p className="font-mono text-xs">{bestRatioPoint ? formatRatio(bestRatioPoint.ratio) : 'N/A'}</p>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground">Quadrants</p>
                  <div className="grid grid-cols-2 gap-1 text-xs font-mono">
                    <span>Q1: {quadrantCounts.Q1}</span>
                    <span>Q2: {quadrantCounts.Q2}</span>
                    <span>Q3: {quadrantCounts.Q3}</span>
                    <span>Q4: {quadrantCounts.Q4}</span>
                  </div>
                </div>

                {bubbleMetric && (
                  <div>
                    <p className="text-xs text-muted-foreground">Bubble Range</p>
                    <p className="font-mono text-xs">{formatMetricValue(plotted.minBubble, bubbleMetric)} - {formatMetricValue(plotted.maxBubble, bubbleMetric)}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-3 pt-4 px-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">Paired Data</CardTitle>
              <span className="text-xs text-muted-foreground">Rows plotted in current chart ({plotted.points.length})</span>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <DataTable
                columns={tableColumns}
                data={plotted.points}
                emptyMessage="No paired data"
              />
            </CardContent>
          </Card>
        </>
      )}
    </PageLayout>
  )
}
