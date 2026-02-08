import { useState, useEffect, useRef, useCallback } from 'react'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface WsMessage {
  type: string
  timestamp?: string
  files_processed?: number
  turns_inserted?: number
  tool_calls_inserted?: number
  entries_parsed?: number
  // active_session fields
  session_id?: string
  project_display?: string
  git_branch?: string
  // daily_cost_update fields
  cost_today?: number
  sessions_today?: number
}

interface UseWebSocketReturn {
  status: ConnectionStatus
  lastMessage: WsMessage | null
  messages: WsMessage[]
}

const MAX_MESSAGES = 100
const PING_INTERVAL = 30_000
const RECONNECT_BASE = 1_000
const RECONNECT_CAP = 30_000

export function useWebSocket(url: string): UseWebSocketReturn {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null)
  const [messages, setMessages] = useState<WsMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retriesRef = useRef(0)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current) return

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws
      setStatus('connecting')

      ws.onopen = () => {
        if (!mountedRef.current) return
        setStatus('connected')
        retriesRef.current = 0

        // Start heartbeat
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, PING_INTERVAL)
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const msg = JSON.parse(event.data) as WsMessage
          if (msg.type === 'pong') return

          setLastMessage(msg)
          setMessages(prev => {
            const next = [msg, ...prev]
            return next.length > MAX_MESSAGES ? next.slice(0, MAX_MESSAGES) : next
          })
        } catch {
          // Ignore non-JSON messages
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        cleanup()
        setStatus('disconnected')
        scheduleReconnect()
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        setStatus('error')
      }
    } catch {
      setStatus('error')
      scheduleReconnect()
    }
  }, [url])

  const cleanup = useCallback(() => {
    if (pingRef.current) {
      clearInterval(pingRef.current)
      pingRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current = null
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return
    const delay = Math.min(RECONNECT_BASE * Math.pow(2, retriesRef.current), RECONNECT_CAP)
    retriesRef.current++
    reconnectRef.current = setTimeout(() => {
      if (mountedRef.current) connect()
    }, delay)
  }, [connect])

  useEffect(() => {
    mountedRef.current = true
    connect()

    // Pause/resume based on page visibility
    const handleVisibility = () => {
      if (document.hidden) {
        // Don't disconnect, but stop reconnecting
      } else if (wsRef.current?.readyState !== WebSocket.OPEN) {
        connect()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      mountedRef.current = false
      document.removeEventListener('visibilitychange', handleVisibility)
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      cleanup()
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.close()
      }
    }
  }, [connect, cleanup])

  return { status, lastMessage, messages }
}
