import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { apiFetch, buildQuery } from './client'
import { searchKeys } from './keys'

export interface SearchResult {
  category: string
  label: string
  sublabel: string
  url: string
}

export interface SearchResponse {
  results: SearchResult[]
  query: string
}

export function useSearch(query: string) {
  return useQuery({
    queryKey: searchKeys.query(query),
    queryFn: () => apiFetch<SearchResponse>(
      `/search${buildQuery({ q: query })}`
    ),
    enabled: query.length >= 2,
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  })
}
