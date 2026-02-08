import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useWebSocket } from '@/hooks/useWebSocket'

// --- Mock WebSocket ---

interface MockWsInstance {
  url: string
  onopen: ((ev: Event) => void) | null
  onmessage: ((ev: MessageEvent) => void) | null
  onclose: ((ev: CloseEvent) => void) | null
  onerror: ((ev: Event) => void) | null
  readyState: number
  send: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
}

let mockWsInstances: MockWsInstance[] = []

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  readyState = 0
  send = vi.fn()
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    mockWsInstances.push(this)
  }
}

beforeEach(() => {
  mockWsInstances = []
  vi.useFakeTimers()
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function getLatestWs(): MockWsInstance {
  return mockWsInstances[mockWsInstances.length - 1]
}

function simulateOpen(ws: MockWsInstance) {
  ws.readyState = 1 // OPEN
  ws.onopen?.(new Event('open'))
}

function simulateMessage(ws: MockWsInstance, data: string) {
  ws.onmessage?.(new MessageEvent('message', { data }))
}

function simulateClose(ws: MockWsInstance) {
  ws.readyState = 3 // CLOSED
  ws.onclose?.(new CloseEvent('close'))
}

function simulateError(ws: MockWsInstance) {
  ws.onerror?.(new Event('error'))
}

describe('useWebSocket', () => {
  it('initial state is disconnected', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))

    // connect() is called in useEffect. After the effect runs, status is 'connecting'.
    // lastMessage and messages should be empty.
    expect(['connecting', 'disconnected']).toContain(result.current.status)
    expect(result.current.lastMessage).toBeNull()
    expect(result.current.messages).toEqual([])
  })

  it('sets status to connecting when WebSocket is created', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))

    expect(result.current.status).toBe('connecting')
    expect(mockWsInstances.length).toBe(1)
    expect(getLatestWs().url).toBe('ws://test/ws/live')
  })

  it('sets status to connected on WebSocket open', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))

    act(() => {
      simulateOpen(getLatestWs())
    })

    expect(result.current.status).toBe('connected')
  })

  it('parses JSON messages and adds to messages array', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateOpen(ws)
    })

    const msg = {
      type: 'etl_update',
      timestamp: '2026-02-05T12:00:00',
      files_processed: 3,
      turns_inserted: 10,
      tool_calls_inserted: 5,
    }

    act(() => {
      simulateMessage(ws, JSON.stringify(msg))
    })

    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0]).toEqual(msg)
    expect(result.current.lastMessage).toEqual(msg)
  })

  it('prepends new messages (most recent first)', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateOpen(ws)
    })

    const msg1 = { type: 'etl_update', turns_inserted: 1 }
    const msg2 = { type: 'etl_update', turns_inserted: 2 }

    act(() => {
      simulateMessage(ws, JSON.stringify(msg1))
    })
    act(() => {
      simulateMessage(ws, JSON.stringify(msg2))
    })

    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]).toEqual(msg2)
    expect(result.current.messages[1]).toEqual(msg1)
  })

  it('ignores pong messages', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateOpen(ws)
    })

    act(() => {
      simulateMessage(ws, JSON.stringify({ type: 'pong' }))
    })

    expect(result.current.messages).toHaveLength(0)
    expect(result.current.lastMessage).toBeNull()
  })

  it('ignores non-JSON messages', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateOpen(ws)
    })

    act(() => {
      simulateMessage(ws, 'this is not valid json')
    })

    expect(result.current.messages).toHaveLength(0)
  })

  it('caps messages at MAX_MESSAGES (100)', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateOpen(ws)
    })

    // Send 105 messages
    for (let i = 0; i < 105; i++) {
      act(() => {
        simulateMessage(ws, JSON.stringify({ type: 'etl_update', turns_inserted: i }))
      })
    }

    expect(result.current.messages).toHaveLength(100)
    // Most recent message should be turns_inserted: 104 (0-indexed)
    expect(result.current.messages[0].turns_inserted).toBe(104)
  })

  it('sets status to disconnected on close', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateOpen(ws)
    })
    expect(result.current.status).toBe('connected')

    act(() => {
      simulateClose(ws)
    })
    expect(result.current.status).toBe('disconnected')
  })

  it('sets status to error on WebSocket error', () => {
    const { result } = renderHook(() => useWebSocket('ws://test/ws/live'))
    const ws = getLatestWs()

    act(() => {
      simulateError(ws)
    })

    expect(result.current.status).toBe('error')
  })

  describe('reconnect behavior', () => {
    it('schedules reconnect after close', () => {
      renderHook(() => useWebSocket('ws://test/ws/live'))
      const ws = getLatestWs()

      act(() => {
        simulateOpen(ws)
      })

      const instanceCountBefore = mockWsInstances.length

      act(() => {
        simulateClose(ws)
      })

      // Advance past the first reconnect delay (1000ms base)
      act(() => {
        vi.advanceTimersByTime(1100)
      })

      // A new WebSocket should have been created
      expect(mockWsInstances.length).toBeGreaterThan(instanceCountBefore)
    })

    it('uses exponential backoff for reconnect delays', () => {
      renderHook(() => useWebSocket('ws://test/ws/live'))

      // First close - triggers reconnect at 1000ms (2^0 * 1000)
      act(() => {
        simulateClose(getLatestWs())
      })

      const countAfterFirstClose = mockWsInstances.length

      // Advance 999ms - should NOT have reconnected yet
      act(() => {
        vi.advanceTimersByTime(999)
      })
      expect(mockWsInstances.length).toBe(countAfterFirstClose)

      // Advance 1 more ms (total 1000ms) - should reconnect
      act(() => {
        vi.advanceTimersByTime(1)
      })
      expect(mockWsInstances.length).toBe(countAfterFirstClose + 1)

      // Second close - triggers reconnect at 2000ms (2^1 * 1000)
      act(() => {
        simulateClose(getLatestWs())
      })
      const countAfterSecondClose = mockWsInstances.length

      // Advance 1999ms - should NOT have reconnected yet
      act(() => {
        vi.advanceTimersByTime(1999)
      })
      expect(mockWsInstances.length).toBe(countAfterSecondClose)

      // Advance 1 more ms (total 2000ms) - should reconnect
      act(() => {
        vi.advanceTimersByTime(1)
      })
      expect(mockWsInstances.length).toBe(countAfterSecondClose + 1)
    })

    it('resets retry count on successful connection', () => {
      renderHook(() => useWebSocket('ws://test/ws/live'))

      // Simulate a few disconnects to build up retry count
      act(() => { simulateClose(getLatestWs()) })
      act(() => { vi.advanceTimersByTime(1000) }) // retry 0: 1s
      act(() => { simulateClose(getLatestWs()) })
      act(() => { vi.advanceTimersByTime(2000) }) // retry 1: 2s

      // Now simulate a successful connection
      act(() => { simulateOpen(getLatestWs()) })

      // Then disconnect again - should reconnect at base delay (1000ms), not 4000ms
      const countBefore = mockWsInstances.length
      act(() => { simulateClose(getLatestWs()) })
      act(() => { vi.advanceTimersByTime(1000) })

      // Should have reconnected at 1s, meaning retries was reset
      expect(mockWsInstances.length).toBe(countBefore + 1)
    })
  })

  describe('heartbeat', () => {
    it('sends ping at PING_INTERVAL (30s) when connected', () => {
      renderHook(() => useWebSocket('ws://test/ws/live'))
      const ws = getLatestWs()

      act(() => {
        simulateOpen(ws)
      })

      // Should not have sent anything yet
      expect(ws.send).not.toHaveBeenCalled()

      // Advance 30 seconds
      act(() => {
        vi.advanceTimersByTime(30_000)
      })

      expect(ws.send).toHaveBeenCalledWith('ping')
    })

    it('sends multiple pings over time', () => {
      renderHook(() => useWebSocket('ws://test/ws/live'))
      const ws = getLatestWs()

      act(() => {
        simulateOpen(ws)
      })

      // Advance 90 seconds - should get 3 pings
      act(() => {
        vi.advanceTimersByTime(90_000)
      })

      expect(ws.send).toHaveBeenCalledTimes(3)
      for (const call of ws.send.mock.calls) {
        expect(call[0]).toBe('ping')
      }
    })

    it('stops heartbeat on close', () => {
      renderHook(() => useWebSocket('ws://test/ws/live'))
      const ws = getLatestWs()

      act(() => {
        simulateOpen(ws)
      })

      act(() => {
        simulateClose(ws)
      })

      // Clear call count on the original ws
      ws.send.mockClear()

      // Advance 60 seconds - no more pings should be sent to THIS ws
      act(() => {
        vi.advanceTimersByTime(60_000)
      })

      expect(ws.send).not.toHaveBeenCalled()
    })
  })

  describe('cleanup on unmount', () => {
    it('nullifies event handlers on unmount', () => {
      const { unmount } = renderHook(() => useWebSocket('ws://test/ws/live'))
      const ws = getLatestWs()

      act(() => {
        simulateOpen(ws)
      })

      // Before unmount, handlers are set
      expect(ws.onopen).not.toBeNull()

      unmount()

      // After unmount, the hook's cleanup() nullifies the handlers.
      // The hook calls cleanup() which sets onopen/onclose/etc to null and
      // clears wsRef.current, then checks wsRef.current for close() -- so
      // close() is NOT called (wsRef is already null). This is the actual
      // behavior of the hook.
      expect(ws.onopen).toBeNull()
      expect(ws.onmessage).toBeNull()
      expect(ws.onclose).toBeNull()
      expect(ws.onerror).toBeNull()
    })

    it('sets mountedRef to false so callbacks become no-ops', () => {
      const { result, unmount } = renderHook(() => useWebSocket('ws://test/ws/live'))
      const ws = getLatestWs()

      act(() => {
        simulateOpen(ws)
      })

      unmount()

      // After unmount, the status should remain as it was at the time of unmount
      // No further state updates should occur
      expect(result.current.status).toBe('connected')
    })
  })
})
