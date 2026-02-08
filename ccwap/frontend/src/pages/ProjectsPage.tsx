import { useState, useCallback } from 'react'
import { Link } from 'react-router'
import { ChevronDown, ChevronUp, Search, ChevronLeft, ChevronRight, ChevronsUpDown } from 'lucide-react'
import { PageLayout } from '@/components/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import { useProjects } from '@/api/projects'
import type { ProjectData } from '@/api/projects'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatCurrency, formatNumber, formatPercent, formatDuration, cn } from '@/lib/utils'
import { ExportDropdown } from '@/components/ExportDropdown'

type SortField = 'cost' | 'sessions' | 'loc_written' | 'error_rate' | 'messages' | 'tool_calls' | 'cost_per_kloc' | 'tokens_per_loc' | 'cache_hit_rate'
type SortOrder = 'asc' | 'desc'

interface Column {
  key: SortField
  label: string
  format: (v: number) => string
  align?: 'left' | 'right'
}

const defaultColumns: Column[] = [
  { key: 'sessions', label: 'Sessions', format: formatNumber, align: 'right' },
  { key: 'cost', label: 'Cost', format: formatCurrency, align: 'right' },
  { key: 'loc_written', label: 'LOC', format: formatNumber, align: 'right' },
  { key: 'messages', label: 'Messages', format: formatNumber, align: 'right' },
  { key: 'tool_calls', label: 'Tool Calls', format: formatNumber, align: 'right' },
  { key: 'error_rate', label: 'Error Rate', format: formatPercent, align: 'right' },
  { key: 'cost_per_kloc', label: '$/kLOC', format: formatCurrency, align: 'right' },
  { key: 'cache_hit_rate', label: 'Cache Hit', format: formatPercent, align: 'right' },
]

function ExpandedRow({ project }: { project: ProjectData }) {
  const fields = [
    ['Sessions', formatNumber(project.sessions)],
    ['Messages', formatNumber(project.messages)],
    ['User Turns', formatNumber(project.user_turns)],
    ['Duration', formatDuration(project.duration_seconds)],
    ['Cost', formatCurrency(project.cost)],
    ['Avg Turn Cost', formatCurrency(project.avg_turn_cost)],
    ['Cost/kLOC', formatCurrency(project.cost_per_kloc)],
    ['Tokens/LOC', formatNumber(project.tokens_per_loc)],
    ['LOC Written', formatNumber(project.loc_written)],
    ['LOC Delivered', formatNumber(project.loc_delivered)],
    ['Lines Added', formatNumber(project.lines_added)],
    ['Lines Deleted', formatNumber(project.lines_deleted)],
    ['Files Created', formatNumber(project.files_created)],
    ['Files Edited', formatNumber(project.files_edited)],
    ['Input Tokens', formatNumber(project.input_tokens)],
    ['Output Tokens', formatNumber(project.output_tokens)],
    ['Cache Read', formatNumber(project.cache_read_tokens)],
    ['Cache Write', formatNumber(project.cache_write_tokens)],
    ['Cache Hit Rate', formatPercent(project.cache_hit_rate)],
    ['Thinking Chars', formatNumber(project.thinking_chars)],
    ['Tool Calls', formatNumber(project.tool_calls)],
    ['Errors', formatNumber(project.error_count)],
    ['Error Rate', formatPercent(project.error_rate)],
    ['Agent Spawns', formatNumber(project.agent_spawns)],
  ] as const

  return (
    <tr>
      <td colSpan={defaultColumns.length + 1} className="p-0">
        <div className="bg-accent/30 p-4 border-t border-border">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-x-6 gap-y-2">
            {fields.map(([label, value]) => (
              <div key={label} className="flex justify-between text-sm">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-mono">{value}</span>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <Link
              to={`/sessions?project=${encodeURIComponent(project.project_path)}`}
              className="text-sm text-primary hover:underline"
            >
              View Sessions &rarr;
            </Link>
          </div>
        </div>
      </td>
    </tr>
  )
}

export default function ProjectsPage() {
  const { dateRange } = useDateRange()
  const [sort, setSort] = useState<SortField>('cost')
  const [order, setOrder] = useState<SortOrder>('desc')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  const { data, isLoading, error } = useProjects(dateRange, sort, order, page, search || undefined)

  const handleSort = useCallback((field: SortField) => {
    if (sort === field) {
      setOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSort(field)
      setOrder('desc')
    }
    setPage(1)
  }, [sort])

  const toggleExpand = useCallback((path: string) => {
    setExpandedRow(prev => prev === path ? null : path)
  }, [])

  return (
    <PageLayout
      title="Projects"
      subtitle="Project-level metrics and drill-down"
      actions={
        data?.projects && <ExportDropdown
          page="projects"
          getData={() => (data?.projects || []).map(p => ({
            project: p.project_display,
            sessions: p.sessions,
            cost: p.cost,
            loc_written: p.loc_written,
            error_rate: p.error_rate,
            messages: p.messages,
            tool_calls: p.tool_calls,
            cost_per_kloc: p.cost_per_kloc,
          }))}
          columns={['project', 'sessions', 'cost', 'loc_written', 'error_rate', 'messages', 'tool_calls', 'cost_per_kloc']}
        />
      }
    >
      {/* Search */}
      <div className="mb-4 relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search projects..."
          className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {isLoading ? <LoadingState message="Loading projects..." /> :
       error ? <ErrorState message={error.message} /> :
       !data || data.projects.length === 0 ? <EmptyState message="No projects found" /> : (
        <>
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Project</th>
                    {defaultColumns.map(col => (
                      <th
                        key={col.key}
                        onClick={() => handleSort(col.key)}
                        className="px-4 py-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors text-right whitespace-nowrap"
                      >
                        <span className="inline-flex items-center gap-1">
                          {col.label}
                          {sort === col.key ? (
                            order === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronsUpDown className="h-3 w-3 opacity-30" />
                          )}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.projects.map(p => (
                    <>
                      <tr
                        key={p.project_path}
                        onClick={() => toggleExpand(p.project_path)}
                        className={cn(
                          "border-b border-border cursor-pointer transition-colors",
                          expandedRow === p.project_path ? "bg-accent/20" : "hover:bg-accent/10"
                        )}
                      >
                        <td className="px-4 py-3 font-medium truncate max-w-xs">
                          <Link
                            to={`/projects/${btoa(unescape(encodeURIComponent(p.project_path)))}`}
                            onClick={e => e.stopPropagation()}
                            className="text-primary hover:underline"
                          >
                            {p.project_display}
                          </Link>
                        </td>
                        {defaultColumns.map(col => (
                          <td key={col.key} className="px-4 py-3 font-mono text-right whitespace-nowrap">
                            {col.format(p[col.key])}
                          </td>
                        ))}
                      </tr>
                      {expandedRow === p.project_path && <ExpandedRow key={`${p.project_path}-expanded`} project={p} />}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {data.pagination.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-sm text-muted-foreground">
                Page {data.pagination.page} of {data.pagination.total_pages} ({data.pagination.total_count} projects)
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-2 rounded border border-border hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(data.pagination.total_pages, p + 1))}
                  disabled={page >= data.pagination.total_pages}
                  className="p-2 rounded border border-border hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </PageLayout>
  )
}
