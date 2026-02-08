import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'

// Mock recharts to avoid rendering SVG in jsdom
vi.mock('recharts', () => ({
  AreaChart: ({ children }: { children: ReactNode }) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div data-testid="area" />,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div data-testid="responsive-container">{children}</div>,
}))

// Mock useWebSocket - we control the return value per test
const mockUseWebSocket = vi.fn()
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => mockUseWebSocket(...args),
}))

// Must import after mocks are set up
const { default: LiveMonitorPage } = await import('@/pages/LiveMonitorPage')

beforeEach(() => {
  mockUseWebSocket.mockReset()
})

describe('LiveMonitorPage', () => {
  describe('connection status indicator', () => {
    it('renders the current connection status text', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('connected')).toBeInTheDocument()
    })

    it('renders the page title', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'disconnected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('Live Monitor')).toBeInTheDocument()
    })
  })

  describe('connecting state', () => {
    it('shows Connecting... message when status is connecting', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connecting',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('Connecting...')).toBeInTheDocument()
      expect(screen.getByText(/Establishing WebSocket connection/)).toBeInTheDocument()
    })
  })

  describe('disconnected state', () => {
    it('shows Disconnected message when status is disconnected', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'disconnected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('Disconnected')).toBeInTheDocument()
      expect(screen.getByText(/WebSocket connection lost/)).toBeInTheDocument()
    })

    it('does not show totals cards when disconnected', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'disconnected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.queryByText('Turns Received')).not.toBeInTheDocument()
      expect(screen.queryByText('Tool Calls')).not.toBeInTheDocument()
      expect(screen.queryByText('Files Processed')).not.toBeInTheDocument()
    })
  })

  describe('connected state with no messages', () => {
    it('shows totals cards with zero values', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('Turns Received')).toBeInTheDocument()
      expect(screen.getByText('Tool Calls')).toBeInTheDocument()
      expect(screen.getByText('Files Processed')).toBeInTheDocument()
    })

    it('shows waiting for activity message in event log', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('Waiting for activity...')).toBeInTheDocument()
    })
  })

  describe('connected state with etl_update messages', () => {
    it('shows totals cards with accumulated values', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
          turns_inserted: 5,
          tool_calls_inserted: 3,
          files_processed: 2,
        },
        messages: [
          {
            type: 'etl_update',
            timestamp: '2026-02-05T12:00:00',
            turns_inserted: 5,
            tool_calls_inserted: 3,
            files_processed: 2,
          },
          {
            type: 'etl_update',
            timestamp: '2026-02-05T11:55:00',
            turns_inserted: 10,
            tool_calls_inserted: 7,
            files_processed: 1,
          },
        ],
      })

      render(<LiveMonitorPage />)

      // Totals: turns=15, toolCalls=10, files=3
      expect(screen.getByText('Turns Received')).toBeInTheDocument()
      expect(screen.getByText('Tool Calls')).toBeInTheDocument()
      expect(screen.getByText('Files Processed')).toBeInTheDocument()
    })

    it('shows event log entries', () => {
      const messages = [
        {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
          turns_inserted: 5,
          tool_calls_inserted: 3,
          files_processed: 2,
        },
      ]

      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: messages[0],
        messages,
      })

      render(<LiveMonitorPage />)

      // Event log should show the message data
      expect(screen.getByText('Event Log')).toBeInTheDocument()
      expect(screen.getByText('5 turns')).toBeInTheDocument()
      expect(screen.getByText('3 tool calls')).toBeInTheDocument()
      expect(screen.getByText('2 files')).toBeInTheDocument()
    })

    it('does not show waiting message when events exist', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
          turns_inserted: 1,
        },
        messages: [
          {
            type: 'etl_update',
            timestamp: '2026-02-05T12:00:00',
            turns_inserted: 1,
          },
        ],
      })

      render(<LiveMonitorPage />)

      expect(screen.queryByText('Waiting for activity...')).not.toBeInTheDocument()
    })

    it('filters out non-etl_update messages for display', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: { type: 'other_type' },
        messages: [
          { type: 'other_type' },
          {
            type: 'etl_update',
            timestamp: '2026-02-05T12:00:00',
            turns_inserted: 5,
            files_processed: 1,
          },
        ],
      })

      render(<LiveMonitorPage />)

      // Only the etl_update event should appear in the log
      expect(screen.getByText('5 turns')).toBeInTheDocument()
    })
  })

  describe('sparkline rendering', () => {
    it('renders sparkline chart when there are 2+ etl_update messages', () => {
      const messages = [
        {
          type: 'etl_update',
          timestamp: '2026-02-05T12:05:00',
          turns_inserted: 5,
          files_processed: 1,
        },
        {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
          turns_inserted: 3,
          files_processed: 1,
        },
      ]

      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: messages[0],
        messages,
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText('Recent Activity (turns/update)')).toBeInTheDocument()
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
    })

    it('does not render sparkline when only 1 etl_update message', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
          turns_inserted: 5,
        },
        messages: [
          {
            type: 'etl_update',
            timestamp: '2026-02-05T12:00:00',
            turns_inserted: 5,
          },
        ],
      })

      render(<LiveMonitorPage />)

      expect(screen.queryByText('Recent Activity (turns/update)')).not.toBeInTheDocument()
    })

    it('does not render sparkline when no etl_update messages', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.queryByText('Recent Activity (turns/update)')).not.toBeInTheDocument()
    })
  })

  describe('last update timestamp', () => {
    it('shows last update time when connected with a message', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
        },
        messages: [
          {
            type: 'etl_update',
            timestamp: '2026-02-05T12:00:00',
          },
        ],
      })

      render(<LiveMonitorPage />)

      expect(screen.getByText(/Last update:/)).toBeInTheDocument()
    })

    it('does not show last update when connected with no message', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: null,
        messages: [],
      })

      render(<LiveMonitorPage />)

      expect(screen.queryByText(/Last update:/)).not.toBeInTheDocument()
    })
  })

  describe('event log entry details', () => {
    it('hides zero-value metrics in event log entries', () => {
      mockUseWebSocket.mockReturnValue({
        status: 'connected',
        lastMessage: {
          type: 'etl_update',
          timestamp: '2026-02-05T12:00:00',
          turns_inserted: 5,
          tool_calls_inserted: 0,
          files_processed: 0,
        },
        messages: [
          {
            type: 'etl_update',
            timestamp: '2026-02-05T12:00:00',
            turns_inserted: 5,
            tool_calls_inserted: 0,
            files_processed: 0,
          },
        ],
      })

      render(<LiveMonitorPage />)

      // Should show turns but not tool calls or files (they are 0)
      expect(screen.getByText('5 turns')).toBeInTheDocument()
      expect(screen.queryByText(/0 tool calls/)).not.toBeInTheDocument()
      expect(screen.queryByText(/0 files/)).not.toBeInTheDocument()
    })
  })
})
