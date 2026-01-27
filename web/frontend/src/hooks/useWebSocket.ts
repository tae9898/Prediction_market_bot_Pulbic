import { useEffect, useRef, useState, useCallback } from 'react'
import type { WebSocketMessage, StateUpdate } from '@/api/types'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void
  onStateUpdate?: (state: StateUpdate) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  enabled?: boolean
}

interface UseWebSocketReturn {
  isConnected: boolean
  lastMessage: WebSocketMessage | null
  sendMessage: (message: any) => void
  sendCommand: (command: string, data?: Record<string, any>) => void
  reconnect: () => void
}

export function useWebSocket({
  onMessage,
  onStateUpdate,
  onConnect,
  onDisconnect,
  reconnectInterval = 3000,
  enabled = true,
}: UseWebSocketOptions = {}): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()
  const messageHandlersRef = useRef({ onMessage, onStateUpdate, onConnect, onDisconnect })

  // Update refs when callbacks change
  useEffect(() => {
    messageHandlersRef.current = { onMessage, onStateUpdate, onConnect, onDisconnect }
  }, [onMessage, onStateUpdate, onConnect, onDisconnect])

  const connect = useCallback(() => {
    if (!enabled) return

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        messageHandlersRef.current.onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          setLastMessage(message)

          // Handle state updates
          if (message.type === 'state_update' && message.data) {
            messageHandlersRef.current.onStateUpdate?.(message.data as StateUpdate)
          }

          messageHandlersRef.current.onMessage?.(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        messageHandlersRef.current.onDisconnect?.()

        // Attempt to reconnect
        if (enabled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
  }, [enabled, reconnectInterval])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const reconnect = useCallback(() => {
    disconnect()
    connect()
  }, [disconnect, connect])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const sendCommand = useCallback((command: string, data?: Record<string, any>) => {
    sendMessage({ command, ...data })
  }, [sendMessage])

  // Connect on mount
  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    isConnected,
    lastMessage,
    sendMessage,
    sendCommand,
    reconnect,
  }
}

export default useWebSocket
