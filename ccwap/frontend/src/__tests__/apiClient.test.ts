import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch, buildQuery, ApiError } from '@/api/client'

describe('buildQuery', () => {
  it('returns empty string for empty object', () => {
    expect(buildQuery({})).toBe('')
  })

  it('returns empty string when all values are null', () => {
    expect(buildQuery({ a: null, b: undefined })).toBe('')
  })

  it('returns empty string when all values are empty strings', () => {
    expect(buildQuery({ a: '', b: '' })).toBe('')
  })

  it('builds query string for single param', () => {
    expect(buildQuery({ foo: 'bar' })).toBe('?foo=bar')
  })

  it('builds query string for multiple params', () => {
    const result = buildQuery({ from: '2025-01-01', to: '2025-01-31' })
    expect(result).toBe('?from=2025-01-01&to=2025-01-31')
  })

  it('filters out null and undefined values', () => {
    const result = buildQuery({ from: '2025-01-01', to: null, page: undefined })
    expect(result).toBe('?from=2025-01-01')
  })

  it('filters out empty string values', () => {
    const result = buildQuery({ from: '2025-01-01', search: '' })
    expect(result).toBe('?from=2025-01-01')
  })

  it('encodes special characters', () => {
    const result = buildQuery({ q: 'hello world', path: 'foo/bar' })
    expect(result).toBe('?q=hello%20world&path=foo%2Fbar')
  })

  it('handles numeric values', () => {
    const result = buildQuery({ page: 1, limit: 50 })
    expect(result).toBe('?page=1&limit=50')
  })

  it('handles zero as a valid value', () => {
    const result = buildQuery({ count: 0 })
    expect(result).toBe('?count=0')
  })
})

describe('ApiError', () => {
  it('creates an error with status and message', () => {
    const err = new ApiError(404, 'Not found')
    expect(err).toBeInstanceOf(Error)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(404)
    expect(err.message).toBe('Not found')
    expect(err.detail).toBeUndefined()
  })

  it('creates an error with status, message, and detail', () => {
    const err = new ApiError(422, 'Validation error', 'Invalid date format')
    expect(err.status).toBe(422)
    expect(err.message).toBe('Validation error')
    expect(err.detail).toBe('Invalid date format')
  })
})

describe('apiFetch', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('makes a GET request to /api + path', async () => {
    const mockResponse = { data: 'test' }
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response)

    const result = await apiFetch('/dashboard')

    expect(fetch).toHaveBeenCalledWith('/api/dashboard', expect.objectContaining({
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
      }),
    }))
    expect(result).toEqual(mockResponse)
  })

  it('includes Content-Type header by default', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response)

    await apiFetch('/test')

    const callArgs = vi.mocked(fetch).mock.calls[0]
    expect((callArgs[1] as RequestInit).headers).toEqual(
      expect.objectContaining({ 'Content-Type': 'application/json' })
    )
  })

  it('merges custom headers with defaults', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response)

    await apiFetch('/test', {
      headers: { 'X-Custom': 'value' },
    })

    const callArgs = vi.mocked(fetch).mock.calls[0]
    expect((callArgs[1] as RequestInit).headers).toEqual(
      expect.objectContaining({
        'Content-Type': 'application/json',
        'X-Custom': 'value',
      })
    )
  })

  it('passes through request init options', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response)

    await apiFetch('/test', { method: 'POST' })

    expect(fetch).toHaveBeenCalledWith('/api/test', expect.objectContaining({
      method: 'POST',
    }))
  })

  it('throws ApiError on non-ok response with error body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: 'Resource not found', detail: 'Session xyz missing' }),
    } as unknown as Response)

    await expect(apiFetch('/sessions/xyz')).rejects.toThrow(ApiError)

    try {
      await apiFetch('/sessions/xyz')
    } catch (e) {
      const err = e as ApiError
      expect(err.status).toBe(404)
      expect(err.message).toBe('Resource not found')
      expect(err.detail).toBe('Session xyz missing')
    }
  })

  it('throws ApiError with HTTP status message when json parse fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('invalid json')),
    } as unknown as Response)

    await expect(apiFetch('/bad')).rejects.toThrow(ApiError)

    try {
      await apiFetch('/bad')
    } catch (e) {
      const err = e as ApiError
      expect(err.status).toBe(500)
      expect(err.message).toBe('HTTP 500')
    }
  })

  it('returns parsed JSON on success', async () => {
    const payload = { sessions: [1, 2, 3], total: 3 }
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(payload),
    } as Response)

    const result = await apiFetch<typeof payload>('/sessions')
    expect(result).toEqual(payload)
  })
})
