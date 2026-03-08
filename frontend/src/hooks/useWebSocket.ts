'use client'
/**
 * WebSocket 커스텀 훅
 * 실시간 데이터 스트림 구독
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8002'

interface WebSocketMessage<T = unknown> {
  type: string
  data: T
}

interface UseWebSocketOptions {
  reconnectInterval?: number   // 재연결 간격 (ms)
  maxReconnectAttempts?: number
}

export function useWebSocket<T = unknown>(
  channel: string,
  options: UseWebSocketOptions = {},
) {
  const { reconnectInterval = 3000, maxReconnectAttempts = 5 } = options

  const [lastMessage, setLastMessage] = useState<WebSocketMessage<T> | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCount = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(`${WS_URL}/ws/${channel}`)

      ws.onopen = () => {
        setIsConnected(true)
        setError(null)
        reconnectCount.current = 0
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const message = JSON.parse(event.data as string) as WebSocketMessage<T>
          setLastMessage(message)
        } catch {
          // JSON 파싱 오류 무시
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null

        // 재연결 시도
        if (reconnectCount.current < maxReconnectAttempts) {
          reconnectCount.current++
          reconnectTimer.current = setTimeout(connect, reconnectInterval)
        } else {
          setError(`WebSocket 연결 실패: ${channel}`)
        }
      }

      ws.onerror = () => {
        setError(`WebSocket 오류: ${channel}`)
      }

      wsRef.current = ws

    } catch (err) {
      setError(`WebSocket 초기화 오류: ${err}`)
    }
  }, [channel, reconnectInterval, maxReconnectAttempts])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  return { lastMessage, isConnected, error }
}
