import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useExport } from '@/hooks/useExport'

describe('useExport', () => {
  let mockCreateObjectURL: ReturnType<typeof vi.fn>
  let mockRevokeObjectURL: ReturnType<typeof vi.fn>
  let mockClick: ReturnType<typeof vi.fn>
  let capturedAnchor: { href: string; download: string }
  let capturedBlobContent: string
  let capturedBlobType: string
  let appendChildSpy: ReturnType<typeof vi.spyOn>
  let removeChildSpy: ReturnType<typeof vi.spyOn>

  const OriginalBlob = globalThis.Blob

  beforeEach(() => {
    mockCreateObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    mockRevokeObjectURL = vi.fn()
    mockClick = vi.fn()
    capturedAnchor = { href: '', download: '' }
    capturedBlobContent = ''
    capturedBlobType = ''

    URL.createObjectURL = mockCreateObjectURL as typeof URL.createObjectURL
    URL.revokeObjectURL = mockRevokeObjectURL as typeof URL.revokeObjectURL

    // Intercept Blob constructor to capture content before it's created
    globalThis.Blob = class MockBlob extends OriginalBlob {
      constructor(parts?: BlobPart[], options?: BlobPropertyBag) {
        super(parts, options)
        if (parts && parts.length > 0) {
          capturedBlobContent = String(parts[0])
        }
        capturedBlobType = options?.type ?? ''
      }
    } as typeof Blob

    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') {
        const anchor = {
          href: '',
          download: '',
          click: mockClick,
        } as unknown as HTMLAnchorElement
        return new Proxy(anchor, {
          set(target, prop, value) {
            if (prop === 'href') capturedAnchor.href = value as string
            if (prop === 'download') capturedAnchor.download = value as string
            ;(target as unknown as Record<string, unknown>)[prop as string] = value
            return true
          },
        })
      }
      return document.createElementNS('http://www.w3.org/1999/xhtml', tag) as HTMLElement
    })

    appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node)
    removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node)

    // Fix the date for deterministic filenames
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-05T12:00:00Z'))
  })

  afterEach(() => {
    globalThis.Blob = OriginalBlob
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  describe('CSV export', () => {
    it('creates a blob with BOM prefix', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ name: 'Alice', age: 30 }],
      })

      expect(capturedBlobContent.charCodeAt(0)).toBe(0xFEFF)
    })

    it('creates a blob with text/csv content type', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ name: 'Alice' }],
      })

      expect(capturedBlobType).toBe('text/csv;charset=utf-8')
    })

    it('escapes values containing commas by wrapping in double quotes', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ value: 'hello, world' }],
      })

      expect(capturedBlobContent).toContain('"hello, world"')
    })

    it('escapes values containing double quotes by doubling them', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ value: 'say "hi"' }],
      })

      // Quotes inside are doubled, entire field wrapped in quotes
      expect(capturedBlobContent).toContain('"say ""hi"""')
    })

    it('escapes values containing newlines', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ value: 'line1\nline2' }],
      })

      expect(capturedBlobContent).toContain('"line1\nline2"')
    })

    it('handles null and undefined values as empty strings', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        columns: ['a', 'b'],
        data: [{ a: null, b: undefined }],
      })

      // After BOM and header row "a,b\r\n", the data row should be ","
      const lines = capturedBlobContent.replace('\uFEFF', '').split('\r\n')
      expect(lines[1]).toBe(',')
    })

    it('uses specified columns order', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        columns: ['age', 'name'],
        data: [{ name: 'Alice', age: 30, extra: 'ignored' }],
      })

      const lines = capturedBlobContent.replace('\uFEFF', '').split('\r\n')
      // Header should follow columns order
      expect(lines[0]).toBe('age,name')
      // Data row should follow columns order, not object key order
      expect(lines[1]).toBe('30,Alice')
    })

    it('uses object keys as headers when columns are not specified', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ name: 'Alice', age: 30 }],
      })

      const lines = capturedBlobContent.replace('\uFEFF', '').split('\r\n')
      expect(lines[0]).toBe('name,age')
    })

    it('separates rows with CRLF', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ v: 1 }, { v: 2 }],
      })

      const withoutBom = capturedBlobContent.replace('\uFEFF', '')
      expect(withoutBom).toBe('v\r\n1\r\n2')
    })

    it('handles multiple data rows correctly', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        columns: ['id', 'name'],
        data: [
          { id: 1, name: 'Alice' },
          { id: 2, name: 'Bob' },
          { id: 3, name: 'Charlie' },
        ],
      })

      const lines = capturedBlobContent.replace('\uFEFF', '').split('\r\n')
      expect(lines).toHaveLength(4) // header + 3 data rows
      expect(lines[0]).toBe('id,name')
      expect(lines[1]).toBe('1,Alice')
      expect(lines[2]).toBe('2,Bob')
      expect(lines[3]).toBe('3,Charlie')
    })

    it('handles values with combined special characters', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ value: 'has "quotes", commas,\nand newlines' }],
      })

      // Should be escaped: quotes doubled, entire field wrapped
      expect(capturedBlobContent).toContain('"has ""quotes"", commas,\nand newlines"')
    })
  })

  describe('JSON export', () => {
    it('includes metadata wrapper with exported_at', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'sessions',
        data: [{ id: 1 }],
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.exported_at).toBeDefined()
      // exported_at should be an ISO string
      expect(new Date(parsed.exported_at).toISOString()).toBe(parsed.exported_at)
    })

    it('includes source field set to CCWAP Dashboard', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'sessions',
        data: [{ id: 1 }],
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.source).toBe('CCWAP Dashboard')
    })

    it('includes page field matching the provided page', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'cost-analysis',
        data: [{ id: 1 }],
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.page).toBe('cost-analysis')
    })

    it('includes record_count matching data length', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'sessions',
        data: [{ id: 1 }, { id: 2 }, { id: 3 }],
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.record_count).toBe(3)
    })

    it('includes the data array in the wrapper', () => {
      const { result } = renderHook(() => useExport())
      const data = [{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }]
      result.current.exportData('json', {
        page: 'sessions',
        data,
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.data).toEqual(data)
    })

    it('includes custom metadata when provided', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'sessions',
        data: [{ id: 1 }],
        metadata: { filter: 'last-30-days', user: 'test-user' },
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.filter).toBe('last-30-days')
      expect(parsed.user).toBe('test-user')
    })

    it('creates a blob with application/json content type', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'sessions',
        data: [{ id: 1 }],
      })

      expect(capturedBlobType).toBe('application/json')
    })

    it('produces pretty-printed JSON with 2-space indent', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'test',
        data: [{ id: 1 }],
      })

      // Pretty-printed JSON should contain newlines and 2-space indentation
      expect(capturedBlobContent).toContain('\n')
      expect(capturedBlobContent).toContain('  ')
      // Verify it round-trips correctly
      expect(() => JSON.parse(capturedBlobContent)).not.toThrow()
    })

    it('record_count is 0 when data is empty', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'test',
        data: [],
      })

      const parsed = JSON.parse(capturedBlobContent)
      expect(parsed.record_count).toBe(0)
    })
  })

  describe('empty data handling', () => {
    it('does not trigger download for CSV when data is empty', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [],
      })

      expect(mockCreateObjectURL).not.toHaveBeenCalled()
      expect(mockClick).not.toHaveBeenCalled()
    })

    it('still exports JSON even when data array is empty (wrapper has metadata)', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'test',
        data: [],
      })

      // JSON export does not guard against empty data (only CSV does)
      expect(mockCreateObjectURL).toHaveBeenCalled()
    })
  })

  describe('file naming', () => {
    it('follows ccwap-{page}-{YYYY-MM-DD}.csv pattern for CSV', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'sessions',
        data: [{ id: 1 }],
      })

      expect(capturedAnchor.download).toBe('ccwap-sessions-2026-02-05.csv')
    })

    it('follows ccwap-{page}-{YYYY-MM-DD}.json pattern for JSON', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('json', {
        page: 'cost-analysis',
        data: [{ id: 1 }],
      })

      expect(capturedAnchor.download).toBe('ccwap-cost-analysis-2026-02-05.json')
    })

    it('pads single-digit month and day with leading zeros', () => {
      vi.setSystemTime(new Date('2026-01-03T12:00:00Z'))
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ id: 1 }],
      })

      expect(capturedAnchor.download).toBe('ccwap-test-2026-01-03.csv')
    })
  })

  describe('download mechanism', () => {
    it('creates an object URL from the blob', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ id: 1 }],
      })

      expect(mockCreateObjectURL).toHaveBeenCalledTimes(1)
      const blob = mockCreateObjectURL.mock.calls[0][0] as Blob
      expect(blob).toBeInstanceOf(Blob)
    })

    it('sets the anchor href to the created object URL', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ id: 1 }],
      })

      expect(capturedAnchor.href).toBe('blob:mock-url')
    })

    it('clicks the anchor to trigger download', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ id: 1 }],
      })

      expect(mockClick).toHaveBeenCalledTimes(1)
    })

    it('appends and then removes the anchor from the document body', () => {
      // Reset counts since renderHook itself may call appendChild
      appendChildSpy.mockClear()
      removeChildSpy.mockClear()

      const { result } = renderHook(() => useExport())
      // Clear again after renderHook mounts its container
      appendChildSpy.mockClear()
      removeChildSpy.mockClear()

      result.current.exportData('csv', {
        page: 'test',
        data: [{ id: 1 }],
      })

      expect(appendChildSpy).toHaveBeenCalledTimes(1)
      expect(removeChildSpy).toHaveBeenCalledTimes(1)
    })

    it('revokes the object URL after download', () => {
      const { result } = renderHook(() => useExport())
      result.current.exportData('csv', {
        page: 'test',
        data: [{ id: 1 }],
      })

      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    })
  })
})
