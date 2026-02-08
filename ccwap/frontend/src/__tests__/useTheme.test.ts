import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTheme } from '@/hooks/useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark', 'light')
  })

  it('defaults to dark theme when localStorage is empty', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')
  })

  it('reads stored theme from localStorage', () => {
    localStorage.setItem('ccwap-theme', 'light')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('light')
  })

  it('applies theme class to document.documentElement on mount', () => {
    const { result } = renderHook(() => useTheme())
    expect(document.documentElement.classList.contains(result.current.theme)).toBe(true)
  })

  it('toggles from dark to light', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.theme).toBe('light')
  })

  it('toggles from light to dark', () => {
    localStorage.setItem('ccwap-theme', 'light')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('light')

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.theme).toBe('dark')
  })

  it('persists theme to localStorage on toggle', () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.toggleTheme()
    })

    expect(localStorage.getItem('ccwap-theme')).toBe('light')
  })

  it('removes the previous theme class before adding the new one', () => {
    const { result } = renderHook(() => useTheme())
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    act(() => {
      result.current.toggleTheme()
    })

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(document.documentElement.classList.contains('light')).toBe(true)
  })

  it('toggleTheme is referentially stable across renders', () => {
    const { result, rerender } = renderHook(() => useTheme())
    const firstToggle = result.current.toggleTheme
    rerender()
    expect(result.current.toggleTheme).toBe(firstToggle)
  })
})
