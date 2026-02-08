import { describe, it, expect } from 'vitest'
import { cn, formatCurrency, formatNumber, formatPercent, formatDuration } from '@/lib/utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible')
  })

  it('handles undefined and null inputs', () => {
    expect(cn('base', undefined, null, 'end')).toBe('base end')
  })

  it('returns empty string for no arguments', () => {
    expect(cn()).toBe('')
  })

  it('deduplicates tailwind conflicts using tailwind-merge', () => {
    // tailwind-merge should resolve px-2 vs px-4 to the last one
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })

  it('handles array inputs via clsx', () => {
    expect(cn(['foo', 'bar'])).toBe('foo bar')
  })

  it('handles object inputs via clsx', () => {
    expect(cn({ foo: true, bar: false, baz: true })).toBe('foo baz')
  })
})

describe('formatCurrency', () => {
  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.0000')
  })

  it('formats small decimals to 4 places', () => {
    expect(formatCurrency(0.0012)).toBe('$0.0012')
  })

  it('formats larger values', () => {
    expect(formatCurrency(12.5)).toBe('$12.5000')
  })

  it('rounds to 4 decimal places', () => {
    expect(formatCurrency(1.23456789)).toBe('$1.2346')
  })

  it('formats negative values', () => {
    expect(formatCurrency(-5.1234)).toBe('$-5.1234')
  })
})

describe('formatNumber', () => {
  it('formats millions', () => {
    expect(formatNumber(1_500_000)).toBe('1.5M')
  })

  it('formats exactly 1 million', () => {
    expect(formatNumber(1_000_000)).toBe('1.0M')
  })

  it('formats thousands', () => {
    expect(formatNumber(2_500)).toBe('2.5K')
  })

  it('formats exactly 1 thousand', () => {
    expect(formatNumber(1_000)).toBe('1.0K')
  })

  it('formats values below 1000 with locale string', () => {
    // toLocaleString behavior may vary, but for small integers should be the number itself
    expect(formatNumber(42)).toBe('42')
  })

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0')
  })

  it('formats 999 without K suffix', () => {
    expect(formatNumber(999)).toBe('999')
  })

  it('formats values just at the million boundary', () => {
    expect(formatNumber(999_999)).toBe('1000.0K')
  })
})

describe('formatPercent', () => {
  it('formats 0', () => {
    expect(formatPercent(0)).toBe('0.0%')
  })

  it('formats 1.0 as 100%', () => {
    expect(formatPercent(1)).toBe('100.0%')
  })

  it('formats fractional value', () => {
    expect(formatPercent(0.456)).toBe('45.6%')
  })

  it('formats small percentage', () => {
    expect(formatPercent(0.003)).toBe('0.3%')
  })

  it('formats value over 1 (over 100%)', () => {
    expect(formatPercent(1.5)).toBe('150.0%')
  })
})

describe('formatDuration', () => {
  it('formats seconds only when under a minute', () => {
    expect(formatDuration(45)).toBe('45s')
  })

  it('formats zero seconds', () => {
    expect(formatDuration(0)).toBe('0s')
  })

  it('formats exactly 59 seconds', () => {
    expect(formatDuration(59)).toBe('59s')
  })

  it('formats minutes and seconds', () => {
    expect(formatDuration(90)).toBe('1m 30s')
  })

  it('formats exactly 60 seconds as 1m 0s', () => {
    expect(formatDuration(60)).toBe('1m 0s')
  })

  it('formats large minute values under an hour', () => {
    expect(formatDuration(3599)).toBe('59m 59s')
  })

  it('formats hours and minutes', () => {
    expect(formatDuration(3600)).toBe('1h 0m')
  })

  it('formats hours with remaining minutes', () => {
    expect(formatDuration(3661)).toBe('1h 1m')
  })

  it('formats large hour values', () => {
    expect(formatDuration(7200)).toBe('2h 0m')
  })

  it('drops seconds from hours display', () => {
    // 1h 30m 45s should show as 1h 30m (seconds dropped)
    expect(formatDuration(5445)).toBe('1h 30m')
  })
})
