import { useState } from 'react'
import {
  type ColumnDef,
  type SortingState,
  type PaginationState,
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
} from '@tanstack/react-table'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { DataTablePagination } from '@/components/composite/DataTablePagination'
import { cn } from '@/lib/utils'

interface DataTablePaginationConfig {
  pageIndex: number
  pageSize: number
  pageCount: number
  totalRows?: number
  onPageChange: (pageIndex: number) => void
}

interface DataTableSortingConfig {
  sortBy: string
  sortDirection: 'asc' | 'desc'
  onSort: (columnId: string, direction: 'asc' | 'desc') => void
}

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  isLoading?: boolean
  pagination?: DataTablePaginationConfig
  sorting?: DataTableSortingConfig
  emptyMessage?: string
  onRowClick?: (row: TData) => void
  getRowClassName?: (row: TData) => string
}

export function DataTable<TData, TValue>({
  columns,
  data,
  isLoading = false,
  pagination,
  sorting: externalSorting,
  emptyMessage = 'No results.',
  onRowClick,
  getRowClassName,
}: DataTableProps<TData, TValue>) {
  const [internalSorting, setInternalSorting] = useState<SortingState>(
    externalSorting
      ? [{ id: externalSorting.sortBy, desc: externalSorting.sortDirection === 'desc' }]
      : []
  )

  const isServerSide = !!pagination?.onPageChange && !!externalSorting?.onSort

  const paginationState: PaginationState | undefined = pagination
    ? { pageIndex: pagination.pageIndex, pageSize: pagination.pageSize }
    : undefined

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting: externalSorting
        ? [{ id: externalSorting.sortBy, desc: externalSorting.sortDirection === 'desc' }]
        : internalSorting,
      ...(paginationState ? { pagination: paginationState } : {}),
    },
    onSortingChange: (updater) => {
      const newSorting = typeof updater === 'function' ? updater(internalSorting) : updater
      if (externalSorting && newSorting.length > 0) {
        externalSorting.onSort(newSorting[0].id, newSorting[0].desc ? 'desc' : 'asc')
      } else {
        setInternalSorting(newSorting)
      }
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: isServerSide ? undefined : getSortedRowModel(),
    getPaginationRowModel: isServerSide ? undefined : getPaginationRowModel(),
    ...(pagination ? { pageCount: pagination.pageCount, manualPagination: isServerSide } : {}),
    ...(externalSorting ? { manualSorting: isServerSide } : {}),
  })

  const skeletonRows = pagination?.pageSize ?? 10

  return (
    <div>
      <div className="rounded-md border border-border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: skeletonRows }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  {columns.map((_, j) => (
                    <TableCell key={`skeleton-${i}-${j}`}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && 'selected'}
                  className={cn(
                    getRowClassName?.(row.original),
                    onRowClick && 'cursor-pointer'
                  )}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {pagination && (
        <DataTablePagination
          pageIndex={pagination.pageIndex}
          pageSize={pagination.pageSize}
          pageCount={pagination.pageCount}
          totalRows={pagination.totalRows}
          onPageChange={pagination.onPageChange}
        />
      )}
    </div>
  )
}
