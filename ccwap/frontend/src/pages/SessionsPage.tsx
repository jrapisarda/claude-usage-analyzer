import { useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ChevronLeft, ChevronRight, ArrowLeft } from 'lucide-react'
import { PageLayout } from '@/components/PageLayout'
import { useDateRange } from '@/hooks/useDateRange'
import { useSessions } from '@/api/sessions'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatCurrency, formatNumber, formatDuration } from '@/lib/utils'
import { ExportDropdown } from '@/components/ExportDropdown'

export default function SessionsPage() {
  const [searchParams] = useSearchParams()
  const project = searchParams.get('project') || undefined
  const { dateRange } = useDateRange()
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useSessions(dateRange, project, page)

  const handlePrev = useCallback(() => setPage(p => Math.max(1, p - 1)), [])
  const handleNext = useCallback(
    () => setPage(p => Math.min(data?.pagination.total_pages ?? p, p + 1)),
    [data],
  )

  const projectDisplay = project?.replace(/^.*--/, '').replace(/-/g, '/') || null

  return (
    <PageLayout
      title="Sessions"
      subtitle={projectDisplay ? `Filtered by ${projectDisplay}` : 'All sessions'}
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
      {/* Back link */}
      {project && (
        <Link
          to="/projects"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4" /> Back to projects
        </Link>
      )}

      {isLoading ? (
        <LoadingState message="Loading sessions..." />
      ) : error ? (
        <ErrorState message={error.message} />
      ) : !data || data.sessions.length === 0 ? (
        <EmptyState message="No sessions found" />
      ) : (
        <>
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Session</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Project</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Cost</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Duration</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Turns</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Tools</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Errors</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Model</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Branch</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sessions.map(s => (
                    <tr
                      key={s.session_id}
                      className="border-b border-border hover:bg-accent/10 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <Link
                          to={`/sessions/${s.session_id}`}
                          className="text-primary hover:underline font-mono text-xs"
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
                            <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1 py-0.5 rounded">
                              agent
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 truncate max-w-[200px]">
                        {s.project_display || s.project_path}
                      </td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">
                        {formatCurrency(s.cost)}
                      </td>
                      <td className="px-4 py-3 font-mono text-right whitespace-nowrap">
                        {formatDuration(s.duration_seconds)}
                      </td>
                      <td className="px-4 py-3 font-mono text-right">
                        {formatNumber(s.turns)}
                        <span className="text-muted-foreground text-xs ml-1" title="user turns">
                          ({s.user_turns} user)
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-right">
                        {formatNumber(s.tool_calls)}
                      </td>
                      <td className="px-4 py-3 font-mono text-right">
                        <span className={s.errors > 0 ? 'text-amber-400' : ''}>
                          {s.errors}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs truncate max-w-[120px]">
                        {s.model || 'N/A'}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs truncate max-w-[120px]">
                        {s.git_branch || ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {data.pagination.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-sm text-muted-foreground">
                Page {data.pagination.page} of {data.pagination.total_pages} (
                {data.pagination.total_count} sessions)
              </span>
              <div className="flex gap-2">
                <button
                  onClick={handlePrev}
                  disabled={page <= 1}
                  className="p-2 rounded border border-border hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={handleNext}
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
