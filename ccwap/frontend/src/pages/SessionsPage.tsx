import { useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router'
import type { ColumnDef } from '@tanstack/react-table'
import { PageLayout } from '@/components/layout/PageLayout'
import type { BreadcrumbItem } from '@/components/layout/Breadcrumbs'
import { DataTable } from '@/components/composite/DataTable'
import { ErrorState } from '@/components/composite/ErrorState'
import { ExportDropdown } from '@/components/composite/ExportDropdown'
import { Badge } from '@/components/ui/badge'
import { useDateRange } from '@/hooks/useDateRange'
import { useSessions } from '@/api/sessions'
import { formatCurrency, formatNumber, formatDuration } from '@/lib/utils'

interface SessionListItem {
  session_id: string
  project_path: string
  project_display: string | null
  first_timestamp: string | null
  last_timestamp: string | null
  duration_seconds: number
  cost: number
  turns: number
  user_turns: number
  tool_calls: number
  errors: number
  is_agent: boolean
  cc_version: string | null
  git_branch: string | null
  model: string | null
}

const sessionColumns: ColumnDef<SessionListItem, unknown>[] = [
  {
    id: 'session',
    header: 'Session',
    cell: ({ row }) => {
      const s = row.original
      return (
        <div>
          <Link
            to={`/sessions/${s.session_id}`}
            className="text-primary hover:underline font-mono text-xs"
            onClick={e => e.stopPropagation()}
          >
            {s.session_id.slice(0, 12)}...
          </Link>
          <div className="text-xs text-muted-foreground mt-0.5">
            {s.first_timestamp
              ? new Date(s.first_timestamp).toLocaleString()
              : 'N/A'}
          </div>
          <div className="flex gap-1 mt-0.5">
            {s.is_agent && (
              <Badge variant="secondary" className="bg-purple-500/20 text-purple-400 text-[10px] px-1 py-0.5">
                agent
              </Badge>
            )}
          </div>
        </div>
      )
    },
  },
  {
    accessorKey: 'project_display',
    header: 'Project',
    cell: ({ row }) => {
      const s = row.original
      return (
        <span className="truncate block max-w-[200px]">
          {s.project_display || s.project_path}
        </span>
      )
    },
  },
  {
    accessorKey: 'cost',
    header: () => <div className="text-right">Cost</div>,
    cell: ({ getValue }) => <div className="text-right font-mono whitespace-nowrap">{formatCurrency(getValue<number>())}</div>,
  },
  {
    accessorKey: 'duration_seconds',
    header: () => <div className="text-right">Duration</div>,
    cell: ({ getValue }) => <div className="text-right font-mono whitespace-nowrap">{formatDuration(getValue<number>())}</div>,
  },
  {
    accessorKey: 'turns',
    header: () => <div className="text-right">Turns</div>,
    cell: ({ row }) => {
      const s = row.original
      return (
        <div className="text-right font-mono">
          {formatNumber(s.turns)}
          <span className="text-muted-foreground text-xs ml-1" title="user turns">
            ({s.user_turns} user)
          </span>
        </div>
      )
    },
  },
  {
    accessorKey: 'tool_calls',
    header: () => <div className="text-right">Tools</div>,
    cell: ({ getValue }) => <div className="text-right font-mono">{formatNumber(getValue<number>())}</div>,
  },
  {
    accessorKey: 'errors',
    header: () => <div className="text-right">Errors</div>,
    cell: ({ getValue }) => {
      const v = getValue<number>()
      return (
        <div className="text-right font-mono">
          <span className={v > 0 ? 'text-amber-400' : ''}>{v}</span>
        </div>
      )
    },
  },
  {
    accessorKey: 'model',
    header: 'Model',
    cell: ({ getValue }) => (
      <span className="font-mono text-xs truncate block max-w-[120px]">{getValue<string>() || 'N/A'}</span>
    ),
  },
  {
    accessorKey: 'git_branch',
    header: 'Branch',
    cell: ({ getValue }) => (
      <span className="font-mono text-xs truncate block max-w-[120px]">{getValue<string>() || ''}</span>
    ),
  },
]

export default function SessionsPage() {
  const [searchParams] = useSearchParams()
  const project = searchParams.get('project') || undefined
  const { dateRange } = useDateRange()
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useSessions(dateRange, project, page)

  const handlePageChange = useCallback((pageIndex: number) => {
    setPage(pageIndex + 1) // DataTable uses 0-indexed, API uses 1-indexed
  }, [])

  const projectDisplay = project?.replace(/^.*--/, '').replace(/-/g, '/') || null

  const breadcrumbs: BreadcrumbItem[] | undefined = project
    ? [
        { label: 'Projects', href: '/projects' },
        { label: projectDisplay || 'Project' },
      ]
    : undefined

  if (error) return <ErrorState message={error.message} />

  return (
    <PageLayout
      title="Sessions"
      subtitle={projectDisplay ? `Filtered by ${projectDisplay}` : 'All sessions'}
      breadcrumbs={breadcrumbs}
      actions={
        data?.sessions && (
          <ExportDropdown
            page="sessions"
            getData={() =>
              (data?.sessions || []).map(s => ({
                session_id: s.session_id,
                project: s.project_display || s.project_path,
                timestamp: s.first_timestamp || '',
                duration: s.duration_seconds,
                cost: s.cost,
                turns: s.turns,
                tool_calls: s.tool_calls,
                errors: s.errors,
                model: s.model || '',
                branch: s.git_branch || '',
              }))
            }
            columns={['session_id', 'project', 'timestamp', 'duration', 'cost', 'turns', 'tool_calls', 'errors', 'model', 'branch']}
          />
        )
      }
    >
      <DataTable
        columns={sessionColumns}
        data={(data?.sessions ?? []) as SessionListItem[]}
        isLoading={isLoading}
        emptyMessage="No sessions found"
        pagination={data ? {
          pageIndex: page - 1,
          pageSize: data.pagination.limit,
          pageCount: data.pagination.total_pages,
          totalRows: data.pagination.total_count,
          onPageChange: handlePageChange,
        } : undefined}
      />
    </PageLayout>
  )
}
