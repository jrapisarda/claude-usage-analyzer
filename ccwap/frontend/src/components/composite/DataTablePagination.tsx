import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react'

import { Button } from '@/components/ui/button'

interface DataTablePaginationProps {
  pageIndex: number
  pageSize: number
  pageCount: number
  totalRows?: number
  onPageChange: (pageIndex: number) => void
}

export function DataTablePagination({
  pageIndex,
  pageSize,
  pageCount,
  totalRows,
  onPageChange,
}: DataTablePaginationProps) {
  const canPreviousPage = pageIndex > 0
  const canNextPage = pageIndex < pageCount - 1

  const from = pageIndex * pageSize + 1
  const to = totalRows
    ? Math.min((pageIndex + 1) * pageSize, totalRows)
    : (pageIndex + 1) * pageSize

  return (
    <div className="flex items-center justify-between px-2 py-4">
      <div className="text-sm text-muted-foreground">
        {totalRows != null ? (
          <>
            Showing {from}-{to} of {totalRows} rows
          </>
        ) : (
          <>
            Page {pageIndex + 1} of {pageCount}
          </>
        )}
      </div>
      <div className="flex items-center space-x-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(0)}
          disabled={!canPreviousPage}
          aria-label="Go to first page"
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(pageIndex - 1)}
          disabled={!canPreviousPage}
          aria-label="Go to previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(pageIndex + 1)}
          disabled={!canNextPage}
          aria-label="Go to next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(pageCount - 1)}
          disabled={!canNextPage}
          aria-label="Go to last page"
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
