export interface DateRange {
  from?: string
  to?: string
}

export interface PaginationMeta {
  page: number
  limit: number
  total: number
  total_pages: number
}

export interface SortConfig {
  column: string
  direction: 'asc' | 'desc'
}
