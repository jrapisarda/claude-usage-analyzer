import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { ReactNode } from 'react'
import { useDateRange, presets } from '@/hooks/useDateRange'

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

function wrapperWithParams(initialEntries: string[]) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
  }
}

describe('useDateRange', () => {
  it('defaults to last-30-days preset', () => {
    const { result } = renderHook(() => useDateRange(), { wrapper })
    expect(result.current.preset).toBe('last-30-days')
  })

  it('provides a dateRange with from and to strings for last-30-days', () => {
    const { result } = renderHook(() => useDateRange(), { wrapper })
    expect(result.current.dateRange.from).toBeTruthy()
    expect(result.current.dateRange.to).toBeTruthy()
    // last-30-days: "to" should be today
    const today = new Date().toISOString().split('T')[0]
    expect(result.current.dateRange.to).toBe(today)
  })

  it('reads preset from URL search params', () => {
    const { result } = renderHook(() => useDateRange(), {
      wrapper: wrapperWithParams(['/?preset=today']),
    })
    expect(result.current.preset).toBe('today')
  })

  it('reads from/to from URL search params', () => {
    const { result } = renderHook(() => useDateRange(), {
      wrapper: wrapperWithParams(['/?from=2025-01-01&to=2025-01-31']),
    })
    expect(result.current.dateRange.from).toBe('2025-01-01')
    expect(result.current.dateRange.to).toBe('2025-01-31')
  })

  describe('setPreset', () => {
    it('changes the preset', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setPreset('today')
      })

      expect(result.current.preset).toBe('today')
    })

    it('updates dateRange when preset changes to today', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })
      const today = new Date().toISOString().split('T')[0]

      act(() => {
        result.current.setPreset('today')
      })

      expect(result.current.dateRange.from).toBe(today)
      expect(result.current.dateRange.to).toBe(today)
    })

    it('returns null from/to for all-time preset', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setPreset('all-time')
      })

      expect(result.current.dateRange.from).toBeNull()
      expect(result.current.dateRange.to).toBeNull()
    })
  })

  describe('setDateRange', () => {
    it('sets a custom date range and clears the preset', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setDateRange({ from: '2025-06-01', to: '2025-06-30' })
      })

      expect(result.current.dateRange.from).toBe('2025-06-01')
      expect(result.current.dateRange.to).toBe('2025-06-30')
      expect(result.current.preset).toBeNull()
    })
  })

  describe('granularity', () => {
    it('returns daily for all-time (null dates)', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setPreset('all-time')
      })

      expect(result.current.granularity).toBe('daily')
    })

    it('returns daily for short date ranges (under 60 days)', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setDateRange({ from: '2025-01-01', to: '2025-01-30' })
      })

      expect(result.current.granularity).toBe('daily')
    })

    it('returns weekly for medium ranges (61-180 days)', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setDateRange({ from: '2025-01-01', to: '2025-04-15' })
      })

      // 104 days: > 60, <= 180 -> weekly
      expect(result.current.granularity).toBe('weekly')
    })

    it('returns monthly for long ranges (over 180 days)', () => {
      const { result } = renderHook(() => useDateRange(), { wrapper })

      act(() => {
        result.current.setDateRange({ from: '2024-01-01', to: '2025-01-01' })
      })

      // 366 days: > 180 -> monthly
      expect(result.current.granularity).toBe('monthly')
    })
  })

  describe('presets constant', () => {
    it('has 8 preset entries', () => {
      expect(presets).toHaveLength(8)
    })

    it('includes all expected presets', () => {
      const values = presets.map(p => p.value)
      expect(values).toEqual([
        'today', 'yesterday', 'this-week', 'last-week',
        'last-30-days', 'this-month', 'last-month', 'all-time',
      ])
    })

    it('each preset has a label and value', () => {
      for (const p of presets) {
        expect(p.label).toBeTruthy()
        expect(p.value).toBeTruthy()
      }
    })
  })
})
