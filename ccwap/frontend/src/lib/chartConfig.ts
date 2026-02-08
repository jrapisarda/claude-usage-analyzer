export const TOOLTIP_STYLE = {
  backgroundColor: 'var(--color-card)',
  color: 'var(--color-card-foreground)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
  fontSize: '12px',
}

export const AXIS_STYLE = {
  fontSize: 11,
  fill: 'var(--color-muted-foreground)',
}

export const CHART_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
]

export const TOKEN_COLORS = {
  input: 'var(--color-token-input)',
  output: 'var(--color-token-output)',
  cache_read: 'var(--color-token-cache-read)',
  cache_write: 'var(--color-token-cache-write)',
}

/**
 * Fill missing keys with zeros in data arrays for stacked charts.
 * Stacked charts require every data point to have all keys present.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function fillZeros<T>(
  data: T[],
  keys: string[],
): T[] {
  return data.map(d => {
    const filled = { ...d } as any
    for (const k of keys) {
      if (filled[k] == null) filled[k] = 0
    }
    return filled as T
  })
}

export function getStaleTime(dateRange: { from: string | null; to: string | null }): number {
  if (!dateRange.from && !dateRange.to) return 5 * 60 * 1000 // all-time: 5min
  // Dynamic import would be circular, just compare dates directly
  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  if (dateRange.to === todayStr) return 2 * 60 * 1000 // includes today: 2min
  return Infinity // historical range: never refetch
}

export function shouldAnimate(dataLength: number): boolean {
  return dataLength < 200
}
