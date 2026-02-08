import { useState, useCallback, Fragment } from 'react'
import { Link } from 'react-router'
import type { ColumnDef } from '@tanstack/react-table'
import { Search } from 'lucide-react'
import { PageLayout } from '@/components/layout/PageLayout'
import { DataTable } from '@/components/composite/DataTable'
import { ErrorState } from '@/components/composite/ErrorState'
import { EmptyState } from '@/components/composite/EmptyState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { Input } from '@/components/ui/input'
import { useDateRange } from '@/hooks/useDateRange'
import { useProjects } from '@/api/projects'
import type { ProjectData } from '@/api/projects'
import { formatCurrency, formatNumber, formatPercent, formatDuration } from '@/lib/utils'

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
  )
}

type SortField = 'cost' | 'sessions' | 'loc_written' | 'error_rate' | 'messages' | 'tool_calls' | 'cost_per_kloc' | 'tokens_per_loc' | 'cache_hit_rate'

const projectColumns: ColumnDef<ProjectData, unknown>[] = [
  {
    id: 'project_display',
    accessorKey: 'project_display',
    header: 'Project',
    enableSorting: false,
    cell: ({ row }) => {
      const p = row.original
      return (
        <Link
          to={`/projects/${btoa(unescape(encodeURIComponent(p.project_path)))}`}
          onClick={e => e.stopPropagation()}
          className="text-primary hover:underline font-medium truncate block max-w-xs"
        >
          {p.project_display}
        </Link>
      )
    },
  },
  {
    accessorKey: 'sessions',
    header: () => <div className="text-right">Sessions</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'cost',
    header: () => <div className="text-right">Cost</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatCurrency(getValue<number>())}</div>,
  },
  {
    accessorKey: 'loc_written',
    header: () => <div className="text-right">LOC</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'messages',
    header: () => <div className="text-right">Messages</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'tool_calls',
    header: () => <div className="text-right">Tool Calls</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'error_rate',
    header: () => <div className="text-right">Error Rate</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatPercent(getValue<number>())}</div>,
  },
  {
    accessorKey: 'cost_per_kloc',
    header: () => <div className="text-right">$/kLOC</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatCurrency(getValue<number>())}</div>,
  },
  {
    accessorKey: 'cache_hit_rate',
    header: () => <div className="text-right">Cache Hit</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatPercent(getValue<number>())}</div>,
  },
]

export default function ProjectsPage() {
  const { dateRange } = useDateRange()
  const [sort, setSort] = useState<SortField>('cost')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  const { data, isLoading, error } = useProjects(dateRange, sort, order, page, search || undefined)

  const handleSort = useCallback((columnId: string, direction: 'asc' | 'desc') => {
    setSort(columnId as SortField)
    setOrder(direction)
    setPage(1)
  }, [])

  const handlePageChange = useCallback((pageIndex: number) => {
    setPage(pageIndex + 1) // DataTable uses 0-indexed, API uses 1-indexed
  }, [])

  if (error) return <ErrorState message={error.message} />

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
        <Input
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search projects..."
          className="pl-9"
        />
      </div>

      {!data || data.projects.length === 0 ? (
        isLoading ? null : <EmptyState message="No projects found" />
      ) : (
        <>
          {/* We use the DataTable for column headers and server-side sort,
              but render custom rows with expansion support */}
          <div className="rounded-md border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  {projectColumns.map((col) => {
                    const colId = ('accessorKey' in col ? col.accessorKey : col.id) as string
                    const isSorted = sort === colId
                    const canSort = col.enableSorting !== false && colId !== 'project_display'
                    return (
                      <th
                        key={colId}
                        onClick={() => {
                          if (!canSort) return
                          if (isSorted) {
                            handleSort(colId, order === 'asc' ? 'desc' : 'asc')
                          } else {
                            handleSort(colId, 'desc')
                          }
                        }}
                        className={`px-4 py-3 font-medium text-muted-foreground text-sm whitespace-nowrap ${
                          colId === 'project_display' ? 'text-left' : 'text-right'
                        } ${canSort ? 'cursor-pointer hover:text-foreground transition-colors' : ''}`}
                      >
                        <span className="inline-flex items-center gap-1">
                          {typeof col.header === 'function' ? (col.header as any)({}) : col.header}
                          {canSort && isSorted && (
                            <span className="text-xs">{order === 'asc' ? '\u25B2' : '\u25BC'}</span>
                          )}
                        </span>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {data.projects.map(p => (
                  <Fragment key={p.project_path}>
                    <tr
                      onClick={() => setExpandedRow(prev => prev === p.project_path ? null : p.project_path)}
                      className={`border-b border-border cursor-pointer transition-colors ${
                        expandedRow === p.project_path ? 'bg-accent/20' : 'hover:bg-accent/10'
                      }`}
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
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatNumber(p.sessions)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatCurrency(p.cost)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatNumber(p.loc_written)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatNumber(p.messages)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatNumber(p.tool_calls)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatPercent(p.error_rate)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatCurrency(p.cost_per_kloc)}</td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">{formatPercent(p.cache_hit_rate)}</td>
                    </tr>
                    {expandedRow === p.project_path && (
                      <tr key={`${p.project_path}-expanded`}>
                        <td colSpan={projectColumns.length} className="p-0">
                          <ExpandedRow project={p} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
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
                  &lt;
                </button>
                <button
                  onClick={() => setPage(p => Math.min(data.pagination.total_pages, p + 1))}
                  disabled={page >= data.pagination.total_pages}
                  className="p-2 rounded border border-border hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  &gt;
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </PageLayout>
  )
}
